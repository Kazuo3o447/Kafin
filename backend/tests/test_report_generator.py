import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.config import settings

@pytest.fixture(autouse=True)
def force_mock_data():
    settings.use_mock_data = True
    yield

@pytest.mark.asyncio
async def test_generate_audit_report():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/reports/generate/AAPL")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "success"
    assert "MOCK_REPORT:" in data["report"]
    assert "AAPL" in data["report"]

@pytest.mark.asyncio
async def test_generate_sunday_report():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/reports/generate-sunday")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "success"
    assert "MOCK_REPORT" in data["report"]
    assert "SUNDAY REPORT" in data["report"]
