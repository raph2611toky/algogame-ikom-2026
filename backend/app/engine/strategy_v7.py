from __future__ import annotations

from app.domain.enums import HeroAction, HeroId
from app.domain.models import GameState, Position
from app.engine.chest_planner import plan_chest_to_bush
from app.engine.strategy_v4 import DirectChestPlan, UnlockProfile
from app.engine.strategy_v6 import OptimizedCollaborativePortfolioStrategy


class CachedCollaborativePortfolioStrategy(OptimizedCollaborativePortfolioStrategy):
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
        self._topology_profiles: dict[tuple[object, ...], UnlockProfile] = {}
        self._last_topology: tuple[object, ...] | None = None
        self._terminal_no_goal = False
        self.stop_reason: str | None = None

    def _direct_chest_plans(self, state: GameState, *, only_chest: Position | None = None) -> list[DirectChestPlan]:
        if not state.chests or not state.game_map.bushes:
            return []
        chests = [only_chest] if only_chest is not None and only_chest in state.chests else sorted(state.chests)
        cells = state.game_map.height * state.game_map.width
        if cells <= 160:
            max_expansions = max(6000, min(70000, cells * 350))
        elif cells <= 600:
            max_expansions = max(7000, min(28000, cells * 80))
        else:
            max_expansions = max(5000, min(18000, cells * 35))
        plans: list[DirectChestPlan] = []
        attempts = 0
        budget = self.max_chest_pairs_per_hero * 2
        for chest in chests:
            for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
                hero = state.heroes[hero_id]
                bushes = sorted(
                    state.game_map.bushes,
                    key=lambda bush: (chest.manhattan(bush), hero.position.manhattan(chest), bush.row, bush.col),
                )
                for bush in bushes:
                    if attempts >= budget:
                        break
                    attempts += 1
                    plan = plan_chest_to_bush(
                        state,
                        hero_id,
                        chest,
                        bush,
                        max_expansions=max_expansions,
                        optimize_for_score=True,
                    )
                    if plan is not None and plan.actions:
                        plans.append(DirectChestPlan(hero_id, chest, bush, plan))
        plans.sort(key=lambda item: item.cost_key)
        return plans

    @staticmethod
    def _topology_signature(state: GameState) -> tuple[object, ...]:
        return (
            tuple(sorted((p.row, p.col) for p in state.chests)),
            tuple(sorted((p.row, p.col) for p in state.holes)),
            tuple(sorted((p.row, p.col) for p in state.trees)),
            tuple(sorted((p.row, p.col) for p in state.game_map.rocks)),
            tuple(sorted((p.row, p.col) for p in state.game_map.bushes)),
        )

    @classmethod
    def _profile_signature(cls, state: GameState, chest: Position) -> tuple[object, ...]:
        return (
            chest.row,
            chest.col,
            cls._topology_signature(state),
        )

    def _unlock_profile(self, state: GameState, chest: Position) -> UnlockProfile:
        signature = self._profile_signature(state, chest)
        cached = self._topology_profiles.get(signature)
        if cached is not None:
            return cached
        profile = super()._unlock_profile(state, chest)
        self._topology_profiles[signature] = profile
        if len(self._topology_profiles) > 256:
            current = self._topology_signature(state)
            self._topology_profiles = {
                key: value
                for key, value in self._topology_profiles.items()
                if key[2] == current
            }
        return profile

    def _refresh_impossible(self, state: GameState) -> None:
        signature = self._topology_signature(state)
        if signature == self._impossible_signature:
            return
        self._impossible_signature = signature
        self._impossible_chests = set()
        for chest in sorted(state.chests):
            profile = self._unlock_profile(state, chest)
            if not profile.structurally_possible:
                self._impossible_chests.add(chest)

    def _select_target_chest(self, state: GameState) -> Position | None:
        self._refresh_impossible(state)
        if self._target_chest in state.chests and self._target_chest not in self._impossible_chests:
            return self._target_chest

        candidates: list[tuple[int, int, int, Position]] = []
        for chest in sorted(state.chests):
            if chest in self._impossible_chests:
                continue
            profile = self._unlock_profile(state, chest)
            if not profile.structurally_possible:
                continue
            hero_distance = min(hero.position.manhattan(chest) for hero in state.heroes.values())
            candidates.append(
                (
                    profile.obstacle_count,
                    hero_distance,
                    chest.row * state.game_map.width + chest.col,
                    chest,
                )
            )
        if not candidates:
            self._target_chest = None
            return None
        candidates.sort()
        self._target_chest = candidates[0][3]
        return self._target_chest

    def _fill_idle_heroes(
        self,
        state: GameState,
        decisions: dict[HeroId, HeroAction],
        *,
        excluded_chests: set[Position],
        reserved_stones: set[tuple[object, ...]] | None = None,
    ) -> dict[HeroId, HeroAction]:
        reserved = set() if reserved_stones is None else set(reserved_stones)
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            if decisions[hero_id] != HeroAction.WAIT:
                continue
            hero = state.heroes[hero_id]
            if hero.is_hacking:
                continue
            action, key, desc = self._best_stone_action_for_hero(state, hero_id, reserved=reserved)
            if key is not None:
                decisions[hero_id] = action
                reserved.add(key)
                self.last_decisions[hero_id.value] = desc
                continue
            unlock = self._secondary_unlock_action(state, hero_id, excluded_chests=excluded_chests)
            if unlock is not None:
                action, desc = unlock
                decisions[hero_id] = action
                self.last_decisions[hero_id.value] = desc
                continue
            self.last_decisions[hero_id.value] = desc
        return decisions

    def should_end(self, state: GameState) -> bool:
        self.stop_reason = None
        if state.objectives_finished:
            self.stop_reason = "OBJECTIVES_FINISHED"
            return True
        if state.remaining_time <= 0:
            self.stop_reason = "TIME_LIMIT"
            return True
        if self._terminal_no_goal:
            self.stop_reason = "NO_REACHABLE_OBJECTIVES"
            return True
        if self.stuck_ticks >= self.stuck_end_threshold:
            self.stop_reason = "STRATEGY_STUCK"
            return True
        return False

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        topology = self._topology_signature(state)
        if self._last_topology is not None and topology != self._last_topology:
            self.stuck_ticks = 0
        decisions = super().next_actions(state)
        self._terminal_no_goal = (
            not state.stones
            and not any(machine.carried_stones > 0 for machine in state.machines.values())
            and bool(state.chests)
            and all(chest in self._impossible_chests for chest in state.chests)
        )
        self._last_topology = topology
        return decisions
