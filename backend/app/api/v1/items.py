import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.enums import UserRole
from app.models.item import Item
from app.models.stock import Stock
from app.repositories.category_repository import CategoryRepository
from app.repositories.item_repository import ItemRepository
from app.repositories.stock_repository import StockRepository
from app.repositories.tax_profile_repository import TaxProfileRepository
from app.schemas.common import PaginatedResponse
from app.schemas.item import BulkImportResult, ItemCreate, ItemOut, ItemUpdate
from app.services.audit_service import record_audit_log
from app.services.item_service import bulk_import_items
from app.utils.store_scope import resolve_store_id

router = APIRouter(prefix="/items", tags=["items"])

require_admin = require_role(UserRole.ADMIN)
require_staff = require_role(UserRole.ADMIN, UserRole.POS_USER)


@router.get("", response_model=PaginatedResponse[ItemOut])
async def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    store_id: uuid.UUID | None = Query(None),
    barcode: str | None = Query(None),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ItemOut]:
    assert current_user.tenant_id is not None
    repo = ItemRepository(db)

    if barcode:
        # Single indexed (tenant_id, barcode) lookup — the scan-to-search path.
        item = await repo.get_by_barcode(current_user.tenant_id, barcode)
        items = [item] if item else []
        return PaginatedResponse(
            items=[ItemOut.model_validate(i) for i in items],
            total=len(items),
            page=1,
            page_size=page_size,
        )

    effective_store_id = store_id or current_user.store_id
    items, total = await repo.list_for_tenant(
        current_user.tenant_id,
        page=page,
        page_size=page_size,
        search=search,
        category_id=category_id,
        store_id=effective_store_id,
    )
    return PaginatedResponse(
        items=[ItemOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ItemOut:
    assert current_user.tenant_id is not None
    store_id = resolve_store_id(current_user, payload.store_id)

    item_repo = ItemRepository(db)
    category_repo = CategoryRepository(db)
    tax_repo = TaxProfileRepository(db)
    stock_repo = StockRepository(db)

    category = await category_repo.get_by_id_for_tenant(payload.category_id, current_user.tenant_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="category_id does not exist"
        )
    if await tax_repo.get_by_id_for_tenant(payload.tax_profile_id, current_user.tenant_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="tax_profile_id does not exist"
        )
    if payload.barcode and await item_repo.get_by_barcode(current_user.tenant_id, payload.barcode):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An item with this barcode already exists for this tenant",
        )

    item = Item(
        tenant_id=current_user.tenant_id,
        store_id=store_id,
        category_id=payload.category_id,
        name_en=payload.name_en,
        name_ta=payload.name_ta,
        sku=payload.sku,
        barcode=payload.barcode,
        unit=payload.unit,
        mrp_paise=payload.mrp_paise,
        selling_price_paise=payload.selling_price_paise,
        cost_price_paise=payload.cost_price_paise,
        tax_profile_id=payload.tax_profile_id,
        reorder_level=payload.reorder_level,
        reorder_qty=payload.reorder_qty,
        brand=payload.brand,
        pack_size=payload.pack_size,
        hsn_code=payload.hsn_code,
        batch_tracked=payload.batch_tracked,
    )
    await item_repo.create(item)

    if payload.opening_stock > 0:
        await stock_repo.create(
            Stock(
                tenant_id=current_user.tenant_id,
                store_id=store_id,
                item_id=item.id,
                quantity_on_hand=payload.opening_stock,
            )
        )

    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="item.create",
        entity="item",
        entity_id=item.id,
    )
    await db.commit()
    return ItemOut.model_validate(item)


@router.post("/bulk-import", response_model=BulkImportResult)
async def bulk_import(
    file: UploadFile,
    store_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BulkImportResult:
    assert current_user.tenant_id is not None
    target_store_id = resolve_store_id(current_user, store_id)

    raw = await file.read()
    try:
        csv_text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file must be UTF-8 encoded"
        ) from exc

    result = await bulk_import_items(
        db, tenant_id=current_user.tenant_id, store_id=target_store_id, csv_text=csv_text
    )
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="item.bulk_import",
        entity="item",
        metadata={"created_count": result.created_count, "error_count": result.error_count},
    )
    await db.commit()
    return result


@router.get("/{item_id}", response_model=ItemOut)
async def get_item(
    item_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> ItemOut:
    assert current_user.tenant_id is not None
    repo = ItemRepository(db)
    item = await repo.get_by_id_for_tenant(item_id, current_user.tenant_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return ItemOut.model_validate(item)


@router.patch("/{item_id}", response_model=ItemOut)
async def update_item(
    item_id: uuid.UUID,
    payload: ItemUpdate,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ItemOut:
    assert current_user.tenant_id is not None
    item_repo = ItemRepository(db)
    item = await item_repo.get_by_id_for_tenant(item_id, current_user.tenant_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "category_id" in update_data:
        category_repo = CategoryRepository(db)
        category = await category_repo.get_by_id_for_tenant(
            update_data["category_id"], current_user.tenant_id
        )
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="category_id does not exist"
            )

    if "tax_profile_id" in update_data:
        tax_repo = TaxProfileRepository(db)
        tax_profile = await tax_repo.get_by_id_for_tenant(
            update_data["tax_profile_id"], current_user.tenant_id
        )
        if tax_profile is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="tax_profile_id does not exist"
            )

    if "barcode" in update_data and update_data["barcode"]:
        existing = await item_repo.get_by_barcode(current_user.tenant_id, update_data["barcode"])
        if existing is not None and existing.id != item_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An item with this barcode already exists for this tenant",
            )

    for field, value in update_data.items():
        setattr(item, field, value)

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="item.update",
        entity="item",
        entity_id=item.id,
    )
    await db.commit()
    return ItemOut.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_item(
    item_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    assert current_user.tenant_id is not None
    repo = ItemRepository(db)
    item = await repo.get_by_id_for_tenant(item_id, current_user.tenant_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    item.is_active = False
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="item.deactivate",
        entity="item",
        entity_id=item.id,
    )
    await db.commit()
    return None
