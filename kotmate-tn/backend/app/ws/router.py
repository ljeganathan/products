import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select, text

from app.core.security import JWTError, decode_token
from app.db.session import async_session_maker
from app.models import TenantLocation
from app.ws.manager import manager

router = APIRouter()


@router.websocket("/ws/location/{location_id}")
async def location_socket(
    websocket: WebSocket, location_id: uuid.UUID, token: str = Query(...)
) -> None:
    """Both the Kitchen Display and the POS grid (Phase 07) connect here for
    `kot_ticket`/`item_stock` messages, and (Phase 25) so does a guest's own order-
    status page, using its `guest` token instead of a staff `access` one. Native
    browser WebSocket can't set an Authorization header, so the token travels as a
    query param instead — validated the same way as the HTTP bearer path
    (`decode_token`), just read from a different place.
    """
    try:
        payload = decode_token(token)
    except JWTError:
        await websocket.close(code=4401)
        return
    if payload.get("type") not in ("access", "guest"):
        await websocket.close(code=4401)
        return

    tenant_id_raw = payload.get("tenant_id")
    if not tenant_id_raw:
        await websocket.close(code=4403)
        return
    tenant_id = uuid.UUID(tenant_id_raw)

    # A guest token is scoped to exactly one location (its own `location_id` claim,
    # Phase 25) — reject outright rather than silently connecting it to a different
    # location's fan-out than the one it was issued for.
    if payload.get("type") == "guest" and payload.get("location_id") != str(location_id):
        await websocket.close(code=4403)
        return

    async with async_session_maker() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_id)}
        )
        location = (
            await session.execute(
                select(TenantLocation.id).where(
                    TenantLocation.id == location_id, TenantLocation.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()
    if location is None:
        await websocket.close(code=4404)
        return

    await manager.connect(location_id, websocket)
    try:
        while True:
            # No client->server protocol — this just keeps the connection (and the
            # exception-based disconnect signal) alive. Any inbound frame is ignored.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(location_id, websocket)
