from __future__ import annotations

import math

from app.domain.enums import Direction, HeroId, NoiseKind
from app.domain.models import GameMap, GameState, HeroState, Position


DIRECTION_VECTOR: dict[Direction, tuple[int, int]] = {
    Direction.UP: (-1, 0),
    Direction.DOWN: (1, 0),
    Direction.LEFT: (0, -1),
    Direction.RIGHT: (0, 1),
}

NOISE_RADIUS: dict[NoiseKind, int] = {
    NoiseKind.WALK: 2,
    NoiseKind.RUN: 5,
    NoiseKind.JUMP: 5,
    NoiseKind.HEAL: 3,
    NoiseKind.CARRY: 7,
    NoiseKind.ASSISTED_JUMP: 8,
    NoiseKind.MACHINE: 12,
    NoiseKind.IMPACT: 5,
}


def health_factor(hp: int) -> float:
    if hp <= 0:
        return 0.0
    if hp <= 25:
        return 0.55
    if hp <= 50:
        return 0.75
    if hp <= 75:
        return 0.90
    return 1.0


def hero_base_speed(hero_id: HeroId) -> float:
    return 1.10 if hero_id == HeroId.IKOTOFOSA else 1.0


def hero_speed(hero: HeroState, state: GameState, *, running: bool = False) -> float:
    speed = hero_base_speed(hero.id) * health_factor(hero.hp)
    if hero.carrying is not None:
        speed *= state.balance.carry_speed_factor
    if running:
        speed *= state.balance.run_speed_factor
    return speed


def cooldown_from_speed(speed: float) -> int:
    if speed <= 0:
        return 10**9
    return max(1, math.ceil(10 / speed))


def direction_between(source: Position, destination: Position) -> Direction | None:
    dr = destination.row - source.row
    dc = destination.col - source.col
    if abs(dr) > abs(dc):
        return Direction.DOWN if dr > 0 else Direction.UP
    if dc:
        return Direction.RIGHT if dc > 0 else Direction.LEFT
    return None


def next_position(position: Position, direction: Direction, steps: int = 1) -> Position:
    dr, dc = DIRECTION_VECTOR[direction]
    return position.moved(dr, dc, steps)


def elevation_allowed(
    game_map: GameMap,
    source: Position,
    destination: Position,
    *,
    max_up: int = 2,
    max_down: int = 4,
) -> bool:
    if not game_map.has_elevation:
        return True
    delta = game_map.elevation_at(destination) - game_map.elevation_at(source)
    return delta <= max_up and delta >= -max_down


def guard_cell_walkable(state: GameState, pos: Position) -> bool:
    return guard_step_allowed(state, state.guard.position, pos)


def guard_step_allowed(state: GameState, source: Position, pos: Position) -> bool:
    game_map = state.game_map
    return (
        game_map.in_bounds(pos)
        and pos not in game_map.rocks
        and pos not in state.trees
        and pos not in state.holes
        and pos not in state.chests
        and elevation_allowed(game_map, source, pos)
    )


def guard_static_walkable(state: GameState, pos: Position) -> bool:
    game_map = state.game_map
    return (
        game_map.in_bounds(pos)
        and pos not in game_map.rocks
        and pos not in state.trees
        and pos not in state.holes
        and pos not in state.chests
    )


def machine_step_allowed(state: GameState, source: Position, pos: Position) -> bool:
    game_map = state.game_map
    if not game_map.in_bounds(pos) or pos in game_map.rocks:
        return False
    if game_map.has_elevation:
        delta = game_map.elevation_at(pos) - game_map.elevation_at(source)
        if abs(delta) > 4:
            return False
    return True


def generic_walkable(state: GameState, pos: Position, *, ignore_heroes: bool = False) -> bool:
    game_map = state.game_map
    if not game_map.in_bounds(pos):
        return False
    if pos in game_map.rocks or pos in state.trees or pos in state.holes or pos in state.chests:
        return False
    if not ignore_heroes and any(hero.position == pos and hero.carried_by is None for hero in state.heroes.values()):
        return False
    return True


def hero_destination(
    state: GameState,
    hero: HeroState,
    direction: Direction,
) -> tuple[Position | None, str, int, NoiseKind]:
    """Return destination, movement kind, stamina cost and noise kind."""
    first = next_position(hero.position, direction)
    game_map = state.game_map
    if not game_map.in_bounds(first) or first in game_map.rocks:
        return None, "blocked", 0, NoiseKind.WALK
    if first in state.chests:
        return None, "chest", 0, NoiseKind.WALK
    if first in state.holes:
        if hero.id != HeroId.IKOTOFOSA:
            return None, "hole", 0, NoiseKind.WALK
        landing = next_position(hero.position, direction, 2)
        if not generic_walkable(state, landing, ignore_heroes=True):
            return None, "invalid_jump", 0, NoiseKind.JUMP
        if not elevation_allowed(game_map, hero.position, landing):
            return None, "elevation", 0, NoiseKind.JUMP
        return landing, "jump", 10, NoiseKind.JUMP
    if first in state.trees:
        if hero.id != HeroId.IMAHAKI:
            return None, "tree", 0, NoiseKind.WALK
        landing = next_position(hero.position, direction, 2)
        if not generic_walkable(state, landing, ignore_heroes=True):
            return None, "invalid_climb", 0, NoiseKind.JUMP
        if not elevation_allowed(game_map, hero.position, landing):
            return None, "elevation", 0, NoiseKind.JUMP
        return landing, "climb", 10, NoiseKind.JUMP
    if not elevation_allowed(game_map, hero.position, first):
        return None, "elevation", 0, NoiseKind.WALK
    return first, "walk", 1, NoiseKind.WALK


def adjacent(a: Position, b: Position) -> bool:
    return a.manhattan(b) <= 1
