from __future__ import annotations

import heapq
from collections.abc import Callable

from app.domain.enums import Direction
from app.domain.models import Position
from app.engine.rules import DIRECTION_VECTOR


def astar(
    start: Position,
    goal: Position,
    walkable: Callable[[Position], bool],
    *,
    max_nodes: int = 5000,
) -> list[Position]:
    if start == goal:
        return [start]
    frontier: list[tuple[int, int, Position]] = []
    serial = 0
    heapq.heappush(frontier, (start.manhattan(goal), serial, start))
    came_from: dict[Position, Position | None] = {start: None}
    cost: dict[Position, int] = {start: 0}
    visited = 0
    while frontier and visited < max_nodes:
        _, _, current = heapq.heappop(frontier)
        visited += 1
        if current == goal:
            break
        for dr, dc in DIRECTION_VECTOR.values():
            nxt = current.moved(dr, dc)
            if nxt != goal and not walkable(nxt):
                continue
            new_cost = cost[current] + 1
            if new_cost >= cost.get(nxt, 10**9):
                continue
            cost[nxt] = new_cost
            came_from[nxt] = current
            serial += 1
            heapq.heappush(frontier, (new_cost + nxt.manhattan(goal), serial, nxt))
    if goal not in came_from:
        return []
    path = []
    cursor: Position | None = goal
    while cursor is not None:
        path.append(cursor)
        cursor = came_from[cursor]
    path.reverse()
    return path


def direction_for_step(source: Position, destination: Position) -> Direction | None:
    delta = (destination.row - source.row, destination.col - source.col)
    for direction, vector in DIRECTION_VECTOR.items():
        if vector == delta:
            return direction
    return None

