from __future__ import annotations
from dataclasses import dataclass
from app.domain.enums import HeroAction, HeroId, MachineKind, PUSH_ACTIONS
from app.domain.models import GameState, Position
from app.engine.chest_planner import plan_chest_to_bush
from app.engine.pathfinding import PathResult
from app.engine.rules import Rules
from app.engine.score_pathfinding import find_score_path, score_cost_units
from app.engine.strategy import HeuristicStrategy

STONE_REWARD_UNITS = 100
CHEST_REWARD_UNITS = 600

@dataclass(slots=True)
class CachedPlan:
    actions: list[HeroAction]
    target_key: tuple[object, ...]
    description: str
    utility_units: int

@dataclass(frozen=True, slots=True)
class PlanCandidate:
    actions: tuple[HeroAction, ...]
    target_key: tuple[object, ...]
    description: str
    utility_units: int

class ScalableStrategy:

    def __init__(self, *, max_stones_per_hero: int=6, max_chest_pairs_per_hero: int=2, chest_expansions: int=4000, stuck_end_threshold: int=16, max_ticks: int=500) -> None:
        self.max_stones_per_hero = max_stones_per_hero
        self.max_chest_pairs_per_hero = max_chest_pairs_per_hero
        self.chest_expansions = chest_expansions
        self.stuck_end_threshold = stuck_end_threshold
        self.max_ticks = max_ticks
        self.stuck_ticks = 0
        self.last_decisions: dict[str, str] = {}
        self._plans: dict[HeroId, CachedPlan] = {}
        self._machine_helper = HeuristicStrategy(max_stones_per_hero=2, max_chest_pairs_per_hero=1, stuck_end_threshold=stuck_end_threshold)

    def should_end(self, state: GameState) -> bool:
        if state.objectives_finished or state.remaining_time <= 0:
            return True
        if state.elapsed >= min(state.game_map.time_limit, self.max_ticks):
            return True
        return self.stuck_ticks >= self.stuck_end_threshold

    @staticmethod
    def _value_path(path: PathResult, reward_units: int) -> int:
        return reward_units - score_cost_units(path.ticks, path.total_stamina_cost)

    def _stone_candidates(self, state: GameState, hero_id: HeroId) -> list[PlanCandidate]:
        heros = state.heroes[hero_id]
        pierres = sorted(state.stones, key=lambda p: (heros.position.manhattan(p), p.row, p.col))[:self.max_stones_per_hero]
        resultat: list[PlanCandidate] = []
        limite = max(2000, min(25000, state.game_map.height * state.game_map.width * 3))
        for pierre in pierres:
            chemin = find_score_path(state, hero_id, pierre, max_expansions=limite)
            if chemin is None or not chemin.steps:
                continue
            valeur = self._value_path(chemin, STONE_REWARD_UNITS)
            if valeur <= 0:
                continue
            resultat.append(PlanCandidate(tuple(etape.action for etape in chemin.steps), ('stone', pierre.row, pierre.col), f'pierre ({pierre.row},{pierre.col})', valeur))
        return resultat

    def _machine_stone_candidates(self, state: GameState, hero_id: HeroId) -> list[PlanCandidate]:
        heros = state.heroes[hero_id]
        machines = [machine for machine in state.machines.values() if machine.carried_stones > 0]
        machines.sort(key=lambda m: (heros.position.manhattan(m.position), m.id))
        resultat: list[PlanCandidate] = []
        limite = max(2000, min(25000, state.game_map.height * state.game_map.width * 3))
        for machine in machines[:3]:
            chemin = find_score_path(state, hero_id, machine.position, max_expansions=limite)
            if chemin is None or not chemin.steps:
                continue
            valeur = self._value_path(chemin, machine.carried_stones * STONE_REWARD_UNITS)
            if valeur <= 0:
                continue
            resultat.append(PlanCandidate(tuple(etape.action for etape in chemin.steps), ('machine_stones', machine.id), f'pierres machine {machine.id}', valeur))
        return resultat

    def _chest_candidates(self, state: GameState, hero_id: HeroId) -> list[PlanCandidate]:
        if not state.chests or not state.game_map.bushes:
            return []
        heros = state.heroes[hero_id]
        paires: list[tuple[int, Position, Position]] = []
        for coffre in state.chests:
            cachettes = sorted(state.game_map.bushes, key=lambda b: (coffre.manhattan(b), b.row, b.col))[:3]
            for cachette in cachettes:
                approximation = heros.position.manhattan(coffre) + coffre.manhattan(cachette)
                paires.append((approximation, coffre, cachette))
        paires.sort(key=lambda item: (item[0], item[1].row, item[1].col, item[2].row, item[2].col))
        resultat: list[PlanCandidate] = []
        for _distance, coffre, cachette in paires[:self.max_chest_pairs_per_hero]:
            plan = plan_chest_to_bush(state, hero_id, coffre, cachette, max_expansions=self.chest_expansions, optimize_for_score=True)
            if plan is None or not plan.actions:
                continue
            valeur = CHEST_REWARD_UNITS - plan.score_cost_units
            if valeur <= 0:
                continue
            resultat.append(PlanCandidate(plan.actions, ('chest', coffre.row, coffre.col, cachette.row, cachette.col), f'coffre ({coffre.row},{coffre.col}) -> ({cachette.row},{cachette.col})', valeur))
        return resultat

    def _compatible_machine_candidate(self, state: GameState, hero_id: HeroId) -> PlanCandidate | None:
        heros = state.heroes[hero_id]
        if heros.battery <= 0:
            return None
        type_voulu = MachineKind.EXCAVATOR if hero_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        machines = [machine for machine in state.machines.values() if machine.kind == type_voulu and not machine.is_hacked]
        machines.sort(key=lambda m: (heros.position.manhattan(m.position), m.id))
        limite = max(2000, min(25000, state.game_map.height * state.game_map.width * 3))
        for machine in machines[:4]:
            if machine.position == heros.position:
                return PlanCandidate((HeroAction.HACK,), ('machine', machine.id), f'hacker {machine.id}', 8)
            chemin = find_score_path(state, hero_id, machine.position, max_expansions=limite)
            if chemin is None or not chemin.steps:
                continue
            actions = tuple(etape.action for etape in chemin.steps)
            valeur = max(1, 16 - score_cost_units(chemin.ticks, chemin.total_stamina_cost))
            return PlanCandidate(actions, ('machine', machine.id), f'rejoindre {machine.id}', valeur)
        return None

    def _candidate_plans(self, state: GameState, hero_id: HeroId) -> list[PlanCandidate]:
        if len(state.stones) > 8:
            resultat = self._stone_candidates(state, hero_id)
            resultat.sort(key=lambda p: (-p.utility_units, p.description))
            if resultat:
                return resultat[:4]
        resultat = self._chest_candidates(state, hero_id)
        resultat.extend(self._stone_candidates(state, hero_id))
        if len(state.stones) <= 8:
            resultat.extend(self._machine_stone_candidates(state, hero_id))
        resultat.sort(key=lambda p: (-p.utility_units, p.description))
        if resultat:
            return resultat[:6]
        machine = self._compatible_machine_candidate(state, hero_id)
        return [machine] if machine is not None else []

    @staticmethod
    def _target_still_relevant(state: GameState, plan: CachedPlan) -> bool:
        if not plan.target_key:
            return False
        kind = plan.target_key[0]
        if kind == 'stone':
            return Position(int(plan.target_key[1]), int(plan.target_key[2])) in state.stones
        if kind == 'machine_stones':
            machine = state.machines.get(str(plan.target_key[1]))
            return machine is not None and machine.carried_stones > 0
        if kind == 'machine':
            return str(plan.target_key[1]) in state.machines
        if kind == 'chest':
            return bool(state.chests)
        return True

    def _cached_action(self, state: GameState, hero_id: HeroId) -> HeroAction | None:
        plan = self._plans.get(hero_id)
        if plan is None or not plan.actions or not self._target_still_relevant(state, plan):
            self._plans.pop(hero_id, None)
            return None
        heros = state.heroes[hero_id]
        action = plan.actions[0]
        if action in {HeroAction.UP, HeroAction.DOWN, HeroAction.LEFT, HeroAction.RIGHT}:
            mouvement = Rules.hero_move(state, heros, action)
            if not mouvement.valid:
                self._plans.pop(hero_id, None)
                return None
            if heros.stamina < mouvement.stamina_cost:
                return HeroAction.WAIT
        elif action in PUSH_ACTIONS:
            poussee = Rules.chest_push(state, heros, action)
            if not poussee.valid or not Rules.hero_chest_push_safe_this_tick(state, poussee):
                self._plans.pop(hero_id, None)
                return None
        plan.actions.pop(0)
        if not plan.actions:
            self._plans.pop(hero_id, None)
        return action

    def _choose_new_plan(self, state: GameState, hero_id: HeroId, reserved: set[tuple[object, ...]]) -> HeroAction:
        candidats = self._candidate_plans(state, hero_id)
        for candidat in candidats:
            if candidat.target_key in reserved:
                continue
            if not candidat.actions:
                continue
            plan = CachedPlan(list(candidat.actions), candidat.target_key, candidat.description, candidat.utility_units)
            self._plans[hero_id] = plan
            action = self._cached_action(state, hero_id)
            if action is not None:
                reserved.add(candidat.target_key)
                self.last_decisions[hero_id.value] = candidat.description
                return action
        self.last_decisions[hero_id.value] = 'attendre'
        return HeroAction.WAIT

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        decisions: dict[HeroId, HeroAction] = {}
        reserved: set[tuple[object, ...]] = set()
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            heros = state.heroes[hero_id]
            if heros.is_hacking:
                self._plans.pop(hero_id, None)
                candidat = self._machine_helper._control_machine(state, hero_id)
                action = self._machine_helper._make_executable(state, hero_id, candidat)
                decisions[hero_id] = action
                self.last_decisions[hero_id.value] = candidat.description
                if candidat.target_key is not None:
                    reserved.add(candidat.target_key)
                continue
            plan = self._plans.get(hero_id)
            if plan is not None and plan.target_key not in reserved:
                action = self._cached_action(state, hero_id)
                if action is not None:
                    decisions[hero_id] = action
                    reserved.add(plan.target_key)
                    self.last_decisions[hero_id.value] = plan.description
                    continue
            decisions[hero_id] = self._choose_new_plan(state, hero_id, reserved)
        if all(action == HeroAction.WAIT for action in decisions.values()) and not self._plans:
            self.stuck_ticks += 1
        else:
            self.stuck_ticks = 0
        return decisions
