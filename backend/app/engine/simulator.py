from __future__ import annotations
from collections import Counter
from typing import Iterable, Protocol
from uuid import uuid4
from app.domain.enums import HACK_ACTIONS, MOVE_ACTIONS, PUSH_ACTIONS, HeroAction, HeroId, MachineAction, MachineKind
from app.domain.models import Event, GameState, SimulationResult, TickRecord
from app.engine.actions_writer import build_actions_text
from app.engine.rules import Rules
from app.engine.scoring import compute_score
from app.engine.snapshot import snapshot_state

class StrategyProtocol(Protocol):

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        ...

    def should_end(self, state: GameState) -> bool:
        ...

class Simulator:

    def __init__(self, state: GameState):
        self.state = state
        self.initial_snapshot = snapshot_state(state)
        self.ticks: list[TickRecord] = []

    def _event(self, events: list[Event], type_: str, message: str, *, actor: str | None=None, position=None, **data: object) -> None:
        events.append(Event(type=type_, message=message, actor=actor, position=position, data=data))

    def _collect_for_hero(self, hero_id: HeroId, events: list[Event]) -> None:
        heros = self.state.heroes[hero_id]
        if heros.position in self.state.stones:
            self.state.stones.remove(heros.position)
            heros.stones += 1
            self._event(events, 'STONE_COLLECTED', f'{hero_id.value} récupère une pierre précieuse.', actor=hero_id.value, position=heros.position)
        self._steal_machine_stones(hero_id, events)

    def _steal_machine_stones(self, hero_id: HeroId, events: list[Event]) -> None:
        heros = self.state.heroes[hero_id]
        for machine in self.state.machines.values():
            if machine.position == heros.position and machine.carried_stones > 0:
                quantite = machine.carried_stones
                machine.carried_stones = 0
                heros.stones += quantite
                self._event(events, 'STONES_STOLEN', f'{hero_id.value} récupère {quantite} pierre(s) portée(s) par {machine.id}.', actor=hero_id.value, position=heros.position, machine_id=machine.id, amount=quantite)

    def _unhack(self, hero_id: HeroId, events: list[Event]) -> None:
        heros = self.state.heroes[hero_id]
        if not heros.hacking_machine_id:
            return
        machine = self.state.machines[heros.hacking_machine_id]
        machine.hacked_by = None
        machine.pending_move = False
        machine.resume_delay = 1
        heros.hacking_machine_id = None
        self._event(events, 'UNHACK', f'{hero_id.value} quitte {machine.id}; la routine automatique reprend après 1 tick.', actor=hero_id.value, position=heros.position, machine_id=machine.id)

    def _apply_chest_destination(self, chest_from, chest_to, events, actor: str) -> None:
        self.state.chests.discard(chest_from)
        if chest_to in self.state.holes:
            self.state.lost_chests += 1
            self._event(events, 'CHEST_LOST', 'Un coffre tombe dans un trou et est perdu.', actor=actor, position=chest_to)
        elif chest_to in self.state.game_map.bushes:
            self.state.secured_chests += 1
            self._event(events, 'CHEST_SECURED', 'Un coffre est placé dans une cachette.', actor=actor, position=chest_to)
        else:
            self.state.chests.add(chest_to)
            self._event(events, 'CHEST_PUSHED', "Un coffre est poussé d'une case.", actor=actor, position=chest_to)

    def _coerce_wait(self, hero_id: HeroId, effective: dict[HeroId, HeroAction], events: list[Event], reason: str) -> None:
        if effective[hero_id] != HeroAction.WAIT:
            self._event(events, 'ACTION_COERCED_TO_WAIT', f'Action de {hero_id.value} remplacée par WAIT: {reason}.', actor=hero_id.value, requested=effective[hero_id].value, reason=reason)
        effective[hero_id] = HeroAction.WAIT

    def step(self, requested: dict[HeroId, HeroAction]) -> TickRecord:
        if self.state.ended:
            raise RuntimeError('La partie est déjà terminée.')
        if self.state.elapsed >= self.state.game_map.time_limit:
            self.state.ended = True
            self.state.end_reason = 'TIME_LIMIT'
            raise RuntimeError('TIME_LIMIT atteint.')
        evenements: list[Event] = []
        for machine in self.state.machines.values():
            machine.last_action = MachineAction.NONE
        requested_actions = {HeroId.IKOTOFOSA: requested.get(HeroId.IKOTOFOSA, HeroAction.WAIT), HeroId.IMAHAKI: requested.get(HeroId.IMAHAKI, HeroAction.WAIT)}
        effectif = dict(requested_actions)
        controle_attente_avant = {id_machine: machine.pending_move for id_machine, machine in self.state.machines.items()}
        auto_attente_avant = {id_machine: machine.auto_move_pending for id_machine, machine in self.state.machines.items()}
        for id_heros, heros in self.state.heroes.items():
            if heros.hacking_machine_id:
                machine = self.state.machines[heros.hacking_machine_id]
                if controle_attente_avant[machine.id]:
                    self._coerce_wait(id_heros, effectif, evenements, 'HACK_MOVE en cours')
                elif machine.kind == MachineKind.GRAPPLER and machine.position in self.state.trees:
                    self._coerce_wait(id_heros, effectif, evenements, 'Grappler en train de couper un arbre')
        poussees_heros = {id_heros: action for id_heros, action in effectif.items() if action in PUSH_ACTIONS}
        for id_heros in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            heros = self.state.heroes[id_heros]
            action = effectif[id_heros]
            if action in MOVE_ACTIONS:
                mouvement = Rules.hero_move(self.state, heros, action)
                if not mouvement.valid:
                    self._coerce_wait(id_heros, effectif, evenements, mouvement.reason or 'déplacement invalide')
                    continue
                if heros.is_hacking:
                    self._unhack(id_heros, evenements)
                ancien = heros.position
                heros.position = mouvement.destination
                heros.stamina -= mouvement.stamina_cost
                self._event(evenements, 'HERO_MOVED', f'{id_heros.value} se déplace.', actor=id_heros.value, position=heros.position, from_row=ancien.row, from_col=ancien.col, jumped=mouvement.jumped, stamina_cost=mouvement.stamina_cost)
                self._collect_for_hero(id_heros, evenements)
                continue
            if action in PUSH_ACTIONS:
                continue
            if action == HeroAction.HACK:
                if heros.is_hacking or heros.battery <= 0:
                    self._coerce_wait(id_heros, effectif, evenements, 'HACK invalide')
                    continue
                candidats = [machine_locale for machine_locale in self.state.machines_at(heros.position) if Rules.compatible_machine(heros, machine_locale) and (not machine_locale.is_hacked)]
                if not candidats:
                    self._coerce_wait(id_heros, effectif, evenements, 'aucune machine compatible sur la case')
                    continue
                machine = sorted(candidats, key=lambda m: m.id)[0]
                heros.battery -= 1
                heros.hacking_machine_id = machine.id
                machine.hacked_by = id_heros
                machine.auto_move_pending = False
                machine.pending_move = False
                machine.resume_delay = 0
                self._event(evenements, 'MACHINE_HACKED', f'{id_heros.value} prend le contrôle de {machine.id}.', actor=id_heros.value, position=heros.position, machine_id=machine.id)
                continue
            if action in HACK_ACTIONS - {HeroAction.HACK}:
                if not heros.is_hacking or heros.battery <= 0:
                    self._coerce_wait(id_heros, effectif, evenements, 'action de hacking invalide')
                    continue
                machine = self.state.machines[heros.hacking_machine_id]
                if action == HeroAction.HACK_MOVE:
                    if machine.pending_move or not Rules.machine_forward_clear(self.state, machine):
                        self._coerce_wait(id_heros, effectif, evenements, 'HACK_MOVE bloqué')
                        continue
                    heros.battery -= 1
                    machine.pending_move = True
                    machine.last_action = MachineAction.MOVE
                    self._event(evenements, 'HACK_MOVE_QUEUED', f'{id_heros.value} programme le déplacement de {machine.id}.', actor=id_heros.value, machine_id=machine.id)
                elif action == HeroAction.HACK_CW:
                    heros.battery -= 1
                    Rules.rotate_cw(machine)
                    machine.last_action = MachineAction.CW
                    self._event(evenements, 'MACHINE_ROTATED', f'{machine.id} tourne CW.', actor=id_heros.value, machine_id=machine.id)
                elif action == HeroAction.HACK_CCW:
                    heros.battery -= 1
                    Rules.rotate_ccw(machine)
                    machine.last_action = MachineAction.CCW
                    self._event(evenements, 'MACHINE_ROTATED', f'{machine.id} tourne CCW.', actor=id_heros.value, machine_id=machine.id)
                elif action == HeroAction.HACK_FILL:
                    if id_heros != HeroId.IKOTOFOSA or machine.kind != MachineKind.EXCAVATOR:
                        self._coerce_wait(id_heros, effectif, evenements, 'HACK_FILL réservé à Ikotofosa/Excavator')
                        continue
                    devant = Rules.machine_forward(machine)
                    if devant not in self.state.holes:
                        self._coerce_wait(id_heros, effectif, evenements, "aucun trou devant l'excavateur")
                        continue
                    heros.battery -= 1
                    self.state.holes.remove(devant)
                    machine.last_action = MachineAction.FILL
                    self._event(evenements, 'HOLE_FILLED', 'Un trou est rebouché.', actor=id_heros.value, position=devant, machine_id=machine.id)
                elif action == HeroAction.HACK_CUT:
                    if id_heros != HeroId.IMAHAKI or machine.kind != MachineKind.GRAPPLER:
                        self._coerce_wait(id_heros, effectif, evenements, 'HACK_CUT réservé à Imahaki/Grappler')
                        continue
                    position_coupe = machine.position if machine.position in self.state.trees else Rules.machine_forward(machine)
                    if position_coupe not in self.state.trees:
                        self._coerce_wait(id_heros, effectif, evenements, 'aucun arbre à couper')
                        continue
                    heros.battery -= 1
                    self.state.trees.remove(position_coupe)
                    machine.last_action = MachineAction.CUT
                    self._event(evenements, 'TREE_CUT', 'Un arbre est coupé.', actor=id_heros.value, position=position_coupe, machine_id=machine.id)
                continue
            if action != HeroAction.WAIT:
                self._coerce_wait(id_heros, effectif, evenements, 'action inconnue')
        ids_machines_conflit_poussee: set[str] = set()
        poussees_heros_valides: dict[HeroId, object] = {}
        groupes: dict[object, list[tuple[str, object, object]]] = {}
        for id_heros, action in poussees_heros.items():
            heros = self.state.heroes[id_heros]
            poussee = Rules.chest_push(self.state, heros, action)
            if not poussee.valid:
                self._coerce_wait(id_heros, effectif, evenements, poussee.reason or 'poussée invalide')
                continue
            poussees_heros_valides[id_heros] = poussee
            groupes.setdefault(poussee.chest_from, []).append((f'hero:{id_heros.value}', poussee.chest_to, poussee))
        for id_machine, machine in self.state.machines.items():
            a_executer = False
            if machine.is_hacked:
                a_executer = controle_attente_avant[id_machine] and machine.pending_move
            else:
                a_executer = auto_attente_avant[id_machine] and machine.auto_move_pending and (machine.resume_delay == 0)
            if not a_executer or not Rules.machine_forward_clear(self.state, machine):
                continue
            coffre_depart = Rules.machine_forward(machine)
            if coffre_depart not in self.state.chests:
                continue
            delta_ligne = coffre_depart.row - machine.position.row
            delta_col = coffre_depart.col - machine.position.col
            coffre_arrivee = coffre_depart.moved(delta_ligne, delta_col)
            groupes.setdefault(coffre_depart, []).append((f'machine:{id_machine}', coffre_arrivee, None))
        for coffre_depart, poussees in groupes.items():
            entrees_heros = [entree for entree in poussees if entree[0].startswith('hero:')]
            if not entrees_heros:
                continue
            destinations = {entree[1] for entree in poussees}
            if len(destinations) > 1:
                self._event(evenements, 'CHEST_PUSH_CONFLICT', 'Plusieurs agents poussent le même coffre dans des directions différentes.', position=coffre_depart)
                for actor, _destination, _poussee in poussees:
                    if actor.startswith('hero:'):
                        id_heros = HeroId(actor.split(':', 1)[1])
                        self._coerce_wait(id_heros, effectif, evenements, 'conflit de poussée')
                    else:
                        ids_machines_conflit_poussee.add(actor.split(':', 1)[1])
                continue
            coffre_arrivee = next(iter(destinations))
            self._apply_chest_destination(coffre_depart, coffre_arrivee, evenements, 'MULTI_PUSH')
            for actor, _destination, poussee in entrees_heros:
                id_heros = HeroId(actor.split(':', 1)[1])
                heros = self.state.heroes[id_heros]
                if heros.is_hacking:
                    self._unhack(id_heros, evenements)
                heros.stamina -= 5
                heros.position = poussee.hero_to
                self._collect_for_hero(id_heros, evenements)
        intentions_mouvement: dict[str, object] = {}
        ids_mouvements_controles: set[str] = set()
        for id_machine in sorted(self.state.machines):
            machine = self.state.machines[id_machine]
            if id_machine in ids_machines_conflit_poussee:
                machine.pending_move = False
                machine.auto_move_pending = False
                machine.last_action = MachineAction.WAIT
                self._event(evenements, 'CHEST_PUSH_CONFLICT', f'{id_machine} est bloqué par un conflit de poussée.', actor=id_machine)
                continue
            if machine.is_hacked:
                if controle_attente_avant[id_machine] and machine.pending_move:
                    machine.pending_move = False
                    if Rules.machine_forward_clear(self.state, machine):
                        cible = Rules.machine_forward(machine)
                        intentions_mouvement[id_machine] = cible
                        ids_mouvements_controles.add(id_machine)
                        machine.last_action = MachineAction.MOVE
                    else:
                        machine.last_action = MachineAction.WAIT
                        self._event(evenements, 'MACHINE_MOVE_BLOCKED', f'{id_machine} ne peut pas exécuter HACK_MOVE.', actor=id_machine)
                elif machine.kind == MachineKind.GRAPPLER and machine.position in self.state.trees:
                    self.state.trees.remove(machine.position)
                    machine.last_action = MachineAction.CUT
                    self._event(evenements, 'TREE_CUT', "Le Grappler coupe automatiquement l'arbre occupé.", actor=id_machine, position=machine.position)
                continue
            if machine.resume_delay > 0:
                machine.resume_delay -= 1
                machine.last_action = MachineAction.WAIT
                continue
            if machine.kind == MachineKind.GRAPPLER and machine.position in self.state.trees:
                self.state.trees.remove(machine.position)
                machine.last_action = MachineAction.CUT
                self._event(evenements, 'TREE_CUT', "Le Grappler coupe l'arbre occupé.", actor=id_machine, position=machine.position)
                continue
            if machine.kind == MachineKind.EXCAVATOR and machine.steps_since_dig >= 5:
                self.state.holes.add(machine.position)
                machine.steps_since_dig = 0
                machine.last_action = MachineAction.DIG
                self._event(evenements, 'HOLE_DUG', "L'Excavator creuse un trou.", actor=id_machine, position=machine.position)
                continue
            if auto_attente_avant[id_machine] and machine.auto_move_pending:
                machine.auto_move_pending = False
                if Rules.machine_forward_clear(self.state, machine):
                    intentions_mouvement[id_machine] = Rules.machine_forward(machine)
                    machine.last_action = MachineAction.MOVE
                else:
                    machine.last_action = MachineAction.WAIT
                    self._event(evenements, 'MACHINE_MOVE_BLOCKED', f'{id_machine} ne peut pas terminer son déplacement.', actor=id_machine)
                continue
            if Rules.machine_forward_clear(self.state, machine):
                machine.auto_move_pending = True
                machine.last_action = MachineAction.MOVE
                self._event(evenements, 'MACHINE_MOVE_QUEUED', f'{id_machine} commence un MOVE de 2 ticks.', actor=id_machine)
            else:
                if machine.kind == MachineKind.EXCAVATOR:
                    Rules.rotate_ccw(machine)
                    machine.last_action = MachineAction.CCW
                else:
                    Rules.rotate_cw(machine)
                    machine.last_action = MachineAction.CW
                self._event(evenements, 'MACHINE_ROTATED', f'{id_machine} pivote car son chemin est bloqué.', actor=id_machine)
        comptes_cibles = Counter(intentions_mouvement.values())
        ids_bloques = {id_machine for id_machine, cible in intentions_mouvement.items() if comptes_cibles[cible] > 1}
        for id_machine in ids_bloques:
            self.state.machines[id_machine].last_action = MachineAction.WAIT
            self._event(evenements, 'MACHINE_COLLISION_AVOIDED', f'{id_machine} reste sur place: cible partagée.', actor=id_machine, position=intentions_mouvement[id_machine])
        for id_machine in sorted(intentions_mouvement):
            if id_machine in ids_bloques:
                continue
            machine = self.state.machines[id_machine]
            cible = intentions_mouvement[id_machine]
            if any((autre.id != id_machine and autre.position == cible for autre in self.state.machines.values())):
                machine.last_action = MachineAction.WAIT
                self._event(evenements, 'MACHINE_MOVE_BLOCKED', f'{id_machine} reste sur place: machine sur la cible.', actor=id_machine, position=cible)
                continue
            if cible in self.state.chests:
                direction = Rules.machine_forward(machine)
                devant_machine = cible
                delta_ligne = devant_machine.row - machine.position.row
                delta_col = devant_machine.col - machine.position.col
                coffre_arrivee = devant_machine.moved(delta_ligne, delta_col)
                if not self.state.game_map.in_bounds(coffre_arrivee) or coffre_arrivee in self.state.game_map.rocks or coffre_arrivee in self.state.trees or (coffre_arrivee in self.state.chests):
                    machine.last_action = MachineAction.WAIT
                    self._event(evenements, 'CHEST_PUSH_BLOCKED', f'{id_machine} ne peut pas pousser le coffre.', actor=id_machine, position=cible)
                    continue
                self._apply_chest_destination(cible, coffre_arrivee, evenements, id_machine)
            ancien = machine.position
            machine.position = cible
            if machine.kind == MachineKind.EXCAVATOR and id_machine not in ids_mouvements_controles:
                machine.steps_since_dig += 1
            if machine.hacked_by is not None:
                conducteur = self.state.heroes[machine.hacked_by]
                conducteur.position = machine.position
            self._event(evenements, 'MACHINE_MOVED', f'{id_machine} termine son déplacement.', actor=id_machine, position=machine.position, from_row=ancien.row, from_col=ancien.col)
            heros_ici = sorted([h for h in self.state.heroes.values() if h.position == machine.position], key=lambda h: h.id.value)
            if machine.position in self.state.stones:
                if heros_ici:
                    self.state.stones.remove(machine.position)
                    heros_ici[0].stones += 1
                    self._event(evenements, 'STONE_COLLECTED', f"{heros_ici[0].id.value} récupère la pierre à l'arrivée de {id_machine}.", actor=heros_ici[0].id.value, position=machine.position)
                else:
                    self.state.stones.remove(machine.position)
                    machine.carried_stones += 1
                    self._event(evenements, 'STONE_PICKED_BY_MACHINE', f'{id_machine} ramasse une pierre.', actor=id_machine, position=machine.position)
            for heros in heros_ici:
                self._steal_machine_stones(heros.id, evenements)
        for id_heros, heros in self.state.heroes.items():
            if effectif[id_heros] == HeroAction.WAIT or heros.is_hacking:
                heros.recovery_seconds += 1
                if heros.recovery_seconds >= 2:
                    if heros.stamina < 100:
                        heros.stamina += 1
                        self._event(evenements, 'STAMINA_RECOVERED', f'{id_heros.value} récupère 1 stamina.', actor=id_heros.value, position=heros.position)
                    heros.recovery_seconds -= 2
            else:
                heros.recovery_seconds = 0
        self.state.elapsed += 1
        if self.state.elapsed >= self.state.game_map.time_limit:
            self.state.ended = True
            self.state.end_reason = 'TIME_LIMIT'
        enregistrement = TickRecord(tick=self.state.elapsed, requested_actions=requested_actions, effective_actions=dict(effectif), machine_actions={id_machine: machine_locale.last_action for id_machine, machine_locale in self.state.machines.items()}, events=evenements, snapshot=snapshot_state(self.state))
        self.ticks.append(enregistrement)
        return enregistrement

    def run_actions(self, actions: Iterable[dict[HeroId, HeroAction]], *, stop_when_objectives_finished: bool=False) -> SimulationResult:
        for paire in actions:
            if self.state.ended:
                break
            self.step(paire)
            if stop_when_objectives_finished and self.state.objectives_finished:
                self.state.ended = True
                self.state.end_reason = 'OBJECTIVES_FINISHED'
                break
        if not self.state.ended:
            self.state.ended = True
            self.state.end_reason = 'END_GAME'
        return self.result()

    def run_strategy(self, strategy: StrategyProtocol) -> SimulationResult:
        while not self.state.ended:
            if self.state.objectives_finished:
                self.state.ended = True
                self.state.end_reason = 'OBJECTIVES_FINISHED'
                break
            if strategy.should_end(self.state):
                self.state.ended = True
                self.state.end_reason = 'STRATEGY_END_GAME'
                break
            self.step(strategy.next_actions(self.state))
        return self.result()

    def result(self) -> SimulationResult:
        return SimulationResult(simulation_id=str(uuid4()), initial_snapshot=self.initial_snapshot, ticks=list(self.ticks), final_snapshot=snapshot_state(self.state), score=compute_score(self.state), actions_text=build_actions_text(self.ticks, self.state.game_map.time_limit))
