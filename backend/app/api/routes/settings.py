from __future__ import annotations
from fastapi import APIRouter
from app.schemas.settings import AppSettingsSchema, SettingsResponse
from app.services.settings_service import settings_service


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get(
    "",
    response_model=SettingsResponse,
    summary="Lire les paramètres sauvegardés",
    description="Retourne les paramètres persistés localement par le backend pour le frontend Godot.",
    operation_id="get_settings",
)
def get_settings() -> SettingsResponse:
    return SettingsResponse(settings=settings_service.load())


@router.put(
    "",
    response_model=SettingsResponse,
    summary="Sauvegarder les paramètres",
    description="Remplace et persiste les paramètres UI/audio/affichage ainsi que la stratégie de simulation par défaut.",
    operation_id="save_settings",
)
def save_settings(payload: AppSettingsSchema) -> SettingsResponse:
    return SettingsResponse(settings=settings_service.save(payload))


@router.post(
    "/reset",
    response_model=SettingsResponse,
    summary="Réinitialiser les paramètres",
    description="Réinitialise les paramètres aux valeurs par défaut puis les sauvegarde.",
    operation_id="reset_settings",
)
def reset_settings() -> SettingsResponse:
    return SettingsResponse(settings=settings_service.reset())
