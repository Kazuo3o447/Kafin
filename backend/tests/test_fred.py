import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.config import settings

@pytest.fixture(autouse=True)
def force_mock_data():
    settings.use_mock_data = True
    yield

@pytest.mark.asyncio
async def test_get_macro_snapshot():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/data/macro")
    assert response.status_code == 200
    data = response.json()
    assert "fed_funds_rate" in data
    assert "yield_curve" in data
