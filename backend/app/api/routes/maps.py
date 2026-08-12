from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.engine.map_parser import MapFormatError, MapParser
from app.schemas.maps import MapParseResponse, MapTextRequest

router = APIRouter(prefix="/maps", tags=["maps"])


def _to_response(name: str, text: str) -> MapParseResponse:
    try:
        game_map = MapParser.parse(text)
    except MapFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return MapParseResponse.model_validate(
        {
            "name": name,
            "height": game_map.height,
            "width": game_map.width,
            "time_limit": game_map.time_limit,
            "rows": list(game_map.rows),
            "heroes": {
                hero.value: {"row": pos.row, "col": pos.col}
                for hero, pos in game_map.initial_hero_positions.items()
            },
            "machines": [
                {
                    "id": m.id,
                    "kind": m.kind.value,
                    "position": {"row": m.position.row, "col": m.position.col},
                    "orientation": m.orientation.value,
                }
                for m in game_map.initial_machines
            ],
            "counts": {
                "rocks": len(game_map.rocks),
                "trees": len(game_map.trees),
                "holes": len(game_map.holes),
                "bushes": len(game_map.bushes),
                "stones": len(game_map.stones),
                "chests": len(game_map.chests),
                "machines": len(game_map.initial_machines),
            },
        }
    )


@router.post("/parse", response_model=MapParseResponse)
def parse_map(payload: MapTextRequest) -> MapParseResponse:
    return _to_response(payload.name, payload.map_text)


@router.post("/upload", response_model=MapParseResponse)
async def upload_map(file: UploadFile = File(...)) -> MapParseResponse:
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Fichier map.txt trop volumineux.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="map.txt doit être encodé en UTF-8.") from exc
    return _to_response(file.filename or "mission", text)
