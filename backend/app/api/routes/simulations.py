from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from app.core.config import settings
from app.domain.enums import HeroId
from app.engine.actions_parser import ActionsFormatError, parse_actions_text
from app.engine.map_parser import MapFormatError, MapParser
from app.schemas.simulation import ReplayRequest, ReplayTextRequest, SimulationRequest, SimulationResponse, StrategyOptions
from app.services.simulation_service import SimulationNotFound, simulation_service
router = APIRouter(prefix='/simulations', tags=['simulations'])

def _handle_domain_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))

async def _read_utf8_upload(file: UploadFile, *, label: str) -> str:
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f'{label} trop volumineux.')
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail=f'{label} doit être encodé en UTF-8.') from exc

@router.post('', response_model=SimulationResponse, summary='Calculer une simulation IA depuis du JSON', description="Route principale Godot → FastAPI. Le backend valide map.txt, construit l'état, calcule les actions de F/M avec la stratégie choisie, exécute chaque tick dans le moteur de règles puis renvoie l'historique complet et actions.txt.", operation_id='simulate_mission')
def simulate(payload: SimulationRequest) -> SimulationResponse:
    try:
        return simulation_service.simulate(map_text=payload.mission.map_text, mission_name=payload.mission.name, strategy_options=payload.strategy)
    except (MapFormatError, ValueError) as exc:
        raise _handle_domain_error(exc) from exc

@router.post('/upload', response_model=SimulationResponse, summary='Calculer une simulation depuis map.txt', description='Équivalent multipart de `POST /simulations`. Dans Swagger `/docs`, `file`, `name` et `strategy_json` sont affichés comme paramètres `formData` individuels, sans bloc Request Body.', operation_id='simulate_uploaded_map')
async def simulate_upload(file: Annotated[UploadFile, File(..., description='Fichier map.txt UTF-8 à simuler.')], name: Annotated[str, Form(description='Nom de mission renvoyé à Godot.')]='mission', strategy_json: Annotated[str | None, Form(description='JSON optionnel de StrategyOptions. Exemple: {"name":"portfolio_v4","max_unlock_obstacles":20}')]=None) -> SimulationResponse:
    map_text = await _read_utf8_upload(file, label='map.txt')
    try:
        strategy = StrategyOptions.model_validate_json(strategy_json) if strategy_json else StrategyOptions()
        return simulation_service.simulate(map_text=map_text, mission_name=name or file.filename or 'mission', strategy_options=strategy)
    except (MapFormatError, ValueError) as exc:
        raise _handle_domain_error(exc) from exc

@router.post('/replay', response_model=SimulationResponse, summary="Rejouer une liste d'actions JSON", description="Exécute exactement les couples d'actions F/M fournis dans le moteur de règles. Les actions invalides deviennent WAIT conformément au GDD.", operation_id='replay_actions_json')
def replay(payload: ReplayRequest) -> SimulationResponse:
    actions = [{HeroId.IKOTOFOSA: paire.F, HeroId.IMAHAKI: paire.M} for paire in payload.actions]
    try:
        return simulation_service.replay(map_text=payload.mission.map_text, mission_name=payload.mission.name, actions=actions, stop_when_objectives_finished=payload.stop_when_objectives_finished)
    except (MapFormatError, ValueError) as exc:
        raise _handle_domain_error(exc) from exc

@router.post('/replay-text', response_model=SimulationResponse, summary="Rejouer le texte d'un actions.txt", description='Valide le format `ACTION_F | ACTION_M`, exige `END_GAME`, puis rejoue les actions tick par tick sur la mission fournie.', operation_id='replay_actions_text')
def replay_text(payload: ReplayTextRequest) -> SimulationResponse:
    try:
        game_map = MapParser.parse(payload.mission.map_text)
        actions = parse_actions_text(payload.actions_text, time_limit=game_map.time_limit)
        return simulation_service.replay(map_text=payload.mission.map_text, mission_name=payload.mission.name, actions=actions)
    except (MapFormatError, ActionsFormatError, ValueError) as exc:
        raise _handle_domain_error(exc) from exc

@router.post('/replay-upload', response_model=SimulationResponse, summary='Rejouer map.txt + actions.txt uploadés', description='Route multipart pratique pour les tests de compétition. Dans Swagger `/docs`, les deux fichiers et options sont des paramètres `formData` manuels.', operation_id='replay_uploaded_files')
async def replay_upload(map_file: Annotated[UploadFile, File(..., description='Fichier map.txt UTF-8.')], actions_file: Annotated[UploadFile, File(..., description='Fichier actions.txt UTF-8 terminé par END_GAME.')], name: Annotated[str, Form(description='Nom de mission pour le résultat du replay.')]='replay', stop_when_objectives_finished: Annotated[bool, Form(description='Arrêter le replay dès que tous les objectifs sont terminés.')]=False) -> SimulationResponse:
    map_text = await _read_utf8_upload(map_file, label='map.txt')
    actions_text = await _read_utf8_upload(actions_file, label='actions.txt')
    try:
        game_map = MapParser.parse(map_text)
        actions = parse_actions_text(actions_text, time_limit=game_map.time_limit)
        return simulation_service.replay(map_text=map_text, mission_name=name or map_file.filename or 'replay', actions=actions, stop_when_objectives_finished=stop_when_objectives_finished)
    except (MapFormatError, ActionsFormatError, ValueError) as exc:
        raise _handle_domain_error(exc) from exc

@router.get('/{simulation_id}', response_model=SimulationResponse, summary='Relire une simulation en mémoire', description='Retourne exactement le même objet SimulationResponse que la route de calcul.', operation_id='get_simulation')
def get_simulation(simulation_id: str) -> SimulationResponse:
    try:
        return simulation_service.get(simulation_id)
    except SimulationNotFound as exc:
        raise HTTPException(status_code=404, detail='Simulation inconnue.') from exc

@router.get('/{simulation_id}/actions.txt', response_class=PlainTextResponse, summary='Télécharger actions.txt', description="Retourne uniquement le fichier officiel d'actions: une paire F|M par tick, puis END_GAME.", operation_id='download_actions_txt', responses={200: {'description': 'Fichier actions.txt généré par la simulation.', 'content': {'text/plain': {'schema': {'type': 'string'}, 'example': 'LEFT | LEFT\nUP | LEFT\nRIGHT | HACK\nEND_GAME\n'}}}, 404: {'description': 'Simulation inconnue.'}})
def get_actions_txt(simulation_id: str) -> PlainTextResponse:
    try:
        response = simulation_service.get(simulation_id)
    except SimulationNotFound as exc:
        raise HTTPException(status_code=404, detail='Simulation inconnue.') from exc
    return PlainTextResponse(response.actions_txt, media_type='text/plain; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="{simulation_id}_actions.txt"'})
