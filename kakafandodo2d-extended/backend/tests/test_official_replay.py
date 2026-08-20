from pathlib import Path
from app.domain.enums import HeroAction, HeroId
from app.domain.models import Position
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator

F_ACTIONS = ['LEFT', 'UP', 'RIGHT', 'RIGHT', 'RIGHT', 'RIGHT', 'RIGHT', 'WAIT', 'WAIT', 'HACK', 'HACK_CCW', 'HACK_MOVE', 'WAIT', 'HACK_MOVE', 'WAIT', 'HACK_CW', 'HACK_MOVE', 'WAIT', 'HACK_MOVE', 'WAIT']
M_ACTIONS = ['LEFT', 'LEFT', 'HACK', 'HACK_MOVE', 'WAIT', 'HACK_MOVE', 'WAIT', 'HACK_MOVE', 'WAIT', 'HACK_CW', 'HACK_MOVE', 'WAIT', 'WAIT', 'HACK_CCW', 'HACK_MOVE', 'WAIT', 'WAIT', 'HACK_CCW', 'HACK_MOVE', 'WAIT']


def test_original_appendix_replay_matches_until_new_addendum_lookahead_intervenes() -> None:
    texte = Path('maps/official_sample.txt').read_text(encoding='utf-8')
    state = MapParser.build_initial_state(MapParser.parse(texte))
    sim = Simulator(state)
    records = []
    for f, m in zip(F_ACTIONS, M_ACTIONS, strict=True):
        records.append(sim.step({HeroId.IKOTOFOSA: HeroAction(f), HeroId.IMAHAKI: HeroAction(m)}))

    # Through tick 13 the historical appendix remains identical. At tick 14,
    # X1 would move into a destination whose side look-ahead contains G1. The
    # second-week addendum now has priority, so F's HACK_MOVE is ignored.
    tick14 = records[13]
    assert tick14.effective_actions[HeroId.IKOTOFOSA] == HeroAction.WAIT
    assert state.elapsed == 20
    assert state.remaining_time == 80
    assert state.heroes[HeroId.IKOTOFOSA].position == Position(2, 5)
    assert state.heroes[HeroId.IKOTOFOSA].battery == 96
    assert state.heroes[HeroId.IMAHAKI].position == Position(0, 4)
    assert state.heroes[HeroId.IMAHAKI].battery == 91


def test_original_appendix_actions_have_stable_post_addendum_hero_states() -> None:
    texte = Path('maps/official_sample.txt').read_text(encoding='utf-8')
    state = MapParser.build_initial_state(MapParser.parse(texte))
    sim = Simulator(state)
    expected_f = [((4, 0), 99, 100), ((2, 0), 89, 100), ((2, 2), 79, 100), ((2, 3), 78, 100), ((2, 4), 77, 100), ((2, 5), 76, 100), ((2, 6), 75, 100), ((2, 6), 75, 100), ((2, 6), 76, 100), ((2, 6), 76, 99), ((2, 6), 77, 98), ((2, 6), 77, 97), ((2, 5), 78, 97), ((2, 5), 78, 97), ((2, 5), 79, 97), ((2, 5), 79, 96), ((2, 5), 80, 96), ((2, 5), 80, 96), ((2, 5), 81, 96), ((2, 5), 81, 96)]
    expected_m = [((0, 2), 99, 100), ((0, 1), 98, 100), ((0, 1), 98, 99), ((0, 1), 99, 98), ((0, 2), 99, 98), ((0, 2), 100, 97), ((0, 3), 100, 97), ((0, 3), 100, 96), ((0, 4), 100, 96), ((0, 4), 100, 95), ((0, 4), 100, 94), ((1, 4), 100, 94), ((1, 4), 100, 94), ((1, 4), 100, 93), ((1, 4), 100, 93), ((1, 4), 100, 93), ((1, 4), 100, 93), ((1, 4), 100, 92), ((1, 4), 100, 91), ((0, 4), 100, 91)]
    for i, (f_action, m_action) in enumerate(zip(F_ACTIONS, M_ACTIONS, strict=True)):
        sim.step({HeroId.IKOTOFOSA: HeroAction(f_action), HeroId.IMAHAKI: HeroAction(m_action)})
        f = state.heroes[HeroId.IKOTOFOSA]
        m = state.heroes[HeroId.IMAHAKI]
        assert ((f.position.row, f.position.col), f.stamina, f.battery) == expected_f[i]
        assert ((m.position.row, m.position.col), m.stamina, m.battery) == expected_m[i]
