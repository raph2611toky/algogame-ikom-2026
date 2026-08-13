from __future__ import annotations
from fastapi import APIRouter
from app.schemas.health import HealthResponse
router = APIRouter(tags=['health'])

@router.get('/health', response_model=HealthResponse, summary='Vérifier le backend', description="Retourne l'état du service, la version de contrat et la stratégie IA recommandée.", operation_id='health_check')
def health() -> HealthResponse:
    return HealthResponse(status='ok', service='kakafandodo-backend', contract='1.0', strategy='portfolio_v5')
