from __future__ import annotations
import json
from pathlib import Path
from threading import Lock
from app.core.config import settings as app_config
from app.schemas.settings import AppSettingsSchema


class SettingsService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._path = app_config.settings_file
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> AppSettingsSchema:
        with self._lock:
            if not self._path.exists():
                valeur = AppSettingsSchema()
                self._write_unlocked(valeur)
                return valeur
            try:
                donnees = json.loads(self._path.read_text(encoding="utf-8"))
                return AppSettingsSchema.model_validate(donnees)
            except (OSError, json.JSONDecodeError, ValueError):
                valeur = AppSettingsSchema()
                self._write_unlocked(valeur)
                return valeur

    def save(self, valeur: AppSettingsSchema) -> AppSettingsSchema:
        with self._lock:
            self._write_unlocked(valeur)
        return valeur

    def reset(self) -> AppSettingsSchema:
        return self.save(AppSettingsSchema())

    def _write_unlocked(self, valeur: AppSettingsSchema) -> None:
        temp = self._path.with_suffix(self._path.suffix + ".tmp")
        temp.write_text(
            json.dumps(valeur.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp.replace(self._path)

    @property
    def path(self) -> Path:
        return self._path


settings_service = SettingsService()
