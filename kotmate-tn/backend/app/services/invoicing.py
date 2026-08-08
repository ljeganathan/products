import uuid
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Invoice, Plan, Subscription, Tenant
from app.schemas.platform import (
    DashboardAlertsResponse,
    ExpiringSubscriptionAlert,
    InvoiceCreateRequest,
    InvoiceResponse,
    OverdueInvoiceAlert,
)

# Subscriptions within this many days of `current_period_end` (or already past it) show
# up as a dashboard alert (PO-7) — chosen to give the platform owner a heads-up before
# a renewal lapses, not just after.
_EXPIRY_WARNING_DAYS = 7


def _to_response(invoice: Invoice, company_name: str) -> InvoiceResponse:
    return InvoiceResponse(
        id=invoice.id,
        tenant_id=invoice.tenant_id,
        tenant_company_name=company_name,
        subscription_id=invoice.subscription_id,
        invoice_number=invoice.invoice_number,
        amount=float(invoice.amount),
        status=invoice.status,
        issued_date=invoice.issued_date,
        due_date=invoice.due_date,
        paid_date=invoice.paid_date,
        description=invoice.description,
    )


async def _generate_invoice_number(session: AsyncSession) -> str:
    """`INV-{YYYYMM}-{seq}`, sequence resets each calendar month, collision-safe the
    same way `generate_tenant_code` (Phase 03) handles `tenant_code` collisions.
    """
    prefix = f"INV-{date.today():%Y%m}-"
    seq = 1
    while True:
        candidate = f"{prefix}{seq:04d}"
        existing = (
            await session.execute(select(Invoice.id).where(Invoice.invoice_number == candidate))
        ).scalar_one_or_none()
        if existing is None:
            return candidate
        seq += 1


async def create_invoice(session: AsyncSession, req: InvoiceCreateRequest) -> InvoiceResponse:
    tenant = (await session.execute(select(Tenant).where(Tenant.id == req.tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")

    invoice = Invoice(
        tenant_id=req.tenant_id,
        subscription_id=req.subscription_id,
        invoice_number=await _generate_invoice_number(session),
        amount=req.amount,
        status="sent",
        issued_date=date.today(),
        due_date=req.due_date,
        description=req.description,
    )
    session.add(invoice)
    await session.flush()
    return _to_response(invoice, tenant.company_name)


async def list_invoices(
    session: AsyncSession, tenant_id: uuid.UUID | None, invoice_status: str | None
) -> list[InvoiceResponse]:
    query = select(Invoice, Tenant.company_name).join(Tenant, Tenant.id == Invoice.tenant_id)
    if tenant_id is not None:
        query = query.where(Invoice.tenant_id == tenant_id)
    if invoice_status is not None:
        query = query.where(Invoice.status == invoice_status)
    rows = (await session.execute(query.order_by(Invoice.issued_date.desc()))).all()
    return [_to_response(invoice, company_name) for invoice, company_name in rows]


async def list_overdue_invoices(session: AsyncSession) -> list[InvoiceResponse]:
    today = date.today()
    rows = (
        await session.execute(
            select(Invoice, Tenant.company_name)
            .join(Tenant, Tenant.id == Invoice.tenant_id)
            .where(Invoice.status != "paid", Invoice.due_date < today)
            .order_by(Invoice.due_date)
        )
    ).all()
    return [_to_response(invoice, company_name) for invoice, company_name in rows]


async def mark_invoice_paid(session: AsyncSession, invoice_id: uuid.UUID) -> InvoiceResponse:
    invoice = (await session.execute(select(Invoice).where(Invoice.id == invoice_id))).scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")

    invoice.status = "paid"
    invoice.paid_date = date.today()
    await session.flush()

    tenant = (await session.execute(select(Tenant).where(Tenant.id == invoice.tenant_id))).scalar_one()
    return _to_response(invoice, tenant.company_name)


async def get_dashboard_alerts(session: AsyncSession) -> DashboardAlertsResponse:
    """`overdue` is never persisted on `Invoice.status` — computed here from `due_date`
    on every read, same "no cron, compute on read" choice noted in the Invoice model's
    docstring, so there's no scheduled job that can silently stop running.
    """
    today = date.today()
    warning_cutoff = today + timedelta(days=_EXPIRY_WARNING_DAYS)

    expiring_rows = (
        await session.execute(
            select(Subscription, Tenant.company_name, Plan.code)
            .join(Tenant, Tenant.id == Subscription.tenant_id)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.status == "active", Subscription.current_period_end <= warning_cutoff)
            .order_by(Subscription.current_period_end)
        )
    ).all()
    expiring_subscriptions = [
        ExpiringSubscriptionAlert(
            tenant_id=sub.tenant_id,
            company_name=company_name,
            plan_code=plan_code,
            current_period_end=sub.current_period_end,
            days_remaining=(sub.current_period_end - today).days,
        )
        for sub, company_name, plan_code in expiring_rows
    ]

    overdue = await list_overdue_invoices(session)
    overdue_invoices = [
        OverdueInvoiceAlert(
            invoice_id=inv.id,
            tenant_id=inv.tenant_id,
            company_name=inv.tenant_company_name,
            invoice_number=inv.invoice_number,
            amount=inv.amount,
            due_date=inv.due_date,
            days_overdue=(today - inv.due_date).days,
        )
        for inv in overdue
    ]

    return DashboardAlertsResponse(
        expiring_subscriptions=expiring_subscriptions, overdue_invoices=overdue_invoices
    )
