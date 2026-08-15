from __future__ import annotations

from app.domain.enums import HeroAction, HeroId
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
from app.engine.strategy_v4 import ChestFirstPortfolioStrategy
from app.schemas.simulation import StrategyOptions
from app.services.simulation_service import SimulationService

OFFICIAL = """5 7 100
G+.M..+
.###tt#
.o*.+.@
o##t#tX
.F#++..
"""

TWO_CHESTS = """10 14 300
F..+.....G....
.##..t........
..o..*....@...
..............
....X.........
.......X......
G....t..o.tt..
..........+...
o##..........M
.*o.ot.#...oo.
"""

IMPOSSIBLE_BOTTOM_CHEST = """10 14 300
F..+.....G....
.##..t........
..o..#....@...
..............
....X.........
.......X......
G....t..o.tt..
..........+...
o##..........M
.*o.ot.#...oo.
"""

HOLE_LOCKED_CORRIDOR = """3 9 120
#########
#F*o.@XM#
#########
"""

TREE_LOCKED_CORRIDOR = """3 9 120
#########
#M*t.@GF#
#########
"""


def _run(text: str):
    game_map = MapParser.parse(text)
    state = MapParser.build_initial_state(game_map)
    strategy = ChestFirstPortfolioStrategy(stuck_end_threshold=40)
    result = Simulator(state).run_strategy(strategy)
    return state, result


def _events(result):
    return [event for tick in result.ticks for event in tick.events]


def _hack_actions(result):
    return [
        action
        for tick in result.ticks
        for action in tick.effective_actions.values()
        if action in {
            HeroAction.HACK,
            HeroAction.HACK_MOVE,
            HeroAction.HACK_FILL,
            HeroAction.HACK_CW,
            HeroAction.HACK_CCW,
            HeroAction.HACK_CUT,
        }
    ]


def test_portfolio_v4_secures_direct_chest_before_wasting_hacks() -> None:
    state, result = _run(TWO_CHESTS)
    assert state.secured_chests == 1
    assert state.lost_chests == 0
    assert state.total_hero_stones == 2
    assert _hack_actions(result) == []
    secured_ticks = [tick.tick for tick in result.ticks if any(e.type == "CHEST_SECURED" for e in tick.events)]
    assert secured_ticks


def test_portfolio_v4_proves_bottom_edge_chest_unsalvageable_and_does_not_hack_randomly() -> None:
    game_map = MapParser.parse(IMPOSSIBLE_BOTTOM_CHEST)
    initial = MapParser.build_initial_state(game_map)
    strategy = ChestFirstPortfolioStrategy(stuck_end_threshold=40)
    assert strategy.structurally_solvable_chest_count(initial) == 0
    result = Simulator(initial).run_strategy(strategy)
    assert initial.secured_chests == 0
    assert initial.lost_chests == 0
    assert initial.total_hero_stones == 2
    assert initial.total_battery == 200
    assert _hack_actions(result) == []


def test_portfolio_v4_uses_excavator_to_fill_required_hole_then_secures_chest() -> None:
    state, result = _run(HOLE_LOCKED_CORRIDOR)
    events = _events(result)
    assert state.secured_chests == 1
    assert state.lost_chests == 0
    assert any(e.type == "MACHINE_HACKED" and e.actor == HeroId.IKOTOFOSA.value for e in events)
    assert any(e.type == "HOLE_FILLED" and e.actor == HeroId.IKOTOFOSA.value for e in events)
    assert any(e.type == "CHEST_SECURED" for e in events)


def test_portfolio_v4_uses_grappler_to_cut_required_tree_then_secures_chest() -> None:
    state, result = _run(TREE_LOCKED_CORRIDOR)
    events = _events(result)
    assert state.secured_chests == 1
    assert state.lost_chests == 0
    assert any(e.type == "MACHINE_HACKED" and e.actor == HeroId.IMAHAKI.value for e in events)
    assert any(e.type == "TREE_CUT" for e in events)
    assert any(e.type == "CHEST_SECURED" for e in events)


def test_portfolio_v4_coordinates_both_machine_roles_on_official_dependency_map() -> None:
    state, result = _run(OFFICIAL)
    events = _events(result)
    assert state.secured_chests == 1
    assert state.lost_chests == 0
    assert state.total_hero_stones == 5
    assert any(e.type == "MACHINE_HACKED" and e.actor == HeroId.IKOTOFOSA.value for e in events)
    assert any(e.type == "MACHINE_HACKED" and e.actor == HeroId.IMAHAKI.value for e in events)
    assert any(e.type == "TREE_CUT" for e in events)
    assert any(e.type == "HOLE_FILLED" for e in events)
    assert result.score >= 370


def test_service_portfolio_v4_is_fast_and_preserves_requested_priority_map() -> None:
    service = SimulationService()
    response = service.simulate(
        map_text=TWO_CHESTS,
        mission_name="priority-regression",
        strategy_options=StrategyOptions(name="portfolio_v4"),
    )
    assert response.result.chests_secured == 1
    assert response.result.chests_lost == 0
    assert response.result.stones_collected == 2
    assert response.result.total_battery == 200


def test_portfolio_v9_is_default_strategy_option() -> None:
    assert StrategyOptions().name == "portfolio_v9"
