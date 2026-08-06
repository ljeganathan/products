import uuid
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.session import async_session_maker
from app.models import (
    Category,
    Item,
    ItemSectionPrice,
    Plan,
    Role,
    SeatingSection,
    Subscription,
    Tenant,
    TenantLocation,
    User,
)

# Windows + asyncpg: the module-level engine's connection pool doesn't survive a
# per-test event loop teardown cleanly, so keep one loop for the whole module.
pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _set_platform_admin(session) -> None:
    """Bypass RLS for test setup, mirroring the `require_platform_scope` dependency
    Phase 02 will wire up for real product_owner requests.

    Uses set_config(), not `SET LOCAL x = :param` — Postgres's SET statement doesn't
    accept bind parameters at all (fails with a syntax error), parameterized or not;
    set_config() is a regular function call and takes them normally. `true` as the
    third arg scopes it to the current transaction only, same as SET LOCAL.
    """
    await session.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))


async def _set_tenant_scope(session, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_id)}
    )


async def _make_tenant_with_lite_plan(session) -> Tenant:
    tenant = Tenant(
        tenant_code=f"T{uuid.uuid4().hex[:5].upper()}",
        company_name="Test Hotel Co",
        door_no="12",
        street="Main Street",
        city="Chennai",
        district="Chennai",
        state="Tamil Nadu",
        pincode="600001",
    )
    session.add(tenant)
    await session.flush()

    plan = (await session.execute(select(Plan).where(Plan.code == "lite"))).scalar_one()
    session.add(
        Subscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status="active",
            billing_cycle="monthly",
            current_period_start=date.today(),
            current_period_end=date.today(),
        )
    )
    await session.flush()
    return tenant


@pytest.mark.asyncio
async def test_rls_blocks_writes_with_no_session_context():
    """Fail-closed check: an INSERT into a tenant-scoped table (RLS applies to
    `categories`, not to `tenants` itself — see docs/db-schema.md) with neither
    app.current_tenant_id nor app.is_platform_admin set must be rejected, not silently
    allowed. Uses a real tenant id (created via platform-admin bypass) so the failure
    is specifically the RLS policy, not an incidental FK violation.

    Deliberately uses its own throwaway engine/pool rather than the shared
    `async_session_maker`: the connection that hits the RLS error gets fully disposed
    here instead of being returned to (and later reused from) the pool other tests
    share — avoids a Windows/ProactorEventLoop asyncpg quirk where closing a connection
    that errored mid-transaction can wedge a *different*, later test's connection.
    """
    engine = create_async_engine(get_settings().APP_DATABASE_URL)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_maker() as session:
            await _set_platform_admin(session)
            tenant = await _make_tenant_with_lite_plan(session)
            await session.commit()
            tenant_id = tenant.id

        async with session_maker() as session:
            session.add(Category(tenant_id=tenant_id, name_en="Should Not Insert"))
            with pytest.raises(Exception):
                await session.flush()
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_tenant_location_user_roundtrip_and_isolation():
    """Acceptance criteria: insert a tenant + location + user (user_id, not email) and
    read it back through an async session; also proves RLS tenant isolation holds.
    """
    async with async_session_maker() as session:
        await _set_platform_admin(session)

        tenant = await _make_tenant_with_lite_plan(session)
        session.add(
            TenantLocation(
                tenant_id=tenant.id,
                name="Test Hotel - Main",
                door_no="12",
                street="Main Street",
                city="Chennai",
                district="Chennai",
                state="Tamil Nadu",
                pincode="600001",
            )
        )
        role = (await session.execute(select(Role).where(Role.code == "tenant_admin"))).scalar_one()
        # user_id is globally unique (Phase 02) and composed as {tenant_code}-{local
        # handle}, exactly as Phase 04 will do at real user-creation time.
        login_id = f"{tenant.tenant_code}-admin01"
        session.add(
            User(
                tenant_id=tenant.id,
                user_id=login_id,
                password_hash="not-a-real-hash",
                role_id=role.id,
                name="Test Admin",
            )
        )
        await session.commit()
        tenant_id = tenant.id

    # Read back scoped to this tenant.
    async with async_session_maker() as session:
        await _set_tenant_scope(session, tenant_id)
        fetched = (await session.execute(select(User).where(User.user_id == login_id))).scalar_one()
        assert fetched.name == "Test Admin"
        assert fetched.tenant_id == tenant_id

        location = (await session.execute(select(TenantLocation))).scalar_one()
        assert location.name == "Test Hotel - Main"

    # A different tenant context must see none of this tenant's rows.
    async with async_session_maker() as session:
        await _set_tenant_scope(session, uuid.uuid4())
        rows = (await session.execute(select(User).where(User.user_id == login_id))).scalars().all()
        assert rows == []


@pytest.mark.asyncio
async def test_item_section_price_fallback_and_override():
    """Acceptance criteria: an item with no item_section_prices row resolves to
    items.price; adding an override for one section changes only that section's price.
    """
    async with async_session_maker() as session:
        await _set_platform_admin(session)

        tenant = await _make_tenant_with_lite_plan(session)
        category = Category(tenant_id=tenant.id, name_en="Meals")
        session.add(category)
        await session.flush()

        item = Item(tenant_id=tenant.id, category_id=category.id, name_en="Meals", price=100)
        ac_section = SeatingSection(tenant_id=tenant.id, name_en="AC")
        non_ac_section = SeatingSection(tenant_id=tenant.id, name_en="Non-AC")
        session.add_all([item, ac_section, non_ac_section])
        await session.flush()

        item_id, ac_id, non_ac_id = item.id, ac_section.id, non_ac_section.id

        # No override rows yet — both sections must fall back to items.price.
        overrides = (
            await session.execute(select(ItemSectionPrice).where(ItemSectionPrice.item_id == item_id))
        ).scalars().all()
        assert overrides == []
        assert item.price == 100

        # Override AC only.
        session.add(ItemSectionPrice(tenant_id=tenant.id, item_id=item_id, section_id=ac_id, price=120))
        await session.commit()

        # SET LOCAL only lasts one transaction — commit() ended it, so re-apply before
        # the next queries.
        await _set_platform_admin(session)

        ac_override = (
            await session.execute(
                select(ItemSectionPrice).where(
                    ItemSectionPrice.item_id == item_id, ItemSectionPrice.section_id == ac_id
                )
            )
        ).scalar_one()
        assert ac_override.price == 120

        non_ac_override = (
            await session.execute(
                select(ItemSectionPrice).where(
                    ItemSectionPrice.item_id == item_id, ItemSectionPrice.section_id == non_ac_id
                )
            )
        ).scalar_one_or_none()
        assert non_ac_override is None  # Non-AC still falls back to items.price = 100
