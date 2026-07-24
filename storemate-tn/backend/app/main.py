import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.scheduler import shutdown_scheduler, start_scheduler

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # Production runs multiple gunicorn+uvicorn worker processes
    # (docker-compose.prod.yml); core/scheduler.py's file lock ensures only
    # one of them actually starts APScheduler, so it's safe to call this in
    # every worker's lifespan. SCHEDULER_ENABLED is the escape hatch to turn
    # the jobs off entirely (e.g. a one-off script importing this app).
    if settings.SCHEDULER_ENABLED:
        start_scheduler()
    if settings.ENV == "production" and any(
        "localhost" in origin or "127.0.0.1" in origin for origin in settings.cors_origins_list
    ):
        logger.warning(
            "ENV=production but CORS_ORIGINS still includes a localhost origin (%s) — "
            "set it to the real frontend domain(s) before going live.",
            settings.CORS_ORIGINS,
        )
    yield
    if settings.SCHEDULER_ENABLED:
        shutdown_scheduler()


app = FastAPI(title="StoreMate TN API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

Path(settings.MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
app.mount(settings.MEDIA_URL_PREFIX, StaticFiles(directory=settings.MEDIA_ROOT), name="media")
