import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
from app.core.security import (
    JWTError,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.db.session import get_db
from app.models import PlatformSettings, Role, Tenant, User, UserLocationAccess
from app.schemas.auth import LoginRequest, MeResponse, RefreshRequest, TokenResponse
from app.services.stock_service import is_stock_tracking_enabled
from app.services.tenant_onboarding import get_active_plan

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID_CREDENTIALS = HTTPException(
    status.HTTP_401_UNAUTHORIZED, "Invalid user ID or password"
)
_INVALID_REFRESH = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")


async def _bypass_rls_for_login(db: AsyncSession) -> None:
    """Login/refresh are unauthenticated — they don't know the caller's tenant yet, so
    the user lookup must cross tenant boundaries by design (`users.user_id` is globally
    unique, Phase 02 migration `3d908345eda4`). `is_local=true` scopes this to the
    current request's transaction only (see `deps.require_platform_scope`).
    """
    await db.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))


async def _load_role_code(db: AsyncSession, role_id: uuid.UUID) -> str:
    return (await db.execute(select(Role.code).where(Role.id == role_id))).scalar_one()


async def _load_location_ids(db: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    rows = await db.execute(
        select(UserLocationAccess.location_id).where(UserLocationAccess.user_id == user_id)
    )
    return list(rows.scalars().all())


async def _reject_if_maintenance_mode(db: AsyncSession, role_code: str) -> None:
    """`platform_settings` (Phase 03) isn't tenant-scoped, so no RLS bypass is needed
    to read it — only `product_owner` logs in while maintenance mode is on.
    """
    if role_code == "product_owner":
        return
    settings_row = (
        await db.execute(select(PlatformSettings).where(PlatformSettings.id == 1))
    ).scalar_one()
    if settings_row.maintenance_mode:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            settings_row.maintenance_message or "KOTMate TN is undergoing scheduled maintenance.",
        )


def _issue_tokens(*, user: User, role_code: str, location_ids: list[uuid.UUID]) -> TokenResponse:
    access_token = create_access_token(
        user_id=user.id,
        login_id=user.user_id,
        role=role_code,
        tenant_id=user.tenant_id,
        location_ids=location_ids,
    )
    refresh_token = create_refresh_token(user_id=user.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=role_code,
        tenant_id=str(user.tenant_id) if user.tenant_id else None,
        login_id=user.user_id,
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    await _bypass_rls_for_login(db)

    user = (
        await db.execute(select(User).where(User.user_id == payload.user_id))
    ).scalar_one_or_none()

    # Same generic error whether the user_id doesn't exist, the password is wrong, or
    # the account is deactivated — avoids leaking which case it was.
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise _INVALID_CREDENTIALS

    role_code = await _load_role_code(db, user.role_id)
    await _reject_if_maintenance_mode(db, role_code)
    location_ids = await _load_location_ids(db, user.id)
    return _issue_tokens(user=user, role_code=role_code, location_ids=location_ids)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        claims = decode_token(payload.refresh_token)
    except JWTError as exc:
        raise _INVALID_REFRESH from exc

    if claims.get("type") != "refresh":
        raise _INVALID_REFRESH

    await _bypass_rls_for_login(db)

    user = (await db.execute(select(User).where(User.id == uuid.UUID(claims["sub"])))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise _INVALID_REFRESH

    role_code = await _load_role_code(db, user.role_id)
    await _reject_if_maintenance_mode(db, role_code)
    location_ids = await _load_location_ids(db, user.id)
    return _issue_tokens(user=user, role_code=role_code, location_ids=location_ids)


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> MeResponse:
    if current_user.tenant_id is None:
        return MeResponse(
            login_id=current_user.login_id,
            role=current_user.role,
            tenant_id=None,
            tenant_code=None,
            company_name=None,
            plan_code=None,
            max_users=None,
            max_locations=None,
            features=None,
            stock_tracking_enabled=False,
        )

    # `/me` serves every tenant-scoped role, not just one — set the RLS session var
    # directly (`require_tenant_scope` would 403 a product_owner caller, handled above).
    await db.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"),
        {"tid": str(current_user.tenant_id)},
    )
    tenant = (await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))).scalar_one()
    plan = await get_active_plan(db, current_user.tenant_id)

    return MeResponse(
        login_id=current_user.login_id,
        role=current_user.role,
        tenant_id=str(current_user.tenant_id),
        tenant_code=tenant.tenant_code,
        company_name=tenant.company_name,
        plan_code=plan.code if plan else None,
        max_users=plan.max_users if plan else None,
        max_locations=plan.max_locations if plan else None,
        features=plan.features if plan else None,
        stock_tracking_enabled=is_stock_tracking_enabled(tenant, plan.features if plan else None),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(_current_user=Depends(get_current_user)) -> None:
    """Stateless JWT logout: there is no server-side refresh-token blacklist in v1, so
    this only confirms the caller held a valid access token — the client is
    responsible for discarding both tokens. A revocation store is a future concern if
    early token invalidation (e.g. on password change) becomes a requirement.
    """
    return None
