from __future__ import annotations

import json
from typing import Annotated
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.schemas.jobs import SimulationJobResult, SimulationJobStatus
from app.schemas.simulation import SimulationRequest, StrategyOptions
from app.services.simulation_job_service import (
    SimulationJobNotFound,
    SimulationJobNotReady,
    simulation_job_service,
)

router = APIRouter(prefix="/simulation-jobs", tags=["simulation-jobs"])


async def _read_utf8(file: UploadFile, *, label: str) -> str:
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"{label} trop volumineux.")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"{label} doit être encodé en UTF-8.") from exc


@router.post(
    "",
    response_model=SimulationJobStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Démarrer une simulation asynchrone",
    description="Retourne immédiatement un job_id. mission.elevation_text est optionnel.",
    operation_id="create_simulation_job",
)
def create_job(payload: SimulationRequest) -> SimulationJobStatus:
    return simulation_job_service.submit(
        map_text=payload.mission.map_text,
        elevation_text=payload.mission.elevation_text,
        mission_name=payload.mission.name,
        strategy=payload.strategy,
    )


@router.post(
    "/upload",
    response_model=SimulationJobStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Démarrer une simulation asynchrone avec map.txt + elevation.txt optionnel",
    description="Upload multipart léger. Les anciennes intégrations peuvent omettre elevation_file.",
    operation_id="create_simulation_job_upload",
)
async def create_job_upload(
    file: Annotated[UploadFile, File(..., description="Fichier map.txt UTF-8 à simuler.")],
    elevation_file: Annotated[UploadFile | None, File(description="Fichier elevation.txt UTF-8 optionnel.")] = None,
    name: Annotated[str, Form(description="Nom de mission.")] = "mission",
    strategy_json: Annotated[str, Form(description="Options StrategyOptions en JSON.")] = '{"name":"portfolio_v13"}',
) -> SimulationJobStatus:
    map_text = await _read_utf8(file, label='map.txt')
    elevation_text = await _read_utf8(elevation_file, label='elevation.txt') if elevation_file is not None else None
    try:
        parsed = json.loads(strategy_json or "{}")
        strategy = StrategyOptions.model_validate(parsed)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"strategy_json invalide: {exc}") from exc
    return simulation_job_service.submit(
        map_text=map_text,
        elevation_text=elevation_text,
        mission_name=name or file.filename or "mission",
        strategy=strategy,
    )


@router.get(
    "/{job_id}",
    response_model=SimulationJobStatus,
    summary="Lire l'état d'un calcul",
    operation_id="get_simulation_job",
)
def get_job(job_id: str) -> SimulationJobStatus:
    try:
        return simulation_job_service.status(job_id)
    except SimulationJobNotFound as exc:
        raise HTTPException(status_code=404, detail="Job de simulation inconnu.") from exc


@router.get(
    "/{job_id}/result",
    response_model=SimulationJobResult,
    summary="Récupérer le résultat complet d'un job terminé",
    description="Le gros SimulationResponse n'est téléchargé qu'une fois le calcul terminé.",
    operation_id="get_simulation_job_result",
)
def get_job_result(job_id: str) -> SimulationJobResult:
    try:
        return simulation_job_service.result(job_id)
    except SimulationJobNotFound as exc:
        raise HTTPException(status_code=404, detail="Job de simulation inconnu.") from exc
    except SimulationJobNotReady as exc:
        raise HTTPException(status_code=409, detail=f"Job pas encore terminé: {exc}") from exc
