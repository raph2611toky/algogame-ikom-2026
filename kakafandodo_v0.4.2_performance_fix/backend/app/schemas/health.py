from __future__ import annotations
from app.schemas.common import APIModel

class HealthResponse(APIModel):
    status: str
    service: str
    contract: str
    strategy: str
