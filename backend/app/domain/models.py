from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable
from app.domain.enums import HeroAction, HeroId, MachineAction, MachineKind, Orientation

@dataclass(frozen=True, order=True, slots=True)
class Position:
    row: int
    col: int

    def moved(self, dr: int, dc: int, steps: int=1) -> 'Position':
        return Position(self.row + dr * steps, self.col + dc * steps)

    def manhattan(self, other: 'Position') -> int:
        return abs(self.row - other.row) + abs(self.col - other.col)

@dataclass(slots=True)
class HeroState:
    id: HeroId
    position: Position
    stamina: int = 100
    battery: int = 100
    stones: int = 0
    hacking_machine_id: str | None = None
    recovery_seconds: int = 0

    @property
    def is_hacking(self) -> bool:
        return self.hacking_machine_id is not None

@dataclass(slots=True)
class MachineState:
    id: str
    kind: MachineKind
    position: Position
    orientation: Orientation
    hacked_by: HeroId | None = None
    carried_stones: int = 0
    pending_move: bool = False
    auto_move_pending: bool = False
    steps_since_dig: int = 0
    resume_delay: int = 0
    last_action: MachineAction = MachineAction.NONE

    @property
    def is_hacked(self) -> bool:
        return self.hacked_by is not None

@dataclass(slots=True)
class GameMap:
    height: int
    width: int
    time_limit: int
    rows: tuple[str, ...]
    # Backward-compatible flat mode: when elevation.txt is not supplied every
    # cell is represented as elevation 0 and has_elevation=False.  In explicit
    # elevation mode, reachable cells are 1..9 and rocks are 0.
    elevations: tuple[tuple[int, ...], ...] = field(default_factory=tuple)
    has_elevation: bool = False
    rocks: set[Position] = field(default_factory=set)
    trees: set[Position] = field(default_factory=set)
    holes: set[Position] = field(default_factory=set)
    bushes: set[Position] = field(default_factory=set)
    stones: set[Position] = field(default_factory=set)
    chests: set[Position] = field(default_factory=set)
    initial_hero_positions: dict[HeroId, Position] = field(default_factory=dict)
    initial_machines: list[MachineState] = field(default_factory=list)

    def in_bounds(self, pos: Position) -> bool:
        return 0 <= pos.row < self.height and 0 <= pos.col < self.width

    def all_positions(self) -> Iterable[Position]:
        for ligne in range(self.height):
            for colonne in range(self.width):
                yield Position(ligne, colonne)

    def elevation_at(self, pos: Position) -> int:
        if not self.in_bounds(pos):
            raise IndexError(f'Position hors carte: {pos}')
        if not self.elevations:
            return 0
        return self.elevations[pos.row][pos.col]

@dataclass(slots=True)
class GameState:
    game_map: GameMap
    heroes: dict[HeroId, HeroState]
    machines: dict[str, MachineState]
    stones: set[Position]
    chests: set[Position]
    trees: set[Position]
    holes: set[Position]
    elapsed: int = 0
    secured_chests: int = 0
    lost_chests: int = 0
    ended: bool = False
    end_reason: str | None = None

    @property
    def remaining_time(self) -> int:
        return max(0, self.game_map.time_limit - self.elapsed)

    @property
    def total_hero_stones(self) -> int:
        return sum((heros.stones for heros in self.heroes.values()))

    @property
    def total_stamina(self) -> int:
        return sum((heros.stamina for heros in self.heroes.values()))

    @property
    def total_battery(self) -> int:
        return sum((heros.battery for heros in self.heroes.values()))

    @property
    def objectives_finished(self) -> bool:
        pierres_machines = sum((machine.carried_stones for machine in self.machines.values()))
        return not self.stones and pierres_machines == 0 and (not self.chests)

    def machine_at(self, pos: Position) -> MachineState | None:
        for machine in self.machines.values():
            if machine.position == pos:
                return machine
        return None

    def machines_at(self, pos: Position) -> list[MachineState]:
        return [machine_locale for machine_locale in self.machines.values() if machine_locale.position == pos]

    def hero_at(self, pos: Position) -> list[HeroState]:
        return [h for h in self.heroes.values() if h.position == pos]

@dataclass(slots=True)
class Event:
    type: str
    message: str
    actor: str | None = None
    position: Position | None = None
    data: dict[str, object] = field(default_factory=dict)

@dataclass(slots=True)
class TickRecord:
    tick: int
    requested_actions: dict[HeroId, HeroAction]
    effective_actions: dict[HeroId, HeroAction]
    machine_actions: dict[str, MachineAction]
    events: list[Event]
    snapshot: dict[str, object]

@dataclass(slots=True)
class SimulationResult:
    simulation_id: str
    initial_snapshot: dict[str, object]
    ticks: list[TickRecord]
    final_snapshot: dict[str, object]
    score: int
    actions_text: str
