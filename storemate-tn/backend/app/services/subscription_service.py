import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.plan_limits import UNLIMITED
from app.models.enums import InvoiceStatus, SubscriptionStatus
from app.models.plan import Plan
from app.models.printer_profile import PrinterProfile
from app.models.store import Store
from app.models.subscription import Subscription, SubscriptionInvoice
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.common import UsageOut
from app.schemas.platform_tenant import TenantOut

BILLING_PERIOD_DAYS = 30
GST_RATE_BPS = 1800  # 18% GST on the SaaS fee itself, per docs/SUBSCRIPTION_TIERS.md
EXTRA_USER_PRICE_PAISE = 9_900  # ₹99/user/month
EXTRA_STORE_PRICE_PAISE = 99_900  # ₹999/store/month


async def get_tenant_usage(
    db: AsyncSession, tenant_id: uuid.UUID, subscription: Subscription, plan: Plan
) -> UsageOut:
    users_count = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.tenant_id == tenant_id, User.is_active.is_(True))
    )
    stores_count = await db.scalar(
        select(func.count()).select_from(Store).where(Store.tenant_id == tenant_id)
    )
    printer_profiles_count = await db.scalar(
        select(func.count())
        .select_from(PrinterProfile)
        .where(PrinterProfile.tenant_id == tenant_id)
    )
    users_limit = (
        plan.max_users + subscription.extra_users if plan.max_users != UNLIMITED else UNLIMITED
    )
    stores_limit = (
        plan.max_stores + subscription.extra_stores if plan.max_stores != UNLIMITED else UNLIMITED
    )
    return UsageOut(
        users_count=users_count or 0,
        users_limit=users_limit,
        stores_count=stores_count or 0,
        stores_limit=stores_limit,
        printer_profiles_count=printer_profiles_count or 0,
        printer_profiles_limit=plan.max_printer_profiles,
    )


async def build_tenant_out(db: AsyncSession, tenant: Tenant) -> TenantOut:
    joined = await SubscriptionRepository(db).get_active_joined_for_tenant(tenant.id)
    if joined is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tenant '{tenant.name}' has no active subscription — data integrity issue",
        )
    subscription, _, plan, _ = joined
    usage = await get_tenant_usage(db, tenant.id, subscription, plan)
    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        owner_email=tenant.owner_email,
        owner_phone=tenant.owner_phone,
        status=tenant.status,
        created_at=tenant.created_at,
        subscription_id=subscription.id,
        plan_id=plan.id,
        plan_code=plan.code,
        plan_name=plan.name,
        subscription_status=subscription.status,
        current_period_end=subscription.current_period_end,
        usage=usage,
        has_pending_upgrade_request=subscription.requested_plan_id is not None,
    )


async def get_plan_change_blockers(
    db: AsyncSession, tenant_id: uuid.UUID, subscription: Subscription, target_plan: Plan
) -> list[str]:
    """Reasons a plan change would leave the tenant over its new limits.

    Empty list means the change is safe to apply immediately — matches
    docs/SUBSCRIPTION_TIERS.md's "downgrades are blocked if current usage
    exceeds the target plan's limits" note (this also protects an upgrade
    that happens to lower a limit, though that's not a real scenario today).
    """
    reasons: list[str] = []

    users_count = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.tenant_id == tenant_id, User.is_active.is_(True))
    )
    if target_plan.max_users != UNLIMITED:
        limit = target_plan.max_users + subscription.extra_users
        if (users_count or 0) > limit:
            reasons.append(
                f"{users_count} active users exceed the '{target_plan.name}' plan's limit of "
                f"{limit}. Deactivate {(users_count or 0) - limit} user(s) first."
            )

    stores_count = await db.scalar(
        select(func.count()).select_from(Store).where(Store.tenant_id == tenant_id)
    )
    if target_plan.max_stores != UNLIMITED:
        limit = target_plan.max_stores + subscription.extra_stores
        if (stores_count or 0) > limit:
            reasons.append(
                f"{stores_count} stores exceed the '{target_plan.name}' plan's limit of {limit}. "
                f"Remove {(stores_count or 0) - limit} store(s) first."
            )

    printer_profiles_count = await db.scalar(
        select(func.count())
        .select_from(PrinterProfile)
        .where(PrinterProfile.tenant_id == tenant_id)
    )
    if target_plan.max_printer_profiles != UNLIMITED:
        if (printer_profiles_count or 0) > target_plan.max_printer_profiles:
            over_by = (printer_profiles_count or 0) - target_plan.max_printer_profiles
            reasons.append(
                f"{printer_profiles_count} printer profiles exceed the '{target_plan.name}' plan's "
                f"limit of {target_plan.max_printer_profiles}. Remove {over_by} profile(s) first."
            )

    return reasons


def compute_invoice_amount(plan: Plan, subscription: Subscription) -> tuple[int, int]:
    """Returns (amount_paise, gst_paise) for one billing period of `subscription`."""
    amount_paise = (
        plan.price_paise
        + subscription.extra_users * EXTRA_USER_PRICE_PAISE
        + subscription.extra_stores * EXTRA_STORE_PRICE_PAISE
    )
    gst_paise = (amount_paise * GST_RATE_BPS) // 10_000
    return amount_paise, gst_paise


async def generate_next_invoice(
    db: AsyncSession, subscription: Subscription, plan: Plan
) -> SubscriptionInvoice:
    """Creates an invoice for the billing period that starts where the
    subscription's current period ends — the period only actually rolls
    forward once that invoice is marked paid (see mark_invoice_paid)."""
    amount_paise, gst_paise = compute_invoice_amount(plan, subscription)

    invoice_repo = InvoiceRepository(db)
    period_start = subscription.current_period_end
    year_month = period_start.strftime("%Y%m")
    count_this_month = await invoice_repo.count_by_invoice_number_prefix(f"INV-{year_month}-")
    invoice_number = f"INV-{year_month}-{count_this_month + 1:04d}"

    invoice = SubscriptionInvoice(
        tenant_id=subscription.tenant_id,
        subscription_id=subscription.id,
        amount_paise=amount_paise,
        gst_paise=gst_paise,
        status=InvoiceStatus.PENDING,
        invoice_number=invoice_number,
        issued_at=datetime.now(UTC),
    )
    return await invoice_repo.create(invoice)


def mark_invoice_paid(invoice: SubscriptionInvoice, subscription: Subscription) -> None:
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = datetime.now(UTC)
    # Roll the subscription's billing period forward to match what this
    # invoice covered, and clear any past-due state now that it's settled.
    subscription.current_period_start = subscription.current_period_end
    subscription.current_period_end = subscription.current_period_start + timedelta(
        days=BILLING_PERIOD_DAYS
    )
    subscription.status = SubscriptionStatus.ACTIVE
