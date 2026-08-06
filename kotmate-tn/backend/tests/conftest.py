import asyncio
import sys
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.core.security import hash_password
from app.db.session import async_session_maker, engine
from app.main import app
from app.models import Role, User

# Windows' default ProactorEventLoop has a well-known asyncpg connection-teardown bug
# (AttributeError / "Event loop is closed" noise from a background cancellation task
# firing after the loop closes) that doesn't reproduce on Linux CI. SelectorEventLoop
# doesn't have it and we don't need Proactor's subprocess support for these tests.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture(autouse=True)
async def _dispose_shared_engine_after_each_test():
    """`app.db.session.engine` is a module-level global, so its connection pool can
    outlive whichever event loop was active when a connection was first checked out.
    Disposing after every test forces the next test to open a fresh connection bound to
    its own (session-scoped) loop instead of reusing one from a stale loop — otherwise
    asyncpg raises "Task ... got Future ... attached to a different loop" on pool_pre_ping.
    """
    yield
    await engine.dispose()


# KNOWN LOCAL-WINDOWS-ONLY FLAKINESS (does not reproduce on Linux CI, matching the
# established pattern above): running the full suite together in one process on
# Windows can surface "got result for unknown protocol state" / "attached to a
# different loop" asyncpg errors in test_platform.py when *any* test_db_schema.py test
# ran earlier in the same session — reproduces even with only one of those two tests
# selected, and reordering test_db_schema.py's own throwaway-engine test to run last
# did not change the outcome, so the trigger is not that specific test's cleanup as
# originally suspected. Every test file passes cleanly on its own or paired with
# test_auth.py/test_health.py; only test_db_schema.py + test_platform.py in the same
# process reproduces it. Not chased further — this is Windows-local pytest-asyncio/
# asyncpg event-loop interaction, not an application bug, and CI runs on Linux. If it
# ever reproduces in CI, that would mean it's NOT Windows-specific and needs a real fix.


# Shared fixtures for every test module that needs an authenticated product_owner or
# tenant_admin — first introduced in test_platform.py/test_users.py, promoted here once
# a third module (Phase 05) needed the identical setup, so later phases just declare
# `tenant_admin` as a parameter instead of re-copying this boilerplate.


async def _set_platform_admin(session) -> None:
    await session.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))


async def _seed_product_owner(session) -> str:
    role = (await session.execute(select(Role).where(Role.code == "product_owner"))).scalar_one()
    login_id = f"owner-{uuid.uuid4().hex[:8]}"
    session.add(
        User(
            tenant_id=None,
            user_id=login_id,
            password_hash=hash_password("password123"),
            role_id=role.id,
            name=login_id,
            is_active=True,
        )
    )
    await session.flush()
    return login_id


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def owner_headers(client: AsyncClient) -> dict:
    async with async_session_maker() as session:
        await _set_platform_admin(session)
        login_id = await _seed_product_owner(session)
        await session.commit()

    resp = await client.post("/api/v1/auth/login", json={"user_id": login_id, "password": "password123"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _tenant_payload(**overrides) -> dict:
    suffix = uuid.uuid4().hex[:6]
    payload = {
        "company_name": f"Test Hotel {suffix}",
        "door_no": "12",
        "street": "Main Street",
        "city": "Chennai",
        "district": "Chennai",
        "state": "Tamil Nadu",
        "pincode": "600001",
        "plan_code": "lite",
        "billing_cycle": "monthly",
        "location_name": f"Test Hotel {suffix} - Main",
        "admin_local_handle": "admin01",
        "admin_name": "Test Admin",
        "admin_password": "password123",
    }
    payload.update(overrides)
    return payload


async def _onboard_tenant(client: AsyncClient, owner_headers: dict, **overrides) -> dict:
    resp = await client.post(
        "/api/v1/platform/tenants", json=_tenant_payload(**overrides), headers=owner_headers
    )
    assert resp.status_code == 201
    return resp.json()


async def _login(client: AsyncClient, login_id: str, password: str = "password123") -> dict:
    resp = await client.post("/api/v1/auth/login", json={"user_id": login_id, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def tenant_admin(client: AsyncClient, owner_headers: dict) -> dict:
    """A freshly onboarded Lite-tier tenant (max_users=2) plus its admin's auth headers."""
    tenant = await _onboard_tenant(client, owner_headers)
    headers = await _login(client, tenant["admin_login_id"])
    return {"tenant": tenant, "headers": headers}


@pytest_asyncio.fixture
async def pro_max_tenant_admin(client: AsyncClient, owner_headers: dict) -> dict:
    """Same as `tenant_admin` but on Pro Max — for tests exercising plan-gated features
    (item images, section pricing) that Lite deliberately blocks.
    """
    tenant = await _onboard_tenant(client, owner_headers, plan_code="pro_max")
    headers = await _login(client, tenant["admin_login_id"])
    return {"tenant": tenant, "headers": headers}


@pytest_asyncio.fixture
async def pro_tenant_admin(client: AsyncClient, owner_headers: dict) -> dict:
    """Same as `tenant_admin` but on Pro — the middle tier, needed for Phase 11's
    reports export gating (csv only, no pdf/excel, no multi-location) which is
    otherwise indistinguishable from testing only the Lite/Pro Max extremes.
    """
    tenant = await _onboard_tenant(client, owner_headers, plan_code="pro")
    headers = await _login(client, tenant["admin_login_id"])
    return {"tenant": tenant, "headers": headers}
