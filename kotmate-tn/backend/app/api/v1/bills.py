import uuid
from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.schemas.bills import (
    BillCreateRequest,
    BillPreviewRequest,
    BillPreviewResponse,
    BillResponse,
    BillSearchParams,
)
from app.services.bill_service import (
    build_bill_response,
    finalize_bill,
    get_bill_or_404,
    preview_bill,
    reprint_bill,
    search_bills,
)

# Finalizing/reading bills is tenant_admin/pos_user only — a `waiter` token is rejected
# with 403 even if called directly (CLAUDE.md §5/§9: a waiter can never finalize/print a
# bill or take payment), enforced once here for the whole router rather than per-route.
router = APIRouter(
    prefix="/bills",
    tags=["bills"],
    dependencies=[
        Depends(require_tenant_scope),
        Depends(require_role("tenant_admin", "pos_user")),
    ],
)


@router.post("/preview", response_model=BillPreviewResponse)
async def preview_tenant_bill(
    payload: BillPreviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillPreviewResponse:
    return await preview_bill(db, current_user.tenant_id, payload)


@router.post("", response_model=BillResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_bill(
    payload: BillCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillResponse:
    result = await finalize_bill(db, current_user.tenant_id, current_user, payload)
    await db.commit()
    return result


@router.get("", response_model=list[BillResponse])
async def list_tenant_bills(
    bill_number: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    table_id: uuid.UUID | None = None,
    waiter_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    section_id: uuid.UUID | None = None,
    pos_user_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BillResponse]:
    params = BillSearchParams(
        bill_number=bill_number,
        date_from=date_from,
        date_to=date_to,
        table_id=table_id,
        waiter_id=waiter_id,
        location_id=location_id,
        section_id=section_id,
        pos_user_id=pos_user_id,
    )
    bills = await search_bills(db, current_user.tenant_id, params)
    return [await build_bill_response(db, bill) for bill in bills]


@router.get("/{bill_id}", response_model=BillResponse)
async def get_tenant_bill(
    bill_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillResponse:
    bill = await get_bill_or_404(db, current_user.tenant_id, bill_id)
    return await build_bill_response(db, bill)


@router.post("/{bill_id}/reprint", response_model=BillResponse)
async def reprint_tenant_bill(
    bill_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillResponse:
    bill = await get_bill_or_404(db, current_user.tenant_id, bill_id)
    printed = await reprint_bill(db, current_user.tenant_id, bill)
    # Build the response before committing — `require_tenant_scope`'s RLS var is
    # SET LOCAL (transaction-scoped, see deps.py), so it's gone once this transaction
    # ends (Phase 08's kot.py hit the identical bug in set_ticket_status).
    response = await build_bill_response(db, bill, printed=printed)
    await db.commit()
    return response
