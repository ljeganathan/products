import csv
import io
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ItemUnit
from app.models.item import Item
from app.models.stock import Stock
from app.repositories.category_repository import CategoryRepository
from app.repositories.item_repository import ItemRepository
from app.repositories.stock_repository import StockRepository
from app.repositories.tax_profile_repository import TaxProfileRepository
from app.schemas.item import BulkImportResult, BulkImportRowError

REQUIRED_TEMPLATE_COLUMNS = [
    "name_en",
    "name_ta",
    "category",
    "brand",
    "pack_size",
    "barcode",
    "sku",
    "unit",
    "mrp",
    "selling_price",
    "cost_price",
    "tax_profile",
    "hsn_code",
    "reorder_level",
    "reorder_qty",
    "opening_stock",
]


def _parse_float(value: str | None, field: str, errors: list[str], default: float = 0.0) -> float:
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        errors.append(f"{field} '{value}' is not a valid number")
        return default


async def bulk_import_items(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID,
    csv_text: str,
) -> BulkImportResult:
    """Validates and imports a CSV of items row by row. Bad rows are skipped
    and reported individually rather than failing the whole import."""
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file is empty")

    missing_columns = [c for c in REQUIRED_TEMPLATE_COLUMNS if c not in reader.fieldnames]
    if missing_columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV is missing required columns: {', '.join(missing_columns)}",
        )

    category_repo = CategoryRepository(db)
    tax_repo = TaxProfileRepository(db)
    item_repo = ItemRepository(db)
    stock_repo = StockRepository(db)

    all_categories = await category_repo.list_all_for_tenant(tenant_id)
    categories_by_name = {c.name_en.lower(): c for c in all_categories}
    tax_profiles_by_name = {t.name.lower(): t for t in await tax_repo.list_for_tenant(tenant_id)}

    seen_barcodes: dict[str, int] = {}
    row_errors: list[BulkImportRowError] = []
    created_count = 0
    total_rows = 0

    for row_number, row in enumerate(reader, start=2):
        total_rows += 1
        errors: list[str] = []

        name_en = (row.get("name_en") or "").strip()
        name_ta = (row.get("name_ta") or "").strip()
        category_name = (row.get("category") or "").strip()
        unit_value = (row.get("unit") or "").strip().lower()
        tax_profile_name = (row.get("tax_profile") or "").strip()
        barcode = (row.get("barcode") or "").strip() or None
        sku = (row.get("sku") or "").strip() or None
        brand = (row.get("brand") or "").strip() or None
        pack_size = (row.get("pack_size") or "").strip() or None
        hsn_code = (row.get("hsn_code") or "").strip() or None

        if not name_en:
            errors.append("name_en is required")
        if not name_ta:
            errors.append("name_ta is required")

        category = categories_by_name.get(category_name.lower()) if category_name else None
        if not category_name:
            errors.append("category is required")
        elif category is None:
            errors.append(f"category '{category_name}' does not exist for this tenant")

        tax_profile = (
            tax_profiles_by_name.get(tax_profile_name.lower()) if tax_profile_name else None
        )
        if not tax_profile_name:
            errors.append("tax_profile is required")
        elif tax_profile is None:
            errors.append(f"tax_profile '{tax_profile_name}' does not exist for this tenant")

        unit: ItemUnit | None
        try:
            unit = ItemUnit(unit_value)
        except ValueError:
            valid = ", ".join(u.value for u in ItemUnit)
            errors.append(f"unit '{unit_value}' is invalid (must be one of: {valid})")
            unit = None

        mrp_rupees = _parse_float(row.get("mrp"), "mrp", errors)
        selling_rupees = _parse_float(row.get("selling_price"), "selling_price", errors)
        cost_rupees = _parse_float(row.get("cost_price"), "cost_price", errors)
        reorder_level = _parse_float(row.get("reorder_level"), "reorder_level", errors)
        reorder_qty = _parse_float(row.get("reorder_qty"), "reorder_qty", errors)
        opening_stock = _parse_float(row.get("opening_stock"), "opening_stock", errors)

        if barcode:
            if barcode in seen_barcodes:
                errors.append(
                    f"barcode '{barcode}' is duplicated in this file "
                    f"(also row {seen_barcodes[barcode]})"
                )
            elif await item_repo.get_by_barcode(tenant_id, barcode) is not None:
                errors.append(f"barcode '{barcode}' already exists for this tenant")
            seen_barcodes.setdefault(barcode, row_number)

        if errors:
            row_errors.append(BulkImportRowError(row_number=row_number, errors=errors))
            continue

        assert category is not None
        assert tax_profile is not None
        assert unit is not None

        item = Item(
            tenant_id=tenant_id,
            store_id=store_id,
            category_id=category.id,
            name_en=name_en,
            name_ta=name_ta,
            sku=sku,
            barcode=barcode,
            unit=unit,
            mrp_paise=round(mrp_rupees * 100),
            selling_price_paise=round(selling_rupees * 100),
            cost_price_paise=round(cost_rupees * 100),
            tax_profile_id=tax_profile.id,
            reorder_level=reorder_level,
            reorder_qty=reorder_qty,
            brand=brand,
            pack_size=pack_size,
            hsn_code=hsn_code,
        )
        await item_repo.create(item)

        if opening_stock > 0:
            await stock_repo.create(
                Stock(
                    tenant_id=tenant_id,
                    store_id=store_id,
                    item_id=item.id,
                    quantity_on_hand=opening_stock,
                )
            )

        created_count += 1

    return BulkImportResult(
        total_rows=total_rows,
        created_count=created_count,
        error_count=len(row_errors),
        errors=row_errors,
    )


async def export_items_csv(
    db: AsyncSession, *, tenant_id: uuid.UUID, store_id: uuid.UUID | None
) -> str:
    """Exports current items in the exact column format bulk-import expects,
    so an export can be edited and re-imported as-is (round-trip)."""
    item_repo = ItemRepository(db)
    stock_repo = StockRepository(db)
    category_repo = CategoryRepository(db)
    tax_repo = TaxProfileRepository(db)

    items = await item_repo.list_all_for_tenant(tenant_id, store_id)
    categories_by_id = {c.id: c for c in await category_repo.list_all_for_tenant(tenant_id)}
    tax_profiles_by_id = {t.id: t for t in await tax_repo.list_for_tenant(tenant_id)}
    stock_by_item_id = await stock_repo.map_by_item_id(tenant_id, store_id, [i.id for i in items])

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(REQUIRED_TEMPLATE_COLUMNS)
    for item in items:
        category = categories_by_id.get(item.category_id)
        tax_profile = tax_profiles_by_id.get(item.tax_profile_id)
        stock = stock_by_item_id.get(item.id)
        writer.writerow(
            [
                item.name_en,
                item.name_ta,
                category.name_en if category else "",
                item.brand or "",
                item.pack_size or "",
                item.barcode or "",
                item.sku or "",
                item.unit.value,
                f"{item.mrp_paise / 100:.2f}",
                f"{item.selling_price_paise / 100:.2f}",
                f"{item.cost_price_paise / 100:.2f}",
                tax_profile.name if tax_profile else "",
                item.hsn_code or "",
                item.reorder_level,
                item.reorder_qty,
                stock.quantity_on_hand if stock else 0,
            ]
        )

    return buffer.getvalue()
