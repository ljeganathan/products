import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import JWTError, decode_token
from app.db.session import get_db

_bearer_scheme = HTTPBearer(auto_error=True)


@dataclass(frozen=True)
class CurrentUser:
    """Built entirely from the access token's claims (Phase 02 `security.py`) — no DB
    round trip on every request. Access tokens are short-lived (30 min default), so a
    deactivation or role change takes effect within one token lifetime at worst.
    """

    id: uuid.UUID
    login_id: str
    role: str
    tenant_id: uuid.UUID | None
    location_ids: list[uuid.UUID]


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> CurrentUser:
    try:
        payload = decode_token(credentials.credentials)
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not an access token")

    tenant_id = payload.get("tenant_id")
    return CurrentUser(
        id=uuid.UUID(payload["sub"]),
        login_id=payload["user_id"],
        role=payload["role"],
        tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
        location_ids=[uuid.UUID(loc) for loc in payload.get("location_ids", [])],
    )


def require_role(*roles: str):
    """`Depends(require_role("tenant_admin", "pos_user"))` — 403s any other role."""

    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role for this route")
        return current_user

    return _dependency


async def require_tenant_scope(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Tenant-scoped routes: rejects `product_owner` (no `tenant_id`) and sets the RLS
    session var so Postgres enforces tenant isolation (CLAUDE.md §4, migration
    `dd586dfba4be_row_level_security_policies`) on every query this request makes.

    Uses `set_config(..., is_local=true)`, i.e. `SET LOCAL` semantics, scoped to the
    current transaction only — required, not cosmetic: `AsyncSession` connections are
    pooled and reused across unrelated requests, so a session-scoped (`is_local=false`)
    var would leak this request's tenant into whichever later request happens to reuse
    the same pooled connection. `is_local=true` resets automatically when this
    request's transaction ends (commit/rollback on session close), which is exactly
    when the connection goes back to the pool.
    """
    if current_user.tenant_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This route requires a tenant-scoped user")
    await db.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"),
        {"tid": str(current_user.tenant_id)},
    )
    return current_user


async def require_platform_scope(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Platform (`product_owner`) routes: sets `app.is_platform_admin` for the RLS
    policy's cross-tenant visibility branch. Same `is_local=true` reasoning as
    `require_tenant_scope` above.
    """
    if current_user.role != "product_owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This route requires product_owner")
    await db.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))
    return current_user
