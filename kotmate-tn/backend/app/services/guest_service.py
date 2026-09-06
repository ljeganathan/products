import secrets
import uuid
from datetime import UTC, date, datetime
from urllib.parse import quote

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentGuest, CurrentUser
from app.core.security import GUEST_TOKEN_EXPIRE, hash_password
from app.models import GuestSession, HotelMaster, Item, Role, Table, TableQrCode, Tenant, User
from app.schemas.bills import BillPreviewRequest
from app.schemas.guest import GuestBillPreviewResponse, GuestProfileUpdateRequest, GuestSessionResponse
from app.schemas.kot import ActiveKotTicketResponse
from app.schemas.orders import OrderCreateRequest, OrderLineInput, OrderResponse, OrderUpdateRequest
from app.services.bill_service import preview_bill
from app.services.branch_header import resolve_branch_header
from app.services.item_service import list_items, list_top_sellers
from app.services.kot_service import KotSendResult, list_active_tickets
from app.services.kot_service import send_kot as _send_kot
from app.services.order_service import (
    apply_order_update,
    build_order_response,
    create_order,
    get_order_or_404,
)
from app.services.tenant_onboarding import get_active_plan, get_active_subscription

_UNAVAILABLE_MESSAGE = "Ordering is currently unavailable at this table."


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


async def _resolve_qr_or_404(session: AsyncSession, qr_token: str) -> TableQrCode:
    qr = (
        await session.execute(
            select(TableQrCode).where(TableQrCode.qr_token == qr_token, TableQrCode.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if qr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This QR code isn't valid or has been deactivated")
    return qr


def to_session_response(guest_session: GuestSession, table: Table) -> GuestSessionResponse:
    return GuestSessionResponse(
        guest_token="",  # filled in by the caller, which alone knows the JWT
        tenant_id=guest_session.tenant_id,
        location_id=guest_session.location_id,
        table_id=guest_session.table_id,
        table_number=table.table_number,
        customer_name=guest_session.customer_name,
        customer_phone=guest_session.customer_phone,
        order_id=guest_session.order_id,
        status=guest_session.status,
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


async def create_or_resume_session(
    session: AsyncSession, qr_token: str
) -> tuple[GuestSession, TableQrCode, Table, Tenant]:
    """The guest "login" — one table, one QR, one shared order. Every scan of a
    table's QR resolves to that table's single active `guest_sessions` row (creating
    one if none exists yet, or the previous one already expired) — there's no
    customer/seat identity to assign or detect: whoever scans it is ordering into the
    same cart, exactly like a table already works for staff without seat-splitting
    (CLAUDE.md §11's party_label feature is a separate, staff-side-only concern).
    """
    await _bypass_rls_for_guest_login(session)
    qr = await _resolve_qr_or_404(session, qr_token)
    tenant = (await session.execute(select(Tenant).where(Tenant.id == qr.tenant_id))).scalar_one()
    await _reject_if_ordering_unavailable(session, tenant)
    table = (await session.execute(select(Table).where(Table.id == qr.table_id))).scalar_one()

    now = datetime.now(UTC)
    existing = await _current_guest_session(session, tenant.id, qr.table_id)
    if existing is not None:
        if existing.expires_at > now:
            return existing, qr, table, tenant
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
    return guest_session, qr, table, tenant


async def _get_active_session_or_404(session: AsyncSession, guest: CurrentGuest) -> GuestSession:
    row = await _current_guest_session(session, guest.tenant_id, guest.table_id)
    if row is None or row.expires_at < datetime.now(UTC):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This ordering session has ended — please rescan")
    return row


async def update_profile(
    session: AsyncSession, guest: CurrentGuest, req: GuestProfileUpdateRequest
) -> GuestSession:
    guest_session = await _get_active_session_or_404(session, guest)
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
    guest_session = await _get_active_session_or_404(session, guest)
    system_user = await get_or_create_system_account(session, tenant)
    fake_current_user = _system_current_user(system_user, tenant.id)

    if guest_session.order_id is None:
        table = (
            await session.execute(select(Table).where(Table.id == guest_session.table_id))
        ).scalar_one()
        req = OrderCreateRequest(
            location_id=guest_session.location_id,
            section_id=table.section_id,
            table_id=table.id,
            waiter_id=None,
            items=items,
            party_label=None,
        )
        order = await create_order(session, tenant.id, fake_current_user, req, source="guest")
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
    guest_session = await _get_active_session_or_404(session, guest)
    if guest_session.order_id is None:
        return None
    order_row = await get_order_or_404(session, guest.tenant_id, guest_session.order_id)
    return await build_order_response(session, order_row)


async def send_kot_for_guest(session: AsyncSession, guest: CurrentGuest) -> KotSendResult:
    tenant = (await session.execute(select(Tenant).where(Tenant.id == guest.tenant_id))).scalar_one()
    guest_session = await _get_active_session_or_404(session, guest)
    if guest_session.order_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add an item before sending to the kitchen")
    return await _send_kot(session, tenant, guest_session.order_id)


async def get_order_status(session: AsyncSession, guest: CurrentGuest) -> list[ActiveKotTicketResponse]:
    guest_session = await _get_active_session_or_404(session, guest)
    if guest_session.order_id is None:
        return []
    tickets = await list_active_tickets(session, guest.tenant_id, guest.location_id)
    return [t for t in tickets if t.order_id == guest_session.order_id]


async def preview_guest_bill(session: AsyncSession, guest: CurrentGuest) -> GuestBillPreviewResponse:
    guest_session = await _get_active_session_or_404(session, guest)
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
        upi_link = (
            f"upi://pay?pa={quote(hotel.upi_id)}&pn={quote(branch.name)}"
            f"&am={preview.grand_total:.2f}&cu=INR&tn={quote('Table order')}"
        )
    return GuestBillPreviewResponse(**preview.model_dump(), upi_link=upi_link)


async def request_bill(session: AsyncSession, guest: CurrentGuest) -> GuestSession:
    guest_session = await _get_active_session_or_404(session, guest)
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
