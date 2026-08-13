from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, File, HTTPException, UploadFile
from app.core.config import settings
from app.engine.map_parser import MapFormatError, MapParser
from app.schemas.maps import MapParseResponse, MapTextRequest
router = APIRouter(prefix='/maps', tags=['maps'])

def _to_response(name: str, text: str) -> MapParseResponse:
    try:
        game_map = MapParser.parse(text)
    except MapFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return MapParseResponse.model_validate({'name': name, 'height': game_map.height, 'width': game_map.width, 'time_limit': game_map.time_limit, 'rows': list(game_map.rows), 'heroes': {heros.value: {'row': pos.row, 'col': pos.col} for heros, pos in game_map.initial_hero_positions.items()}, 'machines': [{'id': machine_locale.id, 'kind': machine_locale.kind.value, 'position': {'row': machine_locale.position.row, 'col': machine_locale.position.col}, 'orientation': machine_locale.orientation.value} for machine_locale in game_map.initial_machines], 'counts': {'rocks': len(game_map.rocks), 'trees': len(game_map.trees), 'holes': len(game_map.holes), 'bushes': len(game_map.bushes), 'stones': len(game_map.stones), 'chests': len(game_map.chests), 'machines': len(game_map.initial_machines)}})

@router.post('/parse', response_model=MapParseResponse, summary='Analyser une map depuis du JSON', description="Valide le header `H W TIME_LIMIT`, les dimensions, l'alphabet officiel et les positions initiales. Aucun algorithme de jeu n'est lancé.", operation_id='parse_map_text')
def parse_map(payload: MapTextRequest) -> MapParseResponse:
    return _to_response(payload.name, payload.map_text)

@router.post('/upload', response_model=MapParseResponse, summary='Analyser un fichier map.txt', description='Upload multipart de map.txt. Dans `/docs`, le fichier est volontairement exposé comme paramètre manuel `formData` et non comme bloc Request Body.', operation_id='upload_map_file')
async def upload_map(file: Annotated[UploadFile, File(..., description='Fichier map.txt UTF-8 conforme au GDD AlgoGames 2.')]) -> MapParseResponse:
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail='Fichier map.txt trop volumineux.')
    try:
        texte = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail='map.txt doit être encodé en UTF-8.') from exc
    return _to_response(file.filename or 'mission', texte)
