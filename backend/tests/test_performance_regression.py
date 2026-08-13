from pathlib import Path
from app.schemas.simulation import StrategyOptions
from app.services.simulation_service import SimulationService

ROOT = Path(__file__).resolve().parents[1]


def test_problematic_10x14_portfolio_returns_without_runaway_retry() -> None:
    texte = (ROOT / 'tests' / 'fixtures' / 'regression_slow_10x14.txt').read_text(encoding='utf-8')
    response = SimulationService().simulate(
        map_text=texte,
        mission_name='regression-slow-10x14',
        strategy_options=StrategyOptions(name='portfolio_v3'),
    )
    assert response.result.score >= 400
    assert len(response.ticks) < 100
    assert response.result.chests_lost == 0


def test_scalable_strategy_is_available_for_stress_maps() -> None:
    rows = ['.' * 40 for _ in range(40)]
    rows[0] = 'F' + '+' * 10 + '.' * 28 + 'G'
    rows[-1] = 'X' + '.' * 28 + '+' * 10 + 'M'
    texte = '40 40 80\n' + '\n'.join(rows) + '\n'
    response = SimulationService().simulate(
        map_text=texte,
        mission_name='stress-profile',
        strategy_options=StrategyOptions(name='scalable_v1'),
    )
    assert response.ticks
    assert len(response.ticks) <= 80
