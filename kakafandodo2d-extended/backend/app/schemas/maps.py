from __future__ import annotations
from pydantic import Field
from app.schemas.common import APIModel, PositionSchema

OFFICIAL_SAMPLE_MAP = '5 7 100\nG+.M..+\n.###tt#\n.o*.+.@\no##t#tX\n.F#++..'
OFFICIAL_SAMPLE_ELEVATION = '1111111\n1000110\n1111111\n1001011\n1101111'

class MapTextRequest(APIModel):
    map_text: str = Field(min_length=1, max_length=1000000, description='Contenu complet de map.txt.')
    elevation_text: str | None = Field(default=None, max_length=1000000, description='Contenu optionnel de elevation.txt. Si absent, le backend utilise une carte plate d elevation 0 pour compatibilite avec les anciennes maps.')
    name: str = Field(default='mission', min_length=1, max_length=120)
    model_config = {
        'extra': 'forbid',
        'json_schema_extra': {
            'example': {
                'name': 'official_sample',
                'map_text': OFFICIAL_SAMPLE_MAP,
                'elevation_text': OFFICIAL_SAMPLE_ELEVATION,
            }
        },
    }

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
    elevation_rows: list[str]
    has_elevation: bool
    heroes: dict[str, PositionSchema]
    machines: list[MachineInitialSchema]
    counts: MapCountsSchema
    valid: bool = True
