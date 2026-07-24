import uuid
from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.plan_limits import get_saved_bill_days
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.bill import Bill, BillItem
from app.models.enums import BillStatus, UserRole
from app.repositories.bill_repository import BillRepository
from app.schemas.bill import (
    BillCreate,
    BillItemOut,
    BillOut,
    BillPrintPayload,
    BillSearchResponse,
    ResumeBillResponse,
)
from app.services.audit_service import record_audit_log
from app.services.billing_service import (
    build_print_payload,
    cancel_bill,
    create_bill,
    resume_held_bill,
)
from app.services.notification_service import check_and_notify_low_stock
from app.utils.store_scope import resolve_store_id

router = APIRouter(prefix="/bills", tags=["bills"])

require_staff = require_role(UserRole.ADMIN, UserRole.POS_USER)


def _to_bill_out(bill: Bill, items: list[BillItem] | None = None) -> BillOut:
    out = BillOut.model_validate(bill)
    out.items = [BillItemOut.model_validate(i) for i in (items or [])]
    return out


async def _get_own_scoped_bill(
    repo: BillRepository, bill_id: uuid.UUID, current_user: CurrentUser
) -> Bill:
    assert current_user.tenant_id is not None
    bill = await repo.get_by_id_for_tenant(bill_id, current_user.tenant_id)
    if bill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    # pos_user is restricted to their own shift's bills (CLAUDE.md §5) — a
    # bill belonging to another cashier is reported as 404, not 403, so its
    # existence isn't leaked (same pattern as cross-tenant isolation).
    if current_user.role == UserRole.POS_USER and bill.cashier_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    return bill


@router.post("", response_model=BillOut, status_code=status.HTTP_201_CREATED)
async def create_bill_endpoint(
    payload: BillCreate,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> BillOut:
    assert current_user.tenant_id is not None
    store_id = resolve_store_id(current_user, payload.store_id)

    bill, items = await create_bill(
        db,
        tenant_id=current_user.tenant_id,
        store_id=store_id,
        cashier_id=current_user.user_id,
        payload=payload,
    )
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="bill.hold" if payload.hold else "bill.create",
        entity="bill",
        entity_id=bill.id,
    )
    await db.commit()

    if not payload.hold:
        for line in payload.items:
            background_tasks.add_task(
                check_and_notify_low_stock, current_user.tenant_id, store_id, line.item_id
            )

    return _to_bill_out(bill, items)


@router.get("", response_model=BillSearchResponse)
async def search_bills(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    store_id: uuid.UUID | None = Query(None),
    bill_number: int | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    cashier_id: uuid.UUID | None = Query(None),
    customer_phone: str | None = Query(None),
    bill_status: BillStatus | None = Query(None, alias="status"),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> BillSearchResponse:
    assert current_user.tenant_id is not None

    # pos_user always sees only their own shift's bills (CLAUDE.md §5); no
    # "see all" override exists yet, so the query param is ignored for them.
    effective_cashier_id = (
        current_user.user_id if current_user.role == UserRole.POS_USER else cashier_id
    )

    saved_bill_days = await get_saved_bill_days(db, current_user.tenant_id)
    window_start: date | None = None
    requested_from_clamped = False
    effective_date_from = date_from
    if saved_bill_days != -1:
        window_start = date.today() - timedelta(days=saved_bill_days)
        if date_from is not None and date_from < window_start:
            requested_from_clamped = True
            effective_date_from = window_start
        elif date_from is None:
            effective_date_from = window_start

    repo = BillRepository(db)
    bills, total = await repo.search(
        current_user.tenant_id,
        store_id,
        page=page,
        page_size=page_size,
        bill_number=bill_number,
        date_from=effective_date_from,
        date_to=date_to,
        cashier_id=effective_cashier_id,
        customer_phone=customer_phone,
        status=bill_status,
    )
    return BillSearchResponse(
        items=[_to_bill_out(b) for b in bills],
        total=total,
        page=page,
        page_size=page_size,
        saved_bill_days=saved_bill_days,
        window_start=window_start,
        requested_from_clamped=requested_from_clamped,
    )


@router.get("/{bill_id}", response_model=BillOut)
async def get_bill(
    bill_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> BillOut:
    repo = BillRepository(db)
    bill = await _get_own_scoped_bill(repo, bill_id, current_user)
    items = await repo.get_items(bill_id)
    return _to_bill_out(bill, items)


@router.post("/{bill_id}/resume", response_model=ResumeBillResponse)
async def resume_bill(
    bill_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> ResumeBillResponse:
    assert current_user.tenant_id is not None
    repo = BillRepository(db)
    bill = await _get_own_scoped_bill(repo, bill_id, current_user)
    if bill.status != BillStatus.HELD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only a held bill can be resumed"
        )

    result = await resume_held_bill(db, bill=bill)
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="bill.resume",
        entity="bill",
        entity_id=bill_id,
    )
    await db.commit()
    return result


@router.post("/{bill_id}/print", response_model=BillPrintPayload)
async def print_bill(
    bill_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> BillPrintPayload:
    assert current_user.tenant_id is not None
    repo = BillRepository(db)
    bill = await _get_own_scoped_bill(repo, bill_id, current_user)
    items = await repo.get_items(bill_id)

    payload = await build_print_payload(db, bill=bill, items=items)
    bill.printed_count += 1
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="bill.print",
        entity="bill",
        entity_id=bill_id,
    )
    await db.commit()
    return payload


@router.post("/{bill_id}/cancel", response_model=BillOut)
async def cancel_bill_endpoint(
    bill_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> BillOut:
    assert current_user.tenant_id is not None
    repo = BillRepository(db)
    bill = await _get_own_scoped_bill(repo, bill_id, current_user)

    await cancel_bill(db, bill=bill, cashier_id=current_user.user_id)
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="bill.cancel",
        entity="bill",
        entity_id=bill_id,
    )
    await db.commit()

    items = await repo.get_items(bill_id)
    return _to_bill_out(bill, items)
