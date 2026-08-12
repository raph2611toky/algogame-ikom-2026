from __future__ import annotations
from enum import StrEnum

class HeroId(StrEnum):
    IKOTOFOSA = 'F'
    IMAHAKI = 'M'

class MachineKind(StrEnum):
    EXCAVATOR = 'X'
    GRAPPLER = 'G'

class CellSymbol(StrEnum):
    EMPTY = '.'
    IKOTOFOSA = 'F'
    IMAHAKI = 'M'
    ROCK = '#'
    TREE = 't'
    HOLE = 'o'
    EXCAVATOR = 'X'
    GRAPPLER = 'G'
    CHEST = '*'
    STONE = '+'
    BUSH = '@'

class Direction(StrEnum):
    UP = 'UP'
    RIGHT = 'RIGHT'
    DOWN = 'DOWN'
    LEFT = 'LEFT'

class Orientation(StrEnum):
    FACING_UP = 'FACING_UP'
    FACING_RIGHT = 'FACING_RIGHT'
    FACING_DOWN = 'FACING_DOWN'
    FACING_LEFT = 'FACING_LEFT'

class HeroAction(StrEnum):
    UP = 'UP'
    DOWN = 'DOWN'
    LEFT = 'LEFT'
    RIGHT = 'RIGHT'
    WAIT = 'WAIT'
    PUSH_UP = 'PUSH_UP'
    PUSH_DOWN = 'PUSH_DOWN'
    PUSH_LEFT = 'PUSH_LEFT'
    PUSH_RIGHT = 'PUSH_RIGHT'
    HACK = 'HACK'
    HACK_MOVE = 'HACK_MOVE'
    HACK_FILL = 'HACK_FILL'
    HACK_CW = 'HACK_CW'
    HACK_CCW = 'HACK_CCW'
    HACK_CUT = 'HACK_CUT'

class MachineAction(StrEnum):
    NONE = 'NONE'
    WAIT = 'WAIT'
    MOVE = 'MOVE'
    CW = 'CW'
    CCW = 'CCW'
    CUT = 'CUT'
    DIG = 'DIG'
    FILL = 'FILL'
MOVE_ACTIONS = {HeroAction.UP, HeroAction.DOWN, HeroAction.LEFT, HeroAction.RIGHT}
PUSH_ACTIONS = {HeroAction.PUSH_UP, HeroAction.PUSH_DOWN, HeroAction.PUSH_LEFT, HeroAction.PUSH_RIGHT}
HACK_ACTIONS = {HeroAction.HACK, HeroAction.HACK_MOVE, HeroAction.HACK_FILL, HeroAction.HACK_CW, HeroAction.HACK_CCW, HeroAction.HACK_CUT}
DIRECTION_VECTORS: dict[Direction, tuple[int, int]] = {Direction.UP: (-1, 0), Direction.RIGHT: (0, 1), Direction.DOWN: (1, 0), Direction.LEFT: (0, -1)}
ACTION_TO_DIRECTION: dict[HeroAction, Direction] = {HeroAction.UP: Direction.UP, HeroAction.RIGHT: Direction.RIGHT, HeroAction.DOWN: Direction.DOWN, HeroAction.LEFT: Direction.LEFT, HeroAction.PUSH_UP: Direction.UP, HeroAction.PUSH_RIGHT: Direction.RIGHT, HeroAction.PUSH_DOWN: Direction.DOWN, HeroAction.PUSH_LEFT: Direction.LEFT}
DIRECTION_TO_MOVE_ACTION: dict[Direction, HeroAction] = {Direction.UP: HeroAction.UP, Direction.RIGHT: HeroAction.RIGHT, Direction.DOWN: HeroAction.DOWN, Direction.LEFT: HeroAction.LEFT}
DIRECTION_TO_PUSH_ACTION: dict[Direction, HeroAction] = {Direction.UP: HeroAction.PUSH_UP, Direction.RIGHT: HeroAction.PUSH_RIGHT, Direction.DOWN: HeroAction.PUSH_DOWN, Direction.LEFT: HeroAction.PUSH_LEFT}
ORIENTATION_TO_DIRECTION: dict[Orientation, Direction] = {Orientation.FACING_UP: Direction.UP, Orientation.FACING_RIGHT: Direction.RIGHT, Orientation.FACING_DOWN: Direction.DOWN, Orientation.FACING_LEFT: Direction.LEFT}
DIRECTION_TO_ORIENTATION: dict[Direction, Orientation] = {value: key for key, value in ORIENTATION_TO_DIRECTION.items()}
CLOCKWISE: dict[Orientation, Orientation] = {Orientation.FACING_UP: Orientation.FACING_RIGHT, Orientation.FACING_RIGHT: Orientation.FACING_DOWN, Orientation.FACING_DOWN: Orientation.FACING_LEFT, Orientation.FACING_LEFT: Orientation.FACING_UP}
COUNTER_CLOCKWISE: dict[Orientation, Orientation] = {Orientation.FACING_UP: Orientation.FACING_LEFT, Orientation.FACING_LEFT: Orientation.FACING_DOWN, Orientation.FACING_DOWN: Orientation.FACING_RIGHT, Orientation.FACING_RIGHT: Orientation.FACING_UP}
ALL_MAP_SYMBOLS = {item.value for item in CellSymbol}
ALL_HERO_ACTIONS = {item.value for item in HeroAction}
