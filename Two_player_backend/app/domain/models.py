from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

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


@dataclass(frozen=True, order=True, slots=True)
class Position:
    row: int
    col: int

    def moved(self, dr: int, dc: int, steps: int = 1) -> "Position":
        return Position(self.row + dr * steps, self.col + dc * steps)

    def manhattan(self, other: "Position") -> int:
        return abs(self.row - other.row) + abs(self.col - other.col)


@dataclass(slots=True)
class HeroCommand:
    action: HeroAction = HeroAction.WAIT
    direction: Direction | None = None
    target: HeroId | None = None


@dataclass(slots=True)
class HeroState:
    id: HeroId
    position: Position
    hp: int = 100
    stamina: int = 100
    cooldown: int = 0
    hidden: bool = False
    carrying: HeroId | None = None
    carried_by: HeroId | None = None
    invulnerable_ticks: int = 0
    rescue_ticks: int = 0
    heal_target: HeroId | None = None
    heal_ticks_remaining: int = 0
    heal_charge_reserved: bool = False
    last_direction: Direction | None = None

    @property
    def is_ko(self) -> bool:
        return self.hp <= 0

    @property
    def is_busy(self) -> bool:
        return self.cooldown > 0 or self.heal_ticks_remaining > 0


@dataclass(slots=True)
class MachineState:
    id: str
    kind: MachineKind
    position: Position
    orientation: Direction
    cooldown: int = 0
    controlled_by: HeroId | None = None
    autonomous_counter: int = 0


@dataclass(slots=True)
class NoiseEvent:
    position: Position
    radius: int
    ttl: int
    kind: NoiseKind
    source: str


@dataclass(slots=True)
class GuardMemory:
    mode: GuardMode = GuardMode.PATROL
    target: HeroId | None = None
    last_known: dict[HeroId, Position] = field(default_factory=dict)
    last_heard: Position | None = None
    last_heard_strength: int = 0
    search_ticks: int = 0
    detection: dict[HeroId, int] = field(
        default_factory=lambda: {HeroId.IKOTOFOSA: 0, HeroId.IMAHAKI: 0}
    )
    visible: set[HeroId] = field(default_factory=set)
    beliefs: dict[HeroId, dict[Position, float]] = field(default_factory=dict)


@dataclass(slots=True)
class GuardState:
    position: Position
    orientation: Direction = Direction.DOWN
    cooldown: int = 0
    memory: GuardMemory = field(default_factory=GuardMemory)
    intended_destination: Position | None = None


@dataclass(slots=True)
class GameMap:
    height: int
    width: int
    time_limit_seconds: int
    rows: tuple[str, ...]
    elevations: tuple[tuple[int, ...], ...]
    has_elevation: bool
    rocks: set[Position] = field(default_factory=set)
    trees: set[Position] = field(default_factory=set)
    holes: set[Position] = field(default_factory=set)
    bushes: set[Position] = field(default_factory=set)
    initial_stones: set[Position] = field(default_factory=set)
    initial_chests: set[Position] = field(default_factory=set)
    exits: set[Position] = field(default_factory=set)
    initial_heroes: dict[HeroId, Position] = field(default_factory=dict)
    initial_guard: Position | None = None
    initial_machines: list[MachineState] = field(default_factory=list)

    def in_bounds(self, pos: Position) -> bool:
        return 0 <= pos.row < self.height and 0 <= pos.col < self.width

    def elevation_at(self, pos: Position) -> int:
        if not self.in_bounds(pos):
            raise IndexError(pos)
        return self.elevations[pos.row][pos.col]

    def positions(self) -> Iterable[Position]:
        for row in range(self.height):
            for col in range(self.width):
                yield Position(row, col)


@dataclass(slots=True)
class BalanceConfig:
    tick_ms: int = 100
    hp_max: int = 100
    stamina_max: int = 100
    guard_damage: int = 20
    heal_amount: int = 20
    partner_heal_ticks: int = 15
    self_heal_ticks: int = 5
    rescue_window_ticks: int = 80
    invulnerability_ticks: int = 10
    guard_vision_range: int = 7
    detection_threshold: int = 100
    machine_speed: float = 1.55
    carry_speed_factor: float = 0.825
    run_speed_factor: float = 1.45


@dataclass(slots=True)
class Event:
    type: str
    message: str
    actor: str | None = None
    position: Position | None = None
    data: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class GameState:
    id: str
    game_map: GameMap
    difficulty: Difficulty
    seed: int
    balance: BalanceConfig
    heroes: dict[HeroId, HeroState]
    guard: GuardState
    machines: dict[str, MachineState]
    trees: set[Position]
    holes: set[Position]
    stones: set[Position]
    chests: set[Position]
    healing_charges: int = 0
    collected_stones: int = 0
    secured_chests: int = 0
    elapsed_ticks: int = 0
    status: GameStatus = GameStatus.ACTIVE
    end_reason: str | None = None
    version: int = 0
    noises: list[NoiseEvent] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    hit_count: int = 0
    score: int = 0

    @property
    def time_limit_ticks(self) -> int:
        return max(1, self.game_map.time_limit_seconds * 1000 // self.balance.tick_ms)

    @property
    def remaining_ticks(self) -> int:
        return max(0, self.time_limit_ticks - self.elapsed_ticks)

    @property
    def remaining_seconds(self) -> float:
        return self.remaining_ticks * self.balance.tick_ms / 1000.0

    @property
    def objectives_finished(self) -> bool:
        return not self.stones and not self.chests
