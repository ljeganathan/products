from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType
from app.models.notification import Notification
from app.tests.conftest import auth_headers, create_pos_user, login


async def test_list_and_mark_notification_read(
    client: AsyncClient, lite_tenant: dict, db_session: AsyncSession
) -> None:
    tenant = lite_tenant["tenant"]
    store = lite_tenant["store"]

    notification = Notification(
        tenant_id=tenant.id,
        store_id=store.id,
        type=NotificationType.LOW_STOCK,
        title="Low stock: Test Item",
        body="Test Item is down to 2 (reorder level 5).",
    )
    db_session.add(notification)
    await db_session.flush()

    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    list_resp = await client.get("/api/v1/notifications", headers=headers)
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == 1
    assert body["items"][0]["is_read"] is False

    unread_resp = await client.get(
        "/api/v1/notifications", params={"is_read": False}, headers=headers
    )
    assert unread_resp.json()["total"] == 1

    mark_read_resp = await client.patch(
        f"/api/v1/notifications/{notification.id}/read", headers=headers
    )
    assert mark_read_resp.status_code == 200
    assert mark_read_resp.json()["is_read"] is True

    unread_after = await client.get(
        "/api/v1/notifications", params={"is_read": False}, headers=headers
    )
    assert unread_after.json()["total"] == 0


async def test_pos_user_cannot_access_notifications(
    client: AsyncClient, lite_tenant: dict, db_session: AsyncSession
) -> None:
    tenant = lite_tenant["tenant"]
    store = lite_tenant["store"]
    await create_pos_user(
        db_session,
        tenant_id=tenant.id,
        store_id=store.id,
        email="cashier@tenanta.dev",
        password="Cashier@123",
    )
    tokens = await login(client, "cashier@tenanta.dev", "Cashier@123")
    resp = await client.get(
        "/api/v1/notifications", headers=auth_headers(tokens["access_token"])
    )
    assert resp.status_code == 403
