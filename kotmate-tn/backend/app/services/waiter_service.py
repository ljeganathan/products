import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role, TenantLocation, User, Waiter
from app.schemas.waiters import WaiterCreateRequest, WaiterUpdateRequest


async def _validate_location(session: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID) -> None:
    exists = (
        await session.execute(
            select(TenantLocation.id).where(
                TenantLocation.id == location_id, TenantLocation.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "location_id does not belong to this tenant")


async def _validate_login_link(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    exclude_waiter_id: uuid.UUID | None = None,
) -> None:
    if user_id is None:
        return
    user = (
        await session.execute(
            select(User)
            .join(Role, Role.id == User.role_id)
            .where(User.id == user_id, User.tenant_id == tenant_id, Role.code == "waiter")
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "user_id must be a waiter-role login belonging to this tenant"
        )
    query = select(Waiter.id).where(Waiter.user_id == user_id)
    if exclude_waiter_id is not None:
        query = query.where(Waiter.id != exclude_waiter_id)
    already_linked = (await session.execute(query)).scalar_one_or_none()
    if already_linked is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That login is already linked to another waiter")


async def list_waiters(
    session: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID | None
) -> list[Waiter]:
    query = select(Waiter).where(Waiter.tenant_id == tenant_id)
    if location_id is not None:
        query = query.where(Waiter.location_id == location_id)
    rows = await session.execute(query.order_by(Waiter.waiter_number))
    return list(rows.scalars().all())


async def get_waiter_or_404(session: AsyncSession, tenant_id: uuid.UUID, waiter_id: uuid.UUID) -> Waiter:
    waiter = (
        await session.execute(select(Waiter).where(Waiter.id == waiter_id, Waiter.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if waiter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Waiter not found")
    return waiter


async def create_waiter(session: AsyncSession, tenant_id: uuid.UUID, req: WaiterCreateRequest) -> Waiter:
    await _validate_location(session, tenant_id, req.location_id)
    await _validate_login_link(session, tenant_id, req.user_id)

    waiter = Waiter(
        tenant_id=tenant_id,
        location_id=req.location_id,
        waiter_number=req.waiter_number,
        name=req.name,
        phone=req.phone,
        incentive_rate=req.incentive_rate,
        user_id=req.user_id,
        is_active=True,
    )
    session.add(waiter)
    await session.flush()
    return waiter


async def update_waiter(
    session: AsyncSession, tenant_id: uuid.UUID, waiter: Waiter, req: WaiterUpdateRequest
) -> Waiter:
    data = req.model_dump(exclude_unset=True)
    if "location_id" in data:
        await _validate_location(session, tenant_id, data["location_id"])
    if "user_id" in data:
        await _validate_login_link(session, tenant_id, data["user_id"], exclude_waiter_id=waiter.id)

    for field, value in data.items():
        setattr(waiter, field, value)

    await session.flush()
    return waiter


async def get_waiter_by_user_id(
    session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> Waiter | None:
    """Resolves a logged-in `waiter`-role user's own Waiter Master row, if linked — used
    by the POS screen (Phase 07) to auto-lock the waiter selector to themself.
    """
    return (
        await session.execute(
            select(Waiter).where(
                Waiter.tenant_id == tenant_id, Waiter.user_id == user_id, Waiter.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
