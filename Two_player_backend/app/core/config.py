from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "KAKAFANDODO Co-player Backend"
    api_prefix: str = "/api/v1"
    host: str = os.getenv("KAKAFANDODO_HOST", "127.0.0.1")
    port: int = int(os.getenv("KAKAFANDODO_PORT", "8000"))
    max_map_chars: int = int(os.getenv("KAKAFANDODO_MAX_MAP_CHARS", "1000000"))
    tick_ms: int = int(os.getenv("KAKAFANDODO_TICK_MS", "100"))
    cors_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv(
            "KAKAFANDODO_CORS_ORIGINS",
            "*",
        ).split(",")
        if item.strip()
    )


settings = Settings()
