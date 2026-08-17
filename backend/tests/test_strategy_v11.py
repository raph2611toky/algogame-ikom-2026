from __future__ import annotations

from pathlib import Path

from app.domain.enums import HeroId
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
from app.engine.strategy_v10 import OpportunityCommittedPortfolioStrategy
from app.engine.strategy_v11 import ProgressiveParallelPortfolioStrategy


PARALLEL_MAP = Path("maps/regression/parallel_roles_v11_9x20.txt")




def test_v11_prefers_independent_chest_work_over_far_stone_during_direct_route() -> None:
    game_map = MapParser.parse(PARALLEL_MAP.read_text(encoding="utf-8"))

    v10_state = MapParser.build_initial_state(game_map)
    v10 = OpportunityCommittedPortfolioStrategy(max_chest_pairs_per_hero=20, max_unlock_checks=20)
    v10.next_actions(v10_state)
    assert "collecter pierre" in v10.last_decisions[HeroId.IMAHAKI.value]

    v11_state = MapParser.build_initial_state(game_map)
    v11 = ProgressiveParallelPortfolioStrategy(max_chest_pairs_per_hero=20, max_unlock_checks=20)
    decisions = v11.next_actions(v11_state)

    # F poursuit le coffre libre pendant que M commence reellement le travail du
    # second coffre au lieu de traverser le corridor pour la pierre lointaine.
    assert decisions[HeroId.IKOTOFOSA].value == "RIGHT"
    assert decisions[HeroId.IMAHAKI].value == "RIGHT"
    assert "travail simultane" in v11.last_decisions[HeroId.IMAHAKI.value]
    assert "couper arbre" in v11.last_decisions[HeroId.IMAHAKI.value]


def test_v11_parallel_work_reaches_hack_while_other_hero_keeps_pushing() -> None:
    game_map = MapParser.parse(PARALLEL_MAP.read_text(encoding="utf-8"))
    sim = Simulator(MapParser.build_initial_state(game_map))
    strategy = ProgressiveParallelPortfolioStrategy(max_chest_pairs_per_hero=20, max_unlock_checks=20)

    first = strategy.next_actions(sim.state)
    sim.step(first)
    second = strategy.next_actions(sim.state)

    assert second[HeroId.IKOTOFOSA].value.startswith("PUSH_")
    assert second[HeroId.IMAHAKI].value == "HACK"
    assert "travail simultane" in strategy.last_decisions[HeroId.IMAHAKI.value]


def test_v11_does_not_replace_v10_machine_or_safety_core() -> None:
    # V11 peut ajuster uniquement le choix d'un pousseur direct et le remplissage
    # du heros support. Toute la logique critique machines/securite reste v10.
    forbidden_overrides = {
        "_select_target_chest",
        "_machine_tasks_for",
        "_action_for_machine_task",
        "_action_for_staging_task",
        "_protect_chests_from_autonomous_machines",
        "_active_defense_short_circuit",
        "_rotation_guard",
        "_deadlock_resolver",
        "_cache_route",
        "_route_valid",
        "_maybe_handoff",
        "next_actions",
        "_unlock_actions",
    }
    assert forbidden_overrides.isdisjoint(ProgressiveParallelPortfolioStrategy.__dict__)


def test_v11_keeps_v10_first_chest_sequence_on_user_regression() -> None:
    regression = Path("maps/regression/user_15x20_shared_opportunity.txt")
    game_map = MapParser.parse(regression.read_text(encoding="utf-8"))

    v10_sim = Simulator(MapParser.build_initial_state(game_map))
    v11_sim = Simulator(MapParser.build_initial_state(game_map))
    v10 = OpportunityCommittedPortfolioStrategy(max_chest_pairs_per_hero=20, max_unlock_checks=20)
    v11 = ProgressiveParallelPortfolioStrategy(max_chest_pairs_per_hero=20, max_unlock_checks=20)

    # La correction ne doit pas reproduire l'ancien v11 qui faisait WAIT a M des
    # le depart. Sur le premier coffre, les deux versions doivent rester identiques.
    for _ in range(11):
        a10 = v10.next_actions(v10_sim.state)
        a11 = v11.next_actions(v11_sim.state)
        assert a11 == a10
        v10_sim.step(a10)
        v11_sim.step(a11)

    assert v11_sim.state.secured_chests == 1
