from pathlib import Path
from app.engine.map_parser import MapParser
from app.engine.strategy_v2 import AdaptiveScoreStrategy
from app.engine.simulator import Simulator
text=Path('/mnt/data/backend_inspect/backend/maps/user_problem_10x14.txt').read_text(); gm=MapParser.parse(text); st=MapParser.build_initial_state(gm); Simulator(st).run_strategy(AdaptiveScoreStrategy())
