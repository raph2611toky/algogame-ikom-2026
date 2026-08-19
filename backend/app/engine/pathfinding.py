from __future__ import annotations
from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from app.domain.enums import DIRECTION_TO_MOVE_ACTION, DIRECTION_VECTORS, Direction, HeroAction, HeroId
from app.domain.models import GameState, Position
from app.engine.rules import Rules

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

def hero_neighbors(state: GameState, hero_id: HeroId, position: Position) -> list[PathStep]:
    resultat: list[PathStep] = []
    for direction in Direction:
        delta_ligne, delta_col = DIRECTION_VECTORS[direction]
        adjacent = position.moved(delta_ligne, delta_col)
        if not state.game_map.in_bounds(adjacent):
            continue
        if adjacent in state.game_map.rocks:
            continue
        if hero_id == HeroId.IKOTOFOSA and adjacent in state.holes:
            atterrissage = adjacent.moved(delta_ligne, delta_col)
            if not state.game_map.in_bounds(atterrissage):
                continue
            if atterrissage in state.game_map.rocks or atterrissage in state.trees or atterrissage in state.holes:
                continue
            if Rules.hero_elevation_reason(state, position, atterrissage) is not None:
                continue
            resultat.append(PathStep(DIRECTION_TO_MOVE_ACTION[direction], atterrissage, stamina_cost=10, special=True))
            continue
        if hero_id == HeroId.IMAHAKI and adjacent in state.trees:
            atterrissage = adjacent.moved(delta_ligne, delta_col)
            if not state.game_map.in_bounds(atterrissage):
                continue
            if atterrissage in state.game_map.rocks or atterrissage in state.trees or atterrissage in state.holes:
                continue
            if Rules.hero_elevation_reason(state, position, atterrissage) is not None:
                continue
            resultat.append(PathStep(DIRECTION_TO_MOVE_ACTION[direction], atterrissage, stamina_cost=10, special=True))
            continue
        if adjacent in state.trees or adjacent in state.holes:
            continue
        if Rules.hero_elevation_reason(state, position, adjacent) is not None:
            continue
        resultat.append(
            PathStep(
                DIRECTION_TO_MOVE_ACTION[direction],
                adjacent,
                stamina_cost=Rules.hero_walk_stamina_cost(state, position, adjacent),
            )
        )
    return resultat

def _heuristic(a: Position, b: Position) -> int:
    return (a.manhattan(b) + 1) // 2

def find_path(state: GameState, hero_id: HeroId, goal: Position, *, start: Position | None=None, max_expansions: int=100000) -> PathResult | None:
    if not state.game_map.in_bounds(goal):
        return None
    start = start or state.heroes[hero_id].position
    if start == goal:
        return PathResult(steps=(), total_stamina_cost=0)
    serie = count()
    tas: list[tuple[int, int, int, int, Position]] = []
    heappush(tas, (_heuristic(start, goal), 0, 0, next(serie), start))
    meilleur: dict[Position, tuple[int, int]] = {start: (0, 0)}
    precedents: dict[Position, tuple[Position, PathStep]] = {}
    explorations = 0
    while tas and explorations < max_expansions:
        _, ticks_g, cout_stamina, _, courant = heappop(tas)
        connu = meilleur.get(courant)
        if connu is None or (ticks_g, cout_stamina) != connu:
            continue
        if courant == goal:
            etapes_inversees: list[PathStep] = []
            curseur = courant
            while curseur != start:
                precedent, etape = precedents[curseur]
                etapes_inversees.append(etape)
                curseur = precedent
            etapes_inversees.reverse()
            return PathResult(tuple(etapes_inversees), cout_stamina)
        explorations += 1
        for etape in hero_neighbors(state, hero_id, courant):
            nouveau_g = ticks_g + 1
            nouvelle_stamina = cout_stamina + etape.stamina_cost
            ancien = meilleur.get(etape.destination)
            if ancien is not None and ancien <= (nouveau_g, nouvelle_stamina):
                continue
            meilleur[etape.destination] = (nouveau_g, nouvelle_stamina)
            precedents[etape.destination] = (courant, etape)
            heappush(tas, (nouveau_g + _heuristic(etape.destination, goal), nouveau_g, nouvelle_stamina, next(serie), etape.destination))
    return None
