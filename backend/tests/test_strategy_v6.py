from __future__ import annotations

from functools import lru_cache
from app.domain.enums import HeroId
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
from app.engine.strategy_v6 import OptimizedCollaborativePortfolioStrategy
from app.schemas.simulation import StrategyOptions
from app.services.simulation_service import SimulationService


USER_TWO_CHESTS = """10 14 300
F..+.....G....
.##..t........
..o..#....@...
+...X.........
.......X......
G....t..o*tt..
.+........+...
o##o.........M
.*o.ot.#...oo.
+.o...t....+..
"""

OFFICIAL = """5 7 100
G+.M..+
.###tt#
.o*.+.@
o##t#tX
.F#++..
"""

MACHINE_STONES = """1 9 60
F+..X..M.
"""


@lru_cache(maxsize=None)
def _run(text: str):
    game_map = MapParser.parse(text)
    state = MapParser.build_initial_state(game_map)
    strategy = OptimizedCollaborativePortfolioStrategy(
        max_stones_per_hero=16,
        max_chest_pairs_per_hero=24,
        stuck_end_threshold=24,
        max_unlock_checks=60,
    )
    result = Simulator(state).run_strategy(strategy)
    return state, result


def test_portfolio_v6_does_not_end_while_second_chest_is_still_solvable() -> None:
    state, result = _run(USER_TWO_CHESTS)
    assert result.final_snapshot["end_reason"] == "OBJECTIVES_FINISHED"
    assert state.secured_chests == 2
    assert state.lost_chests == 0
    assert state.total_hero_stones == 6
    assert state.objectives_finished
    assert len(result.ticks) <= 100
    assert result.score >= 600


def test_portfolio_v6_recovers_stones_already_collected_by_machine() -> None:
    state, result = _run(USER_TWO_CHESTS)
    events = [event for tick in result.ticks for event in tick.events]
    stolen = [event for event in events if event.type == "STONES_STOLEN"]
    assert stolen
    assert sum(int(event.data.get("amount", 0)) for event in stolen) >= 1
    assert all(machine.carried_stones == 0 for machine in state.machines.values())
    assert state.total_hero_stones == 6


def test_portfolio_v6_values_multiple_machine_stones_above_single_free_stone() -> None:
    game_map = MapParser.parse(MACHINE_STONES)
    state = MapParser.build_initial_state(game_map)
    machine = next(iter(state.machines.values()))
    machine.carried_stones = 3
    strategy = OptimizedCollaborativePortfolioStrategy()
    choices = strategy._stone_choices(state, HeroId.IKOTOFOSA)
    assert choices
    assert choices[0].key[0] == "machine_stones"
    assert choices[0].key[1] == machine.id


def test_portfolio_v6_keeps_official_map_result_strong() -> None:
    state, result = _run(OFFICIAL)
    assert state.secured_chests == 1
    assert state.lost_chests == 0
    assert state.total_hero_stones == 5
    assert state.objectives_finished
    assert result.score >= 375
    assert len(result.ticks) <= 70


def test_latest_portfolio_is_service_default() -> None:
    assert StrategyOptions().name == "portfolio_v9"
    response = SimulationService().simulate(
        map_text=USER_TWO_CHESTS,
        mission_name="latest-regression",
        strategy_options=StrategyOptions(),
    )
    assert response.result.end_reason == "OBJECTIVES_FINISHED"
    assert response.result.chests_secured == 2
    assert response.result.stones_collected == 6
    assert response.result.score >= 600
