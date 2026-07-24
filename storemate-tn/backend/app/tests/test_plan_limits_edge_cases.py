"""Edge cases in middleware/plan_limits.py not already exercised through the
ordinary per-resource tests (test_printer_profiles.py, test_stock.py, etc.)
— specifically what happens when a tenant has no active subscription at
all (e.g. cancelled and never replaced), since every limit/feature check
funnels through the same `get_active_subscription_with_plan` guard."""

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.plan_limits import (
    check_printer_profile_limit,
    check_store_limit,
    check_user_limit,
    feature_enabled,
    get_active_subscription_with_plan,
    get_saved_bill_days,
)
from app.models.enums import SubscriptionStatus


async def test_no_active_subscription_raises_402(
    lite_tenant: dict, db_session: AsyncSession
) -> None:
    subscription = lite_tenant["subscription"]
    subscription.status = SubscriptionStatus.CANCELLED
    await db_session.flush()

    with pytest.raises(HTTPException) as exc:
        await get_active_subscription_with_plan(db_session, lite_tenant["tenant"].id)
    assert exc.value.status_code == 402


async def test_every_limit_check_surfaces_the_same_402_with_no_subscription(
    lite_tenant: dict, db_session: AsyncSession
) -> None:
    subscription = lite_tenant["subscription"]
    subscription.status = SubscriptionStatus.CANCELLED
    await db_session.flush()
    tenant_id = lite_tenant["tenant"].id

    for check in (check_user_limit, check_store_limit, check_printer_profile_limit):
        with pytest.raises(HTTPException) as exc:
            await check(db_session, tenant_id)
        assert exc.value.status_code == 402

    with pytest.raises(HTTPException):
        await feature_enabled(db_session, tenant_id, "low_stock_alerts")
    with pytest.raises(HTTPException):
        await get_saved_bill_days(db_session, tenant_id)
