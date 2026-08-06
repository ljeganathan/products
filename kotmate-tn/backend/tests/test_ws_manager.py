import uuid

import pytest

from app.ws.manager import LocationConnectionManager

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _FakeWebSocket:
    def __init__(self, fail: bool = False) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self._fail = fail

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        if self._fail:
            raise RuntimeError("connection closed")
        self.sent.append(message)


async def test_broadcast_only_reaches_connections_for_that_location():
    manager = LocationConnectionManager()
    loc_a, loc_b = uuid.uuid4(), uuid.uuid4()
    ws_a = _FakeWebSocket()
    ws_b = _FakeWebSocket()

    await manager.connect(loc_a, ws_a)
    await manager.connect(loc_b, ws_b)
    assert ws_a.accepted and ws_b.accepted

    await manager.broadcast(loc_a, {"type": "kot_ticket", "id": "1"})
    assert ws_a.sent == [{"type": "kot_ticket", "id": "1"}]
    assert ws_b.sent == []


async def test_broadcast_drops_dead_connections_without_raising():
    manager = LocationConnectionManager()
    location_id = uuid.uuid4()
    healthy = _FakeWebSocket()
    dead = _FakeWebSocket(fail=True)

    await manager.connect(location_id, healthy)
    await manager.connect(location_id, dead)

    await manager.broadcast(location_id, {"type": "item_stock"})
    assert healthy.sent == [{"type": "item_stock"}]

    # The failed send should have pruned `dead` — a second broadcast only reaches
    # `healthy` and doesn't re-raise for the now-removed connection.
    await manager.broadcast(location_id, {"type": "item_stock"})
    assert len(healthy.sent) == 2


async def test_disconnect_removes_connection_and_cleans_up_empty_location():
    manager = LocationConnectionManager()
    location_id = uuid.uuid4()
    ws = _FakeWebSocket()
    await manager.connect(location_id, ws)

    manager.disconnect(location_id, ws)
    assert location_id not in manager._connections
