from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Iterable

from app.domain.enums import (
    CLOCKWISE,
    COUNTER_CLOCKWISE,
    DIRECTION_VECTORS,
    ORIENTATION_TO_DIRECTION,
    HeroAction,
    HeroId,
    MachineKind,
    MOVE_ACTIONS,
    PUSH_ACTIONS,
)
from app.domain.models import GameState, MachineState, Position
from app.engine.chest_planner import ChestPlan, plan_chest_to_bush
from app.engine.machine_planner import MachineControlPlan, plan_machine_to_obstacle, plan_machine_to_position
from app.engine.pathfinding import PathResult, hero_neighbors
from app.engine.rules import Rules
from app.engine.score_pathfinding import find_score_path, score_cost_units


@dataclass(frozen=True, slots=True)
class DirectChestPlan:
    hero_id: HeroId
    chest: Position
    bush: Position
    plan: ChestPlan

    @property
    def cost_key(self) -> tuple[int, int, int, str]:
        return (self.plan.ticks, self.plan.stamina_cost, self.chest.manhattan(self.bush), self.hero_id.value)


@dataclass(frozen=True, slots=True)
class UnlockProfile:
    chest: Position
    holes: frozenset[Position]
    trees: frozenset[Position]
    structurally_possible: bool

    @property
    def obstacle_count(self) -> int:
        return len(self.holes) + len(self.trees)


@dataclass(frozen=True, slots=True)
class MachineTask:
    hero_id: HeroId
    machine_id: str
    obstacle: Position
    approach: PathResult | None
    control: MachineControlPlan
    total_ticks: int
    total_cost_units: int


class ChestFirstPortfolioStrategy:
    def __init__(
        self,
        *,
        max_stones_per_hero: int = 16,
        max_chest_pairs_per_hero: int = 24,
        stuck_end_threshold: int = 16,
        max_unlock_checks: int = 32,
    ) -> None:
        self.max_stones_per_hero = max_stones_per_hero
        self.max_chest_pairs_per_hero = max_chest_pairs_per_hero
        self.stuck_end_threshold = stuck_end_threshold
        self.max_unlock_checks = max_unlock_checks
        self.stuck_ticks = 0
        self.last_decisions: dict[str, str] = {}
        self._target_chest: Position | None = None
        self._unlock_cache: dict[tuple[object, ...], UnlockProfile] = {}
        self._impossible_signature: tuple[object, ...] | None = None
        self._impossible_chests: set[Position] = set()

    def should_end(self, state: GameState) -> bool:
        if state.objectives_finished or state.remaining_time <= 0:
            return True
        if not self._has_pending_productive_goal(state):
            return True
        return self.stuck_ticks >= self.stuck_end_threshold

    @staticmethod
    def _state_topology_signature(state: GameState) -> tuple[object, ...]:
        def pts(items: Iterable[Position]) -> tuple[tuple[int, int], ...]:
            return tuple(sorted((p.row, p.col) for p in items))

        return (
            pts(state.chests),
            pts(state.holes),
            pts(state.trees),
            pts(state.stones),
            tuple(sorted((m.id, m.position.row, m.position.col, m.kind.value, m.hacked_by.value if m.hacked_by else None) for m in state.machines.values())),
        )

    @staticmethod
    def _copy_without(state: GameState, holes: Iterable[Position], trees: Iterable[Position]) -> GameState:
        copie = deepcopy(state)
        copie.holes.difference_update(holes)
        copie.trees.difference_update(trees)
        return copie

    def _direct_chest_plans(self, state: GameState, *, only_chest: Position | None = None) -> list[DirectChestPlan]:
        if not state.chests or not state.game_map.bushes:
            return []
        coffres = [only_chest] if only_chest is not None and only_chest in state.chests else sorted(state.chests)
        plans: list[DirectChestPlan] = []
        limite = max(6000, min(70000, state.game_map.height * state.game_map.width * 350))
        essais = 0
        for chest in coffres:
            for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
                hero = state.heroes[hero_id]
                bushes = sorted(state.game_map.bushes, key=lambda b: (chest.manhattan(b), hero.position.manhattan(chest), b.row, b.col))
                for bush in bushes:
                    if essais >= self.max_chest_pairs_per_hero * 2:
                        break
                    essais += 1
                    plan = plan_chest_to_bush(
                        state,
                        hero_id,
                        chest,
                        bush,
                        max_expansions=limite,
                        optimize_for_score=True,
                    )
                    if plan is not None and plan.actions:
                        plans.append(DirectChestPlan(hero_id, chest, bush, plan))
        plans.sort(key=lambda p: p.cost_key)
        return plans

    @staticmethod
    def _trace_required_obstacles(
        state: GameState,
        hero_id: HeroId,
        chest: Position,
        plan: ChestPlan,
    ) -> tuple[set[Position], set[Position]]:
        hero_pos = state.heroes[hero_id].position
        chest_pos = chest
        holes: set[Position] = set()
        trees: set[Position] = set()

        for action in plan.actions:
            if action in MOVE_ACTIONS:
                dr, dc = Rules.direction_delta(action)
                destination = hero_pos.moved(dr, dc)
                if destination in state.holes:
                    holes.add(destination)
                if destination in state.trees:
                    trees.add(destination)
                hero_pos = destination
                continue
            if action in PUSH_ACTIONS:
                dr, dc = Rules.direction_delta(action)
                destination = chest_pos.moved(dr, dc)
                if destination in state.holes:
                    holes.add(destination)
                if destination in state.trees:
                    trees.add(destination)
                hero_pos = chest_pos
                chest_pos = destination
        return holes, trees

    def _best_direct_after_removals(
        self,
        state: GameState,
        chest: Position,
        holes: set[Position],
        trees: set[Position],
    ) -> DirectChestPlan | None:
        hypothetique = self._copy_without(state, holes, trees)
        plans = self._direct_chest_plans(hypothetique, only_chest=chest)
        return plans[0] if plans else None

    def _unlock_profile(self, state: GameState, chest: Position) -> UnlockProfile:
        signature = (
            chest.row,
            chest.col,
            tuple(sorted((p.row, p.col) for p in state.holes)),
            tuple(sorted((p.row, p.col) for p in state.trees)),
            tuple(sorted((p.row, p.col) for p in state.chests if p != chest)),
            tuple(sorted((p.row, p.col) for p in state.game_map.bushes)),
            tuple((hid.value, state.heroes[hid].position.row, state.heroes[hid].position.col) for hid in (HeroId.IKOTOFOSA, HeroId.IMAHAKI)),
        )
        cached = self._unlock_cache.get(signature)
        if cached is not None:
            return cached

        direct = self._direct_chest_plans(state, only_chest=chest)
        if direct:
            profile = UnlockProfile(chest, frozenset(), frozenset(), True)
            self._unlock_cache[signature] = profile
            return profile

        all_holes = set(state.holes)
        all_trees = set(state.trees)
        completely_open = self._best_direct_after_removals(state, chest, all_holes, all_trees)
        if completely_open is None:
            profile = UnlockProfile(chest, frozenset(), frozenset(), False)
            self._unlock_cache[signature] = profile
            return profile

        needed_holes, needed_trees = self._trace_required_obstacles(
            state,
            completely_open.hero_id,
            chest,
            completely_open.plan,
        )
        if self._best_direct_after_removals(state, chest, needed_holes, needed_trees) is None:
            needed_holes = set(all_holes)
            needed_trees = set(all_trees)

        checks = 0
        changed = True
        while changed and checks < self.max_unlock_checks:
            changed = False
            ordered = sorted(
                [("hole", p) for p in needed_holes] + [("tree", p) for p in needed_trees],
                key=lambda item: (item[1].manhattan(chest), item[0], item[1].row, item[1].col),
                reverse=True,
            )
            for kind, obstacle in ordered:
                if checks >= self.max_unlock_checks:
                    break
                checks += 1
                trial_holes = set(needed_holes)
                trial_trees = set(needed_trees)
                if kind == "hole":
                    trial_holes.discard(obstacle)
                else:
                    trial_trees.discard(obstacle)
                if self._best_direct_after_removals(state, chest, trial_holes, trial_trees) is not None:
                    needed_holes, needed_trees = trial_holes, trial_trees
                    changed = True

        profile = UnlockProfile(chest, frozenset(needed_holes), frozenset(needed_trees), True)
        self._unlock_cache[signature] = profile
        return profile

    def _unlock_operationally_possible(self, state: GameState, profile: UnlockProfile) -> bool:
        if not profile.structurally_possible:
            return False
        if not profile.holes and not profile.trees:
            return True
        holes, trees = self._expanded_unlock_obstacles(state, profile)
        for hole in holes:
            if self._task_exists(state, HeroId.IKOTOFOSA, hole):
                continue
            if self._cross_prerequisites(state, HeroId.IKOTOFOSA, hole) is None:
                return False
        for tree in trees:
            if self._task_exists(state, HeroId.IMAHAKI, tree):
                continue
            if self._cross_prerequisites(state, HeroId.IMAHAKI, tree) is None:
                return False
        return True

    def _refresh_impossible(self, state: GameState) -> None:
        signature = (
            tuple(sorted((p.row, p.col) for p in state.chests)),
            tuple(sorted((p.row, p.col) for p in state.game_map.bushes)),
            tuple(sorted((p.row, p.col) for p in state.game_map.rocks)),
            tuple(sorted((p.row, p.col) for p in state.holes)),
            tuple(sorted((p.row, p.col) for p in state.trees)),
        )
        if signature == self._impossible_signature:
            return
        self._impossible_signature = signature
        self._impossible_chests = set()
        for chest in sorted(state.chests):
            profile = self._unlock_profile(state, chest)
            if not self._unlock_operationally_possible(state, profile):
                self._impossible_chests.add(chest)

    def _select_target_chest(self, state: GameState) -> Position | None:
        self._refresh_impossible(state)

        direct = self._direct_chest_plans(state)
        if direct:
            self._target_chest = direct[0].chest
            return self._target_chest

        if self._target_chest in state.chests and self._target_chest not in self._impossible_chests:
            return self._target_chest

        candidats: list[tuple[int, int, int, Position]] = []
        for chest in sorted(state.chests):
            if chest in self._impossible_chests:
                continue
            profile = self._unlock_profile(state, chest)
            if not profile.structurally_possible:
                continue
            hero_distance = min(h.position.manhattan(chest) for h in state.heroes.values())
            candidats.append((profile.obstacle_count, hero_distance, chest.row * state.game_map.width + chest.col, chest))
        if not candidats:
            self._target_chest = None
            return None
        candidats.sort()
        self._target_chest = candidats[0][3]
        return self._target_chest

    @staticmethod
    def _first_direct_action(state: GameState, item: DirectChestPlan) -> HeroAction:
        hero = state.heroes[item.hero_id]
        action = item.plan.actions[0]
        if action in MOVE_ACTIONS:
            movement = Rules.hero_move(state, hero, action)
            if not movement.valid or movement.stamina_cost > hero.stamina:
                return HeroAction.WAIT
        if action in PUSH_ACTIONS:
            push = Rules.chest_push(state, hero, action)
            if not push.valid or not Rules.hero_chest_push_safe_this_tick(state, push) or hero.stamina < 5:
                return HeroAction.WAIT
        return action

    def structurally_solvable_chest_count(self, state: GameState) -> int:
        self._refresh_impossible(state)
        return sum(1 for chest in state.chests if chest not in self._impossible_chests)

    @staticmethod
    def _compatible_kind(hero_id: HeroId) -> MachineKind:
        return MachineKind.EXCAVATOR if hero_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER

    def _machine_tasks_for(
        self,
        state: GameState,
        hero_id: HeroId,
        obstacles: Iterable[Position],
        *,
        ignore_other_machines: bool = False,
    ) -> list[MachineTask]:
        hero = state.heroes[hero_id]
        if hero.battery <= 0:
            return []
        kind = self._compatible_kind(hero_id)
        tasks: list[MachineTask] = []
        for obstacle in obstacles:
            for machine in sorted(state.machines.values(), key=lambda m: m.id):
                if machine.kind != kind:
                    continue
                if machine.is_hacked and machine.hacked_by != hero_id:
                    continue
                if hero.is_hacking and hero.hacking_machine_id != machine.id:
                    continue
                control = plan_machine_to_obstacle(state, machine, obstacle, max_expansions=30000, ignore_other_machines=ignore_other_machines)
                if control is None:
                    continue
                if hero.is_hacking:
                    approach = None
                    hack_ticks = 0
                    hack_battery = 0
                else:
                    approach = find_score_path(state, hero_id, machine.position, max_expansions=30000)
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
                tasks.append(MachineTask(hero_id, machine.id, obstacle, approach, control, total_ticks, cost))
        tasks.sort(key=lambda t: (t.total_ticks, t.total_cost_units, t.obstacle.row, t.obstacle.col, t.machine_id))
        return tasks

    def _task_exists(
        self,
        state: GameState,
        hero_id: HeroId,
        obstacle: Position,
        *,
        structural: bool = False,
    ) -> bool:
        return bool(self._machine_tasks_for(
            state,
            hero_id,
            (obstacle,),
            ignore_other_machines=structural,
        ))

    def _cross_prerequisites(
        self,
        state: GameState,
        hero_id: HeroId,
        obstacle: Position,
    ) -> set[Position] | None:
        if self._task_exists(state, hero_id, obstacle):
            return set()

        cross = set(state.trees if hero_id == HeroId.IKOTOFOSA else state.holes)
        if not cross:
            return None

        if hero_id == HeroId.IKOTOFOSA:
            opened = self._copy_without(state, set(), cross)
        else:
            opened = self._copy_without(state, cross, set())
        if not self._task_exists(opened, hero_id, obstacle, structural=True):
            return None

        required = set(cross)
        checks = 0
        for candidate in sorted(cross, key=lambda p: (p.manhattan(obstacle), p.row, p.col), reverse=True):
            if checks >= self.max_unlock_checks:
                break
            checks += 1
            trial = set(required)
            trial.discard(candidate)
            if hero_id == HeroId.IKOTOFOSA:
                hypothetical = self._copy_without(state, set(), trial)
            else:
                hypothetical = self._copy_without(state, trial, set())
            if self._task_exists(hypothetical, hero_id, obstacle, structural=True):
                required = trial
        return required

    def _expanded_unlock_obstacles(
        self,
        state: GameState,
        profile: UnlockProfile,
    ) -> tuple[set[Position], set[Position]]:
        holes = set(profile.holes) & set(state.holes)
        trees = set(profile.trees) & set(state.trees)
        for _ in range(4):
            changed = False
            for hole in sorted(holes):
                if self._task_exists(state, HeroId.IKOTOFOSA, hole):
                    continue
                prerequisites = self._cross_prerequisites(state, HeroId.IKOTOFOSA, hole)
                if prerequisites:
                    before = len(trees)
                    trees.update(prerequisites & set(state.trees))
                    changed = changed or len(trees) != before
            for tree in sorted(trees):
                if self._task_exists(state, HeroId.IMAHAKI, tree):
                    continue
                prerequisites = self._cross_prerequisites(state, HeroId.IMAHAKI, tree)
                if prerequisites:
                    before = len(holes)
                    holes.update(prerequisites & set(state.holes))
                    changed = changed or len(holes) != before
            if not changed:
                break
        return holes, trees

    def _staging_task_for(
        self,
        state: GameState,
        hero_id: HeroId,
        obstacles: set[Position],
    ) -> MachineTask | None:
        hero = state.heroes[hero_id]
        kind = self._compatible_kind(hero_id)
        candidates: list[MachineTask] = []
        for obstacle in sorted(obstacles):
            prerequisites = self._cross_prerequisites(state, hero_id, obstacle)
            if prerequisites is None:
                continue
            if hero_id == HeroId.IKOTOFOSA:
                hypothetical = self._copy_without(state, set(), prerequisites)
            else:
                hypothetical = self._copy_without(state, prerequisites, set())
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
                    max_expansions=50000,
                    ignore_other_machines=True,
                )
                if control is None:
                    continue
                if hero.is_hacking:
                    approach = None
                    hack_ticks = 0
                    hack_battery = 0
                else:
                    approach = find_score_path(state, hero_id, machine.position, max_expansions=30000)
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
                cost = score_cost_units(total_ticks, approach_stamina, battery)
                candidates.append(MachineTask(hero_id, machine.id, obstacle, approach, control, total_ticks, cost))
        if not candidates:
            return None
        candidates.sort(key=lambda task: (task.total_ticks, task.total_cost_units, task.machine_id, task.obstacle.row, task.obstacle.col))
        return candidates[0]

    def _action_for_staging_task(self, state: GameState, task: MachineTask) -> HeroAction:
        hero = state.heroes[task.hero_id]
        machine = state.machines[task.machine_id]
        if hero.is_hacking:
            if hero.hacking_machine_id == machine.id:
                return HeroAction.WAIT
            return HeroAction.WAIT
        if hero.position == machine.position:
            return HeroAction.HACK
        path = find_score_path(state, task.hero_id, machine.position, max_expansions=30000)
        if path is None or not path.steps:
            return HeroAction.WAIT
        step = path.steps[0]
        if step.stamina_cost > hero.stamina:
            return HeroAction.WAIT
        return step.action

    def _action_for_machine_task(self, state: GameState, task: MachineTask) -> HeroAction:
        hero = state.heroes[task.hero_id]
        machine = state.machines[task.machine_id]
        if hero.is_hacking:
            if machine.pending_move:
                return HeroAction.WAIT
            if machine.kind == MachineKind.GRAPPLER and machine.position in state.trees:
                return HeroAction.WAIT
            replanned = plan_machine_to_obstacle(state, machine, task.obstacle, max_expansions=30000)
            if replanned is None or not replanned.actions:
                return HeroAction.WAIT
            return replanned.actions[0]
        if hero.position == machine.position:
            return HeroAction.HACK
        approach = find_score_path(state, task.hero_id, machine.position, max_expansions=30000)
        if approach is None or not approach.steps:
            return HeroAction.WAIT
        step = approach.steps[0]
        if step.stamina_cost > hero.stamina:
            return HeroAction.WAIT
        return step.action

    def _partner_relocation_action(
        self,
        state: GameState,
        controller_id: HeroId,
        partner_obstacles: set[Position],
    ) -> HeroAction | None:
        controller = state.heroes[controller_id]
        if not controller.is_hacking or controller.hacking_machine_id is None or not partner_obstacles:
            return None
        partner_id = HeroId.IMAHAKI if controller_id == HeroId.IKOTOFOSA else HeroId.IKOTOFOSA
        if self._machine_tasks_for(state, partner_id, partner_obstacles):
            return None
        if not any(self._task_exists(state, partner_id, obstacle, structural=True) for obstacle in partner_obstacles):
            return None

        machine = state.machines[controller.hacking_machine_id]
        if machine.pending_move:
            return HeroAction.WAIT
        if machine.kind == MachineKind.GRAPPLER and machine.position in state.trees:
            return HeroAction.WAIT
        if controller.battery <= 0:
            return None

        positions = sorted(
            (
                pos
                for pos in state.game_map.all_positions()
                if 1 <= machine.position.manhattan(pos) <= 4
            ),
            key=lambda pos: (machine.position.manhattan(pos), pos.row, pos.col),
        )
        best: tuple[tuple[int, int, int, int], MachineControlPlan] | None = None
        for target in positions:
            control = plan_machine_to_position(state, machine, target, max_expansions=20000)
            if control is None or not control.actions or control.battery_cost > controller.battery:
                continue
            hypothetical = deepcopy(state)
            moved = hypothetical.machines[machine.id]
            moved.position = target
            moved.pending_move = False
            moved.auto_move_pending = False
            hypothetical.heroes[controller_id].position = target
            if moved.kind == MachineKind.GRAPPLER and target in hypothetical.trees:
                hypothetical.trees.remove(target)
            if not self._machine_tasks_for(hypothetical, partner_id, partner_obstacles):
                continue
            distance_obstacle = min(target.manhattan(obstacle) for obstacle in partner_obstacles)
            rank = (control.score_cost_units, control.ticks, -distance_obstacle, target.row * state.game_map.width + target.col)
            if best is None or rank < best[0]:
                best = (rank, control)
        if best is None:
            return None
        return best[1].actions[0]

    def _unlock_actions(self, state: GameState, chest: Position) -> dict[HeroId, HeroAction]:
        profile = self._unlock_profile(state, chest)
        remaining_holes, remaining_trees = self._expanded_unlock_obstacles(state, profile)
        decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}

        relocation_m = self._partner_relocation_action(state, HeroId.IMAHAKI, remaining_holes)
        relocation_f = self._partner_relocation_action(state, HeroId.IKOTOFOSA, remaining_trees)
        if relocation_m is not None:
            decisions[HeroId.IMAHAKI] = relocation_m
            self.last_decisions[HeroId.IMAHAKI.value] = "repositionner Grappler pour libérer le trajet Excavator"
        if relocation_f is not None:
            decisions[HeroId.IKOTOFOSA] = relocation_f
            self.last_decisions[HeroId.IKOTOFOSA.value] = "repositionner Excavator pour libérer le trajet Grappler"

        assignments = (
            (HeroId.IKOTOFOSA, remaining_holes),
            (HeroId.IMAHAKI, remaining_trees),
        )
        for hero_id, obstacles in assignments:
            if hero_id.value in self.last_decisions and "repositionner" in self.last_decisions[hero_id.value]:
                continue
            if not obstacles:
                self.last_decisions[hero_id.value] = "attendre déblocage partenaire" if remaining_holes or remaining_trees else "coffre bientôt accessible"
                continue
            tasks = self._machine_tasks_for(state, hero_id, obstacles)
            if not tasks:
                staging = self._staging_task_for(state, hero_id, set(obstacles))
                if staging is None:
                    self.last_decisions[hero_id.value] = "aucune machine compatible atteignable pour obstacle requis"
                    continue
                decisions[hero_id] = self._action_for_staging_task(state, staging)
                self.last_decisions[hero_id.value] = f"prépositionner et neutraliser {staging.machine_id} pour obstacle ({staging.obstacle.row},{staging.obstacle.col})"
                continue
            task = tasks[0]
            action = self._action_for_machine_task(state, task)
            decisions[hero_id] = action
            libelle = "remplir trou" if hero_id == HeroId.IKOTOFOSA else "couper arbre"
            self.last_decisions[hero_id.value] = f"{libelle} ({task.obstacle.row},{task.obstacle.col}) avec {task.machine_id}"
        return decisions

    @staticmethod
    def _rotation_distance(current, target) -> tuple[int, HeroAction | None]:
        if current == target:
            return 0, None
        cw = current
        for steps in range(1, 4):
            cw = CLOCKWISE[cw]
            if cw == target:
                ccw_steps = 4 - steps
                if steps <= ccw_steps:
                    return steps, HeroAction.HACK_CW
                return ccw_steps, HeroAction.HACK_CCW
        return 0, None

    def _prepare_machine_release(self, state: GameState, hero_id: HeroId, chest: Position) -> HeroAction | None:
        hero = state.heroes[hero_id]
        if not hero.is_hacking or hero.hacking_machine_id is None:
            return None
        machine = state.machines[hero.hacking_machine_id]
        if machine.pending_move:
            return HeroAction.WAIT
        if machine.kind == MachineKind.GRAPPLER and machine.position in state.trees:
            return HeroAction.WAIT
        if hero.battery <= 0:
            return None

        current_distance = machine.position.manhattan(chest)
        orientation_candidates = []
        for orientation in ORIENTATION_TO_DIRECTION:
            direction = ORIENTATION_TO_DIRECTION[orientation]
            dr, dc = DIRECTION_VECTORS[direction]
            forward = machine.position.moved(dr, dc)
            forward_distance = forward.manhattan(chest) if state.game_map.in_bounds(forward) else -999
            same_axis_danger = (
                machine.position.row == chest.row
                and dr == 0
                and ((dc > 0 and chest.col > machine.position.col) or (dc < 0 and chest.col < machine.position.col))
            ) or (
                machine.position.col == chest.col
                and dc == 0
                and ((dr > 0 and chest.row > machine.position.row) or (dr < 0 and chest.row < machine.position.row))
            )
            copie = deepcopy(state)
            machine_copie = copie.machines[machine.id]
            machine_copie.orientation = orientation
            queueable = Rules.machine_forward_queueable(copie, machine_copie)
            orientation_candidates.append((int(queueable), int(not same_axis_danger), forward_distance, orientation.value, orientation))
        orientation_candidates.sort(reverse=True)
        best_orientation = orientation_candidates[0][-1]
        _steps, rotate_action = self._rotation_distance(machine.orientation, best_orientation)
        if rotate_action is not None:
            return rotate_action

        return None

    def _direct_chest_actions(self, state: GameState, target: Position) -> dict[HeroId, HeroAction] | None:
        plans = self._direct_chest_plans(state, only_chest=target)
        if not plans:
            return None
        best = plans[0]
        decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
        release_action = self._prepare_machine_release(state, best.hero_id, target)
        decisions[best.hero_id] = release_action if release_action is not None else self._first_direct_action(state, best)
        self.last_decisions[best.hero_id.value] = f"coffre direct ({target.row},{target.col}) -> cachette ({best.bush.row},{best.bush.col})"
        other = HeroId.IMAHAKI if best.hero_id == HeroId.IKOTOFOSA else HeroId.IKOTOFOSA
        self.last_decisions[other.value] = "laisser le pousseur terminer le coffre prioritaire"
        return decisions

    def _stone_target_candidates(self, state: GameState, hero_id: HeroId) -> list[tuple[int, int, tuple[object, ...], HeroAction, str]]:
        hero = state.heroes[hero_id]
        result: list[tuple[int, int, tuple[object, ...], HeroAction, str]] = []
        stones = sorted(state.stones, key=lambda p: (hero.position.manhattan(p), p.row, p.col))[: self.max_stones_per_hero]
        for stone in stones:
            path = find_score_path(state, hero_id, stone, max_expansions=30000)
            if path is None:
                continue
            if not path.steps:
                continue
            value = 25 * 4 - score_cost_units(path.ticks, path.total_stamina_cost)
            if value <= 0:
                continue
            step = path.steps[0]
            result.append((path.ticks, -value, ("stone", stone.row, stone.col), step.action, f"collecter pierre ({stone.row},{stone.col})"))
        for machine in sorted(state.machines.values(), key=lambda m: m.id):
            if machine.carried_stones <= 0:
                continue
            path = find_score_path(state, hero_id, machine.position, max_expansions=30000)
            if path is None or not path.steps:
                continue
            value = machine.carried_stones * 25 * 4 - score_cost_units(path.ticks, path.total_stamina_cost)
            if value <= 0:
                continue
            step = path.steps[0]
            result.append((path.ticks, -value, ("machine_stones", machine.id), step.action, f"récupérer {machine.carried_stones} pierre(s) sur {machine.id}"))
        result.sort()
        return result

    def _stone_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
        reserved: set[tuple[object, ...]] = set()
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            candidates = self._stone_target_candidates(state, hero_id)
            chosen = next((item for item in candidates if item[2] not in reserved), None)
            if chosen is None:
                self.last_decisions[hero_id.value] = "aucune pierre libre atteignable"
                continue
            _ticks, _neg_value, key, action, desc = chosen
            hero = state.heroes[hero_id]
            if action in MOVE_ACTIONS:
                move = Rules.hero_move(state, hero, action)
                if not move.valid or move.stamina_cost > hero.stamina:
                    action = HeroAction.WAIT
            decisions[hero_id] = action
            reserved.add(key)
            self.last_decisions[hero_id.value] = desc
        return decisions

    def _has_pending_productive_goal(self, state: GameState) -> bool:
        self._refresh_impossible(state)
        if any(chest not in self._impossible_chests for chest in state.chests):
            return True
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            if self._stone_target_candidates(state, hero_id):
                return True
        return False

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        self.last_decisions = {}
        target = self._select_target_chest(state)
        if target is not None:
            direct = self._direct_chest_actions(state, target)
            if direct is not None:
                decisions = direct
            else:
                decisions = self._unlock_actions(state, target)
        else:
            decisions = self._stone_actions(state)

        if all(action == HeroAction.WAIT for action in decisions.values()):
            self.stuck_ticks += 1
        else:
            self.stuck_ticks = 0
        return decisions
