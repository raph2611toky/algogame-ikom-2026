from pathlib import Path
import pytest
from app.domain.enums import HeroId, MachineKind, Orientation
from app.domain.models import Position
from app.engine.map_parser import MapFormatError, MapParser

def sample_text() -> str:
    return Path('maps/official_sample.txt').read_text(encoding='utf-8')

def test_parse_official_sample() -> None:
    game_map = MapParser.parse(sample_text())
    assert (game_map.height, game_map.width, game_map.time_limit) == (5, 7, 100)
    assert game_map.initial_hero_positions[HeroId.IKOTOFOSA] == Position(4, 1)
    assert game_map.initial_hero_positions[HeroId.IMAHAKI] == Position(0, 3)
    assert len(game_map.stones) == 5
    assert len(game_map.chests) == 1
    assert len(game_map.trees) == 4
    assert len(game_map.holes) == 2
    assert len(game_map.bushes) == 1
    x = next((machine_locale for machine_locale in game_map.initial_machines if machine_locale.kind == MachineKind.EXCAVATOR))
    g = next((machine_locale for machine_locale in game_map.initial_machines if machine_locale.kind == MachineKind.GRAPPLER))
    assert x.orientation == Orientation.FACING_LEFT
    assert g.orientation == Orientation.FACING_RIGHT

def test_rejects_wrong_width() -> None:
    texte = '2 3 10\nF..\nM.\n'
    with pytest.raises(MapFormatError):
        MapParser.parse(texte)

def test_rejects_unknown_symbol() -> None:
    with pytest.raises(MapFormatError):
        MapParser.parse('2 2 10\nF?\nM.\n')

def test_requires_both_heroes() -> None:
    with pytest.raises(MapFormatError):
        MapParser.parse('2 2 10\nF.\n..\n')
