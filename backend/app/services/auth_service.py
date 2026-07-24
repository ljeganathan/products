import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.enums import TenantStatus
from app.models.user import User
from app.repositories.tenant_repository import TenantRepository
from app.repositories.user_repository import UserRepository


async def _check_tenant_active(db: AsyncSession, user: User) -> None:
    """Blocks login/refresh for a suspended or cancelled tenant's users.

    Already-issued access tokens (30 min TTL) still work until they expire —
    there's no session store to revoke them early in this stateless-JWT
    design (CLAUDE.md's "no Redis" constraint), so suspension takes full
    effect on the next login or refresh, not instantly mid-session.
    """
    if user.tenant_id is None:
        return
    tenant = await TenantRepository(db).get_by_id(user.tenant_id)
    if tenant is not None and tenant.status in (TenantStatus.SUSPENDED, TenantStatus.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This store's account is suspended. Contact StoreMate TN support.",
        )


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    """Verifies credentials with a DB-backed lockout after repeated failures
    (Phase 9 hardening) — see `User.failed_login_attempts`/`locked_until`
    for why this lives on the row rather than in-memory/Redis.

    A failed attempt commits immediately rather than waiting for the
    caller's own commit (which only happens on the success path in
    api/v1/auth.py) — otherwise the incremented counter would be rolled
    back when the session closes after this function raises.
    """
    repo = UserRepository(db)
    user = await repo.get_by_email(email)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    now = datetime.now(UTC)
    if user.locked_until is not None and user.locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many failed login attempts. Try again after "
                f"{user.locked_until.strftime('%H:%M UTC')}."
            ),
        )

    if not verify_password(password, user.password_hash):
        settings = get_settings()
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        await db.flush()

    await _check_tenant_active(db, user)
    return user


def issue_tokens(user: User) -> tuple[str, str]:
    access_token = create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, store_id=user.store_id, role=user.role.value
    )
    refresh_token = create_refresh_token(user_id=user.id)
    return access_token, refresh_token


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> str:
    try:
        payload = decode_token(refresh_token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        ) from exc

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")

    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(sub))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer active"
        )
    await _check_tenant_active(db, user)

    return create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, store_id=user.store_id, role=user.role.value
    )
