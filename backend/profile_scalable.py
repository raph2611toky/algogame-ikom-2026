from pathlib import Path
from app.engine.map_parser import MapParser
from app.engine.strategy_scalable import ScalableStrategy
from app.engine.simulator import Simulator
text=Path('maps/complex_map_90x120.txt').read_text(); gm=MapParser.parse(text); st=MapParser.build_initial_state(gm); Simulator(st).run_strategy(ScalableStrategy(max_ticks=100))
