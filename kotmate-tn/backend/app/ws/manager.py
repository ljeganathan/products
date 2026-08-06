import uuid
from collections import defaultdict

from fastapi import WebSocket


class LocationConnectionManager:
    """In-memory fan-out for `/ws/location/{location_id}` (Phase 08) — both the Kitchen
    Display and the POS grid (Phase 07) connect here for `kot_ticket`/`item_stock`
    messages. Single-process only (no Redis pub/sub): fine for this project's scale
    (one uvicorn worker per tenant deployment per docker-compose.yml), and a clean spot
    to swap in a shared broker later if that changes.
    """

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, location_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[location_id].add(websocket)

    def disconnect(self, location_id: uuid.UUID, websocket: WebSocket) -> None:
        self._connections[location_id].discard(websocket)
        if not self._connections[location_id]:
            del self._connections[location_id]

    async def broadcast(self, location_id: uuid.UUID, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections.get(location_id, set()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(location_id, ws)


manager = LocationConnectionManager()
