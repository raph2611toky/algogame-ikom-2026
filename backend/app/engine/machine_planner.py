from __future__ import annotations
from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from app.domain.enums import CLOCKWISE, COUNTER_CLOCKWISE, DIRECTION_TO_ORIENTATION, DIRECTION_VECTORS, ORIENTATION_TO_DIRECTION, HeroAction, MachineKind, Orientation
from app.domain.models import GameState, MachineState, Position
from app.engine.score_pathfinding import score_cost_units
from app.engine.rules import Rules

@dataclass(frozen=True, slots=True)
class MachineControlPlan:
    actions: tuple[HeroAction, ...]
    target: Position
    ticks: int
    battery_cost: int

    @property
    def score_cost_units(self) -> int:
        return score_cost_units(self.ticks, 0, self.battery_cost)


@dataclass(frozen=True, slots=True)
class _MachineNode:
    position: Position
    orientation: Orientation

def _forward(position: Position, orientation: Orientation) -> Position:
    direction = ORIENTATION_TO_DIRECTION[orientation]
    delta_ligne, delta_col = DIRECTION_VECTORS[direction]
    return position.moved(delta_ligne, delta_col)

def _move_passable(state: GameState, machine: MachineState, current: Position, target: Position, *, ignore_other_machines: bool=False) -> bool:
    if not state.game_map.in_bounds(target):
        return False
    if target in state.game_map.rocks:
        return False
    if Rules.machine_elevation_reason(state, current, target) is not None:
        return False
    delta_ligne = target.row - current.row
    delta_col = target.col - current.col
    orientation = None
    for direction, vector in DIRECTION_VECTORS.items():
        if vector == (delta_ligne, delta_col):
            orientation = DIRECTION_TO_ORIENTATION[direction]
            break
    if orientation is None:
        return False
    if not ignore_other_machines and Rules.machine_lookahead_reason(
        state,
        machine,
        position=current,
        orientation=orientation,
        check_heroes=False,
    ) is not None:
        return False
    if target in state.chests:
        return False
    if machine.kind == MachineKind.EXCAVATOR and target in state.trees:
        return False
    if machine.kind == MachineKind.GRAPPLER and target in state.holes:
        return False
    return True

def _reconstruct(parent: dict[_MachineNode, tuple[_MachineNode, tuple[HeroAction, ...], int]], start: _MachineNode, goal: _MachineNode) -> tuple[list[HeroAction], int]:
    blocs: list[tuple[HeroAction, ...]] = []
    batterie = 0
    curseur = goal
    while curseur != start:
        precedent, actions, batterie_transition = parent[curseur]
        blocs.append(actions)
        batterie += batterie_transition
        curseur = precedent
    blocs.reverse()
    aplati: list[HeroAction] = []
    for bloc in blocs:
        aplati.extend(bloc)
    return (aplati, batterie)

def plan_machine_to_obstacle(state: GameState, machine: MachineState, target: Position, *, max_expansions: int=100000, ignore_other_machines: bool=False) -> MachineControlPlan | None:
    if machine.kind == MachineKind.EXCAVATOR:
        if target not in state.holes:
            return None
    elif target not in state.trees:
        return None
    depart = _MachineNode(machine.position, machine.orientation)
    if machine.kind == MachineKind.GRAPPLER and machine.position == target:
        return MachineControlPlan(actions=(HeroAction.WAIT,), target=target, ticks=1, battery_cost=0)
    serie = count()
    tas: list[tuple[int, int, int, int, _MachineNode]] = [(0, 0, 0, next(serie), depart)]
    meilleur: dict[_MachineNode, tuple[int, int, int]] = {depart: (0, 0, 0)}
    precedents: dict[_MachineNode, tuple[_MachineNode, tuple[HeroAction, ...], int]] = {}
    explorations = 0
    while tas and explorations < max_expansions:
        unites, ticks, batterie, _serie, noeud = heappop(tas)
        if meilleur.get(noeud) != (unites, ticks, batterie):
            continue
        if machine.kind == MachineKind.EXCAVATOR and _forward(noeud.position, noeud.orientation) == target:
            actions, batterie_utilisee = _reconstruct(precedents, depart, noeud)
            actions.append(HeroAction.HACK_FILL)
            return MachineControlPlan(actions=tuple(actions), target=target, ticks=len(actions), battery_cost=batterie_utilisee + 1)
        if machine.kind == MachineKind.GRAPPLER and noeud.position == target:
            actions, batterie_utilisee = _reconstruct(precedents, depart, noeud)
            return MachineControlPlan(actions=tuple(actions), target=target, ticks=len(actions), battery_cost=batterie_utilisee)
        explorations += 1
        for action, orientation in ((HeroAction.HACK_CW, CLOCKWISE[noeud.orientation]), (HeroAction.HACK_CCW, COUNTER_CLOCKWISE[noeud.orientation])):
            suivant = _MachineNode(noeud.position, orientation)
            nouveaux_ticks = ticks + 1
            nouvelle_batterie = batterie + 1
            nouvelles_unites = score_cost_units(nouveaux_ticks, 0, nouvelle_batterie)
            enregistrement = (nouvelles_unites, nouveaux_ticks, nouvelle_batterie)
            if meilleur.get(suivant) is not None and meilleur[suivant] <= enregistrement:
                continue
            meilleur[suivant] = enregistrement
            precedents[suivant] = (noeud, (action,), 1)
            heappush(tas, (nouvelles_unites, nouveaux_ticks, nouvelle_batterie, next(serie), suivant))
        devant = _forward(noeud.position, noeud.orientation)
        if _move_passable(state, machine, noeud.position, devant, ignore_other_machines=ignore_other_machines):
            entre_arbre = machine.kind == MachineKind.GRAPPLER and devant in state.trees
            bloc_action = (HeroAction.HACK_MOVE, HeroAction.WAIT, HeroAction.WAIT) if entre_arbre else (HeroAction.HACK_MOVE, HeroAction.WAIT)
            suivant = _MachineNode(devant, noeud.orientation)
            nouveaux_ticks = ticks + len(bloc_action)
            nouvelle_batterie = batterie + 1
            nouvelles_unites = score_cost_units(nouveaux_ticks, 0, nouvelle_batterie)
            enregistrement = (nouvelles_unites, nouveaux_ticks, nouvelle_batterie)
            if meilleur.get(suivant) is None or enregistrement < meilleur[suivant]:
                meilleur[suivant] = enregistrement
                precedents[suivant] = (noeud, bloc_action, 1)
                heappush(tas, (nouvelles_unites, nouveaux_ticks, nouvelle_batterie, next(serie), suivant))
    return None

def plan_machine_to_position(state: GameState, machine: MachineState, target: Position, *, max_expansions: int=100000, ignore_other_machines: bool=False) -> MachineControlPlan | None:
    if not state.game_map.in_bounds(target):
        return None
    if target in state.game_map.rocks or target in state.chests:
        return None
    if machine.kind == MachineKind.EXCAVATOR and target in state.trees:
        return None
    if machine.kind == MachineKind.GRAPPLER and target in state.holes:
        return None
    if not ignore_other_machines and any((autre.id != machine.id and autre.position == target for autre in state.machines.values())):
        return None
    depart = _MachineNode(machine.position, machine.orientation)
    if depart.position == target:
        return MachineControlPlan(actions=(), target=target, ticks=0, battery_cost=0)
    serie = count()
    tas: list[tuple[int, int, int, int, _MachineNode]] = [(0, 0, 0, next(serie), depart)]
    meilleur: dict[_MachineNode, tuple[int, int, int]] = {depart: (0, 0, 0)}
    precedents: dict[_MachineNode, tuple[_MachineNode, tuple[HeroAction, ...], int]] = {}
    explorations = 0
    while tas and explorations < max_expansions:
        unites, ticks, batterie, _serie, noeud = heappop(tas)
        if meilleur.get(noeud) != (unites, ticks, batterie):
            continue
        if noeud.position == target:
            actions, batterie_utilisee = _reconstruct(precedents, depart, noeud)
            return MachineControlPlan(actions=tuple(actions), target=target, ticks=len(actions), battery_cost=batterie_utilisee)
        explorations += 1
        for action, orientation in ((HeroAction.HACK_CW, CLOCKWISE[noeud.orientation]), (HeroAction.HACK_CCW, COUNTER_CLOCKWISE[noeud.orientation])):
            suivant = _MachineNode(noeud.position, orientation)
            nouveaux_ticks = ticks + 1
            nouvelle_batterie = batterie + 1
            nouvelles_unites = score_cost_units(nouveaux_ticks, 0, nouvelle_batterie)
            enregistrement = (nouvelles_unites, nouveaux_ticks, nouvelle_batterie)
            if meilleur.get(suivant) is not None and meilleur[suivant] <= enregistrement:
                continue
            meilleur[suivant] = enregistrement
            precedents[suivant] = (noeud, (action,), 1)
            heappush(tas, (nouvelles_unites, nouveaux_ticks, nouvelle_batterie, next(serie), suivant))
        devant = _forward(noeud.position, noeud.orientation)
        if _move_passable(state, machine, noeud.position, devant, ignore_other_machines=ignore_other_machines):
            entre_arbre = machine.kind == MachineKind.GRAPPLER and devant in state.trees
            bloc_action = (HeroAction.HACK_MOVE, HeroAction.WAIT, HeroAction.WAIT) if entre_arbre else (HeroAction.HACK_MOVE, HeroAction.WAIT)
            suivant = _MachineNode(devant, noeud.orientation)
            nouveaux_ticks = ticks + len(bloc_action)
            nouvelle_batterie = batterie + 1
            nouvelles_unites = score_cost_units(nouveaux_ticks, 0, nouvelle_batterie)
            enregistrement = (nouvelles_unites, nouveaux_ticks, nouvelle_batterie)
            if meilleur.get(suivant) is None or enregistrement < meilleur[suivant]:
                meilleur[suivant] = enregistrement
                precedents[suivant] = (noeud, bloc_action, 1)
                heappush(tas, (nouvelles_unites, nouveaux_ticks, nouvelle_batterie, next(serie), suivant))
    return None

