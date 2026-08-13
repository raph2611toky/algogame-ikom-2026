from __future__ import annotations
from pydantic import Field
from app.schemas.common import APIModel
from app.schemas.simulation import StrategyOptions


class AppSettingsSchema(APIModel):
    sound: int = Field(default=80, ge=0, le=100)
    music: int = Field(default=60, ge=0, le=100)
    effects: int = Field(default=80, ge=0, le=100)
    dialogue: int = Field(default=90, ge=0, le=100)
    quality: int = Field(default=2, ge=0, le=3)
    fullscreen: bool = False
    language: int = Field(default=0, ge=0, le=2)
    strategy: StrategyOptions = Field(default_factory=StrategyOptions)


class SettingsResponse(APIModel):
    settings: AppSettingsSchema
    storage: str = "backend-json"
