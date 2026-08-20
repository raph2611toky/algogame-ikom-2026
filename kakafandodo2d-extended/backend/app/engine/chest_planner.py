from __future__ import annotations
from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from app.domain.enums import DIRECTION_TO_PUSH_ACTION, DIRECTION_VECTORS, Direction, HeroAction, HeroId
from app.domain.models import GameState, Position
from app.engine.pathfinding import hero_neighbors
from app.engine.rules import Rules
from app.engine.score_pathfinding import score_cost_units

@dataclass(frozen=True, slots=True)
class ChestPlan:
    actions: tuple[HeroAction, ...]
    stamina_cost: int
    chest_start: Position
    bush: Position

    @property
    def ticks(self) -> int:
        return len(self.actions)

    @property
    def score_cost_units(self) -> int:
        return score_cost_units(self.ticks, self.stamina_cost)

@dataclass(frozen=True, slots=True)
class _Node:
    hero: Position
    chest: Position

def _ticks_heuristic(chest: Position, bush: Position) -> int:
    return chest.manhattan(bush)

def _score_heuristic_units(chest: Position, bush: Position) -> int:
    return 7 * chest.manhattan(bush)

def plan_chest_to_bush(state: GameState, hero_id: HeroId, chest: Position, bush: Position, *, max_expansions: int=50000, optimize_for_score: bool=False, avoid_machine_push_destinations: bool=False) -> ChestPlan | None:
    if chest not in state.chests or bush not in state.game_map.bushes:
        return None
    cellules = state.game_map.height * state.game_map.width
    if cellules > 2500:
        max_expansions = min(max_expansions, 5000)
    elif cellules > 1000:
        max_expansions = min(max_expansions, 15000)
    depart = _Node(state.heroes[hero_id].position, chest)
    serie = count()
    tas: list[tuple[int, int, int, int, int, _Node]] = []
    depart_heros = _score_heuristic_units(chest, bush) if optimize_for_score else _ticks_heuristic(chest, bush)
    heappush(tas, (depart_heros, 0, 0, 0, next(serie), depart))
    meilleur: dict[_Node, tuple[int, int, int]] = {depart: (0, 0, 0)}
    precedents: dict[_Node, tuple[_Node, HeroAction, int]] = {}
    autres_coffres = set(state.chests)
    autres_coffres.discard(chest)
    explorations = 0
    noeud_but: _Node | None = None
    action_but: HeroAction | None = None
    stamina_but = 0

    def primary(ticks: int, stamina: int) -> int:
        return score_cost_units(ticks, stamina) if optimize_for_score else ticks
    while tas and explorations < max_expansions:
        _priorite, cout_principal, ticks, stamina, _serie, noeud = heappop(tas)
        if meilleur.get(noeud) != (cout_principal, ticks, stamina):
            continue
        explorations += 1
        for etape in hero_neighbors(state, hero_id, noeud.hero):
            noeud_suivant = _Node(etape.destination, noeud.chest)
            nouveaux_ticks = ticks + 1
            nouvelle_stamina = stamina + etape.stamina_cost
            nouvelle_position = primary(nouveaux_ticks, nouvelle_stamina)
            enregistrement = (nouvelle_position, nouveaux_ticks, nouvelle_stamina)
            if meilleur.get(noeud_suivant) is not None and meilleur[noeud_suivant] <= enregistrement:
                continue
            meilleur[noeud_suivant] = enregistrement
            precedents[noeud_suivant] = (noeud, etape.action, etape.stamina_cost)
            heuristique = _score_heuristic_units(noeud.chest, bush) if optimize_for_score else _ticks_heuristic(noeud.chest, bush)
            heappush(tas, (nouvelle_position + heuristique, nouvelle_position, nouveaux_ticks, nouvelle_stamina, next(serie), noeud_suivant))
        for direction in Direction:
            delta_ligne, delta_col = DIRECTION_VECTORS[direction]
            if noeud.hero.moved(delta_ligne, delta_col) != noeud.chest:
                continue
            coffre_arrivee = noeud.chest.moved(delta_ligne, delta_col)
            if not state.game_map.in_bounds(coffre_arrivee):
                continue
            if coffre_arrivee in state.game_map.rocks or coffre_arrivee in state.trees:
                continue
            if coffre_arrivee in autres_coffres:
                continue
            # A chest may be pushed into a hole by the rules, but a direct plan
            # must never intentionally lose it.  FAQ exception: when DIG happened
            # on a bush, the bush remains a valid hiding spot even though the same
            # cell is also present in state.holes.
            if coffre_arrivee in state.holes and coffre_arrivee not in state.game_map.bushes:
                continue
            # Optional strict mode for predictive strategies. Legacy planners keep
            # their existing behavior because a currently occupied machine cell may
            # be vacated before the planned PUSH executes. V13 opts into the strict
            # mode when it wants a collision-free immediate route.
            if avoid_machine_push_destinations and state.machine_at(coffre_arrivee) is not None:
                continue
            if Rules.hero_elevation_reason(state, noeud.hero, noeud.chest) is not None:
                continue
            if Rules.hero_chest_elevation_reason(state, noeud.chest, coffre_arrivee) is not None:
                continue
            # A direct chest plan must never choose a cliff-destruction push.
            if Rules.chest_destroyed_by_cliff(state, noeud.chest, coffre_arrivee):
                continue
            action = DIRECTION_TO_PUSH_ACTION[direction]
            if coffre_arrivee == bush:
                noeud_but = noeud
                action_but = action
                stamina_but = stamina + 5
                tas.clear()
                break
            noeud_suivant = _Node(noeud.chest, coffre_arrivee)
            nouveaux_ticks = ticks + 1
            nouvelle_stamina = stamina + 5
            nouvelle_position = primary(nouveaux_ticks, nouvelle_stamina)
            enregistrement = (nouvelle_position, nouveaux_ticks, nouvelle_stamina)
            if meilleur.get(noeud_suivant) is not None and meilleur[noeud_suivant] <= enregistrement:
                continue
            meilleur[noeud_suivant] = enregistrement
            precedents[noeud_suivant] = (noeud, action, 5)
            heuristique = _score_heuristic_units(coffre_arrivee, bush) if optimize_for_score else _ticks_heuristic(coffre_arrivee, bush)
            heappush(tas, (nouvelle_position + heuristique, nouvelle_position, nouveaux_ticks, nouvelle_stamina, next(serie), noeud_suivant))
        if noeud_but is not None:
            break
    if noeud_but is None or action_but is None:
        return None
    actions_inversees: list[HeroAction] = [action_but]
    curseur = noeud_but
    while curseur != depart:
        precedent, action, _cout = precedents[curseur]
        actions_inversees.append(action)
        curseur = precedent
    actions_inversees.reverse()
    return ChestPlan(tuple(actions_inversees), stamina_but, chest, bush)
