import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import BILLABLE_ROLE_CODES
from app.core.security import hash_password
from app.models import Role, Tenant, TenantLocation, User, UserLocationAccess
from app.schemas.users import UserCreateRequest, UserResponse, UserUpdateRequest
from app.services.tenant_onboarding import count_active_billable_users, get_active_plan


async def _get_role_or_400(session: AsyncSession, code: str) -> Role:
    role = (await session.execute(select(Role).where(Role.code == code))).scalar_one_or_none()
    if role is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown role '{code}'")
    return role


async def _validate_location_ids(
    session: AsyncSession, tenant_id: uuid.UUID, location_ids: list[uuid.UUID]
) -> None:
    if not location_ids:
        return
    rows = (
        await session.execute(
            select(TenantLocation.id).where(
                TenantLocation.tenant_id == tenant_id, TenantLocation.id.in_(location_ids)
            )
        )
    ).scalars().all()
    if set(rows) != set(location_ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "One or more locations do not belong to this tenant")


async def _replace_location_access(
    session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID, location_ids: list[uuid.UUID]
) -> None:
    await session.execute(
        delete(UserLocationAccess).where(UserLocationAccess.user_id == user_id)
    )
    for location_id in location_ids:
        session.add(
            UserLocationAccess(tenant_id=tenant_id, user_id=user_id, location_id=location_id)
        )


async def _enforce_seat_cap(session: AsyncSession, tenant_id: uuid.UUID, role_code: str) -> None:
    """Reject if adding one more billable (tenant_admin/pos_user) seat would exceed
    `plan.max_users` (CLAUDE.md §6). Waiter/kitchen seats are uncapped.
    """
    if role_code not in BILLABLE_ROLE_CODES:
        return
    plan = await get_active_plan(session, tenant_id)
    if plan is None or plan.max_users is None:
        return
    current_count = await count_active_billable_users(session, tenant_id)
    if current_count >= plan.max_users:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Plan seat limit reached ({plan.max_users} users). Upgrade your plan to add more users.",
        )


def _to_response(user: User, role_code: str, tenant_code: str, location_ids: list[uuid.UUID]) -> UserResponse:
    prefix = f"{tenant_code}-"
    local_handle = user.user_id[len(prefix):] if user.user_id.startswith(prefix) else user.user_id
    return UserResponse(
        id=user.id,
        user_id=user.user_id,
        local_handle=local_handle,
        name=user.name,
        phone=user.phone,
        role=role_code,
        incentive_rate=float(user.incentive_rate) if user.incentive_rate is not None else None,
        location_ids=location_ids,
        is_active=user.is_active,
        created_at=user.created_at,
    )


async def _load_location_ids(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    rows = await session.execute(
        select(UserLocationAccess.location_id).where(UserLocationAccess.user_id == user_id)
    )
    return list(rows.scalars().all())


async def list_users(session: AsyncSession, tenant: Tenant) -> list[UserResponse]:
    rows = (
        await session.execute(
            select(User, Role.code)
            .join(Role, Role.id == User.role_id)
            .where(User.tenant_id == tenant.id)
            .order_by(User.created_at)
        )
    ).all()
    responses = []
    for user, role_code in rows:
        location_ids = await _load_location_ids(session, user.id)
        responses.append(_to_response(user, role_code, tenant.tenant_code, location_ids))
    return responses


async def get_user_or_404(session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User:
    user = (
        await session.execute(
            select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


async def create_user(session: AsyncSession, tenant: Tenant, req: UserCreateRequest) -> UserResponse:
    role = await _get_role_or_400(session, req.role)
    await _enforce_seat_cap(session, tenant.id, req.role)
    await _validate_location_ids(session, tenant.id, req.location_ids)

    login_id = f"{tenant.tenant_code}-{req.local_handle}"
    existing = (await session.execute(select(User.id).where(User.user_id == login_id))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Login id '{login_id}' is already in use")

    user = User(
        tenant_id=tenant.id,
        user_id=login_id,
        password_hash=hash_password(req.password),
        role_id=role.id,
        name=req.name,
        phone=req.phone,
        incentive_rate=req.incentive_rate,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    await _replace_location_access(session, tenant.id, user.id, req.location_ids)
    await session.flush()

    return _to_response(user, req.role, tenant.tenant_code, req.location_ids)


async def update_user(
    session: AsyncSession, tenant: Tenant, user: User, req: UserUpdateRequest
) -> UserResponse:
    old_role_code = (
        await session.execute(select(Role.code).where(Role.id == user.role_id))
    ).scalar_one()
    new_role_code = req.role if req.role is not None else old_role_code
    new_is_active = req.is_active if req.is_active is not None else user.is_active

    if req.incentive_rate is not None and new_role_code != "pos_user":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "incentive_rate can only be set for role=pos_user")

    # Only re-check the seat cap when this update newly makes the user an active
    # billable seat (role change and/or reactivation) — shrinking never needs a check,
    # and a user already counted as billable-active before this update stays counted.
    was_billable_active = old_role_code in BILLABLE_ROLE_CODES and user.is_active
    will_be_billable_active = new_role_code in BILLABLE_ROLE_CODES and new_is_active
    if will_be_billable_active and not was_billable_active:
        await _enforce_seat_cap(session, tenant.id, new_role_code)

    if req.role is not None:
        role = await _get_role_or_400(session, req.role)
        user.role_id = role.id
    if req.name is not None:
        user.name = req.name
    if req.phone is not None:
        user.phone = req.phone
    if req.incentive_rate is not None:
        user.incentive_rate = req.incentive_rate
    elif new_role_code != "pos_user":
        user.incentive_rate = None
    if req.is_active is not None:
        user.is_active = req.is_active

    if req.location_ids is not None:
        await _validate_location_ids(session, tenant.id, req.location_ids)
        await _replace_location_access(session, tenant.id, user.id, req.location_ids)

    await session.flush()
    location_ids = await _load_location_ids(session, user.id)
    return _to_response(user, new_role_code, tenant.tenant_code, location_ids)


async def reset_password(session: AsyncSession, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    await session.flush()
