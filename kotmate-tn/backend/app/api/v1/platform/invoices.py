import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.platform import InvoiceCreateRequest, InvoiceResponse
from app.services.invoice_pdf import render_invoice_pdf
from app.services.invoicing import (
    create_invoice,
    get_invoice_with_tenant,
    list_invoices,
    list_overdue_invoices,
    mark_invoice_paid,
)

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


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Response:
    """Invoices have no email-delivery mechanism in this codebase — `status="sent"` set
    at creation (services/invoicing.create_invoice) is only ever a status label, never a
    dispatched email — so this PDF download is the actual way to hand an invoice to a
    tenant.
    """
    invoice, tenant = await get_invoice_with_tenant(db, invoice_id)
    pdf_bytes = render_invoice_pdf(invoice, tenant)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'},
    )


@router.patch("/{invoice_id}/mark-paid", response_model=InvoiceResponse)
async def mark_invoice_paid_endpoint(
    invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> InvoiceResponse:
    invoice = await mark_invoice_paid(db, invoice_id)
    await db.commit()
    return invoice
