from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.tests.conftest import auth_headers, login


async def test_get_my_subscription_shows_plan_and_usage(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get(
        "/api/v1/settings/subscription", headers=auth_headers(tokens["access_token"])
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan_code"] == "lite"
    assert body["usage"]["users_count"] == 1
    assert body["usage"]["users_limit"] == 2
    assert body["requested_plan_code"] is None


async def test_available_plans_lists_active_plans(
    client: AsyncClient, lite_tenant: dict, all_plans: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get(
        "/api/v1/settings/subscription/available-plans",
        headers=auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 200
    codes = {p["code"] for p in resp.json()}
    assert {"lite", "pro", "pro_max"}.issubset(codes)


async def test_pos_user_cannot_access_subscription(
    client: AsyncClient, lite_tenant: dict, db_session: AsyncSession
) -> None:
    cashier = User(
        tenant_id=lite_tenant["tenant"].id,
        store_id=lite_tenant["store"].id,
        name="Cashier",
        email="cashier-sub@tenanta.dev",
        password_hash=hash_password("Cashier@123"),
        role=UserRole.POS_USER,
    )
    db_session.add(cashier)
    await db_session.flush()

    tokens = await login(client, "cashier-sub@tenanta.dev", "Cashier@123")
    resp = await client.get(
        "/api/v1/settings/subscription", headers=auth_headers(tokens["access_token"])
    )
    assert resp.status_code == 403
