from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count

from app.domain.enums import (
    DIRECTION_TO_PUSH_ACTION,
    DIRECTION_VECTORS,
    Direction,
    HeroAction,
    HeroId,
)
from app.domain.models import GameState, Position
from app.engine.pathfinding import hero_neighbors


@dataclass(frozen=True, slots=True)
class ChestPlan:
    actions: tuple[HeroAction, ...]
    stamina_cost: int
    chest_start: Position
    bush: Position

    @property
    def ticks(self) -> int:
        return len(self.actions)


@dataclass(frozen=True, slots=True)
class _Node:
    hero: Position
    chest: Position


def _heuristic(chest: Position, bush: Position) -> int:
    return chest.manhattan(bush)


def plan_chest_to_bush(
    state: GameState,
    hero_id: HeroId,
    chest: Position,
    bush: Position,
    *,
    max_expansions: int = 30_000,
) -> ChestPlan | None:
    if chest not in state.chests or bush not in state.game_map.bushes:
        return None

    start = _Node(state.heroes[hero_id].position, chest)
    serial = count()
    heap: list[tuple[int, int, int, int, _Node]] = []
    heappush(heap, (_heuristic(chest, bush), 0, 0, next(serial), start))
    best: dict[_Node, tuple[int, int]] = {start: (0, 0)}
    parent: dict[_Node, tuple[_Node, HeroAction, int]] = {}
    other_chests = set(state.chests)
    other_chests.discard(chest)
    expansions = 0
    goal_node: _Node | None = None
    goal_action: HeroAction | None = None
    goal_stamina = 0

    while heap and expansions < max_expansions:
        _, ticks, stamina, _, node = heappop(heap)
        if best.get(node) != (ticks, stamina):
            continue
        expansions += 1

        for step in hero_neighbors(state, hero_id, node.hero):
            next_node = _Node(step.destination, node.chest)
            nt = ticks + 1
            ns = stamina + step.stamina_cost
            if best.get(next_node, (10**9, 10**9)) <= (nt, ns):
                continue
            best[next_node] = (nt, ns)
            parent[next_node] = (node, step.action, step.stamina_cost)
            heappush(
                heap,
                (
                    nt + _heuristic(node.chest, bush),
                    nt,
                    ns,
                    next(serial),
                    next_node,
                ),
            )

        for direction in Direction:
            dr, dc = DIRECTION_VECTORS[direction]
            if node.hero.moved(dr, dc) != node.chest:
                continue
            chest_to = node.chest.moved(dr, dc)
            if not state.game_map.in_bounds(chest_to):
                continue
            if chest_to in state.game_map.rocks or chest_to in state.trees:
                continue
            if chest_to in other_chests:
                continue
            if chest_to in state.holes:
                continue

            action = DIRECTION_TO_PUSH_ACTION[direction]
            if chest_to == bush:
                goal_node = node
                goal_action = action
                goal_stamina = stamina + 5
                heap.clear()
                break

            next_node = _Node(node.chest, chest_to)
            nt = ticks + 1
            ns = stamina + 5
            if best.get(next_node, (10**9, 10**9)) <= (nt, ns):
                continue
            best[next_node] = (nt, ns)
            parent[next_node] = (node, action, 5)
            heappush(
                heap,
                (
                    nt + _heuristic(chest_to, bush),
                    nt,
                    ns,
                    next(serial),
                    next_node,
                ),
            )
        if goal_node is not None:
            break

    if goal_node is None or goal_action is None:
        return None

    actions_rev: list[HeroAction] = [goal_action]
    cursor = goal_node
    while cursor != start:
        prev, action, _cost = parent[cursor]
        actions_rev.append(action)
        cursor = prev
    actions_rev.reverse()
    return ChestPlan(tuple(actions_rev), goal_stamina, chest, bush)
