from fastapi import APIRouter

from app.api.routes import contracts, games, health


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(contracts.router)
api_router.include_router(games.router)
