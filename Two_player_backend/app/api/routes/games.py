from fastapi import APIRouter, Depends, HTTPException, Response, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from app.api.dependencies import get_game_service
from app.engine.map_parser import MapFormatError, MapParser
from app.schemas.game import (
    CreateGameRequest,
    GameSnapshot,
    ReplayRequest,
    ReplayResponse,
    TickRequest,
    ValidateMapRequest,
    ValidateMapResponse,
)
from app.services.game_service import GameNotFound, GameService, SequenceConflict


router = APIRouter(tags=["games"])


def _not_found(game_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Partie introuvable : {game_id}")


@router.post("/maps/validate", response_model=ValidateMapResponse, tags=["maps"])
def validate_map(request: ValidateMapRequest) -> ValidateMapResponse:
    try:
        game_map = MapParser.parse(request.map_text, request.elevation_text)
    except MapFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ValidateMapResponse(
        valid=True,
        height=game_map.height,
        width=game_map.width,
        has_elevation=game_map.has_elevation,
        heroes=len(game_map.initial_heroes),
        guards=1 if game_map.initial_guard is not None else 0,
        machines=len(game_map.initial_machines),
        stones=len(game_map.initial_stones),
        chests=len(game_map.initial_chests),
        exits=len(game_map.exits),
    )


@router.post("/games", response_model=GameSnapshot, status_code=status.HTTP_201_CREATED)
def create_game(
    request: CreateGameRequest,
    service: GameService = Depends(get_game_service),
) -> GameSnapshot:
    try:
        return service.create(request)
    except MapFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/games/{game_id}", response_model=GameSnapshot)
def get_game(game_id: str, service: GameService = Depends(get_game_service)) -> GameSnapshot:
    try:
        return service.get(game_id)
    except GameNotFound as exc:
        raise _not_found(game_id) from exc


@router.post("/games/{game_id}/ticks", response_model=GameSnapshot)
def tick_game(
    game_id: str,
    request: TickRequest,
    service: GameService = Depends(get_game_service),
) -> GameSnapshot:
    try:
        return service.tick(game_id, request)
    except GameNotFound as exc:
        raise _not_found(game_id) from exc
    except SequenceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/games/{game_id}/reset", response_model=GameSnapshot)
def reset_game(game_id: str, service: GameService = Depends(get_game_service)) -> GameSnapshot:
    try:
        return service.reset(game_id)
    except GameNotFound as exc:
        raise _not_found(game_id) from exc


@router.delete("/games/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(game_id: str, service: GameService = Depends(get_game_service)) -> Response:
    try:
        service.delete(game_id)
    except GameNotFound as exc:
        raise _not_found(game_id) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/replays", response_model=ReplayResponse)
def replay(
    request: ReplayRequest,
    service: GameService = Depends(get_game_service),
) -> ReplayResponse:
    try:
        return service.replay(request)
    except MapFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.websocket("/games/{game_id}/ws")
async def game_socket(websocket: WebSocket, game_id: str) -> None:
    await websocket.accept()
    service = get_game_service()
    try:
        await websocket.send_json(service.get(game_id).model_dump(mode="json"))
        while True:
            payload = await websocket.receive_json()
            try:
                request = TickRequest.model_validate(payload)
                snapshot = service.tick(game_id, request)
                await websocket.send_json(snapshot.model_dump(mode="json"))
            except (ValidationError, SequenceConflict) as exc:
                await websocket.send_json({"error": str(exc), "status": 409})
    except GameNotFound:
        await websocket.send_json({"error": f"Partie introuvable : {game_id}", "status": 404})
        await websocket.close(code=4404)
    except WebSocketDisconnect:
        return
