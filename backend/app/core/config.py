from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "KAKAFANDODO Backend"
    api_prefix: str = "/api/v1"
    host: str = os.getenv("KAKAFANDODO_HOST", "127.0.0.1")
    port: int = int(os.getenv("KAKAFANDODO_PORT", "8000"))
    max_upload_bytes: int = int(os.getenv("KAKAFANDODO_MAX_UPLOAD_BYTES", str(1024 * 1024)))
    output_dir: Path = Path(os.getenv("KAKAFANDODO_OUTPUT_DIR", "output"))


settings = Settings()
