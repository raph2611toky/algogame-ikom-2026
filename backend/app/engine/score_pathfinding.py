from __future__ import annotations
from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from app.domain.enums import HeroId
from app.domain.models import GameState, Position
from app.engine.pathfinding import PathResult, PathStep, hero_neighbors
TIME_COST_UNITS_PER_TICK = 2
RESOURCE_COST_UNITS = 1

def score_cost_units(ticks: int, stamina_cost: int, battery_cost: int=0) -> int:
    return TIME_COST_UNITS_PER_TICK * ticks + stamina_cost + battery_cost

def _heuristic_units(a: Position, b: Position) -> int:
    ticks_minimum = (a.manhattan(b) + 1) // 2
    return TIME_COST_UNITS_PER_TICK * ticks_minimum

def find_score_path(state: GameState, hero_id: HeroId, goal: Position, *, start: Position | None=None, max_expansions: int=150000) -> PathResult | None:
    if not state.game_map.in_bounds(goal):
        return None
    start = start or state.heroes[hero_id].position
    if start == goal:
        return PathResult(steps=(), total_stamina_cost=0)
    serie = count()
    tas: list[tuple[int, int, int, int, int, Position]] = []
    heappush(tas, (_heuristic_units(start, goal), 0, 0, 0, next(serie), start))
    meilleur: dict[Position, tuple[int, int, int]] = {start: (0, 0, 0)}
    precedents: dict[Position, tuple[Position, PathStep]] = {}
    explorations = 0
    while tas and explorations < max_expansions:
        _f, unites_g, ticks, stamina, _serie, courant = heappop(tas)
        if meilleur.get(courant) != (unites_g, ticks, stamina):
            continue
        if courant == goal:
            etapes_inversees: list[PathStep] = []
            curseur = courant
            while curseur != start:
                precedent, etape = precedents[curseur]
                etapes_inversees.append(etape)
                curseur = precedent
            etapes_inversees.reverse()
            return PathResult(tuple(etapes_inversees), stamina)
        explorations += 1
        for etape in hero_neighbors(state, hero_id, courant):
            nouveaux_ticks = ticks + 1
            nouvelle_stamina = stamina + etape.stamina_cost
            nouvelles_unites = score_cost_units(nouveaux_ticks, nouvelle_stamina)
            enregistrement = (nouvelles_unites, nouveaux_ticks, nouvelle_stamina)
            ancien = meilleur.get(etape.destination)
            if ancien is not None and ancien <= enregistrement:
                continue
            meilleur[etape.destination] = enregistrement
            precedents[etape.destination] = (courant, etape)
            heappush(tas, (nouvelles_unites + _heuristic_units(etape.destination, goal), nouvelles_unites, nouveaux_ticks, nouvelle_stamina, next(serie), etape.destination))
    return None
