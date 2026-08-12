from app.domain.enums import HeroAction, HeroId
from app.domain.models import Position
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator

def waits():
    return {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}

def test_excavator_digs_after_five_automatic_steps() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 10 30\n........X.\nF........M\n'))
    sim = Simulator(state)
    for _ in range(10):
        sim.step(waits())
    x = state.machines['X1']
    assert x.position == Position(0, 3)
    assert x.steps_since_dig == 5
    sim.step(waits())
    assert Position(0, 3) in state.holes
    assert x.steps_since_dig == 0

def test_machine_carried_stone_is_still_an_unfinished_objective() -> None:
    state = MapParser.build_initial_state(MapParser.parse('3 5 20\nG+...\n.....\nF...M\n'))
    sim = Simulator(state)
    sim.step(waits())
    sim.step(waits())
    assert state.machines['G1'].carried_stones == 1
    assert not state.objectives_finished
