from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from itertools import combinations, product
from app.domain.enums import HeroAction, HeroId, MachineKind, PUSH_ACTIONS
from app.domain.models import GameState, Position
from app.engine.chest_planner import ChestPlan, plan_chest_to_bush
from app.engine.machine_planner import MachineControlPlan, plan_machine_to_obstacle, plan_machine_to_position
from app.engine.pathfinding import PathResult, hero_neighbors
from app.engine.rules import Rules
from app.engine.score_pathfinding import find_score_path, score_cost_units
STONE_REWARD_UNITS = 25 * 4
CHEST_REWARD_UNITS = 150 * 4
HACK_COMMAND_COST_UNITS = score_cost_units(1, 0, 1)

@dataclass(frozen=True, slots=True)
class Candidate:
    action: HeroAction
    utility_units: int
    target_key: tuple[object, ...] | None
    description: str
    required_stamina: int = 0

    @property
    def utility(self) -> float:
        return self.utility_units / 4.0

class AdaptiveScoreStrategy:

    def __init__(self, *, max_stones_per_hero: int=16, max_chest_pairs_per_hero: int=12, max_unlock_obstacles: int=20, unlock_pair_candidates: int=8, stuck_end_threshold: int=8) -> None:
        self.max_stones_per_hero = max_stones_per_hero
        self.max_chest_pairs_per_hero = max_chest_pairs_per_hero
        self.max_unlock_obstacles = max_unlock_obstacles
        self.unlock_pair_candidates = unlock_pair_candidates
        self.stuck_end_threshold = stuck_end_threshold
        self.stuck_ticks = 0
        self.last_decisions: dict[str, str] = {}
        self._unlock_cache_tick: int | None = None
        self._unlock_cache_state_id: int | None = None
        self._unlock_cache: dict[HeroId, dict[Position, int]] = {}
        self._threat_cache_tick: int | None = None
        self._threat_cache_state_id: int | None = None
        self._threat_cache: dict[str, tuple[int, int]] = {}
        self._potential_cache: dict[tuple[object, ...], int] = {}

    def should_end(self, state: GameState) -> bool:
        if state.objectives_finished or state.remaining_time <= 0:
            return True
        return self.stuck_ticks >= self.stuck_end_threshold

    @staticmethod
    def _adjusted_path_cost(state: GameState, hero_id: HeroId, *, ticks: int, stamina_cost: int) -> tuple[int, int] | None:
        heros = state.heroes[hero_id]
        deficit = max(0, stamina_cost - heros.stamina)
        ticks_recuperation = deficit * 2
        ticks_effectifs = ticks + ticks_recuperation
        if ticks_effectifs > state.remaining_time:
            return None
        perte_stamina_nette = min(stamina_cost, heros.stamina)
        return (ticks_effectifs, score_cost_units(ticks_effectifs, perte_stamina_nette))

    def _path_value_units(self, state: GameState, hero_id: HeroId, path: PathResult, reward_units: int) -> tuple[int, int] | None:
        ajuste = self._adjusted_path_cost(state, hero_id, ticks=path.ticks, stamina_cost=path.total_stamina_cost)
        if ajuste is None:
            return None
        ticks_effectifs, unites_cout = ajuste
        return (reward_units - unites_cout, ticks_effectifs)

    def _chest_value_units(self, state: GameState, hero_id: HeroId, plan: ChestPlan) -> tuple[int, int] | None:
        ajuste = self._adjusted_path_cost(state, hero_id, ticks=plan.ticks, stamina_cost=plan.stamina_cost)
        if ajuste is None:
            return None
        ticks_effectifs, unites_cout = ajuste
        return (CHEST_REWARD_UNITS - unites_cout, ticks_effectifs)

    def _stone_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        heros = state.heroes[hero_id]
        pierres = sorted(state.stones, key=lambda p: (heros.position.manhattan(p), p.row, p.col))
        resultat: list[Candidate] = []
        for pierre in pierres[:self.max_stones_per_hero]:
            chemin = find_score_path(state, hero_id, pierre)
            if not chemin or not chemin.steps:
                continue
            valorise = self._path_value_units(state, hero_id, chemin, STONE_REWARD_UNITS)
            if valorise is None:
                continue
            unites_valeur, _ticks_effectifs = valorise
            if unites_valeur <= 0:
                continue
            premier = chemin.steps[0]
            resultat.append(Candidate(action=premier.action, utility_units=unites_valeur, target_key=('stone', pierre.row, pierre.col), description=f'pierre ({pierre.row},{pierre.col}) - chemin score-aware', required_stamina=premier.stamina_cost))
        return resultat

    def _machine_stone_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        resultat: list[Candidate] = []
        for machine in sorted(state.machines.values(), key=lambda m: m.id):
            if machine.carried_stones <= 0:
                continue
            chemin = find_score_path(state, hero_id, machine.position)
            if not chemin or not chemin.steps:
                continue
            recompense = machine.carried_stones * STONE_REWARD_UNITS
            valorise = self._path_value_units(state, hero_id, chemin, recompense)
            if valorise is None:
                continue
            unites_valeur, _ticks_effectifs = valorise
            if unites_valeur <= 0:
                continue
            premier = chemin.steps[0]
            resultat.append(Candidate(action=premier.action, utility_units=unites_valeur, target_key=('machine_stones', machine.id), description=f'récupérer {machine.carried_stones} pierre(s) sur {machine.id}', required_stamina=premier.stamina_cost))
        return resultat

    def _chest_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        if not state.chests or not state.game_map.bushes:
            return []
        heros = state.heroes[hero_id]
        paires: list[tuple[int, Position, Position]] = []
        for coffre in state.chests:
            for cachette in state.game_map.bushes:
                approximation = heros.position.manhattan(coffre) + coffre.manhattan(cachette)
                paires.append((approximation, coffre, cachette))
        paires.sort(key=lambda item: (item[0], item[1].row, item[1].col, item[2].row, item[2].col))
        resultat: list[Candidate] = []
        for _approx, coffre, cachette in paires[:self.max_chest_pairs_per_hero]:
            plan = plan_chest_to_bush(state, hero_id, coffre, cachette, optimize_for_score=True)
            if not plan or not plan.actions:
                continue
            valorise = self._chest_value_units(state, hero_id, plan)
            if valorise is None:
                continue
            unites_valeur, _ticks_effectifs = valorise
            if unites_valeur <= 0:
                continue
            premier = plan.actions[0]
            if premier in PUSH_ACTIONS:
                requis = 5
            else:
                mouvement = Rules.hero_move(state, heros, premier)
                requis = mouvement.stamina_cost if mouvement.valid else 1000
            resultat.append(Candidate(action=premier, utility_units=unites_valeur, target_key=('chest', coffre.row, coffre.col), description=f'coffre ({coffre.row},{coffre.col}) -> cachette ({cachette.row},{cachette.col})', required_stamina=requis))
        return resultat

    def _direct_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        candidats = self._chest_candidates(state, hero_id) + self._stone_candidates(state, hero_id) + self._machine_stone_candidates(state, hero_id)
        candidats.sort(key=lambda c: (-c.utility_units, c.description))
        return candidats

    @staticmethod
    def _potential_signature(state: GameState) -> tuple[object, ...]:

        def pos_tuple(values):
            return tuple(sorted(((point.row, point.col) for point in values)))
        positions_heros = tuple(((id_heros.value, heros.position.row, heros.position.col, heros.stamina, heros.battery, heros.stones, heros.hacking_machine_id) for id_heros, heros in sorted(state.heroes.items(), key=lambda item: item[0].value)))
        machines = tuple(((machine.id, machine.kind.value, machine.position.row, machine.position.col, machine.orientation.value, machine.hacked_by.value if machine.hacked_by else None, machine.carried_stones, machine.pending_move, machine.auto_move_pending) for machine in sorted(state.machines.values(), key=lambda m: m.id)))
        return (state.elapsed, state.secured_chests, state.lost_chests, pos_tuple(state.stones), pos_tuple(state.chests), pos_tuple(state.trees), pos_tuple(state.holes), positions_heros, machines)

    def _direct_potential_units(self, state: GameState) -> int:
        signature = self._potential_signature(state)
        cache = self._potential_cache.get(signature)
        if cache is not None:
            return cache
        total = 0
        for pierre in state.stones:
            meilleur = 0
            for id_heros in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
                chemin = find_score_path(state, id_heros, pierre)
                if not chemin:
                    continue
                if not chemin.steps:
                    meilleur = max(meilleur, STONE_REWARD_UNITS)
                    continue
                valorise = self._path_value_units(state, id_heros, chemin, STONE_REWARD_UNITS)
                if valorise is not None:
                    meilleur = max(meilleur, valorise[0])
            total += max(0, meilleur)
        for coffre in state.chests:
            meilleur = 0
            for cachette in state.game_map.bushes:
                for id_heros in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
                    plan = plan_chest_to_bush(state, id_heros, coffre, cachette, optimize_for_score=True, max_expansions=30000)
                    if not plan:
                        continue
                    valorise = self._chest_value_units(state, id_heros, plan)
                    if valorise is not None:
                        meilleur = max(meilleur, valorise[0])
            total += max(0, meilleur)
        for machine in state.machines.values():
            if machine.carried_stones <= 0:
                continue
            recompense = machine.carried_stones * STONE_REWARD_UNITS
            meilleur = 0
            for id_heros in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
                chemin = find_score_path(state, id_heros, machine.position)
                if chemin is None:
                    continue
                if not chemin.steps:
                    meilleur = max(meilleur, recompense)
                    continue
                valorise = self._path_value_units(state, id_heros, chemin, recompense)
                if valorise is not None:
                    meilleur = max(meilleur, valorise[0])
            total += max(0, meilleur)
        self._potential_cache[signature] = total
        return total

    def _rank_obstacles(self, state: GameState, hero_id: HeroId) -> list[Position]:
        obstacles = state.holes if hero_id == HeroId.IKOTOFOSA else state.trees
        if not obstacles:
            return []
        type_voulu = MachineKind.EXCAVATOR if hero_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        positions_machines = [machine_locale.position for machine_locale in state.machines.values() if machine_locale.kind == type_voulu]
        if not positions_machines:
            return []
        objectifs = set(state.stones) | set(state.chests) | set(state.game_map.bushes)
        objectifs |= {machine_locale.position for machine_locale in state.machines.values() if machine_locale.carried_stones > 0}
        if not objectifs:
            objectifs = set(obstacles)

        def rank(pos: Position) -> tuple[int, int, int]:
            near_objective = min((pos.manhattan(o) for o in objectifs))
            near_machine = min((pos.manhattan(machine_locale) for machine_locale in positions_machines))
            return (near_objective + near_machine, pos.row, pos.col)
        return sorted(obstacles, key=rank)[:self.max_unlock_obstacles]

    def _machine_option_from_direct_gain(self, state: GameState, controller_id: HeroId, *, base_direct: int | None=None) -> int:
        heros = state.heroes[controller_id]
        if heros.battery <= 0:
            return 0
        type_voulu = MachineKind.EXCAVATOR if controller_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        obstacles = self._rank_obstacles(state, controller_id)
        if not obstacles:
            return 0
        base = self._direct_potential_units(state) if base_direct is None else base_direct
        meilleure_valeur = 0
        for obstacle in obstacles:
            hypothetique = deepcopy(state)
            if controller_id == HeroId.IKOTOFOSA:
                hypothetique.holes.discard(obstacle)
            else:
                hypothetique.trees.discard(obstacle)
            gain = self._direct_potential_units(hypothetique) - base
            if gain <= 0:
                continue
            for machine in state.machines.values():
                if machine.kind != type_voulu:
                    continue
                if machine.is_hacked and machine.hacked_by != controller_id:
                    continue
                plan = plan_machine_to_obstacle(state, machine, obstacle, ignore_other_machines=True)
                if plan is None:
                    continue
                if heros.is_hacking and heros.hacking_machine_id == machine.id:
                    batterie_totale = plan.battery_cost
                    cout_total = plan.score_cost_units
                    ticks_totaux = plan.ticks
                else:
                    if machine.is_hacked:
                        continue
                    approche = find_score_path(state, controller_id, machine.position)
                    if approche is None:
                        continue
                    ajuste = self._adjusted_path_cost(state, controller_id, ticks=approche.ticks, stamina_cost=approche.total_stamina_cost)
                    if ajuste is None:
                        continue
                    ticks_approche, cout_approche = ajuste
                    batterie_totale = 1 + plan.battery_cost
                    cout_total = cout_approche + HACK_COMMAND_COST_UNITS + plan.score_cost_units
                    ticks_totaux = ticks_approche + 1 + plan.ticks
                if batterie_totale > heros.battery or ticks_totaux > state.remaining_time:
                    continue
                meilleure_valeur = max(meilleure_valeur, gain - cout_total)
        return max(0, meilleure_valeur)

    def _compute_unlock_values(self, state: GameState, hero_id: HeroId) -> dict[Position, int]:
        obstacles = self._rank_obstacles(state, hero_id)
        if not obstacles:
            return {}
        direct_initial = self._direct_potential_units(state)
        autre_id = HeroId.IMAHAKI if hero_id == HeroId.IKOTOFOSA else HeroId.IKOTOFOSA
        option_autre_machine_base = self._machine_option_from_direct_gain(state, autre_id, base_direct=direct_initial)
        resultat: dict[Position, int] = {}
        for obstacle in obstacles:
            hypothetique = deepcopy(state)
            if hero_id == HeroId.IKOTOFOSA:
                hypothetique.holes.discard(obstacle)
            else:
                hypothetique.trees.discard(obstacle)
            direct_apres = self._direct_potential_units(hypothetique)
            gain_direct = direct_apres - direct_initial
            autre_apres = self._machine_option_from_direct_gain(hypothetique, autre_id, base_direct=direct_apres)
            gain_deblocage = autre_apres - option_autre_machine_base
            gain = max(gain_direct, gain_deblocage)
            if gain > 0:
                resultat[obstacle] = gain
        if not resultat:
            frontiere = obstacles[:self.unlock_pair_candidates]
            for premier, second in combinations(frontiere, 2):
                hypothetique = deepcopy(state)
                if hero_id == HeroId.IKOTOFOSA:
                    hypothetique.holes.discard(premier)
                    hypothetique.holes.discard(second)
                else:
                    hypothetique.trees.discard(premier)
                    hypothetique.trees.discard(second)
                gain_paire = self._direct_potential_units(hypothetique) - direct_initial
                if gain_paire <= 0:
                    continue
                resultat[premier] = max(resultat.get(premier, 0), gain_paire)
                resultat[second] = max(resultat.get(second, 0), gain_paire)
        return resultat

    def _unlock_values(self, state: GameState, hero_id: HeroId) -> dict[Position, int]:
        if self._unlock_cache_tick != state.elapsed or self._unlock_cache_state_id != id(state):
            self._unlock_cache_tick = state.elapsed
            self._unlock_cache_state_id = id(state)
            self._unlock_cache = {}
        if hero_id not in self._unlock_cache:
            self._unlock_cache[hero_id] = self._compute_unlock_values(state, hero_id)
        return self._unlock_cache[hero_id]

    def _machine_plan_for_target(self, state: GameState, machine, target: Position) -> MachineControlPlan | None:
        return plan_machine_to_obstacle(state, machine, target)

    def _predict_chest_loss_threats(self, state: GameState, *, horizon: int=24, release_machine_id: str | None=None) -> dict[str, tuple[int, int]]:
        if release_machine_id is None:
            if self._threat_cache_tick == state.elapsed and self._threat_cache_state_id == id(state):
                return dict(self._threat_cache)
        from app.engine.simulator import Simulator
        copie = deepcopy(state)
        if release_machine_id is not None:
            machine = copie.machines.get(release_machine_id)
            if machine is not None and machine.hacked_by is not None:
                conducteur = copie.heroes[machine.hacked_by]
                conducteur.hacking_machine_id = None
                machine.hacked_by = None
                machine.pending_move = False
                machine.resume_delay = 1
        simulateur = Simulator(copie)
        menaces: dict[str, tuple[int, int]] = {}
        limite = min(horizon, copie.remaining_time)
        attentes = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
        for relative_tick in range(1, limite + 1):
            if copie.ended:
                break
            enregistrement = simulateur.step(attentes)
            for evenement in enregistrement.events:
                if evenement.type != 'CHEST_LOST' or not evenement.actor:
                    continue
                precedent = menaces.get(evenement.actor)
                if precedent is None:
                    menaces[evenement.actor] = (relative_tick, 1)
                else:
                    menaces[evenement.actor] = (precedent[0], precedent[1] + 1)
        if release_machine_id is None:
            self._threat_cache_tick = state.elapsed
            self._threat_cache_state_id = id(state)
            self._threat_cache = dict(menaces)
        return menaces

    def _defensive_machine_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        heros = state.heroes[hero_id]
        if heros.battery <= 0 or not state.chests:
            return []
        type_voulu = MachineKind.EXCAVATOR if hero_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        menaces = self._predict_chest_loss_threats(state)
        resultat: list[Candidate] = []
        for id_machine, (tick_menace, nombre_perdus) in menaces.items():
            machine = state.machines.get(id_machine)
            if machine is None or machine.kind != type_voulu or machine.is_hacked:
                continue
            chemin = find_score_path(state, hero_id, machine.position)
            if chemin is None:
                continue
            ajuste = self._adjusted_path_cost(state, hero_id, ticks=chemin.ticks, stamina_cost=chemin.total_stamina_cost)
            if ajuste is None:
                continue
            ticks_effectifs, cout_approche = ajuste
            if ticks_effectifs + 1 > tick_menace + 2:
                continue
            prevent_units = nombre_perdus * CHEST_REWARD_UNITS
            net = prevent_units - cout_approche - HACK_COMMAND_COST_UNITS
            if net <= 0:
                continue
            if chemin.steps:
                premier = chemin.steps[0]
                action = premier.action
                requis = premier.stamina_cost
            else:
                action = HeroAction.HACK
                requis = 0
            resultat.append(Candidate(action=action, utility_units=net, target_key=('defend_chest', id_machine), description=f'intercepter {id_machine}: risque de perte de coffre dans ~{tick_menace} ticks', required_stamina=requis))
        resultat.sort(key=lambda c: (-c.utility_units, c.description))
        return resultat

    def _machine_unlock_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        heros = state.heroes[hero_id]
        if heros.battery <= 0:
            return []
        valeurs = self._unlock_values(state, hero_id)
        if not valeurs:
            return []
        type_voulu = MachineKind.EXCAVATOR if hero_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        resultat: list[Candidate] = []
        for machine in sorted(state.machines.values(), key=lambda m: m.id):
            if machine.kind != type_voulu or machine.is_hacked:
                continue
            approche = find_score_path(state, hero_id, machine.position)
            if approche is None:
                continue
            for obstacle, unites_gain in sorted(valeurs.items(), key=lambda item: (-item[1], item[0].row, item[0].col)):
                controle = self._machine_plan_for_target(state, machine, obstacle)
                if controle is None:
                    continue
                batterie_totale = 1 + controle.battery_cost
                if batterie_totale > heros.battery:
                    continue
                ajuste = self._adjusted_path_cost(state, hero_id, ticks=approche.ticks, stamina_cost=approche.total_stamina_cost)
                if ajuste is None:
                    continue
                ticks_approche, cout_approche = ajuste
                ticks_totaux = ticks_approche + 1 + controle.ticks
                if ticks_totaux > state.remaining_time:
                    continue
                net = unites_gain - cout_approche - HACK_COMMAND_COST_UNITS - controle.score_cost_units
                if net <= 0:
                    continue
                if approche.steps:
                    premier = approche.steps[0]
                    action = premier.action
                    requis = premier.stamina_cost
                else:
                    action = HeroAction.HACK
                    requis = 0
                resultat.append(Candidate(action=action, utility_units=net, target_key=('unlock', obstacle.row, obstacle.col), description=f'{machine.id} -> obstacle utile ({obstacle.row},{obstacle.col}), gain estimé {unites_gain / 4:.2f}', required_stamina=requis))
        resultat.sort(key=lambda c: (-c.utility_units, c.description))
        return resultat[:6]

    def _exit_machine(self, state: GameState, hero_id: HeroId) -> HeroAction:
        heros = state.heroes[hero_id]
        etapes = sorted(hero_neighbors(state, hero_id, heros.position), key=lambda s: (score_cost_units(1, s.stamina_cost), s.action.value))
        for etape in etapes:
            if heros.stamina >= etape.stamina_cost:
                return etape.action
        return HeroAction.WAIT

    def _blocks_other_machine_plan(self, state: GameState, hero_id: HeroId, machine_id: str) -> bool:
        autre_id = HeroId.IMAHAKI if hero_id == HeroId.IKOTOFOSA else HeroId.IKOTOFOSA
        valeurs = self._unlock_values(state, autre_id)
        if not valeurs:
            return False
        type_voulu = MachineKind.EXCAVATOR if autre_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        for cible, gain in valeurs.items():
            if gain <= 0:
                continue
            for autre_machine in state.machines.values():
                if autre_machine.id == machine_id or autre_machine.kind != type_voulu:
                    continue
                if plan_machine_to_obstacle(state, autre_machine, cible) is not None:
                    continue
                hypothetique = deepcopy(state)
                bloqueur = hypothetique.machines.pop(machine_id, None)
                if bloqueur is not None and bloqueur.hacked_by is not None:
                    conducteur = hypothetique.heroes[bloqueur.hacked_by]
                    conducteur.hacking_machine_id = None
                autre_copie = hypothetique.machines.get(autre_machine.id)
                if autre_copie is None:
                    continue
                if plan_machine_to_obstacle(hypothetique, autre_copie, cible) is not None:
                    return True
        return False

    def _partner_useful_machine_plan_exists(self, state: GameState, controller_id: HeroId, *, reference_values: dict[Position, int] | None=None) -> bool:
        autre_id = HeroId.IMAHAKI if controller_id == HeroId.IKOTOFOSA else HeroId.IKOTOFOSA
        valeurs = reference_values if reference_values is not None else self._unlock_values(state, autre_id)
        if not valeurs:
            return False
        type_voulu = MachineKind.EXCAVATOR if autre_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        partenaire = state.heroes[autre_id]
        for cible, gain in valeurs.items():
            if gain <= 0:
                continue
            for autre_machine in state.machines.values():
                if autre_machine.kind != type_voulu:
                    continue
                if autre_machine.is_hacked and autre_machine.hacked_by != autre_id:
                    continue
                if partenaire.battery <= 0:
                    continue
                plan = plan_machine_to_obstacle(state, autre_machine, cible)
                if plan is not None and plan.battery_cost <= partenaire.battery:
                    return True
        return False

    def _partner_profitable_control_exists(self, state: GameState, controller_id: HeroId) -> bool:
        autre_id = HeroId.IMAHAKI if controller_id == HeroId.IKOTOFOSA else HeroId.IKOTOFOSA
        autre_heros = state.heroes[autre_id]
        if not autre_heros.is_hacking or autre_heros.hacking_machine_id is None:
            return False
        autre_machine = state.machines[autre_heros.hacking_machine_id]
        for cible, gain in self._unlock_values(state, autre_id).items():
            if gain <= 0:
                continue
            plan = plan_machine_to_obstacle(state, autre_machine, cible)
            if plan is None or plan.battery_cost > autre_heros.battery:
                continue
            if gain - plan.score_cost_units > 0:
                return True
        return False

    def _safe_relocation_for_blocker(self, state: GameState, hero_id: HeroId, machine) -> Candidate | None:
        if not self._blocks_other_machine_plan(state, hero_id, machine.id):
            return None
        autre_id = HeroId.IMAHAKI if hero_id == HeroId.IKOTOFOSA else HeroId.IKOTOFOSA
        valeurs_reference = self._unlock_values(state, autre_id)
        if not valeurs_reference:
            return None
        positions = sorted((position_courante for position_courante in state.game_map.all_positions() if 0 < machine.position.manhattan(position_courante) <= 3), key=lambda pos: (machine.position.manhattan(pos), pos.row, pos.col))
        meilleur: tuple[tuple[int, int, int, int, int], MachineControlPlan, Position] | None = None
        for cible in positions:
            controle = plan_machine_to_position(state, machine, cible, max_expansions=20000)
            if controle is None or not controle.actions:
                continue
            if controle.battery_cost > state.heroes[hero_id].battery:
                continue
            if controle.ticks > state.remaining_time:
                continue
            hypothetique = deepcopy(state)
            machine_copiee = hypothetique.machines[machine.id]
            machine_copiee.position = cible
            machine_copiee.pending_move = False
            machine_copiee.auto_move_pending = False
            if machine_copiee.hacked_by is not None:
                hypothetique.heroes[machine_copiee.hacked_by].position = cible
            if machine_copiee.kind == MachineKind.GRAPPLER and cible in hypothetique.trees:
                hypothetique.trees.remove(cible)
            if not self._partner_useful_machine_plan_exists(hypothetique, hero_id, reference_values=valeurs_reference):
                continue
            coupe_arbre = machine.kind == MachineKind.GRAPPLER and cible in state.trees
            distance_coffre = min((cible.manhattan(coffre) for coffre in state.chests)) if state.chests else 99
            classement = (controle.score_cost_units, -int(coupe_arbre), -distance_coffre, cible.row, cible.col)
            if meilleur is None or classement < meilleur[0]:
                meilleur = (classement, controle, cible)
        if meilleur is None:
            return None
        _classement, controle, cible = meilleur
        return Candidate(action=controle.actions[0], utility_units=max(1, CHEST_REWARD_UNITS - controle.score_cost_units), target_key=('park_machine', machine.id, cible.row, cible.col), description=f'repositionner {machine.id} vers ({cible.row},{cible.col}) pour libérer le plan machine du partenaire')

    def _control_machine(self, state: GameState, hero_id: HeroId) -> Candidate:
        heros = state.heroes[hero_id]
        machine = state.machines[heros.hacking_machine_id]
        if machine.pending_move:
            return Candidate(HeroAction.WAIT, 1, ('machine', machine.id), 'attendre exécution HACK_MOVE')
        if machine.kind == MachineKind.GRAPPLER and machine.position in state.trees:
            return Candidate(HeroAction.WAIT, 1, ('machine', machine.id), 'laisser Grappler couper')
        valeurs = self._unlock_values(state, hero_id)
        meilleur: Candidate | None = None
        for obstacle, unites_gain in valeurs.items():
            plan = self._machine_plan_for_target(state, machine, obstacle)
            if not plan or not plan.actions:
                continue
            if plan.battery_cost > heros.battery:
                continue
            net = unites_gain - plan.score_cost_units
            if net <= 0:
                continue
            candidat = Candidate(action=plan.actions[0], utility_units=net, target_key=('unlock', obstacle.row, obstacle.col), description=f'contrôler {machine.id} vers obstacle utile ({obstacle.row},{obstacle.col})')
            if meilleur is None or (candidat.utility_units, candidat.description) > (meilleur.utility_units, meilleur.description):
                meilleur = candidat
        if meilleur is not None:
            return meilleur
        autre_id = HeroId.IMAHAKI if hero_id == HeroId.IKOTOFOSA else HeroId.IKOTOFOSA
        autre_heros = state.heroes[autre_id]
        if state.chests and autre_heros.is_hacking and self._partner_profitable_control_exists(state, hero_id):
            return Candidate(action=HeroAction.WAIT, utility_units=CHEST_REWARD_UNITS, target_key=('hold_corridor', machine.id), description=f'maintenir {machine.id} immobilisé pendant le plan machine du partenaire')
        menaces_relachees = self._predict_chest_loss_threats(state, horizon=32, release_machine_id=machine.id)
        menace = menaces_relachees.get(machine.id)
        bloque_partenaire = self._blocks_other_machine_plan(state, hero_id, machine.id)
        if bloque_partenaire and state.chests:
            repositionnement = self._safe_relocation_for_blocker(state, hero_id, machine)
            if repositionnement is not None:
                return repositionnement
        if menace is not None and state.chests:
            tick_menace, nombre_perdus = menace
            return Candidate(action=HeroAction.WAIT, utility_units=nombre_perdus * CHEST_REWARD_UNITS - 2 * tick_menace, target_key=('defend_chest', machine.id), description=f'maintenir {machine.id} neutralisé pour protéger le coffre')
        return Candidate(action=self._exit_machine(state, hero_id), utility_units=0, target_key=None, description='quitter machine: aucun obstacle rentable')

    def _all_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        heros = state.heroes[hero_id]
        if heros.is_hacking:
            return [self._control_machine(state, hero_id)]
        coffres = self._chest_candidates(state, hero_id)
        pierres = self._stone_candidates(state, hero_id)
        pierres_machines = self._machine_stone_candidates(state, hero_id)
        direct = coffres + pierres + pierres_machines
        direct.sort(key=lambda c: (-c.utility_units, c.description))
        defense = self._defensive_machine_candidates(state, hero_id)[:2]
        deblocage: list[Candidate] = []
        if not coffres and state.chests:
            deblocage = self._machine_unlock_candidates(state, hero_id)[:4]
        elif not direct and not defense:
            deblocage = self._machine_unlock_candidates(state, hero_id)[:4]
        candidats = direct[:10] + defense + deblocage
        candidats.sort(key=lambda c: (-c.utility_units, c.description))
        return candidats[:12]

    def _make_executable(self, state: GameState, hero_id: HeroId, candidate: Candidate) -> HeroAction:
        heros = state.heroes[hero_id]
        if candidate.required_stamina > heros.stamina:
            return HeroAction.WAIT
        if candidate.action in {HeroAction.UP, HeroAction.DOWN, HeroAction.LEFT, HeroAction.RIGHT}:
            if not Rules.hero_move(state, heros, candidate.action).valid:
                return HeroAction.WAIT
        elif candidate.action in PUSH_ACTIONS:
            poussee = Rules.chest_push(state, heros, candidate.action)
            if not poussee.valid or not Rules.hero_chest_push_safe_this_tick(state, poussee):
                return HeroAction.WAIT
        return candidate.action

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        self._potential_cache.clear()
        reservoirs: dict[HeroId, list[Candidate]] = {}
        for id_heros in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            candidats = self._all_candidates(state, id_heros)
            candidats.append(Candidate(HeroAction.WAIT, 0, None, 'attendre'))
            reservoirs[id_heros] = candidats
        meilleure_paire: tuple[Candidate, Candidate] | None = None
        meilleure_cle: tuple[int, str, str] | None = None
        for candidat_f, candidat_m in product(reservoirs[HeroId.IKOTOFOSA], reservoirs[HeroId.IMAHAKI]):
            if candidat_f.target_key is not None and candidat_f.target_key == candidat_m.target_key:
                continue
            total = candidat_f.utility_units + candidat_m.utility_units
            cle = (total, candidat_f.description, candidat_m.description)
            if meilleure_cle is None or cle > meilleure_cle:
                meilleure_cle = cle
                meilleure_paire = (candidat_f, candidat_m)
        if meilleure_paire is None:
            meilleure_paire = (Candidate(HeroAction.WAIT, 0, None, 'attendre'), Candidate(HeroAction.WAIT, 0, None, 'attendre'))
        decisions = {HeroId.IKOTOFOSA: self._make_executable(state, HeroId.IKOTOFOSA, meilleure_paire[0]), HeroId.IMAHAKI: self._make_executable(state, HeroId.IMAHAKI, meilleure_paire[1])}
        self.last_decisions = {'F': meilleure_paire[0].description, 'M': meilleure_paire[1].description}
        but_positif = any((colonne_idx.utility_units > 0 for colonne_idx in meilleure_paire))
        if but_positif:
            self.stuck_ticks = 0
        elif all((action == HeroAction.WAIT for action in decisions.values())):
            self.stuck_ticks += 1
        else:
            self.stuck_ticks = 0
        return decisions
