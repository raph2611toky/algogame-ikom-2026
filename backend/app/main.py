from __future__ import annotations

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Backend local de simulation et d'IA pour KAKAFANDODO / AlgoGames 2. "
            "La logique du jeu reste indépendante des animations Godot."
        ),
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
