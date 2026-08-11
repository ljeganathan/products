import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.deps import require_platform_scope, require_role, require_tenant_scope
from app.core.security import hash_password
from app.db.session import async_session_maker
from app.main import app
from app.models import Plan, Role, Subscription, Tenant, User

# Windows + asyncpg: keep one event loop for the whole module (see test_db_schema.py).
pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _set_platform_admin(session) -> None:
    await session.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))


def _unique_code() -> str:
    return f"T{uuid.uuid4().hex[:5].upper()}"


async def _seed_tenant(session) -> Tenant:
    tenant = Tenant(
        tenant_code=_unique_code(),
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


async def _seed_user(
    session, *, tenant: Tenant | None, login_id: str, role_code: str, password: str = "password123"
) -> User:
    role = (await session.execute(select(Role).where(Role.code == role_code))).scalar_one()
    user = User(
        tenant_id=tenant.id if tenant else None,
        user_id=login_id,
        password_hash=hash_password(password),
        role_id=role.id,
        name=login_id,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


def _forge_expired_access_token(*, user_id: uuid.UUID, role: str, tenant_id: uuid.UUID | None) -> str:
    """Simulates "expire access token manually" from the acceptance criteria: a
    same-secret, same-algorithm token whose `exp` is already in the past.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now - timedelta(minutes=31),
        "exp": now - timedelta(minutes=1),
        "user_id": "expired-test-user",
        "role": role,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "location_ids": [],
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_login_by_user_id_for_product_owner_and_tenant_admin(client: AsyncClient):
    async with async_session_maker() as session:
        await _set_platform_admin(session)
        tenant = await _seed_tenant(session)
        owner_login = f"owner-{uuid.uuid4().hex[:8]}"
        admin_login = f"{tenant.tenant_code}-admin01"
        await _seed_user(session, tenant=None, login_id=owner_login, role_code="product_owner")
        await _seed_user(session, tenant=tenant, login_id=admin_login, role_code="tenant_admin")
        await session.commit()

    owner_resp = await client.post(
        "/api/v1/auth/login", json={"user_id": owner_login, "password": "password123"}
    )
    assert owner_resp.status_code == 200
    owner_body = owner_resp.json()
    assert owner_body["role"] == "product_owner"
    assert owner_body["tenant_id"] is None

    admin_resp = await client.post(
        "/api/v1/auth/login", json={"user_id": admin_login, "password": "password123"}
    )
    assert admin_resp.status_code == 200
    admin_body = admin_resp.json()
    assert admin_body["role"] == "tenant_admin"
    assert admin_body["tenant_id"] == str(tenant.id)


async def test_login_user_id_is_case_insensitive(client: AsyncClient):
    async with async_session_maker() as session:
        await _set_platform_admin(session)
        tenant = await _seed_tenant(session)
        login_id = f"{tenant.tenant_code}-Cashier01"
        await _seed_user(session, tenant=tenant, login_id=login_id, role_code="pos_user")
        await session.commit()

    for attempt in (login_id.upper(), login_id.lower(), login_id):
        resp = await client.post(
            "/api/v1/auth/login", json={"user_id": attempt, "password": "password123"}
        )
        assert resp.status_code == 200, attempt
        assert resp.json()["role"] == "pos_user"


async def test_login_rejects_wrong_password_and_unknown_user_id(client: AsyncClient):
    async with async_session_maker() as session:
        await _set_platform_admin(session)
        tenant = await _seed_tenant(session)
        login_id = f"{tenant.tenant_code}-cashier01"
        await _seed_user(session, tenant=tenant, login_id=login_id, role_code="pos_user")
        await session.commit()

    wrong_password = await client.post(
        "/api/v1/auth/login", json={"user_id": login_id, "password": "not-the-password"}
    )
    assert wrong_password.status_code == 401

    unknown_user = await client.post(
        "/api/v1/auth/login", json={"user_id": "no-such-user-id", "password": "whatever"}
    )
    assert unknown_user.status_code == 401


async def test_login_blocked_once_subscription_expired(client: AsyncClient):
    async with async_session_maker() as session:
        await _set_platform_admin(session)
        tenant = await _seed_tenant(session)  # current_period_end defaults to today
        login_id = f"{tenant.tenant_code}-cashier01"
        await _seed_user(session, tenant=tenant, login_id=login_id, role_code="pos_user")
        await session.commit()

    # Still valid the day the period ends — expiry is exclusive of "today".
    still_valid = await client.post(
        "/api/v1/auth/login", json={"user_id": login_id, "password": "password123"}
    )
    assert still_valid.status_code == 200

    async with async_session_maker() as session:
        await _set_platform_admin(session)
        subscription = (
            await session.execute(select(Subscription).where(Subscription.tenant_id == tenant.id))
        ).scalar_one()
        subscription.current_period_end = date.today() - timedelta(days=1)
        await session.commit()

    expired = await client.post(
        "/api/v1/auth/login", json={"user_id": login_id, "password": "password123"}
    )
    assert expired.status_code == 403

    # A product_owner login has no tenant to expire, so it's never affected.
    async with async_session_maker() as session:
        await _set_platform_admin(session)
        owner_login = f"owner-{uuid.uuid4().hex[:8]}"
        await _seed_user(session, tenant=None, login_id=owner_login, role_code="product_owner")
        await session.commit()

    owner_resp = await client.post(
        "/api/v1/auth/login", json={"user_id": owner_login, "password": "password123"}
    )
    assert owner_resp.status_code == 200


async def test_login_blocked_when_subscription_suspended(client: AsyncClient):
    async with async_session_maker() as session:
        await _set_platform_admin(session)
        tenant = await _seed_tenant(session)
        login_id = f"{tenant.tenant_code}-admin01"
        await _seed_user(session, tenant=tenant, login_id=login_id, role_code="tenant_admin")
        subscription = (
            await session.execute(select(Subscription).where(Subscription.tenant_id == tenant.id))
        ).scalar_one()
        subscription.status = "suspended"
        await session.commit()

    resp = await client.post(
        "/api/v1/auth/login", json={"user_id": login_id, "password": "password123"}
    )
    assert resp.status_code == 403


async def test_duplicate_user_id_same_tenant_rejected_cross_tenant_allowed():
    """Local handles only need to be unique *within* a tenant (CLAUDE.md §5) — the
    global uniqueness constraint is on the *composed* {tenant_code}-{local handle}
    login id, so two different tenants picking the same local handle never collide.
    """
    async with async_session_maker() as session:
        await _set_platform_admin(session)
        tenant_a = await _seed_tenant(session)
        tenant_b = await _seed_tenant(session)
        await session.commit()

    # Same tenant, same composed login id twice -> rejected.
    async with async_session_maker() as session:
        await _set_platform_admin(session)
        login_id = f"{tenant_a.tenant_code}-admin01"
        await _seed_user(session, tenant=tenant_a, login_id=login_id, role_code="tenant_admin")
        await session.commit()

    async with async_session_maker() as session:
        await _set_platform_admin(session)
        with pytest.raises(IntegrityError):
            await _seed_user(session, tenant=tenant_a, login_id=login_id, role_code="pos_user")
        await session.rollback()

    # Same local handle "admin01", different tenant -> allowed (different composed id).
    async with async_session_maker() as session:
        await _set_platform_admin(session)
        other_login_id = f"{tenant_b.tenant_code}-admin01"
        user = await _seed_user(session, tenant=tenant_b, login_id=other_login_id, role_code="tenant_admin")
        await session.commit()
        assert user.user_id == other_login_id


async def test_refresh_flow_issues_new_access_token_after_expiry(client: AsyncClient):
    async with async_session_maker() as session:
        await _set_platform_admin(session)
        tenant = await _seed_tenant(session)
        login_id = f"{tenant.tenant_code}-admin01"
        await _seed_user(session, tenant=tenant, login_id=login_id, role_code="tenant_admin")
        await session.commit()
        user_id, tenant_id = None, tenant.id

    login_resp = await client.post(
        "/api/v1/auth/login", json={"user_id": login_id, "password": "password123"}
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    user_id = uuid.UUID(jwt.get_unverified_claims(tokens["access_token"])["sub"])

    expired_access_token = _forge_expired_access_token(
        user_id=user_id, role="tenant_admin", tenant_id=tenant_id
    )
    stale_call = await client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {expired_access_token}"}
    )
    assert stale_call.status_code == 401

    refresh_resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()
    assert jwt.get_unverified_claims(new_tokens["access_token"])["type"] == "access"
    assert new_tokens["role"] == "tenant_admin"

    silent_retry = await client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {new_tokens['access_token']}"}
    )
    assert silent_retry.status_code == 204


async def test_refresh_rejects_garbage_token(client: AsyncClient):
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-jwt"})
    assert resp.status_code == 401


async def test_public_routes_do_not_require_auth(client: AsyncClient):
    health = await client.get("/api/v1/health")
    assert health.status_code == 200

    # A bad login is still a public (unauthenticated) request — 401 for bad
    # credentials, never a 403/redirect for "missing auth header".
    bad_login = await client.post(
        "/api/v1/auth/login", json={"user_id": "nope", "password": "nope"}
    )
    assert bad_login.status_code == 401


async def test_authenticated_route_rejects_missing_or_malformed_token(client: AsyncClient):
    no_header = await client.post("/api/v1/auth/logout")
    assert no_header.status_code in (401, 403)

    bad_token = await client.post(
        "/api/v1/auth/logout", headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert bad_token.status_code == 401


async def test_role_and_scope_dependencies_block_wrong_role(client: AsyncClient):
    """RBAC dependencies (Phase 02 `deps.py`) are the mechanism every future phase's
    routers attach to their routes. No real product_owner-only or tenant-only business
    route exists yet, so this exercises the dependencies directly on throwaway routes —
    the exact pattern Phase 03+ will use for real.
    """
    probe_app = FastAPI()

    @probe_app.get("/platform-only")
    async def _platform_only(_user=Depends(require_platform_scope)):
        return {"ok": True}

    @probe_app.get("/tenant-only")
    async def _tenant_only(_user=Depends(require_tenant_scope)):
        return {"ok": True}

    @probe_app.get("/admin-or-cashier")
    async def _admin_or_cashier(_user=Depends(require_role("tenant_admin", "pos_user"))):
        return {"ok": True}

    async with async_session_maker() as session:
        await _set_platform_admin(session)
        tenant = await _seed_tenant(session)
        owner_login = f"owner-{uuid.uuid4().hex[:8]}"
        admin_login = f"{tenant.tenant_code}-admin01"
        waiter_login = f"{tenant.tenant_code}-waiter01"
        await _seed_user(session, tenant=None, login_id=owner_login, role_code="product_owner")
        await _seed_user(session, tenant=tenant, login_id=admin_login, role_code="tenant_admin")
        await _seed_user(session, tenant=tenant, login_id=waiter_login, role_code="waiter")
        await session.commit()

    owner_tokens = (
        await client.post("/api/v1/auth/login", json={"user_id": owner_login, "password": "password123"})
    ).json()
    admin_tokens = (
        await client.post("/api/v1/auth/login", json={"user_id": admin_login, "password": "password123"})
    ).json()
    waiter_tokens = (
        await client.post("/api/v1/auth/login", json={"user_id": waiter_login, "password": "password123"})
    ).json()

    async with AsyncClient(transport=ASGITransport(app=probe_app), base_url="http://test") as probe_client:
        owner_headers = {"Authorization": f"Bearer {owner_tokens['access_token']}"}
        admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}
        waiter_headers = {"Authorization": f"Bearer {waiter_tokens['access_token']}"}

        # product_owner reaches /platform-only but is blocked from /tenant-only (no tenant_id).
        assert (await probe_client.get("/platform-only", headers=owner_headers)).status_code == 200
        assert (await probe_client.get("/tenant-only", headers=owner_headers)).status_code == 403

        # tenant_admin reaches /tenant-only but is blocked from /platform-only.
        assert (await probe_client.get("/tenant-only", headers=admin_headers)).status_code == 200
        assert (await probe_client.get("/platform-only", headers=admin_headers)).status_code == 403

        # tenant_admin is allowed by require_role("tenant_admin", "pos_user"); waiter is not.
        assert (await probe_client.get("/admin-or-cashier", headers=admin_headers)).status_code == 200
        assert (await probe_client.get("/admin-or-cashier", headers=waiter_headers)).status_code == 403
