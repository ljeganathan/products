import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# Keep one event loop for the whole module (see test_db_schema.py) so the shared
# app.db.session engine's connection pool doesn't get torn down across loop boundaries.
pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_health_check() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
