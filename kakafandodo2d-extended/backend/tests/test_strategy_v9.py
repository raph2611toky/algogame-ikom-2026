from __future__ import annotations

from app.domain.enums import HeroId
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
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

USER_10 = """10 14 300
F..+.....G....
.##..t........
..o..#....@...
+...X.........
.......X......
G....t..o*tt..
.+........+...
o##o.........M
.*o.ot.#...oo.
+.o...t....+..
"""


def _push_actors(response) -> list[str]:
    actors: list[str] = []
    for tick in response.ticks:
        for event in tick.events:
            if event.type in {"CHEST_PUSHED", "CHEST_SECURED"} and event.actor in {"F", "M"}:
                actors.append(event.actor)
    return actors


def _switches(actors: list[str]) -> int:
    return sum(a != b for a, b in zip(actors, actors[1:]))


def test_v9_is_a_thin_v8_layer_not_a_replacement() -> None:
    # Ces methodes constituent le coeur v8 et NE DOIVENT PAS etre reimplementees
    # dans v9. Le test protege explicitement contre la regression de l'ancienne v9.
    forbidden_overrides = {
        "_cache_route",
        "_route_valid",
        "_direct_collaborative_actions",
        "_unlock_actions",
        "_select_target_chest",
        "_machine_tasks_for",
        "_partner_relocation_action",
        "_prepare_machine_release",
        "next_actions",
    }
    assert forbidden_overrides.isdisjoint(StrategicRelayPortfolioStrategy.__dict__)


def test_v9_official_is_identical_to_v8() -> None:
    service = SimulationService()
    v8 = service.simulate(map_text=OFFICIAL, mission_name="official-v8", strategy_options=StrategyOptions(name="portfolio_v8"))
    v9 = service.simulate(map_text=OFFICIAL, mission_name="official-v9", strategy_options=StrategyOptions(name="portfolio_v9"))
    assert v9.result.model_dump() == v8.result.model_dump()
    assert len(v9.ticks) == len(v8.ticks)


def test_v9_user10_is_identical_to_v8() -> None:
    service = SimulationService()
    v8 = service.simulate(map_text=USER_10, mission_name="user10-v8", strategy_options=StrategyOptions(name="portfolio_v8"))
    v9 = service.simulate(map_text=USER_10, mission_name="user10-v9", strategy_options=StrategyOptions(name="portfolio_v9"))
    assert v9.result.model_dump() == v8.result.model_dump()
    assert len(v9.ticks) == len(v8.ticks)


def test_v9_long_single_chest_reduces_pingpong_without_losing_score() -> None:
    row = "F*" + "." * 25 + "@.M"
    map_text = f"1 {len(row)} 300\n{row}\n"
    service = SimulationService()
    v8 = service.simulate(map_text=map_text, mission_name="long-v8", strategy_options=StrategyOptions(name="portfolio_v8"))
    v9 = service.simulate(map_text=map_text, mission_name="long-v9", strategy_options=StrategyOptions(name="portfolio_v9"))
    assert v9.result.end_reason == "OBJECTIVES_FINISHED"
    assert v9.result.chests_secured == 1
    assert v9.result.chests_lost == 0
    assert v9.result.score >= v8.result.score
    assert len(v9.ticks) <= len(v8.ticks)
    assert _switches(_push_actors(v9)) < _switches(_push_actors(v8))


def test_v9_last_chest_low_stamina_uses_segments() -> None:
    row = "F*" + "." * 15 + "@.M"
    state = MapParser.build_initial_state(MapParser.parse(f"1 {len(row)} 240\n{row}\n"))
    state.heroes[HeroId.IKOTOFOSA].stamina = 15
    state.heroes[HeroId.IMAHAKI].stamina = 15
    result = Simulator(state).run_strategy(StrategicRelayPortfolioStrategy(stuck_end_threshold=100))
    actors: list[str] = []
    for tick in result.ticks:
        push_events = [e for e in tick.events if e.type in {"CHEST_PUSHED", "CHEST_SECURED"} and e.actor in {"F", "M"}]
        # Un coffre unique n'est jamais pousse par F et M au meme tick.
        assert len(push_events) <= 1
        actors.extend(str(e.actor) for e in push_events)
    assert result.final_snapshot["end_reason"] == "OBJECTIVES_FINISHED"
    assert result.final_snapshot["score_inputs"]["secured_chests"] == 1
    # La nouvelle couche cree de vrais petits segments au lieu d'un switch par PUSH.
    assert _switches(actors) <= 4


def test_v9_two_distinct_chests_keeps_v8_parallelism() -> None:
    map_text = """3 15 100
###############
#F.*.@...@.*.M#
###############
"""
    service = SimulationService()
    v8 = service.simulate(map_text=map_text, mission_name="two-v8", strategy_options=StrategyOptions(name="portfolio_v8"))
    v9 = service.simulate(map_text=map_text, mission_name="two-v9", strategy_options=StrategyOptions(name="portfolio_v9"))
    assert v9.result.model_dump() == v8.result.model_dump()
    assert any(
        tick.effective_actions["F"].value.startswith("PUSH_")
        and tick.effective_actions["M"].value.startswith("PUSH_")
        for tick in v9.ticks
    )
