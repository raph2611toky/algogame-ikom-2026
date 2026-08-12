from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
from app.engine.strategy import HeuristicStrategy

def main() -> None:
    texte = Path('maps/official_sample.txt').read_text(encoding='utf-8')
    game_map = MapParser.parse(texte)
    result = Simulator(MapParser.build_initial_state(game_map)).run_strategy(HeuristicStrategy())
    print('ticks:', len(result.ticks))
    print('score local:', result.score)
    print('end:', result.final_snapshot['end_reason'])
    print('actions.txt:\n', result.actions_text)
if __name__ == '__main__':
    main()
