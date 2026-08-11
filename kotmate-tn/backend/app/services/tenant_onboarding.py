import re
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import BILLABLE_ROLE_CODES
from app.core.security import hash_password
from app.models import Plan, Role, SeatingSection, Subscription, Tenant, TenantLocation, User
from app.schemas.platform import TenantCreateRequest, TenantDetail, TenantSummary

_PERIOD_LENGTH = {"monthly": timedelta(days=30), "yearly": timedelta(days=365)}

# name_en, name_ta, is_seating (CLAUDE.md §9/§11) — seeded once per new tenant.
_DEFAULT_SECTIONS = [
    ("AC", "ஏசி", True),
    ("Non-AC", "ஏசி இல்லை", True),
    ("Rooftop", "மொட்டை மாடி", True),
    ("Family", "குடும்பம்", True),
    ("Takeaway", "பார்சல்", False),
    ("Online Delivery", "ஆன்லைன் டெலிவரி", False),
]


async def generate_tenant_code(session: AsyncSession, company_name: str) -> str:
    """Short uppercase prefix (CLAUDE.md §5) — initials of each word in the company
    name, falling back to the first word itself for a single-word name, with a
    numeric suffix on collision. Always 2-10 chars to satisfy the DB CHECK constraint.
    """
    words = re.findall(r"[A-Za-z0-9]+", company_name.upper())
    base = "".join(w[0] for w in words)[:8] if len(words) >= 2 else (words[0] if words else "")[:8]
    if len(base) < 2:
        base = (base + "TENANT")[:8]

    candidate = base
    suffix = 1
    while True:
        existing = await session.execute(select(Tenant.id).where(Tenant.tenant_code == candidate))
        if existing.scalar_one_or_none() is None:
            return candidate
        suffix += 1
        candidate = f"{base}{suffix}"[:10]


async def onboard_tenant(session: AsyncSession, req: TenantCreateRequest) -> Tenant:
    """Creates tenant + subscription + default location + tenant_admin user + default
    seating sections in one transaction (CLAUDE.md §4/§5/§11, Phase 03 scope) — the
    caller commits. Raises `sqlalchemy.exc.IntegrityError` on a genuine uniqueness
    collision (e.g. the composed admin login id already exists somewhere).
    """
    plan = (await session.execute(select(Plan).where(Plan.code == req.plan_code))).scalar_one()
    tenant_admin_role = (
        await session.execute(select(Role).where(Role.code == "tenant_admin"))
    ).scalar_one()

    tenant_code = await generate_tenant_code(session, req.company_name)
    tenant = Tenant(
        tenant_code=tenant_code,
        company_name=req.company_name,
        email=req.email,
        phone=req.phone,
        door_no=req.door_no,
        street=req.street,
        city=req.city,
        district=req.district,
        state=req.state,
        pincode=req.pincode,
    )
    session.add(tenant)
    await session.flush()

    today = date.today()
    session.add(
        Subscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status="active",
            billing_cycle=req.billing_cycle,
            current_period_start=today,
            current_period_end=today + _PERIOD_LENGTH[req.billing_cycle],
        )
    )

    session.add(
        TenantLocation(
            tenant_id=tenant.id,
            name=req.location_name,
            door_no=req.door_no,
            street=req.street,
            city=req.city,
            district=req.district,
            state=req.state,
            pincode=req.pincode,
        )
    )

    login_id = f"{tenant_code}{req.admin_local_handle}"
    session.add(
        User(
            tenant_id=tenant.id,
            user_id=login_id,
            password_hash=hash_password(req.admin_password),
            role_id=tenant_admin_role.id,
            name=req.admin_name,
            is_active=True,
        )
    )

    for order, (name_en, name_ta, is_seating) in enumerate(_DEFAULT_SECTIONS):
        session.add(
            SeatingSection(
                tenant_id=tenant.id,
                name_en=name_en,
                name_ta=name_ta,
                is_seating=is_seating,
                display_order=order,
            )
        )

    await session.flush()
    return tenant


async def change_plan(
    session: AsyncSession, tenant: Tenant, plan_code: str, billing_cycle: str
) -> Subscription:
    """New subscriptions row rather than mutating in place, so billing history survives
    a plan change (docs/db-schema.md — `subscriptions` is intentionally 1:many per
    tenant, latest `status='active'` row wins per the location-cap trigger's own query).
    """
    plan = (await session.execute(select(Plan).where(Plan.code == plan_code))).scalar_one()

    current = (
        await session.execute(
            select(Subscription)
            .where(Subscription.tenant_id == tenant.id, Subscription.status == "active")
            .order_by(Subscription.created_at.desc())
        )
    ).scalars().first()
    if current is not None:
        current.status = "cancelled"

    today = date.today()
    new_subscription = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        billing_cycle=billing_cycle,
        current_period_start=today,
        current_period_end=today + _PERIOD_LENGTH[billing_cycle],
    )
    session.add(new_subscription)
    await session.flush()
    return new_subscription


async def get_active_subscription(session: AsyncSession, tenant_id: uuid.UUID) -> Subscription | None:
    return (
        await session.execute(
            select(Subscription)
            .where(Subscription.tenant_id == tenant_id, Subscription.status == "active")
            .order_by(Subscription.created_at.desc())
        )
    ).scalars().first()


async def get_active_plan(session: AsyncSession, tenant_id: uuid.UUID) -> Plan | None:
    subscription = await get_active_subscription(session, tenant_id)
    if subscription is None:
        return None
    return (await session.execute(select(Plan).where(Plan.id == subscription.plan_id))).scalar_one()


async def count_active_billable_users(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Active tenant_admin + pos_user seats, counted against `plans.max_users`
    (CLAUDE.md §6) — waiter/kitchen seats are uncapped. Shared by the Phase 03 tenant
    summary and the Phase 04 seat-cap check so both always agree on what counts.
    """
    return (
        await session.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
                User.role_id.in_(select(Role.id).where(Role.code.in_(BILLABLE_ROLE_CODES))),
            )
        )
    ).scalar_one()


async def build_tenant_summary(session: AsyncSession, tenant: Tenant) -> TenantSummary:
    subscription = await get_active_subscription(session, tenant.id)
    plan = (
        (await session.execute(select(Plan).where(Plan.id == subscription.plan_id))).scalar_one()
        if subscription
        else None
    )

    active_user_count = await count_active_billable_users(session, tenant.id)

    active_location_count = (
        await session.execute(
            select(func.count())
            .select_from(TenantLocation)
            .where(TenantLocation.tenant_id == tenant.id, TenantLocation.is_active.is_(True))
        )
    ).scalar_one()

    admin_user = (
        await session.execute(
            select(User)
            .where(User.tenant_id == tenant.id)
            .join(Role, Role.id == User.role_id)
            .where(Role.code == "tenant_admin")
            .order_by(User.created_at)
        )
    ).scalars().first()

    return TenantSummary(
        id=tenant.id,
        tenant_code=tenant.tenant_code,
        company_name=tenant.company_name,
        is_active=tenant.is_active,
        plan_code=plan.code if plan else None,
        subscription_status=subscription.status if subscription else None,
        billing_cycle=subscription.billing_cycle if subscription else None,
        active_user_count=active_user_count,
        max_users=plan.max_users if plan else None,
        active_location_count=active_location_count,
        max_locations=plan.max_locations if plan else None,
        admin_login_id=admin_user.user_id if admin_user else None,
        current_period_end=subscription.current_period_end if subscription else None,
    )


async def build_tenant_detail(session: AsyncSession, tenant: Tenant) -> TenantDetail:
    summary = await build_tenant_summary(session, tenant)
    subscription = await get_active_subscription(session, tenant.id)
    return TenantDetail(
        **summary.model_dump(),
        email=tenant.email,
        phone=tenant.phone,
        door_no=tenant.door_no,
        street=tenant.street,
        city=tenant.city,
        district=tenant.district,
        state=tenant.state,
        pincode=tenant.pincode,
        current_period_start=subscription.current_period_start if subscription else None,
        created_at=tenant.created_at,
    )
