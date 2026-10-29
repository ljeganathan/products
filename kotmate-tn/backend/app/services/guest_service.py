import logging
import secrets
import uuid
from datetime import UTC, date, datetime
from urllib.parse import quote

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentGuest, CurrentUser
from app.core.security import GUEST_TOKEN_EXPIRE, hash_password
from app.models import (
    GuestSession,
    HotelMaster,
    Item,
    Role,
    SeatingSection,
    SectionQrCode,
    Table,
    TableQrCode,
    Tenant,
    TenantLocation,
    User,
)
from app.schemas.bills import BillCreateRequest, BillPaymentInput, BillPreviewRequest, BillResponse
from app.schemas.guest import GuestBillPreviewResponse, GuestProfileUpdateRequest, GuestSessionResponse
from app.schemas.kot import ActiveKotTicketResponse
from app.schemas.orders import OrderCreateRequest, OrderLineInput, OrderResponse, OrderUpdateRequest
from app.services.bill_service import finalize_bill, preview_bill
from app.services.branch_header import resolve_branch_header
from app.services.item_service import list_items, list_top_sellers
from app.services.kot_service import KotSendResult, list_active_tickets
from app.services.kot_service import send_kot as _send_kot
from app.services.online_payment_service import (
    PaidNotice,
    create_guest_payment,
    find_paid_attempt,
    guest_payment_info,
    guest_payment_status,
)
from app.services.order_service import (
    apply_order_update,
    build_order_response,
    create_order,
    get_order_or_404,
)
from app.services.payment_gateway import get_gateway
from app.services.tenant_onboarding import get_active_plan, get_active_subscription

_UNAVAILABLE_MESSAGE = "Ordering is currently unavailable right now."
# Reuses payment_gateway.py's logger — diagnostic-only, tracing a kiosk bug where the
# guest screen bounces to "session ended" right around a payment that actually
# succeeded (see `_get_active_session_or_404` and `apply_gateway_payments` below).
_logger = logging.getLogger("kotmate.payments")


def is_qr_self_order_enabled(tenant: Tenant, plan_features: dict | None) -> bool:
    """Effective on/off state — requires both the plan feature (Pro Max) and the
    tenant's own toggle, same computed-flag convention as `stock_tracking_enabled`/
    `is_report_printing_enabled`. `/auth/me`'s single source of truth for the frontend.
    """
    if not (plan_features or {}).get("qr_self_order"):
        return False
    return bool(tenant.qr_self_order_enabled)


async def _bypass_rls_for_guest_login(session: AsyncSession) -> None:
    """Same precedent as `auth.py`'s `_bypass_rls_for_login` — resolving a `qr_token`
    happens before any tenant is known, so the lookup must cross tenant boundaries by
    design (`qr_token` is globally unique, same shape as `users.user_id`).
    """
    await session.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))


async def _reject_if_ordering_unavailable(session: AsyncSession, tenant: Tenant) -> None:
    if not tenant.qr_self_order_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, _UNAVAILABLE_MESSAGE)
    plan = await get_active_plan(session, tenant.id)
    if not plan or not plan.features.get("qr_self_order"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, _UNAVAILABLE_MESSAGE)
    subscription = await get_active_subscription(session, tenant.id)
    if subscription is None or subscription.current_period_end < date.today():
        raise HTTPException(status.HTTP_403_FORBIDDEN, _UNAVAILABLE_MESSAGE)


async def get_or_create_system_account(session: AsyncSession, tenant: Tenant) -> User:
    """The one synthetic, un-loginable `pos_user_id` FK target for every guest order
    this tenant ever places — see `User.is_system_account`'s own docstring for why this
    exists instead of a nullable column. Created lazily on the tenant's first guest
    order, not at Settings-toggle time, so a tenant that enables the feature but never
    actually gets a guest order never gets a phantom user row.
    """
    login_id = f"{tenant.tenant_code}QRORDER"
    existing = (
        await session.execute(select(User).where(User.user_id == login_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    role = (await session.execute(select(Role).where(Role.code == "pos_user"))).scalar_one()
    user = User(
        tenant_id=tenant.id,
        user_id=login_id,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role_id=role.id,
        name="QR Self-Order",
        is_active=False,
        is_system_account=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _resolve_qr_or_404(session: AsyncSession, qr_token: str) -> TableQrCode | SectionQrCode:
    """`qr_token` is drawn from the same `secrets.token_urlsafe(24)` space for both a
    table's QR and a non-seating section's Takeaway QR (Phase 26), so a raw token alone
    doesn't say which kind it is — try both tables in turn.
    """
    table_qr = (
        await session.execute(
            select(TableQrCode).where(TableQrCode.qr_token == qr_token, TableQrCode.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if table_qr is not None:
        return table_qr
    section_qr = (
        await session.execute(
            select(SectionQrCode).where(SectionQrCode.qr_token == qr_token, SectionQrCode.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if section_qr is not None:
        return section_qr
    raise HTTPException(status.HTTP_404_NOT_FOUND, "This QR code isn't valid or has been deactivated")


async def to_session_response(session: AsyncSession, guest_session: GuestSession) -> GuestSessionResponse:
    table_number: str | None = None
    section_name_en: str | None = None
    if guest_session.table_id is not None:
        table = (
            await session.execute(select(Table).where(Table.id == guest_session.table_id))
        ).scalar_one()
        table_number = table.table_number
    else:
        section = (
            await session.execute(
                select(SeatingSection).where(SeatingSection.id == guest_session.section_id)
            )
        ).scalar_one()
        section_name_en = section.name_en
    branch = await resolve_branch_header(session, guest_session.location_id)
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == guest_session.tenant_id))
    ).scalar_one()
    kiosk_welcome_image_url = None
    if guest_session.is_kiosk:
        hotel = (
            await session.execute(
                select(HotelMaster).where(HotelMaster.location_id == guest_session.location_id)
            )
        ).scalar_one_or_none()
        kiosk_welcome_image_url = hotel.kiosk_welcome_image_url if hotel else None
    return GuestSessionResponse(
        guest_token="",  # filled in by the caller, which alone knows the JWT
        tenant_id=guest_session.tenant_id,
        location_id=guest_session.location_id,
        hotel_name=tenant.company_name,
        branch_name=branch.name,
        table_id=guest_session.table_id,
        table_number=table_number,
        pickup_token=guest_session.pickup_token,
        section_name_en=section_name_en,
        customer_name=guest_session.customer_name,
        customer_phone=guest_session.customer_phone,
        order_id=guest_session.order_id,
        status=guest_session.status,
        takeaway_payment=guest_session.takeaway_payment,
        kiosk_welcome_image_url=kiosk_welcome_image_url,
    )


async def _current_guest_session(
    session: AsyncSession, tenant_id: uuid.UUID, table_id: uuid.UUID
) -> GuestSession | None:
    """The table's one current session. `active` and `payment_claimed` are both
    "still open" states — a guest requesting the bill doesn't end the table's session,
    only a staff bill finalize does (`bill_service.finalize_bill` closes it) — so both
    must be treated as "current" here, not just `active`. Also self-heals a
    duplicate-current-rows state a since-fixed bug could have left behind (it only
    checked `active`, so a `payment_claimed` row could sit unresolved forever while a
    separate `active` row got created alongside it): only the most recently created
    row is ever treated as current, and any straggler(s) are force-closed.
    """
    rows = (
        (
            await session.execute(
                select(GuestSession)
                .where(
                    GuestSession.tenant_id == tenant_id,
                    GuestSession.table_id == table_id,
                    GuestSession.status.in_(("active", "payment_claimed")),
                )
                .order_by(GuestSession.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return None
    current, *stragglers = rows
    for row in stragglers:
        row.status = "closed"
    if stragglers:
        await session.flush()
    return current


async def _next_pickup_token(session: AsyncSession, tenant_id: uuid.UUID) -> str:
    """A Takeaway session's table-number equivalent (e.g. "TA-14") — per-tenant
    sequential, same `count + 1` convention as `kot_service._next_ticket_number`.
    """
    count = (
        await session.execute(
            select(func.count())
            .select_from(GuestSession)
            .where(GuestSession.tenant_id == tenant_id, GuestSession.pickup_token.is_not(None))
        )
    ).scalar_one()
    return f"TA-{count + 1}"


async def create_or_resume_session(session: AsyncSession, qr_token: str) -> tuple[GuestSession, Tenant]:
    """The guest "login". A table's QR resolves to that table's single active
    `guest_sessions` row (creating one if none exists yet, or the previous one already
    expired) — there's no customer/seat identity to assign or detect: whoever scans it
    is ordering into the same cart, exactly like a table already works for staff
    without seat-splitting (CLAUDE.md §11's party_label feature is a separate,
    staff-side-only concern).

    A non-seating section's Takeaway QR (Phase 26) is the opposite: every scan is a
    brand-new, independent session — two strangers scanning a counter's one Takeaway
    code are two unrelated orders, never a shared cart, so there is deliberately no
    resume-by-section lookup here at all.
    """
    await _bypass_rls_for_guest_login(session)
    qr = await _resolve_qr_or_404(session, qr_token)
    tenant = (await session.execute(select(Tenant).where(Tenant.id == qr.tenant_id))).scalar_one()
    await _reject_if_ordering_unavailable(session, tenant)
    now = datetime.now(UTC)

    if isinstance(qr, SectionQrCode):
        guest_session = GuestSession(
            tenant_id=tenant.id,
            location_id=qr.location_id,
            section_id=qr.section_id,
            pickup_token=await _next_pickup_token(session, tenant.id),
            status="active",
            expires_at=now + GUEST_TOKEN_EXPIRE,
        )
        session.add(guest_session)
        await session.flush()
        return guest_session, tenant

    existing = await _current_guest_session(session, tenant.id, qr.table_id)
    if existing is not None:
        if existing.expires_at > now:
            return existing, tenant
        # Expired but still flagged 'active'/'payment_claimed' — must be closed before
        # inserting the table's next session, or the insert below trips
        # `uq_guest_sessions_active_table` (at most one active row per table).
        existing.status = "closed"
        await session.flush()

    guest_session = GuestSession(
        tenant_id=tenant.id,
        location_id=qr.location_id,
        table_id=qr.table_id,
        status="active",
        expires_at=now + GUEST_TOKEN_EXPIRE,
    )
    session.add(guest_session)
    await session.flush()
    return guest_session, tenant


async def _get_active_session_or_404(
    session: AsyncSession, guest: CurrentGuest, context: str = "unknown"
) -> GuestSession:
    """`context` is diagnostic-only (logged on a 404, see below) — names the call site
    so a stray "session ended" can be traced back to exactly which guest-side request
    triggered it, without guessing from the frontend alone.
    """
    if guest.table_id is None:
        # Takeaway: resolved by the JWT's own session id, never by table/section —
        # there is nothing to "resume" or share (see create_or_resume_session).
        row = (
            await session.execute(
                select(GuestSession).where(
                    GuestSession.id == guest.guest_session_id,
                    GuestSession.tenant_id == guest.tenant_id,
                    GuestSession.status.in_(("active", "payment_claimed")),
                )
            )
        ).scalar_one_or_none()
    else:
        row = await _current_guest_session(session, guest.tenant_id, guest.table_id)
    if row is None or row.expires_at < datetime.now(UTC):
        # Diagnostic-only: look the row up again with no status/table filter, purely to
        # log *why* it was excluded (closed? expired? genuinely missing?) — never used
        # to decide anything, so this can't change behavior either way.
        raw = (
            await session.execute(
                select(GuestSession).where(GuestSession.id == guest.guest_session_id)
            )
        ).scalar_one_or_none()
        _logger.info(
            "Guest session 404 [%s]: guest_session_id=%s found=%s status=%s expires_at=%s now=%s",
            context,
            guest.guest_session_id,
            raw is not None,
            raw.status if raw else None,
            raw.expires_at if raw else None,
            datetime.now(UTC),
        )
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This ordering session has ended — please rescan")
    return row


async def update_profile(
    session: AsyncSession, guest: CurrentGuest, req: GuestProfileUpdateRequest
) -> GuestSession:
    guest_session = await _get_active_session_or_404(session, guest, context="update_profile")
    if req.customer_name is not None:
        guest_session.customer_name = req.customer_name
    if req.customer_phone is not None:
        guest_session.customer_phone = req.customer_phone
    await session.flush()
    return guest_session


async def get_menu(session: AsyncSession, guest: CurrentGuest) -> list[Item]:
    return await list_items(session, guest.tenant_id, category_id=None, search=None, active_only=True)


async def get_top_sellers(session: AsyncSession, guest: CurrentGuest) -> list[Item]:
    return await list_top_sellers(session, guest.tenant_id)


def _system_current_user(system_user: User, tenant_id: uuid.UUID) -> CurrentUser:
    # `role="pos_user"` — the same role that's normally the cashier-of-record, so
    # `order_service`'s existing waiter/pricing logic treats a guest order exactly
    # like a `pos_user`-placed one (no special-casing needed there at all).
    return CurrentUser(
        id=system_user.id, login_id=system_user.user_id, role="pos_user", tenant_id=tenant_id, location_ids=[]
    )


async def update_cart(
    session: AsyncSession, guest: CurrentGuest, items: list[OrderLineInput]
) -> OrderResponse:
    tenant = (await session.execute(select(Tenant).where(Tenant.id == guest.tenant_id))).scalar_one()
    guest_session = await _get_active_session_or_404(session, guest, context="update_cart")
    if guest_session.order_id is not None and await find_paid_attempt(
        session, guest.tenant_id, guest_session.order_id
    ):
        # Once an order is paid online its total is settled — further cart changes would
        # silently make the bill differ from what was charged.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This order has been paid — please ask staff to add more items"
        )
    if guest_session.table_id is not None and (
        not guest_session.customer_name or not guest_session.customer_phone
    ):
        # Dine-in only (Phase 27) — the frontend still blocks a dine-in table's whole
        # menu behind this same requirement (a full-screen prompt shown before anything
        # else renders), so this only ever fires against a stale page or a direct API
        # call there, never the normal flow. Takeaway/Kiosk guests (table_id is null)
        # deliberately browse and build a cart with no profile at all — the menu is the
        # first screen for them (production request) — and only have to share their
        # name/phone once they actually choose how to pay (place_takeaway_order).
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Please share your name and phone number before ordering"
        )
    system_user = await get_or_create_system_account(session, tenant)
    fake_current_user = _system_current_user(system_user, tenant.id)

    if guest_session.order_id is None:
        if guest_session.table_id is not None:
            table = (
                await session.execute(select(Table).where(Table.id == guest_session.table_id))
            ).scalar_one()
            section_id = table.section_id
            table_id: uuid.UUID | None = table.id
        else:
            section_id = guest_session.section_id
            table_id = None
        req = OrderCreateRequest(
            location_id=guest_session.location_id,
            section_id=section_id,
            table_id=table_id,
            waiter_id=None,
            items=items,
            party_label=None,
        )
        order = await create_order(
            session, tenant.id, fake_current_user, req, source="kiosk" if guest_session.is_kiosk else "guest"
        )
        guest_session.order_id = order.id
        await session.flush()
        return order

    order_row = await get_order_or_404(session, tenant.id, guest_session.order_id)
    return await apply_order_update(
        session, tenant.id, fake_current_user, order_row, OrderUpdateRequest(items=items)
    )


async def get_cart(session: AsyncSession, guest: CurrentGuest) -> OrderResponse | None:
    """Rehydrates the guest frontend's cart on load/reload — without this, a guest who
    added items but hasn't sent them to the kitchen yet would lose sight of their own
    draft cart the moment they refreshed the page or came back to a backgrounded tab.
    """
    guest_session = await _get_active_session_or_404(session, guest, context="get_cart")
    if guest_session.order_id is None:
        return None
    order_row = await get_order_or_404(session, guest.tenant_id, guest_session.order_id)
    return await build_order_response(session, order_row)


async def send_kot_for_guest(session: AsyncSession, guest: CurrentGuest) -> KotSendResult:
    """Dine-in only — fires a real kitchen ticket immediately, exactly as a staff
    "Add to KOT" would. Never called for a Takeaway guest (`guest.table_id is None`);
    see `place_takeaway_order` for that flow's very different timing.
    """
    tenant = (await session.execute(select(Tenant).where(Tenant.id == guest.tenant_id))).scalar_one()
    guest_session = await _get_active_session_or_404(session, guest, context="send_kot_for_guest")
    if guest_session.order_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add an item before sending to the kitchen")
    return await _send_kot(session, tenant, guest_session.order_id)


async def _finalize_kiosk_cash_order(
    session: AsyncSession, guest: CurrentGuest, guest_session: GuestSession
) -> BillResponse:
    """A Kiosk guest choosing "Pay by Cash" pays nobody online and nobody's there to
    collect cash before the fact, so — unlike a plain Takeaway QR cash order, which
    stays unbilled until staff confirms it — the bill finalizes and prints immediately
    (production request: "bill has to print"), the same way a Lite/Pro tenant's "no
    kitchen ticket step" sale always has. The kitchen ticket itself is deliberately
    held back: `send_kot`'s own guard lets a POS operator fire it later for this exact
    shape of order (billed, source="kiosk", no ticket yet) from the KOT Tickets screen's
    "Approve & Send to Kitchen" action — see `kot_service.list_active_tickets`'s kiosk
    pending-approval rows. On a plan with no KDS feature this is simply a normal direct
    bill with no kitchen-ticket concept at all, same as any other Lite/Pro sale.
    """
    tenant = (await session.execute(select(Tenant).where(Tenant.id == guest.tenant_id))).scalar_one()
    system_user = await get_or_create_system_account(session, tenant)
    fake_current_user = _system_current_user(system_user, tenant.id)
    preview = await preview_bill(
        session, guest.tenant_id, BillPreviewRequest(order_id=guest_session.order_id)
    )
    req = BillCreateRequest(
        order_id=guest_session.order_id,
        payments=[BillPaymentInput(method="cash", amount=preview.grand_total)],
    )
    return await finalize_bill(session, guest.tenant_id, fake_current_user, req)


async def place_takeaway_order(
    session: AsyncSession, guest: CurrentGuest, payment_method: str | None = None
) -> tuple[GuestSession, BillResponse | None]:
    """A Takeaway guest's equivalent of "Send to Kitchen" — deliberately does almost
    nothing server-side (production decision): no `KotTicket` is created, no stock is
    deducted, and nothing is sent to the kitchen printer yet. The items are already
    live on the order via `update_cart`; this just confirms there's something to place
    and returns the session so the guest sees their pickup token. The real kitchen
    send + bill happens together, later, when staff picks this order up from the KOT
    Tickets screen and uses the existing "KOT + Print Bill" action
    (`kot_and_bill_service.send_kot_and_finalize_bill`) — until then this order sits
    visible to staff as a pending, unconfirmed Takeaway order
    (`kot_service.list_active_tickets`'s pending-Takeaway rows), never visible to the
    kitchen itself.

    Exception: a Kiosk guest paying cash gets its bill finalized right here instead —
    see `_finalize_kiosk_cash_order`. The second tuple element is that finalized bill,
    None for every other case (including a Kiosk guest paying online, which still
    finalizes later via the verified-payment webhook as before).
    """
    guest_session = await _get_active_session_or_404(session, guest, context="place_takeaway_order")
    if guest_session.order_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add an item before placing your order")
    if payment_method is None:
        return guest_session, None

    # Takeaway/Kiosk guests only have to share their name/phone once they actually
    # choose how to pay (the menu/cart stayed open with no profile at all until now,
    # production request) — dine-in's own requirement is enforced earlier, in
    # update_cart, since a dine-in table never reaches this function at all.
    if not guest_session.customer_name or not guest_session.customer_phone:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Please share your name and phone number before paying"
        )

    if payment_method == "online":
        if guest_session.takeaway_payment == "cash":
            raise HTTPException(
                status.HTTP_409_CONFLICT, "This order is set to pay at the counter"
            )
        if await get_gateway(session, guest.tenant_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Online payment isn't available here")
        if await find_paid_attempt(session, guest.tenant_id, guest_session.order_id) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "This order has already been paid")
    guest_session.takeaway_payment = payment_method

    if payment_method == "cash" and guest_session.is_kiosk:
        bill = await _finalize_kiosk_cash_order(session, guest, guest_session)
        return guest_session, bill

    return guest_session, None


async def get_order_status(session: AsyncSession, guest: CurrentGuest) -> list[ActiveKotTicketResponse]:
    guest_session = await _get_active_session_or_404(session, guest, context="get_order_status")
    if guest_session.order_id is None:
        return []
    tickets = await list_active_tickets(session, guest.tenant_id, guest.location_id)
    return [t for t in tickets if t.order_id == guest_session.order_id]


# Merchant category code for restaurants/eating places (ISO 18245) — sent as `mc` so
# UPI apps treat the link as a merchant payment rather than a peer-to-peer transfer.
_UPI_MERCHANT_CODE_RESTAURANT = "5812"


def build_guest_upi_link(
    *, upi_id: str, payee_name: str, amount: float, order_id: uuid.UUID, order_label: str
) -> str:
    """The guest "Pay via UPI" deep link. Same core fields as the printed-bill QR, plus
    what UPI apps expect on a link opened from a web page (an "intent" payment, held to a
    stricter standard than a scanned QR): a unique transaction reference `tr` per order
    (NPCI: alphanumeric, max 35 chars), a merchant category code `mc`, and a specific
    note instead of a bare "Order".
    """
    tr = "KM" + order_id.hex[:30]
    return (
        f"upi://pay?pa={quote(upi_id)}&pn={quote(payee_name)}&mc={_UPI_MERCHANT_CODE_RESTAURANT}"
        f"&tr={tr}&am={amount:.2f}&cu=INR&tn={quote('Order ' + order_label)}"
    )


async def _table_label(session: AsyncSession, guest_session: GuestSession) -> str:
    if guest_session.table_id is None:
        return ""
    table = (
        await session.execute(select(Table).where(Table.id == guest_session.table_id))
    ).scalar_one()
    return table.table_number


async def preview_guest_bill(session: AsyncSession, guest: CurrentGuest) -> GuestBillPreviewResponse:
    guest_session = await _get_active_session_or_404(session, guest, context="preview_guest_bill")
    if guest_session.order_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add an item before viewing the bill")

    preview = await preview_bill(
        session, guest.tenant_id, BillPreviewRequest(order_id=guest_session.order_id)
    )

    hotel = (
        await session.execute(select(HotelMaster).where(HotelMaster.location_id == guest.location_id))
    ).scalar_one_or_none()
    upi_link = None
    if hotel and hotel.upi_id:
        branch = await resolve_branch_header(session, guest.location_id)
        upi_link = build_guest_upi_link(
            upi_id=hotel.upi_id,
            payee_name=branch.name,
            amount=preview.grand_total,
            order_id=guest_session.order_id,
            order_label=guest_session.pickup_token or await _table_label(session, guest_session),
        )
    online_payment = await guest_payment_info(session, guest.tenant_id, guest_session.order_id)
    return GuestBillPreviewResponse(**preview.model_dump(), upi_link=upi_link, online_payment=online_payment)


async def start_online_payment(session: AsyncSession, guest: CurrentGuest):
    guest_session = await _get_active_session_or_404(session, guest, context="start_online_payment")
    return await create_guest_payment(session, guest, guest_session)


async def online_payment_status(
    session: AsyncSession, guest: CurrentGuest
) -> tuple[object, PaidNotice | None]:
    guest_session = await _get_active_session_or_404(session, guest, context="online_payment_status")
    return await guest_payment_status(session, guest, guest_session)


async def request_bill(session: AsyncSession, guest: CurrentGuest) -> GuestSession:
    guest_session = await _get_active_session_or_404(session, guest, context="request_bill")
    if guest_session.order_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add an item before requesting the bill")
    guest_session.status = "payment_claimed"
    await session.flush()
    return guest_session


async def get_or_create_qr_code_for_table(
    session: AsyncSession, tenant_id: uuid.UUID, table: Table
) -> TableQrCode:
    """One QR per table — idempotent, safe to call again (e.g. the admin revisits
    Table Master); it never creates a second code for the same table.
    """
    existing = (
        await session.execute(select(TableQrCode).where(TableQrCode.table_id == table.id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    qr = TableQrCode(
        tenant_id=tenant_id,
        location_id=table.location_id,
        table_id=table.id,
        qr_token=secrets.token_urlsafe(24),
    )
    session.add(qr)
    await session.flush()
    return qr


async def get_qr_code_for_table(
    session: AsyncSession, tenant_id: uuid.UUID, table_id: uuid.UUID
) -> TableQrCode | None:
    return (
        await session.execute(
            select(TableQrCode).where(TableQrCode.tenant_id == tenant_id, TableQrCode.table_id == table_id)
        )
    ).scalar_one_or_none()


async def get_or_create_qr_code_for_section(
    session: AsyncSession, tenant_id: uuid.UUID, section: SeatingSection, location_id: uuid.UUID
) -> SectionQrCode:
    """One QR per (location, section) — idempotent, safe to call again. `location_id`
    is explicit rather than derived from the section, since `seating_sections` is
    tenant-wide (a multi-location tenant's one "Takeaway" section is shared by every
    branch) — each branch still gets its own independent code.
    """
    existing = (
        await session.execute(
            select(SectionQrCode).where(
                SectionQrCode.location_id == location_id, SectionQrCode.section_id == section.id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    qr = SectionQrCode(
        tenant_id=tenant_id,
        location_id=location_id,
        section_id=section.id,
        qr_token=secrets.token_urlsafe(24),
    )
    session.add(qr)
    await session.flush()
    return qr


async def get_qr_code_for_section(
    session: AsyncSession, tenant_id: uuid.UUID, section_id: uuid.UUID, location_id: uuid.UUID
) -> SectionQrCode | None:
    return (
        await session.execute(
            select(SectionQrCode).where(
                SectionQrCode.tenant_id == tenant_id,
                SectionQrCode.section_id == section_id,
                SectionQrCode.location_id == location_id,
            )
        )
    ).scalar_one_or_none()


async def start_kiosk_session(
    session: AsyncSession, current_user: CurrentUser, location_id: uuid.UUID, section_id: uuid.UUID
) -> tuple[GuestSession, Tenant]:
    """A Kiosk-role login's equivalent of scanning a counter's Takeaway QR — reuses the
    exact same section-QR session creation (`create_or_resume_session`'s SectionQrCode
    branch, including its `_reject_if_ordering_unavailable` check), just triggered by an
    authenticated staff token instead of a `qr_token` in the URL, and always mints a
    fresh session (a kiosk never resumes one, same as any other Takeaway scan).
    """
    location = (
        await session.execute(
            select(TenantLocation).where(
                TenantLocation.id == location_id, TenantLocation.tenant_id == current_user.tenant_id
            )
        )
    ).scalar_one_or_none()
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found")

    section = (
        await session.execute(
            select(SeatingSection).where(
                SeatingSection.id == section_id, SeatingSection.tenant_id == current_user.tenant_id
            )
        )
    ).scalar_one_or_none()
    if section is None or section.is_seating:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Choose a non-seating section (e.g. Takeaway) for the kiosk"
        )

    qr = await get_or_create_qr_code_for_section(session, current_user.tenant_id, section, location_id)
    guest_session, tenant = await create_or_resume_session(session, qr.qr_token)
    guest_session.is_kiosk = True
    await session.flush()
    return guest_session, tenant
