from __future__ import annotations
from app.schemas.common import APIModel


class StrategyDescriptorSchema(APIModel):
    name: str
    label: str
    family: str
    description: str
    recommended: bool = False
    supports_large_maps: bool = True


class StrategiesResponse(APIModel):
    default_strategy: str
    strategies: list[StrategyDescriptorSchema]
