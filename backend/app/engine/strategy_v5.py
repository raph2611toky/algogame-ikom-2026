from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import HeroAction, HeroId, MOVE_ACTIONS
from app.domain.models import GameState, Position
from app.engine.rules import Rules
from app.engine.score_pathfinding import score_cost_units
from app.engine.strategy_v4 import ChestFirstPortfolioStrategy, DirectChestPlan


@dataclass(frozen=True, slots=True)
class StoneChoice:
    hero_id: HeroId
    ticks: int
    value_units: int
    key: tuple[object, ...]
    action: HeroAction
    description: str


class CollaborativePortfolioStrategy(ChestFirstPortfolioStrategy):
    def __init__(
        self,
        *,
        max_stones_per_hero: int = 16,
        max_chest_pairs_per_hero: int = 24,
        stuck_end_threshold: int = 16,
        max_unlock_checks: int = 32,
    ) -> None:
        super().__init__(
            max_stones_per_hero=max_stones_per_hero,
            max_chest_pairs_per_hero=max_chest_pairs_per_hero,
            stuck_end_threshold=stuck_end_threshold,
            max_unlock_checks=max_unlock_checks,
        )
        self._hero_chest_targets: dict[HeroId, Position | None] = {
            HeroId.IKOTOFOSA: None,
            HeroId.IMAHAKI: None,
        }

    @staticmethod
    def _other(hero_id: HeroId) -> HeroId:
        return HeroId.IMAHAKI if hero_id == HeroId.IKOTOFOSA else HeroId.IKOTOFOSA

    @staticmethod
    def _direct_cost(plan: DirectChestPlan) -> int:
        return score_cost_units(plan.plan.ticks, plan.plan.stamina_cost)

    def _prune_chest_targets(self, state: GameState) -> None:
        for hero_id, target in tuple(self._hero_chest_targets.items()):
            if target not in state.chests:
                self._hero_chest_targets[hero_id] = None

    def _best_direct_by_hero_chest(self, state: GameState) -> dict[tuple[HeroId, Position], DirectChestPlan]:
        best: dict[tuple[HeroId, Position], DirectChestPlan] = {}
        for plan in self._direct_chest_plans(state):
            key = (plan.hero_id, plan.chest)
            current = best.get(key)
            if current is None or plan.cost_key < current.cost_key:
                best[key] = plan
        return best

    def _choose_direct_pair(
        self,
        state: GameState,
        plans: dict[tuple[HeroId, Position], DirectChestPlan],
    ) -> tuple[DirectChestPlan, DirectChestPlan] | None:
        f_plans = [p for (hid, _), p in plans.items() if hid == HeroId.IKOTOFOSA]
        m_plans = [p for (hid, _), p in plans.items() if hid == HeroId.IMAHAKI]
        best: tuple[tuple[object, ...], tuple[DirectChestPlan, DirectChestPlan]] | None = None
        current_f = self._hero_chest_targets[HeroId.IKOTOFOSA]
        current_m = self._hero_chest_targets[HeroId.IMAHAKI]
        for f_plan in f_plans:
            for m_plan in m_plans:
                if f_plan.chest == m_plan.chest:
                    continue
                switches = int(current_f is not None and current_f != f_plan.chest) + int(current_m is not None and current_m != m_plan.chest)
                rank = (
                    switches,
                    max(f_plan.plan.ticks, m_plan.plan.ticks),
                    self._direct_cost(f_plan) + self._direct_cost(m_plan),
                    f_plan.plan.ticks + m_plan.plan.ticks,
                    f_plan.chest.row,
                    f_plan.chest.col,
                    m_plan.chest.row,
                    m_plan.chest.col,
                )
                if best is None or rank < best[0]:
                    best = (rank, (f_plan, m_plan))
        return None if best is None else best[1]

    def _choose_single_direct(
        self,
        plans: dict[tuple[HeroId, Position], DirectChestPlan],
    ) -> DirectChestPlan | None:
        if not plans:
            return None
        persistent: list[DirectChestPlan] = []
        for hero_id, target in self._hero_chest_targets.items():
            if target is None:
                continue
            plan = plans.get((hero_id, target))
            if plan is not None:
                persistent.append(plan)
        if persistent:
            return min(persistent, key=lambda p: (p.cost_key, self._direct_cost(p)))
        return min(plans.values(), key=lambda p: (p.cost_key, self._direct_cost(p)))

    def _direct_action(self, state: GameState, plan: DirectChestPlan) -> HeroAction:
        release = self._prepare_machine_release(state, plan.hero_id, plan.chest)
        return release if release is not None else self._first_direct_action(state, plan)

    def _stone_choices(self, state: GameState, hero_id: HeroId) -> list[StoneChoice]:
        choices: list[StoneChoice] = []
        for ticks, neg_value, key, action, desc in self._stone_target_candidates(state, hero_id):
            choices.append(StoneChoice(hero_id, ticks, -neg_value, key, action, desc))
        return choices

    @staticmethod
    def _validate_hero_action(state: GameState, hero_id: HeroId, action: HeroAction) -> HeroAction:
        if action not in MOVE_ACTIONS:
            return action
        hero = state.heroes[hero_id]
        movement = Rules.hero_move(state, hero, action)
        if not movement.valid or movement.stamina_cost > hero.stamina:
            return HeroAction.WAIT
        return action

    def _best_stone_action_for_hero(
        self,
        state: GameState,
        hero_id: HeroId,
        *,
        reserved: set[tuple[object, ...]] | None = None,
    ) -> tuple[HeroAction, tuple[object, ...] | None, str]:
        reserved = reserved or set()
        for choice in self._stone_choices(state, hero_id):
            if choice.key in reserved:
                continue
            action = self._validate_hero_action(state, hero_id, choice.action)
            if action == HeroAction.WAIT and choice.action != HeroAction.WAIT:
                return HeroAction.WAIT, choice.key, f"récupérer stamina avant {choice.description}"
            return action, choice.key, choice.description
        return HeroAction.WAIT, None, "aucune pierre libre atteignable"

    def _collaborative_stone_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
        f_choices = self._stone_choices(state, HeroId.IKOTOFOSA)
        m_choices = self._stone_choices(state, HeroId.IMAHAKI)
        pair_best: tuple[tuple[object, ...], tuple[StoneChoice, StoneChoice]] | None = None
        for f_choice in f_choices:
            for m_choice in m_choices:
                if f_choice.key == m_choice.key:
                    continue
                rank = (
                    -(f_choice.value_units + m_choice.value_units),
                    max(f_choice.ticks, m_choice.ticks),
                    f_choice.ticks + m_choice.ticks,
                    f_choice.key,
                    m_choice.key,
                )
                if pair_best is None or rank < pair_best[0]:
                    pair_best = (rank, (f_choice, m_choice))
        if pair_best is not None:
            for choice in pair_best[1]:
                action = self._validate_hero_action(state, choice.hero_id, choice.action)
                decisions[choice.hero_id] = action
                self.last_decisions[choice.hero_id.value] = choice.description if action != HeroAction.WAIT else f"récupérer stamina avant {choice.description}"
            return decisions

        singles = f_choices + m_choices
        if singles:
            choice = min(singles, key=lambda c: (-c.value_units, c.ticks, c.hero_id.value, c.key))
            action = self._validate_hero_action(state, choice.hero_id, choice.action)
            decisions[choice.hero_id] = action
            self.last_decisions[choice.hero_id.value] = choice.description if action != HeroAction.WAIT else f"récupérer stamina avant {choice.description}"
            other = self._other(choice.hero_id)
            self.last_decisions[other.value] = "aucune cible distincte rentable"
        else:
            self.last_decisions[HeroId.IKOTOFOSA.value] = "aucune pierre libre atteignable"
            self.last_decisions[HeroId.IMAHAKI.value] = "aucune pierre libre atteignable"
        return decisions

    def _secondary_unlock_action(
        self,
        state: GameState,
        hero_id: HeroId,
        *,
        excluded_chests: set[Position],
    ) -> tuple[HeroAction, str] | None:
        hero = state.heroes[hero_id]
        if hero.is_hacking:
            return None
        self._refresh_impossible(state)
        candidates: list[tuple[tuple[object, ...], HeroAction, str]] = []
        for chest in sorted(state.chests):
            if chest in excluded_chests or chest in self._impossible_chests:
                continue
            if self._direct_chest_plans(state, only_chest=chest):
                continue
            profile = self._unlock_profile(state, chest)
            if not profile.structurally_possible:
                continue
            holes, trees = self._expanded_unlock_obstacles(state, profile)
            obstacles = holes if hero_id == HeroId.IKOTOFOSA else trees
            if not obstacles:
                continue
            tasks = self._machine_tasks_for(state, hero_id, obstacles)
            if not tasks:
                continue
            task = tasks[0]
            action = self._action_for_machine_task(state, task)
            rank = (task.total_ticks, task.total_cost_units, chest.row, chest.col, task.machine_id)
            libelle = "remplir trou" if hero_id == HeroId.IKOTOFOSA else "couper arbre"
            candidates.append((rank, action, f"préparer coffre ({chest.row},{chest.col}) : {libelle} ({task.obstacle.row},{task.obstacle.col}) avec {task.machine_id}"))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        _rank, action, desc = candidates[0]
        return action, desc

    def _fill_idle_heroes(
        self,
        state: GameState,
        decisions: dict[HeroId, HeroAction],
        *,
        excluded_chests: set[Position],
        reserved_stones: set[tuple[object, ...]] | None = None,
    ) -> dict[HeroId, HeroAction]:
        reserved_stones = set() if reserved_stones is None else set(reserved_stones)
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            if decisions[hero_id] != HeroAction.WAIT:
                continue
            hero = state.heroes[hero_id]
            if hero.is_hacking:
                continue
            unlock = self._secondary_unlock_action(state, hero_id, excluded_chests=excluded_chests)
            if unlock is not None:
                action, desc = unlock
                decisions[hero_id] = action
                self.last_decisions[hero_id.value] = desc
                continue
            action, key, desc = self._best_stone_action_for_hero(state, hero_id, reserved=reserved_stones)
            decisions[hero_id] = action
            if key is not None:
                reserved_stones.add(key)
            self.last_decisions[hero_id.value] = desc
        return decisions

    def _direct_collaborative_actions(self, state: GameState) -> dict[HeroId, HeroAction] | None:
        self._prune_chest_targets(state)
        plans = self._best_direct_by_hero_chest(state)
        if not plans:
            return None
        distinct_chests = {chest for _, chest in plans}
        pair = self._choose_direct_pair(state, plans) if len(distinct_chests) >= 2 else None
        decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
        assigned: set[Position] = set()
        if pair is not None:
            for plan in pair:
                decisions[plan.hero_id] = self._direct_action(state, plan)
                self._hero_chest_targets[plan.hero_id] = plan.chest
                assigned.add(plan.chest)
                self.last_decisions[plan.hero_id.value] = f"coffre direct ({plan.chest.row},{plan.chest.col}) -> cachette ({plan.bush.row},{plan.bush.col}) en parallèle"
            self._target_chest = pair[0].chest
            return decisions

        best = self._choose_single_direct(plans)
        if best is None:
            return None
        decisions[best.hero_id] = self._direct_action(state, best)
        self._hero_chest_targets[best.hero_id] = best.chest
        self._hero_chest_targets[self._other(best.hero_id)] = None
        assigned.add(best.chest)
        self._target_chest = best.chest
        self.last_decisions[best.hero_id.value] = f"coffre direct ({best.chest.row},{best.chest.col}) -> cachette ({best.bush.row},{best.bush.col})"
        return self._fill_idle_heroes(state, decisions, excluded_chests=assigned)

    def _unlock_collaborative_actions(self, state: GameState, target: Position) -> dict[HeroId, HeroAction]:
        decisions = self._unlock_actions(state, target)
        self._hero_chest_targets[HeroId.IKOTOFOSA] = None
        self._hero_chest_targets[HeroId.IMAHAKI] = None
        return self._fill_idle_heroes(state, decisions, excluded_chests={target})

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        self.last_decisions = {}
        direct = self._direct_collaborative_actions(state)
        if direct is not None:
            decisions = direct
        else:
            target = self._select_target_chest(state)
            if target is not None:
                decisions = self._unlock_collaborative_actions(state, target)
            else:
                decisions = self._collaborative_stone_actions(state)

        if all(action == HeroAction.WAIT for action in decisions.values()):
            self.stuck_ticks += 1
        else:
            self.stuck_ticks = 0
        return decisions
