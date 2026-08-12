from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field

class APIModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class PositionSchema(APIModel):
    row: int = Field(ge=0)
    col: int = Field(ge=0)
