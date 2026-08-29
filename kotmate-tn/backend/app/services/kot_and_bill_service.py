from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models import Tenant
from app.schemas.bills import BillCreateRequest, BillResponse
from app.services.bill_service import finalize_bill
from app.services.kot_service import KotSendResult, has_kds_feature, send_kot
from app.services.tenant_onboarding import get_active_plan

_KDS_UPGRADE_MESSAGE = "The KOT screen is only available on Pro Max. Upgrade to unlock it."


async def send_kot_and_finalize_bill(
    session: AsyncSession, tenant: Tenant, current_user: CurrentUser, req: BillCreateRequest
) -> tuple[BillResponse, KotSendResult]:
    """Guided POS's non-seating "KOT + Print Bill" action — fires a kitchen ticket and
    finalizes the bill in one DB transaction (no commit between the two halves, the
    caller commits once), so a network blip between them can never leave a ticket fired
    with no bill, or a bill charged with no ticket ever reaching the kitchen. Only ever
    called from that one Guided POS action; Default layout and Guided POS dine-in
    tables are entirely unaffected and keep calling the existing separate
    send-to-KOT/finalize-bill endpoints/services.
    """
    plan = await get_active_plan(session, tenant.id)
    if not has_kds_feature(plan.features if plan else None):
        raise HTTPException(status.HTTP_403_FORBIDDEN, _KDS_UPGRADE_MESSAGE)

    kot_result = await send_kot(session, tenant, req.order_id)
    # Marks this ticket as an exception to the usual "hide once billed" visibility rule
    # (kot_service.list_active_tickets) — the order below is about to be billed, but the
    # kitchen still needs to see the ticket until it's actually ready.
    kot_result.ticket.order_billed_via_kot = True
    await session.flush()

    bill_response = await finalize_bill(session, tenant.id, current_user, req)

    merged = bill_response.model_copy(
        update={
            "kot_ticket_number": kot_result.ticket.ticket_number,
            "kot_printed": kot_result.printed,
            "kot_print_job": kot_result.print_job,
            "kot_print_error": kot_result.print_error,
        }
    )
    return merged, kot_result
