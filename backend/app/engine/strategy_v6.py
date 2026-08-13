from __future__ import annotations

from typing import Iterable

from app.domain.enums import HeroAction, HeroId
from app.domain.models import GameState, Position
from app.engine.strategy_v4 import MachineTask
from app.engine.strategy_v5 import CollaborativePortfolioStrategy, StoneChoice


class OptimizedCollaborativePortfolioStrategy(CollaborativePortfolioStrategy):
    def __init__(
        self,
        *,
        max_stones_per_hero: int = 16,
        max_chest_pairs_per_hero: int = 24,
        stuck_end_threshold: int = 20,
        max_unlock_checks: int = 40,
    ) -> None:
        super().__init__(
            max_stones_per_hero=max_stones_per_hero,
            max_chest_pairs_per_hero=max_chest_pairs_per_hero,
            stuck_end_threshold=stuck_end_threshold,
            max_unlock_checks=max_unlock_checks,
        )
        self._last_dynamic_signature: tuple[object, ...] | None = None

    @staticmethod
    def _dynamic_signature(state: GameState) -> tuple[object, ...]:
        return (
            tuple(sorted((p.row, p.col) for p in state.chests)),
            tuple(sorted((p.row, p.col) for p in state.stones)),
            tuple(sorted((p.row, p.col) for p in state.holes)),
            tuple(sorted((p.row, p.col) for p in state.trees)),
            tuple(
                sorted(
                    (
                        m.id,
                        m.position.row,
                        m.position.col,
                        m.orientation.value,
                        m.carried_stones,
                        m.hacked_by.value if m.hacked_by else None,
                        m.pending_move,
                        m.auto_move_pending,
                    )
                    for m in state.machines.values()
                )
            ),
        )

    def _refresh_impossible(self, state: GameState) -> None:
        signature = (
            tuple(sorted((p.row, p.col) for p in state.chests)),
            tuple(sorted((p.row, p.col) for p in state.game_map.bushes)),
            tuple(sorted((p.row, p.col) for p in state.game_map.rocks)),
            tuple(sorted((p.row, p.col) for p in state.holes)),
            tuple(sorted((p.row, p.col) for p in state.trees)),
            tuple(
                (hero_id.value, state.heroes[hero_id].position.row, state.heroes[hero_id].position.col)
                for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI)
            ),
        )
        if signature == self._impossible_signature:
            return
        self._impossible_signature = signature
        self._impossible_chests = set()
        for chest in sorted(state.chests):
            profile = self._unlock_profile(state, chest)
            if not profile.structurally_possible:
                self._impossible_chests.add(chest)

    def _machine_tasks_for(
        self,
        state: GameState,
        hero_id: HeroId,
        obstacles: Iterable[Position],
        *,
        ignore_other_machines: bool = False,
    ) -> list[MachineTask]:
        tasks = super()._machine_tasks_for(
            state,
            hero_id,
            obstacles,
            ignore_other_machines=ignore_other_machines,
        )

        def rank(task: MachineTask) -> tuple[object, ...]:
            approach_ticks = 0 if task.approach is None else task.approach.ticks
            already_controlled = int(state.heroes[hero_id].hacking_machine_id != task.machine_id)
            return (
                already_controlled,
                approach_ticks,
                task.total_cost_units,
                task.total_ticks,
                task.obstacle.row,
                task.obstacle.col,
                task.machine_id,
            )

        tasks.sort(key=rank)
        return tasks

    def _stone_choices(self, state: GameState, hero_id: HeroId) -> list[StoneChoice]:
        choices = super()._stone_choices(state, hero_id)
        choices.sort(
            key=lambda choice: (
                -choice.value_units,
                choice.ticks,
                0 if choice.key and choice.key[0] == "machine_stones" else 1,
                choice.key,
            )
        )
        return choices

    def _has_pending_productive_goal(self, state: GameState) -> bool:
        self._refresh_impossible(state)
        if any(chest not in self._impossible_chests for chest in state.chests):
            return True
        if state.stones:
            return True
        if any(machine.carried_stones > 0 for machine in state.machines.values()):
            return True
        return False

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        signature = self._dynamic_signature(state)
        if self._last_dynamic_signature is not None and signature != self._last_dynamic_signature:
            self.stuck_ticks = 0
        decisions = super().next_actions(state)
        self._last_dynamic_signature = signature
        return decisions
