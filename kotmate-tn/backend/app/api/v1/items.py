import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.models import Tenant
from app.schemas.items import (
    ItemCreateRequest,
    ItemImportResult,
    ItemResponse,
    ItemUpdateRequest,
    RestockRequest,
    SectionPriceOption,
    SectionPriceUpdateRequest,
)
from app.services.item_service import (
    create_item,
    export_items_csv,
    get_item_by_code,
    get_item_or_404,
    get_section_prices,
    import_items_csv,
    list_items,
    list_top_sellers,
    restock_item,
    search_items,
    set_section_prices,
    update_item,
    upload_item_image,
)
from app.services.tenant_onboarding import get_active_plan

# Read access is broad (Phase 07/08 need it for the POS/KOT screens); writes are
# tenant_admin-only, enforced per-route below.
router = APIRouter(prefix="/items", tags=["items"], dependencies=[Depends(require_tenant_scope)])


async def _get_tenant(db: AsyncSession, current_user: CurrentUser) -> Tenant:
    return (await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))).scalar_one()


@router.get("", response_model=list[ItemResponse])
async def list_tenant_items(
    category_id: uuid.UUID | None = None,
    search: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ItemResponse]:
    items = await list_items(db, current_user.tenant_id, category_id, search)
    return [ItemResponse.model_validate(i) for i in items]


@router.get("/search", response_model=list[ItemResponse])
async def search_tenant_items(
    q: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ItemResponse]:
    items = await search_items(db, current_user.tenant_id, q)
    return [ItemResponse.model_validate(i) for i in items]


@router.get("/top-sellers", response_model=list[ItemResponse])
async def list_tenant_top_sellers(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ItemResponse]:
    items = await list_top_sellers(db, current_user.tenant_id)
    return [ItemResponse.model_validate(i) for i in items]


@router.get("/by-code/{item_code}", response_model=ItemResponse)
async def get_tenant_item_by_code(
    item_code: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ItemResponse:
    item = await get_item_by_code(db, current_user.tenant_id, item_code)
    return ItemResponse.model_validate(item)


@router.get("/export.csv", dependencies=[Depends(require_role("tenant_admin"))])
async def export_tenant_items_csv(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    tenant = await _get_tenant(db, current_user)
    plan = await get_active_plan(db, tenant.id)
    csv_text = await export_items_csv(db, tenant.id, plan)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=items.csv"},
    )


@router.post(
    "/import.csv", response_model=ItemImportResult, dependencies=[Depends(require_role("tenant_admin"))]
)
async def import_tenant_items_csv(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ItemImportResult:
    tenant = await _get_tenant(db, current_user)
    plan = await get_active_plan(db, tenant.id)
    content = (await file.read()).decode("utf-8-sig")
    try:
        result = await import_items_csv(db, tenant.id, plan, content)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Import failed: a duplicate item code was encountered"
        ) from exc
    await db.commit()
    return result


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_item(
    payload: ItemCreateRequest,
    current_user: CurrentUser = Depends(require_role("tenant_admin")),
    db: AsyncSession = Depends(get_db),
) -> ItemResponse:
    try:
        item = await create_item(db, current_user.tenant_id, payload)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "That item code is already in use") from exc
    return ItemResponse.model_validate(item)


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_tenant_item(
    item_id: uuid.UUID,
    payload: ItemUpdateRequest,
    current_user: CurrentUser = Depends(require_role("tenant_admin")),
    db: AsyncSession = Depends(get_db),
) -> ItemResponse:
    item = await get_item_or_404(db, current_user.tenant_id, item_id)
    try:
        item = await update_item(db, current_user.tenant_id, item, payload)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "That item code is already in use") from exc
    return ItemResponse.model_validate(item)


@router.patch("/{item_id}/restock", response_model=ItemResponse)
async def restock_tenant_item(
    item_id: uuid.UUID,
    payload: RestockRequest,
    current_user: CurrentUser = Depends(require_role("tenant_admin")),
    db: AsyncSession = Depends(get_db),
) -> ItemResponse:
    item = await get_item_or_404(db, current_user.tenant_id, item_id)
    item = await restock_item(db, current_user.tenant_id, item, payload.available_qty)
    await db.commit()
    return ItemResponse.model_validate(item)


@router.post("/{item_id}/image", response_model=ItemResponse)
async def upload_tenant_item_image(
    item_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_role("tenant_admin")),
    db: AsyncSession = Depends(get_db),
) -> ItemResponse:
    tenant = await _get_tenant(db, current_user)
    item = await get_item_or_404(db, tenant.id, item_id)
    plan = await get_active_plan(db, tenant.id)
    item = await upload_item_image(db, tenant, plan, item, file)
    await db.commit()
    return ItemResponse.model_validate(item)


@router.get(
    "/{item_id}/section-prices",
    response_model=list[SectionPriceOption],
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def get_tenant_item_section_prices(
    item_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SectionPriceOption]:
    item = await get_item_or_404(db, current_user.tenant_id, item_id)
    return await get_section_prices(db, current_user.tenant_id, item)


@router.put(
    "/{item_id}/section-prices",
    response_model=list[SectionPriceOption],
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def set_tenant_item_section_prices(
    item_id: uuid.UUID,
    payload: SectionPriceUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SectionPriceOption]:
    tenant = await _get_tenant(db, current_user)
    item = await get_item_or_404(db, tenant.id, item_id)
    plan = await get_active_plan(db, tenant.id)
    result = await set_section_prices(db, tenant.id, plan, item, payload.prices)
    await db.commit()
    return result
