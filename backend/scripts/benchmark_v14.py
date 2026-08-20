from __future__ import annotations

"""Deterministic V14 regression benchmark.

Run from the backend root:
    python scripts/benchmark_v14.py

The benchmark is intentionally not part of the fast unit-test suite because the
15x20 predictive mission search is a competition-scale integration scenario.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
from app.engine.strategy_v14 import GlobalMissionPortfolioStrategy

MAP = ROOT / "maps" / "regression" / "v14_complex_15x20.txt"
ELEVATION = ROOT / "maps" / "regression" / "v14_complex_15x20_elevation.txt"


def main() -> None:
    game_map = MapParser.parse(MAP.read_text(encoding="utf-8"), elevation_text=ELEVATION.read_text(encoding="utf-8"))
    state = MapParser.build_initial_state(game_map)
    strategy = GlobalMissionPortfolioStrategy(
        planning_bias="score",
        medium_mode=True,
        max_stones_per_hero=8,
        max_chest_pairs_per_hero=24,
        stuck_end_threshold=40,
        max_unlock_checks=32,
    )
    result = Simulator(state).run_strategy(strategy)
    final = result.final_snapshot
    props = final["props"]
    score_inputs = final["score_inputs"]

    print(f"score={result.score}")
    print(f"ticks={len(result.ticks)} remaining={final['remaining_time']}")
    print(f"chests={props['secured_chests']} lost={props['lost_chests']}")
    print(f"stones={score_inputs['hero_stones']}")
    print(f"stamina={score_inputs['total_stamina']} battery={score_inputs['total_battery']}")
    print(f"end_reason={final['end_reason']}")

    assert props["secured_chests"] == 5
    assert props["lost_chests"] == 0
    assert score_inputs["hero_stones"] == 10
    assert result.score >= 1150
    assert len(result.ticks) <= 250
    assert final["end_reason"] == "OBJECTIVES_FINISHED"


if __name__ == "__main__":
    main()
