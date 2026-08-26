from __future__ import annotations

import copy
import math
import uuid

from app.domain.enums import (
    Difficulty,
    Direction,
    GameStatus,
    GuardMode,
    HeroAction,
    HeroId,
    MachineKind,
    NoiseKind,
)
from app.domain.models import (
    BalanceConfig,
    Event,
    GameMap,
    GameState,
    GuardState,
    HeroCommand,
    HeroState,
    NoiseEvent,
    Position,
)
from app.engine.guard_ai import EasyGuardAI, HardGuardAI, MediumGuardAI
from app.engine.rules import (
    NOISE_RADIUS,
    adjacent,
    cooldown_from_speed,
    elevation_allowed,
    guard_step_allowed,
    hero_destination,
    hero_speed,
    machine_step_allowed,
    next_position,
)
from app.engine.perception import update_perception


class Simulator:
    """Boucle de jeu autoritaire à pas fixe (100 ms par défaut)."""

    def __init__(self, state: GameState):
        self.state = state
        self._guard_ai = {
            Difficulty.EASY: EasyGuardAI(),
            Difficulty.MEDIUM: MediumGuardAI(),
            Difficulty.HARD: HardGuardAI(),
        }[state.difficulty]

    @staticmethod
    def initial_state(
        game_map: GameMap,
        *,
        difficulty: Difficulty = Difficulty.MEDIUM,
        seed: int = 1,
        balance: BalanceConfig | None = None,
        game_id: str | None = None,
    ) -> GameState:
        if game_map.initial_guard is None:
            raise ValueError("La carte doit contenir un gardien.")
        return GameState(
            id=game_id or str(uuid.uuid4()),
            game_map=game_map,
            difficulty=difficulty,
            seed=seed,
            balance=balance or BalanceConfig(),
            heroes={
                hero_id: HeroState(hero_id, position)
                for hero_id, position in game_map.initial_heroes.items()
            },
            guard=GuardState(game_map.initial_guard),
            machines={machine.id: copy.deepcopy(machine) for machine in game_map.initial_machines},
            trees=set(game_map.trees),
            holes=set(game_map.holes),
            stones=set(game_map.initial_stones),
            chests=set(game_map.initial_chests),
        )

    def step(self, commands: dict[HeroId, HeroCommand] | None = None) -> GameState:
        state = self.state
        state.events = []
        if state.status != GameStatus.ACTIVE:
            return state
        commands = commands or {}
        normalized = {hero_id: commands.get(hero_id, HeroCommand()) for hero_id in HeroId}

        self._advance_timers()
        self._complete_heals()
        self._hero_actions(normalized)
        self._collect_stones()
        self._move_autonomous_machines()
        update_perception(state)
        self._move_guard()
        self._guard_hits()

        state.elapsed_ticks += 1
        state.version += 1
        self._check_end_conditions()
        state.score = self._score()
        return state

    def _event(
        self,
        type_: str,
        message: str,
        *,
        actor: str | None = None,
        position: Position | None = None,
        **data: object,
    ) -> None:
        self.state.events.append(Event(type_, message, actor, position, data))

    def _noise(self, position: Position, kind: NoiseKind, source: str) -> None:
        self.state.noises.append(
            NoiseEvent(position, NOISE_RADIUS[kind], ttl=18, kind=kind, source=source)
        )
        self._event("NOISE", f"Bruit {kind.value}", actor=source, position=position, radius=NOISE_RADIUS[kind])

    def _advance_timers(self) -> None:
        for hero in self.state.heroes.values():
            hero.cooldown = max(0, hero.cooldown - 1)
            hero.invulnerable_ticks = max(0, hero.invulnerable_ticks - 1)
            if hero.is_ko and hero.rescue_ticks > 0:
                hero.rescue_ticks -= 1
        for machine in self.state.machines.values():
            machine.cooldown = max(0, machine.cooldown - 1)
        self.state.guard.cooldown = max(0, self.state.guard.cooldown - 1)
        alive_noises: list[NoiseEvent] = []
        for noise in self.state.noises:
            noise.ttl -= 1
            if noise.ttl > 0:
                alive_noises.append(noise)
        self.state.noises = alive_noises

    def _complete_heals(self) -> None:
        for hero in self.state.heroes.values():
            if hero.heal_ticks_remaining <= 0:
                continue
            target = self.state.heroes.get(hero.heal_target or hero.id)
            if target is None or (target.id != hero.id and not adjacent(hero.position, target.position)):
                self._cancel_heal(hero, "Le soin a été interrompu : cible hors de portée.")
                continue
            hero.heal_ticks_remaining -= 1
            if hero.heal_ticks_remaining == 0:
                target.hp = min(self.state.balance.hp_max, target.hp + self.state.balance.heal_amount)
                target.rescue_ticks = 0
                hero.heal_target = None
                hero.heal_charge_reserved = False
                self._event("HEAL_COMPLETED", f"{target.id.value} récupère {self.state.balance.heal_amount} HP.", actor=hero.id.value, position=target.position)

    def _cancel_heal(self, hero: HeroState, reason: str) -> None:
        if hero.heal_charge_reserved:
            self.state.healing_charges += 1
        hero.heal_charge_reserved = False
        hero.heal_ticks_remaining = 0
        hero.heal_target = None
        self._event("HEAL_CANCELLED", reason, actor=hero.id.value, position=hero.position)

    def _ready(self, hero: HeroState) -> bool:
        return not hero.is_ko and hero.carried_by is None and not hero.is_busy

    def _hero_actions(self, commands: dict[HeroId, HeroCommand]) -> None:
        # Les commandes du héros porté sont normalement ignorées, sauf le saut assisté.
        for hero_id in HeroId:
            hero = self.state.heroes[hero_id]
            command = commands[hero_id]
            if hero.carried_by is not None and command.action == HeroAction.ASSISTED_JUMP:
                self._assisted_jump(hero, command)

        movement_commands: dict[HeroId, HeroCommand] = {}
        for hero_id in HeroId:
            hero = self.state.heroes[hero_id]
            command = commands[hero_id]
            if hero.carried_by is not None:
                continue
            if not self._ready(hero):
                continue
            if command.action == HeroAction.WAIT:
                hero.stamina = min(self.state.balance.stamina_max, hero.stamina + 4)
            elif command.action in {HeroAction.MOVE, HeroAction.RUN}:
                movement_commands[hero_id] = command
            elif command.action == HeroAction.PUSH:
                self._push(hero, command)
            elif command.action == HeroAction.HIDE:
                self._hide(hero)
            elif command.action == HeroAction.CARRY:
                self._carry(hero, command)
            elif command.action == HeroAction.DROP:
                self._drop(hero, command)
            elif command.action == HeroAction.HEAL:
                self._start_heal(hero, command)
            elif command.action == HeroAction.USE_MACHINE:
                self._use_machine(hero, command)
            elif command.action == HeroAction.ASSISTED_JUMP:
                self._event("ACTION_REJECTED", "ASSISTED_JUMP doit être déclenché par le héros porté.", actor=hero.id.value)
        self._resolve_hero_movements(movement_commands)

    def _resolve_hero_movements(self, commands: dict[HeroId, HeroCommand]) -> None:
        proposals: dict[HeroId, tuple[Position, str, int, NoiseKind, bool]] = {}
        for hero_id, command in commands.items():
            hero = self.state.heroes[hero_id]
            if command.direction is None:
                self._event("ACTION_REJECTED", "Direction obligatoire.", actor=hero_id.value)
                continue
            running = command.action == HeroAction.RUN
            destination, kind, base_cost, noise_kind = hero_destination(self.state, hero, command.direction)
            cost = base_cost + (5 if running else 0)
            if destination is None:
                self._event("MOVE_BLOCKED", f"Déplacement bloqué : {kind}.", actor=hero_id.value, position=hero.position)
                continue
            if hero.stamina < cost:
                self._event("ACTION_REJECTED", "Stamina insuffisante.", actor=hero_id.value)
                continue
            proposals[hero_id] = (destination, kind, cost, NoiseKind.RUN if running else noise_kind, running)

        if len(proposals) == 2:
            values = list(proposals.items())
            if values[0][1][0] == values[1][1][0]:
                for hero_id in list(proposals):
                    self._event("MOVE_COLLISION", "Deux héros visaient la même cellule.", actor=hero_id.value)
                    del proposals[hero_id]

        for hero_id, proposal in list(proposals.items()):
            destination = proposal[0]
            other_id = HeroId.IMAHAKI if hero_id == HeroId.IKOTOFOSA else HeroId.IKOTOFOSA
            other = self.state.heroes[other_id]
            if other.carried_by is not None:
                continue
            if destination == other.position:
                other_destination = proposals.get(other_id, (None,))[0]
                if other_destination is None:
                    self._event("MOVE_COLLISION", "Cellule occupée par le partenaire.", actor=hero_id.value)
                    del proposals[hero_id]

        for hero_id, (destination, kind, cost, noise_kind, running) in proposals.items():
            hero = self.state.heroes[hero_id]
            hero.position = destination
            hero.hidden = False
            hero.stamina -= cost
            hero.last_direction = commands[hero_id].direction
            hero.cooldown = cooldown_from_speed(hero_speed(hero, self.state, running=running))
            if hero.carrying is not None:
                self.state.heroes[hero.carrying].position = destination
                noise_kind = NoiseKind.CARRY
            self._noise(destination, noise_kind, hero_id.value)
            self._event("HERO_MOVED", kind, actor=hero_id.value, position=destination, cooldown=hero.cooldown)

    def _hide(self, hero: HeroState) -> None:
        if hero.position not in self.state.game_map.bushes:
            self._event("ACTION_REJECTED", "HIDE exige une cachette @.", actor=hero.id.value)
            return
        hero.hidden = True
        hero.cooldown = 4
        self._event("HIDDEN", "Héros caché.", actor=hero.id.value, position=hero.position)

    def _carry(self, hero: HeroState, command: HeroCommand) -> None:
        target_id = command.target or (HeroId.IMAHAKI if hero.id == HeroId.IKOTOFOSA else HeroId.IKOTOFOSA)
        target = self.state.heroes[target_id]
        if hero.carrying is not None or target.carried_by is not None or target.carrying is not None:
            self._event("ACTION_REJECTED", "Portage déjà actif ou incompatible.", actor=hero.id.value)
            return
        if not adjacent(hero.position, target.position):
            self._event("ACTION_REJECTED", "Le partenaire doit être adjacent.", actor=hero.id.value)
            return
        hero.carrying = target_id
        target.carried_by = hero.id
        target.position = hero.position
        target.hidden = False
        hero.hidden = False
        hero.cooldown = 6
        self._noise(hero.position, NoiseKind.CARRY, hero.id.value)
        self._event("CARRY_STARTED", f"{hero.id.value} porte {target_id.value}.", actor=hero.id.value, position=hero.position)

    def _drop(self, hero: HeroState, command: HeroCommand) -> None:
        if hero.carrying is None:
            self._event("ACTION_REJECTED", "Aucun partenaire porté.", actor=hero.id.value)
            return
        directions = [command.direction] if command.direction else list(Direction)
        occupied = {other.position for other in self.state.heroes.values() if other.id != hero.carrying and other.carried_by is None}
        destination = next(
            (
                next_position(hero.position, direction)
                for direction in directions
                if direction is not None
                and self._hero_cell_free(next_position(hero.position, direction))
                and next_position(hero.position, direction) not in occupied
                and elevation_allowed(self.state.game_map, hero.position, next_position(hero.position, direction))
            ),
            None,
        )
        if destination is None:
            self._event("ACTION_REJECTED", "Aucune cellule valide pour déposer.", actor=hero.id.value)
            return
        target = self.state.heroes[hero.carrying]
        target.position = destination
        target.carried_by = None
        hero.carrying = None
        hero.cooldown = 4
        self._event("CARRY_DROPPED", "Partenaire déposé.", actor=hero.id.value, position=destination)

    def _start_heal(self, hero: HeroState, command: HeroCommand) -> None:
        target_id = command.target or hero.id
        target = self.state.heroes[target_id]
        if self.state.healing_charges <= 0:
            self._event("ACTION_REJECTED", "Aucune charge de soin.", actor=hero.id.value)
            return
        if target.hp >= self.state.balance.hp_max:
            self._event("ACTION_REJECTED", "La cible a déjà tous ses HP.", actor=hero.id.value)
            return
        if target.id != hero.id and not adjacent(hero.position, target.position):
            self._event("ACTION_REJECTED", "Le partenaire doit être adjacent.", actor=hero.id.value)
            return
        self.state.healing_charges -= 1
        hero.heal_charge_reserved = True
        hero.heal_target = target.id
        hero.heal_ticks_remaining = (
            self.state.balance.self_heal_ticks if target.id == hero.id else self.state.balance.partner_heal_ticks
        )
        self._noise(hero.position, NoiseKind.HEAL, hero.id.value)
        self._event("HEAL_STARTED", "Canalisation du soin.", actor=hero.id.value, position=hero.position, ticks=hero.heal_ticks_remaining)

    def _push(self, hero: HeroState, command: HeroCommand) -> None:
        if command.direction is None:
            self._event("ACTION_REJECTED", "Direction obligatoire pour PUSH.", actor=hero.id.value)
            return
        chest = next_position(hero.position, command.direction)
        destination = next_position(chest, command.direction)
        if chest not in self.state.chests:
            self._event("ACTION_REJECTED", "Aucun coffre à pousser.", actor=hero.id.value)
            return
        if not self._chest_destination_free(destination):
            self._event("ACTION_REJECTED", "Destination du coffre invalide.", actor=hero.id.value)
            return
        if self.state.game_map.has_elevation and self.state.game_map.elevation_at(destination) > self.state.game_map.elevation_at(chest):
            self._event("ACTION_REJECTED", "Un héros ne peut pas pousser un coffre vers le haut.", actor=hero.id.value)
            return
        if hero.stamina < 5:
            self._event("ACTION_REJECTED", "Stamina insuffisante.", actor=hero.id.value)
            return
        self.state.chests.remove(chest)
        hero.position = chest
        hero.hidden = False
        hero.stamina -= 5
        hero.cooldown = cooldown_from_speed(hero_speed(hero, self.state)) + 3
        if destination in self.state.game_map.bushes or destination in self.state.game_map.exits:
            self.state.secured_chests += 1
            self._event("CHEST_SECURED", "Coffre sécurisé.", actor=hero.id.value, position=destination)
        else:
            self.state.chests.add(destination)
            self._event("CHEST_PUSHED", "Coffre déplacé.", actor=hero.id.value, position=destination)
        self._noise(destination, NoiseKind.IMPACT, hero.id.value)

    def _assisted_jump(self, passenger: HeroState, command: HeroCommand) -> None:
        if command.direction is None or passenger.carried_by is None:
            return
        carrier = self.state.heroes[passenger.carried_by]
        if carrier.cooldown > 0 or carrier.stamina < 15 or passenger.stamina < 10:
            self._event("ACTION_REJECTED", "Saut assisté indisponible.", actor=passenger.id.value)
            return
        destination = next_position(carrier.position, command.direction, 2)
        middle = next_position(carrier.position, command.direction)
        if not self._hero_cell_free(destination):
            self._event("ACTION_REJECTED", "Cellule d’arrivée du saut invalide.", actor=passenger.id.value)
            return
        if middle in self.state.game_map.rocks:
            self._event("ACTION_REJECTED", "Un rocher ne peut pas être franchi.", actor=passenger.id.value)
            return
        if not elevation_allowed(self.state.game_map, carrier.position, destination, max_up=4, max_down=4):
            self._event("ACTION_REJECTED", "Élévation du saut assisté invalide.", actor=passenger.id.value)
            return
        carrier.carrying = None
        passenger.carried_by = None
        passenger.position = destination
        carrier.stamina -= 15
        passenger.stamina -= 10
        carrier.cooldown = 12
        passenger.cooldown = 12
        self._noise(destination, NoiseKind.ASSISTED_JUMP, passenger.id.value)
        self._event("ASSISTED_JUMP", "Saut coopératif réussi.", actor=passenger.id.value, position=destination)

    def _use_machine(self, hero: HeroState, command: HeroCommand) -> None:
        compatible = MachineKind.EXCAVATOR if hero.id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        machine = next(
            (
                item
                for item in self.state.machines.values()
                if item.kind == compatible and adjacent(item.position, hero.position)
            ),
            None,
        )
        if machine is None or command.direction is None or machine.cooldown > 0:
            self._event("ACTION_REJECTED", "Machine compatible, proche et disponible requise.", actor=hero.id.value)
            return
        destination = next_position(machine.position, command.direction)
        if (
            not machine_step_allowed(self.state, machine.position, destination)
            or destination in self.state.chests
            or any(
                other.id != machine.id and other.position == destination
                for other in self.state.machines.values()
            )
        ):
            self._event("ACTION_REJECTED", "Déplacement machine bloqué.", actor=hero.id.value)
            return
        if destination in self.state.holes:
            if machine.kind != MachineKind.EXCAVATOR:
                self._event("ACTION_REJECTED", "Seul l’excavateur comble un trou.", actor=hero.id.value)
                return
            self.state.holes.remove(destination)
            self._event("HOLE_FILLED", "Trou comblé.", actor=hero.id.value, position=destination)
        if destination in self.state.trees:
            if machine.kind != MachineKind.GRAPPLER:
                self._event("ACTION_REJECTED", "Seul le grappler coupe un arbre.", actor=hero.id.value)
                return
            self.state.trees.remove(destination)
            self._event("TREE_CUT", "Arbre coupé.", actor=hero.id.value, position=destination)
        if any(other.position == destination and other.carried_by is None for other in self.state.heroes.values() if other.id != hero.id):
            self._event("ACTION_REJECTED", "Machine bloquée par le partenaire.", actor=hero.id.value)
            return
        machine.position = destination
        machine.orientation = command.direction
        machine.cooldown = cooldown_from_speed(self.state.balance.machine_speed)
        machine.controlled_by = hero.id
        hero.position = destination
        hero.cooldown = machine.cooldown
        if hero.carrying is not None:
            self.state.heroes[hero.carrying].position = destination
        self._noise(destination, NoiseKind.MACHINE, machine.id)
        self._event("MACHINE_MOVED", "Machine pilotée.", actor=hero.id.value, position=destination, machine=machine.id)

    def _collect_stones(self) -> None:
        occupied = {hero.position for hero in self.state.heroes.values() if not hero.is_ko}
        collected = self.state.stones & occupied
        for position in sorted(collected):
            self.state.stones.remove(position)
            self.state.collected_stones += 1
            self.state.healing_charges += 1
            self._event("STONE_COLLECTED", "Pierre collectée : +1 charge de soin.", position=position)

    def _move_autonomous_machines(self) -> None:
        for machine in self.state.machines.values():
            if machine.cooldown > 0:
                continue
            machine.controlled_by = None
            destination = next_position(machine.position, machine.orientation)
            blocked = (
                not machine_step_allowed(self.state, machine.position, destination)
                or destination in self.state.chests
                or any(hero.position == destination for hero in self.state.heroes.values())
                or any(
                    other.id != machine.id and other.position == destination
                    for other in self.state.machines.values()
                )
            )
            if destination in self.state.holes and machine.kind == MachineKind.EXCAVATOR:
                self.state.holes.remove(destination)
                blocked = False
            elif destination in self.state.holes:
                blocked = True
            if destination in self.state.trees and machine.kind == MachineKind.GRAPPLER:
                self.state.trees.remove(destination)
                blocked = False
            elif destination in self.state.trees:
                blocked = True
            if blocked:
                clockwise = [Direction.UP, Direction.RIGHT, Direction.DOWN, Direction.LEFT]
                index = clockwise.index(machine.orientation)
                offset = 1 if machine.kind == MachineKind.EXCAVATOR else -1
                machine.orientation = clockwise[(index + offset) % 4]
                continue
            machine.position = destination
            machine.cooldown = cooldown_from_speed(self.state.balance.machine_speed)
            self._noise(destination, NoiseKind.MACHINE, machine.id)

    def _move_guard(self) -> None:
        guard = self.state.guard
        if guard.cooldown > 0:
            guard.intended_destination = None
            return
        direction = self._guard_ai.choose_direction(self.state)
        if direction is None:
            guard.intended_destination = None
            return
        destination = next_position(guard.position, direction)
        guard.intended_destination = destination
        guard.orientation = direction
        if not guard_step_allowed(self.state, guard.position, destination):
            self._event("GUARD_BLOCKED", "Trajectoire du gardien bloquée.", actor="K", position=guard.position)
            return
        guard.position = destination
        speed = {
            GuardMode.PATROL: 0.80,
            GuardMode.INVESTIGATE: 1.00,
            GuardMode.SEARCH: 1.00,
            GuardMode.CHASE: 1.20,
        }[guard.memory.mode]
        guard.cooldown = cooldown_from_speed(speed)
        self._event("GUARD_MOVED", guard.memory.mode.value, actor="K", position=destination, cooldown=guard.cooldown)

    def _guard_hits(self) -> None:
        for hero in self.state.heroes.values():
            if hero.position != self.state.guard.position or hero.is_ko or hero.invulnerable_ticks > 0:
                continue
            if hero.heal_ticks_remaining:
                self._cancel_heal(hero, "Soin interrompu par le gardien.")
            hero.hp = max(0, hero.hp - self.state.balance.guard_damage)
            hero.hidden = False
            hero.invulnerable_ticks = self.state.balance.invulnerability_ticks
            self.state.hit_count += 1
            self._event("GUARD_HIT", f"{hero.id.value} perd {self.state.balance.guard_damage} HP.", actor="K", position=hero.position, hp=hero.hp)
            if hero.is_ko:
                hero.rescue_ticks = self.state.balance.rescue_window_ticks
                if hero.carrying is not None:
                    carried = self.state.heroes[hero.carrying]
                    carried.carried_by = None
                    hero.carrying = None
                self._event("HERO_KO", "Fenêtre de secours ouverte.", actor=hero.id.value, position=hero.position, rescue_ticks=hero.rescue_ticks)

    def _hero_cell_free(self, position: Position) -> bool:
        return (
            self.state.game_map.in_bounds(position)
            and position not in self.state.game_map.rocks
            and position not in self.state.trees
            and position not in self.state.holes
            and position not in self.state.chests
        )

    def _chest_destination_free(self, position: Position) -> bool:
        return (
            self.state.game_map.in_bounds(position)
            and position not in self.state.game_map.rocks
            and position not in self.state.trees
            and position not in self.state.holes
            and position not in self.state.chests
            and all(machine.position != position for machine in self.state.machines.values())
            and all(hero.position != position for hero in self.state.heroes.values())
        )

    def _check_end_conditions(self) -> None:
        state = self.state
        heroes = list(state.heroes.values())
        if all(hero.is_ko for hero in heroes):
            state.status = GameStatus.LOST
            state.end_reason = "BOTH_HEROES_KO"
        elif any(hero.is_ko and hero.rescue_ticks <= 0 for hero in heroes):
            state.status = GameStatus.LOST
            state.end_reason = "RESCUE_WINDOW_EXPIRED"
        elif state.elapsed_ticks >= state.time_limit_ticks:
            state.status = GameStatus.LOST
            state.end_reason = "TIME_LIMIT"
        elif state.objectives_finished:
            if not state.game_map.exits or all(hero.position in state.game_map.exits for hero in heroes):
                state.status = GameStatus.WON
                state.end_reason = "MISSION_COMPLETE"

    def _score(self) -> int:
        # Indicateur de télémétrie compatible avec l'esprit de l'ancien score ;
        # il n'est pas présenté comme une règle officielle du Twist 2.
        hp_bonus = math.floor(sum(max(0, hero.hp) for hero in self.state.heroes.values()) / 4)
        time_bonus = math.floor(self.state.remaining_seconds / 2)
        return 150 * self.state.secured_chests + 25 * self.state.collected_stones + hp_bonus + time_bonus
