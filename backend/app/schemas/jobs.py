from __future__ import annotations
from typing import Literal
from app.schemas.common import APIModel
from app.schemas.simulation import ResultSummarySchema, SimulationResponse


class SimulationJobStatus(APIModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    mission_name: str
    strategy_name: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_seconds: float = 0.0
    simulation_id: str | None = None
    result: ResultSummarySchema | None = None
    result_url: str | None = None
    error: str | None = None


class SimulationJobResult(APIModel):
    job: SimulationJobStatus
    simulation: SimulationResponse
