from __future__ import annotations

import random

from app.domain.enums import Direction, GuardMode
from app.domain.models import GameState, Position
from app.engine.guard_ai.base import direction_towards, legal_directions


class MediumGuardAI:
    """Heuristique locale : vue, dernière position, bruit, puis patrouille."""

    def _goal(self, state: GameState) -> Position | None:
        memory = state.guard.memory
        if memory.visible:
            return min(
                (memory.last_known[hero_id] for hero_id in memory.visible),
                key=state.guard.position.manhattan,
            )
        if memory.mode == GuardMode.SEARCH and memory.target is not None:
            return memory.last_known.get(memory.target)
        if memory.mode == GuardMode.INVESTIGATE:
            return memory.last_heard
        return None

    def choose_direction(self, state: GameState) -> Direction | None:
        goal = self._goal(state)
        directed = direction_towards(state, goal)
        if directed is not None:
            return directed
        legal = legal_directions(state)
        if not legal:
            return None
        rng = random.Random(state.seed * 2_000_003 + state.elapsed_ticks * 193)
        # Une patrouille lisible : continuer tout droit si possible, sinon tourner.
        if state.guard.orientation in legal and rng.random() < 0.72:
            return state.guard.orientation
        return rng.choice(legal)
