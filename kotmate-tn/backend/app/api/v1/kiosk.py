from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_role, require_tenant_scope
from app.core.security import create_guest_token
from app.db.session import get_db
from app.schemas.guest import GuestSessionResponse, KioskSessionRequest
from app.services.guest_service import start_kiosk_session, to_session_response

# A "Kiosk" role login (CLAUDE.md §5-adjacent — see constants.py's ROLE_CODES comment)
# only ever calls this one route: it mints a fresh QR-self-order guest session for an
# unattended on-premise ordering screen, then the kiosk frontend switches entirely to
# that guest JWT and talks to the existing /guest/* routes unchanged, exactly like a
# scanned Takeaway QR would. `tenant_admin` is allowed too, for setup/preview.
router = APIRouter(prefix="/kiosk", tags=["kiosk"], dependencies=[Depends(require_tenant_scope)])


@router.post("/session", response_model=GuestSessionResponse)
async def start_or_restart_kiosk_session(
    payload: KioskSessionRequest,
    current_user: CurrentUser = Depends(require_role("kiosk", "tenant_admin")),
    db: AsyncSession = Depends(get_db),
) -> GuestSessionResponse:
    guest_session, tenant = await start_kiosk_session(
        db, current_user, payload.location_id, payload.section_id
    )
    response = await to_session_response(db, guest_session)
    await db.commit()
    response.guest_token = create_guest_token(
        guest_session_id=guest_session.id,
        tenant_id=tenant.id,
        location_id=guest_session.location_id,
        table_id=guest_session.table_id,
    )
    return response
