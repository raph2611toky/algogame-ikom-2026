from __future__ import annotations

import random

from app.domain.enums import Direction
from app.domain.models import GameState
from app.engine.guard_ai.base import legal_directions


class EasyGuardAI:
    """Déplacement volontairement imprévisible, mais toujours légal."""

    def choose_direction(self, state: GameState) -> Direction | None:
        rng = random.Random(state.seed * 1_000_003 + state.elapsed_ticks * 97)
        choices: list[Direction | None] = [None, *legal_directions(state)]
        return rng.choice(choices)
