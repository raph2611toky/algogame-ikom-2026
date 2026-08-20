from pathlib import Path

from app.domain.enums import HeroAction, HeroId
from app.domain.models import Position
from app.engine.chest_planner import ChestPlan
from app.engine.map_parser import MapParser
from app.engine.strategy_v4 import DirectChestPlan
from app.engine.strategy_v13 import PredictiveGlobalPortfolioStrategy
from app.schemas.simulation import StrategyOptions
from app.services.simulation_service import SimulationService


def test_v13_direct_ranking_prefers_lower_official_score_cost_over_shorter_route() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 6 50\nF....M\n..@...\n'))
    strategy = PredictiveGlobalPortfolioStrategy(planning_bias='score')
    # Shorter path burns much more stamina: 5*2 + 20 = 30 units.
    short = DirectChestPlan(
        HeroId.IKOTOFOSA,
        Position(0, 2),
        Position(1, 2),
        ChestPlan((HeroAction.RIGHT,) * 5, 20, Position(0, 2), Position(1, 2)),
    )
    # Longer path preserves stamina: 7*2 + 0 = 14 units.
    long = DirectChestPlan(
        HeroId.IKOTOFOSA,
        Position(0, 3),
        Position(1, 2),
        ChestPlan((HeroAction.RIGHT,) * 7, 0, Position(0, 3), Position(1, 2)),
    )
    assert strategy._plan_runtime_key(state, long) < strategy._plan_runtime_key(state, short)


def test_v13_machine_estimate_rejects_manhattan_shortcut_blocked_by_elevation() -> None:
    game_map = MapParser.parse(
        '2 5 50\nXF..o\n#G..M\n',
        '19111\n01111\n',
    )
    state = MapParser.build_initial_state(game_map)
    strategy = PredictiveGlobalPortfolioStrategy()
    # X is boxed on the left/bottom and cannot cross the 1->9 wall. A Manhattan
    # estimate would call the hole close; the real machine planner proves it is not.
    assert strategy._machine_cost_estimate(state, HeroId.IKOTOFOSA, {Position(0, 4)}) >= 100_000


def test_v13_temporal_hazard_predictor_uses_production_simulator_for_cliff() -> None:
    state = MapParser.build_initial_state(
        MapParser.parse(
            '2 7 50\nG*....X\nF.....M\n',
            '7721111\n1111111\n',
        )
    )
    strategy = PredictiveGlobalPortfolioStrategy()
    hazard = strategy._predict_autonomous_hazard(state, 'G1', horizon=8)
    assert hazard is not None
    assert hazard.risk >= 100_000
    assert 'falaise' in hazard.reason


def test_v13_does_not_delegate_small_maps_to_the_separate_v9_reference() -> None:
    state = MapParser.build_initial_state(MapParser.parse('2 5 30\nF+..M\nG..X.\n'))
    strategy = PredictiveGlobalPortfolioStrategy()

    def boom(_state):
        raise AssertionError('V13 ne doit pas deleguer au _v9_reference sur petite carte')

    strategy._v9_reference.next_actions = boom  # type: ignore[method-assign]
    actions = strategy.next_actions(state)
    assert set(actions) == {HeroId.IKOTOFOSA, HeroId.IMAHAKI}


def test_portfolio_v13_is_never_worse_than_v12_on_reference_10x14() -> None:
    text = Path('maps/evaluation_10x14.txt').read_text(encoding='utf-8')
    service = SimulationService()
    v12 = service.simulate(
        map_text=text,
        mission_name='v12-reference',
        strategy_options=StrategyOptions(name='portfolio_v12'),
    )
    v13 = service.simulate(
        map_text=text,
        mission_name='v13-reference',
        strategy_options=StrategyOptions(name='portfolio_v13'),
    )
    assert v13.result.score >= v12.result.score
    assert v13.result.chests_lost <= v12.result.chests_lost


def test_v13_stops_immediately_when_objectives_are_finished_even_with_stale_commitment_state() -> None:
    state = MapParser.build_initial_state(MapParser.parse('1 3 20\nFM.\n'))
    strategy = PredictiveGlobalPortfolioStrategy()
    # No stones/chests exist, so objectives are already complete. This guards
    # against stale machine commitments keeping a solved run alive to TIME_LIMIT.
    assert state.objectives_finished
    assert strategy.should_end(state) is True
