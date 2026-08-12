from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from app.domain.enums import CLOCKWISE, COUNTER_CLOCKWISE, DIRECTION_TO_ORIENTATION, DIRECTION_VECTORS, ORIENTATION_TO_DIRECTION, Direction, HeroAction, HeroId, MachineKind, Orientation, PUSH_ACTIONS
from app.domain.models import GameState, MachineState, Position
from app.engine.chest_planner import plan_chest_to_bush
from app.engine.machine_pathfinding import direction_between, find_machine_path
from app.engine.pathfinding import PathStep, find_path, hero_neighbors
from app.engine.rules import Rules

@dataclass(frozen=True, slots=True)
class Candidate:
    action: HeroAction
    utility: float
    target_key: tuple[object, ...] | None
    description: str
    required_stamina: int = 0

class HeuristicStrategy:

    def __init__(self, *, max_stones_per_hero: int=8, max_chest_pairs_per_hero: int=6, stuck_end_threshold: int=8) -> None:
        self.max_stones_per_hero = max_stones_per_hero
        self.max_chest_pairs_per_hero = max_chest_pairs_per_hero
        self.stuck_end_threshold = stuck_end_threshold
        self.stuck_ticks = 0
        self.last_decisions: dict[str, str] = {}

    def should_end(self, state: GameState) -> bool:
        if state.objectives_finished:
            return True
        if state.remaining_time <= 0:
            return True
        return self.stuck_ticks >= self.stuck_end_threshold

    @staticmethod
    def _utility(reward: int, ticks: int, stamina_cost: int, battery_cost: int=0) -> float:
        return reward - 0.5 * ticks - 0.25 * stamina_cost - 0.25 * battery_cost

    def _stone_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        heros = state.heroes[hero_id]
        pierres = sorted(state.stones, key=lambda p: (heros.position.manhattan(p), p.row, p.col))
        candidats: list[Candidate] = []
        for pierre in pierres[:self.max_stones_per_hero]:
            chemin = find_path(state, hero_id, pierre)
            if not chemin or not chemin.steps:
                continue
            premier = chemin.steps[0]
            if chemin.ticks > state.remaining_time:
                continue
            candidats.append(Candidate(action=premier.action, utility=self._utility(25, chemin.ticks, chemin.total_stamina_cost), target_key=('stone', pierre.row, pierre.col), description=f'pierre ({pierre.row},{pierre.col}) via A*', required_stamina=premier.stamina_cost))
        return candidats

    def _chest_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        heros = state.heroes[hero_id]
        if not state.chests or not state.game_map.bushes:
            return []
        paires: list[tuple[int, Position, Position]] = []
        for coffre in state.chests:
            for cachette in state.game_map.bushes:
                approximation = heros.position.manhattan(coffre) + coffre.manhattan(cachette)
                paires.append((approximation, coffre, cachette))
        paires.sort(key=lambda item: (item[0], item[1].row, item[1].col, item[2].row, item[2].col))
        candidats: list[Candidate] = []
        for _approx, coffre, cachette in paires[:self.max_chest_pairs_per_hero]:
            plan = plan_chest_to_bush(state, hero_id, coffre, cachette)
            if not plan or not plan.actions or plan.ticks > state.remaining_time:
                continue
            premier = plan.actions[0]
            if premier in PUSH_ACTIONS:
                requis = 5
            else:
                mouvement = Rules.hero_move(state, heros, premier)
                requis = mouvement.stamina_cost if mouvement.valid else 1000
            candidats.append(Candidate(action=premier, utility=self._utility(150, plan.ticks, plan.stamina_cost), target_key=('chest', coffre.row, coffre.col), description=f'coffre ({coffre.row},{coffre.col}) -> cachette ({cachette.row},{cachette.col})', required_stamina=requis))
        return candidats

    def _machine_stone_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        heros = state.heroes[hero_id]
        candidats: list[Candidate] = []
        for machine in sorted(state.machines.values(), key=lambda m: m.id):
            if machine.carried_stones <= 0:
                continue
            chemin = find_path(state, hero_id, machine.position)
            if not chemin or not chemin.steps:
                continue
            premier = chemin.steps[0]
            recompense = machine.carried_stones * 25
            candidats.append(Candidate(action=premier.action, utility=self._utility(recompense, chemin.ticks, chemin.total_stamina_cost), target_key=('machine_stones', machine.id), description=f'récupérer {machine.carried_stones} pierre(s) sur {machine.id}', required_stamina=premier.stamina_cost))
        return candidats

    def _compatible_machine_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        heros = state.heroes[hero_id]
        type_voulu = MachineKind.EXCAVATOR if hero_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        relevant_obstacles = state.holes if hero_id == HeroId.IKOTOFOSA else state.trees
        if not relevant_obstacles or heros.battery <= 0:
            return []
        candidats: list[Candidate] = []
        for machine in sorted(state.machines.values(), key=lambda m: m.id):
            if machine.kind != type_voulu or machine.is_hacked:
                continue
            if machine.position == heros.position:
                candidats.append(Candidate(action=HeroAction.HACK, utility=4.0, target_key=('machine', machine.id), description=f'prendre contrôle de {machine.id}', required_stamina=0))
                continue
            chemin = find_path(state, hero_id, machine.position)
            if not chemin or not chemin.steps:
                continue
            premier = chemin.steps[0]
            candidats.append(Candidate(action=premier.action, utility=max(0.5, 4.0 - 0.25 * chemin.ticks), target_key=('machine', machine.id), description=f'rejoindre {machine.id}', required_stamina=premier.stamina_cost))
        return candidats

    @staticmethod
    def _rotation_action(current: Orientation, desired: Direction) -> HeroAction:
        cible = DIRECTION_TO_ORIENTATION[desired]
        if current == cible:
            return HeroAction.HACK_MOVE
        cw = current
        ccw = current
        for distance in range(1, 4):
            cw = CLOCKWISE[cw]
            if cw == cible:
                distance_horaire = distance
                break
        else:
            distance_horaire = 4
        for distance in range(1, 4):
            ccw = COUNTER_CLOCKWISE[ccw]
            if ccw == cible:
                distance_antihoraire = distance
                break
        else:
            distance_antihoraire = 4
        return HeroAction.HACK_CW if distance_horaire <= distance_antihoraire else HeroAction.HACK_CCW

    def _exit_machine(self, state: GameState, hero_id: HeroId) -> HeroAction:
        heros = state.heroes[hero_id]
        for etape in hero_neighbors(state, hero_id, heros.position):
            if heros.stamina >= etape.stamina_cost:
                return etape.action
        return HeroAction.WAIT

    def _control_machine(self, state: GameState, hero_id: HeroId) -> Candidate:
        heros = state.heroes[hero_id]
        machine = state.machines[heros.hacking_machine_id]
        if heros.battery <= 0:
            return Candidate(self._exit_machine(state, hero_id), 0.1, None, 'quitter machine: batterie vide')
        if machine.pending_move:
            return Candidate(HeroAction.WAIT, 3.0, ('machine', machine.id), 'attendre HACK_MOVE')
        if machine.kind == MachineKind.GRAPPLER and machine.position in state.trees:
            return Candidate(HeroAction.WAIT, 3.0, ('machine', machine.id), 'laisser le Grappler couper')
        if machine.kind == MachineKind.EXCAVATOR:
            devant = Rules.machine_forward(machine)
            if devant in state.holes:
                return Candidate(HeroAction.HACK_FILL, 8.0, ('hole', devant.row, devant.col), 'reboucher trou')
            if not state.holes:
                return Candidate(self._exit_machine(state, hero_id), 0.1, None, 'plus de trou utile')
            buts: set[Position] = set()
            trou_par_but: dict[Position, list[Position]] = {}
            for trou in state.holes:
                for delta_ligne, delta_col in DIRECTION_VECTORS.values():
                    point = trou.moved(-delta_ligne, -delta_col)
                    if not state.game_map.in_bounds(point):
                        continue
                    if point in state.game_map.rocks or point in state.trees:
                        continue
                    buts.add(point)
                    trou_par_but.setdefault(point, []).append(trou)
            chemin = find_machine_path(state, machine, buts)
            if chemin:
                if len(chemin) == 1:
                    trou = min(trou_par_but[machine.position], key=lambda p: (p.row, p.col))
                    delta_ligne = trou.row - machine.position.row
                    delta_col = trou.col - machine.position.col
                    souhaite = next((distance_tmp for distance_tmp, valeur_tmp in DIRECTION_VECTORS.items() if valeur_tmp == (delta_ligne, delta_col)))
                    action = self._rotation_action(machine.orientation, souhaite)
                    return Candidate(action, 5.0, ('hole', trou.row, trou.col), 'orienter Excavator vers trou')
                souhaite = direction_between(chemin[0], chemin[1])
                action = self._rotation_action(machine.orientation, souhaite)
                if action == HeroAction.HACK_MOVE and (not Rules.machine_forward_clear(state, machine)):
                    return Candidate(HeroAction.WAIT, 0.2, ('machine', machine.id), 'chemin machine momentanément bloqué')
                return Candidate(action, 4.0, ('machine', machine.id), 'déplacer Excavator vers trou')
        else:
            if not state.trees:
                return Candidate(self._exit_machine(state, hero_id), 0.1, None, "plus d'arbre utile")
            chemin = find_machine_path(state, machine, set(state.trees))
            if chemin:
                if len(chemin) == 1:
                    return Candidate(HeroAction.WAIT, 5.0, ('tree', machine.position.row, machine.position.col), 'couper arbre')
                souhaite = direction_between(chemin[0], chemin[1])
                action = self._rotation_action(machine.orientation, souhaite)
                if action == HeroAction.HACK_MOVE and (not Rules.machine_forward_clear(state, machine)):
                    return Candidate(HeroAction.WAIT, 0.2, ('machine', machine.id), 'chemin machine momentanément bloqué')
                return Candidate(action, 4.0, ('machine', machine.id), 'déplacer Grappler vers arbre')
        return Candidate(self._exit_machine(state, hero_id), 0.1, None, 'quitter machine sans objectif')

    def _all_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        heros = state.heroes[hero_id]
        if heros.is_hacking:
            return [self._control_machine(state, hero_id)]
        candidats_recompense = self._chest_candidates(state, hero_id) + self._stone_candidates(state, hero_id) + self._machine_stone_candidates(state, hero_id)
        candidats_recompense.sort(key=lambda c: (-c.utility, c.description))
        if candidats_recompense:
            return candidats_recompense[:8] + self._compatible_machine_candidates(state, hero_id)[:2]
        return self._compatible_machine_candidates(state, hero_id)[:4]

    def _make_executable(self, state: GameState, hero_id: HeroId, candidate: Candidate) -> HeroAction:
        heros = state.heroes[hero_id]
        if candidate.required_stamina > heros.stamina:
            return HeroAction.WAIT
        if candidate.action in {HeroAction.UP, HeroAction.DOWN, HeroAction.LEFT, HeroAction.RIGHT}:
            mouvement = Rules.hero_move(state, heros, candidate.action)
            if not mouvement.valid:
                return HeroAction.WAIT
        elif candidate.action in PUSH_ACTIONS:
            if not Rules.chest_push(state, heros, candidate.action).valid:
                return HeroAction.WAIT
        return candidate.action

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        reservoirs: dict[HeroId, list[Candidate]] = {}
        for id_heros in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            candidats = self._all_candidates(state, id_heros)
            candidats.append(Candidate(HeroAction.WAIT, 0.0, None, 'attendre'))
            reservoirs[id_heros] = candidats
        meilleure_paire: tuple[Candidate, Candidate] | None = None
        meilleur_score = float('-inf')
        for candidat_f, candidat_m in product(reservoirs[HeroId.IKOTOFOSA], reservoirs[HeroId.IMAHAKI]):
            if candidat_f.target_key is not None and candidat_f.target_key == candidat_m.target_key:
                continue
            score = candidat_f.utility + candidat_m.utility
            if score > meilleur_score:
                meilleur_score = score
                meilleure_paire = (candidat_f, candidat_m)
        if meilleure_paire is None:
            meilleure_paire = (Candidate(HeroAction.WAIT, 0.0, None, 'attendre'), Candidate(HeroAction.WAIT, 0.0, None, 'attendre'))
        decisions = {HeroId.IKOTOFOSA: self._make_executable(state, HeroId.IKOTOFOSA, meilleure_paire[0]), HeroId.IMAHAKI: self._make_executable(state, HeroId.IMAHAKI, meilleure_paire[1])}
        self.last_decisions = {'F': meilleure_paire[0].description, 'M': meilleure_paire[1].description}
        a_un_but = any((candidat.target_key is not None or candidat.utility > 0 for candidat in meilleure_paire))
        if a_un_but:
            self.stuck_ticks = 0
        elif all((action == HeroAction.WAIT for action in decisions.values())):
            self.stuck_ticks += 1
        else:
            self.stuck_ticks = 0
        return decisions
