import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.middleware.plan_limits import feature_enabled
from app.models.enums import NotificationType, SubscriptionStatus
from app.models.item import Item
from app.models.notification import Notification
from app.models.plan import Plan
from app.models.stock import Stock
from app.models.subscription import Subscription
from app.repositories.notification_repository import NotificationRepository
from app.repositories.stock_repository import StockRepository

logger = logging.getLogger(__name__)

# A given item won't generate a second low-stock notification within this
# window even if it's sold again (per-sale check) or rescanned (scheduler) —
# without this, a slow-moving item sitting at/under its reorder level would
# spam one notification per sale, and the 15-minute scheduler scan
# (`run_low_stock_scan`) would spam one every 15 minutes.
LOW_STOCK_COOLDOWN_HOURS = 24


async def check_and_notify_low_stock(
    tenant_id: uuid.UUID, store_id: uuid.UUID, item_id: uuid.UUID
) -> None:
    """Runs as a FastAPI BackgroundTask after a sale — opens its own session
    since the request's session is already closed by the time background
    tasks execute. `run_low_stock_scan` (below) is the scheduled, tenant-wide
    counterpart that catches items nobody has sold recently.

    Deliberately swallows every exception: a background side-effect must
    never propagate into (and blow up) the ASGI response cycle it runs
    after — Starlette re-raises an uncaught background-task error and it
    surfaces as if the request itself failed, even though the response was
    already sent successfully."""
    try:
        async with AsyncSessionLocal() as db:
            if not await feature_enabled(db, tenant_id, "low_stock_alerts"):
                return

            stock_repo = StockRepository(db)
            stock = await stock_repo.get_by_item_store(tenant_id, store_id, item_id)
            if stock is None:
                return

            item = await db.get(Item, item_id)
            if item is None or float(stock.quantity_on_hand) > float(item.reorder_level):
                return

            if await _notify_if_not_recent(db, stock, item):
                await db.commit()
    except Exception:
        logger.exception("Low-stock notification check failed for item %s", item_id)


async def run_low_stock_scan() -> int:
    """APScheduler job (every 15 min, see core/scheduler.py): catches items
    that drift at/under their reorder level without a triggering sale (e.g.
    a manual stock adjustment, or a reorder level edited downward). Scans
    every tenant with the `low_stock_alerts` feature on their active plan.
    Returns the number of new notifications created (logged by the caller).
    """
    notified_count = 0
    async with AsyncSessionLocal() as db:
        subs_result = await db.execute(
            select(Subscription.tenant_id, Plan.features_json)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.status == SubscriptionStatus.ACTIVE)
        )
        eligible_tenant_ids = [
            tenant_id
            for tenant_id, features in subs_result.tuples().all()
            if features.get("low_stock_alerts", False)
        ]

        for tenant_id in eligible_tenant_ids:
            low_stock_result = await db.execute(
                select(Stock, Item)
                .join(Item, Item.id == Stock.item_id)
                .where(
                    Stock.tenant_id == tenant_id,
                    Item.is_active.is_(True),
                    Stock.quantity_on_hand <= Item.reorder_level,
                )
            )
            for stock, item in low_stock_result.tuples().all():
                if await _notify_if_not_recent(db, stock, item):
                    notified_count += 1

        await db.commit()
    return notified_count


async def _notify_if_not_recent(db: AsyncSession, stock: Stock, item: Item) -> bool:
    """Creates a low-stock notification unless one for this exact item was
    already created within `LOW_STOCK_COOLDOWN_HOURS`. Returns whether a new
    notification was created."""
    cooldown_start = datetime.now(UTC) - timedelta(hours=LOW_STOCK_COOLDOWN_HOURS)
    already_notified = await NotificationRepository(db).exists_recent(
        tenant_id=stock.tenant_id,
        store_id=stock.store_id,
        reference_id=item.id,
        notification_type=NotificationType.LOW_STOCK,
        since=cooldown_start,
    )
    if already_notified:
        return False

    _create_low_stock_notification(db, stock, item)
    return True


def _create_low_stock_notification(db: AsyncSession, stock: Stock, item: Item) -> None:
    db.add(
        Notification(
            tenant_id=stock.tenant_id,
            store_id=stock.store_id,
            type=NotificationType.LOW_STOCK,
            title=f"Low stock: {item.name_en}",
            body=(
                f"{item.name_en} is down to {stock.quantity_on_hand} "
                f"(reorder level {item.reorder_level})."
            ),
            reference_id=item.id,
        )
    )
