from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENV: str = "development"
    # Superuser/migration connection — Alembic only. Never used by the running app.
    DATABASE_URL: str = "postgresql+asyncpg://kotmate:kotmate@localhost:5432/kotmate"
    # Non-superuser connection the app actually runs as, so Postgres RLS (CLAUDE.md §4,
    # Phase 01) is genuinely enforced — a superuser bypasses RLS regardless of FORCE.
    APP_DATABASE_URL: str = "postgresql+asyncpg://kotmate_app:kotmate_app@localhost:5432/kotmate"
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Local-disk item image storage (Phase 05) — served back at UPLOAD_URL_PREFIX,
    # abstracted behind app/services/storage.py so swapping to S3/Azure Blob later is a
    # one-file change (CLAUDE.md §2).
    UPLOAD_DIR: str = "uploads"
    UPLOAD_URL_PREFIX: str = "/uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
