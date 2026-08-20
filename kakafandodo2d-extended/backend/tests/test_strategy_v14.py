from app.domain.enums import HeroAction, HeroId
from app.engine.machine_chest_planner import plan_machine_chest_to_bush
from app.engine.map_parser import MapParser
from app.engine.rules import Rules
from app.engine.simulator import Simulator
from app.engine.strategy_v14 import GlobalMissionPortfolioStrategy


def _machine_uphill_map():
    return MapParser.parse(
        """3 6 80
M.G*@.
......
F.X...
""",
        elevation_text="""111123
111111
111111
""",
    )


def test_machine_chest_planner_solves_push_heroes_cannot_do_uphill() -> None:
    game_map = _machine_uphill_map()
    state = MapParser.build_initial_state(game_map)
    hero = state.heroes[HeroId.IMAHAKI]
    machine = state.machines["G1"]

    # A hero on the left of this chest is forbidden from pushing 1 -> 2 uphill.
    hero.position = machine.position
    push = Rules.chest_push(state, hero, HeroAction.PUSH_RIGHT)
    assert push.valid is False
    assert push.reason == "chest_uphill_forbidden_for_hero"

    # A Grappler may intentionally perform that +1 uphill push and secure it.
    hero.hacking_machine_id = machine.id
    machine.hacked_by = hero.id
    chest = next(iter(state.chests))
    bush = next(iter(game_map.bushes))
    plan = plan_machine_chest_to_bush(state, machine, chest, bush)
    assert plan is not None
    assert HeroAction.HACK_MOVE in plan.actions

    class FixedPlan:
        def __init__(self, actions):
            self.actions = list(actions)

        def should_end(self, current):
            return not self.actions or current.objectives_finished

        def next_actions(self, current):
            action = self.actions.pop(0) if self.actions else HeroAction.WAIT
            return {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: action}

    result = Simulator(state).run_strategy(FixedPlan(plan.actions))
    assert result.final_snapshot["props"]["secured_chests"] == 1
    assert result.final_snapshot["props"]["lost_chests"] == 0


def test_v14_joint_missions_finish_two_independent_direct_chests() -> None:
    game_map = MapParser.parse(
        """5 9 100
F.*.@....
.........
.........
....@.*.M
.........
""",
        elevation_text="""111111111
111111111
111111111
111111111
111111111
""",
    )
    state = MapParser.build_initial_state(game_map)
    strategy = GlobalMissionPortfolioStrategy(
        planning_bias="score",
        medium_mode=False,
        max_stones_per_hero=4,
        max_chest_pairs_per_hero=12,
        stuck_end_threshold=24,
        max_unlock_checks=12,
    )
    result = Simulator(state).run_strategy(strategy)
    assert result.final_snapshot["props"]["secured_chests"] == 2
    assert result.final_snapshot["props"]["lost_chests"] == 0
    assert result.final_snapshot["end_reason"] == "OBJECTIVES_FINISHED"
    # Both heroes should have contributed before the mission ends.
    requested_f = [tick.requested_actions[HeroId.IKOTOFOSA] for tick in result.ticks]
    requested_m = [tick.requested_actions[HeroId.IMAHAKI] for tick in result.ticks]
    assert any(action != HeroAction.WAIT for action in requested_f)
    assert any(action != HeroAction.WAIT for action in requested_m)
