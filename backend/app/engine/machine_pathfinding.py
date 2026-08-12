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
    if any((machine_locale.id != machine.id and machine_locale.position == pos for machine_locale in state.machines.values())):
        return False
    if pos in state.chests:
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
            if suivant in precedents or not _base_passable(state, machine, suivant):
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
