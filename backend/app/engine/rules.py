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

    @staticmethod
    def hero_move(state: GameState, hero: HeroState, action: HeroAction) -> HeroMove:
        dr, dc = Rules.direction_delta(action)
        adjacent = hero.position.moved(dr, dc)
        game_map = state.game_map

        if not game_map.in_bounds(adjacent):
            return HeroMove(False, hero.position, reason="outside_map")
        if adjacent in game_map.rocks:
            return HeroMove(False, hero.position, reason="rock")

        if hero.id == HeroId.IKOTOFOSA and adjacent in state.holes:
            landing = adjacent.moved(dr, dc)
            if not game_map.in_bounds(landing):
                return HeroMove(False, hero.position, reason="hop_outside_map")
            if landing in game_map.rocks or landing in state.trees or landing in state.holes:
                return HeroMove(False, hero.position, reason="invalid_hop_landing")
            if hero.stamina < 10:
                return HeroMove(False, hero.position, reason="not_enough_stamina")
            return HeroMove(True, landing, stamina_cost=10, jumped=True)

        if hero.id == HeroId.IMAHAKI and adjacent in state.trees:
            landing = adjacent.moved(dr, dc)
            if not game_map.in_bounds(landing):
                return HeroMove(False, hero.position, reason="climb_outside_map")
            if landing in game_map.rocks or landing in state.trees or landing in state.holes:
                return HeroMove(False, hero.position, reason="invalid_climb_landing")
            if hero.stamina < 10:
                return HeroMove(False, hero.position, reason="not_enough_stamina")
            return HeroMove(True, landing, stamina_cost=10, jumped=True)

        # The other hero-specific blocker remains impassable.
        if adjacent in state.trees:
            return HeroMove(False, hero.position, reason="tree")
        if adjacent in state.holes:
            return HeroMove(False, hero.position, reason="hole")
        if hero.stamina < 1:
            return HeroMove(False, hero.position, reason="not_enough_stamina")
        return HeroMove(True, adjacent, stamina_cost=1)

    @staticmethod
    def chest_push(state: GameState, hero: HeroState, action: HeroAction) -> ChestPush:
        dr, dc = Rules.direction_delta(action)
        chest_from = hero.position.moved(dr, dc)
        chest_to = chest_from.moved(dr, dc)
        if hero.stamina < 5:
            return ChestPush(False, reason="not_enough_stamina")
        if chest_from not in state.chests:
            return ChestPush(False, reason="no_chest")
        if not state.game_map.in_bounds(chest_to):
            return ChestPush(False, reason="chest_outside_map")
        if chest_to in state.game_map.rocks:
            return ChestPush(False, reason="rock")
        if chest_to in state.trees:
            return ChestPush(False, reason="tree")
        if chest_to in state.chests:
            return ChestPush(False, reason="another_chest")
        return ChestPush(True, chest_from=chest_from, chest_to=chest_to, hero_to=chest_from)

    @staticmethod
    def compatible_machine(hero: HeroState, machine: MachineState) -> bool:
        return (
            hero.id == HeroId.IKOTOFOSA and machine.kind == MachineKind.EXCAVATOR
        ) or (
            hero.id == HeroId.IMAHAKI and machine.kind == MachineKind.GRAPPLER
        )

    @staticmethod
    def machine_forward(machine: MachineState) -> Position:
        direction = ORIENTATION_TO_DIRECTION[machine.orientation]
        dr, dc = DIRECTION_VECTORS[direction]
        return machine.position.moved(dr, dc)

    @staticmethod
    def machine_forward_clear(state: GameState, machine: MachineState) -> bool:
        target = Rules.machine_forward(machine)
        if not state.game_map.in_bounds(target):
            return False
        if target in state.game_map.rocks:
            return False
        for other in state.machines.values():
            if other.id != machine.id and other.position == target:
                return False
        if machine.kind == MachineKind.EXCAVATOR and target in state.trees:
            return False
        if machine.kind == MachineKind.GRAPPLER and target in state.holes:
            return False
        if target in state.chests:
            return Rules.machine_can_push_chest(state, machine, target)
        return True

    @staticmethod
    def machine_can_push_chest(
        state: GameState, machine: MachineState, chest_pos: Position
    ) -> bool:
        direction = ORIENTATION_TO_DIRECTION[machine.orientation]
        dr, dc = DIRECTION_VECTORS[direction]
        destination = chest_pos.moved(dr, dc)
        if not state.game_map.in_bounds(destination):
            return False
        if destination in state.game_map.rocks:
            return False
        if destination in state.trees:
            return False
        if destination in state.chests:
            return False
        return True

    @staticmethod
    def rotate_cw(machine: MachineState) -> None:
        machine.orientation = CLOCKWISE[machine.orientation]

    @staticmethod
    def rotate_ccw(machine: MachineState) -> None:
        machine.orientation = COUNTER_CLOCKWISE[machine.orientation]
