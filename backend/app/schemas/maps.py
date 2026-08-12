from __future__ import annotations
from pydantic import Field
from app.schemas.common import APIModel, PositionSchema
OFFICIAL_SAMPLE_MAP = '5 7 100\nG+.M..+\n.###tt#\n.o*.+.@\no##t#tX\n.F#++..'

class MapTextRequest(APIModel):
    map_text: str = Field(min_length=1, max_length=1000000, description='Contenu complet de map.txt.')
    name: str = Field(default='mission', min_length=1, max_length=120)
    model_config = {'extra': 'forbid', 'json_schema_extra': {'example': {'name': 'official_sample', 'map_text': OFFICIAL_SAMPLE_MAP}}}

class MachineInitialSchema(APIModel):
    id: str
    kind: str
    position: PositionSchema
    orientation: str

class MapCountsSchema(APIModel):
    rocks: int = Field(ge=0)
    trees: int = Field(ge=0)
    holes: int = Field(ge=0)
    bushes: int = Field(ge=0)
    stones: int = Field(ge=0)
    chests: int = Field(ge=0)
    machines: int = Field(ge=0)

class MapParseResponse(APIModel):
    name: str
    height: int = Field(gt=0)
    width: int = Field(gt=0)
    time_limit: int = Field(gt=0)
    rows: list[str]
    heroes: dict[str, PositionSchema]
    machines: list[MachineInitialSchema]
    counts: MapCountsSchema
    valid: bool = True
