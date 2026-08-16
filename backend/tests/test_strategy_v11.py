from __future__ import annotations

from app.domain.enums import HeroAction, HeroId
from app.engine.map_parser import MapParser
from app.engine.strategy_v11 import StrictPriorityPortfolioStrategy


def test_v11_rejects_far_stone_while_chest_remains() -> None:
    game_map = MapParser.parse("""3 12 100
F.*........@
...........+
M...........
""")
    state = MapParser.build_initial_state(game_map)
    strategy = StrictPriorityPortfolioStrategy()
    action, key, _ = strategy._priority_local_stone_action(state, HeroId.IKOTOFOSA)
    assert key is None
    assert action == HeroAction.WAIT


def test_v11_accepts_stone_within_three_cells_of_remaining_chest() -> None:
    game_map = MapParser.parse("""3 8 100
F.*+..@.
........
M.......
""")
    state = MapParser.build_initial_state(game_map)
    strategy = StrictPriorityPortfolioStrategy()
    action, key, _ = strategy._priority_local_stone_action(state, HeroId.IKOTOFOSA)
    assert key == ("stone", 0, 3)
    assert action != HeroAction.WAIT


def test_v11_does_not_replace_v10_core_planners() -> None:
    forbidden = {
        "_direct_collaborative_actions",
        "_fill_direct_support",
        "_unlock_actions",
        "_select_target_chest",
        "_machine_tasks_for",
        "_protect_chests_from_autonomous_machines",
        "_maybe_handoff",
    }
    assert forbidden.isdisjoint(StrictPriorityPortfolioStrategy.__dict__)
