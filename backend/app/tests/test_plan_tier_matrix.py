"""Phase 7 task 3: walks the full plan-tier feature matrix from
docs/SUBSCRIPTION_TIERS.md across Lite/Pro/Pro Max and confirms the backend
`plan_limits` middleware agrees with it — user limits, low-stock alerts,
multi-store, discount rules, and the api_access flag. Store creation has no
CRUD endpoint yet (out of scope for this phase), so multi-store is verified
directly against `check_store_limit`."""

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.plan_limits import check_store_limit, feature_enabled
from app.models.store import Store
from app.tests.conftest import auth_headers, login


async def test_low_stock_access_matches_plan_tier(
    client: AsyncClient, lite_tenant: dict, pro_tenant: dict, pro_max_tenant: dict
) -> None:
    lite = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get("/api/v1/stock/low-stock", headers=auth_headers(lite["access_token"]))
    assert resp.status_code == 403

    pro = await login(client, "admin@tenantpro.dev", "Admin@123")
    resp = await client.get("/api/v1/stock/low-stock", headers=auth_headers(pro["access_token"]))
    assert resp.status_code == 200

    pro_max = await login(client, "admin@tenantpromax.dev", "Admin@123")
    resp = await client.get(
        "/api/v1/stock/low-stock", headers=auth_headers(pro_max["access_token"])
    )
    assert resp.status_code == 200


async def test_discount_rules_access_matches_plan_tier(
    client: AsyncClient, lite_tenant: dict, pro_tenant: dict, pro_max_tenant: dict
) -> None:
    bill_rule = {"scope": "bill", "type": "percent", "value": 500}

    lite = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.post(
        "/api/v1/discount-rules", json=bill_rule, headers=auth_headers(lite["access_token"])
    )
    assert resp.status_code == 403

    pro = await login(client, "admin@tenantpro.dev", "Admin@123")
    resp = await client.post(
        "/api/v1/discount-rules", json=bill_rule, headers=auth_headers(pro["access_token"])
    )
    assert resp.status_code == 201

    pro_max = await login(client, "admin@tenantpromax.dev", "Admin@123")
    resp = await client.post(
        "/api/v1/discount-rules", json=bill_rule, headers=auth_headers(pro_max["access_token"])
    )
    assert resp.status_code == 201


async def test_user_limit_matches_plan_tier(
    client: AsyncClient, lite_tenant: dict, pro_tenant: dict, pro_max_tenant: dict
) -> None:
    def _add_user(email_prefix: str) -> dict:
        return {
            "name": "New Cashier",
            "email": f"{email_prefix}@test.dev",
            "password": "Cashier@123",
            "role": "pos_user",
        }

    # Lite: max_users=2, tenant already has 1 admin — the 2nd fits, the 3rd doesn't.
    lite = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(lite["access_token"])
    first = await client.post("/api/v1/users", json=_add_user("lite1"), headers=headers)
    assert first.status_code == 201
    resp = await client.post("/api/v1/users", json=_add_user("lite2"), headers=headers)
    assert resp.status_code == 402

    # Pro: max_users=5, tenant already has 1 admin — 4 more fit, the 5th doesn't.
    pro = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(pro["access_token"])
    for i in range(4):
        resp = await client.post("/api/v1/users", json=_add_user(f"pro{i}"), headers=headers)
        assert resp.status_code == 201, resp.text
    resp = await client.post("/api/v1/users", json=_add_user("pro-over"), headers=headers)
    assert resp.status_code == 402

    # Pro Max: unlimited — adding well beyond any other tier's limit still succeeds.
    pro_max = await login(client, "admin@tenantpromax.dev", "Admin@123")
    headers = auth_headers(pro_max["access_token"])
    for i in range(6):
        resp = await client.post("/api/v1/users", json=_add_user(f"promax{i}"), headers=headers)
        assert resp.status_code == 201, resp.text


async def test_store_limit_matches_plan_tier(
    db_session: AsyncSession, lite_tenant: dict, pro_tenant: dict, pro_max_tenant: dict
) -> None:
    # Lite and Pro both default to max_stores=1, and the fixture's own store
    # already fills that slot — a check for one more store is rejected.
    with pytest.raises(HTTPException) as lite_exc:
        await check_store_limit(db_session, lite_tenant["tenant"].id)
    assert lite_exc.value.status_code == 402

    with pytest.raises(HTTPException) as pro_exc:
        await check_store_limit(db_session, pro_tenant["tenant"].id)
    assert pro_exc.value.status_code == 402

    # Pro Max is unlimited (-1) — passes even with more than one store already.
    await check_store_limit(db_session, pro_max_tenant["tenant"].id)
    db_session.add(Store(tenant_id=pro_max_tenant["tenant"].id, name="Second store"))
    await db_session.flush()
    await check_store_limit(db_session, pro_max_tenant["tenant"].id)


async def test_api_access_flag_matches_plan_tier(
    db_session: AsyncSession, lite_tenant: dict, pro_tenant: dict, pro_max_tenant: dict
) -> None:
    assert await feature_enabled(db_session, lite_tenant["tenant"].id, "api_access") is False
    assert await feature_enabled(db_session, pro_tenant["tenant"].id, "api_access") is False
    assert await feature_enabled(db_session, pro_max_tenant["tenant"].id, "api_access") is True
