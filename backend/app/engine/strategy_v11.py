from __future__ import annotations

from app.domain.enums import HeroAction, HeroId
from app.domain.models import GameState, Position
from app.engine.score_pathfinding import find_score_path
from app.engine.strategy_v10 import OpportunityCommittedPortfolioStrategy


class StrictPriorityPortfolioStrategy(OpportunityCommittedPortfolioStrategy):
    """portfolio_v11: v10 intact + discipline de priorite des pierres.

    Le coeur des coffres, opportunites, machines, relais et protections est celui
    de v10. La seule contrainte ajoutee est la suivante tant qu'un coffre reste:
    une action secondaire de collecte n'est acceptee que si la pierre (ou la
    machine qui la transporte) se trouve dans un rayon Manhattan <=3 d'au moins
    un coffre restant. Les pierres lointaines attendent la phase finale.
    """

    LOCAL_STONE_RADIUS = 3
    LOCAL_STONE_MAX_PATH_TICKS = 6

    def _priority_local_stone_action(
        self,
        state: GameState,
        hero_id: HeroId,
        *,
        reserved: set[tuple[object, ...]] | None = None,
    ) -> tuple[HeroAction, tuple[object, ...] | None, str]:
        reserved = reserved or set()
        if not state.chests:
            return self._best_stone_action_for_hero(state, hero_id, reserved=reserved)

        hero = state.heroes[hero_id]
        targets: list[tuple[int, Position, tuple[object, ...], str]] = []
        for stone in state.stones:
            chest_distance = min(stone.manhattan(chest) for chest in state.chests)
            if chest_distance <= self.LOCAL_STONE_RADIUS:
                targets.append((chest_distance, stone, ("stone", stone.row, stone.col), f"collecter pierre ({stone.row},{stone.col})"))
        for machine in state.machines.values():
            if machine.carried_stones <= 0:
                continue
            chest_distance = min(machine.position.manhattan(chest) for chest in state.chests)
            if chest_distance <= self.LOCAL_STONE_RADIUS:
                targets.append((chest_distance, machine.position, ("machine_stones", machine.id), f"recuperer {machine.carried_stones} pierre(s) sur {machine.id}"))

        targets.sort(key=lambda item: (item[0], hero.position.manhattan(item[1]), item[1].row, item[1].col, str(item[2])))
        for _chest_distance, target, key, desc in targets[:6]:
            if key in reserved:
                continue
            path = find_score_path(state, hero_id, target, max_expansions=8000)
            if path is None or not path.steps or path.ticks > self.LOCAL_STONE_MAX_PATH_TICKS:
                continue
            action = self._validate_hero_action(state, hero_id, path.steps[0].action)
            if action == HeroAction.WAIT and path.steps[0].action != HeroAction.WAIT:
                return HeroAction.WAIT, key, f"recharger avant pierre locale: {desc}"
            return action, key, f"pierre proche d'un coffre: {desc}"
        return HeroAction.WAIT, None, "pierres lointaines differees; priorite aux coffres"

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        decisions = super().next_actions(state)
        if not state.chests:
            return decisions

        reserved: set[tuple[object, ...]] = set()
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            desc = self.last_decisions.get(hero_id.value, "")
            if "pierre" not in desc.lower():
                continue
            action, key, local_desc = self._priority_local_stone_action(state, hero_id, reserved=reserved)
            decisions[hero_id] = action if key is not None else HeroAction.WAIT
            if key is not None:
                reserved.add(key)
            self.last_decisions[hero_id.value] = local_desc
        return decisions
