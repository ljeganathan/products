from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.core.config import get_settings
from app.ws.router import router as ws_router


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="KOTMate TN API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    # Not under /api/v1 — CLAUDE.md §10/Phase 08: a single /ws/location/{id} channel
    # shared by the Kitchen Display and the POS grid, named for what it covers.
    app.include_router(ws_router)

    # Item image uploads (Phase 05, app/services/storage.py) — StaticFiles requires the
    # directory to exist before mounting.
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount(settings.UPLOAD_URL_PREFIX, StaticFiles(directory=upload_dir), name="uploads")

    return app


app = create_app()
