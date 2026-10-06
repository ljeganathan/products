import json
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.online_payment_service import broadcast_paid_notice, handle_webhook

# Public by design (the gateway calls it, with no login) — authenticity comes from the
# signature each provider sends, checked against that tenant's own saved credentials, and
# the handler re-reads the payment from the gateway instead of trusting the body.
# The Razorpay path is the one hotels already have saved in their Razorpay dashboard, so it
# must not change.
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _handle(provider: str, tenant_id: uuid.UUID, request: Request, db: AsyncSession) -> dict[str, bool]:
    await db.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_id)}
    )
    raw_body = await request.body()
    payload = json.loads(raw_body or b"{}")
    notice = await handle_webhook(db, tenant_id, provider, raw_body, request.headers, payload)
    await db.commit()
    if notice is not None:
        await broadcast_paid_notice(notice)
    return {"ok": True}


@router.post("/razorpay/{tenant_id}")
async def razorpay_webhook(
    tenant_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    return await _handle("razorpay", tenant_id, request, db)


@router.post("/cashfree/{tenant_id}")
async def cashfree_webhook(
    tenant_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    return await _handle("cashfree", tenant_id, request, db)
