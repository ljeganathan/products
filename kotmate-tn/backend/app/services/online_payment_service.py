"""Online (Razorpay) payment for QR self-orders — Phase 28.

Trust model: the customer's browser is never believed about money. An attempt only becomes
'paid' after this backend fetched the order's payments from the gateway with the hotel's
own credentials (polling from the guest page) or received a correctly signed webhook.
Both paths end in `apply_gateway_payments`, so behaviour is identical either way and the
feature works locally without any public webhook URL.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import CurrentGuest
from app.core.secrets import encrypt_secret
from app.models import GuestSession, PaymentAttempt, Tenant, TenantPaymentGateway
from app.schemas.bills import BillPreviewRequest
from app.schemas.online_payments import (
    GuestCreatePaymentResponse,
    GuestOnlinePaymentInfo,
    GuestPaymentStatusResponse,
    OnlinePaymentSettingsRequest,
    OnlinePaymentSettingsResponse,
)
from app.services.bill_service import preview_bill
from app.services.branch_header import resolve_branch_header
from app.services.kot_service import KotSendResult, build_kot_ticket_broadcast, send_kot
from app.services.payment_gateway import PaymentGateway, build_gateway, get_gateway, get_gateway_row
from app.services.tenant_onboarding import get_active_plan
from app.ws.manager import manager as ws_manager

_RECENT_ATTEMPTS_TO_SYNC = 5


@dataclass
class PaidNotice:
    """What the API layer needs to tell staff screens once an attempt turns paid."""

    location_id: uuid.UUID
    table_id: uuid.UUID | None
    pickup_token: str | None
    # Set when a takeaway order's kitchen ticket was fired automatically on payment, so the
    # route can broadcast it to the KOT screens the same way a normal KOT send does.
    kot_result: KotSendResult | None = None


def to_paise(amount: float) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# --- Settings (tenant_admin) -------------------------------------------------------


async def _plan_allows(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
    plan = await get_active_plan(session, tenant_id)
    return bool(plan and plan.features.get("qr_self_order"))


def _webhook_url(tenant_id: uuid.UUID) -> str:
    base = get_settings().PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/api/v1/webhooks/razorpay/{tenant_id}"


async def get_settings_view(session: AsyncSession, tenant_id: uuid.UUID) -> OnlinePaymentSettingsResponse:
    row = await get_gateway_row(session, tenant_id)
    return OnlinePaymentSettingsResponse(
        available=await _plan_allows(session, tenant_id),
        enabled=bool(row and row.is_enabled),
        provider=row.provider if row else "razorpay",
        auth_mode=row.auth_mode if row else "api_keys",
        key_id=row.key_id if row else None,
        has_secret=bool(row and row.secret_encrypted),
        has_webhook_secret=bool(row and row.webhook_secret_encrypted),
        is_test_mode=bool(row and row.key_id and row.key_id.startswith("rzp_test_")),
        webhook_url=_webhook_url(tenant_id),
    )


async def save_settings(
    session: AsyncSession, tenant_id: uuid.UUID, req: OnlinePaymentSettingsRequest
) -> OnlinePaymentSettingsResponse:
    if not await _plan_allows(session, tenant_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Online payments are available on the Pro Max plan")

    row = await get_gateway_row(session, tenant_id)
    if row is None:
        row = TenantPaymentGateway(tenant_id=tenant_id, provider="razorpay", auth_mode="api_keys")
        session.add(row)

    if req.key_id is not None and req.key_id.strip():
        row.key_id = req.key_id.strip()
    if req.key_secret is not None and req.key_secret.strip():
        row.secret_encrypted = encrypt_secret(req.key_secret.strip())
    if req.webhook_secret is not None and req.webhook_secret.strip():
        row.webhook_secret_encrypted = encrypt_secret(req.webhook_secret.strip())
    if req.enabled is not None:
        if req.enabled and not (row.key_id and row.secret_encrypted):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Enter the Razorpay key ID and key secret before enabling"
            )
        row.is_enabled = req.enabled
    await session.flush()
    return await get_settings_view(session, tenant_id)


async def test_credentials(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
    """Makes one cheap authenticated call so a wrong key/secret is caught at setup time,
    not by the first customer. Returns whether the key is a test-mode key.
    """
    row = await get_gateway_row(session, tenant_id)
    gateway = build_gateway(row) if row else None
    if gateway is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Save the Razorpay key ID and key secret first")
    await gateway.check_credentials()
    return gateway.is_test_mode


# --- Guest side --------------------------------------------------------------------


async def _attempts_for_order(
    session: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID
) -> list[PaymentAttempt]:
    return list(
        (
            await session.execute(
                select(PaymentAttempt)
                .where(PaymentAttempt.tenant_id == tenant_id, PaymentAttempt.order_id == order_id)
                .order_by(PaymentAttempt.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def find_paid_attempt(
    session: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID
) -> PaymentAttempt | None:
    attempts = await _attempts_for_order(session, tenant_id, order_id)
    return next((a for a in attempts if a.status == "paid"), None)


async def _auto_send_takeaway_kot(
    session: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID
) -> KotSendResult | None:
    """A verified online payment means the takeaway customer has paid, so their kitchen
    ticket fires automatically (same send path as the Send button). Returns None when there
    is nothing new to send, e.g. staff already sent it, so a paid order is never sent twice.
    """
    tenant = (await session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    try:
        return await send_kot(session, tenant, order_id)
    except HTTPException:
        return None


async def apply_gateway_payments(
    session: AsyncSession,
    gateway: PaymentGateway,
    attempt: PaymentAttempt,
    payments: list[dict[str, Any]],
) -> PaidNotice | None:
    """Moves an attempt forward from the gateway's own list of payments for its order.
    Returns a notice only the first time the attempt becomes paid.
    """
    if attempt.status == "paid":
        return None
    expected = to_paise(float(attempt.amount))

    good = next(
        (p for p in payments if p.get("status") == "captured" and int(p.get("amount", 0)) == expected), None
    )
    if good is None:
        authorized = next(
            (p for p in payments if p.get("status") == "authorized" and int(p.get("amount", 0)) == expected),
            None,
        )
        if authorized is not None:
            good = await gateway.capture_payment(authorized["id"], expected)
            if good.get("status") != "captured":
                good = None

    if good is not None:
        attempt.status = "paid"
        attempt.provider_payment_id = good.get("id")
        attempt.method = good.get("method")
        attempt.failure_reason = None
        attempt.paid_at = datetime.now(UTC)
        guest_session = None
        if attempt.guest_session_id is not None:
            guest_session = (
                await session.execute(select(GuestSession).where(GuestSession.id == attempt.guest_session_id))
            ).scalar_one_or_none()
        if guest_session is not None and guest_session.status == "active":
            # Reuses the existing "guest says paid" state, which staff already see on the
            # KOT Tickets list — now backed by a verified payment instead of a tap.
            guest_session.status = "payment_claimed"
        await session.flush()
        if guest_session is None:
            return None
        kot_result = None
        if guest_session.table_id is None and guest_session.order_id is not None:
            kot_result = await _auto_send_takeaway_kot(session, attempt.tenant_id, guest_session.order_id)
        return PaidNotice(
            guest_session.location_id, guest_session.table_id, guest_session.pickup_token, kot_result
        )

    failed = [p for p in payments if p.get("status") == "failed"]
    if failed:
        attempt.status = "failed"
        attempt.failure_reason = failed[-1].get("error_description") or "The payment didn't go through"
        await session.flush()
    return None


async def sync_order_attempts(
    session: AsyncSession, gateway: PaymentGateway, tenant_id: uuid.UUID, order_id: uuid.UUID
) -> PaidNotice | None:
    """Asks the gateway about the order's recent unpaid attempts. A customer returning
    from their UPI app slowly, or a missed webhook, is corrected here.
    """
    notice: PaidNotice | None = None
    attempts = await _attempts_for_order(session, tenant_id, order_id)
    for attempt in attempts[:_RECENT_ATTEMPTS_TO_SYNC]:
        if attempt.status == "paid":
            continue
        payments = await gateway.fetch_order_payments(attempt.provider_order_id)
        notice = await apply_gateway_payments(session, gateway, attempt, payments) or notice
    return notice


async def guest_payment_info(
    session: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID | None
) -> GuestOnlinePaymentInfo:
    gateway = await get_gateway(session, tenant_id)
    if gateway is None:
        return GuestOnlinePaymentInfo()
    paid = await find_paid_attempt(session, tenant_id, order_id) if order_id else None
    return GuestOnlinePaymentInfo(
        enabled=True,
        key_id=gateway.checkout_key,
        is_test_mode=gateway.is_test_mode,
        paid=paid is not None,
        paid_amount=float(paid.amount) if paid else None,
        reference=paid.provider_payment_id if paid else None,
    )


async def create_guest_payment(
    session: AsyncSession, guest: CurrentGuest, guest_session: GuestSession
) -> GuestCreatePaymentResponse:
    if guest_session.order_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add an item before paying")
    gateway = await get_gateway(session, guest.tenant_id)
    if gateway is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Online payment isn't available here")

    # A payment that already went through (slow return from the UPI app) must never be
    # charged twice: settle what the gateway knows before creating anything new.
    await sync_order_attempts(session, gateway, guest.tenant_id, guest_session.order_id)
    if await find_paid_attempt(session, guest.tenant_id, guest_session.order_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This order has already been paid")

    # Amount always comes from the server's own bill calculation, never from the client.
    preview = await preview_bill(
        session, guest.tenant_id, BillPreviewRequest(order_id=guest_session.order_id)
    )
    amount_paise = to_paise(preview.grand_total)
    if amount_paise <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to pay for this order")

    attempt_id = uuid.uuid4()
    label = guest_session.pickup_token or "table order"
    gateway_order = await gateway.create_order(
        amount_paise,
        receipt=f"KM-{str(attempt_id)[:8]}",
        notes={"tenant_id": str(guest.tenant_id), "order_id": str(guest_session.order_id), "for": label},
    )
    session.add(
        PaymentAttempt(
            id=attempt_id,
            tenant_id=guest.tenant_id,
            order_id=guest_session.order_id,
            guest_session_id=guest_session.id,
            provider=gateway.provider,
            provider_order_id=gateway_order["id"],
            amount=amount_paise / 100,
            currency="INR",
            status="created",
        )
    )
    await session.flush()

    branch = await resolve_branch_header(session, guest_session.location_id)
    tenant = (await session.execute(select(Tenant).where(Tenant.id == guest.tenant_id))).scalar_one()
    return GuestCreatePaymentResponse(
        provider_order_id=gateway_order["id"],
        key_id=gateway.checkout_key,
        amount_paise=amount_paise,
        currency="INR",
        hotel_name=tenant.company_name if branch.name == tenant.company_name else branch.name,
        description=f"Order {label}",
        customer_name=guest_session.customer_name,
        customer_phone=guest_session.customer_phone,
        is_test_mode=gateway.is_test_mode,
    )


async def guest_payment_status(
    session: AsyncSession, guest: CurrentGuest, guest_session: GuestSession
) -> tuple[GuestPaymentStatusResponse, PaidNotice | None]:
    if guest_session.order_id is None:
        return GuestPaymentStatusResponse(status="none"), None
    gateway = await get_gateway(session, guest.tenant_id)
    notice: PaidNotice | None = None
    if gateway is not None:
        notice = await sync_order_attempts(session, gateway, guest.tenant_id, guest_session.order_id)

    attempts = await _attempts_for_order(session, guest.tenant_id, guest_session.order_id)
    if not attempts:
        return GuestPaymentStatusResponse(status="none"), notice
    paid = next((a for a in attempts if a.status == "paid"), None)
    chosen = paid or attempts[0]
    return (
        GuestPaymentStatusResponse(
            status=chosen.status,
            paid_amount=float(chosen.amount) if chosen.status == "paid" else None,
            reference=chosen.provider_payment_id,
            failure_reason=chosen.failure_reason if chosen.status == "failed" else None,
            attempt_id=chosen.id,
        ),
        notice,
    )


# --- Webhook -----------------------------------------------------------------------


async def handle_webhook(
    session: AsyncSession, tenant_id: uuid.UUID, raw_body: bytes, signature: str, payload: dict[str, Any]
) -> PaidNotice | None:
    row = await get_gateway_row(session, tenant_id)
    gateway = build_gateway(row) if row else None
    if gateway is None or not gateway.verify_webhook_signature(raw_body, signature):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature")

    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    provider_order_id = entity.get("order_id")
    if not provider_order_id:
        return None
    attempt = (
        await session.execute(
            select(PaymentAttempt).where(
                PaymentAttempt.tenant_id == tenant_id,
                PaymentAttempt.provider == gateway.provider,
                PaymentAttempt.provider_order_id == provider_order_id,
            )
        )
    ).scalar_one_or_none()
    if attempt is None:
        return None
    # Re-read from the gateway rather than trusting the webhook body's contents.
    payments = await gateway.fetch_order_payments(provider_order_id)
    return await apply_gateway_payments(session, gateway, attempt, payments)


async def broadcast_paid_notice(notice: PaidNotice) -> None:
    """Live updates for staff screens after a verified payment: the "paid" alert, and for a
    takeaway order that just fired its kitchen ticket, the same ticket and stock messages a
    normal KOT send broadcasts. Called only after the DB transaction has committed.
    """
    await ws_manager.broadcast(
        notice.location_id,
        {
            "type": "payment_claimed",
            "table_id": str(notice.table_id) if notice.table_id else None,
            "pickup_token": notice.pickup_token,
            "verified": True,
        },
    )
    if notice.kot_result is not None:
        await ws_manager.broadcast(notice.location_id, build_kot_ticket_broadcast(notice.kot_result))
        for stock_message in notice.kot_result.stock_messages:
            await ws_manager.broadcast(notice.location_id, stock_message)
