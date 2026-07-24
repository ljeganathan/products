import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import InvoiceStatus


class InvoiceOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    subscription_id: uuid.UUID
    amount_paise: int
    gst_paise: int
    status: InvoiceStatus
    invoice_number: str
    issued_at: datetime
    paid_at: datetime | None


class InvoiceGenerateRequest(BaseModel):
    subscription_id: uuid.UUID


class InvoiceStatusUpdate(BaseModel):
    """`status` is restricted to paid/failed/void by the router — there is no
    dedicated "overdue" enum value; an unpaid invoice past its period is
    represented by leaving it `pending` while `subscriptions.status` becomes
    `past_due` (see subscription_service). Product-owner UI copy for the
    `failed` transition reads "mark overdue" for that reason."""

    status: InvoiceStatus
