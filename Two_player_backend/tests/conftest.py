from __future__ import annotations

import pytest

from app.domain.enums import Difficulty
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator


@pytest.fixture
def base_map_text() -> str:
    return """7 9 60
#########
#F..+...#
#..@....#
#.......#
#...*E..#
#M....K.#
#########"""


@pytest.fixture
def state(base_map_text):
    game_map = MapParser.parse(base_map_text)
    result = Simulator.initial_state(game_map, difficulty=Difficulty.MEDIUM, seed=42)
    result.guard.cooldown = 999
    return result
