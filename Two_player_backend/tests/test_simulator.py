from __future__ import annotations

from app.domain.enums import Direction, GameStatus, HeroAction, HeroId
from app.domain.models import HeroCommand
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator


def command(action, direction=None, target=None):
    return HeroCommand(action=action, direction=direction, target=target)


def test_simultaneous_same_destination_is_cancelled():
    game_map = MapParser.parse("""3 7 20
#######
#F.M.K#
#######""")
    state = Simulator.initial_state(game_map)
    state.guard.cooldown = 999
    Simulator(state).step(
        {
            HeroId.IKOTOFOSA: command(HeroAction.MOVE, Direction.RIGHT),
            HeroId.IMAHAKI: command(HeroAction.MOVE, Direction.LEFT),
        }
    )
    assert state.heroes[HeroId.IKOTOFOSA].position.col == 1
    assert state.heroes[HeroId.IMAHAKI].position.col == 3
    assert sum(event.type == "MOVE_COLLISION" for event in state.events) == 2


def test_stone_gives_charge_and_remains_counted():
    game_map = MapParser.parse("""4 7 30
#######
#F+..K#
#M..*.#
#######""")
    state = Simulator.initial_state(game_map)
    state.guard.cooldown = 999
    sim = Simulator(state)
    sim.step({HeroId.IKOTOFOSA: command(HeroAction.MOVE, Direction.RIGHT)})
    assert state.collected_stones == 1
    assert state.healing_charges == 1
    state.heroes[HeroId.IKOTOFOSA].hp = 60
    state.heroes[HeroId.IKOTOFOSA].cooldown = 0
    sim.step({HeroId.IKOTOFOSA: command(HeroAction.HEAL)})
    for _ in range(state.balance.self_heal_ticks):
        sim.step()
    assert state.heroes[HeroId.IKOTOFOSA].hp == 80
    assert state.collected_stones == 1
    assert state.healing_charges == 0


def test_partner_heal_interruption_refunds_charge(state):
    sim = Simulator(state)
    f = state.heroes[HeroId.IKOTOFOSA]
    m = state.heroes[HeroId.IMAHAKI]
    m.position = f.position.moved(1, 0)
    m.hp = 40
    state.healing_charges = 1
    sim.step({HeroId.IKOTOFOSA: command(HeroAction.HEAL, target=HeroId.IMAHAKI)})
    m.position = m.position.moved(2, 0)
    sim.step()
    assert state.healing_charges == 1
    assert f.heal_ticks_remaining == 0
    assert any(event.type == "HEAL_CANCELLED" for event in state.events)


def test_reciprocal_carry_and_drop(state):
    sim = Simulator(state)
    f = state.heroes[HeroId.IKOTOFOSA]
    m = state.heroes[HeroId.IMAHAKI]
    m.position = f.position.moved(1, 0)
    sim.step({HeroId.IKOTOFOSA: command(HeroAction.CARRY, target=HeroId.IMAHAKI)})
    assert f.carrying == HeroId.IMAHAKI
    assert m.carried_by == HeroId.IKOTOFOSA
    f.cooldown = 0
    sim.step({HeroId.IKOTOFOSA: command(HeroAction.DROP, Direction.RIGHT)})
    assert f.carrying is None
    assert m.carried_by is None
    assert m.position == f.position.moved(0, 1)


def test_assisted_jump_validates_landing(state):
    sim = Simulator(state)
    f = state.heroes[HeroId.IKOTOFOSA]
    m = state.heroes[HeroId.IMAHAKI]
    m.position = f.position.moved(1, 0)
    sim.step({HeroId.IKOTOFOSA: command(HeroAction.CARRY, target=HeroId.IMAHAKI)})
    f.cooldown = 0
    sim.step({HeroId.IMAHAKI: command(HeroAction.ASSISTED_JUMP, Direction.RIGHT)})
    assert m.carried_by is None
    assert m.position == f.position.moved(0, 2)
    assert any(event.type == "ASSISTED_JUMP" for event in state.events)


def test_guard_hit_and_invulnerability(state):
    f = state.heroes[HeroId.IKOTOFOSA]
    state.guard.position = f.position
    state.guard.cooldown = 2
    sim = Simulator(state)
    sim.step()
    assert f.hp == 80
    sim.step()
    assert f.hp == 80


def test_ko_rescue_window_expires(state):
    f = state.heroes[HeroId.IKOTOFOSA]
    f.hp = 0
    f.rescue_ticks = 1
    Simulator(state).step()
    assert state.status == GameStatus.LOST
    assert state.end_reason == "RESCUE_WINDOW_EXPIRED"


def test_wait_does_not_pause_world(state):
    initial = state.elapsed_ticks
    Simulator(state).step()
    assert state.elapsed_ticks == initial + 1
    assert state.heroes[HeroId.IKOTOFOSA].stamina == 100


def test_chest_secured_in_bush():
    game_map = MapParser.parse("""4 8 30
########
#F*@.K.#
#M.....#
########""")
    state = Simulator.initial_state(game_map)
    state.guard.cooldown = 999
    Simulator(state).step({HeroId.IKOTOFOSA: command(HeroAction.PUSH, Direction.RIGHT)})
    assert state.secured_chests == 1
    assert not state.chests


def test_exit_requires_both_heroes():
    game_map = MapParser.parse("""4 8 30
########
#F.EEK.#
#M.....#
########""")
    state = Simulator.initial_state(game_map)
    state.guard.cooldown = 999
    state.heroes[HeroId.IKOTOFOSA].position = next(iter(game_map.exits))
    state.heroes[HeroId.IMAHAKI].position = sorted(game_map.exits)[1]
    Simulator(state).step()
    assert state.status == GameStatus.WON


def test_machine_keeps_world_alive_and_makes_noise():
    game_map = MapParser.parse("""5 9 30
#########
#F.X...K#
#.......#
#M......#
#########""")
    state = Simulator.initial_state(game_map)
    state.guard.cooldown = 999
    Simulator(state).step()
    machine = next(iter(state.machines.values()))
    assert machine.position.col == 2  # excavator started facing LEFT
    assert any(event.type == "NOISE" and event.actor == machine.id for event in state.events)
