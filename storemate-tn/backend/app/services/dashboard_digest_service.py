import asyncio
import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models.enums import SubscriptionStatus, UserRole
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.dashboard_repository import DashboardRepository
from app.services.email_service import get_email_service
from app.utils.currency import format_paise_inr

logger = logging.getLogger(__name__)


async def _get_digest_eligible_tenant_ids(db: AsyncSession) -> list[uuid.UUID]:
    result = await db.execute(
        select(Subscription.tenant_id, Plan.features_json)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
    )
    # Scheduled digest emails are the same Pro Max tier as the PDF export
    # and store-switcher (docs/SUBSCRIPTION_TIERS.md) — reusing `multi_store`
    # rather than adding a fourth feature flag for one more Pro-Max-only toggle.
    return [
        tenant_id
        for tenant_id, features in result.tuples().all()
        if features.get("multi_store", False)
    ]


async def run_daily_digest_emails() -> int:
    """APScheduler job (daily, 08:00 server time, see core/scheduler.py):
    emails every Pro Max tenant's active admin(s) a plain-text summary of
    today's sales so far. Returns the number of emails handed to
    `EmailService.send` (still counted even if SMTP is unconfigured and the
    service just logs-and-skips — the job's own responsibility ends at
    calling send)."""
    sent = 0
    email_service = get_email_service()
    async with AsyncSessionLocal() as db:
        eligible_tenant_ids = await _get_digest_eligible_tenant_ids(db)
        dashboard_repo = DashboardRepository(db)

        for tenant_id in eligible_tenant_ids:
            tenant = await db.get(Tenant, tenant_id)
            if tenant is None:
                continue

            summary = await dashboard_repo.get_summary(tenant_id, None, date.today())
            admins_result = await db.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.role == UserRole.ADMIN,
                    User.is_active.is_(True),
                )
            )
            admins = list(admins_result.scalars().all())

            body = (
                f"Good morning! Here's {tenant.name}'s snapshot for {date.today().isoformat()}:\n\n"
                f"Sales so far today: {format_paise_inr(summary['total_paise'])}\n"
                f"Bills: {summary['bill_count']}\n"
                f"Average bill value: {format_paise_inr(summary['avg_bill_paise'])}\n\n"
                "— StoreMate TN"
            )
            for admin in admins:
                await asyncio.to_thread(
                    email_service.send,
                    to=admin.email,
                    subject=f"{tenant.name} — daily summary",
                    body=body,
                )
                sent += 1

    return sent
