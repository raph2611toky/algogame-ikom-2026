from __future__ import annotations
from dataclasses import dataclass
from app.domain.enums import (
    ACTION_TO_DIRECTION,
    CLOCKWISE,
    COUNTER_CLOCKWISE,
    DIRECTION_VECTORS,
    ORIENTATION_TO_DIRECTION,
    HeroAction,
    HeroId,
    MachineKind,
    Orientation,
)
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

    # ------------------------------------------------------------------
    # Elevation helpers (GDD Addendum)
    # ------------------------------------------------------------------
    @staticmethod
    def elevation(state: GameState, pos: Position) -> int:
        return state.game_map.elevation_at(pos)

    @staticmethod
    def hero_elevation_reason(state: GameState, start: Position, destination: Position) -> str | None:
        """Validate only the elevation delta for a hero move.

        Legacy maps without elevation use 0 everywhere, therefore this method
        naturally preserves the old flat-map behaviour.
        """
        start_alt = Rules.elevation(state, start)
        end_alt = Rules.elevation(state, destination)
        delta = end_alt - start_alt
        if delta >= 3:
            return 'elevation_uphill_too_steep'
        if delta <= -5:
            return 'elevation_downhill_cliff_too_steep'
        return None

    @staticmethod
    def hero_walk_stamina_cost(state: GameState, start: Position, destination: Position) -> int:
        start_alt = Rules.elevation(state, start)
        end_alt = Rules.elevation(state, destination)
        if end_alt > start_alt:
            return 3
        if end_alt < start_alt:
            return 0
        return 1

    @staticmethod
    def hero_chest_elevation_reason(state: GameState, chest_from: Position, chest_to: Position) -> str | None:
        # Heroes may push only on the same level or downhill. A >=5-level drop
        # is legal as a push but the chest is destroyed by the simulator.
        if Rules.elevation(state, chest_to) > Rules.elevation(state, chest_from):
            return 'chest_uphill_forbidden_for_hero'
        return None

    @staticmethod
    def machine_elevation_reason(state: GameState, start: Position, destination: Position) -> str | None:
        if abs(Rules.elevation(state, destination) - Rules.elevation(state, start)) >= 5:
            return 'machine_elevation_difference_too_high'
        return None

    @staticmethod
    def machine_chest_elevation_reason(state: GameState, chest_from: Position, chest_to: Position) -> str | None:
        # Machines may push a chest uphill by at most 2 levels. Downhill is
        # allowed; a >=5-level drop destroys the chest later.
        uphill = Rules.elevation(state, chest_to) - Rules.elevation(state, chest_from)
        if uphill >= 3:
            return 'machine_chest_uphill_too_steep'
        return None

    @staticmethod
    def chest_destroyed_by_cliff(state: GameState, chest_from: Position, chest_to: Position) -> bool:
        return Rules.elevation(state, chest_from) - Rules.elevation(state, chest_to) >= 5

    # ------------------------------------------------------------------
    # Hero moves
    # ------------------------------------------------------------------
    @staticmethod
    def hero_move(state: GameState, hero: HeroState, action: HeroAction) -> HeroMove:
        delta_ligne, delta_col = Rules.direction_delta(action)
        adjacent = hero.position.moved(delta_ligne, delta_col)
        carte_jeu = state.game_map
        if not carte_jeu.in_bounds(adjacent):
            return HeroMove(False, hero.position, reason='outside_map')
        if adjacent in carte_jeu.rocks:
            return HeroMove(False, hero.position, reason='rock')

        # F and M are allowed to walk ON a chest. Only holes/trees trigger the
        # special two-cell skip. This matches the FAQ clarification for ...F*...
        if hero.id == HeroId.IKOTOFOSA and adjacent in state.holes:
            atterrissage = adjacent.moved(delta_ligne, delta_col)
            if not carte_jeu.in_bounds(atterrissage):
                return HeroMove(False, hero.position, reason='hop_outside_map')
            if atterrissage in carte_jeu.rocks or atterrissage in state.trees or atterrissage in state.holes:
                return HeroMove(False, hero.position, reason='invalid_hop_landing')
            elevation_reason = Rules.hero_elevation_reason(state, hero.position, atterrissage)
            if elevation_reason is not None:
                return HeroMove(False, hero.position, reason=elevation_reason)
            if hero.stamina < 10:
                return HeroMove(False, hero.position, reason='not_enough_stamina')
            return HeroMove(True, atterrissage, stamina_cost=10, jumped=True)

        if hero.id == HeroId.IMAHAKI and adjacent in state.trees:
            atterrissage = adjacent.moved(delta_ligne, delta_col)
            if not carte_jeu.in_bounds(atterrissage):
                return HeroMove(False, hero.position, reason='climb_outside_map')
            if atterrissage in carte_jeu.rocks or atterrissage in state.trees or atterrissage in state.holes:
                return HeroMove(False, hero.position, reason='invalid_climb_landing')
            elevation_reason = Rules.hero_elevation_reason(state, hero.position, atterrissage)
            if elevation_reason is not None:
                return HeroMove(False, hero.position, reason=elevation_reason)
            if hero.stamina < 10:
                return HeroMove(False, hero.position, reason='not_enough_stamina')
            return HeroMove(True, atterrissage, stamina_cost=10, jumped=True)

        if adjacent in state.trees:
            return HeroMove(False, hero.position, reason='tree')
        if adjacent in state.holes:
            return HeroMove(False, hero.position, reason='hole')

        elevation_reason = Rules.hero_elevation_reason(state, hero.position, adjacent)
        if elevation_reason is not None:
            return HeroMove(False, hero.position, reason=elevation_reason)
        stamina_cost = Rules.hero_walk_stamina_cost(state, hero.position, adjacent)
        if hero.stamina < stamina_cost:
            return HeroMove(False, hero.position, reason='not_enough_stamina')
        return HeroMove(True, adjacent, stamina_cost=stamina_cost)

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
        # PUSH also advances the hero into the chest's previous cell. The hero
        # movement itself must therefore respect the same +2 / -4 elevation
        # limits as a normal move. The chest has its own, separate rule below.
        hero_step_reason = Rules.hero_elevation_reason(state, hero.position, coffre_depart)
        if hero_step_reason is not None:
            return ChestPush(False, reason=f'hero_push_step_{hero_step_reason}')
        elevation_reason = Rules.hero_chest_elevation_reason(state, coffre_depart, coffre_arrivee)
        if elevation_reason is not None:
            return ChestPush(False, reason=elevation_reason)
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
                # New addendum gives the hero/chest movement priority. The
                # simulator blocks the machine rather than the hero.
                continue
            if cible == push.chest_from and cible in state.chests:
                delta_ligne = cible.row - machine.position.row
                delta_col = cible.col - machine.position.col
                destination_machine = cible.moved(delta_ligne, delta_col)
                if destination_machine != push.chest_to:
                    return False
        return True

    # ------------------------------------------------------------------
    # Machine look-ahead
    # ------------------------------------------------------------------
    @staticmethod
    def compatible_machine(hero: HeroState, machine: MachineState) -> bool:
        return hero.id == HeroId.IKOTOFOSA and machine.kind == MachineKind.EXCAVATOR or (hero.id == HeroId.IMAHAKI and machine.kind == MachineKind.GRAPPLER)

    @staticmethod
    def machine_forward(machine: MachineState) -> Position:
        direction = ORIENTATION_TO_DIRECTION[machine.orientation]
        delta_ligne, delta_col = DIRECTION_VECTORS[direction]
        return machine.position.moved(delta_ligne, delta_col)

    @staticmethod
    def _forward_geometry(position: Position, orientation: Orientation) -> tuple[tuple[int, int], tuple[int, int], Position]:
        direction = ORIENTATION_TO_DIRECTION[orientation]
        dr, dc = DIRECTION_VECTORS[direction]
        # Perpendicular "left" vector. For FACING_RIGHT this is UP, giving the
        # exact user diagram: ..3. / .G12 / ..4.
        side = (-dc, dr)
        destination = position.moved(dr, dc)
        return (dr, dc), side, destination

    @staticmethod
    def machine_move_lookahead_positions(
        machine: MachineState,
        *,
        position: Position | None = None,
        orientation: Orientation | None = None,
    ) -> tuple[Position, Position, Position, Position]:
        """Ordered positions 1..4 from the clarified diagram.

        FACING_RIGHT:
            ..3.
            .G12
            ..4.

        Position 1 is the actual destination. Positions 2/3/4 are the GDD
        look-ahead cells (two-ahead and the two side cells around destination).
        """
        origin = position or machine.position
        facing = orientation or machine.orientation
        (dr, dc), (sr, sc), destination = Rules._forward_geometry(origin, facing)
        return (
            destination,
            destination.moved(dr, dc),
            destination.moved(sr, sc),
            destination.moved(-sr, -sc),
        )

    @staticmethod
    def machine_chest_lookahead_positions(
        machine: MachineState,
        *,
        position: Position | None = None,
        orientation: Orientation | None = None,
    ) -> tuple[tuple[Position, Position, Position], tuple[Position, Position, Position]]:
        """Return the 3 hero-sensitive + 3 extra machine-sensitive cells.

        This rotates the page-2 diagram for every orientation.  For a chest
        directly in front, all six cells are checked for machines; the first
        three are also checked for F/M.
        """
        origin = position or machine.position
        facing = orientation or machine.orientation
        (dr, dc), (sr, sc), chest_from = Rules._forward_geometry(origin, facing)
        chest_to = chest_from.moved(dr, dc)
        first_three = (
            chest_from.moved(sr, sc),
            chest_to,
            chest_from.moved(-sr, -sc),
        )
        extra_three = (
            chest_to.moved(sr, sc),
            chest_to.moved(dr, dc),
            chest_to.moved(-sr, -sc),
        )
        return first_three, extra_three

    @staticmethod
    def machine_lookahead_reason(
        state: GameState,
        machine: MachineState,
        *,
        position: Position | None = None,
        orientation: Orientation | None = None,
        ignore_machines: bool = False,
        check_heroes: bool = True,
    ) -> str | None:
        """Hardcoded collision look-ahead, evaluated before elevation.

        - other machines in destination/two-ahead/side positions block any MOVE;
        - when pushing a chest, machines are checked in the six GDD cells and
          heroes in the three cells closest to the chest;
        - when a chest is adjacent to the destination cell, a hero standing
          behind that chest has priority because it could push into destination.
        """
        origin = position or machine.position
        facing = orientation or machine.orientation
        other_machine_positions = {
            other.position for other in state.machines.values() if other.id != machine.id
        }

        if not ignore_machines:
            for index, pos in enumerate(
                Rules.machine_move_lookahead_positions(machine, position=origin, orientation=facing),
                start=1,
            ):
                if pos in other_machine_positions:
                    return f'machine_lookahead_{index}'

        (dr, dc), (sr, sc), destination = Rules._forward_geometry(origin, facing)
        if destination in state.chests:
            first_three, extra_three = Rules.machine_chest_lookahead_positions(
                machine, position=origin, orientation=facing
            )
            if not ignore_machines:
                for index, pos in enumerate(first_three + extra_three, start=1):
                    if pos in other_machine_positions:
                        return f'chest_machine_lookahead_{index}'
            if check_heroes:
                hero_positions = {hero.position for hero in state.heroes.values()}
                for index, pos in enumerate(first_three, start=1):
                    if pos in hero_positions:
                        return f'chest_hero_priority_{index}'
        elif check_heroes:
            # Nearby chest next to the destination cell: check the three cells
            # other than the machine's origin, and the hero one cell behind it.
            hero_positions = {hero.position for hero in state.heroes.values()}
            for index, (vr, vc) in enumerate(((dr, dc), (sr, sc), (-sr, -sc)), start=1):
                chest_pos = destination.moved(vr, vc)
                hero_pos = chest_pos.moved(vr, vc)
                if chest_pos in state.chests and hero_pos in hero_positions:
                    return f'nearby_chest_hero_priority_{index}'
        return None

    @staticmethod
    def machine_buffer_reason(
        state: GameState,
        machine: MachineState,
        *,
        position: Position | None = None,
        orientation=None,
        ignore_machines: bool = False,
    ) -> str | None:
        # Compatibility name used by V8/V10. Its implementation now follows the
        # official addendum look-ahead rather than the older approximate buffer.
        return Rules.machine_lookahead_reason(
            state,
            machine,
            position=position,
            orientation=orientation,
            ignore_machines=ignore_machines,
            check_heroes=True,
        )

    @staticmethod
    def machine_cell_passable(
        state: GameState,
        machine: MachineState,
        cible: Position,
        *,
        start: Position | None = None,
    ) -> bool:
        origin = start or machine.position
        if not state.game_map.in_bounds(cible):
            return False
        if cible in state.game_map.rocks:
            return False
        if Rules.machine_elevation_reason(state, origin, cible) is not None:
            return False
        if machine.kind == MachineKind.EXCAVATOR and cible in state.trees:
            return False
        if machine.kind == MachineKind.GRAPPLER and cible in state.holes:
            return False
        return True

    @staticmethod
    def machine_forward_queueable(state: GameState, machine: MachineState) -> bool:
        # Look-ahead has explicit priority over elevation checks.
        if Rules.machine_lookahead_reason(state, machine) is not None:
            return False
        cible = Rules.machine_forward(machine)
        if not Rules.machine_cell_passable(state, machine, cible):
            return False
        if cible in state.chests:
            return Rules.machine_can_push_chest(state, machine, cible, ignore_machines=False, skip_lookahead=True)
        return True

    @staticmethod
    def machine_forward_clear(state: GameState, machine: MachineState, *, ignore_machines: bool=False) -> bool:
        if Rules.machine_lookahead_reason(state, machine, ignore_machines=ignore_machines) is not None:
            return False
        cible = Rules.machine_forward(machine)
        if not Rules.machine_cell_passable(state, machine, cible):
            return False
        if cible in state.chests:
            return Rules.machine_can_push_chest(
                state,
                machine,
                cible,
                ignore_machines=ignore_machines,
                skip_lookahead=True,
            )
        return True

    @staticmethod
    def machine_can_push_chest(
        state: GameState,
        machine: MachineState,
        chest_pos: Position,
        *,
        ignore_machines: bool=False,
        skip_lookahead: bool=False,
    ) -> bool:
        if not skip_lookahead and Rules.machine_lookahead_reason(
            state, machine, ignore_machines=ignore_machines
        ) is not None:
            return False
        # The machine itself moves into chest_pos, so its own elevation movement
        # constraint is evaluated independently from the chest's movement.
        if Rules.machine_elevation_reason(state, machine.position, chest_pos) is not None:
            return False
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
        if Rules.machine_chest_elevation_reason(state, chest_pos, destination) is not None:
            return False
        return True

    @staticmethod
    def rotate_cw(machine: MachineState) -> None:
        machine.orientation = CLOCKWISE[machine.orientation]

    @staticmethod
    def rotate_ccw(machine: MachineState) -> None:
        machine.orientation = COUNTER_CLOCKWISE[machine.orientation]
