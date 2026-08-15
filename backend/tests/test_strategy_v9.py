from __future__ import annotations

from app.domain.enums import HeroAction, HeroId
from app.domain.models import Position
from app.engine.chest_planner import plan_chest_to_bush
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
from app.engine.strategy_v4 import DirectChestPlan
from app.engine.strategy_v8 import StaminaAwareCollaborativePortfolioStrategy
from app.engine.strategy_v9 import StrategicRelayPortfolioStrategy
from app.schemas.simulation import StrategyOptions
from app.services.simulation_service import SimulationService


OFFICIAL = """5 7 100
G+.M..+
.###tt#
.o*.+.@
o##t#tX
.F#++..
"""


def _push_actors(response) -> list[str]:
    actors: list[str] = []
    for tick in response.ticks:
        for event in tick.events:
            if event.type in {"CHEST_PUSHED", "CHEST_SECURED"} and event.actor in {"F", "M"}:
                actors.append(event.actor)
    return actors


def _actor_switches(actors: list[str]) -> int:
    return sum(left != right for left, right in zip(actors, actors[1:]))


def test_portfolio_v9_is_default_and_keeps_official_quality() -> None:
    assert StrategyOptions().name == "portfolio_v9"
    response = SimulationService().simulate(
        map_text=OFFICIAL,
        mission_name="official-v9",
        strategy_options=StrategyOptions(),
    )
    assert response.result.end_reason == "OBJECTIVES_FINISHED"
    assert response.result.chests_secured == 1
    assert response.result.stones_collected == 5
    assert response.result.chests_lost == 0
    assert response.result.score >= 380
    assert len(response.ticks) <= 60


def test_v9_keeps_own_chest_route_cached_after_expected_push() -> None:
    game_map = MapParser.parse("1 8 100\nF*..@..M")
    state = MapParser.build_initial_state(game_map)
    strategy = StrategicRelayPortfolioStrategy()
    chest = Position(0, 1)
    bush = Position(0, 4)
    plan = plan_chest_to_bush(
        state,
        HeroId.IKOTOFOSA,
        chest,
        bush,
        optimize_for_score=True,
    )
    assert plan is not None
    route = strategy._cache_route(
        state,
        DirectChestPlan(HeroId.IKOTOFOSA, chest, bush, plan),
    )
    action = strategy._route_action(state, HeroId.IKOTOFOSA, route)
    assert action == HeroAction.PUSH_RIGHT

    # Reproduit l'etat du tick suivant. Le mouvement NORMAL du coffre suivi ne doit
    # plus etre pris pour un changement externe de topologie.
    state.chests.remove(chest)
    state.chests.add(Position(0, 2))
    state.heroes[HeroId.IKOTOFOSA].position = Position(0, 1)
    state.heroes[HeroId.IKOTOFOSA].stamina -= 5
    assert strategy._route_valid(state, HeroId.IKOTOFOSA, route)

    # Un vrai changement dynamique (DIG/CUT/FILL) doit toujours invalider la route.
    state.holes.add(Position(0, 6))
    assert not strategy._route_valid(state, HeroId.IKOTOFOSA, route)


def test_v9_long_single_chest_uses_one_strategic_handoff_not_pingpong() -> None:
    row = "F*" + "." * 25 + "@.M"
    map_text = f"1 {len(row)} 300\n{row}\n"
    service = SimulationService()
    old = service.simulate(
        map_text=map_text,
        mission_name="relay-v8",
        strategy_options=StrategyOptions(name="portfolio_v8"),
    )
    new = service.simulate(
        map_text=map_text,
        mission_name="relay-v9",
        strategy_options=StrategyOptions(name="portfolio_v9"),
    )
    actors = _push_actors(new)
    assert new.result.end_reason == "OBJECTIVES_FINISHED"
    assert new.result.chests_secured == 1
    assert new.result.chests_lost == 0
    assert set(actors) == {"F", "M"}
    assert _actor_switches(actors) <= 1
    assert len(new.ticks) < len(old.ticks)
    assert new.result.score >= old.result.score
    # Pendant que F pousse le premier segment, M se deplace vers le relais.
    assert any(
        tick.effective_actions["F"].value.startswith("PUSH_")
        and tick.effective_actions["M"].value in {"LEFT", "RIGHT", "UP", "DOWN"}
        for tick in new.ticks[:20]
    )


def test_v9_two_distinct_direct_chests_keep_parallel_pushes() -> None:
    map_text = """3 15 100
###############
#F.*.@...@.*.M#
###############
"""
    response = SimulationService().simulate(
        map_text=map_text,
        mission_name="two-direct-v9",
        strategy_options=StrategyOptions(name="portfolio_v9"),
    )
    assert response.result.end_reason == "OBJECTIVES_FINISHED"
    assert response.result.chests_secured == 2
    assert response.result.chests_lost == 0
    # Les deux peuvent pousser EN MEME TEMPS uniquement parce qu'il s'agit de deux
    # coffres differents. C'est le parallele utile que l'on veut conserver.
    assert any(
        tick.effective_actions["F"].value.startswith("PUSH_")
        and tick.effective_actions["M"].value.startswith("PUSH_")
        and len([event for event in tick.events if event.type.startswith("CHEST_")]) == 2
        for tick in response.ticks
    )


def test_v9_both_low_stamina_relay_uses_segments_not_single_push_pingpong() -> None:
    row = "F*" + "." * 15 + "@.M"
    game_map = MapParser.parse(f"1 {len(row)} 240\n{row}\n")
    state = MapParser.build_initial_state(game_map)
    state.heroes[HeroId.IKOTOFOSA].stamina = 15
    state.heroes[HeroId.IMAHAKI].stamina = 15
    strategy = StrategicRelayPortfolioStrategy(stuck_end_threshold=100)
    result = Simulator(state).run_strategy(strategy)
    assert result.final_snapshot["end_reason"] == "OBJECTIVES_FINISHED"
    assert result.final_snapshot["score_inputs"]["secured_chests"] == 1

    actors: list[str] = []
    for tick in result.ticks:
        push_events = [event for event in tick.events if event.type in {"CHEST_PUSHED", "CHEST_SECURED"}]
        assert len(push_events) <= 1  # un seul pousseur pour ce coffre unique
        if push_events and push_events[0].actor in {"F", "M"}:
            actors.append(str(push_events[0].actor))
    assert _actor_switches(actors) <= 3


def test_v9_specialist_pressure_prefers_early_relay_hint_without_heavy_planner() -> None:
    # Deux coffres restent et un trou est proche du second: F doit pouvoir etre
    # libere rapidement du premier coffre pour reprendre son role F/X.
    game_map = MapParser.parse("""3 18 160
F*........@......M
..................
....*o............
""")
    state = MapParser.build_initial_state(game_map)
    strategy = StrategicRelayPortfolioStrategy()
    chest = Position(0, 1)
    bush = Position(0, 10)
    plan = plan_chest_to_bush(state, HeroId.IKOTOFOSA, chest, bush, optimize_for_score=True)
    assert plan is not None
    route = strategy._cache_route(state, DirectChestPlan(HeroId.IKOTOFOSA, chest, bush, plan))
    assert strategy._cheap_specialist_pressure(state, HeroId.IKOTOFOSA, excluded_chest=chest)
    relay = strategy._build_relay(state, HeroId.IKOTOFOSA, route)
    assert relay is not None
    assert "specialiste" in relay.reason
