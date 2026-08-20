from __future__ import annotations
from pathlib import Path
from app.domain.enums import HeroId, MachineKind
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
from app.engine.strategy import HeuristicStrategy
from app.engine.strategy_v2 import AdaptiveScoreStrategy
from app.schemas.simulation import StrategyOptions
from app.services.simulation_service import SimulationService
ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = (ROOT / 'maps' / 'official_sample.txt').read_text(encoding='utf-8')

def _run(strategy):
    game_map = MapParser.parse(OFFICIAL)
    state = MapParser.build_initial_state(game_map)
    result = Simulator(state).run_strategy(strategy)
    return (state, result)

def test_adaptive_v2_beats_baseline_on_official_reference_map() -> None:
    baseline_state, baseline = _run(HeuristicStrategy())
    adaptive_state, adaptive = _run(AdaptiveScoreStrategy())
    # The second-week machine look-ahead addendum changes the historical
    # baseline replay; adaptive_v2 must still dominate it under the current rules.
    assert baseline.score == 165
    assert adaptive.score >= 370
    assert adaptive.score > baseline.score
    assert adaptive_state.secured_chests == 1
    assert adaptive_state.lost_chests == 0
    assert adaptive_state.total_hero_stones == 5
    assert adaptive_state.objectives_finished
    assert any((pos.row == 3 and pos.col == 0 for pos in adaptive_state.holes))

def test_strategy_only_hacks_each_hero_compatible_machine_kind() -> None:
    _state, result = _run(AdaptiveScoreStrategy())
    machine_kinds = {'X': MachineKind.EXCAVATOR, 'G': MachineKind.GRAPPLER}
    for tick in result.ticks:
        for event in tick.events:
            if event.type != 'MACHINE_HACKED':
                continue
            machine_id = str(event.data['machine_id'])
            if event.actor == HeroId.IKOTOFOSA.value:
                assert machine_kinds[machine_id[0]] == MachineKind.EXCAVATOR
            elif event.actor == HeroId.IMAHAKI.value:
                assert machine_kinds[machine_id[0]] == MachineKind.GRAPPLER
            else:
                raise AssertionError(f'Unexpected hacking actor {event.actor}')

def test_portfolio_v3_is_never_below_included_baselines_on_test_maps() -> None:
    service = SimulationService()
    for chemin in sorted((ROOT / 'maps').glob('*.txt')):
        texte = chemin.read_text(encoding='utf-8')
        scores = {}
        for nom in ('heuristic_v1', 'adaptive_v2', 'portfolio_v3'):
            response = service.simulate(map_text=texte, mission_name=chemin.stem, strategy_options=StrategyOptions(name=nom))
            scores[nom] = response.result.score
        assert scores['portfolio_v3'] >= scores['heuristic_v1']
        assert scores['portfolio_v3'] >= scores['adaptive_v2']

def test_official_portfolio_plan_replays_to_exact_same_score() -> None:
    service = SimulationService()
    planned = service.simulate(map_text=OFFICIAL, mission_name='official', strategy_options=StrategyOptions(name='portfolio_v3'))
    actions = [{HeroId.IKOTOFOSA: paire.F, HeroId.IMAHAKI: paire.M} for paire in planned.actions]
    replay = service.replay(map_text=OFFICIAL, mission_name='official-replay', actions=actions, stop_when_objectives_finished=True)
    assert replay.result.score == planned.result.score
    assert replay.result.chests_secured == planned.result.chests_secured
    assert replay.result.chests_lost == planned.result.chests_lost
    assert replay.result.stones_collected == planned.result.stones_collected

def test_score_pathfinding_uses_each_hero_specific_traversal_ability() -> None:
    from app.domain.models import Position
    from app.engine.score_pathfinding import find_score_path
    hole_map = '3 5 40\n#####\nFo..M\n#####\n'
    hole_state = MapParser.build_initial_state(MapParser.parse(hole_map))
    f_path = find_score_path(hole_state, HeroId.IKOTOFOSA, Position(1, 2))
    m_path = find_score_path(hole_state, HeroId.IMAHAKI, Position(1, 0))
    assert f_path is not None
    assert f_path.steps[0].special is True
    assert f_path.steps[0].stamina_cost == 10
    assert m_path is None
    tree_map = '3 5 40\n#####\nFt..M\n#####\n'
    tree_state = MapParser.build_initial_state(MapParser.parse(tree_map))
    m_path = find_score_path(tree_state, HeroId.IMAHAKI, Position(1, 0))
    f_path = find_score_path(tree_state, HeroId.IKOTOFOSA, Position(1, 2))
    assert m_path is not None
    assert m_path.steps[-1].special is True
    assert m_path.steps[-1].stamina_cost == 10
    assert f_path is None
