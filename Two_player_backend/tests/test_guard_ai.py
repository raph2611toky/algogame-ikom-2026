from __future__ import annotations

import copy

from app.domain.enums import Difficulty, Direction, GuardMode, HeroId, NoiseKind
from app.domain.models import NoiseEvent, Position
from app.engine.guard_ai.easy import EasyGuardAI
from app.engine.guard_ai.hard import HardGuardAI
from app.engine.guard_ai.medium import MediumGuardAI
from app.engine.map_parser import MapParser
from app.engine.perception import update_perception
from app.engine.simulator import Simulator


MAP = """7 9 60
#########
#F......#
#.......#
#...K...#
#.......#
#M......#
#########"""


def make_state(difficulty=Difficulty.MEDIUM):
    return Simulator.initial_state(MapParser.parse(MAP), difficulty=difficulty, seed=7)


def test_easy_is_seeded_and_legal():
    first = make_state(Difficulty.EASY)
    second = make_state(Difficulty.EASY)
    assert EasyGuardAI().choose_direction(first) == EasyGuardAI().choose_direction(second)


def test_medium_investigates_audible_noise():
    state = make_state()
    state.noises.append(NoiseEvent(Position(3, 2), 5, 10, NoiseKind.RUN, "F"))
    update_perception(state)
    assert state.guard.memory.mode == GuardMode.INVESTIGATE
    assert MediumGuardAI().choose_direction(state) == Direction.LEFT


def test_hard_does_not_read_hidden_position():
    first = make_state(Difficulty.HARD)
    second = copy.deepcopy(first)
    first.heroes[HeroId.IKOTOFOSA].hidden = True
    second.heroes[HeroId.IKOTOFOSA].hidden = True
    second.heroes[HeroId.IKOTOFOSA].position = Position(5, 7)
    assert HardGuardAI().choose_direction(first) == HardGuardAI().choose_direction(second)


def test_hard_uses_belief_after_lost_contact():
    state = make_state(Difficulty.HARD)
    state.guard.memory.mode = GuardMode.SEARCH
    state.guard.memory.target = HeroId.IKOTOFOSA
    state.guard.memory.last_known[HeroId.IKOTOFOSA] = Position(1, 3)
    state.guard.memory.beliefs[HeroId.IKOTOFOSA] = {Position(1, 3): 1.0}
    direction = HardGuardAI().choose_direction(state)
    assert direction in set(Direction)
    assert state.guard.memory.beliefs[HeroId.IKOTOFOSA]
