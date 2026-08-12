from __future__ import annotations

from collections import deque

from app.domain.enums import DIRECTION_VECTORS, Direction, MachineKind
from app.domain.models import GameState, MachineState, Position


def _base_passable(state: GameState, machine: MachineState, pos: Position) -> bool:
    if not state.game_map.in_bounds(pos):
        return False
    if pos in state.game_map.rocks:
        return False
    if machine.kind == MachineKind.EXCAVATOR and pos in state.trees:
        return False
    if machine.kind == MachineKind.GRAPPLER and pos in state.holes:
        return False
    if any(m.id != machine.id and m.position == pos for m in state.machines.values()):
        return False
    # Chests are potentially pushable; for route planning we conservatively avoid
    # them. The simulator still implements automatic machine pushes when they occur.
    if pos in state.chests:
        return False
    return True


def find_machine_path(
    state: GameState,
    machine: MachineState,
    goals: set[Position],
    *,
    max_expansions: int = 100_000,
) -> list[Position] | None:
    """BFS over machine positions; returns [start, ..., reached_goal]."""
    if machine.position in goals:
        return [machine.position]
    q = deque([machine.position])
    parent: dict[Position, Position | None] = {machine.position: None}
    expansions = 0
    found: Position | None = None
    while q and expansions < max_expansions:
        cur = q.popleft()
        expansions += 1
        for direction in Direction:
            dr, dc = DIRECTION_VECTORS[direction]
            nxt = cur.moved(dr, dc)
            if nxt in parent or not _base_passable(state, machine, nxt):
                continue
            parent[nxt] = cur
            if nxt in goals:
                found = nxt
                q.clear()
                break
            q.append(nxt)
    if found is None:
        return None
    path: list[Position] = []
    cur: Position | None = found
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path


def direction_between(a: Position, b: Position) -> Direction:
    dr = b.row - a.row
    dc = b.col - a.col
    for direction, (r, c) in DIRECTION_VECTORS.items():
        if (dr, dc) == (r, c):
            return direction
    raise ValueError(f"Positions non adjacentes: {a} -> {b}")
