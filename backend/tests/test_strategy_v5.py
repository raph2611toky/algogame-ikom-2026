from __future__ import annotations

from app.domain.enums import HeroAction, HeroId
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
from app.engine.strategy_v5 import CollaborativePortfolioStrategy
from app.schemas.simulation import StrategyOptions
from app.services.simulation_service import SimulationService

USER_COLLABORATION = """10 14 300
F..+.....G....
.##..t........
..o..#....@...
....X.........
.......X......
G....t..o.tt..
..........+...
o##..........M
.*o.ot.#...oo.
+.o.........+.
"""

TWO_DIRECT = """1 13 80
F.*.@...@.*.M
"""

ONLY_STONES = """1 9 60
F.+...+.M
"""

HOLE_LOCKED_WITH_SIDE_STONE = """3 11 120
###########
#F*o.@X.+M#
###########
"""

TREE_LOCKED_WITH_SIDE_STONE = """3 11 120
###########
#M*t.@G.+F#
###########
"""

OFFICIAL = """5 7 100
G+.M..+
.###tt#
.o*.+.@
o##t#tX
.F#++..
"""


def _run(text: str):
    game_map = MapParser.parse(text)
    state = MapParser.build_initial_state(game_map)
    result = Simulator(state).run_strategy(CollaborativePortfolioStrategy(stuck_end_threshold=40))
    return state, result


def test_portfolio_v5_uses_both_heroes_for_two_direct_chests() -> None:
    state, result = _run(TWO_DIRECT)
    assert state.secured_chests == 2
    assert state.lost_chests == 0
    assert len(result.ticks) == 3
    first = result.ticks[0].effective_actions
    assert first[HeroId.IKOTOFOSA] == HeroAction.RIGHT
    assert first[HeroId.IMAHAKI] == HeroAction.LEFT
    assert any(
        tick.effective_actions[HeroId.IKOTOFOSA] in {HeroAction.PUSH_LEFT, HeroAction.PUSH_RIGHT}
        and tick.effective_actions[HeroId.IMAHAKI] in {HeroAction.PUSH_LEFT, HeroAction.PUSH_RIGHT}
        for tick in result.ticks
    )


def test_portfolio_v5_splits_stone_collection_between_both_heroes() -> None:
    state, result = _run(ONLY_STONES)
    assert state.total_hero_stones == 2
    assert state.objectives_finished
    assert result.ticks[0].effective_actions[HeroId.IKOTOFOSA] == HeroAction.RIGHT
    assert result.ticks[0].effective_actions[HeroId.IMAHAKI] == HeroAction.LEFT


def test_portfolio_v5_idle_partner_collects_while_ikotofosa_unlocks_hole() -> None:
    state, result = _run(HOLE_LOCKED_WITH_SIDE_STONE)
    assert state.secured_chests == 1
    assert state.total_hero_stones == 1
    assert any(tick.effective_actions[HeroId.IMAHAKI] != HeroAction.WAIT for tick in result.ticks[:3])
    assert any(event.type == "HOLE_FILLED" for tick in result.ticks for event in tick.events)


def test_portfolio_v5_idle_partner_collects_while_imahaki_unlocks_tree() -> None:
    state, result = _run(TREE_LOCKED_WITH_SIDE_STONE)
    assert state.secured_chests == 1
    assert state.total_hero_stones == 1
    assert any(tick.effective_actions[HeroId.IKOTOFOSA] != HeroAction.WAIT for tick in result.ticks[:3])
    assert any(event.type == "TREE_CUT" for tick in result.ticks for event in tick.events)


def test_portfolio_v5_regression_user_map_does_not_leave_imahaki_idle() -> None:
    state, result = _run(USER_COLLABORATION)
    assert state.secured_chests == 1
    assert state.total_hero_stones == 4
    assert state.objectives_finished
    assert result.ticks[0].effective_actions[HeroId.IMAHAKI] != HeroAction.WAIT
    assert any(tick.effective_actions[HeroId.IMAHAKI] != HeroAction.WAIT for tick in result.ticks[:8])
    assert result.score >= 440


def test_portfolio_v5_preserves_and_improves_official_dependency_result() -> None:
    state, result = _run(OFFICIAL)
    assert state.secured_chests == 1
    assert state.total_hero_stones == 5
    assert state.lost_chests == 0
    assert state.objectives_finished
    assert result.score >= 379
    assert len(result.ticks) <= 60


def test_service_portfolio_v5_remains_available_for_comparison() -> None:
    response = SimulationService().simulate(
        map_text=USER_COLLABORATION,
        mission_name="collaboration-regression",
        strategy_options=StrategyOptions(name="portfolio_v5"),
    )
    assert response.result.chests_secured == 1
    assert response.result.stones_collected == 4
    assert response.result.score >= 440

TWO_TRAPPED_SPECIALISTS = """5 11 200
###########
#F*o.@X...#
###########
#M*t.@G...#
###########
"""


def test_portfolio_v5_runs_two_specialized_trapped_chests_in_parallel() -> None:
    state, result = _run(TWO_TRAPPED_SPECIALISTS)
    assert state.secured_chests == 2
    assert state.lost_chests == 0
    assert state.objectives_finished
    assert result.ticks[0].effective_actions[HeroId.IKOTOFOSA] != HeroAction.WAIT
    assert result.ticks[0].effective_actions[HeroId.IMAHAKI] != HeroAction.WAIT
    events = [event for tick in result.ticks for event in tick.events]
    assert any(event.type == "HOLE_FILLED" for event in events)
    assert any(event.type == "TREE_CUT" for event in events)
