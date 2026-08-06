import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.models import Tenant
from app.schemas.users import (
    PasswordResetRequest,
    SeatUsage,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.services.tenant_onboarding import count_active_billable_users, get_active_plan
from app.services.user_management import create_user, get_user_or_404, list_users, reset_password, update_user

# Every route here is tenant_admin-only (CLAUDE.md §5, Phase 04) and tenant-scoped.
router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_tenant_scope), Depends(require_role("tenant_admin"))],
)


async def _get_tenant(db: AsyncSession, current_user: CurrentUser) -> Tenant:
    return (await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))).scalar_one()


@router.get("", response_model=list[UserResponse])
async def list_tenant_users(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    tenant = await _get_tenant(db, current_user)
    return await list_users(db, tenant)


@router.get("/seat-usage", response_model=SeatUsage)
async def get_seat_usage(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SeatUsage:
    plan = await get_active_plan(db, current_user.tenant_id)
    count = await count_active_billable_users(db, current_user.tenant_id)
    return SeatUsage(active_billable_users=count, max_users=plan.max_users if plan else None)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_user(
    payload: UserCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    tenant = await _get_tenant(db, current_user)
    try:
        result = await create_user(db, tenant, payload)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "That login handle is already in use") from exc
    return result


@router.patch("/{user_id}", response_model=UserResponse)
async def update_tenant_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    tenant = await _get_tenant(db, current_user)
    user = await get_user_or_404(db, tenant.id, user_id)
    result = await update_user(db, tenant, user, payload)
    await db.commit()
    return result


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_tenant_user_password(
    user_id: uuid.UUID,
    payload: PasswordResetRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    tenant = await _get_tenant(db, current_user)
    user = await get_user_or_404(db, tenant.id, user_id)
    await reset_password(db, user, payload.new_password)
    await db.commit()
