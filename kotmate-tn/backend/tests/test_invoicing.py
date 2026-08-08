from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import async_session_maker
from app.models import Subscription
from tests.conftest import _onboard_tenant

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_list_and_mark_paid_invoice(client: AsyncClient, owner_headers: dict):
    tenant = await _onboard_tenant(client, owner_headers)

    create_resp = await client.post(
        "/api/v1/platform/invoices",
        json={
            "tenant_id": tenant["id"],
            "amount": 2499.0,
            "due_date": str(date.today() + timedelta(days=7)),
            "description": "Pro — test cycle",
        },
        headers=owner_headers,
    )
    assert create_resp.status_code == 201
    invoice = create_resp.json()
    assert invoice["status"] == "sent"
    assert invoice["invoice_number"].startswith("INV-")
    assert invoice["tenant_company_name"] == tenant["company_name"]

    list_resp = await client.get(
        "/api/v1/platform/invoices", params={"tenant_id": tenant["id"]}, headers=owner_headers
    )
    assert list_resp.status_code == 200
    assert any(i["id"] == invoice["id"] for i in list_resp.json())

    paid_resp = await client.patch(
        f"/api/v1/platform/invoices/{invoice['id']}/mark-paid", headers=owner_headers
    )
    assert paid_resp.status_code == 200
    paid_body = paid_resp.json()
    assert paid_body["status"] == "paid"
    assert paid_body["paid_date"] == str(date.today())


async def test_overdue_invoice_surfaces_without_persisted_status_flip(
    client: AsyncClient, owner_headers: dict
):
    tenant = await _onboard_tenant(client, owner_headers)

    create_resp = await client.post(
        "/api/v1/platform/invoices",
        json={
            "tenant_id": tenant["id"],
            "amount": 999.0,
            "due_date": str(date.today() - timedelta(days=3)),
        },
        headers=owner_headers,
    )
    assert create_resp.status_code == 201
    invoice = create_resp.json()
    # Stored status stays "sent" — overdue is computed from due_date on every read,
    # never persisted (see invoicing.get_dashboard_alerts docstring).
    assert invoice["status"] == "sent"

    overdue_resp = await client.get("/api/v1/platform/invoices/overdue", headers=owner_headers)
    assert overdue_resp.status_code == 200
    assert any(i["id"] == invoice["id"] for i in overdue_resp.json())

    alerts_resp = await client.get("/api/v1/platform/dashboard/alerts", headers=owner_headers)
    assert alerts_resp.status_code == 200
    overdue_ids = [row["invoice_id"] for row in alerts_resp.json()["overdue_invoices"]]
    assert invoice["id"] in overdue_ids


async def test_expiring_subscription_appears_in_dashboard_alerts(
    client: AsyncClient, owner_headers: dict
):
    tenant = await _onboard_tenant(client, owner_headers)

    async with async_session_maker() as session:
        from tests.conftest import _set_platform_admin

        await _set_platform_admin(session)
        subscription = (
            await session.execute(select(Subscription).where(Subscription.tenant_id == tenant["id"]))
        ).scalar_one()
        subscription.current_period_end = date.today() + timedelta(days=3)
        await session.commit()

    alerts_resp = await client.get("/api/v1/platform/dashboard/alerts", headers=owner_headers)
    assert alerts_resp.status_code == 200
    expiring = alerts_resp.json()["expiring_subscriptions"]
    assert any(row["tenant_id"] == tenant["id"] and row["days_remaining"] == 3 for row in expiring)
