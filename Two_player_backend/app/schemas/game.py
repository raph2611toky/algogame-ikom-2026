from __future__ import annotations

from typing import Annotated

from pydantic import Field, model_validator

from app.domain.enums import Difficulty, Direction, GameStatus, GuardMode, HeroAction, HeroId
from app.schemas.base import APIModel


class BalanceOptions(APIModel):
    tick_ms: Annotated[int, Field(ge=50, le=1000)] = 100
    hp_max: Annotated[int, Field(ge=1, le=1000)] = 100
    stamina_max: Annotated[int, Field(ge=1, le=1000)] = 100
    guard_damage: Annotated[int, Field(ge=1, le=1000)] = 20
    heal_amount: Annotated[int, Field(ge=1, le=1000)] = 20
    partner_heal_ticks: Annotated[int, Field(ge=1, le=600)] = 15
    self_heal_ticks: Annotated[int, Field(ge=1, le=600)] = 5
    rescue_window_ticks: Annotated[int, Field(ge=1, le=6000)] = 80
    invulnerability_ticks: Annotated[int, Field(ge=0, le=600)] = 10
    guard_vision_range: Annotated[int, Field(ge=1, le=100)] = 7
    detection_threshold: Annotated[int, Field(ge=1, le=100)] = 100
    machine_speed: Annotated[float, Field(gt=0, le=10)] = 1.55
    carry_speed_factor: Annotated[float, Field(gt=0, le=2)] = 0.825
    run_speed_factor: Annotated[float, Field(gt=0, le=5)] = 1.45


class CreateGameRequest(APIModel):
    map_text: Annotated[str, Field(min_length=1, max_length=100_000)]
    elevation_text: str | None = None
    difficulty: Difficulty = Difficulty.MEDIUM
    seed: int = 1
    balance: BalanceOptions = Field(default_factory=BalanceOptions)


class CommandInput(APIModel):
    action: HeroAction = HeroAction.WAIT
    direction: Direction | None = None
    target: HeroId | None = None

    @model_validator(mode="after")
    def direction_when_required(self) -> "CommandInput":
        if self.action in {
            HeroAction.MOVE,
            HeroAction.RUN,
            HeroAction.PUSH,
            HeroAction.ASSISTED_JUMP,
            HeroAction.USE_MACHINE,
        } and self.direction is None:
            raise ValueError(f"direction est obligatoire pour {self.action}")
        return self


class TickRequest(APIModel):
    sequence: Annotated[int, Field(ge=1)]
    actions: dict[HeroId, CommandInput] = Field(default_factory=dict)


class PositionOut(APIModel):
    row: int
    col: int


class HeroOut(APIModel):
    id: HeroId
    position: PositionOut
    hp: int
    stamina: int
    speed_factor: float
    cooldown_ticks: int
    hidden: bool
    is_ko: bool
    rescue_ticks: int
    carrying: HeroId | None
    carried_by: HeroId | None
    healing: bool


class GuardOut(APIModel):
    position: PositionOut
    orientation: Direction
    mode: GuardMode
    cooldown_ticks: int
    intended_destination: PositionOut | None
    visible_heroes: list[HeroId]
    detection: dict[HeroId, int]


class MachineOut(APIModel):
    id: str
    kind: str
    position: PositionOut
    orientation: Direction
    cooldown_ticks: int


class EventOut(APIModel):
    type: str
    message: str
    actor: str | None
    position: PositionOut | None
    data: dict[str, object]


class MapOut(APIModel):
    height: int
    width: int
    time_limit_seconds: int
    tick_ms: int
    has_elevation: bool
    elevations: list[list[int]]
    rocks: list[PositionOut]
    trees: list[PositionOut]
    holes: list[PositionOut]
    bushes: list[PositionOut]
    exits: list[PositionOut]


class ObjectivesOut(APIModel):
    stones_collected: int
    stones_remaining: int
    chests_secured: int
    chests_remaining: int
    healing_charges: int


class GameSnapshot(APIModel):
    game_id: str
    sequence: int
    version: int
    duplicate: bool = False
    status: GameStatus
    end_reason: str | None
    difficulty: Difficulty
    elapsed_ticks: int
    remaining_seconds: float
    telemetry_score: int
    mission_progress_percent: float
    heroes: dict[HeroId, HeroOut]
    guard: GuardOut
    machines: list[MachineOut]
    objectives: ObjectivesOut
    stones: list[PositionOut]
    chests: list[PositionOut]
    events: list[EventOut]
    map: MapOut


class ReplayRequest(CreateGameRequest):
    ticks: Annotated[list[dict[HeroId, CommandInput]], Field(max_length=100_000)]


class ReplayResponse(APIModel):
    processed_ticks: int
    final: GameSnapshot


class ErrorResponse(APIModel):
    detail: str


class ValidateMapRequest(APIModel):
    map_text: Annotated[str, Field(min_length=1, max_length=100_000)]
    elevation_text: str | None = None


class ValidateMapResponse(APIModel):
    valid: bool
    height: int
    width: int
    has_elevation: bool
    heroes: int
    guards: int
    machines: int
    stones: int
    chests: int
    exits: int
