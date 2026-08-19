from __future__ import annotations

from app.domain.enums import HeroAction, HeroId
from app.domain.models import Position
from app.engine.actions_parser import parse_actions_text
from app.engine.chest_planner import plan_chest_to_bush
from app.engine.map_parser import MapParser
from app.engine.result_optimizer import trim_to_best_score_prefix
from app.engine.simulator import Simulator
from app.engine.strategy_v4 import DirectChestPlan
from app.engine.strategy_v8 import StaminaAwareCollaborativePortfolioStrategy
from app.schemas.simulation import StrategyOptions
from app.services.simulation_service import SimulationService


OFFICIAL = """5 7 100
G+.M..+
.###tt#
.o*.+.@
o##t#tX
.F#++..
"""


def test_default_v9_still_improves_official_sample_while_v8_unit_tests_remain() -> None:
    assert StrategyOptions().name == "portfolio_v12"
    response = SimulationService().simulate(
        map_text=OFFICIAL,
        mission_name="official-v8",
        strategy_options=StrategyOptions(),
    )
    assert response.result.end_reason == "OBJECTIVES_FINISHED"
    assert response.result.chests_secured == 1
    assert response.result.stones_collected == 5
    assert response.result.chests_lost == 0
    assert response.result.score >= 379
    assert len(response.ticks) <= 60
    assert response.ticks[-1].state.current_score == response.result.score


def test_portfolio_v8_hands_long_chest_route_to_fresher_hero() -> None:
    game_map = MapParser.parse("1 10 100\nF*......@M")
    state = MapParser.build_initial_state(game_map)
    state.heroes[HeroId.IKOTOFOSA].stamina = 5
    strategy = StaminaAwareCollaborativePortfolioStrategy()
    chest = Position(0, 1)
    bush = Position(0, 8)
    plan = plan_chest_to_bush(
        state,
        HeroId.IKOTOFOSA,
        chest,
        bush,
        max_expansions=10000,
        optimize_for_score=True,
    )
    assert plan is not None
    route = strategy._cache_route(state, DirectChestPlan(HeroId.IKOTOFOSA, chest, bush, plan))
    assert strategy._maybe_handoff(state, HeroId.IKOTOFOSA, route)
    assert HeroId.IKOTOFOSA not in strategy._direct_routes
    assert HeroId.IMAHAKI in strategy._direct_routes


def test_portfolio_v8_keeps_route_owner_waiting_instead_of_diverting_to_stone() -> None:
    game_map = MapParser.parse("1 8 100\nF*..@+.M")
    state = MapParser.build_initial_state(game_map)
    strategy = StaminaAwareCollaborativePortfolioStrategy()
    chest = Position(0, 1)
    bush = Position(0, 4)
    plan = plan_chest_to_bush(state, HeroId.IKOTOFOSA, chest, bush, optimize_for_score=True)
    assert plan is not None
    strategy._cache_route(state, DirectChestPlan(HeroId.IKOTOFOSA, chest, bush, plan))
    state.heroes[HeroId.IKOTOFOSA].stamina = 0
    decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
    filled = strategy._fill_direct_support(state, decisions, {chest})
    assert filled[HeroId.IKOTOFOSA] == HeroAction.WAIT
    assert HeroId.IKOTOFOSA in strategy._direct_routes


def test_portfolio_v8_invalidates_cached_chest_route_when_dynamic_topology_changes() -> None:
    game_map = MapParser.parse("2 8 100\nF*..@..M\n........")
    state = MapParser.build_initial_state(game_map)
    strategy = StaminaAwareCollaborativePortfolioStrategy()
    chest = Position(0, 1)
    bush = Position(0, 4)
    plan = plan_chest_to_bush(state, HeroId.IKOTOFOSA, chest, bush, optimize_for_score=True)
    assert plan is not None
    route = strategy._cache_route(state, DirectChestPlan(HeroId.IKOTOFOSA, chest, bush, plan))
    assert strategy._route_valid(state, HeroId.IKOTOFOSA, route)
    state.holes.add(Position(1, 3))
    assert not strategy._route_valid(state, HeroId.IKOTOFOSA, route)


def test_portfolio_v8_orients_hacked_machine_before_dangerous_unhack() -> None:
    game_map = MapParser.parse("1 7 80\nFX*o@.M")
    state = MapParser.build_initial_state(game_map)
    strategy = StaminaAwareCollaborativePortfolioStrategy()
    machine = next(iter(state.machines.values()))
    hero = state.heroes[HeroId.IKOTOFOSA]
    hero.position = machine.position
    hero.hacking_machine_id = machine.id
    machine.hacked_by = HeroId.IKOTOFOSA
    action = strategy._prepare_machine_release(state, HeroId.IKOTOFOSA, Position(0, 2))
    assert action in {HeroAction.HACK_CW, HeroAction.HACK_CCW, HeroAction.WAIT}


def test_best_score_prefix_can_end_earlier_and_replay_same_score() -> None:
    game_map = MapParser.parse("1 5 20\nF.+.M")
    state = MapParser.build_initial_state(game_map)
    actions = [
        {HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT},
        {HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT},
        {HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT},
        {HeroId.IKOTOFOSA: HeroAction.LEFT, HeroId.IMAHAKI: HeroAction.WAIT},
        {HeroId.IKOTOFOSA: HeroAction.RIGHT, HeroId.IMAHAKI: HeroAction.WAIT},
    ]
    raw = Simulator(state).run_actions(actions)
    trimmed = trim_to_best_score_prefix(raw, time_limit=game_map.time_limit)
    assert trimmed.score >= raw.score
    assert len(trimmed.ticks) < len(raw.ticks)
    assert trimmed.final_snapshot["end_reason"] == "BEST_SCORE_END_GAME"
    replay_state = MapParser.build_initial_state(game_map)
    replay_actions = parse_actions_text(trimmed.actions_text, time_limit=game_map.time_limit)
    replay = Simulator(replay_state).run_actions(replay_actions)
    assert replay.score == trimmed.score
