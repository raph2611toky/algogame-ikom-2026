from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count

from app.domain.enums import (
    DIRECTION_TO_MOVE_ACTION,
    DIRECTION_VECTORS,
    Direction,
    HeroAction,
    HeroId,
)
from app.domain.models import GameState, Position


@dataclass(frozen=True, slots=True)
class PathStep:
    action: HeroAction
    destination: Position
    stamina_cost: int
    special: bool = False


@dataclass(frozen=True, slots=True)
class PathResult:
    steps: tuple[PathStep, ...]
    total_stamina_cost: int

    @property
    def ticks(self) -> int:
        return len(self.steps)


def hero_neighbors(
    state: GameState,
    hero_id: HeroId,
    position: Position,
) -> list[PathStep]:
    result: list[PathStep] = []
    for direction in Direction:
        dr, dc = DIRECTION_VECTORS[direction]
        adjacent = position.moved(dr, dc)
        if not state.game_map.in_bounds(adjacent):
            continue
        if adjacent in state.game_map.rocks:
            continue

        if hero_id == HeroId.IKOTOFOSA and adjacent in state.holes:
            landing = adjacent.moved(dr, dc)
            if not state.game_map.in_bounds(landing):
                continue
            if (
                landing in state.game_map.rocks
                or landing in state.trees
                or landing in state.holes
            ):
                continue
            result.append(
                PathStep(
                    DIRECTION_TO_MOVE_ACTION[direction],
                    landing,
                    stamina_cost=10,
                    special=True,
                )
            )
            continue

        if hero_id == HeroId.IMAHAKI and adjacent in state.trees:
            landing = adjacent.moved(dr, dc)
            if not state.game_map.in_bounds(landing):
                continue
            if (
                landing in state.game_map.rocks
                or landing in state.trees
                or landing in state.holes
            ):
                continue
            result.append(
                PathStep(
                    DIRECTION_TO_MOVE_ACTION[direction],
                    landing,
                    stamina_cost=10,
                    special=True,
                )
            )
            continue

        if adjacent in state.trees or adjacent in state.holes:
            continue
        result.append(
            PathStep(
                DIRECTION_TO_MOVE_ACTION[direction],
                adjacent,
                stamina_cost=1,
            )
        )
    return result


def _heuristic(a: Position, b: Position) -> int:
    return (a.manhattan(b) + 1) // 2


def find_path(
    state: GameState,
    hero_id: HeroId,
    goal: Position,
    *,
    start: Position | None = None,
    max_expansions: int = 100_000,
) -> PathResult | None:
    if not state.game_map.in_bounds(goal):
        return None
    start = start or state.heroes[hero_id].position
    if start == goal:
        return PathResult(steps=(), total_stamina_cost=0)

    serial = count()
    heap: list[tuple[int, int, int, int, Position]] = []
    heappush(heap, (_heuristic(start, goal), 0, 0, next(serial), start))
    best: dict[Position, tuple[int, int]] = {start: (0, 0)}
    parent: dict[Position, tuple[Position, PathStep]] = {}
    expansions = 0

    while heap and expansions < max_expansions:
        _, g_ticks, stamina_cost, _, current = heappop(heap)
        known = best.get(current)
        if known is None or (g_ticks, stamina_cost) != known:
            continue
        if current == goal:
            steps_rev: list[PathStep] = []
            cursor = current
            while cursor != start:
                prev, step = parent[cursor]
                steps_rev.append(step)
                cursor = prev
            steps_rev.reverse()
            return PathResult(tuple(steps_rev), stamina_cost)

        expansions += 1
        for step in hero_neighbors(state, hero_id, current):
            ng = g_ticks + 1
            ns = stamina_cost + step.stamina_cost
            old = best.get(step.destination)
            if old is not None and old <= (ng, ns):
                continue
            best[step.destination] = (ng, ns)
            parent[step.destination] = (current, step)
            heappush(
                heap,
                (
                    ng + _heuristic(step.destination, goal),
                    ng,
                    ns,
                    next(serial),
                    step.destination,
                ),
            )
    return None
