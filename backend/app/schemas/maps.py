from __future__ import annotations

from pydantic import Field

from app.schemas.common import APIModel, PositionSchema


class MapTextRequest(APIModel):
    map_text: str = Field(min_length=1, max_length=1_000_000)
    name: str = Field(default="mission", min_length=1, max_length=120)


class MachineInitialSchema(APIModel):
    id: str
    kind: str
    position: PositionSchema
    orientation: str


class MapParseResponse(APIModel):
    name: str
    height: int
    width: int
    time_limit: int
    rows: list[str]
    heroes: dict[str, PositionSchema]
    machines: list[MachineInitialSchema]
    counts: dict[str, int]
    valid: bool = True
