import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Category, Item, ItemSectionPrice, Plan, SeatingSection, TaxRule, Tenant
from app.schemas.items import (
    ItemCreateRequest,
    ItemUpdateRequest,
    SectionPriceEntry,
    SectionPriceOption,
)
from app.services.storage import get_storage

_ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


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


async def search_items(session: AsyncSession, tenant_id: uuid.UUID, q: str, limit: int = 50) -> list[Item]:
    """Trigram-similarity search across name_en/name_ta (Phase 07, CLAUDE.md §9) — the
    `ix_items_name_en_trgm`/`ix_items_name_ta_trgm` GIN indexes keep this fast even on a
    large catalog, and `%` (pg_trgm's similarity operator) tolerates typos/partial
    matches that a plain ILIKE can't.
    """
    rows = await session.execute(
        select(Item)
        .where(
            Item.tenant_id == tenant_id,
            Item.is_active.is_(True),
            text("(name_en % :q OR name_ta % :q)"),
        )
        .params(q=q)
        .order_by(
            text("GREATEST(similarity(name_en, :q), similarity(COALESCE(name_ta, ''), :q)) DESC")
        )
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
    """
    rows = await session.execute(
        select(Item)
        .where(Item.tenant_id == tenant_id, Item.is_active.is_(True), Item.is_top_seller.is_(True))
        .order_by(Item.name_en)
    )
    return list(rows.scalars().all())


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
