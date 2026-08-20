import pytest

from app.domain.enums import HeroAction, HeroId, MachineAction, Orientation
from app.domain.models import Position
from app.engine.chest_planner import plan_chest_to_bush
from app.engine.map_parser import ElevationFormatError, MapParser
from app.engine.pathfinding import find_path
from app.engine.rules import Rules
from app.engine.simulator import Simulator


def waits():
    return {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}


def test_legacy_map_without_elevation_is_flat_zero_and_backward_compatible() -> None:
    game_map = MapParser.parse('2 4 20\nF#.M\n..@.\n')
    assert game_map.has_elevation is False
    assert game_map.elevations == ((0, 0, 0, 0), (0, 0, 0, 0))


def test_explicit_elevation_requires_zero_only_on_rocks_and_1_to_9_elsewhere() -> None:
    game_map = MapParser.parse('2 3 20\nF#M\n.@.\n', '101\n111\n')
    assert game_map.has_elevation is True
    assert game_map.elevation_at(Position(0, 1)) == 0
    with pytest.raises(ElevationFormatError):
        MapParser.parse('2 3 20\nF#M\n.@.\n', '111\n111\n')
    with pytest.raises(ElevationFormatError):
        MapParser.parse('2 3 20\nF#M\n.@.\n', '100\n111\n')


def test_elevation_dimensions_must_match_map_exactly() -> None:
    with pytest.raises(ElevationFormatError):
        MapParser.parse('2 3 20\nF.M\n.@.\n', '111\n11\n')


def test_faq_hero_walks_onto_and_over_chest_without_carrying_it() -> None:
    state = MapParser.build_initial_state(MapParser.parse('1 6 20\nF*...M\n'))
    sim = Simulator(state)
    sim.step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert state.heroes[HeroId.IKOTOFOSA].position == Position(0, 1)
    assert state.heroes[HeroId.IKOTOFOSA].stamina == 99
    assert state.chests == {Position(0, 1)}
    sim.step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert state.heroes[HeroId.IKOTOFOSA].position == Position(0, 2)
    assert state.heroes[HeroId.IKOTOFOSA].stamina == 98
    assert state.chests == {Position(0, 1)}


def test_hero_uphill_costs_three_same_level_one_downhill_zero() -> None:
    state = MapParser.build_initial_state(MapParser.parse('1 5 20\nF...M\n', '12321\n'))
    sim = Simulator(state)
    sim.step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert state.heroes[HeroId.IKOTOFOSA].stamina == 97
    sim.step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert state.heroes[HeroId.IKOTOFOSA].stamina == 94
    sim.step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert state.heroes[HeroId.IKOTOFOSA].stamina == 94


def test_hero_cannot_climb_three_levels_or_descend_five_levels() -> None:
    up = MapParser.build_initial_state(MapParser.parse('1 5 20\nF...M\n', '14111\n'))
    rec = Simulator(up).step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert rec.effective_actions[HeroId.IKOTOFOSA] == HeroAction.WAIT
    assert up.heroes[HeroId.IKOTOFOSA].position == Position(0, 0)

    down = MapParser.build_initial_state(MapParser.parse('1 5 20\nF...M\n', '72111\n'))
    rec = Simulator(down).step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert rec.effective_actions[HeroId.IKOTOFOSA] == HeroAction.WAIT
    assert down.heroes[HeroId.IKOTOFOSA].position == Position(0, 0)


def test_hole_hop_uses_start_to_landing_elevation_and_keeps_special_cost_ten() -> None:
    bad = MapParser.build_initial_state(MapParser.parse('1 5 20\nFo..M\n', '11511\n'))
    rec = Simulator(bad).step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert rec.effective_actions[HeroId.IKOTOFOSA] == HeroAction.WAIT

    good = MapParser.build_initial_state(MapParser.parse('1 5 20\nFo..M\n', '11311\n'))
    Simulator(good).step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert good.heroes[HeroId.IKOTOFOSA].position == Position(0, 2)
    assert good.heroes[HeroId.IKOTOFOSA].stamina == 90


def test_hero_cannot_push_chest_uphill() -> None:
    state = MapParser.build_initial_state(MapParser.parse('1 5 20\nF*.@M\n', '12311\n'))
    rec = Simulator(state).step({HeroId.IKOTOFOSA: HeroAction.PUSH_RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert rec.effective_actions[HeroId.IKOTOFOSA] == HeroAction.WAIT
    assert state.chests == {Position(0, 1)}
    assert state.heroes[HeroId.IKOTOFOSA].stamina == 100


def test_chest_drop_of_five_levels_is_destroyed_even_if_destination_is_bush() -> None:
    state = MapParser.build_initial_state(MapParser.parse('1 4 20\nF*@M\n', '7721\n'))
    rec = Simulator(state).step({HeroId.IKOTOFOSA: HeroAction.PUSH_RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert rec.effective_actions[HeroId.IKOTOFOSA] == HeroAction.PUSH_RIGHT
    assert state.lost_chests == 1
    assert state.secured_chests == 0
    assert not state.chests
    assert any(event.type == 'CHEST_DESTROYED_CLIFF' for event in rec.events)


def test_machine_can_move_delta_four_but_not_five() -> None:
    allowed = MapParser.build_initial_state(MapParser.parse('2 6 20\nG....X\nF....M\n', '155555\n111111\n'))
    sim = Simulator(allowed)
    sim.step(waits())
    assert allowed.machines['G1'].auto_move_pending
    sim.step(waits())
    assert allowed.machines['G1'].position == Position(0, 1)

    blocked = MapParser.build_initial_state(MapParser.parse('2 6 20\nG....X\nF....M\n', '166666\n111111\n'))
    rec = Simulator(blocked).step(waits())
    assert blocked.machines['G1'].position == Position(0, 0)
    assert blocked.machines['G1'].orientation == Orientation.FACING_DOWN
    assert any(e.data.get('reason') == 'machine_elevation_difference_too_high' for e in rec.events)


def test_machine_chest_uphill_limit_is_two_levels() -> None:
    allowed = MapParser.build_initial_state(MapParser.parse('2 6 20\nG*...X\nF....M\n', '123111\n111111\n'))
    sim = Simulator(allowed)
    sim.step(waits())
    sim.step(waits())
    assert Position(0, 2) in allowed.chests

    blocked = MapParser.build_initial_state(MapParser.parse('2 6 20\nG*...X\nF....M\n', '125111\n111111\n'))
    rec = Simulator(blocked).step(waits())
    assert Position(0, 1) in blocked.chests
    assert blocked.machines['G1'].orientation == Orientation.FACING_DOWN
    assert any(e.data.get('reason') == 'machine_chest_uphill_too_steep' for e in rec.events)


def test_machine_can_push_chest_down_cliff_but_chest_is_destroyed() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 6 20\nG*...X\nF....M\n', '772111\n111111\n'))
    sim = Simulator(state)
    sim.step(waits())
    rec = sim.step(waits())
    assert state.lost_chests == 1
    assert Position(0, 1) == state.machines['G1'].position
    assert any(event.type == 'CHEST_DESTROYED_CLIFF' for event in rec.events)


@pytest.mark.parametrize('blocker', [Position(1, 2), Position(1, 3), Position(0, 2), Position(2, 2)])
def test_machine_checks_all_four_move_lookahead_positions(blocker: Position) -> None:
    state = MapParser.build_initial_state(MapParser.parse('4 6 20\n......\n.G...X\n......\nF....M\n'))
    g = state.machines['G1']
    x = state.machines['X1']
    g.orientation = Orientation.FACING_RIGHT
    x.position = blocker
    rec = Simulator(state).step(waits())
    assert g.position == Position(1, 1)
    assert g.orientation == Orientation.FACING_DOWN
    assert any(str(e.data.get('reason', '')).startswith('machine_lookahead_') for e in rec.events if e.actor == 'G1')


def test_pending_automatic_move_rechecks_lookahead_on_second_tick() -> None:
    state = MapParser.build_initial_state(MapParser.parse('4 7 20\n.......\n.G....X\n.......\nF.....M\n'))
    g = state.machines['G1']
    x = state.machines['X1']
    sim = Simulator(state)
    sim.step(waits())
    assert g.auto_move_pending
    x.position = Position(0, 2)
    rec = sim.step(waits())
    assert g.position == Position(1, 1)
    assert g.orientation == Orientation.FACING_DOWN
    assert not g.auto_move_pending
    assert any(str(e.data.get('reason', '')).startswith('machine_lookahead_') for e in rec.events if e.actor == 'G1')


def test_hacked_pending_move_rechecks_lookahead_and_waits_without_rotation() -> None:
    state = MapParser.build_initial_state(MapParser.parse('4 7 20\n.......\n.G....X\n.......\nF.....M\n'))
    g = state.machines['G1']
    x = state.machines['X1']
    m = state.heroes[HeroId.IMAHAKI]
    m.position = g.position
    m.hacking_machine_id = g.id
    g.hacked_by = HeroId.IMAHAKI
    g.pending_move = True
    x.position = Position(0, 2)
    rec = Simulator(state).step(waits())
    assert g.position == Position(1, 1)
    assert g.orientation == Orientation.FACING_RIGHT
    assert g.last_action == MachineAction.WAIT
    assert not g.pending_move
    assert any(str(e.data.get('reason', '')).startswith('machine_lookahead_') for e in rec.events if e.actor == 'G1')


def test_hack_move_is_ignored_before_spending_battery_when_lookahead_blocks() -> None:
    state = MapParser.build_initial_state(MapParser.parse('4 7 20\n..X....\n.G.....\n.......\nF.....M\n'))
    g = state.machines['G1']
    m = state.heroes[HeroId.IMAHAKI]
    m.position = g.position
    m.hacking_machine_id = g.id
    g.hacked_by = HeroId.IMAHAKI
    battery = m.battery
    rec = Simulator(state).step({HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.HACK_MOVE})
    assert rec.effective_actions[HeroId.IMAHAKI] == HeroAction.WAIT
    assert m.battery == battery
    assert g.orientation == Orientation.FACING_RIGHT
    assert not g.pending_move


def test_direct_machine_chest_push_yields_to_hero_in_first_three_cells() -> None:
    state = MapParser.build_initial_state(MapParser.parse('3 6 20\n..F...\n..*G..\nM.....\n'))
    g = state.machines['G1']
    g.orientation = Orientation.FACING_LEFT
    rec = Simulator(state).step(waits())
    assert g.position == Position(1, 3)
    assert g.orientation == Orientation.FACING_UP
    assert any(str(e.data.get('reason', '')).startswith('chest_hero_priority_') for e in rec.events if e.actor == 'G1')


def test_direct_machine_chest_push_scans_all_six_cells_for_other_machines() -> None:
    state = MapParser.build_initial_state(MapParser.parse('3 6 20\n.X....\n..*G..\nF....M\n'))
    g = state.machines['G1']
    g.orientation = Orientation.FACING_LEFT
    rec = Simulator(state).step(waits())
    assert g.position == Position(1, 3)
    assert g.orientation == Orientation.FACING_UP
    assert any(str(e.data.get('reason', '')).startswith('chest_machine_lookahead_') for e in rec.events if e.actor == 'G1')


def test_nearby_chest_plus_hero_behind_it_blocks_machine_to_give_hero_priority() -> None:
    state = MapParser.build_initial_state(MapParser.parse('5 6 20\n..F...\n..*...\n...G..\n......\nM.....\n'))
    g = state.machines['G1']
    g.orientation = Orientation.FACING_LEFT
    rec = Simulator(state).step(waits())
    assert g.position == Position(2, 3)
    assert g.orientation == Orientation.FACING_UP
    assert any(str(e.data.get('reason', '')).startswith('nearby_chest_hero_priority_') for e in rec.events if e.actor == 'G1')


def test_hero_push_wins_when_machine_would_enter_chest_destination() -> None:
    state = MapParser.build_initial_state(MapParser.parse('3 6 20\n......\nF*.G..\n.....M\n'))
    g = state.machines['G1']
    g.orientation = Orientation.FACING_LEFT
    rec = Simulator(state).step({HeroId.IKOTOFOSA: HeroAction.PUSH_RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert rec.effective_actions[HeroId.IKOTOFOSA] == HeroAction.PUSH_RIGHT
    assert state.heroes[HeroId.IKOTOFOSA].position == Position(1, 1)
    assert Position(1, 2) in state.chests
    assert g.position == Position(1, 3)


def test_lookahead_reason_has_priority_over_elevation_reason() -> None:
    state = MapParser.build_initial_state(MapParser.parse('4 6 20\n......\n.G.X..\n......\nF....M\n', '111111\n119111\n111111\n111111\n'))
    rec = Simulator(state).step(waits())
    g_events = [e for e in rec.events if e.actor == 'G1' and e.type == 'MACHINE_ROTATED']
    assert g_events
    assert str(g_events[0].data['reason']).startswith('machine_lookahead_')


def test_pathfinding_and_chest_planner_are_elevation_aware() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 5 50\nF*.@M\n.....\n', '14511\n11111\n'))
    assert find_path(state, HeroId.IKOTOFOSA, Position(0, 1)) is None
    assert plan_chest_to_bush(state, HeroId.IKOTOFOSA, Position(0, 1), Position(0, 3)) is None


def test_machine_planner_does_not_treat_current_hero_priority_as_static_wall() -> None:
    """A hero can move before the planned machine reaches a future chest-adjacent cell.

    Runtime look-ahead still gives the hero priority at execution time; the planner
    must not declare the whole machine route impossible only because the hero is
    currently in a potential push position several ticks in the future.
    """
    from app.engine.machine_planner import plan_machine_to_obstacle

    state = MapParser.build_initial_state(
        MapParser.parse('3 9 120\n#########\n#M*t.@GF#\n#########\n')
    )
    plan = plan_machine_to_obstacle(state, state.machines['G1'], Position(1, 3))
    assert plan is not None
    assert HeroAction.HACK_MOVE in plan.actions


def test_maps_api_accepts_optional_elevation_and_preserves_legacy_zero_grid() -> None:
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    map_text = '2 3 20\nF#M\n.@.\n'
    elevation_text = '101\n111\n'

    explicit = client.post(
        '/api/v1/maps/parse',
        json={'name': 'elevated', 'map_text': map_text, 'elevation_text': elevation_text},
    )
    assert explicit.status_code == 200
    assert explicit.json()['has_elevation'] is True
    assert explicit.json()['elevation_rows'] == ['101', '111']

    legacy = client.post('/api/v1/maps/parse', json={'name': 'flat', 'map_text': map_text})
    assert legacy.status_code == 200
    assert legacy.json()['has_elevation'] is False
    assert legacy.json()['elevation_rows'] == ['000', '000']


def test_maps_multipart_accepts_map_and_optional_elevation_file() -> None:
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.post(
        '/api/v1/maps/upload',
        files={
            'file': ('map.txt', '2 3 20\nF#M\n.@.\n', 'text/plain'),
            'elevation_file': ('elevation.txt', '101\n111\n', 'text/plain'),
        },
    )
    assert response.status_code == 200
    assert response.json()['has_elevation'] is True
    assert response.json()['elevation_rows'] == ['101', '111']



def test_same_level_costs_one_and_downhill_does_not_count_as_wait() -> None:
    state = MapParser.build_initial_state(MapParser.parse('1 4 20\nF..M\n', '2211\n'))
    f = state.heroes[HeroId.IKOTOFOSA]
    f.recovery_seconds = 1
    sim = Simulator(state)
    rec1 = sim.step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert f.stamina == 99  # same level -> 1
    rec2 = sim.step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert f.stamina == 99  # downhill -> 0
    assert not any(e.type == 'STAMINA_RECOVERED' and e.actor == 'F' for e in rec2.events)
    assert f.recovery_seconds == 0


def test_hero_up_two_and_down_four_are_legal_boundaries() -> None:
    uphill = MapParser.build_initial_state(MapParser.parse('1 4 20\nF..M\n', '1311\n'))
    Simulator(uphill).step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert uphill.heroes[HeroId.IKOTOFOSA].position == Position(0, 1)
    assert uphill.heroes[HeroId.IKOTOFOSA].stamina == 97

    downhill = MapParser.build_initial_state(MapParser.parse('1 4 20\nF..M\n', '5111\n'))
    Simulator(downhill).step({HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert downhill.heroes[HeroId.IKOTOFOSA].position == Position(0, 1)
    assert downhill.heroes[HeroId.IKOTOFOSA].stamina == 100


def test_tree_climb_uses_start_to_landing_elevation() -> None:
    bad = MapParser.build_initial_state(MapParser.parse('1 5 20\nMt..F\n', '11511\n'))
    rec = Simulator(bad).step({HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.RIGHT})
    assert rec.effective_actions[HeroId.IMAHAKI] == HeroAction.WAIT

    good = MapParser.build_initial_state(MapParser.parse('1 5 20\nMt..F\n', '11311\n'))
    Simulator(good).step({HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.RIGHT})
    assert good.heroes[HeroId.IMAHAKI].position == Position(0, 2)
    assert good.heroes[HeroId.IMAHAKI].stamina == 90


def test_push_checks_hero_step_elevation_separately_from_chest_elevation() -> None:
    # Chest would move flat/down, but F would have to step +3 into the chest's
    # former cell, which is forbidden by the general hero elevation rule.
    state = MapParser.build_initial_state(MapParser.parse('1 5 20\nF*..M\n', '14441\n'))
    rec = Simulator(state).step({HeroId.IKOTOFOSA: HeroAction.PUSH_RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert rec.effective_actions[HeroId.IKOTOFOSA] == HeroAction.WAIT
    assert state.chests == {Position(0, 1)}


def test_hero_push_same_or_downhill_costs_exactly_five() -> None:
    same = MapParser.build_initial_state(MapParser.parse('1 5 20\nF*.@M\n', '22221\n'))
    Simulator(same).step({HeroId.IKOTOFOSA: HeroAction.PUSH_RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert same.heroes[HeroId.IKOTOFOSA].stamina == 95
    assert Position(0, 2) in same.chests

    down = MapParser.build_initial_state(MapParser.parse('1 5 20\nF*.@M\n', '77331\n'))
    Simulator(down).step({HeroId.IKOTOFOSA: HeroAction.PUSH_RIGHT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert down.heroes[HeroId.IKOTOFOSA].stamina == 95
    assert Position(0, 2) in down.chests


def test_machine_down_four_legal_down_five_blocked() -> None:
    allowed = MapParser.build_initial_state(MapParser.parse('2 6 20\nG....X\nF....M\n', '511111\n111111\n'))
    sim = Simulator(allowed)
    sim.step(waits())
    sim.step(waits())
    assert allowed.machines['G1'].position == Position(0, 1)

    blocked = MapParser.build_initial_state(MapParser.parse('2 6 20\nG....X\nF....M\n', '611111\n111111\n'))
    rec = Simulator(blocked).step(waits())
    assert blocked.machines['G1'].position == Position(0, 0)
    assert any(e.data.get('reason') == 'machine_elevation_difference_too_high' for e in rec.events if e.actor == 'G1')


def test_machine_can_push_chest_uphill_exactly_two_but_not_three() -> None:
    allowed = MapParser.build_initial_state(MapParser.parse('2 6 20\nG*...X\nF....M\n', '224111\n111111\n'))
    sim = Simulator(allowed)
    sim.step(waits())
    sim.step(waits())
    assert Position(0, 2) in allowed.chests

    blocked = MapParser.build_initial_state(MapParser.parse('2 6 20\nG*...X\nF....M\n', '225111\n111111\n'))
    rec = Simulator(blocked).step(waits())
    assert Position(0, 1) in blocked.chests
    assert any(e.data.get('reason') == 'machine_chest_uphill_too_steep' for e in rec.events if e.actor == 'G1')


def test_normal_machine_lookahead_ignores_heroes_and_props() -> None:
    state = MapParser.build_initial_state(MapParser.parse('4 7 20\n..F....\n.G+...X\n..@....\n......M\n'))
    g = state.machines['G1']
    g.orientation = Orientation.FACING_RIGHT
    sim = Simulator(state)
    rec1 = sim.step(waits())
    assert g.auto_move_pending
    rec2 = sim.step(waits())
    assert g.position == Position(1, 2)
    assert g.orientation == Orientation.FACING_RIGHT


def test_machine_move_lookahead_order_matches_clarified_right_facing_diagram() -> None:
    from app.engine.rules import Rules
    state = MapParser.build_initial_state(MapParser.parse('4 6 20\n......\n.G...X\n......\nF....M\n'))
    g = state.machines['G1']
    g.orientation = Orientation.FACING_RIGHT
    assert Rules.machine_move_lookahead_positions(g) == (
        Position(1, 2),  # 1 destination
        Position(1, 3),  # 2 two-ahead
        Position(0, 2),  # 3 upper side
        Position(2, 2),  # 4 lower side
    )


@pytest.mark.parametrize('index', range(6))
def test_direct_chest_push_checks_each_of_six_machine_lookahead_cells(index: int) -> None:
    from app.engine.rules import Rules
    state = MapParser.build_initial_state(MapParser.parse('5 8 20\n.......X\n........\n...*G...\n........\nF......M\n'))
    g = state.machines['G1']
    x = state.machines['X1']
    g.orientation = Orientation.FACING_LEFT
    first, extra = Rules.machine_chest_lookahead_positions(g)
    candidates = first + extra
    x.position = candidates[index]
    rec = Simulator(state).step(waits())
    assert g.position == Position(2, 4)
    assert g.orientation == Orientation.FACING_UP
    reasons = [str(e.data.get('reason', '')) for e in rec.events if e.actor == 'G1']
    if index < 3:
        # The first three chest cells overlap the generic machine look-ahead;
        # that generic collision scan has priority and is equivalent here.
        assert any(r.startswith('machine_lookahead_') or r.startswith('chest_machine_lookahead_') for r in reasons)
    else:
        assert any(r.startswith('chest_machine_lookahead_') for r in reasons)


@pytest.mark.parametrize('branch', [0, 1, 2])
def test_nearby_chest_hero_priority_checks_all_three_branches(branch: int) -> None:
    # Build a clean state and place one chest beside the destination plus a hero
    # directly behind it. Ordinary machine MOVE must yield to the potential hero
    # PUSH into the same destination.
    from app.engine.rules import Rules
    state = MapParser.build_initial_state(MapParser.parse('7 9 20\n........X\n.........\n.........\n....G....\n.........\n.........\nF.......M\n'))
    g = state.machines['G1']
    g.orientation = Orientation.FACING_LEFT
    (dr, dc), (sr, sc), destination = Rules._forward_geometry(g.position, g.orientation)
    vectors = ((dr, dc), (sr, sc), (-sr, -sc))
    vr, vc = vectors[branch]
    chest = destination.moved(vr, vc)
    hero_pos = chest.moved(vr, vc)
    state.chests = {chest}
    state.heroes[HeroId.IKOTOFOSA].position = hero_pos
    rec = Simulator(state).step(waits())
    assert g.position == Position(3, 4)
    assert g.orientation == Orientation.FACING_UP
    assert any(str(e.data.get('reason', '')).startswith('nearby_chest_hero_priority_') for e in rec.events if e.actor == 'G1')


def test_explicit_elevation_zero_is_forbidden_on_hole_tree_and_empty_cells() -> None:
    with pytest.raises(ElevationFormatError):
        MapParser.parse('2 4 20\nFt.M\n.o@.\n', '1011\n1111\n')
    with pytest.raises(ElevationFormatError):
        MapParser.parse('2 4 20\nF..M\n.o@.\n', '1111\n1011\n')


def test_replay_api_uses_elevation_rules() -> None:
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.post(
        '/api/v1/simulations/replay',
        json={
            'mission': {
                'name': 'elev-replay',
                'map_text': '1 4 10\nF..M\n',
                'elevation_text': '1311\n',
            },
            'actions': [{'F': 'RIGHT', 'M': 'WAIT'}],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['map']['has_elevation'] is True
    assert payload['ticks'][0]['state']['heroes']['F']['stamina'] == 97
    assert payload['ticks'][0]['state']['heroes']['F']['position'] == {'row': 0, 'col': 1}


def test_simulation_job_preserves_optional_elevation_text() -> None:
    from time import sleep
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    created = client.post(
        '/api/v1/simulation-jobs',
        json={
            'mission': {
                'name': 'elev-job',
                'map_text': '1 5 20\nF+..M\n',
                'elevation_text': '13111\n',
            },
            'strategy': {'name': 'heuristic_v1'},
        },
    )
    assert created.status_code == 202
    job_id = created.json()['job_id']
    for _ in range(100):
        status = client.get(f'/api/v1/simulation-jobs/{job_id}')
        assert status.status_code == 200
        if status.json()['status'] in {'completed', 'failed'}:
            break
        sleep(0.01)
    assert status.json()['status'] == 'completed'
    result = client.get(f'/api/v1/simulation-jobs/{job_id}/result')
    assert result.status_code == 200
    simulation = result.json()['simulation']
    assert simulation['map']['has_elevation'] is True
    assert simulation['map']['elevation_rows'] == ['13111']


def test_contract_exposes_backward_compatible_elevation_rules() -> None:
    from fastapi.testclient import TestClient
    from app.main import app

    payload = TestClient(app).get('/api/v1/contracts').json()
    assert payload['map']['elevation']['optional'] is True
    assert payload['map']['elevation']['reachable_range'] == '1..9'
    assert payload['map']['elevation']['rock_value'] == 0
    assert payload['map']['elevation']['legacy_default'] == 0
    assert payload['resources']['uphill_move_stamina'] == 3
    assert payload['resources']['downhill_move_stamina'] == 0
    assert payload['resources']['push_stamina'] == 5


@pytest.mark.parametrize(
    ('orientation', 'expected'),
    [
        (Orientation.FACING_RIGHT, (Position(2, 3), Position(2, 4), Position(1, 3), Position(3, 3))),
        (Orientation.FACING_LEFT, (Position(2, 1), Position(2, 0), Position(3, 1), Position(1, 1))),
        (Orientation.FACING_UP, (Position(1, 2), Position(0, 2), Position(1, 1), Position(1, 3))),
        (Orientation.FACING_DOWN, (Position(3, 2), Position(4, 2), Position(3, 3), Position(3, 1))),
    ],
)
def test_move_lookahead_geometry_rotates_for_all_orientations(orientation: Orientation, expected: tuple[Position, ...]) -> None:
    state = MapParser.build_initial_state(MapParser.parse('5 5 20\nF....\n.....\n..G..\n.....\n....M\n'))
    g = state.machines['G1']
    g.orientation = orientation
    assert Rules.machine_move_lookahead_positions(g) == expected


def test_direct_chest_six_cell_geometry_matches_official_facing_left_diagram() -> None:
    state = MapParser.build_initial_state(MapParser.parse('3 6 20\nF.....\n..*G..\n.....M\n'))
    g = state.machines['G1']
    g.orientation = Orientation.FACING_LEFT
    first_three, extra_three = Rules.machine_chest_lookahead_positions(g)
    assert set(first_three) == {Position(0, 2), Position(1, 1), Position(2, 2)}
    assert set(extra_three) == {Position(0, 1), Position(1, 0), Position(2, 1)}


def test_faq_excavator_dig_on_bush_keeps_bush_as_chest_hiding_spot() -> None:
    # X starts on @ and is due to DIG immediately. The bush must remain usable
    # even though the same cell is then also a hole.
    state = MapParser.build_initial_state(MapParser.parse('2 5 30\nX...M\nF..*@\n'))
    x = state.machines['X1']
    bush = Position(0, 0)
    # Move the static bush to X's current cell for the edge-case state while
    # keeping a second row for F/M and chest pushing setup.
    state.game_map.bushes.clear()
    state.game_map.bushes.add(bush)
    x.steps_since_dig = 5
    sim = Simulator(state)
    sim.step(waits())
    assert bush in state.holes
    assert bush in state.game_map.bushes

    # Put a chest immediately to the right and F on its right side, then push
    # LEFT into the co-located hole+bush. Bush wins over hole; only a >=5 cliff
    # would destroy it before the hiding rule.
    state.chests = {Position(0, 1)}
    # The excavator may leave the dug bush afterwards; move it away so the
    # chest-push test isolates the hole+bush destination priority.
    x.position = Position(1, 4)
    f = state.heroes[HeroId.IKOTOFOSA]
    f.position = Position(0, 2)
    before_lost = state.lost_chests
    before_secured = state.secured_chests
    rec = sim.step({HeroId.IKOTOFOSA: HeroAction.PUSH_LEFT, HeroId.IMAHAKI: HeroAction.WAIT})
    assert rec.effective_actions[HeroId.IKOTOFOSA] == HeroAction.PUSH_LEFT
    assert state.secured_chests == before_secured + 1
    assert state.lost_chests == before_lost
    assert Position(0, 1) not in state.chests


def test_direct_chest_planner_accepts_bush_that_is_also_a_hole() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 5 30\nF*.@M\n.....\n'))
    bush = Position(0, 3)
    state.holes.add(bush)
    plan = plan_chest_to_bush(state, HeroId.IKOTOFOSA, Position(0, 1), bush, optimize_for_score=True)
    assert plan is not None
    assert plan.actions[-1] == HeroAction.PUSH_RIGHT


def test_direct_chest_planner_rejects_push_destination_occupied_by_machine() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 6 30\nF*X.@M\n......\n'))
    # The only straight push starts into X, so the planner must not return an
    # optimistic direct plan that runtime would coerce to WAIT.
    plan = plan_chest_to_bush(
        state,
        HeroId.IKOTOFOSA,
        Position(0, 1),
        Position(0, 4),
        optimize_for_score=True,
        avoid_machine_push_destinations=True,
    )
    assert plan is None or plan.actions[0] != HeroAction.PUSH_RIGHT
