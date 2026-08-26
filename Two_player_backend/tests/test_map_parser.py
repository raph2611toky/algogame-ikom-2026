from __future__ import annotations

import pytest

from app.domain.enums import HeroId
from app.engine.map_parser import MapFormatError, MapParser


def test_parses_twist_symbols(base_map_text):
    game_map = MapParser.parse(base_map_text)
    assert game_map.height == 7
    assert game_map.initial_guard is not None
    assert game_map.initial_heroes[HeroId.IKOTOFOSA].row == 1
    assert len(game_map.initial_stones) == 1
    assert len(game_map.exits) == 1


def test_rejects_missing_guard():
    text = """3 5 20
#####
#FM.#
#####"""
    with pytest.raises(MapFormatError, match="gardien"):
        MapParser.parse(text)


def test_elevation_contract():
    text = """3 5 20
#####
#FMK#
#####"""
    elevation = """00000
01110
00000"""
    game_map = MapParser.parse(text, elevation)
    assert game_map.has_elevation is True
    assert game_map.elevations[1][2] == 1


def test_rejects_nonzero_rock_elevation():
    text = """3 5 20
#####
#FMK#
#####"""
    with pytest.raises(MapFormatError, match="rocher"):
        MapParser.parse(text, "11111\n11111\n11111")
