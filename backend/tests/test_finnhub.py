import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.config import settings

@pytest.fixture(autouse=True)
def force_mock_data():
    settings.use_mock_data = True
    yield

@pytest.mark.asyncio
async def test_get_earnings_calendar():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/data/earnings-calendar?from_date=2026-04-01&to_date=2026-04-30")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "ticker" in data[0]

@pytest.mark.asyncio
async def test_get_company_news():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/data/company/AAPL/news")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "headline" in data[0]

@pytest.mark.asyncio
async def test_get_short_interest():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/data/company/AAPL/short-interest")
    assert response.status_code == 200
    data = response.json()
    assert "short_interest" in data

@pytest.mark.asyncio
async def test_get_insiders():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/data/company/AAPL/insiders")
    assert response.status_code == 200
    data = response.json()
    assert "is_cluster_buy" in data
