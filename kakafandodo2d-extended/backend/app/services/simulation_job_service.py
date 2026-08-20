from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from uuid import uuid4

from app.schemas.jobs import SimulationJobResult, SimulationJobStatus
from app.schemas.simulation import SimulationResponse, StrategyOptions
from app.services.simulation_service import simulation_service


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class _Job:
    job_id: str
    mission_name: str
    map_text: str
    elevation_text: str | None
    strategy: StrategyOptions
    status: str = "queued"
    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    started_monotonic: float | None = None
    finished_monotonic: float | None = None
    response: SimulationResponse | None = None
    error: str | None = None


class SimulationJobNotFound(KeyError):
    pass


class SimulationJobNotReady(RuntimeError):
    pass


class SimulationJobService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, _Job] = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="kakafandodo-sim")

    def submit(self, *, map_text: str, elevation_text: str | None = None, mission_name: str, strategy: StrategyOptions) -> SimulationJobStatus:
        job = _Job(
            job_id=str(uuid4()),
            mission_name=mission_name,
            map_text=map_text,
            elevation_text=elevation_text,
            strategy=strategy.model_copy(deep=True),
            created_at=_iso_now(),
        )
        with self._lock:
            self._jobs[job.job_id] = job
        self._executor.submit(self._run, job.job_id)
        return self.status(job.job_id)

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "running"
            job.started_at = _iso_now()
            job.started_monotonic = monotonic()
        try:
            response = simulation_service.simulate(
                map_text=job.map_text,
                elevation_text=job.elevation_text,
                mission_name=job.mission_name,
                strategy_options=job.strategy,
            )
            with self._lock:
                job.response = response
                job.status = "completed"
                job.finished_at = _iso_now()
                job.finished_monotonic = monotonic()
        except Exception as exc:
            with self._lock:
                job.error = f"{type(exc).__name__}: {exc}"
                job.status = "failed"
                job.finished_at = _iso_now()
                job.finished_monotonic = monotonic()

    def _get(self, job_id: str) -> _Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise SimulationJobNotFound(job_id)
        return job

    def status(self, job_id: str) -> SimulationJobStatus:
        job = self._get(job_id)
        now = monotonic()
        if job.started_monotonic is None:
            elapsed = 0.0
        elif job.finished_monotonic is not None:
            elapsed = max(0.0, job.finished_monotonic - job.started_monotonic)
        else:
            elapsed = max(0.0, now - job.started_monotonic)
        result = None
        simulation_id = None
        result_url = None
        if job.response is not None:
            result = job.response.result
            simulation_id = job.response.simulation_id
            result_url = f"/api/v1/simulation-jobs/{job.job_id}/result"
        return SimulationJobStatus(
            job_id=job.job_id,
            status=job.status,
            mission_name=job.mission_name,
            strategy_name=job.strategy.name,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            elapsed_seconds=round(elapsed, 3),
            simulation_id=simulation_id,
            result=result,
            result_url=result_url,
            error=job.error,
        )

    def result(self, job_id: str) -> SimulationJobResult:
        job = self._get(job_id)
        if job.status != "completed" or job.response is None:
            raise SimulationJobNotReady(job.status)
        return SimulationJobResult(job=self.status(job_id), simulation=job.response)


simulation_job_service = SimulationJobService()
