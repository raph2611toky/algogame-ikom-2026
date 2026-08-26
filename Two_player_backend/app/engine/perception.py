from __future__ import annotations

from collections import defaultdict

from app.domain.enums import GuardMode, HeroId
from app.domain.models import GameState, Position
from app.engine.rules import DIRECTION_VECTOR, generic_walkable


def _bresenham(a: Position, b: Position) -> list[Position]:
    x0, y0, x1, y1 = a.col, a.row, b.col, b.row
    dx, sx = abs(x1 - x0), 1 if x0 < x1 else -1
    dy, sy = -abs(y1 - y0), 1 if y0 < y1 else -1
    err = dx + dy
    points: list[Position] = []
    while True:
        points.append(Position(y0, x0))
        if x0 == x1 and y0 == y1:
            return points
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def in_line_of_sight(state: GameState, target: Position) -> bool:
    guard = state.guard
    source = guard.position
    distance = source.manhattan(target)
    if distance > state.balance.guard_vision_range:
        return False
    dr, dc = target.row - source.row, target.col - source.col
    fr, fc = DIRECTION_VECTOR[guard.orientation]
    forward = dr * fr + dc * fc
    lateral = abs(dr * fc - dc * fr)
    # A 90-degree forward cone; adjacent side cells remain perceivable.
    if forward < 0 or (forward == 0 and distance > 1) or lateral > forward + 1:
        return False
    blockers = state.game_map.rocks | state.trees | state.chests
    for cell in _bresenham(source, target)[1:-1]:
        if cell in blockers:
            return False
    return True


def update_perception(state: GameState) -> None:
    memory = state.guard.memory
    visible_now: set[HeroId] = set()
    for hero_id, hero in state.heroes.items():
        seen = not hero.hidden and not hero.is_ko and in_line_of_sight(state, hero.position)
        meter = memory.detection.get(hero_id, 0)
        if seen:
            meter = min(100, meter + 34)
            if meter >= state.balance.detection_threshold:
                visible_now.add(hero_id)
                memory.last_known[hero_id] = hero.position
                memory.beliefs[hero_id] = {hero.position: 1.0}
        else:
            meter = max(0, meter - 18)
        memory.detection[hero_id] = meter
    memory.visible = visible_now

    heard = [noise for noise in state.noises if noise.position.manhattan(state.guard.position) <= noise.radius]
    if heard:
        strongest = max(heard, key=lambda n: (n.radius - n.position.manhattan(state.guard.position), n.ttl))
        memory.last_heard = strongest.position
        memory.last_heard_strength = strongest.radius

    if visible_now:
        memory.mode = GuardMode.CHASE
        memory.target = min(visible_now, key=lambda hid: state.guard.position.manhattan(state.heroes[hid].position))
        memory.search_ticks = 35
    elif memory.mode == GuardMode.CHASE and memory.target in memory.last_known:
        memory.mode = GuardMode.SEARCH
        memory.search_ticks = max(memory.search_ticks, 35)
    elif memory.last_heard is not None and memory.last_heard_strength >= 2:
        memory.mode = GuardMode.INVESTIGATE
        memory.search_ticks = max(memory.search_ticks, 25)
    elif memory.mode in {GuardMode.SEARCH, GuardMode.INVESTIGATE}:
        memory.search_ticks -= 1
        if memory.search_ticks <= 0:
            memory.mode = GuardMode.PATROL
            memory.target = None
            memory.last_heard = None
            memory.last_heard_strength = 0


def propagate_beliefs(state: GameState) -> None:
    """Hard AI belief update without reading hidden hero coordinates."""
    memory = state.guard.memory
    guard_visible_cells = {
        pos for pos in state.game_map.positions() if in_line_of_sight(state, pos)
    }
    for hero_id, distribution in list(memory.beliefs.items()):
        if hero_id in memory.visible:
            continue
        if not distribution:
            known = memory.last_known.get(hero_id)
            if known is None:
                continue
            distribution = {known: 1.0}
        expanded: defaultdict[Position, float] = defaultdict(float)
        for pos, probability in distribution.items():
            candidates = [pos]
            for dr, dc in DIRECTION_VECTOR.values():
                nxt = pos.moved(dr, dc)
                if generic_walkable(state, nxt, ignore_heroes=True):
                    candidates.append(nxt)
            share = probability / len(candidates)
            for candidate in candidates:
                # The guard sees that no non-hidden hero is in its current cone.
                if candidate in guard_visible_cells:
                    continue
                expanded[candidate] += share
        total = sum(expanded.values())
        if total <= 0:
            memory.beliefs[hero_id] = {}
            continue
        ranked = sorted(expanded.items(), key=lambda item: item[1], reverse=True)[:256]
        norm = sum(value for _, value in ranked)
        memory.beliefs[hero_id] = {pos: value / norm for pos, value in ranked}

