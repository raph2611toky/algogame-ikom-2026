from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from app.core.config import settings
from app.domain.enums import HeroId
from app.engine.actions_parser import ActionsFormatError, parse_actions_text
from app.engine.map_parser import MapFormatError, MapParser
from app.schemas.simulation import (
    ReplayRequest,
    ReplayTextRequest,
    SimulationRequest,
    SimulationResponse,
    StrategyOptions,
)
from app.services.simulation_service import (
    SimulationNotFound,
    simulation_service,
)

router = APIRouter(prefix="/simulations", tags=["simulations"])


def _handle_domain_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


@router.post("", response_model=SimulationResponse)
def simulate(payload: SimulationRequest) -> SimulationResponse:
    try:
        return simulation_service.simulate(
            map_text=payload.mission.map_text,
            mission_name=payload.mission.name,
            strategy_options=payload.strategy,
        )
    except (MapFormatError, ValueError) as exc:
        raise _handle_domain_error(exc) from exc


@router.post("/upload", response_model=SimulationResponse)
async def simulate_upload(
    file: UploadFile = File(...),
    name: str = Form("mission"),
    strategy_json: str | None = Form(None),
) -> SimulationResponse:
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Fichier map.txt trop volumineux.")
    try:
        map_text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="map.txt doit être encodé en UTF-8.") from exc
    try:
        strategy = (
            StrategyOptions.model_validate_json(strategy_json)
            if strategy_json
            else StrategyOptions()
        )
        return simulation_service.simulate(
            map_text=map_text,
            mission_name=name or file.filename or "mission",
            strategy_options=strategy,
        )
    except (MapFormatError, ValueError) as exc:
        raise _handle_domain_error(exc) from exc


@router.post("/replay", response_model=SimulationResponse)
def replay(payload: ReplayRequest) -> SimulationResponse:
    actions = [
        {
            HeroId.IKOTOFOSA: pair.F,
            HeroId.IMAHAKI: pair.M,
        }
        for pair in payload.actions
    ]
    try:
        return simulation_service.replay(
            map_text=payload.mission.map_text,
            mission_name=payload.mission.name,
            actions=actions,
            stop_when_objectives_finished=payload.stop_when_objectives_finished,
        )
    except (MapFormatError, ValueError) as exc:
        raise _handle_domain_error(exc) from exc


@router.post("/replay-text", response_model=SimulationResponse)
def replay_text(payload: ReplayTextRequest) -> SimulationResponse:
    try:
        game_map = MapParser.parse(payload.mission.map_text)
        actions = parse_actions_text(
            payload.actions_text, time_limit=game_map.time_limit
        )
        return simulation_service.replay(
            map_text=payload.mission.map_text,
            mission_name=payload.mission.name,
            actions=actions,
        )
    except (MapFormatError, ActionsFormatError, ValueError) as exc:
        raise _handle_domain_error(exc) from exc


@router.get("/{simulation_id}", response_model=SimulationResponse)
def get_simulation(simulation_id: str) -> SimulationResponse:
    try:
        return simulation_service.get(simulation_id)
    except SimulationNotFound as exc:
        raise HTTPException(status_code=404, detail="Simulation inconnue.") from exc


@router.get("/{simulation_id}/actions.txt", response_class=PlainTextResponse)
def get_actions_txt(simulation_id: str) -> PlainTextResponse:
    try:
        response = simulation_service.get(simulation_id)
    except SimulationNotFound as exc:
        raise HTTPException(status_code=404, detail="Simulation inconnue.") from exc
    return PlainTextResponse(
        response.actions_txt,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{simulation_id}_actions.txt"'
        },
    )
