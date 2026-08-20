from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Protocol
from uuid import uuid4
from app.domain.enums import HACK_ACTIONS, MOVE_ACTIONS, PUSH_ACTIONS, HeroAction, HeroId, MachineAction, MachineKind
from app.domain.models import Event, GameState, MachineState, Position, SimulationResult, TickRecord
from app.engine.actions_writer import build_actions_text
from app.engine.rules import ChestPush, Rules
from app.engine.scoring import compute_score
from app.engine.snapshot import snapshot_state

class StrategyProtocol(Protocol):

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        ...

    def should_end(self, state: GameState) -> bool:
        ...

@dataclass(frozen=True, slots=True)
class MachineIntent:
    machine_id: str
    target: Position
    controlled: bool
    chest_from: Position | None = None
    chest_to: Position | None = None

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

    def _apply_chest_destination(self, chest_from: Position, chest_to: Position, events: list[Event], actor: str) -> None:
        self.state.chests.discard(chest_from)
        if Rules.chest_destroyed_by_cliff(self.state, chest_from, chest_to):
            self.state.lost_chests += 1
            self._event(
                events,
                'CHEST_DESTROYED_CLIFF',
                'Un coffre chute de 5 niveaux ou plus et est détruit.',
                actor=actor,
                position=chest_to,
                from_elevation=Rules.elevation(self.state, chest_from),
                to_elevation=Rules.elevation(self.state, chest_to),
            )
        # FAQ 19/08: un Excavator peut DIG sur un bush; le trou reste présent
        # mais le bush conserve sa fonction de cachette.  La falaise >=5 reste
        # l'unique priorité supérieure, conformément à l'Addendum.
        elif chest_to in self.state.game_map.bushes:
            self.state.secured_chests += 1
            self._event(events, 'CHEST_SECURED', 'Un coffre est placé dans une cachette.', actor=actor, position=chest_to)
        elif chest_to in self.state.holes:
            self.state.lost_chests += 1
            self._event(events, 'CHEST_LOST', 'Un coffre tombe dans un trou et est perdu.', actor=actor, position=chest_to)
        else:
            self.state.chests.add(chest_to)
            self._event(events, 'CHEST_PUSHED', "Un coffre est poussé d'une case.", actor=actor, position=chest_to)

    def _coerce_wait(self, hero_id: HeroId, effective: dict[HeroId, HeroAction], events: list[Event], reason: str) -> None:
        if effective[hero_id] != HeroAction.WAIT:
            self._event(events, 'ACTION_COERCED_TO_WAIT', f'Action de {hero_id.value} remplacée par WAIT: {reason}.', actor=hero_id.value, requested=effective[hero_id].value, reason=reason)
        effective[hero_id] = HeroAction.WAIT

    def _rotate_automatic_blocked(self, machine: MachineState, events: list[Event], reason: str) -> None:
        machine.pending_move = False
        machine.auto_move_pending = False
        if machine.kind == MachineKind.EXCAVATOR:
            Rules.rotate_ccw(machine)
            machine.last_action = MachineAction.CCW
        else:
            Rules.rotate_cw(machine)
            machine.last_action = MachineAction.CW
        self._event(events, 'MACHINE_ROTATED', f'{machine.id} pivote car son déplacement est bloqué.', actor=machine.id, position=machine.position, reason=reason)

    def _wait_controlled_blocked(self, machine: MachineState, events: list[Event], reason: str) -> None:
        machine.pending_move = False
        machine.last_action = MachineAction.WAIT
        self._event(events, 'MACHINE_MOVE_BLOCKED', f'{machine.id} reste sur place.', actor=machine.id, position=machine.position, reason=reason)

    def _build_machine_intent(self, machine: MachineState, *, controlled: bool) -> tuple[MachineIntent | None, str | None]:
        # GDD Addendum: collision look-ahead is hardcoded and has priority over
        # elevation checks, even for hacked machines.
        lookahead_reason = Rules.machine_lookahead_reason(self.state, machine)
        if lookahead_reason is not None:
            return None, lookahead_reason

        cible = Rules.machine_forward(machine)
        if not Rules.machine_cell_passable(self.state, machine, cible):
            if self.state.game_map.in_bounds(cible):
                elevation_reason = Rules.machine_elevation_reason(self.state, machine.position, cible)
                if elevation_reason is not None:
                    return None, elevation_reason
            return None, 'terrain_blocked'

        coffre_depart: Position | None = None
        coffre_arrivee: Position | None = None
        if cible in self.state.chests:
            delta_ligne = cible.row - machine.position.row
            delta_col = cible.col - machine.position.col
            destination = cible.moved(delta_ligne, delta_col)
            if not self.state.game_map.in_bounds(destination):
                return None, 'chest_outside_map'
            if destination in self.state.game_map.rocks:
                return None, 'chest_rock'
            if destination in self.state.trees:
                return None, 'chest_tree'
            if destination in self.state.chests:
                return None, 'another_chest'
            if self.state.machine_at(destination) is not None:
                return None, 'machine_behind_chest'
            elevation_reason = Rules.machine_chest_elevation_reason(self.state, cible, destination)
            if elevation_reason is not None:
                return None, elevation_reason
            coffre_depart = cible
            coffre_arrivee = destination
        return MachineIntent(machine_id=machine.id, target=cible, controlled=controlled, chest_from=coffre_depart, chest_to=coffre_arrivee), None

    def _resolve_machine_intents(self, intentions: dict[str, MachineIntent], initial_blocked: dict[str, str] | None=None) -> dict[str, str]:
        bloques = dict(initial_blocked or {})
        position_machine = {machine.position: machine.id for machine in self.state.machines.values()}
        par_cible: dict[Position, list[str]] = defaultdict(list)
        for id_machine, intention in intentions.items():
            if id_machine not in bloques:
                par_cible[intention.target].append(id_machine)
        for ids in par_cible.values():
            if len(ids) > 1:
                for id_machine in ids:
                    bloques.setdefault(id_machine, 'shared_machine_target')
        groupes_coffres: dict[Position, list[MachineIntent]] = defaultdict(list)
        for intention in intentions.values():
            if intention.chest_from is not None:
                groupes_coffres[intention.chest_from].append(intention)
        for groupe in groupes_coffres.values():
            destinations = {intention.chest_to for intention in groupe}
            if len(destinations) > 1:
                for intention in groupe:
                    bloques.setdefault(intention.machine_id, 'opposite_chest_push')
        for intention in intentions.values():
            if intention.machine_id in bloques or intention.chest_to is None:
                continue
            autre_sur_destination = position_machine.get(intention.chest_to)
            if autre_sur_destination is not None and autre_sur_destination != intention.machine_id:
                bloques.setdefault(intention.machine_id, 'machine_behind_chest')
                if autre_sur_destination in intentions:
                    bloques.setdefault(autre_sur_destination, 'machine_behind_chest')
        for pousseur in intentions.values():
            if pousseur.machine_id in bloques or pousseur.chest_to is None:
                continue
            for autre in intentions.values():
                if autre.machine_id == pousseur.machine_id or autre.machine_id in bloques:
                    continue
                if autre.target == pousseur.chest_to:
                    bloques.setdefault(pousseur.machine_id, 'chest_machine_crossing')
                    bloques.setdefault(autre.machine_id, 'chest_machine_crossing')
        change = True
        while change:
            change = False
            for id_machine, intention in intentions.items():
                if id_machine in bloques:
                    continue
                occupant_id = position_machine.get(intention.target)
                if occupant_id is None or occupant_id == id_machine:
                    continue
                occupant = self.state.machines[occupant_id]
                machine = self.state.machines[id_machine]
                if machine.orientation != occupant.orientation:
                    bloques[id_machine] = 'machine_orientation_block'
                    change = True
                    continue
                if occupant_id not in intentions or occupant_id in bloques:
                    bloques[id_machine] = 'machine_not_vacating'
                    change = True
        graphe: dict[str, str] = {}
        for id_machine, intention in intentions.items():
            if id_machine in bloques:
                continue
            occupant_id = position_machine.get(intention.target)
            if occupant_id is not None and occupant_id != id_machine and occupant_id in intentions and occupant_id not in bloques:
                graphe[id_machine] = occupant_id
        visites: set[str] = set()
        for depart in list(graphe):
            if depart in visites or depart in bloques:
                continue
            chemin: list[str] = []
            indices: dict[str, int] = {}
            courant = depart
            while courant in graphe and courant not in bloques:
                if courant in indices:
                    for id_cycle in chemin[indices[courant]:]:
                        bloques.setdefault(id_cycle, 'machine_cycle')
                    break
                if courant in visites:
                    break
                indices[courant] = len(chemin)
                chemin.append(courant)
                courant = graphe[courant]
            visites.update(chemin)
        change = True
        while change:
            change = False
            for id_machine, intention in intentions.items():
                if id_machine in bloques:
                    continue
                occupant_id = position_machine.get(intention.target)
                if occupant_id is not None and occupant_id != id_machine and occupant_id in bloques:
                    bloques[id_machine] = 'machine_chain_blocked'
                    change = True
        return bloques

    def _hero_machine_push_conflicts(self, hero_pushes: dict[HeroId, ChestPush], machine_intents: dict[str, MachineIntent]) -> tuple[dict[HeroId, str], dict[str, str]]:
        heros_bloques: dict[HeroId, str] = {}
        machines_bloquees: dict[str, str] = {}
        acteurs_par_coffre: dict[Position, list[tuple[str, Position]]] = defaultdict(list)
        for id_heros, poussee in hero_pushes.items():
            if poussee.chest_from is not None and poussee.chest_to is not None:
                acteurs_par_coffre[poussee.chest_from].append((f'hero:{id_heros.value}', poussee.chest_to))
        for id_machine, intention in machine_intents.items():
            if intention.chest_from is not None and intention.chest_to is not None:
                acteurs_par_coffre[intention.chest_from].append((f'machine:{id_machine}', intention.chest_to))

        for acteurs in acteurs_par_coffre.values():
            destinations = {destination for _acteur, destination in acteurs}
            if len(destinations) <= 1:
                continue
            hero_entries = [(acteur, dest) for acteur, dest in acteurs if acteur.startswith('hero:')]
            machine_entries = [(acteur, dest) for acteur, dest in acteurs if acteur.startswith('machine:')]
            hero_destinations = {dest for _acteur, dest in hero_entries}
            if len(hero_destinations) > 1:
                for acteur, _dest in hero_entries:
                    heros_bloques[HeroId(acteur.split(':', 1)[1])] = 'opposite_chest_push'
            if hero_entries:
                # Addendum / hero priority: a machine must yield to a hero push
                # that would otherwise collide with the machine/chest movement.
                for acteur, _dest in machine_entries:
                    machines_bloquees[acteur.split(':', 1)[1]] = 'hero_chest_priority'
            else:
                for acteur, _dest in machine_entries:
                    machines_bloquees[acteur.split(':', 1)[1]] = 'opposite_chest_push'

        for id_heros, poussee in hero_pushes.items():
            if id_heros in heros_bloques or poussee.chest_to is None:
                continue
            for intention in machine_intents.values():
                if intention.machine_id in machines_bloquees:
                    continue
                if intention.target == poussee.chest_to and intention.chest_from != poussee.chest_from:
                    # Hero/chest gets the destination; machine yields.
                    machines_bloquees[intention.machine_id] = 'hero_chest_destination_priority'
        return heros_bloques, machines_bloquees

    def _apply_pushes(self, hero_pushes: dict[HeroId, ChestPush], machine_intents: dict[str, MachineIntent], hero_blocked: dict[HeroId, str], machine_blocked: dict[str, str], effective: dict[HeroId, HeroAction], events: list[Event]) -> None:
        groupes: dict[Position, list[tuple[str, Position, ChestPush | None]]] = defaultdict(list)
        for id_heros, poussee in hero_pushes.items():
            if id_heros in hero_blocked:
                self._coerce_wait(id_heros, effective, events, hero_blocked[id_heros])
                continue
            if poussee.chest_from is not None and poussee.chest_to is not None:
                groupes[poussee.chest_from].append((f'hero:{id_heros.value}', poussee.chest_to, poussee))
        for id_machine, intention in machine_intents.items():
            if id_machine in machine_blocked or intention.chest_from is None or intention.chest_to is None:
                continue
            groupes[intention.chest_from].append((f'machine:{id_machine}', intention.chest_to, None))
        for coffre_depart, acteurs in groupes.items():
            if coffre_depart not in self.state.chests:
                for acteur, _destination, _poussee in acteurs:
                    if acteur.startswith('hero:'):
                        self._coerce_wait(HeroId(acteur.split(':', 1)[1]), effective, events, 'coffre déjà déplacé')
                continue
            destinations = {destination for _acteur, destination, _poussee in acteurs}
            if len(destinations) != 1:
                for acteur, _destination, _poussee in acteurs:
                    if acteur.startswith('hero:'):
                        self._coerce_wait(HeroId(acteur.split(':', 1)[1]), effective, events, 'conflit de poussée')
                continue
            coffre_arrivee = next(iter(destinations))
            if len(acteurs) == 1:
                acteur_unique = acteurs[0][0]
                acteur_evenement = acteur_unique.split(':', 1)[1]
            else:
                acteur_evenement = 'MULTI_PUSH'
            self._apply_chest_destination(coffre_depart, coffre_arrivee, events, acteur_evenement)
            for acteur, _destination, poussee in acteurs:
                if not acteur.startswith('hero:') or poussee is None:
                    continue
                id_heros = HeroId(acteur.split(':', 1)[1])
                heros = self.state.heroes[id_heros]
                if heros.is_hacking:
                    self._unhack(id_heros, events)
                heros.stamina -= 5
                heros.position = poussee.hero_to
                self._collect_for_hero(id_heros, events)

    def _apply_machine_moves(self, intentions: dict[str, MachineIntent], blocked: dict[str, str], events: list[Event]) -> set[str]:
        deplaces: set[str] = set()
        anciennes_positions = {id_machine: self.state.machines[id_machine].position for id_machine in intentions}
        for id_machine, intention in intentions.items():
            machine = self.state.machines[id_machine]
            if id_machine in blocked:
                if intention.controlled:
                    self._wait_controlled_blocked(machine, events, blocked[id_machine])
                else:
                    self._rotate_automatic_blocked(machine, events, blocked[id_machine])
                continue
            machine.pending_move = False
            machine.auto_move_pending = False
            machine.position = intention.target
            if machine.kind == MachineKind.EXCAVATOR and not intention.controlled:
                machine.steps_since_dig += 1
            machine.last_action = MachineAction.MOVE
            if machine.hacked_by is not None:
                conducteur = self.state.heroes[machine.hacked_by]
                conducteur.position = machine.position
            ancien = anciennes_positions[id_machine]
            self._event(events, 'MACHINE_MOVED', f'{id_machine} termine son déplacement.', actor=id_machine, position=machine.position, from_row=ancien.row, from_col=ancien.col)
            deplaces.add(id_machine)
        for id_machine in sorted(deplaces):
            machine = self.state.machines[id_machine]
            heros_ici = sorted([h for h in self.state.heroes.values() if h.position == machine.position], key=lambda h: h.id.value)
            if machine.position in self.state.stones:
                if heros_ici:
                    self.state.stones.remove(machine.position)
                    heros_ici[0].stones += 1
                    self._event(events, 'STONE_COLLECTED', f"{heros_ici[0].id.value} récupère la pierre à l'arrivée de {id_machine}.", actor=heros_ici[0].id.value, position=machine.position)
                else:
                    self.state.stones.remove(machine.position)
                    machine.carried_stones += 1
                    self._event(events, 'STONE_PICKED_BY_MACHINE', f'{id_machine} ramasse une pierre.', actor=id_machine, position=machine.position)
            for heros in heros_ici:
                self._steal_machine_stones(heros.id, events)
        return deplaces

    def _queue_automatic_moves(self, eligible: list[str], events: list[Event]) -> None:
        intentions: dict[str, MachineIntent] = {}
        bloques_initiaux: dict[str, str] = {}
        for id_machine in eligible:
            machine = self.state.machines[id_machine]
            intention, raison = self._build_machine_intent(machine, controlled=False)
            if intention is None:
                bloques_initiaux[id_machine] = raison or 'blocked'
            else:
                intentions[id_machine] = intention
        bloques = self._resolve_machine_intents(intentions, bloques_initiaux)
        for id_machine in eligible:
            machine = self.state.machines[id_machine]
            if id_machine in bloques:
                self._rotate_automatic_blocked(machine, events, bloques[id_machine])
                continue
            machine.auto_move_pending = True
            machine.last_action = MachineAction.MOVE
            self._event(events, 'MACHINE_MOVE_QUEUED', f'{id_machine} commence un MOVE de 2 ticks.', actor=id_machine)

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
                    if machine.pending_move:
                        self._coerce_wait(id_heros, effectif, evenements, 'HACK_MOVE déjà en cours')
                        continue
                    if not Rules.machine_forward_queueable(self.state, machine):
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
        hero_pushes: dict[HeroId, ChestPush] = {}
        for id_heros, action in effectif.items():
            if action not in PUSH_ACTIONS:
                continue
            poussee = Rules.chest_push(self.state, self.state.heroes[id_heros], action)
            if not poussee.valid:
                self._coerce_wait(id_heros, effectif, evenements, poussee.reason or 'poussée invalide')
                continue
            hero_pushes[id_heros] = poussee
        pretes: dict[str, bool] = {}
        for id_machine, machine in self.state.machines.items():
            if machine.is_hacked:
                if controle_attente_avant[id_machine] and machine.pending_move:
                    pretes[id_machine] = True
            elif machine.resume_delay == 0 and auto_attente_avant[id_machine] and machine.auto_move_pending:
                pretes[id_machine] = False
        intentions: dict[str, MachineIntent] = {}
        bloques_geom: dict[str, str] = {}
        for id_machine, controlee in pretes.items():
            machine = self.state.machines[id_machine]
            intention, raison = self._build_machine_intent(machine, controlled=controlee)
            if intention is None:
                bloques_geom[id_machine] = raison or 'blocked'
            else:
                intentions[id_machine] = intention
        for id_machine, raison in bloques_geom.items():
            machine = self.state.machines[id_machine]
            if pretes[id_machine]:
                self._wait_controlled_blocked(machine, evenements, raison)
            else:
                self._rotate_automatic_blocked(machine, evenements, raison)
        heros_bloques, machines_bloquees_poussee = self._hero_machine_push_conflicts(hero_pushes, intentions)
        machines_bloquees = self._resolve_machine_intents(intentions, machines_bloquees_poussee)
        self._apply_pushes(hero_pushes, intentions, heros_bloques, machines_bloquees, effectif, evenements)
        machines_traitees = set(pretes)
        self._apply_machine_moves(intentions, machines_bloquees, evenements)
        eligibles_queue: list[str] = []
        for id_machine in sorted(self.state.machines):
            machine = self.state.machines[id_machine]
            if id_machine in machines_traitees:
                continue
            if machine.is_hacked:
                if machine.kind == MachineKind.GRAPPLER and machine.position in self.state.trees:
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
            eligibles_queue.append(id_machine)
        if eligibles_queue:
            self._queue_automatic_moves(eligibles_queue, evenements)
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
                reason = getattr(strategy, 'stop_reason', None)
                self.state.end_reason = reason or 'STRATEGY_END_GAME'
                break
            self.step(strategy.next_actions(self.state))
        return self.result()

    def result(self) -> SimulationResult:
        return SimulationResult(simulation_id=str(uuid4()), initial_snapshot=self.initial_snapshot, ticks=list(self.ticks), final_snapshot=snapshot_state(self.state), score=compute_score(self.state), actions_text=build_actions_text(self.ticks, self.state.game_map.time_limit))
