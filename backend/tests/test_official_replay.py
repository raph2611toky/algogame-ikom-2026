from pathlib import Path

from app.domain.enums import HeroAction, HeroId
from app.domain.models import Position
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator


F_ACTIONS = [
    "LEFT", "UP", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "WAIT", "WAIT",
    "HACK", "HACK_CCW", "HACK_MOVE", "WAIT", "HACK_MOVE", "WAIT", "HACK_CW",
    "HACK_MOVE", "WAIT", "HACK_MOVE", "WAIT",
]
M_ACTIONS = [
    "LEFT", "LEFT", "HACK", "HACK_MOVE", "WAIT", "HACK_MOVE", "WAIT", "HACK_MOVE",
    "WAIT", "HACK_CW", "HACK_MOVE", "WAIT", "WAIT", "HACK_CCW", "HACK_MOVE",
    "WAIT", "WAIT", "HACK_CCW", "HACK_MOVE", "WAIT",
]


def test_official_appendix_replay_matches_key_states() -> None:
    text = Path("maps/official_sample.txt").read_text(encoding="utf-8")
    state = MapParser.build_initial_state(MapParser.parse(text))
    sim = Simulator(state)
    for f, m in zip(F_ACTIONS, M_ACTIONS, strict=True):
        sim.step({
            HeroId.IKOTOFOSA: HeroAction(f),
            HeroId.IMAHAKI: HeroAction(m),
        })

    f = state.heroes[HeroId.IKOTOFOSA]
    m = state.heroes[HeroId.IMAHAKI]
    assert (f.position, f.stamina, f.battery) == (Position(0, 4), 81, 93)
    assert (m.position, m.stamina, m.battery) == (Position(0, 5), 100, 90)
    assert f.stones == 1
    assert m.stones == 1

    x = state.machines["X1"]
    g = state.machines["G1"]
    assert x.position == Position(0, 4)
    assert g.position == Position(0, 5)
    assert Position(1, 4) not in state.trees
    assert Position(1, 5) not in state.trees
    assert state.elapsed == 20
    assert state.remaining_time == 80


def test_official_appendix_matches_every_hero_tick() -> None:
    text = Path("maps/official_sample.txt").read_text(encoding="utf-8")
    state = MapParser.build_initial_state(MapParser.parse(text))
    sim = Simulator(state)

    expected_f = [
        ((4, 0), 99, 100), ((2, 0), 89, 100), ((2, 2), 79, 100),
        ((2, 3), 78, 100), ((2, 4), 77, 100), ((2, 5), 76, 100),
        ((2, 6), 75, 100), ((2, 6), 75, 100), ((2, 6), 76, 100),
        ((2, 6), 76, 99), ((2, 6), 77, 98), ((2, 6), 77, 97),
        ((2, 5), 78, 97), ((2, 5), 78, 96), ((2, 4), 79, 96),
        ((2, 4), 79, 95), ((2, 4), 80, 94), ((1, 4), 80, 94),
        ((1, 4), 81, 93), ((0, 4), 81, 93),
    ]
    expected_m = [
        ((0, 2), 99, 100), ((0, 1), 98, 100), ((0, 1), 98, 99),
        ((0, 1), 99, 98), ((0, 2), 99, 98), ((0, 2), 100, 97),
        ((0, 3), 100, 97), ((0, 3), 100, 96), ((0, 4), 100, 96),
        ((0, 4), 100, 95), ((0, 4), 100, 94), ((1, 4), 100, 94),
        ((1, 4), 100, 94), ((1, 4), 100, 93), ((1, 4), 100, 92),
        ((1, 5), 100, 92), ((1, 5), 100, 92), ((1, 5), 100, 91),
        ((1, 5), 100, 90), ((0, 5), 100, 90),
    ]

    for i, (f_action, m_action) in enumerate(zip(F_ACTIONS, M_ACTIONS, strict=True)):
        sim.step({
            HeroId.IKOTOFOSA: HeroAction(f_action),
            HeroId.IMAHAKI: HeroAction(m_action),
        })
        f = state.heroes[HeroId.IKOTOFOSA]
        m = state.heroes[HeroId.IMAHAKI]
        f_expected = expected_f[i]
        m_expected = expected_m[i]
        assert ((f.position.row, f.position.col), f.stamina, f.battery) == f_expected
        assert ((m.position.row, m.position.col), m.stamina, m.battery) == m_expected
