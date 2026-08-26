from __future__ import annotations

from app.domain.enums import Direction, GuardMode, HeroId
from app.domain.models import GameState, Position
from app.engine.guard_ai.base import direction_towards, legal_directions
from app.engine.perception import propagate_beliefs


class HardGuardAI:
    """Poursuite A* et carte de croyance, sans lecture des héros invisibles.

    Cette IA exploite uniquement les observations déjà stockées par le système de
    perception : cible vue, dernière position connue et bruits. La distribution de
    croyance prédit où un héros perdu *pourrait* être, sans tricher.
    """

    def _visible_goal(self, state: GameState) -> Position | None:
        memory = state.guard.memory
        if not memory.visible:
            return None

        def utility(hero_id: HeroId) -> float:
            # Les attributs sont légitimes uniquement parce que le héros est vu.
            hero = state.heroes[hero_id]
            distance = max(1, state.guard.position.manhattan(hero.position))
            vulnerability = (100 - hero.hp) / 25
            objective_pressure = 2.0 if hero.position in state.game_map.exits else 0.0
            carrier_bonus = 3.0 if hero.carrying is not None else 0.0
            return 20 / distance + vulnerability + objective_pressure + carrier_bonus

        target = max(memory.visible, key=utility)
        memory.target = target
        return memory.last_known[target]

    def _belief_goal(self, state: GameState) -> Position | None:
        propagate_beliefs(state)
        memory = state.guard.memory
        candidates: list[tuple[float, Position]] = []
        for hero_id, distribution in memory.beliefs.items():
            if hero_id in memory.visible:
                continue
            for position, probability in distribution.items():
                distance = state.guard.position.manhattan(position)
                candidates.append((probability * 100 - distance * 0.45, position))
        return max(candidates, default=(0.0, None), key=lambda item: item[0])[1]

    def choose_direction(self, state: GameState) -> Direction | None:
        memory = state.guard.memory
        goal = self._visible_goal(state)
        if goal is None and memory.mode in {GuardMode.CHASE, GuardMode.SEARCH}:
            goal = self._belief_goal(state)
        if goal is None and memory.mode == GuardMode.INVESTIGATE:
            goal = memory.last_heard
        directed = direction_towards(state, goal)
        if directed is not None:
            return directed

        legal = legal_directions(state)
        if not legal:
            return None
        # Patrouille déterministe couvrante : droite, face, gauche, demi-tour.
        order = {
            Direction.UP: [Direction.RIGHT, Direction.UP, Direction.LEFT, Direction.DOWN],
            Direction.RIGHT: [Direction.DOWN, Direction.RIGHT, Direction.UP, Direction.LEFT],
            Direction.DOWN: [Direction.LEFT, Direction.DOWN, Direction.RIGHT, Direction.UP],
            Direction.LEFT: [Direction.UP, Direction.LEFT, Direction.DOWN, Direction.RIGHT],
        }[state.guard.orientation]
        return next((direction for direction in order if direction in legal), legal[0])
