from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: str = "development"

    DATABASE_URL: str = "postgresql+asyncpg://storemate:storemate@localhost:5432/storemate"

    JWT_SECRET: str = "change-me-in-env"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MIN: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    CORS_ORIGINS: str = "http://localhost:5173"

    # Local filesystem media storage (logos, etc). Mounted as a Docker volume
    # at /app/media. To move to S3-compatible object storage later, swap
    # `services/media_service.py`'s save/url logic only — callers just deal
    # in `logo_url` strings and never touch the filesystem directly.
    MEDIA_ROOT: str = "media"
    MEDIA_URL_PREFIX: str = "/media"
    MAX_LOGO_UPLOAD_MB: int = 5

    # Transactional email (low-stock alerts, Pro Max scheduled digests) via
    # plain SMTP — see services/email_service.py. Left unset in dev; the
    # service logs and skips instead of pretending to send when SMTP_HOST
    # is empty, so "no mail server configured" stays honest rather than
    # silently faking success.
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = "noreply@storematetn.in"
    SMTP_USE_TLS: bool = True

    # Escape hatch for the APScheduler jobs (low-stock scan, digest email).
    # Safe to leave on with multiple gunicorn workers (docker-compose.prod.yml)
    # — core/scheduler.py uses a file lock so only one worker process actually
    # starts APScheduler. Only turn this off entirely (e.g. a one-off script
    # or a horizontally-scaled multi-container deployment beyond the single
    # VPS this app targets) where even one scheduler instance is unwanted.
    SCHEDULER_ENABLED: bool = True

    # Login lockout (services/auth_service.py) — DB-backed so it's correct
    # across every gunicorn worker, not just the process that saw the
    # attempt.
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
