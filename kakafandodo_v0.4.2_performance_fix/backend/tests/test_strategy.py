from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
from app.engine.strategy import HeuristicStrategy

def test_strategy_runs_without_exceeding_time_limit() -> None:
    texte = '5 8 60\nF..+...@\n........\n..#.....\n..*.....\nM......+\n'
    game_map = MapParser.parse(texte)
    result = Simulator(MapParser.build_initial_state(game_map)).run_strategy(HeuristicStrategy())
    assert len(result.ticks) <= game_map.time_limit
    assert result.actions_text.endswith('END_GAME\n')
    assert result.final_snapshot['elapsed'] <= game_map.time_limit
