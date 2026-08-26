from __future__ import annotations

from enum import StrEnum


class HeroId(StrEnum):
    IKOTOFOSA = "F"
    IMAHAKI = "M"


class Direction(StrEnum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class HeroAction(StrEnum):
    WAIT = "WAIT"
    MOVE = "MOVE"
    RUN = "RUN"
    PUSH = "PUSH"
    HIDE = "HIDE"
    CARRY = "CARRY"
    DROP = "DROP"
    HEAL = "HEAL"
    ASSISTED_JUMP = "ASSISTED_JUMP"
    USE_MACHINE = "USE_MACHINE"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class GuardMode(StrEnum):
    PATROL = "PATROL"
    INVESTIGATE = "INVESTIGATE"
    CHASE = "CHASE"
    SEARCH = "SEARCH"


class GameStatus(StrEnum):
    ACTIVE = "ACTIVE"
    WON = "WON"
    LOST = "LOST"


class MachineKind(StrEnum):
    EXCAVATOR = "X"
    GRAPPLER = "G"


class NoiseKind(StrEnum):
    WALK = "WALK"
    RUN = "RUN"
    JUMP = "JUMP"
    HEAL = "HEAL"
    CARRY = "CARRY"
    ASSISTED_JUMP = "ASSISTED_JUMP"
    MACHINE = "MACHINE"
    IMPACT = "IMPACT"

