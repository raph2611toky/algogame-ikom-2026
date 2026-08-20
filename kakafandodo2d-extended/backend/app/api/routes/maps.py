from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, File, HTTPException, UploadFile
from app.core.config import settings
from app.engine.map_parser import MapFormatError, MapParser
from app.schemas.maps import MapParseResponse, MapTextRequest

router = APIRouter(prefix='/maps', tags=['maps'])


def _elevation_rows(game_map) -> list[str]:
    return [''.join(str(value) for value in row) for row in game_map.elevations]


def _to_response(name: str, text: str, elevation_text: str | None = None) -> MapParseResponse:
    try:
        game_map = MapParser.parse(text, elevation_text=elevation_text)
    except MapFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return MapParseResponse.model_validate({
        'name': name,
        'height': game_map.height,
        'width': game_map.width,
        'time_limit': game_map.time_limit,
        'rows': list(game_map.rows),
        'elevation_rows': _elevation_rows(game_map),
        'has_elevation': game_map.has_elevation,
        'heroes': {heros.value: {'row': pos.row, 'col': pos.col} for heros, pos in game_map.initial_hero_positions.items()},
        'machines': [
            {
                'id': machine_locale.id,
                'kind': machine_locale.kind.value,
                'position': {'row': machine_locale.position.row, 'col': machine_locale.position.col},
                'orientation': machine_locale.orientation.value,
            }
            for machine_locale in game_map.initial_machines
        ],
        'counts': {
            'rocks': len(game_map.rocks),
            'trees': len(game_map.trees),
            'holes': len(game_map.holes),
            'bushes': len(game_map.bushes),
            'stones': len(game_map.stones),
            'chests': len(game_map.chests),
            'machines': len(game_map.initial_machines),
        },
    })


@router.post('/parse', response_model=MapParseResponse, summary='Analyser map.txt + elevation.txt optionnel', description="Valide map.txt et, si fourni, elevation.txt. Sans elevation.txt la carte reste compatible historique avec elevation 0 partout.", operation_id='parse_map_text')
def parse_map(payload: MapTextRequest) -> MapParseResponse:
    return _to_response(payload.name, payload.map_text, payload.elevation_text)


async def _read_utf8_upload(file: UploadFile, *, label: str) -> str:
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f'{label} trop volumineux.')
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail=f'{label} doit être encodé en UTF-8.') from exc


@router.post('/upload', response_model=MapParseResponse, summary='Analyser map.txt et elevation.txt optionnel', description='Upload multipart de map.txt avec elevation.txt facultatif. Sans elevation.txt, toutes les elevations valent 0.', operation_id='upload_map_file')
async def upload_map(
    file: Annotated[UploadFile, File(..., description='Fichier map.txt UTF-8 conforme au GDD AlgoGames 2.')],
    elevation_file: Annotated[UploadFile | None, File(description='Fichier elevation.txt UTF-8 optionnel; chiffres 1..9, et 0 sur les rochers.')] = None,
) -> MapParseResponse:
    texte = await _read_utf8_upload(file, label='map.txt')
    elevation_text = await _read_utf8_upload(elevation_file, label='elevation.txt') if elevation_file is not None else None
    return _to_response(file.filename or 'mission', texte, elevation_text)
