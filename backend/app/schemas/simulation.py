from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain.enums import HeroAction
from app.schemas.common import APIModel, PositionSchema


class MissionInput(APIModel):
    name: str = Field(default="mission", min_length=1, max_length=120)
    map_text: str = Field(min_length=1, max_length=1_000_000)


class StrategyOptions(APIModel):
    name: Literal["heuristic_v1"] = "heuristic_v1"
    max_stones_per_hero: int = Field(default=8, ge=1, le=50)
    max_chest_pairs_per_hero: int = Field(default=6, ge=1, le=50)
    stuck_end_threshold: int = Field(default=8, ge=1, le=100)


class SimulationRequest(APIModel):
    mission: MissionInput
    strategy: StrategyOptions = Field(default_factory=StrategyOptions)


class ReplayActionPair(APIModel):
    F: HeroAction = HeroAction.WAIT
    M: HeroAction = HeroAction.WAIT


class ReplayRequest(APIModel):
    mission: MissionInput
    actions: list[ReplayActionPair] = Field(default_factory=list)
    stop_when_objectives_finished: bool = False


class ReplayTextRequest(APIModel):
    mission: MissionInput
    actions_text: str = Field(min_length=1, max_length=5_000_000)


class ScoreInputsSchema(APIModel):
    secured_chests: int
    hero_stones: int
    total_stamina: int
    total_battery: int


class HeroSnapshotSchema(APIModel):
    position: PositionSchema
    stamina: int
    battery: int
    stones: int
    hacking_machine_id: str | None = None


class MachineSnapshotSchema(APIModel):
    kind: str
    position: PositionSchema
    orientation: str
    hacked_by: str | None = None
    carried_stones: int
    pending_move: bool
    auto_move_pending: bool
    steps_since_dig: int
    last_action: str


class PropsSnapshotSchema(APIModel):
    stones: list[PositionSchema]
    chests: list[PositionSchema]
    trees: list[PositionSchema]
    holes: list[PositionSchema]
    bushes: list[PositionSchema]
    rocks: list[PositionSchema]
    secured_chests: int
    lost_chests: int


class StateSnapshotSchema(APIModel):
    elapsed: int
    remaining_time: int
    score_inputs: ScoreInputsSchema
    heroes: dict[str, HeroSnapshotSchema]
    machines: dict[str, MachineSnapshotSchema]
    props: PropsSnapshotSchema
    ended: bool
    end_reason: str | None = None


class EventSchema(APIModel):
    type: str
    message: str
    actor: str | None = None
    position: PositionSchema | None = None
    data: dict[str, object] = Field(default_factory=dict)


class TickSchema(APIModel):
    tick: int
    requested_actions: dict[str, HeroAction]
    effective_actions: dict[str, HeroAction]
    machine_actions: dict[str, str]
    events: list[EventSchema]
    state: StateSnapshotSchema


class ResultSummarySchema(APIModel):
    score: int
    stones_collected: int
    chests_secured: int
    chests_lost: int
    remaining_time: int
    total_stamina: int
    total_battery: int
    end_reason: str | None = None


class SimulationResponse(APIModel):
    contract_version: Literal["1.0"] = "1.0"
    simulation_id: str
    mission_name: str
    map: dict[str, object]
    initial_state: StateSnapshotSchema
    ticks: list[TickSchema]
    result: ResultSummarySchema
    actions: list[dict[str, object]]
    actions_txt: str
    actions_download_url: str
