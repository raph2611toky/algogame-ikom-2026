from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from collections import Counter

from app.domain.enums import (
    CLOCKWISE,
    COUNTER_CLOCKWISE,
    HACK_ACTIONS,
    MOVE_ACTIONS,
    PUSH_ACTIONS,
    DIRECTION_VECTORS,
    ORIENTATION_TO_DIRECTION,
    HeroAction,
    HeroId,
    MachineKind,
    Orientation,
)
from app.domain.models import GameState, Position
from app.engine.machine_planner import MachineControlPlan, plan_machine_to_obstacle, plan_machine_to_position
from app.engine.rules import Rules
from app.engine.score_pathfinding import find_score_path, score_cost_units
from app.engine.strategy_v4 import MachineTask
from app.engine.strategy_v9 import StrategicRelayPortfolioStrategy


@dataclass(slots=True)
class _MachineCommitment:
    """Petit plan machine garde entre plusieurs ticks.

    Important: ce n'est PAS un nouveau planner. Il memorise uniquement le plan
    que le planner v8/v9 vient deja de choisir afin d'eviter qu'un autre sous-plan
    annule sa rotation au tick suivant.
    """

    hero_id: HeroId
    machine_id: str
    purpose: str
    target: Position
    actions: list[HeroAction]
    created_tick: int
    expected_position: Position
    expected_orientation: Orientation
    pending_target: Position | None = None


@dataclass(frozen=True, slots=True)
class _MachineHazard:
    machine_id: str
    risk: int
    decisions_until: int
    chest_from: Position | None
    chest_to: Position | None
    reason: str
    intercept_positions: tuple[Position, ...] = ()


class OpportunityCommittedPortfolioStrategy(StrategicRelayPortfolioStrategy):
    """portfolio_v10 = portfolio_v9 + corrections ciblees d'orchestration.

    Le coeur v8/v9 est conserve: plans de coffres, relais stamina, score peak,
    carried_stones, safe release, règles et pathfinding ne sont pas remplaces.

    Ajouts uniquement lorsque les coffres NE sont PAS directement accessibles:
    1. opportunite de deblocage partagee entre plusieurs coffres;
    2. priorite aux obstacles communs quand plusieurs coffres en profitent;
    3. commitment d'un micro-plan de machine deja choisi;
    4. anti-oscillation CW<->CCW sans progression;
    5. resolution prudente d'un deadlock X/G;
    6. un heros non necessaire au deblocage peut reprendre les pierres en parallele.
    """

    DEADLOCK_TICKS = 4
    ROTATION_FLIP_LIMIT = 2
    ROTATION_COOLDOWN_TICKS = 2
    AUTONOMOUS_HAZARD_HORIZON = 24
    AUTONOMOUS_HAZARD_CRITICAL = 50000
    AUTONOMOUS_HAZARD_HIGH = 20000

    def __init__(
        self,
        *,
        max_stones_per_hero: int = 16,
        max_chest_pairs_per_hero: int = 24,
        stuck_end_threshold: int = 24,
        max_unlock_checks: int = 40,
    ) -> None:
        super().__init__(
            max_stones_per_hero=max_stones_per_hero,
            max_chest_pairs_per_hero=max_chest_pairs_per_hero,
            stuck_end_threshold=stuck_end_threshold,
            max_unlock_checks=max_unlock_checks,
        )
        # Les cartes <=160 cellules restent confiees a portfolio_v9 comme
        # reference de non-regression. Les ajouts v10 ciblent les cartes plus
        # complexes qui ont revele les conflits de corridors/machines.
        self._v9_reference = StrategicRelayPortfolioStrategy(
            max_stones_per_hero=max_stones_per_hero,
            max_chest_pairs_per_hero=max_chest_pairs_per_hero,
            stuck_end_threshold=stuck_end_threshold,
            max_unlock_checks=max_unlock_checks,
        )
        self._machine_commitments: dict[HeroId, _MachineCommitment] = {}
        self._opportunity_signature: tuple[object, ...] | None = None
        self._opportunity_target: Position | None = None
        self._obstacle_support_cache: dict[Position, int] = {}
        self._deadlock_ticks = 0
        self._rotation_state: dict[str, tuple[Position, tuple[object, ...], HeroAction, int]] = {}
        self._rotation_block_until: dict[str, int] = {}
        self._machine_task_cache: dict[tuple[object, ...], list[MachineTask]] = {}
        self._profile_cache_signature: tuple[object, ...] | None = None
        self._profile_cache: dict[Position, object] = {}
        self._hazard_cache: dict[tuple[object, ...], _MachineHazard | None] = {}
        self._defense_intercepts: dict[HeroId, tuple[str, Position]] = {}
        self._defense_miss_ticks: dict[HeroId, int] = {}

    # ------------------------------------------------------------------
    # Opportunite partagee: activee uniquement apres echec des plans directs.
    # ------------------------------------------------------------------

    def _viable_profiles(self, state: GameState):
        # Les besoins structurels d'un coffre ne changent pas quand F/M font un
        # simple pas. v4 inclut volontairement les positions des heros dans la cle
        # de _unlock_profile; sur une 15x20 cela peut relancer plusieurs planners
        # couteux chaque tick. v10 garde donc UN profil structurel par topologie,
        # sans modifier le cache historique de v8/v9. Les plans directs, eux, sont
        # toujours recalcules sur l'etat courant avant d'arriver ici.
        signature = self._topology_signature(state)
        use_structural_cache = state.game_map.height * state.game_map.width > 160
        if use_structural_cache and signature == self._profile_cache_signature:
            return dict(self._profile_cache)
        self._refresh_impossible(state)
        profiles = {}
        for chest in sorted(state.chests):
            if chest in self._impossible_chests:
                continue
            profile = self._unlock_profile(state, chest)
            if profile.structurally_possible:
                profiles[chest] = profile
        if use_structural_cache:
            self._profile_cache_signature = signature
            self._profile_cache = dict(profiles)
        return profiles

    def _current_obstacle_sets(self, state: GameState, profile) -> tuple[set[Position], set[Position]]:
        return set(profile.holes) & set(state.holes), set(profile.trees) & set(state.trees)

    def _refresh_opportunity_cache(self, state: GameState) -> None:
        signature = self._topology_signature(state)
        if signature == self._opportunity_signature:
            return
        self._opportunity_signature = signature
        self._opportunity_target = None
        profiles = self._viable_profiles(state)
        support: Counter[Position] = Counter()
        for profile in profiles.values():
            holes, trees = self._current_obstacle_sets(state, profile)
            support.update(holes)
            support.update(trees)
        self._obstacle_support_cache = dict(support)

    def _machine_cost_estimate(self, state: GameState, hero_id: HeroId, obstacles: set[Position]) -> int:
        if not obstacles:
            return 0
        kind = MachineKind.EXCAVATOR if hero_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        machines = [m for m in state.machines.values() if m.kind == kind]
        if not machines:
            return 100000
        hero = state.heroes[hero_id]
        total = 0
        for obstacle in obstacles:
            total += min(
                hero.position.manhattan(machine.position)
                + 2 * machine.position.manhattan(obstacle)
                + 2
                for machine in machines
            )
        return total

    def _opportunity_rank(self, state: GameState, chest: Position, profiles) -> tuple[object, ...]:
        profile = profiles[chest]
        holes, trees = self._current_obstacle_sets(state, profile)
        removal = holes | trees
        if not removal:
            # En pratique les plans directs sont traites avant _select_target_chest.
            return (-10_000_000, 0, 0, 0, chest.row, chest.col)

        # Valeurs en quarts de point, coherentes avec score_cost_units:
        # un coffre complet = 150*4 = 600 unites.
        direct_after = 0
        partial_progress = 0
        helped_chests = 0
        for other_chest, other_profile in profiles.items():
            oh, ot = self._current_obstacle_sets(state, other_profile)
            before = oh | ot
            if not before:
                continue
            remaining = before - removal
            reduction = len(before) - len(remaining)
            if reduction <= 0:
                continue
            helped_chests += 1
            if not remaining:
                direct_after += 1
            elif other_chest != chest:
                # Une ouverture partagee qui retire un obstacle du futur coffre a
                # une vraie valeur, mais inferieure aux 150 points d'un coffre fini.
                partial_progress += reduction

        shared_edges = sum(max(0, self._obstacle_support_cache.get(obstacle, 1) - 1) for obstacle in removal)
        cost = (
            self._machine_cost_estimate(state, HeroId.IKOTOFOSA, holes)
            + self._machine_cost_estimate(state, HeroId.IMAHAKI, trees)
            + 4 * len(removal)
        )
        # Le candidat vise toujours au moins son propre coffre (600). Un deuxieme
        # coffre rendu direct vaut aussi 600. La progression partielle est volontairement
        # prudente (15 points = 60 unites par obstacle partage).
        projected_units = direct_after * 600 + partial_progress * 60 + shared_edges * 20
        utility = projected_units - cost
        hero_distance = min(hero.position.manhattan(chest) for hero in state.heroes.values())
        return (
            -utility,
            -direct_after,
            -helped_chests,
            -shared_edges,
            cost,
            len(removal),
            hero_distance,
            chest.row,
            chest.col,
        )

    def _select_target_chest(self, state: GameState) -> Position | None:
        # La logique directe reste strictement celle de v8/v9. Cette methode n'est
        # normalement appelee qu'apres _direct_collaborative_actions == None.
        self._refresh_opportunity_cache(state)
        profiles = self._viable_profiles(state)
        if len(profiles) < 2:
            return super()._select_target_chest(state)

        # Si aucun obstacle n'est partage, conserver exactement le choix v8/v9.
        if not any(count >= 2 for count in self._obstacle_support_cache.values()):
            return super()._select_target_chest(state)

        if self._opportunity_target in state.chests and self._opportunity_target in profiles:
            self._target_chest = self._opportunity_target
            return self._opportunity_target

        candidates = [(self._opportunity_rank(state, chest, profiles), chest) for chest in profiles]
        candidates.sort(key=lambda item: item[0])
        if not candidates:
            return super()._select_target_chest(state)
        self._opportunity_target = candidates[0][1]
        self._target_chest = self._opportunity_target
        return self._opportunity_target

    def _machine_tasks_for(self, state: GameState, hero_id: HeroId, obstacles, *, ignore_other_machines: bool = False):
        obstacle_list = list(obstacles)
        if len(state.chests) >= 2:
            self._refresh_opportunity_cache(state)
            if any(value >= 2 for value in self._obstacle_support_cache.values()):
                obstacle_list.sort(
                    key=lambda p: (
                        -self._obstacle_support_cache.get(p, 1),
                        min((m.position.manhattan(p) for m in state.machines.values()), default=9999),
                        p.row,
                        p.col,
                    )
                )
                # Deux obstacles suffisent pour choisir la prochaine action. On
                # replanifiera apres chaque changement reel de topologie.
                obstacle_list = obstacle_list[:2]

        cache_key = (
            id(state),
            state.elapsed,
            hero_id.value,
            bool(ignore_other_machines),
            tuple(sorted((p.row, p.col) for p in obstacle_list)),
        )
        cached = self._machine_task_cache.get(cache_key)
        if cached is not None:
            return list(cached)

        tasks = super()._machine_tasks_for(
            state,
            hero_id,
            obstacle_list,
            ignore_other_machines=ignore_other_machines,
        )
        if len(state.chests) >= 2 and any(value >= 2 for value in self._obstacle_support_cache.values()):
            tasks.sort(
                key=lambda task: (
                    -self._obstacle_support_cache.get(task.obstacle, 1),
                    0 if state.heroes[hero_id].hacking_machine_id == task.machine_id else 1,
                    0 if task.approach is None else task.approach.ticks,
                    task.total_cost_units,
                    task.total_ticks,
                    task.obstacle.row,
                    task.obstacle.col,
                    task.machine_id,
                )
            )
        self._machine_task_cache[cache_key] = list(tasks)
        if len(self._machine_task_cache) > 256:
            # Les id d'etat precedents ne servent plus apres quelques ticks.
            self._machine_task_cache = {
                key: value for key, value in self._machine_task_cache.items()
                if key[1] >= state.elapsed - 2
            }
        return tasks

    # ------------------------------------------------------------------
    # Expansion des prerequis croises, bornee pour eviter les recherches
    # combinatoires sur les cartes 15x20+.
    # ------------------------------------------------------------------

    def _bounded_cross_prerequisites(
        self,
        state: GameState,
        hero_id: HeroId,
        obstacle: Position,
    ) -> set[Position] | None:
        # Un task direct signifie qu'aucun prerequis croise n'est necessaire.
        if self._task_exists(state, hero_id, obstacle):
            return set()

        opposite = set(state.trees if hero_id == HeroId.IKOTOFOSA else state.holes)
        if not opposite:
            return None

        # Les blocages croises d'une machine sont locaux: arbre devant/lateral de X,
        # trou devant/lateral de G, ou obstacle pres du corridor immediat. On evite
        # volontairement la minimisation exhaustive historique qui pouvait tester
        # tous les arbres/trous de la carte pendant des minutes.
        nearby = sorted(
            (p for p in opposite if p.manhattan(obstacle) <= 3),
            key=lambda p: (p.manhattan(obstacle), p.row, p.col),
        )
        if nearby:
            return set(nearby[:4])

        # Fallback prudent: un seul obstacle oppose le plus proche. S'il n'etait
        # finalement pas necessaire, le prochain replan l'eliminera naturellement.
        nearest = min(opposite, key=lambda p: (p.manhattan(obstacle), p.row, p.col))
        return {nearest}

    def _expanded_unlock_obstacles(self, state: GameState, profile):
        holes = set(profile.holes) & set(state.holes)
        trees = set(profile.trees) & set(state.trees)
        self._refresh_opportunity_cache(state)

        # Quand plusieurs coffres partagent un corridor, traiter d'abord ce noyau.
        # Les obstacles uniques restent dans le profil et seront repris apres la
        # modification de topologie suivante.
        if len(state.chests) >= 2 and any(v >= 2 for v in self._obstacle_support_cache.values()):
            shared_holes = {p for p in holes if self._obstacle_support_cache.get(p, 1) >= 2}
            shared_trees = {p for p in trees if self._obstacle_support_cache.get(p, 1) >= 2}
            if shared_holes or shared_trees:
                holes = shared_holes or holes
                trees = shared_trees or trees

        for _ in range(2):
            changed = False
            for hole in sorted(holes):
                if self._task_exists(state, HeroId.IKOTOFOSA, hole):
                    continue
                prereq = self._bounded_cross_prerequisites(state, HeroId.IKOTOFOSA, hole)
                if prereq:
                    before = len(trees)
                    trees.update(prereq & set(state.trees))
                    changed = changed or len(trees) != before
            for tree in sorted(trees):
                if self._task_exists(state, HeroId.IMAHAKI, tree):
                    continue
                prereq = self._bounded_cross_prerequisites(state, HeroId.IMAHAKI, tree)
                if prereq:
                    before = len(holes)
                    holes.update(prereq & set(state.holes))
                    changed = changed or len(holes) != before
            if not changed:
                break
        return holes, trees

    def _staging_task_for(self, state: GameState, hero_id: HeroId, obstacles: set[Position]) -> MachineTask | None:
        hero = state.heroes[hero_id]
        kind = MachineKind.EXCAVATOR if hero_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        self._refresh_opportunity_cache(state)
        ordered_obstacles = sorted(
            obstacles,
            key=lambda p: (-self._obstacle_support_cache.get(p, 1), p.row, p.col),
        )[:3]
        candidates: list[MachineTask] = []
        for obstacle in ordered_obstacles:
            prerequisites = self._bounded_cross_prerequisites(state, hero_id, obstacle)
            if prerequisites is None:
                continue
            hypothetical = (
                self._copy_without(state, set(), prerequisites)
                if hero_id == HeroId.IKOTOFOSA
                else self._copy_without(state, prerequisites, set())
            )
            for machine in sorted(state.machines.values(), key=lambda m: m.id):
                if machine.kind != kind:
                    continue
                if machine.is_hacked and machine.hacked_by != hero_id:
                    continue
                if hero.is_hacking and hero.hacking_machine_id != machine.id:
                    continue
                machine_hyp = hypothetical.machines[machine.id]
                control = plan_machine_to_obstacle(
                    hypothetical,
                    machine_hyp,
                    obstacle,
                    max_expansions=9000,
                    ignore_other_machines=True,
                )
                if control is None:
                    continue
                if hero.is_hacking:
                    approach = None
                    hack_ticks = 0
                    hack_battery = 0
                else:
                    approach = find_score_path(state, hero_id, machine.position, max_expansions=12000)
                    if approach is None:
                        continue
                    hack_ticks = 1
                    hack_battery = 1
                battery = control.battery_cost + hack_battery
                if battery > hero.battery:
                    continue
                approach_ticks = 0 if approach is None else approach.ticks
                approach_stamina = 0 if approach is None else approach.total_stamina_cost
                total_ticks = approach_ticks + hack_ticks + control.ticks
                if total_ticks > state.remaining_time:
                    continue
                cost = score_cost_units(total_ticks, approach_stamina, battery)
                candidates.append(MachineTask(hero_id, machine.id, obstacle, approach, control, total_ticks, cost))
        if not candidates:
            return None
        candidates.sort(
            key=lambda task: (
                -self._obstacle_support_cache.get(task.obstacle, 1),
                task.total_ticks,
                task.total_cost_units,
                task.machine_id,
                task.obstacle.row,
                task.obstacle.col,
            )
        )
        return candidates[0]

    # ------------------------------------------------------------------
    # Micro-plans machines: commit du plan deja choisi par v8/v9.
    # ------------------------------------------------------------------

    @staticmethod
    def _active_control_actions(plan: MachineControlPlan) -> list[HeroAction]:
        # WAIT de machine_planner represente la latence du HACK_MOVE / coupe arbre.
        # On la gere dynamiquement avec pending_move/tree, pour verifier le vrai etat.
        return [action for action in plan.actions if action != HeroAction.WAIT]

    def _install_commitment(
        self,
        state: GameState,
        hero_id: HeroId,
        machine_id: str,
        purpose: str,
        target: Position,
        plan: MachineControlPlan,
    ) -> _MachineCommitment | None:
        actions = self._active_control_actions(plan)
        if not actions:
            return None
        machine = state.machines[machine_id]
        commitment = _MachineCommitment(
            hero_id=hero_id,
            machine_id=machine_id,
            purpose=purpose,
            target=target,
            actions=actions,
            created_tick=state.elapsed,
            expected_position=machine.position,
            expected_orientation=machine.orientation,
        )
        self._machine_commitments[hero_id] = commitment
        return commitment

    def _drop_commitment(self, hero_id: HeroId) -> None:
        self._machine_commitments.pop(hero_id, None)

    def _commitment_target_done(self, state: GameState, commitment: _MachineCommitment) -> bool:
        machine = state.machines.get(commitment.machine_id)
        if machine is None:
            return True
        if commitment.purpose == "hole":
            return commitment.target not in state.holes
        if commitment.purpose == "tree":
            return commitment.target not in state.trees
        if commitment.purpose in {"staging", "relocation", "deadlock"}:
            return machine.position == commitment.target and not machine.pending_move
        return False

    def _continue_commitment(self, state: GameState, hero_id: HeroId) -> HeroAction | None:
        commitment = self._machine_commitments.get(hero_id)
        if commitment is None:
            return None
        hero = state.heroes[hero_id]
        if not hero.is_hacking or hero.hacking_machine_id != commitment.machine_id:
            self._drop_commitment(hero_id)
            return None
        machine = state.machines[commitment.machine_id]
        if self._commitment_target_done(state, commitment):
            self._drop_commitment(hero_id)
            return None
        if hero.battery <= 0:
            self._drop_commitment(hero_id)
            return None

        # Une transition HACK_MOVE est en vol: ne surtout pas replanifier/retourner.
        if machine.pending_move:
            return HeroAction.WAIT
        if machine.kind == MachineKind.GRAPPLER and machine.position in state.trees:
            return HeroAction.WAIT
        if commitment.pending_target is not None:
            if machine.position != commitment.pending_target:
                self._drop_commitment(hero_id)
                return None
            commitment.expected_position = machine.position
            commitment.pending_target = None

        if machine.position != commitment.expected_position or machine.orientation != commitment.expected_orientation:
            self._drop_commitment(hero_id)
            return None
        if not commitment.actions:
            self._drop_commitment(hero_id)
            return None

        action = commitment.actions[0]
        if action == HeroAction.HACK_MOVE:
            if not Rules.machine_forward_queueable(state, machine):
                self._drop_commitment(hero_id)
                return None
            commitment.actions.pop(0)
            commitment.pending_target = Rules.machine_forward(machine)
            return action
        if action == HeroAction.HACK_CW:
            commitment.actions.pop(0)
            commitment.expected_orientation = CLOCKWISE[machine.orientation]
            return action
        if action == HeroAction.HACK_CCW:
            commitment.actions.pop(0)
            commitment.expected_orientation = COUNTER_CLOCKWISE[machine.orientation]
            return action
        if action == HeroAction.HACK_FILL:
            forward = Rules.machine_forward(machine)
            if machine.kind != MachineKind.EXCAVATOR or forward not in state.holes:
                self._drop_commitment(hero_id)
                return None
            commitment.actions.pop(0)
            return action
        if action == HeroAction.HACK_CUT:
            cut = machine.position if machine.position in state.trees else Rules.machine_forward(machine)
            if machine.kind != MachineKind.GRAPPLER or cut not in state.trees:
                self._drop_commitment(hero_id)
                return None
            commitment.actions.pop(0)
            return action

        self._drop_commitment(hero_id)
        return None

    def _action_for_machine_task(self, state: GameState, task: MachineTask) -> HeroAction:
        hero = state.heroes[task.hero_id]
        if hero.is_hacking:
            committed = self._continue_commitment(state, task.hero_id)
            if committed is not None:
                return committed
            machine = state.machines[task.machine_id]
            if hero.hacking_machine_id != machine.id:
                return HeroAction.WAIT
            plan = plan_machine_to_obstacle(state, machine, task.obstacle, max_expansions=30000)
            if plan is None or not plan.actions:
                return HeroAction.WAIT
            purpose = "hole" if machine.kind == MachineKind.EXCAVATOR else "tree"
            commitment = self._install_commitment(state, task.hero_id, machine.id, purpose, task.obstacle, plan)
            if commitment is not None:
                action = self._continue_commitment(state, task.hero_id)
                if action is not None:
                    return action
        return super()._action_for_machine_task(state, task)

    def _action_for_staging_task(self, state: GameState, task: MachineTask) -> HeroAction:
        hero = state.heroes[task.hero_id]
        if hero.is_hacking:
            committed = self._continue_commitment(state, task.hero_id)
            if committed is not None:
                return committed
            machine = state.machines[task.machine_id]
            if hero.hacking_machine_id == machine.id and task.control.actions:
                commitment = self._install_commitment(
                    state,
                    task.hero_id,
                    machine.id,
                    "staging",
                    task.control.target,
                    task.control,
                )
                if commitment is not None:
                    action = self._continue_commitment(state, task.hero_id)
                    if action is not None:
                        return action
        return super()._action_for_staging_task(state, task)

    def _relocation_plan(
        self,
        state: GameState,
        controller_id: HeroId,
        partner_obstacles: set[Position],
    ) -> tuple[Position, MachineControlPlan] | None:
        controller = state.heroes[controller_id]
        if not controller.is_hacking or controller.hacking_machine_id is None or not partner_obstacles:
            return None
        machine = state.machines[controller.hacking_machine_id]
        partner_id = self._other(controller_id)
        partner_kind = MachineKind.EXCAVATOR if partner_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        partner_machines = [m for m in state.machines.values() if m.kind == partner_kind]
        close = []
        for partner_machine in partner_machines:
            if partner_machine.id == machine.id:
                continue
            direction = Rules.machine_forward(partner_machine)
            # Reproduit le test de buffer v8, sans changer sa regle.
            dr = direction.row - partner_machine.position.row
            dc = direction.col - partner_machine.position.col
            cell1 = direction
            cell2 = cell1.moved(dr, dc)
            cell3 = cell2.moved(dr, dc)
            blocks = machine.position in {cell1, cell2}
            if not blocks and machine.position == cell3 and (cell1 in state.chests or cell2 in state.chests):
                blocks = True
            if blocks:
                close.append(partner_machine)
        if not close or machine.pending_move or controller.battery <= 0:
            return None
        if machine.kind == MachineKind.GRAPPLER and machine.position in state.trees:
            return None

        positions = [
            pos
            for pos in state.game_map.all_positions()
            if 1 <= machine.position.manhattan(pos) <= 2 and pos not in state.game_map.rocks
        ]
        positions.sort(
            key=lambda pos: (
                -min((pos.manhattan(m.position) for m in close), default=0),
                -min((pos.manhattan(o) for o in partner_obstacles), default=0),
                machine.position.manhattan(pos),
                pos.row,
                pos.col,
            )
        )
        best = None
        for target in positions[:10]:
            control = plan_machine_to_position(state, machine, target, max_expansions=5000)
            if control is None or not control.actions or control.battery_cost > controller.battery:
                continue
            rank = (
                control.ticks,
                control.score_cost_units,
                -min(target.manhattan(m.position) for m in close),
                target.row,
                target.col,
            )
            if best is None or rank < best[0]:
                best = (rank, target, control)
        if best is None:
            return None
        return best[1], best[2]

    def _partner_relocation_action(self, state: GameState, controller_id: HeroId, partner_obstacles: set[Position]) -> HeroAction | None:
        committed = self._continue_commitment(state, controller_id)
        if committed is not None:
            return committed
        plan = self._relocation_plan(state, controller_id, partner_obstacles)
        if plan is None:
            return None
        target, control = plan
        hero = state.heroes[controller_id]
        if hero.hacking_machine_id is None:
            return None
        commitment = self._install_commitment(
            state,
            controller_id,
            hero.hacking_machine_id,
            "relocation",
            target,
            control,
        )
        if commitment is None:
            return None
        return self._continue_commitment(state, controller_id)

    # ------------------------------------------------------------------
    # Hero libre pendant un deblocage: pierres en parallele si sa competence
    # n'est pas requise par le coffre actif.
    # ------------------------------------------------------------------

    def _unlock_actions(self, state: GameState, chest: Position) -> dict[HeroId, HeroAction]:
        """Ordre v8 conserve, avec short-circuit d'un micro-plan deja engage.

        Sans ce short-circuit, v8 recalcule d'abord staging/relocation a chaque tick
        avant d'arriver a l'action, ce qui peut etre tres couteux et peut surtout
        changer d'avis pendant un plan deja commence.
        """
        if state.game_map.height * state.game_map.width > 160:
            profiles = self._viable_profiles(state)
            profile = profiles.get(chest)
            if profile is None:
                profile = self._unlock_profile(state, chest)
        else:
            profile = self._unlock_profile(state, chest)
        remaining_holes, remaining_trees = self._expanded_unlock_obstacles(state, profile)
        decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
        assignments = (
            (HeroId.IKOTOFOSA, set(remaining_holes)),
            (HeroId.IMAHAKI, set(remaining_trees)),
        )
        unresolved: dict[HeroId, set[Position]] = {}

        # 0) Un micro-plan engage a priorite sur tout nouveau replan de CETTE machine.
        for hero_id, obstacles in assignments:
            committed = self._continue_commitment(state, hero_id)
            if committed is not None:
                decisions[hero_id] = committed
                unresolved[hero_id] = set()
                self.last_decisions[hero_id.value] = "continuer micro-plan machine engage"
            else:
                unresolved[hero_id] = set(obstacles)

        # 1) Meme priorite v8: une tache directe vers son obstacle avant staging/relocation.
        for hero_id, _obstacles in assignments:
            if decisions[hero_id] != HeroAction.WAIT:
                continue
            obstacles = unresolved.get(hero_id, set())
            if not obstacles:
                continue
            tasks = self._machine_tasks_for(state, hero_id, obstacles)
            if tasks:
                task = tasks[0]
                decisions[hero_id] = self._action_for_machine_task(state, task)
                label = "remplir trou" if hero_id == HeroId.IKOTOFOSA else "couper arbre"
                self.last_decisions[hero_id.value] = f"{label} ({task.obstacle.row},{task.obstacle.col}) avec {task.machine_id}"
                unresolved[hero_id] = set()

        # 2) Meme staging v8, mais borne et engage.
        for hero_id, _obstacles in assignments:
            if decisions[hero_id] != HeroAction.WAIT:
                continue
            obstacles = unresolved.get(hero_id, set())
            if not obstacles:
                continue
            staging = self._staging_task_for(state, hero_id, obstacles)
            if staging is not None:
                decisions[hero_id] = self._action_for_staging_task(state, staging)
                self.last_decisions[hero_id.value] = (
                    f"prepositionner {staging.machine_id} pour obstacle "
                    f"({staging.obstacle.row},{staging.obstacle.col})"
                )
                unresolved[hero_id] = set()

        # 3) Relocation du partenaire en dernier recours, comme v8.
        partner_obstacles = {
            HeroId.IKOTOFOSA: set(remaining_trees),
            HeroId.IMAHAKI: set(remaining_holes),
        }
        for controller_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            if decisions[controller_id] != HeroAction.WAIT:
                continue
            if not unresolved.get(controller_id, set()):
                continue
            relocation = self._partner_relocation_action(state, controller_id, partner_obstacles[controller_id])
            if relocation is not None:
                decisions[controller_id] = relocation
                kind = "Excavator" if controller_id == HeroId.IKOTOFOSA else "Grappler"
                self.last_decisions[controller_id.value] = f"repositionner {kind} pour liberer le partenaire"
                unresolved[controller_id] = set()

        # 4) Si la competence d'un heros n'est pas requise par CE deblocage, il
        # peut collecter une pierre en parallele (ou preparer une relache sure).
        required = {
            HeroId.IKOTOFOSA: bool(remaining_holes),
            HeroId.IMAHAKI: bool(remaining_trees),
        }
        reserved: set[tuple[object, ...]] = set()
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            if required[hero_id] or decisions[hero_id] != HeroAction.WAIT:
                continue
            hero = state.heroes[hero_id]
            if hero.is_hacking:
                release = self._prepare_machine_release(state, hero_id, chest)
                if release is not None:
                    decisions[hero_id] = release
                    continue
            action, key, desc = self._best_stone_action_for_hero(state, hero_id, reserved=reserved)
            if key is not None:
                if hero.is_hacking and action not in MOVE_ACTIONS:
                    continue
                decisions[hero_id] = action
                reserved.add(key)
                self.last_decisions[hero_id.value] = f"deblocage non requis: {desc}"

        for hero_id, obstacles in assignments:
            if hero_id.value not in self.last_decisions:
                self.last_decisions[hero_id.value] = (
                    "attendre deblocage partenaire" if remaining_holes or remaining_trees else "coffre bientot accessible"
                )
        return decisions

    # ------------------------------------------------------------------
    # Protection globale des coffres contre les machines autonomes.
    #
    # v8 securisait deja l'orientation AVANT UNHACK sur un horizon court. Sur
    # les grandes cartes, une machine peut toutefois parcourir 10-20 cases,
    # pivoter automatiquement puis pousser un AUTRE coffre vers un bord/trou.
    # On ajoute ici une prediction bornee, sans toucher au planner v8/v9.
    # ------------------------------------------------------------------

    @staticmethod
    def _is_non_bush_boundary(state: GameState, pos: Position) -> bool:
        if pos in state.game_map.bushes:
            return False
        return (
            pos.row == 0
            or pos.col == 0
            or pos.row == state.game_map.height - 1
            or pos.col == state.game_map.width - 1
        )

    def _hazard_signature(
        self,
        state: GameState,
        machine_id: str,
        orientation: Orientation | None = None,
    ) -> tuple[object, ...]:
        machine = state.machines[machine_id]
        return (
            machine_id,
            machine.position.row,
            machine.position.col,
            (orientation or machine.orientation).value,
            machine.steps_since_dig,
            tuple(sorted((p.row, p.col) for p in state.chests)),
            tuple(sorted((p.row, p.col) for p in state.holes)),
            tuple(sorted((p.row, p.col) for p in state.trees)),
            tuple(
                sorted(
                    (
                        other.id,
                        other.position.row,
                        other.position.col,
                        other.orientation.value,
                        bool(other.is_hacked),
                    )
                    for other in state.machines.values()
                    if other.id != machine_id
                )
            ),
        )

    def _predict_autonomous_hazard(
        self,
        state: GameState,
        machine_id: str,
        *,
        orientation: Orientation | None = None,
        horizon: int | None = None,
    ) -> _MachineHazard | None:
        """Simule seulement la routine automatique de la machine concernee.

        Le modele reproduit les rotations auto X=CCW / G=CW, le DIG tous les 5
        deplacements auto de X, le CUT de G et les poussees de coffre. Les autres
        machines restent a leur position actuelle: c'est volontairement prudent
        et surtout borne (<=24 decisions), donc exploitable a chaque tick.
        """
        machine_real = state.machines.get(machine_id)
        if machine_real is None:
            return None
        horizon = horizon or self.AUTONOMOUS_HAZARD_HORIZON
        signature = (self._hazard_signature(state, machine_id, orientation), int(horizon))
        if signature in self._hazard_cache:
            return self._hazard_cache[signature]

        simulation = deepcopy(state)
        machine = simulation.machines[machine_id]
        machine.hacked_by = None
        machine.pending_move = False
        machine.auto_move_pending = False
        machine.resume_delay = 0
        if orientation is not None:
            machine.orientation = orientation

        result: _MachineHazard | None = None
        trace: list[Position] = [machine.position]
        for decision_index in range(1, horizon + 1):
            # Automatic CUT consumes this decision before the next move.
            if machine.kind == MachineKind.GRAPPLER and machine.position in simulation.trees:
                simulation.trees.remove(machine.position)
                continue

            # Automatic DIG of an unhacked Excavator every five successful moves.
            if machine.kind == MachineKind.EXCAVATOR and machine.steps_since_dig >= 5:
                simulation.holes.add(machine.position)
                machine.steps_since_dig = 0
                # Creuser directement sur une case critique adjacente a un coffre
                # est un risque secondaire; la poussee vers ce trou sera detectee
                # ensuite comme critique si la machine revient dans cet axe.
                continue

            if Rules.machine_buffer_reason(simulation, machine) is not None:
                machine.orientation = (
                    COUNTER_CLOCKWISE[machine.orientation]
                    if machine.kind == MachineKind.EXCAVATOR
                    else CLOCKWISE[machine.orientation]
                )
                continue

            target = Rules.machine_forward(machine)
            if not Rules.machine_cell_passable(simulation, machine, target):
                machine.orientation = (
                    COUNTER_CLOCKWISE[machine.orientation]
                    if machine.kind == MachineKind.EXCAVATOR
                    else CLOCKWISE[machine.orientation]
                )
                continue

            if target in simulation.chests:
                direction = ORIENTATION_TO_DIRECTION[machine.orientation]
                dr, dc = DIRECTION_VECTORS[direction]
                destination = target.moved(dr, dc)

                blocked = (
                    not simulation.game_map.in_bounds(destination)
                    or destination in simulation.game_map.rocks
                    or destination in simulation.trees
                    or destination in simulation.chests
                    or simulation.machine_at(destination) is not None
                )
                if blocked:
                    machine.orientation = (
                        COUNTER_CLOCKWISE[machine.orientation]
                        if machine.kind == MachineKind.EXCAVATOR
                        else CLOCKWISE[machine.orientation]
                    )
                    continue

                if destination in simulation.holes:
                    result = _MachineHazard(
                        machine_id,
                        100000,
                        decision_index,
                        target,
                        destination,
                        "coffre pousse dans un trou",
                        tuple(dict.fromkeys(reversed(trace[-10:]))),
                    )
                    break

                # Une cachette est un bon resultat et ne doit jamais etre bloquee.
                simulation.chests.remove(target)
                if destination in simulation.game_map.bushes:
                    machine.position = target
                    if machine.kind == MachineKind.EXCAVATOR:
                        machine.steps_since_dig += 1
                    continue

                simulation.chests.add(destination)

                # Pousser un coffre sur un bord non-cachette peut le rendre
                # structurellement impossible a ramener vers l'interieur (cas de
                # la regression 15x20: (13,1)->(14,1)).
                if self._is_non_bush_boundary(simulation, destination):
                    result = _MachineHazard(
                        machine_id,
                        90000,
                        decision_index,
                        target,
                        destination,
                        "coffre pousse vers un bord non recuperable",
                        tuple(dict.fromkeys(reversed(trace[-10:]))),
                    )
                    break

                before = min((target.manhattan(b) for b in simulation.game_map.bushes), default=0)
                after = min((destination.manhattan(b) for b in simulation.game_map.bushes), default=0)
                if after >= before + 4:
                    # Degradation importante mais pas necessairement fatale.
                    result = _MachineHazard(
                        machine_id,
                        25000,
                        decision_index,
                        target,
                        destination,
                        "coffre fortement eloigne d'une cachette",
                        tuple(dict.fromkeys(reversed(trace[-10:]))),
                    )
                    break

            machine.position = target
            trace.append(machine.position)
            if machine.kind == MachineKind.EXCAVATOR:
                machine.steps_since_dig += 1

        self._hazard_cache[signature] = result
        if len(self._hazard_cache) > 512:
            # La topologie/position machine rend les anciennes cles inutiles.
            self._hazard_cache.clear()
            self._hazard_cache[signature] = result
        return result

    def _prepare_machine_release(self, state: GameState, hero_id: HeroId, chest: Position) -> HeroAction | None:
        # D'abord conserver toutes les protections v8.
        base = super()._prepare_machine_release(state, hero_id, chest)
        if base is not None:
            return base
        # Sur les cartes officielles/petites, conserver strictement la securite
        # v8. La prediction longue est reservee aux cartes complexes ou le roaming
        # de 20+ decisions a effectivement produit la regression observee.
        if state.game_map.height * state.game_map.width <= 160:
            return None

        hero = state.heroes[hero_id]
        if not hero.is_hacking or hero.hacking_machine_id is None or hero.battery <= 0:
            return None
        machine = state.machines[hero.hacking_machine_id]
        if machine.pending_move:
            return HeroAction.WAIT
        if machine.kind == MachineKind.GRAPPLER and machine.position in state.trees:
            return HeroAction.WAIT

        candidates: list[tuple[object, ...]] = []
        for candidate_orientation in Orientation:
            hazard = self._predict_autonomous_hazard(
                state,
                machine.id,
                orientation=candidate_orientation,
            )
            risk = 0 if hazard is None else hazard.risk
            urgency = self.AUTONOMOUS_HAZARD_HORIZON + 1 if hazard is None else hazard.decisions_until
            rotations, rotate_action = self._rotation_distance(machine.orientation, candidate_orientation)
            candidates.append(
                (
                    risk,
                    -urgency,
                    rotations,
                    candidate_orientation.value,
                    candidate_orientation,
                    rotate_action,
                )
            )
        candidates.sort()
        best_risk, _urgency, _rotations, _name, best_orientation, rotate_action = candidates[0]
        if best_orientation != machine.orientation and rotate_action is not None:
            return rotate_action
        if int(best_risk) >= self.AUTONOMOUS_HAZARD_CRITICAL:
            return HeroAction.WAIT
        return None

    def _defense_action(
        self,
        state: GameState,
        hero_id: HeroId,
        machine_id: str,
        intercept: Position,
    ) -> HeroAction | None:
        hero = state.heroes[hero_id]
        machine = state.machines.get(machine_id)
        if machine is None or machine.is_hacked:
            self._defense_intercepts.pop(hero_id, None)
            return None
        if hero.is_hacking:
            self._defense_intercepts.pop(hero_id, None)
            return None
        if hero.position == machine.position:
            return HeroAction.HACK
        if hero.position == intercept:
            # Embuscade: recuperer la stamina et attendre que la machine arrive.
            return HeroAction.WAIT
        path = find_score_path(state, hero_id, intercept, max_expansions=12000)
        if path is None or not path.steps:
            return None
        step = path.steps[0]
        if step.stamina_cost > hero.stamina:
            return HeroAction.WAIT
        return step.action

    def _best_intercept_for_hazard(
        self,
        state: GameState,
        hero_id: HeroId,
        machine_id: str,
        hazard: _MachineHazard,
    ) -> tuple[Position, int] | None:
        hero = state.heroes[hero_id]
        candidates: list[tuple[object, ...]] = []
        # Les positions les plus proches du danger sont testees en premier, mais
        # on accepte un point plus ancien si le heros peut l'atteindre nettement
        # avant la machine. Le point courant reste un fallback de poursuite.
        positions = list(hazard.intercept_positions)
        positions.append(state.machines[machine_id].position)
        seen: set[Position] = set()
        for index, target in enumerate(positions):
            if target in seen:
                continue
            seen.add(target)
            if hero.position == target:
                path_ticks = 0
            else:
                path = find_score_path(state, hero_id, target, max_expansions=12000)
                if path is None:
                    continue
                path_ticks = path.ticks
            # Plus le point est loin dans la trace (index eleve), plus la machine
            # l'atteindra tot. Pour rester prudent, on compare au danger global;
            # la reservation du heros est ensuite maintenue jusqu'a interception.
            danger_ticks = max(2, hazard.decisions_until * 2)
            if path_ticks > danger_ticks - 1:
                continue
            candidates.append((path_ticks, index, target.row, target.col, target, danger_ticks - path_ticks))
        if not candidates:
            return None
        # Favoriser un rendez-vous atteignable vite; en cas d'egalite, un point
        # proche du coffre menace (petit index dans la trace inversee).
        candidates.sort()
        _ticks, _idx, _r, _c, target, slack = candidates[0]
        return target, int(slack)

    def _protect_chests_from_autonomous_machines(
        self,
        state: GameState,
        decisions: dict[HeroId, HeroAction],
    ) -> None:
        """Intercepte une machine relachee avant une poussee catastrophique.

        Une fois l'interception choisie, elle est engagee sur plusieurs ticks:
        le heros ne repart pas vers un coffre/pierre au tick suivant. Cette petite
        reservation est essentielle sur les grandes cartes ou la machine fuit plus
        vite qu'une poursuite de sa position courante.
        """
        if state.game_map.height * state.game_map.width <= 160:
            return
        # 1) Continuer d'abord une interception deja engagee tant que le danger
        # existe. Cela evite que le coeur v8/v9 reprenne la main un tick sur deux.
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            existing = self._defense_intercepts.get(hero_id)
            if existing is None:
                continue
            machine_id, intercept = existing
            machine = state.machines.get(machine_id)
            if machine is None or machine.is_hacked:
                self._defense_intercepts.pop(hero_id, None)
                self._defense_miss_ticks.pop(hero_id, None)
                continue
            hazard = self._predict_autonomous_hazard(state, machine_id)
            if hazard is None or hazard.risk < self.AUTONOMOUS_HAZARD_CRITICAL:
                misses = self._defense_miss_ticks.get(hero_id, 0) + 1
                self._defense_miss_ticks[hero_id] = misses
                # DIG/CUT/rotation peut masquer la menace pendant un seul cycle
                # automatique. Garder quelques ticks l'embuscade evite un replan
                # global couteux et un abandon premature du rendez-vous.
                if misses > 3:
                    self._defense_intercepts.pop(hero_id, None)
                    self._defense_miss_ticks.pop(hero_id, None)
                    continue
                hazard = _MachineHazard(
                    machine_id,
                    self.AUTONOMOUS_HAZARD_CRITICAL,
                    1,
                    None,
                    None,
                    "menace autonome temporairement masquee",
                    (intercept,),
                )
            else:
                self._defense_miss_ticks.pop(hero_id, None)
            action = self._defense_action(state, hero_id, machine_id, intercept)
            if action is None:
                self._defense_intercepts.pop(hero_id, None)
                continue
            decisions[hero_id] = action
            self._direct_routes.pop(hero_id, None)
            self._hero_chest_targets.pop(hero_id, None)
            self.last_decisions[hero_id.value] = (
                f"proteger coffre: rendez-vous avec {machine_id} avant {hazard.reason}"
            )

        # 2) Detecter de nouvelles menaces pour les heros qui ne sont pas deja
        # reserves a une interception.
        threats: list[tuple[object, ...]] = []
        for machine in state.machines.values():
            if machine.is_hacked or not state.chests:
                continue
            hazard = self._predict_autonomous_hazard(state, machine.id)
            if hazard is None or hazard.risk < self.AUTONOMOUS_HAZARD_CRITICAL:
                continue
            hero_id = HeroId.IKOTOFOSA if machine.kind == MachineKind.EXCAVATOR else HeroId.IMAHAKI
            if hero_id in self._defense_intercepts:
                continue
            hero = state.heroes[hero_id]
            if hero.is_hacking:
                continue
            intercept_info = self._best_intercept_for_hazard(state, hero_id, machine.id, hazard)
            if intercept_info is None:
                continue
            intercept, slack = intercept_info
            threats.append(
                (
                    -hazard.risk,
                    slack,
                    hazard.decisions_until,
                    machine.id,
                    hero_id.value,
                    hero_id,
                    intercept,
                    hazard,
                )
            )

        if not threats:
            return
        threats.sort()
        _risk, slack, _steps, machine_id, _hero_name, hero_id, intercept, hazard = threats[0]
        current = decisions.get(hero_id, HeroAction.WAIT)
        if current in {HeroAction.HACK_FILL, HeroAction.HACK_CUT, HeroAction.HACK_MOVE}:
            return
        if current in PUSH_ACTIONS and slack > 3:
            # Un PUSH utile peut finir le coffre courant avant de partir proteger
            # l'autre; la menace sera reevaluee au tick suivant.
            return

        self._defense_intercepts[hero_id] = (machine_id, intercept)
        action = self._defense_action(state, hero_id, machine_id, intercept)
        if action is None:
            self._defense_intercepts.pop(hero_id, None)
            return
        decisions[hero_id] = action
        self._direct_routes.pop(hero_id, None)
        self._hero_chest_targets.pop(hero_id, None)
        self.last_decisions[hero_id.value] = (
            f"proteger coffre: intercepter {machine_id} a ({intercept.row},{intercept.col}) "
            f"avant {hazard.reason}"
        )

    def _active_defense_short_circuit(self, state: GameState) -> dict[HeroId, HeroAction] | None:
        """Evite un replan global pendant une embuscade deja engagee.

        Le coeur v8/v9 est appele pour CHOISIR l'interception initiale. Une fois F
        ou M reserve sur un point de rendez-vous, recalculer tous les coffres a
        chaque WAIT est a la fois inutile et tres couteux sur une 15x20.
        """
        if state.game_map.height * state.game_map.width <= 160:
            self._defense_intercepts.clear()
            self._defense_miss_ticks.clear()
            return None
        if not self._defense_intercepts:
            return None

        decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
        active = False
        reserved: set[tuple[object, ...]] = set()
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            existing = self._defense_intercepts.get(hero_id)
            if existing is None:
                continue
            machine_id, intercept = existing
            machine = state.machines.get(machine_id)
            if machine is None or machine.is_hacked:
                self._defense_intercepts.pop(hero_id, None)
                self._defense_miss_ticks.pop(hero_id, None)
                continue
            hazard = self._predict_autonomous_hazard(state, machine_id)
            if hazard is None or hazard.risk < self.AUTONOMOUS_HAZARD_CRITICAL:
                misses = self._defense_miss_ticks.get(hero_id, 0) + 1
                self._defense_miss_ticks[hero_id] = misses
                if misses > 3:
                    self._defense_intercepts.pop(hero_id, None)
                    self._defense_miss_ticks.pop(hero_id, None)
                    continue
            else:
                self._defense_miss_ticks.pop(hero_id, None)
            action = self._defense_action(state, hero_id, machine_id, intercept)
            if action is None:
                self._defense_intercepts.pop(hero_id, None)
                self._defense_miss_ticks.pop(hero_id, None)
                continue
            active = True
            decisions[hero_id] = action
            self.last_decisions[hero_id.value] = f"proteger coffre: embuscade engagee sur {machine_id}"

        if not active:
            return None

        # Le partenaire conserve un micro-plan machine deja engage. Sinon il peut
        # collecter les pierres pendant l'embuscade, ce qui respecte la logique de
        # collaboration demandee sans relancer le scheduler complet.
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            if hero_id in self._defense_intercepts:
                continue
            committed = self._continue_commitment(state, hero_id)
            if committed is not None:
                decisions[hero_id] = committed
                self.last_decisions[hero_id.value] = "continuer micro-plan pendant protection d'un coffre"
                continue
            hero = state.heroes[hero_id]
            if hero.is_hacking:
                focus = self._safe_release_focus(state, hero_id)
                if focus is not None:
                    release = self._prepare_machine_release(state, hero_id, focus)
                    if release is not None:
                        decisions[hero_id] = release
                        self.last_decisions[hero_id.value] = "maintenir/orienter machine pendant protection partenaire"
                        continue
            action, key, desc = self._best_stone_action_for_hero(state, hero_id, reserved=reserved)
            if key is not None:
                decisions[hero_id] = action
                reserved.add(key)
                self.last_decisions[hero_id.value] = f"protection partenaire: {desc}"
        return decisions

    # ------------------------------------------------------------------
    # Anti-oscillation + deadlock resolver, apres la decision v9.
    # ------------------------------------------------------------------

    @staticmethod
    def _inverse_rotation(action: HeroAction) -> HeroAction | None:
        if action == HeroAction.HACK_CW:
            return HeroAction.HACK_CCW
        if action == HeroAction.HACK_CCW:
            return HeroAction.HACK_CW
        return None

    def _rotation_guard(self, state: GameState, decisions: dict[HeroId, HeroAction]) -> None:
        topology = self._topology_signature(state)
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            hero = state.heroes[hero_id]
            if not hero.is_hacking or hero.hacking_machine_id is None:
                continue
            machine = state.machines[hero.hacking_machine_id]
            action = decisions.get(hero_id, HeroAction.WAIT)
            if action not in {HeroAction.HACK_CW, HeroAction.HACK_CCW}:
                if action in {HeroAction.HACK_MOVE, HeroAction.HACK_FILL, HeroAction.HACK_CUT}:
                    self._rotation_state.pop(machine.id, None)
                continue
            if state.elapsed < self._rotation_block_until.get(machine.id, -1):
                decisions[hero_id] = HeroAction.WAIT
                continue
            previous = self._rotation_state.get(machine.id)
            flips = 0
            if previous is not None:
                prev_pos, prev_topology, prev_action, prev_flips = previous
                if prev_pos == machine.position and prev_topology == topology and self._inverse_rotation(prev_action) == action:
                    flips = prev_flips + 1
            if flips >= self.ROTATION_FLIP_LIMIT:
                decisions[hero_id] = HeroAction.WAIT
                self._drop_commitment(hero_id)
                self._rotation_block_until[machine.id] = state.elapsed + self.ROTATION_COOLDOWN_TICKS
                self._target_selection_signature = None
                self._opportunity_signature = None
                self.last_decisions[hero_id.value] = "anti-oscillation machine: replan apres CW/CCW contradictoires"
                self._rotation_state[machine.id] = (machine.position, topology, action, flips)
                continue
            self._rotation_state[machine.id] = (machine.position, topology, action, flips)

    def _deadlock_resolver(self, state: GameState, decisions: dict[HeroId, HeroAction]) -> None:
        both_wait = all(decisions.get(hero_id, HeroAction.WAIT) == HeroAction.WAIT for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI))
        both_hacking = all(state.heroes[hero_id].is_hacking for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI))
        if not (both_wait and both_hacking and state.chests):
            self._deadlock_ticks = 0
            return
        self._deadlock_ticks += 1
        if self._deadlock_ticks < self.DEADLOCK_TICKS:
            return
        target = self._target_chest if self._target_chest in state.chests else None
        if target is None:
            return
        if state.game_map.height * state.game_map.width > 160:
            profiles = self._viable_profiles(state)
            profile = profiles.get(target)
            if profile is None:
                profile = self._unlock_profile(state, target)
        else:
            profile = self._unlock_profile(state, target)
        holes, trees = self._expanded_unlock_obstacles(state, profile)
        candidates = []
        for controller_id, partner_obstacles in (
            (HeroId.IKOTOFOSA, set(trees)),
            (HeroId.IMAHAKI, set(holes)),
        ):
            plan = self._relocation_plan(state, controller_id, partner_obstacles)
            if plan is None:
                continue
            relocation_target, control = plan
            candidates.append((control.ticks, control.score_cost_units, controller_id.value, controller_id, relocation_target, control))
        if not candidates:
            return
        candidates.sort()
        _ticks, _cost, _name, hero_id, relocation_target, control = candidates[0]
        hero = state.heroes[hero_id]
        if hero.hacking_machine_id is None:
            return
        self._drop_commitment(hero_id)
        commitment = self._install_commitment(
            state,
            hero_id,
            hero.hacking_machine_id,
            "deadlock",
            relocation_target,
            control,
        )
        if commitment is None:
            return
        action = self._continue_commitment(state, hero_id)
        if action is not None:
            decisions[hero_id] = action
            self.last_decisions[hero_id.value] = "resoudre deadlock machine partenaire via micro-plan engage"
            self._deadlock_ticks = 0

    def should_end(self, state: GameState) -> bool:
        if state.game_map.height * state.game_map.width <= 160:
            ended = self._v9_reference.should_end(state)
            self.stop_reason = getattr(self._v9_reference, "stop_reason", None)
            return ended
        return super().should_end(state)

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        if state.game_map.height * state.game_map.width <= 160:
            decisions = self._v9_reference.next_actions(state)
            self.last_decisions = dict(self._v9_reference.last_decisions)
            self.stop_reason = getattr(self._v9_reference, "stop_reason", None)
            return decisions
        defense = self._active_defense_short_circuit(state)
        if defense is not None:
            self._rotation_guard(state, defense)
            return defense
        decisions = super().next_actions(state)
        self._protect_chests_from_autonomous_machines(state, decisions)
        self._rotation_guard(state, decisions)
        self._deadlock_resolver(state, decisions)
        return decisions
