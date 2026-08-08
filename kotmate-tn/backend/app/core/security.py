import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

TokenType = Literal["access", "refresh"]

_TEMP_PASSWORD_ALPHABET = string.ascii_letters + string.digits


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def generate_temp_password(length: int = 12) -> str:
    """One-time admin-reset password (CLAUDE.md §5 — resets are admin-triggered, no
    self-service email flow in v1). Shown once in the response; caller must hand it to
    the tenant admin out-of-band and the admin should change it on next login.
    """
    return "".join(secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(length))


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def _create_token(
    *,
    subject: uuid.UUID,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(
    *,
    user_id: uuid.UUID,
    login_id: str,
    role: str,
    tenant_id: uuid.UUID | None,
    location_ids: list[uuid.UUID],
) -> str:
    """Access token carries the claims RBAC/RLS dependencies (Phase 02 `deps.py`) need
    on every request, so they never have to hit the DB just to authorize a request.
    """
    settings = get_settings()
    return _create_token(
        subject=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims={
            "user_id": login_id,
            "role": role,
            "tenant_id": str(tenant_id) if tenant_id else None,
            "location_ids": [str(loc_id) for loc_id in location_ids],
        },
    )


def create_refresh_token(*, user_id: uuid.UUID) -> str:
    """Refresh tokens deliberately carry no role/tenant claims — refresh always
    re-reads the user from the DB (Phase 02 `/auth/refresh`) so a role change or
    deactivation between issuance and refresh takes effect immediately instead of
    surviving until the stale refresh token expires.
    """
    settings = get_settings()
    return _create_token(
        subject=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Raises `jose.JWTError` (including on expiry) — callers translate to 401."""
    settings = get_settings()
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


__all__ = [
    "JWTError",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "generate_temp_password",
    "hash_password",
    "verify_password",
]
