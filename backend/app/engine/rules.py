from __future__ import annotations
from dataclasses import dataclass
from app.domain.enums import ACTION_TO_DIRECTION, CLOCKWISE, COUNTER_CLOCKWISE, DIRECTION_VECTORS, ORIENTATION_TO_DIRECTION, HeroAction, HeroId, MachineKind
from app.domain.models import GameState, HeroState, MachineState, Position

@dataclass(frozen=True, slots=True)
class HeroMove:
    valid: bool
    destination: Position
    stamina_cost: int = 0
    jumped: bool = False
    reason: str | None = None

@dataclass(frozen=True, slots=True)
class ChestPush:
    valid: bool
    chest_from: Position | None = None
    chest_to: Position | None = None
    hero_to: Position | None = None
    reason: str | None = None

class Rules:

    @staticmethod
    def direction_delta(action: HeroAction) -> tuple[int, int]:
        direction = ACTION_TO_DIRECTION[action]
        return DIRECTION_VECTORS[direction]

    @staticmethod
    def hero_move(state: GameState, hero: HeroState, action: HeroAction) -> HeroMove:
        delta_ligne, delta_col = Rules.direction_delta(action)
        adjacent = hero.position.moved(delta_ligne, delta_col)
        carte_jeu = state.game_map
        if not carte_jeu.in_bounds(adjacent):
            return HeroMove(False, hero.position, reason='outside_map')
        if adjacent in carte_jeu.rocks:
            return HeroMove(False, hero.position, reason='rock')
        if hero.id == HeroId.IKOTOFOSA and adjacent in state.holes:
            atterrissage = adjacent.moved(delta_ligne, delta_col)
            if not carte_jeu.in_bounds(atterrissage):
                return HeroMove(False, hero.position, reason='hop_outside_map')
            if atterrissage in carte_jeu.rocks or atterrissage in state.trees or atterrissage in state.holes:
                return HeroMove(False, hero.position, reason='invalid_hop_landing')
            if hero.stamina < 10:
                return HeroMove(False, hero.position, reason='not_enough_stamina')
            return HeroMove(True, atterrissage, stamina_cost=10, jumped=True)
        if hero.id == HeroId.IMAHAKI and adjacent in state.trees:
            atterrissage = adjacent.moved(delta_ligne, delta_col)
            if not carte_jeu.in_bounds(atterrissage):
                return HeroMove(False, hero.position, reason='climb_outside_map')
            if atterrissage in carte_jeu.rocks or atterrissage in state.trees or atterrissage in state.holes:
                return HeroMove(False, hero.position, reason='invalid_climb_landing')
            if hero.stamina < 10:
                return HeroMove(False, hero.position, reason='not_enough_stamina')
            return HeroMove(True, atterrissage, stamina_cost=10, jumped=True)
        if adjacent in state.trees:
            return HeroMove(False, hero.position, reason='tree')
        if adjacent in state.holes:
            return HeroMove(False, hero.position, reason='hole')
        if hero.stamina < 1:
            return HeroMove(False, hero.position, reason='not_enough_stamina')
        return HeroMove(True, adjacent, stamina_cost=1)

    @staticmethod
    def chest_push(state: GameState, hero: HeroState, action: HeroAction) -> ChestPush:
        delta_ligne, delta_col = Rules.direction_delta(action)
        coffre_depart = hero.position.moved(delta_ligne, delta_col)
        coffre_arrivee = coffre_depart.moved(delta_ligne, delta_col)
        if hero.stamina < 5:
            return ChestPush(False, reason='not_enough_stamina')
        if coffre_depart not in state.chests:
            return ChestPush(False, reason='no_chest')
        if not state.game_map.in_bounds(coffre_arrivee):
            return ChestPush(False, reason='chest_outside_map')
        if coffre_arrivee in state.game_map.rocks:
            return ChestPush(False, reason='rock')
        if coffre_arrivee in state.trees:
            return ChestPush(False, reason='tree')
        if coffre_arrivee in state.chests:
            return ChestPush(False, reason='another_chest')
        if state.machine_at(coffre_arrivee) is not None:
            return ChestPush(False, reason='machine_behind_chest')
        return ChestPush(True, chest_from=coffre_depart, chest_to=coffre_arrivee, hero_to=coffre_depart)

    @staticmethod
    def hero_chest_push_safe_this_tick(state: GameState, push: ChestPush) -> bool:
        if not push.valid or push.chest_from is None or push.chest_to is None:
            return False
        for machine in state.machines.values():
            if machine.is_hacked:
                prete = machine.pending_move
            else:
                prete = machine.resume_delay == 0 and machine.auto_move_pending
            if not prete:
                continue
            cible = Rules.machine_forward(machine)
            if cible == push.chest_to:
                return False
            if cible == push.chest_from and cible in state.chests:
                delta_ligne = cible.row - machine.position.row
                delta_col = cible.col - machine.position.col
                destination_machine = cible.moved(delta_ligne, delta_col)
                if destination_machine != push.chest_to:
                    return False
        return True

    @staticmethod
    def compatible_machine(hero: HeroState, machine: MachineState) -> bool:
        return hero.id == HeroId.IKOTOFOSA and machine.kind == MachineKind.EXCAVATOR or (hero.id == HeroId.IMAHAKI and machine.kind == MachineKind.GRAPPLER)

    @staticmethod
    def machine_forward(machine: MachineState) -> Position:
        direction = ORIENTATION_TO_DIRECTION[machine.orientation]
        delta_ligne, delta_col = DIRECTION_VECTORS[direction]
        return machine.position.moved(delta_ligne, delta_col)

    @staticmethod
    def machine_cell_passable(state: GameState, machine: MachineState, cible: Position) -> bool:
        if not state.game_map.in_bounds(cible):
            return False
        if cible in state.game_map.rocks:
            return False
        if machine.kind == MachineKind.EXCAVATOR and cible in state.trees:
            return False
        if machine.kind == MachineKind.GRAPPLER and cible in state.holes:
            return False
        return True

    @staticmethod
    def machine_forward_queueable(state: GameState, machine: MachineState) -> bool:
        cible = Rules.machine_forward(machine)
        if not Rules.machine_cell_passable(state, machine, cible):
            return False
        if cible in state.chests:
            return Rules.machine_can_push_chest(state, machine, cible, ignore_machines=False)
        return True

    @staticmethod
    def machine_forward_clear(state: GameState, machine: MachineState, *, ignore_machines: bool=False) -> bool:
        cible = Rules.machine_forward(machine)
        if not Rules.machine_cell_passable(state, machine, cible):
            return False
        if not ignore_machines:
            for autre in state.machines.values():
                if autre.id != machine.id and autre.position == cible:
                    return False
        if cible in state.chests:
            return Rules.machine_can_push_chest(state, machine, cible, ignore_machines=ignore_machines)
        return True

    @staticmethod
    def machine_can_push_chest(state: GameState, machine: MachineState, chest_pos: Position, *, ignore_machines: bool=False) -> bool:
        direction = ORIENTATION_TO_DIRECTION[machine.orientation]
        delta_ligne, delta_col = DIRECTION_VECTORS[direction]
        destination = chest_pos.moved(delta_ligne, delta_col)
        if not state.game_map.in_bounds(destination):
            return False
        if destination in state.game_map.rocks:
            return False
        if destination in state.trees:
            return False
        if destination in state.chests:
            return False
        if not ignore_machines and state.machine_at(destination) is not None:
            return False
        return True

    @staticmethod
    def rotate_cw(machine: MachineState) -> None:
        machine.orientation = CLOCKWISE[machine.orientation]

    @staticmethod
    def rotate_ccw(machine: MachineState) -> None:
        machine.orientation = COUNTER_CLOCKWISE[machine.orientation]
