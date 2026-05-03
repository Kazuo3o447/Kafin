import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.config import settings

@pytest.fixture(autouse=True)
def force_mock_data():
    settings.use_mock_data = True
    yield

@pytest.mark.asyncio
async def test_get_profile():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/data/company/AAPL/profile")
    assert response.status_code == 200
    data = response.json()
    assert "ticker" in data

@pytest.mark.asyncio
async def test_get_estimates():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/data/company/AAPL/estimates")
    assert response.status_code == 200
    data = response.json()
    assert "eps_consensus" in data

@pytest.mark.asyncio
async def test_get_earnings_history():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/data/company/AAPL/earnings-history")
    assert response.status_code == 200
    data = response.json()
    assert "quarters_beat" in data
