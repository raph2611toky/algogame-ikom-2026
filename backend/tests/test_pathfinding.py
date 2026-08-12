from app.domain.enums import HeroAction, HeroId
from app.domain.models import Position
from app.engine.chest_planner import plan_chest_to_bush
from app.engine.map_parser import MapParser
from app.engine.pathfinding import find_path


def test_astar_uses_ikotofosa_hop() -> None:
    state = MapParser.build_initial_state(MapParser.parse("3 5 20\nM....\n.....\nFo.+.\n"))
    path = find_path(state, HeroId.IKOTOFOSA, Position(2, 3))
    assert path is not None
    assert path.steps[0].action == HeroAction.RIGHT
    assert path.steps[0].destination == Position(2, 2)


def test_chest_planner_finds_simple_push() -> None:
    state = MapParser.build_initial_state(MapParser.parse("2 5 20\nF.*@.\nM....\n"))
    plan = plan_chest_to_bush(state, HeroId.IKOTOFOSA, Position(0, 2), Position(0, 3))
    assert plan is not None
    assert plan.actions[-1] == HeroAction.PUSH_RIGHT
