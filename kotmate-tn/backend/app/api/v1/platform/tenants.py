import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_temp_password, hash_password
from app.db.session import get_db
from app.models import Role, Tenant, User
from app.schemas.platform import (
    ChangePlanRequest,
    SubscriptionStatusUpdate,
    TenantAdminPasswordResetResponse,
    TenantCreateRequest,
    TenantDetail,
    TenantSummary,
    TenantUpdateRequest,
)
from app.services.tenant_onboarding import (
    build_tenant_detail,
    build_tenant_summary,
    change_plan,
    get_active_subscription,
    onboard_tenant,
)

router = APIRouter(prefix="/tenants", tags=["platform-tenants"])


async def _reapply_platform_scope(db: AsyncSession) -> None:
    """`require_platform_scope` sets `app.is_platform_admin` scoped to the request's
    transaction (`is_local=true`, see `deps.py`) — `db.commit()` ends that transaction,
    so any RLS-scoped read (e.g. `subscriptions`, via `build_tenant_detail`) after a
    mid-request commit needs this re-applied first, or it silently sees zero rows.
    """
    await db.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))


async def _get_tenant_or_404(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return tenant


@router.post("", response_model=TenantDetail, status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreateRequest, db: AsyncSession = Depends(get_db)) -> TenantDetail:
    try:
        tenant = await onboard_tenant(db, payload)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A tenant/admin login with those details already exists"
        ) from exc
    await _reapply_platform_scope(db)
    return await build_tenant_detail(db, tenant)


@router.get("", response_model=list[TenantSummary])
async def list_tenants(db: AsyncSession = Depends(get_db)) -> list[TenantSummary]:
    tenants = (await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))).scalars().all()
    return [await build_tenant_summary(db, tenant) for tenant in tenants]


@router.get("/{tenant_id}", response_model=TenantDetail)
async def get_tenant(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> TenantDetail:
    tenant = await _get_tenant_or_404(db, tenant_id)
    return await build_tenant_detail(db, tenant)


@router.patch("/{tenant_id}", response_model=TenantDetail)
async def update_tenant(
    tenant_id: uuid.UUID, payload: TenantUpdateRequest, db: AsyncSession = Depends(get_db)
) -> TenantDetail:
    tenant = await _get_tenant_or_404(db, tenant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)
    await db.commit()
    await _reapply_platform_scope(db)
    return await build_tenant_detail(db, tenant)


@router.post("/{tenant_id}/reset-admin-password", response_model=TenantAdminPasswordResetResponse)
async def reset_tenant_admin_password(
    tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> TenantAdminPasswordResetResponse:
    """Platform-admin-triggered reset for a tenant's own admin login — there is no
    self-service/email flow in v1 (CLAUDE.md §5). Resets the tenant's oldest active
    `tenant_admin` account and returns the one-time password for the platform operator
    to hand off out-of-band; it is never logged or stored in plaintext.
    """
    tenant = await _get_tenant_or_404(db, tenant_id)
    admin_user = (
        await db.execute(
            select(User)
            .join(Role, Role.id == User.role_id)
            .where(User.tenant_id == tenant.id, Role.code == "tenant_admin")
            .order_by(User.created_at)
        )
    ).scalars().first()
    if admin_user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant has no admin account")

    temp_password = generate_temp_password()
    admin_user.password_hash = hash_password(temp_password)
    await db.commit()
    return TenantAdminPasswordResetResponse(admin_login_id=admin_user.user_id, temp_password=temp_password)


@router.post("/{tenant_id}/change-plan", response_model=TenantDetail)
async def change_tenant_plan(
    tenant_id: uuid.UUID, payload: ChangePlanRequest, db: AsyncSession = Depends(get_db)
) -> TenantDetail:
    tenant = await _get_tenant_or_404(db, tenant_id)
    await change_plan(db, tenant, payload.plan_code, payload.billing_cycle)
    await db.commit()
    await _reapply_platform_scope(db)
    return await build_tenant_detail(db, tenant)


@router.patch("/{tenant_id}/subscription-status", response_model=TenantDetail)
async def update_subscription_status(
    tenant_id: uuid.UUID, payload: SubscriptionStatusUpdate, db: AsyncSession = Depends(get_db)
) -> TenantDetail:
    tenant = await _get_tenant_or_404(db, tenant_id)
    subscription = await get_active_subscription(db, tenant.id)
    if subscription is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Tenant has no active subscription")
    subscription.status = payload.status
    await db.commit()
    await _reapply_platform_scope(db)
    return await build_tenant_detail(db, tenant)
