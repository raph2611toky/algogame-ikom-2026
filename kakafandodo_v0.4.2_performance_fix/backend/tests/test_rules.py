from app.domain.enums import HeroAction, HeroId
from app.domain.models import Position
from app.engine.map_parser import MapParser
from app.engine.rules import Rules
from app.engine.simulator import Simulator

def test_ikotofosa_hops_one_hole_for_ten_stamina() -> None:
    game_map = MapParser.parse('3 3 10\n.M.\n...\nFo.\n')
    state = MapParser.build_initial_state(game_map)
    heros = state.heroes[HeroId.IKOTOFOSA]
    mouvement = Rules.hero_move(state, heros, HeroAction.RIGHT)
    assert mouvement.valid
    assert mouvement.destination == Position(2, 2)
    assert mouvement.stamina_cost == 10

def test_imahaki_climbs_one_tree_for_ten_stamina() -> None:
    game_map = MapParser.parse('3 3 10\n.F.\n...\nMt.\n')
    state = MapParser.build_initial_state(game_map)
    heros = state.heroes[HeroId.IMAHAKI]
    mouvement = Rules.hero_move(state, heros, HeroAction.RIGHT)
    assert mouvement.valid
    assert mouvement.destination == Position(2, 2)
    assert mouvement.stamina_cost == 10

def test_wait_recovers_stamina_every_two_ticks() -> None:
    game_map = MapParser.parse('2 3 10\nF..\nM..\n')
    state = MapParser.build_initial_state(game_map)
    sim = Simulator(state)
    sim.step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.RIGHT})
    assert state.heroes[HeroId.IKOTOFOSA].stamina == 99
    sim.step({HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert state.heroes[HeroId.IKOTOFOSA].stamina == 99
    sim.step({HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert state.heroes[HeroId.IKOTOFOSA].stamina == 100

def test_push_into_bush_secures_chest() -> None:
    game_map = MapParser.parse('2 4 10\nF*@.\nM...\n')
    state = MapParser.build_initial_state(game_map)
    sim = Simulator(state)
    sim.step({HeroId.IKOTOFOSA: HeroAction.PUSH_RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert state.secured_chests == 1
    assert not state.chests
    assert state.heroes[HeroId.IKOTOFOSA].position == Position(0, 1)
    assert state.heroes[HeroId.IKOTOFOSA].stamina == 95

def test_push_into_hole_loses_chest() -> None:
    game_map = MapParser.parse('2 4 10\nF*o.\nM...\n')
    state = MapParser.build_initial_state(game_map)
    sim = Simulator(state)
    sim.step({HeroId.IKOTOFOSA: HeroAction.PUSH_RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert state.lost_chests == 1
    assert not state.chests
