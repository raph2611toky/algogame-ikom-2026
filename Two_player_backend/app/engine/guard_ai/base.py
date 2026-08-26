from __future__ import annotations

from typing import Protocol

from app.domain.enums import Direction
from app.domain.models import GameState, Position
from app.engine.pathfinding import astar, direction_for_step
from app.engine.rules import guard_static_walkable, guard_step_allowed, next_position


class GuardPolicy(Protocol):
    def choose_direction(self, state: GameState) -> Direction | None: ...


def legal_directions(state: GameState) -> list[Direction]:
    result: list[Direction] = []
    for direction in Direction:
        destination = next_position(state.guard.position, direction)
        if guard_step_allowed(state, state.guard.position, destination):
            result.append(direction)
    return result


def direction_towards(state: GameState, goal: Position | None) -> Direction | None:
    if goal is None or goal == state.guard.position:
        return None
    path = astar(
        state.guard.position,
        goal,
        lambda pos: guard_static_walkable(state, pos),
    )
    if len(path) < 2:
        return None
    direction = direction_for_step(path[0], path[1])
    if direction is None:
        return None
    if not guard_step_allowed(state, path[0], path[1]):
        return None
    return direction
