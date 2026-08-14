from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from app.domain.enums import (
    CLOCKWISE,
    COUNTER_CLOCKWISE,
    DIRECTION_VECTORS,
    MOVE_ACTIONS,
    ORIENTATION_TO_DIRECTION,
    PUSH_ACTIONS,
    HeroAction,
    HeroId,
    MachineKind,
    Orientation,
)
from app.domain.models import GameState, Position
from app.engine.rules import Rules
from app.engine.chest_planner import plan_chest_to_bush
from app.engine.machine_planner import plan_machine_to_position
from app.engine.strategy_v4 import DirectChestPlan
from app.engine.strategy_v7 import CachedCollaborativePortfolioStrategy


@dataclass(slots=True)
class _DirectRoute:
    plan: DirectChestPlan
    actions: list[HeroAction]
    expected_hero: Position
    expected_chest: Position
    remaining_stamina: int
    topology_signature: tuple[object, ...]


class StaminaAwareCollaborativePortfolioStrategy(CachedCollaborativePortfolioStrategy):
    """
    portfolio_v8:
    - conserve la logique coffre/deblocage/pierres de v7;
    - memorise le plan direct d'un coffre au lieu de relancer le planner a chaque tick;
    - autorise un changement de pousseur lorsque le pousseur courant devrait attendre
      longtemps pour recuperer sa stamina;
    - place une machine hackee dans une orientation a faible risque avant UNHACK.
    """

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
        self._direct_routes: dict[HeroId, _DirectRoute] = {}
        self._target_selection_signature: tuple[object, ...] | None = None


    def _direct_chest_plans(self, state: GameState, *, only_chest: Position | None = None) -> list[DirectChestPlan]:
        if not state.chests or not state.game_map.bushes:
            return []
        chests = [only_chest] if only_chest is not None and only_chest in state.chests else sorted(state.chests)
        cells = state.game_map.height * state.game_map.width
        if cells <= 160:
            max_expansions = max(6000, min(70000, cells * 350))
            budget = self.max_chest_pairs_per_hero * 2
            bush_limit = len(state.game_map.bushes)
        elif cells <= 400:
            max_expansions = 9000
            budget = min(self.max_chest_pairs_per_hero * 2, max(8, len(chests) * 4))
            bush_limit = 2
        elif cells <= 800:
            max_expansions = 7000
            budget = min(self.max_chest_pairs_per_hero * 2, max(6, len(chests) * 3))
            bush_limit = 2
        else:
            max_expansions = 5000
            budget = min(self.max_chest_pairs_per_hero * 2, max(4, len(chests) * 2))
            bush_limit = 1

        plans: list[DirectChestPlan] = []
        attempts = 0
        for chest in chests:
            for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
                hero = state.heroes[hero_id]
                bushes = sorted(
                    state.game_map.bushes,
                    key=lambda bush: (chest.manhattan(bush), hero.position.manhattan(chest), bush.row, bush.col),
                )[:bush_limit]
                for bush in bushes:
                    if attempts >= budget:
                        break
                    attempts += 1
                    plan = plan_chest_to_bush(
                        state, hero_id, chest, bush,
                        max_expansions=max_expansions, optimize_for_score=True,
                    )
                    if plan is not None and plan.actions:
                        plans.append(DirectChestPlan(hero_id, chest, bush, plan))
        plans.sort(key=lambda item: item.cost_key)
        return plans

    @staticmethod
    def _recovery_ticks(stamina_needed: int, stamina_available: int) -> int:
        deficit = max(0, stamina_needed - stamina_available)
        # Le GDD: +1 stamina toutes les 2 secondes de WAIT.
        return deficit * 2

    def _plan_runtime_key(self, state: GameState, plan: DirectChestPlan) -> tuple[object, ...]:
        hero = state.heroes[plan.hero_id]
        recovery = self._recovery_ticks(plan.plan.stamina_cost, hero.stamina)
        effective_ticks = plan.plan.ticks + recovery
        return (
            effective_ticks,
            recovery,
            plan.plan.score_cost_units,
            plan.plan.ticks,
            plan.plan.stamina_cost,
            plan.chest.row,
            plan.chest.col,
            plan.hero_id.value,
        )

    def _choose_direct_pair(
        self,
        state: GameState,
        plans: dict[tuple[HeroId, Position], DirectChestPlan],
    ) -> tuple[DirectChestPlan, DirectChestPlan] | None:
        f_plans = [p for (hid, _), p in plans.items() if hid == HeroId.IKOTOFOSA]
        m_plans = [p for (hid, _), p in plans.items() if hid == HeroId.IMAHAKI]
        best: tuple[tuple[object, ...], tuple[DirectChestPlan, DirectChestPlan]] | None = None
        for f_plan in f_plans:
            for m_plan in m_plans:
                if f_plan.chest == m_plan.chest:
                    continue
                f_key = self._plan_runtime_key(state, f_plan)
                m_key = self._plan_runtime_key(state, m_plan)
                rank = (
                    max(int(f_key[0]), int(m_key[0])),
                    int(f_key[0]) + int(m_key[0]),
                    int(f_key[1]) + int(m_key[1]),
                    int(f_key[2]) + int(m_key[2]),
                    f_plan.chest.row,
                    f_plan.chest.col,
                    m_plan.chest.row,
                    m_plan.chest.col,
                )
                if best is None or rank < best[0]:
                    best = (rank, (f_plan, m_plan))
        if best is None:
            return None
        f_plan, m_plan = best[1]
        f_recovery = self._recovery_ticks(f_plan.plan.stamina_cost, state.heroes[HeroId.IKOTOFOSA].stamina)
        m_recovery = self._recovery_ticks(m_plan.plan.stamina_cost, state.heroes[HeroId.IMAHAKI].stamina)
        # Parallele seulement si les deux pousseurs peuvent soutenir leurs plans sans
        # longues pauses. Sinon on traite un coffre avec relais et on garde l'autre
        # heros comme reserve de stamina.
        if max(f_recovery, m_recovery) > 20:
            return None
        return best[1]

    def _choose_single_direct(
        self,
        state: GameState,
        plans: dict[tuple[HeroId, Position], DirectChestPlan],
    ) -> DirectChestPlan | None:
        if not plans:
            return None
        return min(plans.values(), key=lambda plan: self._plan_runtime_key(state, plan))

    def _cache_route(self, state: GameState, plan: DirectChestPlan) -> _DirectRoute:
        route = _DirectRoute(
            plan=plan,
            actions=list(plan.plan.actions),
            expected_hero=state.heroes[plan.hero_id].position,
            expected_chest=plan.chest,
            remaining_stamina=plan.plan.stamina_cost,
            topology_signature=self._topology_signature(state),
        )
        self._direct_routes[plan.hero_id] = route
        return route

    def _route_valid(self, state: GameState, hero_id: HeroId, route: _DirectRoute) -> bool:
        # Un plan coffre depend du terrain dynamique. Une machine peut DIG/CUT
        # pendant que le heros suit la route; continuer l'ancien plan peut alors
        # produire des PUSH impossibles ou envoyer le coffre vers un nouveau trou.
        if route.topology_signature != self._topology_signature(state):
            return False
        if route.expected_chest not in state.chests:
            return False
        if state.heroes[hero_id].position != route.expected_hero:
            return False
        if route.plan.bush not in state.game_map.bushes:
            return False
        return bool(route.actions)

    def _prune_routes(self, state: GameState) -> None:
        for hero_id, route in tuple(self._direct_routes.items()):
            if not self._route_valid(state, hero_id, route):
                self._direct_routes.pop(hero_id, None)
                if self._hero_chest_targets.get(hero_id) == route.expected_chest:
                    self._hero_chest_targets[hero_id] = None

    def _other_takeover_plan(self, state: GameState, route: _DirectRoute) -> DirectChestPlan | None:
        owner = route.plan.hero_id
        other = self._other(owner)
        if other in self._direct_routes:
            return None
        plans = self._direct_chest_plans(state, only_chest=route.expected_chest)
        candidates = [plan for plan in plans if plan.hero_id == other]
        if not candidates:
            return None
        return min(candidates, key=lambda plan: self._plan_runtime_key(state, plan))

    def _maybe_handoff(self, state: GameState, hero_id: HeroId, route: _DirectRoute) -> bool:
        hero = state.heroes[hero_id]
        current_recovery = self._recovery_ticks(route.remaining_stamina, hero.stamina)
        if current_recovery < 4:
            return False
        takeover = self._other_takeover_plan(state, route)
        if takeover is None:
            return False
        other = state.heroes[takeover.hero_id]
        takeover_recovery = self._recovery_ticks(takeover.plan.stamina_cost, other.stamina)
        takeover_ticks = takeover.plan.ticks + takeover_recovery
        current_ticks = len(route.actions) + current_recovery
        # Deux ticks de marge empechent les oscillations de pousseur pour un gain minime.
        if takeover_ticks + 2 >= current_ticks:
            return False
        self._direct_routes.pop(hero_id, None)
        self._hero_chest_targets[hero_id] = None
        self._cache_route(state, takeover)
        self._hero_chest_targets[takeover.hero_id] = takeover.chest
        self.last_decisions[hero_id.value] = (
            f"passer le coffre ({route.expected_chest.row},{route.expected_chest.col}) "
            f"a {takeover.hero_id.value} pour eviter {current_recovery} ticks de recuperation"
        )
        return True

    def _route_action(self, state: GameState, hero_id: HeroId, route: _DirectRoute) -> HeroAction:
        hero = state.heroes[hero_id]
        release = self._prepare_machine_release(state, hero_id, route.expected_chest)
        if release is not None:
            return release
        if not route.actions:
            return HeroAction.WAIT
        action = route.actions[0]
        if action in MOVE_ACTIONS:
            movement = Rules.hero_move(state, hero, action)
            if not movement.valid or movement.stamina_cost > hero.stamina:
                return HeroAction.WAIT
            route.actions.pop(0)
            route.expected_hero = movement.destination
            route.remaining_stamina = max(0, route.remaining_stamina - movement.stamina_cost)
            return action
        if action in PUSH_ACTIONS:
            push = Rules.chest_push(state, hero, action)
            if not push.valid or push.chest_from != route.expected_chest:
                return HeroAction.WAIT
            if not Rules.hero_chest_push_safe_this_tick(state, push):
                return HeroAction.WAIT
            route.actions.pop(0)
            route.expected_hero = push.hero_to or hero.position
            route.expected_chest = push.chest_to or route.expected_chest
            route.remaining_stamina = max(0, route.remaining_stamina - 5)
            return action
        route.actions.pop(0)
        return action


    def _needs_stamina_support(self, state: GameState, assigned: set[Position]) -> HeroId | None:
        if len(self._direct_routes) != 1 or len(assigned) != 1:
            return None
        owner, route = next(iter(self._direct_routes.items()))
        hero = state.heroes[owner]
        recovery = self._recovery_ticks(route.remaining_stamina, hero.stamina)
        if recovery <= 12:
            return None
        return self._other(owner)

    def _fill_direct_support(
        self,
        state: GameState,
        decisions: dict[HeroId, HeroAction],
        assigned: set[Position],
    ) -> dict[HeroId, HeroAction]:
        # Une route directe est un engagement. Si son proprietaire doit WAIT pour
        # recuperer les 5 stamina d'un PUSH, il ne doit surtout pas etre detourne
        # vers une pierre: cela invaliderait le plan, provoquerait un replan et
        # transformerait une simple recharge en longue hesitation.
        active_owners = set(self._direct_routes)
        support = self._needs_stamina_support(state, assigned)

        # Remplit uniquement les heros qui ne possedent PAS une route coffre.
        # On reproduit ici _fill_idle_heroes sans lui laisser toucher un owner.
        reserved: set[Position | str] = set()
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            if hero_id in active_owners:
                route = self._direct_routes[hero_id]
                if decisions[hero_id] == HeroAction.WAIT:
                    next_action = route.actions[0] if route.actions else None
                    if next_action in PUSH_ACTIONS and state.heroes[hero_id].stamina < 5:
                        self.last_decisions[hero_id.value] = (
                            f"recharger stamina pour prochain {next_action.value} "
                            f"du coffre ({route.expected_chest.row},{route.expected_chest.col})"
                        )
                continue
            if decisions[hero_id] != HeroAction.WAIT:
                continue
            hero = state.heroes[hero_id]
            if hero.is_hacking:
                continue

            # Lorsqu'un long trajet de coffre est en cours, le second heros devient
            # une reserve de stamina; il ne collecte que s'il est deja bien recharge.
            if support == hero_id and hero.stamina < 85:
                decisions[hero_id] = HeroAction.WAIT
                self.last_decisions[hero_id.value] = "preserver stamina pour relais du coffre"
                continue

            action, key, desc = self._best_stone_action_for_hero(state, hero_id, reserved=reserved)
            if key is not None:
                decisions[hero_id] = action
                reserved.add(key)
                self.last_decisions[hero_id.value] = desc
                continue
            unlock = self._secondary_unlock_action(state, hero_id, excluded_chests=assigned)
            if unlock is not None:
                action, desc = unlock
                decisions[hero_id] = action
                self.last_decisions[hero_id.value] = desc
                continue
            self.last_decisions[hero_id.value] = desc
        return decisions

    def _direct_collaborative_actions(self, state: GameState) -> dict[HeroId, HeroAction] | None:
        self._prune_chest_targets(state)
        self._prune_routes(state)

        # Tant qu'un plan direct reste valide, on l'execute sans relancer le planner complet.
        if self._direct_routes:
            # Handoff stamina-aware uniquement si l'autre heros n'est pas deja engage sur un autre coffre.
            for hero_id, route in tuple(self._direct_routes.items()):
                if self._route_valid(state, hero_id, route):
                    self._maybe_handoff(state, hero_id, route)
            self._prune_routes(state)

            decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
            assigned: set[Position] = set()
            for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
                route = self._direct_routes.get(hero_id)
                if route is None or not self._route_valid(state, hero_id, route):
                    continue
                decisions[hero_id] = self._route_action(state, hero_id, route)
                assigned.add(route.expected_chest)
                self.last_decisions[hero_id.value] = (
                    f"coffre direct cache ({route.plan.chest.row},{route.plan.chest.col}) "
                    f"-> ({route.plan.bush.row},{route.plan.bush.col})"
                )
            if assigned:
                return self._fill_direct_support(state, decisions, assigned)

        # Replanification globale uniquement lorsqu'il n'existe plus de route directe valide.
        plans = self._best_direct_by_hero_chest(state)
        if not plans:
            return None
        distinct_chests = {chest for _, chest in plans}
        pair = self._choose_direct_pair(state, plans) if len(distinct_chests) >= 2 else None
        chosen: list[DirectChestPlan] = []
        if pair is not None:
            chosen.extend(pair)
        else:
            best = self._choose_single_direct(state, plans)
            if best is not None:
                chosen.append(best)
        if not chosen:
            return None

        self._direct_routes.clear()
        decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
        assigned: set[Position] = set()
        for plan in chosen:
            route = self._cache_route(state, plan)
            self._hero_chest_targets[plan.hero_id] = plan.chest
            assigned.add(plan.chest)
            decisions[plan.hero_id] = self._route_action(state, plan.hero_id, route)
            self.last_decisions[plan.hero_id.value] = (
                f"coffre direct ({plan.chest.row},{plan.chest.col}) -> "
                f"cachette ({plan.bush.row},{plan.bush.col}), cout stamina {plan.plan.stamina_cost}"
            )
        self._target_chest = chosen[0].chest
        return self._fill_direct_support(state, decisions, assigned)





    def _action_for_staging_task(self, state: GameState, task) -> HeroAction:
        hero = state.heroes[task.hero_id]
        machine = state.machines[task.machine_id]
        if not hero.is_hacking:
            return super()._action_for_staging_task(state, task)
        if hero.hacking_machine_id != machine.id or hero.battery <= 0:
            return HeroAction.WAIT
        if machine.pending_move:
            return HeroAction.WAIT
        if machine.kind == MachineKind.GRAPPLER and machine.position in state.trees:
            return HeroAction.WAIT
        if not task.control.actions:
            return HeroAction.WAIT
        action = task.control.actions[0]
        # Un staging n'est pas seulement "HACK puis WAIT": on avance la machine
        # sur la portion deja legalement ouverte de son futur trajet.
        if action == HeroAction.HACK_MOVE:
            return action if Rules.machine_forward_queueable(state, machine) else HeroAction.WAIT
        if action == HeroAction.HACK_FILL:
            forward = Rules.machine_forward(machine)
            return action if machine.kind == MachineKind.EXCAVATOR and forward in state.holes else HeroAction.WAIT
        if action == HeroAction.HACK_CUT:
            forward = Rules.machine_forward(machine)
            return action if machine.kind == MachineKind.GRAPPLER and forward in state.trees else HeroAction.WAIT
        if action in {HeroAction.HACK_CW, HeroAction.HACK_CCW}:
            return action
        return HeroAction.WAIT

    def _unlock_actions(self, state: GameState, chest: Position) -> dict[HeroId, HeroAction]:
        profile = self._unlock_profile(state, chest)
        remaining_holes, remaining_trees = self._expanded_unlock_obstacles(state, profile)
        decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
        assignments = (
            (HeroId.IKOTOFOSA, remaining_holes),
            (HeroId.IMAHAKI, remaining_trees),
        )

        # Priorite absolue: un heros qui peut traiter son propre obstacle le fait.
        # v7 pouvait tenter une relocation du partenaire avant HACK_FILL/HACK_CUT et
        # boucler contre le buffer machine.
        unresolved: dict[HeroId, set[Position]] = {}
        for hero_id, obstacles in assignments:
            obstacle_set = set(obstacles)
            if not obstacle_set:
                unresolved[hero_id] = set()
                continue
            tasks = self._machine_tasks_for(state, hero_id, obstacle_set)
            if tasks:
                task = tasks[0]
                decisions[hero_id] = self._action_for_machine_task(state, task)
                label = "remplir trou" if hero_id == HeroId.IKOTOFOSA else "couper arbre"
                self.last_decisions[hero_id.value] = f"{label} ({task.obstacle.row},{task.obstacle.col}) avec {task.machine_id}"
                unresolved[hero_id] = set()
                continue
            unresolved[hero_id] = obstacle_set

        # Ensuite seulement on prepare une machine si aucun task direct n'existe.
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
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

        # Relocation en dernier recours seulement, et seulement si le heros n'a
        # toujours aucune action productive propre.
        partner_obstacles = {
            HeroId.IKOTOFOSA: set(remaining_trees),
            HeroId.IMAHAKI: set(remaining_holes),
        }
        for controller_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            if decisions[controller_id] != HeroAction.WAIT:
                continue
            relocation = self._partner_relocation_action(state, controller_id, partner_obstacles[controller_id])
            if relocation is not None:
                decisions[controller_id] = relocation
                kind = "Excavator" if controller_id == HeroId.IKOTOFOSA else "Grappler"
                self.last_decisions[controller_id.value] = f"repositionner {kind} pour liberer le partenaire"

        for hero_id, obstacles in assignments:
            if hero_id.value not in self.last_decisions:
                self.last_decisions[hero_id.value] = (
                    "attendre deblocage partenaire" if remaining_holes or remaining_trees else "coffre bientot accessible"
                )
        return decisions

    def _select_target_chest(self, state: GameState) -> Position | None:
        self._refresh_impossible(state)
        signature = self._topology_signature(state)
        if (
            self._target_selection_signature == signature
            and self._target_chest in state.chests
            and self._target_chest not in self._impossible_chests
        ):
            return self._target_chest

        def machine_obstacle_cost(hero_id: HeroId, obstacles: set[Position]) -> int:
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

        candidates: list[tuple[int, int, int, int, Position]] = []
        for chest in sorted(state.chests):
            if chest in self._impossible_chests:
                continue
            profile = self._unlock_profile(state, chest)
            if not profile.structurally_possible:
                continue
            holes = set(profile.holes) & set(state.holes)
            trees = set(profile.trees) & set(state.trees)
            unlock_cost = (
                machine_obstacle_cost(HeroId.IKOTOFOSA, holes)
                + machine_obstacle_cost(HeroId.IMAHAKI, trees)
            )
            hero_distance = min(hero.position.manhattan(chest) for hero in state.heroes.values())
            bush_distance = min((chest.manhattan(bush) for bush in state.game_map.bushes), default=0)
            estimate = unlock_cost + hero_distance + bush_distance * 2 + (len(holes) + len(trees)) * 4
            candidates.append((estimate, len(holes) + len(trees), hero_distance, chest.row * state.game_map.width + chest.col, chest))
        self._target_selection_signature = signature
        if not candidates:
            self._target_chest = None
            return None
        candidates.sort()
        self._target_chest = candidates[0][-1]
        return self._target_chest

    def _machine_tasks_for(
        self,
        state: GameState,
        hero_id: HeroId,
        obstacles,
        *,
        ignore_other_machines: bool = False,
    ):
        obstacle_list = list(obstacles)
        cells = state.game_map.height * state.game_map.width
        if cells > 160 and len(obstacle_list) > 6:
            kind = MachineKind.EXCAVATOR if hero_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
            compatible = [m for m in state.machines.values() if m.kind == kind]
            hero = state.heroes[hero_id]
            obstacle_list.sort(
                key=lambda obstacle: (
                    min((m.position.manhattan(obstacle) for m in compatible), default=9999),
                    hero.position.manhattan(obstacle),
                    obstacle.row,
                    obstacle.col,
                )
            )
            obstacle_list = obstacle_list[:6]
        return super()._machine_tasks_for(
            state, hero_id, obstacle_list, ignore_other_machines=ignore_other_machines
        )

    def _partner_relocation_action(
        self,
        state: GameState,
        controller_id: HeroId,
        partner_obstacles: set[Position],
    ) -> HeroAction | None:
        cells = state.game_map.height * state.game_map.width
        if cells <= 160:
            return super()._partner_relocation_action(state, controller_id, partner_obstacles)
        controller = state.heroes[controller_id]
        if not controller.is_hacking or controller.hacking_machine_id is None or not partner_obstacles:
            return None
        machine = state.machines[controller.hacking_machine_id]
        partner_id = self._other(controller_id)
        partner_kind = MachineKind.EXCAVATOR if partner_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        partner_machines = [m for m in state.machines.values() if m.kind == partner_kind]
        # Le buffer AlgoMada ne peut etre cause par cette machine que si elle se trouve
        # a deux cellules ou moins d'une machine du partenaire. Evite une recherche
        # de relocation exhaustive dans tous les autres cas.
        close = []
        for partner_machine in partner_machines:
            if partner_machine.id == machine.id:
                continue
            direction = ORIENTATION_TO_DIRECTION[partner_machine.orientation]
            dr, dc = DIRECTION_VECTORS[direction]
            cell1 = partner_machine.position.moved(dr, dc)
            cell2 = cell1.moved(dr, dc)
            cell3 = cell2.moved(dr, dc)
            blocks = machine.position in {cell1, cell2}
            if not blocks and machine.position == cell3 and (cell1 in state.chests or cell2 in state.chests):
                blocks = True
            if blocks:
                close.append(partner_machine)
        if not close:
            return None
        if machine.pending_move:
            return HeroAction.WAIT
        if machine.kind == MachineKind.GRAPPLER and machine.position in state.trees:
            return HeroAction.WAIT
        if controller.battery <= 0:
            return None

        positions = [
            pos for pos in state.game_map.all_positions()
            if 1 <= machine.position.manhattan(pos) <= 2
            and pos not in state.game_map.rocks
        ]
        positions.sort(
            key=lambda pos: (
                -min((pos.manhattan(m.position) for m in close), default=0),
                -min((pos.manhattan(o) for o in partner_obstacles), default=0),
                machine.position.manhattan(pos),
                pos.row, pos.col,
            )
        )
        best = None
        for target in positions[:10]:
            control = plan_machine_to_position(state, machine, target, max_expansions=5000)
            if control is None or not control.actions or control.battery_cost > controller.battery:
                continue
            rank = (control.ticks, control.score_cost_units, -min(target.manhattan(m.position) for m in close), target.row, target.col)
            if best is None or rank < best[0]:
                best = (rank, control)
        return None if best is None else best[1].actions[0]

    @staticmethod
    def _release_risk(state: GameState, machine_id: str, orientation: Orientation, focus: Position) -> tuple[int, int, int]:
        simulation = deepcopy(state)
        machine = simulation.machines[machine_id]
        machine.orientation = orientation
        machine.hacked_by = None
        if machine.hacked_by is not None:
            machine.hacked_by = None
        risk = 0
        secured_bonus = 0
        horizon = 7
        for _ in range(horizon):
            if Rules.machine_buffer_reason(simulation, machine) is not None:
                machine.orientation = COUNTER_CLOCKWISE[machine.orientation] if machine.kind == MachineKind.EXCAVATOR else CLOCKWISE[machine.orientation]
                continue
            target = Rules.machine_forward(machine)
            if not Rules.machine_cell_passable(simulation, machine, target):
                machine.orientation = COUNTER_CLOCKWISE[machine.orientation] if machine.kind == MachineKind.EXCAVATOR else CLOCKWISE[machine.orientation]
                continue
            if target in simulation.chests:
                direction = ORIENTATION_TO_DIRECTION[machine.orientation]
                dr, dc = DIRECTION_VECTORS[direction]
                destination = target.moved(dr, dc)
                if not simulation.game_map.in_bounds(destination):
                    risk += 2000
                    machine.orientation = COUNTER_CLOCKWISE[machine.orientation] if machine.kind == MachineKind.EXCAVATOR else CLOCKWISE[machine.orientation]
                    continue
                if destination in simulation.holes:
                    # Le cas que l'on veut absolument eviter avant UNHACK.
                    risk += 100000
                    break
                if destination in simulation.game_map.bushes:
                    simulation.chests.remove(target)
                    secured_bonus += 1
                elif (
                    destination in simulation.game_map.rocks
                    or destination in simulation.trees
                    or destination in simulation.chests
                    or simulation.machine_at(destination) is not None
                ):
                    risk += 300
                    machine.orientation = COUNTER_CLOCKWISE[machine.orientation] if machine.kind == MachineKind.EXCAVATOR else CLOCKWISE[machine.orientation]
                    continue
                else:
                    before = min((target.manhattan(b) for b in simulation.game_map.bushes), default=0)
                    after = min((destination.manhattan(b) for b in simulation.game_map.bushes), default=0)
                    risk += 40 + max(0, after - before) * 80
                    simulation.chests.remove(target)
                    simulation.chests.add(destination)
            machine.position = target
            if machine.kind == MachineKind.GRAPPLER and target in simulation.trees:
                simulation.trees.remove(target)

        # Eviter aussi de laisser la machine alignee vers le coffre actuellement traite.
        direction = ORIENTATION_TO_DIRECTION[machine.orientation]
        dr, dc = DIRECTION_VECTORS[direction]
        aligned_toward_focus = (
            machine.position.row == focus.row
            and dr == 0
            and ((dc > 0 and focus.col > machine.position.col) or (dc < 0 and focus.col < machine.position.col))
        ) or (
            machine.position.col == focus.col
            and dc == 0
            and ((dr > 0 and focus.row > machine.position.row) or (dr < 0 and focus.row < machine.position.row))
        )
        if aligned_toward_focus:
            risk += 600
        return risk, -secured_bonus, machine.position.manhattan(focus)

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

        candidates: list[tuple[object, ...]] = []
        for orientation in Orientation:
            risk = self._release_risk(state, machine.id, orientation, chest)
            rotations, action = self._rotation_distance(machine.orientation, orientation)
            # Le risque domine toujours le cout d'une ou deux rotations de batterie.
            candidates.append((risk[0], risk[1], rotations, -risk[2], orientation.value, orientation, action))
        candidates.sort()
        best_risk, _bonus, _rotations, _distance, _name, best_orientation, rotate_action = candidates[0]
        if best_orientation != machine.orientation and rotate_action is not None:
            return rotate_action
        # Si meme la meilleure orientation connue pousserait tres probablement un
        # coffre dans un trou, on conserve le controle et WAIT. Le partenaire peut
        # alors deplacer le coffre ou modifier le terrain avant que la machine ne
        # reprenne sa routine automatique.
        if best_risk >= 50000:
            return HeroAction.WAIT
        return None

    def _safe_release_focus(self, state: GameState, hero_id: HeroId) -> Position | None:
        if not state.chests:
            return None
        target = self._target_chest
        if target in state.chests:
            return target
        hero = state.heroes[hero_id]
        if hero.hacking_machine_id and hero.hacking_machine_id in state.machines:
            machine = state.machines[hero.hacking_machine_id]
            return min(state.chests, key=lambda chest: (machine.position.manhattan(chest), chest.row, chest.col))
        return min(state.chests, key=lambda chest: (hero.position.manhattan(chest), chest.row, chest.col))

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        decisions = super().next_actions(state)
        # Toute action de mouvement d'un heros actuellement dans une machine
        # provoque UNHACK dans le simulateur. On intercepte donc TOUS les departs,
        # pas seulement ceux d'un plan coffre direct, pour securiser l'orientation
        # de la machine avant de la rendre a sa routine automatique.
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            hero = state.heroes[hero_id]
            action = decisions.get(hero_id, HeroAction.WAIT)
            if not hero.is_hacking or action not in MOVE_ACTIONS:
                continue
            focus = self._safe_release_focus(state, hero_id)
            if focus is None:
                continue
            release = self._prepare_machine_release(state, hero_id, focus)
            if release is not None:
                decisions[hero_id] = release
                if release == HeroAction.WAIT:
                    self.last_decisions[hero_id.value] = "maintenir machine hackee: aucune orientation de relache sure"
                else:
                    self.last_decisions[hero_id.value] = f"orienter machine en securite avant UNHACK ({release.value})"
        return decisions
