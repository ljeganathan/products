import csv
import io
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Bill, BillItem, Category, Item, ItemSectionPrice, Plan, SeatingSection, TaxRule, Tenant
from app.schemas.items import (
    ItemCreateRequest,
    ItemImportResult,
    ItemUpdateRequest,
    SectionPriceEntry,
    SectionPriceOption,
)
from app.services.storage import get_storage

_ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_TOP_SELLER_LIMIT = 8
_TOP_SELLER_LOOKBACK_DAYS = 7

# Low-stock threshold — CLAUDE.md §11: banner/badge (KOT/POS) and the Dashboard's Low
# Stock widget (Phase 20) all agree a tracked item is "low" once 5 or fewer remain.
LOW_STOCK_THRESHOLD = 5

# Deliberately excludes image_url (CLAUDE.md §6 "Item import/export" — images are
# handled by their own per-item upload flow, not the spreadsheet round-trip).
_CSV_COLUMNS = [
    "item_code",
    "name_en",
    "name_ta",
    "category",
    "price",
    "tax_class",
    "is_top_seller",
    "is_combo_tile",
]


def _upgrade_required(feature: str) -> HTTPException:
    return HTTPException(
        status.HTTP_403_FORBIDDEN,
        f"This feature ('{feature}') isn't available on your current plan. Upgrade to Pro to use it.",
    )


async def _validate_category(session: AsyncSession, tenant_id: uuid.UUID, category_id: uuid.UUID) -> None:
    exists = (
        await session.execute(
            select(Category.id).where(Category.id == category_id, Category.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "category_id does not belong to this tenant")


async def _validate_tax_class(
    session: AsyncSession, tenant_id: uuid.UUID, tax_class_id: uuid.UUID | None
) -> None:
    if tax_class_id is None:
        return
    exists = (
        await session.execute(
            select(TaxRule.id).where(TaxRule.id == tax_class_id, TaxRule.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "tax_class_id does not belong to this tenant")


async def list_items(
    session: AsyncSession, tenant_id: uuid.UUID, category_id: uuid.UUID | None, search: str | None
) -> list[Item]:
    query = select(Item).where(Item.tenant_id == tenant_id)
    if category_id is not None:
        query = query.where(Item.category_id == category_id)
    if search:
        like = f"%{search}%"
        query = query.where(
            or_(Item.name_en.ilike(like), Item.name_ta.ilike(like), Item.item_code.ilike(like))
        )
    rows = await session.execute(query.order_by(Item.name_en))
    return list(rows.scalars().all())


async def list_low_stock_items(session: AsyncSession, tenant_id: uuid.UUID) -> list[Item]:
    """Powers the Dashboard's Low Stock widget (Phase 20, Dash-33a) — the same
    `track_inventory`/`available_qty <= LOW_STOCK_THRESHOLD` signal already driving the
    KOT/POS low-stock badges (CLAUDE.md §11), just queried tenant-wide instead of
    per-item. Items that don't opt into tracking never appear here, same as elsewhere.
    """
    rows = await session.execute(
        select(Item)
        .where(
            Item.tenant_id == tenant_id,
            Item.is_active.is_(True),
            Item.track_inventory.is_(True),
            Item.available_qty.is_not(None),
            Item.available_qty <= LOW_STOCK_THRESHOLD,
        )
        .order_by(Item.available_qty.asc(), Item.name_en)
    )
    return list(rows.scalars().all())


async def search_items(session: AsyncSession, tenant_id: uuid.UUID, q: str, limit: int = 50) -> list[Item]:
    """Substring + trigram-similarity search across name_en/name_ta (Phase 07/18,
    CLAUDE.md §9). Substring `ILIKE` alone would miss typos; trigram similarity (`%`)
    alone misses realistic short prefixes — e.g. "cof" vs "Filter Coffee" scores 0.2
    similarity, under pg_trgm's default 0.3 threshold, so a cashier typing the first few
    letters of an item got zero results (POS-37). ORing both keeps the typo-tolerance
    trigram search was added for while still matching plain short prefixes. The
    `ix_items_name_en_trgm`/`ix_items_name_ta_trgm` GIN indexes accelerate both forms.
    """
    like = f"%{q}%"
    # Bind `q` directly on each text() fragment via .bindparams() rather than relying on
    # an outer .params(q=q) on the Select — two separate text() clauses both named `:q`
    # left the outer binding ambiguous under SQLAlchemy's statement-plan caching,
    # intermittently raising "A value is required for bind parameter 'q'" at execution.
    trgm_match = text("(name_en % :q OR name_ta % :q)").bindparams(q=q)
    trgm_rank = text(
        "GREATEST(similarity(name_en, :q), similarity(COALESCE(name_ta, ''), :q)) DESC"
    ).bindparams(q=q)
    rows = await session.execute(
        select(Item)
        .where(
            Item.tenant_id == tenant_id,
            Item.is_active.is_(True),
            or_(
                Item.name_en.ilike(like),
                Item.name_ta.ilike(like),
                trgm_match,
            ),
        )
        .order_by(trgm_rank)
        .limit(limit)
    )
    return list(rows.scalars().all())


async def get_item_by_code(session: AsyncSession, tenant_id: uuid.UUID, item_code: str) -> Item:
    """Exact-match lookup for the POS numeric item-code quick-entry field (CLAUDE.md §9)."""
    item = (
        await session.execute(
            select(Item).where(
                Item.tenant_id == tenant_id, Item.item_code == item_code, Item.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No item found with that code")
    return item


async def list_top_sellers(session: AsyncSession, tenant_id: uuid.UUID) -> list[Item]:
    """Powers the POS screen's "Top Selling" category tab (CLAUDE.md §9), always the
    first tab regardless of what other categories the tenant has configured.

    Manually-pinned items (`is_top_seller=True`, set in Item Master) always show first —
    an owner can still guarantee a Meals/Thali combo leads the tab regardless of recent
    sales. When fewer than `_TOP_SELLER_LIMIT` items are pinned, the rest are filled in
    from actual sales over the last `_TOP_SELLER_LOOKBACK_DAYS` days (Phase 18, POS-31) —
    previously this tab was 100% manual and never reflected what was actually selling.
    """
    pinned = (
        await session.execute(
            select(Item)
            .where(Item.tenant_id == tenant_id, Item.is_active.is_(True), Item.is_top_seller.is_(True))
            .order_by(Item.name_en)
        )
    ).scalars().all()
    if len(pinned) >= _TOP_SELLER_LIMIT:
        return list(pinned)

    pinned_ids = {i.id for i in pinned}
    cutoff = datetime.now(UTC) - timedelta(days=_TOP_SELLER_LOOKBACK_DAYS)
    ranked = await session.execute(
        select(BillItem.item_id, func.sum(BillItem.quantity).label("qty"))
        .join(Bill, Bill.id == BillItem.bill_id)
        .where(Bill.tenant_id == tenant_id, Bill.status == "finalized", Bill.created_at >= cutoff)
        .group_by(BillItem.item_id)
        .order_by(func.sum(BillItem.quantity).desc())
        .limit(_TOP_SELLER_LIMIT + len(pinned))
    )
    computed_ids = [row.item_id for row in ranked if row.item_id not in pinned_ids]
    if not computed_ids:
        return list(pinned)

    computed_items = (
        await session.execute(
            select(Item).where(Item.id.in_(computed_ids), Item.is_active.is_(True))
        )
    ).scalars().all()
    rank = {item_id: i for i, item_id in enumerate(computed_ids)}
    computed_items = sorted(computed_items, key=lambda i: rank[i.id])
    return list(pinned) + computed_items[: _TOP_SELLER_LIMIT - len(pinned)]


async def get_item_or_404(session: AsyncSession, tenant_id: uuid.UUID, item_id: uuid.UUID) -> Item:
    item = (
        await session.execute(select(Item).where(Item.id == item_id, Item.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return item


async def create_item(session: AsyncSession, tenant_id: uuid.UUID, req: ItemCreateRequest) -> Item:
    await _validate_category(session, tenant_id, req.category_id)
    await _validate_tax_class(session, tenant_id, req.tax_class_id)

    item = Item(
        tenant_id=tenant_id,
        name_en=req.name_en,
        name_ta=req.name_ta,
        category_id=req.category_id,
        price=req.price,
        tax_class_id=req.tax_class_id,
        item_code=req.item_code,
        is_top_seller=req.is_top_seller,
        is_combo_tile=req.is_combo_tile,
        track_inventory=req.track_inventory,
        available_qty=req.available_qty,
        is_active=True,
    )
    session.add(item)
    await session.flush()
    return item


async def update_item(
    session: AsyncSession, tenant_id: uuid.UUID, item: Item, req: ItemUpdateRequest
) -> Item:
    data = req.model_dump(exclude_unset=True)

    if "category_id" in data:
        await _validate_category(session, tenant_id, data["category_id"])
    if "tax_class_id" in data:
        await _validate_tax_class(session, tenant_id, data["tax_class_id"])

    new_track_inventory = data.get("track_inventory", item.track_inventory)
    if "available_qty" in data and data["available_qty"] is not None and not new_track_inventory:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "available_qty can only be set when track_inventory=true"
        )

    for field, value in data.items():
        setattr(item, field, value)

    # Toggling tracking off clears the count rather than leaving a stale number hidden
    # behind a disabled flag (CLAUDE.md §11, Phase 05 acceptance criteria).
    if "track_inventory" in data and not data["track_inventory"]:
        item.available_qty = None

    await session.flush()
    return item


async def restock_item(item: Item, new_qty: int) -> Item:
    if not item.track_inventory:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Cannot restock an item that does not have track_inventory enabled"
        )
    item.available_qty = new_qty
    return item


async def upload_item_image(
    session: AsyncSession, tenant: Tenant, plan: Plan | None, item: Item, file: UploadFile
) -> Item:
    if not plan or not plan.features.get("item_images"):
        raise _upgrade_required("item_images")

    if file.content_type not in _ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only JPEG, PNG, or WebP images are allowed")

    content = await file.read()
    if len(content) > get_settings().MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image exceeds the maximum upload size")

    storage = get_storage()
    url = await storage.save(
        tenant_id=tenant.id, subfolder="items", filename=file.filename or "upload", content=content
    )
    item.image_url = url
    await session.flush()
    return item


async def get_section_prices(
    session: AsyncSession, tenant_id: uuid.UUID, item: Item
) -> list[SectionPriceOption]:
    sections = (
        await session.execute(
            select(SeatingSection)
            .where(SeatingSection.tenant_id == tenant_id, SeatingSection.is_active.is_(True))
            .order_by(SeatingSection.display_order)
        )
    ).scalars().all()
    overrides = {
        row.section_id: row.price
        for row in (
            await session.execute(
                select(ItemSectionPrice).where(ItemSectionPrice.item_id == item.id)
            )
        ).scalars()
    }
    return [
        SectionPriceOption(
            section_id=section.id,
            section_name_en=section.name_en,
            override_price=overrides.get(section.id),
            resolved_price=overrides.get(section.id, item.price),
        )
        for section in sections
    ]


async def set_section_prices(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    plan: Plan | None,
    item: Item,
    entries: list[SectionPriceEntry],
) -> list[SectionPriceOption]:
    if not plan or not plan.features.get("section_pricing"):
        raise _upgrade_required("section_pricing")

    section_ids = [entry.section_id for entry in entries]
    if section_ids:
        valid = (
            await session.execute(
                select(SeatingSection.id).where(
                    SeatingSection.tenant_id == tenant_id, SeatingSection.id.in_(section_ids)
                )
            )
        ).scalars().all()
        if set(valid) != set(section_ids):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "One or more sections do not belong to this tenant"
            )

    existing = {
        row.section_id: row
        for row in (
            await session.execute(select(ItemSectionPrice).where(ItemSectionPrice.item_id == item.id))
        ).scalars()
    }

    for entry in entries:
        row = existing.get(entry.section_id)
        if entry.price is None:
            if row is not None:
                await session.delete(row)
        elif row is not None:
            row.price = entry.price
        else:
            session.add(
                ItemSectionPrice(
                    tenant_id=tenant_id, item_id=item.id, section_id=entry.section_id, price=entry.price
                )
            )

    await session.flush()
    return await get_section_prices(session, tenant_id, item)


async def export_items_csv(session: AsyncSession, tenant_id: uuid.UUID, plan: Plan | None) -> str:
    if not plan or not plan.features.get("item_export"):
        raise _upgrade_required("item_export")

    rows = (
        await session.execute(
            select(Item, Category.name_en, TaxRule.name)
            .join(Category, Category.id == Item.category_id)
            .outerjoin(TaxRule, TaxRule.id == Item.tax_class_id)
            .where(Item.tenant_id == tenant_id)
            .order_by(Item.name_en)
        )
    ).all()

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNS)
    writer.writeheader()
    for item, category_name, tax_class_name in rows:
        writer.writerow(
            {
                "item_code": item.item_code or "",
                "name_en": item.name_en,
                "name_ta": item.name_ta or "",
                "category": category_name,
                "price": item.price,
                "tax_class": tax_class_name or "",
                "is_top_seller": item.is_top_seller,
                "is_combo_tile": item.is_combo_tile,
            }
        )
    return buffer.getvalue()


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


async def import_items_csv(
    session: AsyncSession, tenant_id: uuid.UUID, plan: Plan | None, csv_text: str
) -> ItemImportResult:
    if not plan or not plan.features.get("item_import"):
        raise _upgrade_required("item_import")

    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
    except csv.Error as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Malformed CSV: {exc}") from exc

    categories = {
        c.name_en.strip().lower(): c.id
        for c in (
            await session.execute(select(Category).where(Category.tenant_id == tenant_id))
        ).scalars()
    }
    tax_classes = {
        t.name.strip().lower(): t.id
        for t in (await session.execute(select(TaxRule).where(TaxRule.tenant_id == tenant_id))).scalars()
    }
    existing_by_code = {
        i.item_code: i
        for i in (
            await session.execute(
                select(Item).where(Item.tenant_id == tenant_id, Item.item_code.is_not(None))
            )
        ).scalars()
        if i.item_code
    }

    created = 0
    updated = 0
    errors: list[str] = []

    for row_num, row in enumerate(rows, start=2):  # header is row 1
        name_en = (row.get("name_en") or "").strip()
        category_name = (row.get("category") or "").strip()
        price_raw = (row.get("price") or "").strip()
        item_code = (row.get("item_code") or "").strip() or None

        if not name_en:
            errors.append(f"row {row_num}: name_en is required")
            continue
        category_id = categories.get(category_name.lower())
        if category_id is None:
            errors.append(f"row {row_num}: unknown category '{category_name}'")
            continue
        try:
            price = float(price_raw)
            if price <= 0:
                raise ValueError
        except ValueError:
            errors.append(f"row {row_num}: invalid price '{price_raw}'")
            continue

        tax_class_name = (row.get("tax_class") or "").strip()
        tax_class_id = None
        if tax_class_name:
            tax_class_id = tax_classes.get(tax_class_name.lower())
            if tax_class_id is None:
                errors.append(f"row {row_num}: unknown tax_class '{tax_class_name}'")
                continue

        name_ta = (row.get("name_ta") or "").strip() or None
        is_top_seller = _parse_bool(row.get("is_top_seller") or "")
        is_combo_tile = _parse_bool(row.get("is_combo_tile") or "")

        existing = existing_by_code.get(item_code) if item_code else None
        if existing is not None:
            existing.name_en = name_en
            existing.name_ta = name_ta
            existing.category_id = category_id
            existing.price = price
            existing.tax_class_id = tax_class_id
            existing.is_top_seller = is_top_seller
            existing.is_combo_tile = is_combo_tile
            updated += 1
        else:
            session.add(
                Item(
                    tenant_id=tenant_id,
                    name_en=name_en,
                    name_ta=name_ta,
                    category_id=category_id,
                    price=price,
                    tax_class_id=tax_class_id,
                    item_code=item_code,
                    is_top_seller=is_top_seller,
                    is_combo_tile=is_combo_tile,
                    is_active=True,
                )
            )
            created += 1

    await session.flush()
    return ItemImportResult(created=created, updated=updated, errors=errors)
