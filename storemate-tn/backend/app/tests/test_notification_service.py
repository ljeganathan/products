import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.category import Category
from app.models.enums import NotificationType
from app.models.item import Item
from app.models.notification import Notification
from app.models.stock import Stock
from app.models.tax_profile import TaxProfile
from app.services.notification_service import (
    LOW_STOCK_COOLDOWN_HOURS,
    check_and_notify_low_stock,
    run_low_stock_scan,
)


@pytest.fixture(autouse=True)
def _use_test_connection_for_background_sessions(
    scoped_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both functions under test open their own `AsyncSessionLocal()` rather
    than taking a session via `Depends(get_db)` (see notification_service.py
    docstrings) — redirect that onto this test's own connection so they see
    fixture data that was never actually committed to the database."""
    monkeypatch.setattr(
        "app.services.notification_service.AsyncSessionLocal", scoped_session_factory
    )


async def _make_low_stock_item(
    db_session: AsyncSession, *, tenant_id: uuid.UUID, store_id: uuid.UUID, quantity: float = 3
) -> tuple[Item, Stock]:
    category = Category(tenant_id=tenant_id, name_en="Snacks", name_ta="தின்பண்டங்கள்")
    db_session.add(category)
    tax_profile = TaxProfile(
        tenant_id=tenant_id, name="GST 12%", cgst_pct=6, sgst_pct=6, igst_pct=12
    )
    db_session.add(tax_profile)
    await db_session.flush()

    item = Item(
        tenant_id=tenant_id,
        store_id=store_id,
        category_id=category.id,
        name_en="Parle-G Biscuits",
        name_ta="பார்லே-ஜி பிஸ்கட்",
        unit="pack",
        mrp_paise=3000,
        selling_price_paise=2800,
        cost_price_paise=2400,
        tax_profile_id=tax_profile.id,
        reorder_level=5,
    )
    db_session.add(item)
    await db_session.flush()

    stock = Stock(
        tenant_id=tenant_id, store_id=store_id, item_id=item.id, quantity_on_hand=quantity
    )
    db_session.add(stock)
    await db_session.flush()
    return item, stock


async def _count_notifications(db_session: AsyncSession, item_id: uuid.UUID) -> int:
    result = await db_session.execute(
        select(Notification).where(Notification.reference_id == item_id)
    )
    return len(result.scalars().all())


async def test_low_stock_notification_deduped_within_cooldown(
    db_session: AsyncSession, pro_tenant: dict
) -> None:
    tenant = pro_tenant["tenant"]
    store = pro_tenant["store"]
    item, _ = await _make_low_stock_item(db_session, tenant_id=tenant.id, store_id=store.id)
    await db_session.commit()

    await check_and_notify_low_stock(tenant.id, store.id, item.id)
    assert await _count_notifications(db_session, item.id) == 1

    # A second sale of the same already-low item shouldn't spam a duplicate.
    await check_and_notify_low_stock(tenant.id, store.id, item.id)
    assert await _count_notifications(db_session, item.id) == 1


async def test_low_stock_notification_fires_again_after_cooldown_expires(
    db_session: AsyncSession, pro_tenant: dict
) -> None:
    tenant = pro_tenant["tenant"]
    store = pro_tenant["store"]
    item, _ = await _make_low_stock_item(db_session, tenant_id=tenant.id, store_id=store.id)

    stale_notification = Notification(
        tenant_id=tenant.id,
        store_id=store.id,
        type=NotificationType.LOW_STOCK,
        title="Low stock: Parle-G Biscuits",
        body="stale",
        reference_id=item.id,
        created_at=datetime.now(UTC) - timedelta(hours=LOW_STOCK_COOLDOWN_HOURS + 1),
    )
    db_session.add(stale_notification)
    await db_session.commit()

    await check_and_notify_low_stock(tenant.id, store.id, item.id)
    assert await _count_notifications(db_session, item.id) == 2


async def test_low_stock_notification_skipped_when_feature_disabled(
    db_session: AsyncSession, lite_tenant: dict
) -> None:
    tenant = lite_tenant["tenant"]
    store = lite_tenant["store"]
    item, _ = await _make_low_stock_item(db_session, tenant_id=tenant.id, store_id=store.id)
    await db_session.commit()

    await check_and_notify_low_stock(tenant.id, store.id, item.id)
    assert await _count_notifications(db_session, item.id) == 0


async def test_run_low_stock_scan_only_notifies_eligible_tenants_and_dedupes(
    db_session: AsyncSession, pro_tenant: dict, lite_tenant: dict
) -> None:
    pro = pro_tenant["tenant"]
    pro_store = pro_tenant["store"]
    lite = lite_tenant["tenant"]
    lite_store = lite_tenant["store"]

    pro_item, _ = await _make_low_stock_item(db_session, tenant_id=pro.id, store_id=pro_store.id)
    lite_item, _ = await _make_low_stock_item(db_session, tenant_id=lite.id, store_id=lite_store.id)
    await db_session.commit()

    created = await run_low_stock_scan()
    assert created == 1
    assert await _count_notifications(db_session, pro_item.id) == 1
    assert await _count_notifications(db_session, lite_item.id) == 0

    # Running the scan again immediately must not duplicate.
    created_again = await run_low_stock_scan()
    assert created_again == 0
    assert await _count_notifications(db_session, pro_item.id) == 1
