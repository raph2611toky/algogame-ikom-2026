from __future__ import annotations

from pathlib import Path

from app.domain.enums import HeroAction, HeroId, Orientation
from app.domain.models import Position
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
from app.engine.strategy_v10 import OpportunityCommittedPortfolioStrategy


REGRESSION = Path("maps/regression/user_15x20_shared_opportunity.txt")

FIRST_CHEST_ACTIONS = [
    ("RIGHT", "UP"),
    ("RIGHT", "LEFT"),
    ("RIGHT", "LEFT"),
    ("RIGHT", "LEFT"),
    ("DOWN", "RIGHT"),
    ("DOWN", "DOWN"),
    ("PUSH_RIGHT", "DOWN"),
    ("PUSH_RIGHT", "DOWN"),
    ("PUSH_RIGHT", "UP"),
    ("PUSH_RIGHT", "UP"),
    ("PUSH_RIGHT", "UP"),
]


def _state_after_first_chest():
    game_map = MapParser.parse(REGRESSION.read_text(encoding="utf-8"))
    state = MapParser.build_initial_state(game_map)
    sim = Simulator(state)
    for f_action, m_action in FIRST_CHEST_ACTIONS:
        sim.step(
            {
                HeroId.IKOTOFOSA: HeroAction(f_action),
                HeroId.IMAHAKI: HeroAction(m_action),
            }
        )
    return sim.state


def test_v10_shared_corridor_is_ranked_ahead_of_isolated_top_chest() -> None:
    state = _state_after_first_chest()
    strategy = OpportunityCommittedPortfolioStrategy(max_unlock_checks=20)
    strategy._refresh_opportunity_cache(state)

    # Les deux coffres du bas partagent le noyau central; le scheduler doit donc
    # preferer une opportunite qui profite a plusieurs coffres, pas seulement le
    # coffre du haut le plus isole.
    assert strategy._obstacle_support_cache.get(Position(10, 9), 0) >= 2
    assert strategy._obstacle_support_cache.get(Position(11, 9), 0) >= 2
    assert strategy._obstacle_support_cache.get(Position(12, 9), 0) >= 2
    assert strategy._select_target_chest(state) in {Position(13, 1), Position(13, 18)}


def test_v10_predicts_excavator_push_to_non_bush_boundary_as_critical() -> None:
    game_map = MapParser.parse(
        """4 6 100
F...@M
.X....
.*....
......
"""
    )
    state = MapParser.build_initial_state(game_map)
    machine = next(machine for machine in state.machines.values() if machine.id.startswith("X"))
    machine.orientation = Orientation.FACING_DOWN
    strategy = OpportunityCommittedPortfolioStrategy()

    hazard = strategy._predict_autonomous_hazard(state, machine.id, horizon=4)
    assert hazard is not None
    assert hazard.risk >= strategy.AUTONOMOUS_HAZARD_CRITICAL
    assert hazard.chest_from == Position(2, 1)
    assert hazard.chest_to == Position(3, 1)
    assert "bord" in hazard.reason


def test_v10_reserves_compatible_hero_for_critical_machine_interception() -> None:
    rows = ["F..........@M", "..X.........."]
    rows.extend(["............."] * 9)
    rows.append("..*..........")
    rows.append(".............")
    game_map = MapParser.parse("13 13 100\n" + "\n".join(rows) + "\n")
    state = MapParser.build_initial_state(game_map)
    machine = next(machine for machine in state.machines.values() if machine.id.startswith("X"))
    machine.orientation = Orientation.FACING_DOWN
    strategy = OpportunityCommittedPortfolioStrategy()
    decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}

    strategy._protect_chests_from_autonomous_machines(state, decisions)
    assert HeroId.IKOTOFOSA in strategy._defense_intercepts
    assert decisions[HeroId.IKOTOFOSA] != HeroAction.WAIT or state.heroes[HeroId.IKOTOFOSA].position == strategy._defense_intercepts[HeroId.IKOTOFOSA][1]


def test_v10_does_not_override_v8_v9_core_selection_methods() -> None:
    # v10 est volontairement une couche ciblee. Ces methodes restent celles du
    # coeur herite; si quelqu'un les reimplemente plus tard, ce test doit alerter.
    forbidden = {
        "_direct_collaborative_actions",
        "_cache_route",
        "_route_valid",
        "_maybe_handoff",
        "_best_stone_action_for_hero",
    }
    assert forbidden.isdisjoint(OpportunityCommittedPortfolioStrategy.__dict__)
