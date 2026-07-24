import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.rbac import require_role
from app.models.enums import InvoiceStatus, SubscriptionStatus, UserRole
from app.models.subscription import SubscriptionInvoice
from app.models.tenant import Tenant
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.common import PaginatedResponse
from app.schemas.platform_invoice import InvoiceGenerateRequest, InvoiceOut, InvoiceStatusUpdate
from app.services.subscription_service import generate_next_invoice, mark_invoice_paid

router = APIRouter(prefix="/platform/invoices", tags=["platform"])

require_owner = require_role(UserRole.PRODUCT_OWNER)

# InvoiceStatus has no dedicated "overdue" value (see InvoiceStatusUpdate's
# docstring) — FAILED is the console's "mark overdue" action.
ALLOWED_MANUAL_STATUSES = {InvoiceStatus.PAID, InvoiceStatus.FAILED, InvoiceStatus.VOID}


def _to_out(invoice: SubscriptionInvoice, tenant: Tenant) -> InvoiceOut:
    return InvoiceOut(
        id=invoice.id,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        subscription_id=invoice.subscription_id,
        amount_paise=invoice.amount_paise,
        gst_paise=invoice.gst_paise,
        status=invoice.status,
        invoice_number=invoice.invoice_number,
        issued_at=invoice.issued_at,
        paid_at=invoice.paid_at,
    )


@router.get("", response_model=PaginatedResponse[InvoiceOut])
async def list_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: uuid.UUID | None = Query(None),
    status_filter: InvoiceStatus | None = Query(None, alias="status"),
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[InvoiceOut]:
    rows, total = await InvoiceRepository(db).list_all(
        page=page, page_size=page_size, tenant_id=tenant_id, status=status_filter
    )
    return PaginatedResponse(
        items=[_to_out(invoice, tenant) for invoice, tenant in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/generate", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
async def generate_invoice(
    payload: InvoiceGenerateRequest,
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    sub_repo = SubscriptionRepository(db)
    row = await sub_repo.get_by_id_joined(payload.subscription_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    subscription, tenant, plan, _ = row

    invoice = await generate_next_invoice(db, subscription, plan)
    await db.commit()
    return _to_out(invoice, tenant)


@router.patch("/{invoice_id}", response_model=InvoiceOut)
async def update_invoice_status(
    invoice_id: uuid.UUID,
    payload: InvoiceStatusUpdate,
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    if payload.status not in ALLOWED_MANUAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of {[s.value for s in ALLOWED_MANUAL_STATUSES]}",
        )

    invoice_repo = InvoiceRepository(db)
    row = await invoice_repo.get_by_id_joined(invoice_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    invoice, tenant = row

    if payload.status == InvoiceStatus.PAID:
        sub_repo = SubscriptionRepository(db)
        sub_row = await sub_repo.get_by_id_joined(invoice.subscription_id)
        if sub_row is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invoice has no subscription",
            )
        mark_invoice_paid(invoice, sub_row[0])
    elif payload.status == InvoiceStatus.FAILED:
        sub_repo = SubscriptionRepository(db)
        sub_row = await sub_repo.get_by_id_joined(invoice.subscription_id)
        if sub_row is not None:
            sub_row[0].status = SubscriptionStatus.PAST_DUE
        invoice.status = InvoiceStatus.FAILED
    else:
        invoice.status = payload.status

    await db.flush()
    await db.commit()
    return _to_out(invoice, tenant)
