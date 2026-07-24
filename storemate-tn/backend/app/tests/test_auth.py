from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import _create_token, decode_token, hash_password
from app.models.enums import PlanCode, UserRole
from app.models.user import User
from app.tests.conftest import auth_headers, create_tenant_with_admin, login


async def test_login_success_returns_tokens_and_user(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tenant = lite_tenant["tenant"]
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")

    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["user"]["email"] == "admin@tenanta.dev"
    assert tokens["user"]["role"] == "admin"
    assert tokens["user"]["tenant_id"] == str(tenant.id)


async def test_login_wrong_password_fails(client: AsyncClient, lite_tenant: dict) -> None:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "admin@tenanta.dev", "password": "wrong-pass"}
    )
    assert resp.status_code == 401


async def test_login_unknown_email_fails(client: AsyncClient, lite_tenant: dict) -> None:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@nowhere.dev", "password": "whatever123"}
    )
    assert resp.status_code == 401


async def test_product_owner_login_has_null_tenant_in_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
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

    tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    payload = decode_token(tokens["access_token"])

    assert payload["role"] == "product_owner"
    assert payload["tenant_id"] is None
    assert tokens["user"]["tenant_id"] is None


async def test_refresh_issues_new_working_access_token(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")

    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200
    new_access_token = resp.json()["access_token"]

    me_resp = await client.get("/api/v1/auth/me", headers=auth_headers(new_access_token))
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "admin@tenanta.dev"


async def test_refresh_with_garbage_token_fails(client: AsyncClient, lite_tenant: dict) -> None:
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 401


async def test_refresh_with_access_token_fails(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


async def test_protected_route_without_token_returns_401(
    client: AsyncClient, lite_tenant: dict
) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_protected_route_with_garbage_token_returns_401(
    client: AsyncClient, lite_tenant: dict
) -> None:
    resp = await client.get("/api/v1/auth/me", headers=auth_headers("garbage-token"))
    assert resp.status_code == 401


async def test_protected_route_with_expired_token_returns_401(
    client: AsyncClient, lite_tenant: dict
) -> None:
    admin = lite_tenant["admin"]
    expired_token = _create_token(
        subject=admin.id,
        token_type="access",
        expires_delta=timedelta(minutes=-1),
        extra_claims={"tenant_id": str(admin.tenant_id), "store_id": None, "role": "admin"},
    )
    resp = await client.get("/api/v1/auth/me", headers=auth_headers(expired_token))
    assert resp.status_code == 401


async def test_role_guard_rejects_pos_user_from_admin_route(
    client: AsyncClient, lite_tenant: dict, db_session: AsyncSession
) -> None:
    tenant = lite_tenant["tenant"]
    store = lite_tenant["store"]
    cashier = User(
        tenant_id=tenant.id,
        store_id=store.id,
        name="Cashier A",
        email="cashierA@tenanta.dev",
        password_hash=hash_password("Cashier@123"),
        role=UserRole.POS_USER,
    )
    db_session.add(cashier)
    await db_session.flush()

    tokens = await login(client, "cashierA@tenanta.dev", "Cashier@123")
    resp = await client.post(
        "/api/v1/users",
        json={
            "name": "Someone",
            "email": "someone@tenanta.dev",
            "password": "Someone@123",
            "role": "pos_user",
        },
        headers=auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 403


async def test_tenant_isolation_cross_tenant_fetch_fails(
    client: AsyncClient, lite_tenant: dict, db_session: AsyncSession
) -> None:
    tenant_b = await create_tenant_with_admin(
        db_session,
        plan_code=PlanCode.PRO,
        max_users=5,
        tenant_name="Tenant B",
        admin_email="admin@tenantb.dev",
        admin_password="Admin@123",
    )
    user_in_b = User(
        tenant_id=tenant_b["tenant"].id,
        store_id=tenant_b["store"].id,
        name="Cashier B",
        email="cashierB@tenantb.dev",
        password_hash=hash_password("Cashier@123"),
        role=UserRole.POS_USER,
    )
    db_session.add(user_in_b)
    await db_session.flush()

    tokens_a = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get(
        f"/api/v1/users/{user_in_b.id}", headers=auth_headers(tokens_a["access_token"])
    )
    assert resp.status_code == 404


async def test_user_limit_enforcement_blocks_beyond_plan_max(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    # Lite plan max_users=2; tenant already has 1 admin — this 2nd user fits.
    resp = await client.post(
        "/api/v1/users",
        json={
            "name": "Cashier A",
            "email": "cashierA@tenanta.dev",
            "password": "Cashier@123",
            "role": "pos_user",
        },
        headers=headers,
    )
    assert resp.status_code == 201

    # 3rd user exceeds the Lite plan's max_users=2.
    resp = await client.post(
        "/api/v1/users",
        json={
            "name": "Cashier B",
            "email": "cashierB@tenanta.dev",
            "password": "Cashier@123",
            "role": "pos_user",
        },
        headers=headers,
    )
    assert resp.status_code == 402
    assert "limit" in resp.json()["detail"].lower()


async def test_login_locks_out_after_max_failed_attempts(
    client: AsyncClient, lite_tenant: dict
) -> None:
    settings = get_settings()

    # One fewer than the lockout threshold — still plain 401s, not locked yet.
    for _ in range(settings.LOGIN_MAX_ATTEMPTS - 1):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@tenanta.dev", "password": "wrong-pass"},
        )
        assert resp.status_code == 401

    # The attempt that reaches the threshold locks the account.
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@tenanta.dev", "password": "wrong-pass"},
    )
    assert resp.status_code == 401

    # Even the CORRECT password is now rejected — the account is locked,
    # not just still failing on bad credentials.
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@tenanta.dev", "password": "Admin@123"},
    )
    assert resp.status_code == 429
    assert "too many" in resp.json()["detail"].lower()


async def test_successful_login_resets_failed_attempt_counter(
    client: AsyncClient, lite_tenant: dict
) -> None:
    settings = get_settings()

    # A couple of wrong attempts, below the lockout threshold.
    for _ in range(settings.LOGIN_MAX_ATTEMPTS - 2):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@tenanta.dev", "password": "wrong-pass"},
        )
        assert resp.status_code == 401

    # A correct login succeeds and resets the counter...
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    assert tokens["access_token"]

    # ...so it takes a fresh full run of failures to lock out again, not
    # just one more (which would happen if the counter hadn't reset).
    for _ in range(settings.LOGIN_MAX_ATTEMPTS - 1):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@tenanta.dev", "password": "wrong-pass"},
        )
        assert resp.status_code == 401
    still_ok = await login(client, "admin@tenanta.dev", "Admin@123")
    assert still_ok["access_token"]
