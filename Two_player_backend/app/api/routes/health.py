from fastapi import APIRouter, Depends

from app.api.dependencies import get_game_service
from app.services.game_service import GameService


router = APIRouter(tags=["system"])


@router.get("/health")
def health(service: GameService = Depends(get_game_service)) -> dict[str, object]:
    return {
        "status": "ok",
        "service": "kakafandodo-coplayer-backend",
        "version": "1.0.0",
        "active_games": service.count(),
    }
