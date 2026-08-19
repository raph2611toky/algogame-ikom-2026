from __future__ import annotations

from pydantic import Field

from app.schemas.common import APIModel


class ElevationContractSchema(APIModel):
    file: str = 'elevation.txt'
    optional: bool = True
    reachable_range: str = '1..9'
    rock_value: int = 0
    legacy_default: int = 0


class MapContractSchema(APIModel):
    header: str
    symbols: dict[str, str]
    origin: str
    elevation: ElevationContractSchema


class ActionsTextContractSchema(APIModel):
    line: str
    terminator: str


class TimingContractSchema(APIModel):
    relative_seconds_per_tick: int
    standard_timescale: int
    real_seconds_per_tick: float


class ResourcesContractSchema(APIModel):
    initial_stamina_per_hero: int
    initial_battery_per_hero: int
    move_stamina: int
    uphill_move_stamina: int = 3
    downhill_move_stamina: int = 0
    special_hop_or_climb_stamina: int
    push_stamina: int
    stamina_recovery: str
    battery_per_valid_hack_action: int


class ContractResponse(APIModel):
    version: str
    map: MapContractSchema
    hero_actions: list[str]
    machine_orientations: list[str]
    actions_txt: ActionsTextContractSchema
    timing: TimingContractSchema
    resources: ResourcesContractSchema
    score_formula: str
    default_strategy: str = 'portfolio_v13'
