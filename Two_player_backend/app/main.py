from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Moteur autoritaire temps réel pour KAKAFANDODO Twist 2 Co-player.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials="*" not in settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "health": f"{settings.api_prefix}/health",
        "openapi": "/docs",
    }
