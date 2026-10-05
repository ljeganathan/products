import json
import uuid

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.online_payment_service import broadcast_paid_notice, handle_webhook

# Public by design (the gateway calls it, with no login) — authenticity comes from the
# HMAC signature checked against that tenant's own webhook secret, and the handler
# re-reads the payment from the gateway instead of trusting the body.
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/razorpay/{tenant_id}")
async def razorpay_webhook(
    tenant_id: uuid.UUID,
    request: Request,
    x_razorpay_signature: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    await db.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_id)}
    )
    raw_body = await request.body()
    payload = json.loads(raw_body or b"{}")
    notice = await handle_webhook(db, tenant_id, raw_body, x_razorpay_signature, payload)
    await db.commit()
    if notice is not None:
        await broadcast_paid_notice(notice)
    return {"ok": True}
