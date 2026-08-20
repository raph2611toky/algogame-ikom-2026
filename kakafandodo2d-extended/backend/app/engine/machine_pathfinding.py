from __future__ import annotations
from collections import deque
from app.domain.enums import DIRECTION_TO_ORIENTATION, DIRECTION_VECTORS, Direction, MachineKind
from app.domain.models import GameState, MachineState, Position
from app.engine.rules import Rules


def _base_passable(state: GameState, machine: MachineState, current: Position, pos: Position, direction: Direction) -> bool:
    if not state.game_map.in_bounds(pos):
        return False
    if pos in state.game_map.rocks:
        return False
    if Rules.machine_elevation_reason(state, current, pos) is not None:
        return False
    if machine.kind == MachineKind.EXCAVATOR and pos in state.trees:
        return False
    if machine.kind == MachineKind.GRAPPLER and pos in state.holes:
        return False
    if pos in state.chests:
        return False
    # The static planner uses the same four-cell machine look-ahead as runtime.
    # Heroes are intentionally ignored here because they can move and because
    # normal machine movement may share a cell with a hero.
    if Rules.machine_lookahead_reason(
        state,
        machine,
        position=current,
        orientation=DIRECTION_TO_ORIENTATION[direction],
        check_heroes=False,
    ) is not None:
        return False
    return True


def find_machine_path(state: GameState, machine: MachineState, goals: set[Position], *, max_expansions: int=100000) -> list[Position] | None:
    if machine.position in goals:
        return [machine.position]
    file_attente = deque([machine.position])
    precedents: dict[Position, Position | None] = {machine.position: None}
    explorations = 0
    trouve: Position | None = None
    while file_attente and explorations < max_expansions:
        courant = file_attente.popleft()
        explorations += 1
        for direction in Direction:
            delta_ligne, delta_col = DIRECTION_VECTORS[direction]
            suivant = courant.moved(delta_ligne, delta_col)
            if suivant in precedents or not _base_passable(state, machine, courant, suivant, direction):
                continue
            precedents[suivant] = courant
            if suivant in goals:
                trouve = suivant
                file_attente.clear()
                break
            file_attente.append(suivant)
    if trouve is None:
        return None
    chemin: list[Position] = []
    courant: Position | None = trouve
    while courant is not None:
        chemin.append(courant)
        courant = precedents[courant]
    chemin.reverse()
    return chemin


def direction_between(a: Position, b: Position) -> Direction:
    delta_ligne = b.row - a.row
    delta_col = b.col - a.col
    for direction, (ligne_idx, colonne_idx) in DIRECTION_VECTORS.items():
        if (delta_ligne, delta_col) == (ligne_idx, colonne_idx):
            return direction
    raise ValueError(f'Positions non adjacentes: {a} -> {b}')
