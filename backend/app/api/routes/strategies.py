from __future__ import annotations
from fastapi import APIRouter
from app.engine.strategy_registry import DEFAULT_STRATEGY, strategy_catalog
from app.schemas.strategies import StrategiesResponse

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get(
    "",
    response_model=StrategiesResponse,
    summary="Lister les stratégies disponibles",
    description="Retourne dynamiquement les stratégies exposées par ce backend et indique la stratégie recommandée par défaut.",
    operation_id="list_strategies",
)
def list_strategies() -> StrategiesResponse:
    return StrategiesResponse.model_validate({
        "default_strategy": DEFAULT_STRATEGY,
        "strategies": strategy_catalog(),
    })
