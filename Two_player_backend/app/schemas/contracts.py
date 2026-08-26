from __future__ import annotations

from app.schemas.base import APIModel


class AIProfile(APIModel):
    name: str
    behavior: str
    information: str


class ContractsResponse(APIModel):
    backend_authoritative: bool
    tick_ms: int
    map_header: str
    symbols: dict[str, str]
    actions: list[str]
    ai_profiles: list[AIProfile]
    recommendations: list[str]
