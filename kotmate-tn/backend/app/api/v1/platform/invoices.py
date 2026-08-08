import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.platform import InvoiceCreateRequest, InvoiceResponse
from app.services.invoicing import create_invoice, list_invoices, list_overdue_invoices, mark_invoice_paid

router = APIRouter(prefix="/invoices", tags=["platform-invoices"])


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice_endpoint(
    payload: InvoiceCreateRequest, db: AsyncSession = Depends(get_db)
) -> InvoiceResponse:
    invoice = await create_invoice(db, payload)
    await db.commit()
    return invoice


@router.get("", response_model=list[InvoiceResponse])
async def list_invoices_endpoint(
    tenant_id: uuid.UUID | None = Query(default=None),
    invoice_status: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> list[InvoiceResponse]:
    return await list_invoices(db, tenant_id, invoice_status)


@router.get("/overdue", response_model=list[InvoiceResponse])
async def list_overdue_invoices_endpoint(db: AsyncSession = Depends(get_db)) -> list[InvoiceResponse]:
    return await list_overdue_invoices(db)


@router.patch("/{invoice_id}/mark-paid", response_model=InvoiceResponse)
async def mark_invoice_paid_endpoint(
    invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> InvoiceResponse:
    invoice = await mark_invoice_paid(db, invoice_id)
    await db.commit()
    return invoice
