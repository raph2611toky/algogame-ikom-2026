from __future__ import annotations
from fastapi import APIRouter
from app.api.routes import contracts, health, maps, settings, simulations, simulation_jobs, strategies
api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(contracts.router)
api_router.include_router(maps.router)
api_router.include_router(settings.router)
api_router.include_router(strategies.router)
api_router.include_router(simulation_jobs.router)
api_router.include_router(simulations.router)
