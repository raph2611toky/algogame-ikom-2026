from app.domain.enums import HeroAction, HeroId, MachineAction, Orientation
from app.domain.models import Position
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator


def waits():
    return {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}


def test_hack_cancels_auto_move_rotation_and_dig_without_resetting_dig_counter() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 7 20\n..X....\nF.....M\n'))
    x = state.machines['X1']
    f = state.heroes[HeroId.IKOTOFOSA]
    f.position = x.position
    x.auto_move_pending = True
    x.steps_since_dig = 5
    orientation_avant = x.orientation
    Simulator(state).step({HeroId.IKOTOFOSA: HeroAction.HACK, HeroId.IMAHAKI: HeroAction.WAIT})
    assert x.hacked_by == HeroId.IKOTOFOSA
    assert f.hacking_machine_id == 'X1'
    assert x.position == Position(0, 2)
    assert x.orientation == orientation_avant
    assert not x.auto_move_pending
    assert not x.pending_move
    assert x.steps_since_dig == 5
    assert Position(0, 2) not in state.holes


def test_hacked_grappler_keeps_automatic_cut_and_spends_no_battery_for_it() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 6 20\n.G....\nF....M\n'))
    g = state.machines['G1']
    m = state.heroes[HeroId.IMAHAKI]
    m.position = g.position
    m.hacking_machine_id = g.id
    g.hacked_by = HeroId.IMAHAKI
    state.trees.add(g.position)
    batterie_avant = m.battery
    orientation_avant = g.orientation
    rec = Simulator(state).step({HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.HACK_CW})
    assert g.position not in state.trees
    assert g.last_action == MachineAction.CUT
    assert g.orientation == orientation_avant
    assert m.battery == batterie_avant
    assert rec.effective_actions[HeroId.IMAHAKI] == HeroAction.WAIT


def test_adjacent_machines_never_advance_as_a_convoy() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 7 20\nGGX....\nF.....M\n'))
    state.machines['X1'].orientation = Orientation.FACING_RIGHT
    g1 = state.machines['G1']
    g2 = state.machines['G2']
    x1 = state.machines['X1']
    Simulator(state).step(waits())
    assert [g1.position, g2.position, x1.position] == [Position(0, 0), Position(0, 1), Position(0, 2)]
    assert g1.orientation == Orientation.FACING_DOWN
    assert g2.orientation == Orientation.FACING_DOWN
    assert x1.orientation == Orientation.FACING_RIGHT
    assert x1.auto_move_pending
    assert not g1.auto_move_pending
    assert not g2.auto_move_pending


def test_one_empty_cell_machine_buffer_forces_reorientation() -> None:
    state = MapParser.build_initial_state(MapParser.parse('3 7 20\nG.X....\n.......\nF.....M\n'))
    g = state.machines['G1']
    x = state.machines['X1']
    x.orientation = Orientation.FACING_DOWN
    Simulator(state).step(waits())
    assert g.position == Position(0, 0)
    assert g.orientation == Orientation.FACING_DOWN
    assert not g.auto_move_pending
    assert x.auto_move_pending


def test_buffer_depends_only_on_machine_presence_not_other_machine_orientation() -> None:
    for orientation in Orientation:
        state = MapParser.build_initial_state(MapParser.parse('3 7 20\nG.X....\n.......\nF.....M\n'))
        g = state.machines['G1']
        x = state.machines['X1']
        x.orientation = orientation
        Simulator(state).step(waits())
        assert g.position == Position(0, 0)
        assert g.orientation == Orientation.FACING_DOWN
        assert not g.auto_move_pending


def test_two_machine_chest_squeeze_follows_new_lookahead_before_queueing() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 6 20\nG.*X..\nF....M\n'))
    g = state.machines['G1']
    x = state.machines['X1']
    Simulator(state).step(waits())
    assert state.chests == {Position(0, 2)}
    assert g.position == Position(0, 0)
    assert x.position == Position(0, 3)
    # G may queue one step toward the chest: X is not yet in G's 4-cell
    # look-ahead. X has the chest directly ahead and sees G in its extended
    # six-cell chest look-ahead, therefore X rotates.
    assert g.orientation == Orientation.FACING_RIGHT
    assert x.orientation == Orientation.FACING_DOWN
    assert g.auto_move_pending
    assert not x.auto_move_pending


def test_two_machine_chest_squeeze_rechecks_new_lookahead_when_moves_are_ready() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 6 20\nG.*X..\nF....M\n'))
    g = state.machines['G1']
    x = state.machines['X1']
    g.auto_move_pending = True
    x.auto_move_pending = True
    Simulator(state).step(waits())
    assert state.chests == {Position(0, 2)}
    assert g.position == Position(0, 1)
    assert x.position == Position(0, 3)
    assert g.orientation == Orientation.FACING_RIGHT
    assert x.orientation == Orientation.FACING_DOWN


def test_hero_cannot_push_chest_into_machine_on_other_side() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 5 20\nF*X..\n....M\n'))
    f = state.heroes[HeroId.IKOTOFOSA]
    rec = Simulator(state).step({HeroId.IKOTOFOSA: HeroAction.PUSH_RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert rec.effective_actions[HeroId.IKOTOFOSA] == HeroAction.WAIT
    assert f.position == Position(0, 0)
    assert f.stamina == 100
    assert Position(0, 1) in state.chests


def test_hero_can_push_chest_toward_other_hero_cell() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 5 20\nF*M@.\n.....\n'))
    f = state.heroes[HeroId.IKOTOFOSA]
    rec = Simulator(state).step({HeroId.IKOTOFOSA: HeroAction.PUSH_RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert rec.effective_actions[HeroId.IKOTOFOSA] == HeroAction.PUSH_RIGHT
    assert f.position == Position(0, 1)
    assert Position(0, 2) in state.chests


def test_hacked_machine_refuses_hack_move_with_one_cell_machine_buffer() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 7 20\nX.G....\nF.....M\n'))
    x = state.machines['X1']
    x.orientation = Orientation.FACING_RIGHT
    f = state.heroes[HeroId.IKOTOFOSA]
    f.position = x.position
    f.hacking_machine_id = x.id
    x.hacked_by = HeroId.IKOTOFOSA
    batterie_avant = f.battery
    rec = Simulator(state).step({HeroId.IKOTOFOSA: HeroAction.HACK_MOVE, HeroId.IMAHAKI: HeroAction.WAIT})
    assert rec.effective_actions[HeroId.IKOTOFOSA] == HeroAction.WAIT
    assert f.battery == batterie_avant
    assert x.position == Position(0, 0)
    assert x.orientation == Orientation.FACING_RIGHT
    assert not x.pending_move


def test_hacked_machine_pending_move_is_cancelled_by_new_buffer_without_rotation() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 7 20\nX.G....\nF.....M\n'))
    x = state.machines['X1']
    x.orientation = Orientation.FACING_RIGHT
    f = state.heroes[HeroId.IKOTOFOSA]
    f.position = x.position
    f.hacking_machine_id = x.id
    x.hacked_by = HeroId.IKOTOFOSA
    x.pending_move = True
    rec = Simulator(state).step(waits())
    assert x.position == Position(0, 0)
    assert x.orientation == Orientation.FACING_RIGHT
    assert not x.pending_move
    assert rec.machine_actions['X1'] == MachineAction.WAIT


def test_controlled_machine_does_not_queue_chest_push_when_machine_is_behind_chest() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 6 20\nX*G...\nF....M\n'))
    x = state.machines['X1']
    x.orientation = Orientation.FACING_RIGHT
    f = state.heroes[HeroId.IKOTOFOSA]
    f.position = x.position
    f.hacking_machine_id = x.id
    x.hacked_by = HeroId.IKOTOFOSA
    batterie_avant = f.battery
    rec = Simulator(state).step({HeroId.IKOTOFOSA: HeroAction.HACK_MOVE, HeroId.IMAHAKI: HeroAction.WAIT})
    assert rec.effective_actions[HeroId.IKOTOFOSA] == HeroAction.WAIT
    assert f.battery == batterie_avant
    assert not x.pending_move
    assert Position(0, 1) in state.chests


def test_recommended_small_mechanics_map_contains_every_game_element() -> None:
    from pathlib import Path
    game_map = MapParser.parse(Path('maps/mechanics_4x5.txt').read_text(encoding='utf-8'))
    assert (game_map.height, game_map.width) == (4, 5)
    assert len(game_map.initial_machines) == 2
    assert game_map.rocks
    assert game_map.trees
    assert game_map.holes
    assert game_map.bushes
    assert game_map.stones
    assert game_map.chests
    assert set(game_map.initial_hero_positions) == {HeroId.IKOTOFOSA, HeroId.IMAHAKI}


def test_double_reference_size_map_runs_complete_adaptive_simulation() -> None:
    from pathlib import Path
    from app.engine.strategy_v2 import AdaptiveScoreStrategy
    game_map = MapParser.parse(Path('maps/evaluation_10x14.txt').read_text(encoding='utf-8'))
    assert (game_map.height, game_map.width) == (10, 14)
    state = MapParser.build_initial_state(game_map)
    result = Simulator(state).run_strategy(AdaptiveScoreStrategy())
    assert result.ticks
    assert len(result.ticks) <= game_map.time_limit
    assert state.lost_chests == 0
    assert state.secured_chests == 1
    assert state.total_hero_stones == 2


def test_adaptive_strategy_chooses_only_one_hero_to_push_same_chest() -> None:
    from app.engine.strategy_v2 import AdaptiveScoreStrategy
    state = MapParser.build_initial_state(MapParser.parse('2 5 20\nF*M@.\n.....\n'))
    actions = AdaptiveScoreStrategy().next_actions(state)
    pushes = [action for action in actions.values() if action in {HeroAction.PUSH_UP, HeroAction.PUSH_DOWN, HeroAction.PUSH_LEFT, HeroAction.PUSH_RIGHT}]
    assert len(pushes) == 1


def test_chest_lookahead_supersedes_old_two_cell_buffer_rule() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 6 20\nG.*X..\nF....M\n'))
    g = state.machines['G1']
    x = state.machines['X1']
    Simulator(state).step(waits())
    assert g.position == Position(0, 0)
    assert x.position == Position(0, 3)
    assert state.chests == {Position(0, 2)}
    assert g.orientation == Orientation.FACING_RIGHT
    assert x.orientation == Orientation.FACING_DOWN
    assert g.auto_move_pending
    assert not x.auto_move_pending


def test_two_cell_chest_machine_buffer_blocks_both_hacked_hack_moves() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 6 20\nG.*X..\nM....F\n'))
    g = state.machines['G1']
    x = state.machines['X1']
    m = state.heroes[HeroId.IMAHAKI]
    f = state.heroes[HeroId.IKOTOFOSA]
    m.position = g.position
    f.position = x.position
    m.hacking_machine_id = g.id
    f.hacking_machine_id = x.id
    g.hacked_by = HeroId.IMAHAKI
    x.hacked_by = HeroId.IKOTOFOSA
    batterie_m = m.battery
    batterie_f = f.battery
    rec = Simulator(state).step({HeroId.IKOTOFOSA: HeroAction.HACK_MOVE, HeroId.IMAHAKI: HeroAction.HACK_MOVE})
    assert rec.effective_actions[HeroId.IKOTOFOSA] == HeroAction.WAIT
    assert rec.effective_actions[HeroId.IMAHAKI] == HeroAction.WAIT
    assert f.battery == batterie_f
    assert m.battery == batterie_m
    assert g.orientation == Orientation.FACING_RIGHT
    assert x.orientation == Orientation.FACING_LEFT
    assert not g.pending_move
    assert not x.pending_move


def test_hero_does_not_trigger_machine_buffer() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 7 20\nG.F....\n......M\n'))
    g = state.machines['G1']
    sim = Simulator(state)
    sim.step(waits())
    assert g.auto_move_pending
    sim.step(waits())
    assert g.position == Position(0, 1)
    assert not g.auto_move_pending
    sim.step(waits())
    assert g.auto_move_pending
    sim.step(waits())
    assert g.position == Position(0, 2)
    assert state.heroes[HeroId.IKOTOFOSA].position == Position(0, 2)


def test_rock_is_not_a_machine_buffer_but_blocks_when_directly_reached() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 7 20\nG.#....\nF.....M\n'))
    g = state.machines['G1']
    sim = Simulator(state)
    sim.step(waits())
    assert g.auto_move_pending
    sim.step(waits())
    assert g.position == Position(0, 1)
    sim.step(waits())
    assert g.position == Position(0, 1)
    assert g.orientation == Orientation.FACING_DOWN
    assert not g.auto_move_pending
