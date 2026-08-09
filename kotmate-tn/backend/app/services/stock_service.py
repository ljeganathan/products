import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item, StockLedger, Tenant


def has_stock_management_feature(plan_features: dict | None) -> bool:
    """Plan-tier gate alone (Pro/Pro Max) — used for the KOT screen's Stock Management
    tab endpoints and the Settings toggle-write endpoint, independent of whether the
    tenant has actually turned their switch on yet.
    """
    return bool((plan_features or {}).get("stock_management"))


def is_stock_tracking_enabled(tenant: Tenant, plan_features: dict | None) -> bool:
    """Effective on/off state for stock badges (POS/KOT) and the KOT-send deduction —
    the single flag those consumers should check.

    `items.track_inventory`/`available_qty` predate this feature and were never
    plan-gated (CLAUDE.md §11) — a Lite tenant could always opt an item in and see it
    decrement/badge exactly as today. So a plan *without* `stock_management` (Lite)
    always reads as enabled here — "zero behavior change for Lite" per this feature's
    acceptance criteria. Only once a tenant is on a plan that *has* `stock_management`
    (Pro/Pro Max) does the new admin-controlled kill switch (`tenant.stock_management_
    enabled`, defaults off) start gating anything — soft-disable only, this never
    touches `items.track_inventory`/`available_qty` itself, so re-enabling instantly
    restores whatever was already configured.
    """
    if not has_stock_management_feature(plan_features):
        return True
    return bool(tenant.stock_management_enabled)


async def set_item_stock(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    item: Item,
    new_qty: int,
    reason: str,
    *,
    location_id: uuid.UUID | None = None,
    reference_order_id: uuid.UUID | None = None,
    reference_bill_id: uuid.UUID | None = None,
) -> Item:
    """The one place that mutates `available_qty` and writes the matching audit row —
    reused by a manual set (Stock Management tab / Item Master edit), a restock, the
    KOT-send deduction, and the bill-finalize deduction for items billed without ever
    being sent to KOT, so every stock change is traceable. Giving an item a quantity
    here also turns tracking on for it (CLAUDE.md §11 extension, Phase 21+).
    """
    previous = item.available_qty or 0
    item.track_inventory = True
    item.available_qty = new_qty
    session.add(
        StockLedger(
            tenant_id=tenant_id,
            item_id=item.id,
            location_id=location_id,
            change_qty=new_qty - previous,
            reason=reason,
            reference_order_id=reference_order_id,
            reference_bill_id=reference_bill_id,
        )
    )
    await session.flush()
    return item


async def list_stock_items(session: AsyncSession, tenant_id: uuid.UUID) -> list[Item]:
    """Every active item, regardless of current track_inventory state — the Stock
    Management tab lets staff give any item a quantity, which is what turns tracking on
    for it (see `set_item_stock`).
    """
    rows = await session.execute(
        select(Item).where(Item.tenant_id == tenant_id, Item.is_active.is_(True)).order_by(Item.name_en)
    )
    return list(rows.scalars().all())
