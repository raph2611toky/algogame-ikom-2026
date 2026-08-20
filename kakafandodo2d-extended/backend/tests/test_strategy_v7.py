from pathlib import Path
from time import perf_counter

from app.domain.models import Position
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
from app.engine.strategy_v7 import CachedCollaborativePortfolioStrategy


OFFICIAL = """5 7 100
G+.M..+
.###tt#
.o*.+.@
o##t#tX
.F#++..
"""

IMPOSSIBLE_EDGE_CHEST = """4 6 80
F....M
......
@.....
*.....
"""


def _run(text: str):
    game_map = MapParser.parse(text)
    state = MapParser.build_initial_state(game_map)
    strategy = CachedCollaborativePortfolioStrategy(
        max_stones_per_hero=16,
        max_chest_pairs_per_hero=20,
        stuck_end_threshold=24,
        max_unlock_checks=40,
    )
    result = Simulator(state).run_strategy(strategy)
    return state, result


def test_portfolio_v7_keeps_official_score_and_finishes() -> None:
    state, result = _run(OFFICIAL)
    assert result.final_snapshot["end_reason"] == "OBJECTIVES_FINISHED"
    assert state.secured_chests == 1
    assert state.total_hero_stones == 5
    assert state.lost_chests == 0
    assert result.score >= 379
    assert len(result.ticks) <= 60


def test_portfolio_v7_does_not_wait_until_time_limit_for_structurally_impossible_chest() -> None:
    state, result = _run(IMPOSSIBLE_EDGE_CHEST)
    assert state.secured_chests == 0
    assert Position(3, 0) in state.chests
    assert result.final_snapshot["end_reason"] == "NO_REACHABLE_OBJECTIVES"
    assert len(result.ticks) < 30


def test_portfolio_v7_user_15x20_profile_classifies_only_bottom_left_chest_impossible() -> None:
    path = Path('maps/regression/user_15x20_700.txt')
    game_map = MapParser.parse(path.read_text(encoding='utf-8'))
    state = MapParser.build_initial_state(game_map)
    strategy = CachedCollaborativePortfolioStrategy()
    profiles = {chest: strategy._unlock_profile(state, chest) for chest in state.chests}
    impossible = {chest for chest, profile in profiles.items() if not profile.structurally_possible}
    assert impossible == {Position(13, 0)}


def test_portfolio_v7_first_decision_on_15x20_is_bounded() -> None:
    path = Path('maps/regression/user_15x20_700.txt')
    game_map = MapParser.parse(path.read_text(encoding='utf-8'))
    state = MapParser.build_initial_state(game_map)
    strategy = CachedCollaborativePortfolioStrategy()
    started = perf_counter()
    actions = strategy.next_actions(state)
    elapsed = perf_counter() - started
    assert set(actions) == set(state.heroes)
    assert elapsed < 2.0
