import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import hash_password
from app.main import app
from app.models.enums import PlanCode, SubscriptionStatus, TenantStatus, UserRole
from app.models.plan import Plan
from app.models.store import Store
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.models.user import User

# Tests run against the real schema from `alembic upgrade head` (see
# backend's CI job / README) rather than Base.metadata.create_all, so the
# test suite exercises the same DDL that ships to production.
settings = get_settings()
# NullPool: each test gets a brand-new physical connection rather than a
# pooled one, so a mid-transaction error in one test can't leave a "dirty"
# connection for the next test to inherit.
test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """A session bound to a SAVEPOINT, so app-level `db.commit()` calls only
    release the savepoint — the outer transaction (and everything the test
    wrote) is rolled back when the fixture tears down, giving each test a
    clean, isolated slate against the real Postgres instance."""
    async with test_engine.connect() as connection:
        await connection.begin()
        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        async with session_factory() as session:
            yield session
        await connection.rollback()


@pytest_asyncio.fixture
async def scoped_session_factory(db_session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """A session factory bound to the exact same connection/savepoint as
    `db_session`. Some services (background tasks, the APScheduler jobs in
    Phase 8) deliberately open their own session via `AsyncSessionLocal()`
    rather than taking one via `Depends(get_db)` — a real, separate
    connection can't see this test's uncommitted savepoint data. Tests for
    those services monkeypatch the service module's `AsyncSessionLocal`
    name to this factory instead, e.g.:
        monkeypatch.setattr(
            "app.services.notification_service.AsyncSessionLocal", scoped_session_factory
        )
    """
    return async_sessionmaker(
        bind=db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def create_tenant_with_admin(
    db_session: AsyncSession,
    *,
    plan_code: PlanCode,
    max_users: int,
    tenant_name: str,
    admin_email: str,
    admin_password: str,
    max_stores: int = 1,
    max_printer_profiles: int = 1,
    features_json: dict | None = None,
) -> dict:
    """Seed a tenant + store + active subscription + one admin user."""
    plan = Plan(
        code=plan_code,
        name=plan_code.value.replace("_", " ").title(),
        price_paise=79_900,
        max_users=max_users,
        max_stores=max_stores,
        max_printer_profiles=max_printer_profiles,
        low_stock_alerts=bool((features_json or {}).get("low_stock_alerts", False)),
        saved_bill_days=7,
        features_json=features_json or {},
    )
    db_session.add(plan)
    await db_session.flush()

    tenant = Tenant(
        name=tenant_name,
        owner_email=f"owner-{tenant_name.lower().replace(' ', '-')}@test.dev",
        owner_phone="+911111111111",
        status=TenantStatus.ACTIVE,
    )
    db_session.add(tenant)
    await db_session.flush()

    store = Store(tenant_id=tenant.id, name=f"{tenant_name} - Main", is_default=True)
    db_session.add(store)
    await db_session.flush()

    now = datetime.now(UTC)
    subscription = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    db_session.add(subscription)
    await db_session.flush()

    admin = User(
        tenant_id=tenant.id,
        store_id=store.id,
        name=f"Admin {tenant_name}",
        email=admin_email,
        password_hash=hash_password(admin_password),
        role=UserRole.ADMIN,
    )
    db_session.add(admin)
    await db_session.flush()

    return {
        "tenant": tenant,
        "store": store,
        "plan": plan,
        "subscription": subscription,
        "admin": admin,
    }


@pytest_asyncio.fixture
async def lite_tenant(db_session: AsyncSession) -> dict:
    """Lite plan: max_users=2 (1 admin + 1 pos_user) — used for limit-boundary tests."""
    return await create_tenant_with_admin(
        db_session,
        plan_code=PlanCode.LITE,
        max_users=2,
        tenant_name="Tenant A",
        admin_email="admin@tenanta.dev",
        admin_password="Admin@123",
    )


@pytest_asyncio.fixture
async def pro_tenant(db_session: AsyncSession) -> dict:
    """Pro plan with low_stock_alerts + discount_rules_advanced + dashboard_range
    enabled and 3 printer profiles allowed — used for plan-feature-gating tests."""
    return await create_tenant_with_admin(
        db_session,
        plan_code=PlanCode.PRO,
        max_users=5,
        tenant_name="Tenant Pro",
        admin_email="admin@tenantpro.dev",
        admin_password="Admin@123",
        max_printer_profiles=3,
        features_json={
            "low_stock_alerts": True,
            "discount_rules_advanced": True,
            "dashboard_range": True,
        },
    )


@pytest_asyncio.fixture
async def pro_max_tenant(db_session: AsyncSession) -> dict:
    """Pro Max plan: unlimited users/stores/printer profiles, every feature
    flag on — used for plan-feature-gating tests at the top tier."""
    return await create_tenant_with_admin(
        db_session,
        plan_code=PlanCode.PRO_MAX,
        max_users=-1,
        tenant_name="Tenant Pro Max",
        admin_email="admin@tenantpromax.dev",
        admin_password="Admin@123",
        max_stores=-1,
        max_printer_profiles=-1,
        features_json={
            "low_stock_alerts": True,
            "multi_store": True,
            "dashboard_range": True,
            "discount_rules_advanced": True,
            "api_access": True,
        },
    )


@pytest_asyncio.fixture
async def all_plans(db_session: AsyncSession) -> dict:
    """Ensures Lite/Pro/Pro Max Plan rows all exist, idempotently — for
    platform-console tests that need to look up a plan (e.g. to change a
    tenant onto it) beyond whichever single tenant fixture the test also
    uses. Safe alongside lite_tenant/pro_tenant/pro_max_tenant regardless of
    fixture ordering, since it only creates a plan code that's missing."""
    defs = {
        PlanCode.LITE: (2, 1, 1, False),
        PlanCode.PRO: (5, 1, 3, True),
        PlanCode.PRO_MAX: (-1, -1, -1, True),
    }
    plans: dict[PlanCode, Plan] = {}
    for code, (max_users, max_stores, max_printer, low_stock) in defs.items():
        existing = await db_session.scalar(select(Plan).where(Plan.code == code))
        if existing is None:
            existing = Plan(
                code=code,
                name=code.value.replace("_", " ").title(),
                price_paise=79_900,
                max_users=max_users,
                max_stores=max_stores,
                max_printer_profiles=max_printer,
                low_stock_alerts=low_stock,
                saved_bill_days=7,
                features_json={"low_stock_alerts": low_stock},
            )
            db_session.add(existing)
            await db_session.flush()
        plans[code] = existing
    return plans


@pytest_asyncio.fixture
async def product_owner(db_session: AsyncSession) -> User:
    owner = User(
        tenant_id=None,
        store_id=None,
        name="Platform Owner",
        email="owner@storematetn.dev",
        password_hash=hash_password("Owner@123"),
        role=UserRole.PRODUCT_OWNER,
    )
    db_session.add(owner)
    await db_session.flush()
    return owner


async def create_pos_user(
    db_session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID,
    email: str,
    password: str,
    name: str = "Cashier",
) -> User:
    user = User(
        tenant_id=tenant_id,
        store_id=store_id,
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=UserRole.POS_USER,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def create_category_and_tax_profile(client: AsyncClient, headers: dict) -> tuple[str, str]:
    """Creates one category and one (standard 18% GST) tax profile via the
    real API and returns their ids — the two FKs every item needs."""
    category_resp = await client.post(
        "/api/v1/categories",
        json={"name_en": "Beverages", "name_ta": "பானங்கள்"},
        headers=headers,
    )
    tax_resp = await client.post(
        "/api/v1/settings/tax-profiles",
        json={"name": "GST 18%", "cgst_pct": 9, "sgst_pct": 9},
        headers=headers,
    )
    return category_resp.json()["id"], tax_resp.json()["id"]


async def login(client: AsyncClient, email: str, password: str) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
