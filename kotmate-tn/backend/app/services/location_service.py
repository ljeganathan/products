import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Plan, TenantLocation
from app.schemas.locations import LocationCreateRequest, LocationUpdateRequest
from app.services.tenant_onboarding import get_active_plan


async def count_active_locations(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(TenantLocation)
            .where(TenantLocation.tenant_id == tenant_id, TenantLocation.is_active.is_(True))
        )
    ).scalar_one()


async def list_managed_locations(session: AsyncSession, tenant_id: uuid.UUID) -> list[TenantLocation]:
    rows = await session.execute(
        select(TenantLocation).where(TenantLocation.tenant_id == tenant_id).order_by(TenantLocation.name)
    )
    return list(rows.scalars().all())


async def get_location_or_404(
    session: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID
) -> TenantLocation:
    location = (
        await session.execute(
            select(TenantLocation).where(
                TenantLocation.id == location_id, TenantLocation.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found")
    return location


def _upgrade_required_for_location(plan: Plan | None) -> HTTPException:
    next_tier = "Pro" if not plan or plan.code == "lite" else "Pro Max"
    cap = plan.max_locations if plan else 1
    return HTTPException(
        status.HTTP_403_FORBIDDEN,
        f"You've reached your plan's limit of {cap} location(s). Upgrade to {next_tier} to add another.",
    )


async def create_location(
    session: AsyncSession, tenant_id: uuid.UUID, req: LocationCreateRequest
) -> TenantLocation:
    plan = await get_active_plan(session, tenant_id)
    active_count = await count_active_locations(session, tenant_id)
    if plan is None or active_count >= plan.max_locations:
        raise _upgrade_required_for_location(plan)

    location = TenantLocation(
        tenant_id=tenant_id,
        name=req.name,
        door_no=req.door_no,
        street=req.street,
        city=req.city,
        district=req.district,
        state=req.state,
        pincode=req.pincode,
        phone=req.phone,
        is_active=True,
    )
    session.add(location)
    await session.flush()
    return location


async def update_location(
    session: AsyncSession, tenant_id: uuid.UUID, location: TenantLocation, req: LocationUpdateRequest
) -> TenantLocation:
    data = req.model_dump(exclude_unset=True)

    # Re-activating a previously deactivated location is subject to the same cap as
    # creating a new one — otherwise deactivate-then-reactivate would be a silent
    # bypass of the plan limit.
    if data.get("is_active") is True and not location.is_active:
        plan = await get_active_plan(session, tenant_id)
        active_count = await count_active_locations(session, tenant_id)
        if plan is None or active_count >= plan.max_locations:
            raise _upgrade_required_for_location(plan)

    for field, value in data.items():
        setattr(location, field, value)
    await session.flush()
    return location
