import pytest
import httpx
from httpx import AsyncClient, ASGITransport

from backend.app.config import settings
from backend.app.data import fred as fred_module
from backend.app.data.fred import _fetch_fred_series, _redact_fred_url
from backend.app.main import app

@pytest.fixture(autouse=True)
def force_mock_data():
    settings.use_mock_data = True
    yield


class FakeFredClient:
    def __init__(self, failures: int, payload: dict):
        self.failures = failures
        self.payload = payload
        self.calls = 0

    async def get(self, url, params=None):
        self.calls += 1
        request = httpx.Request("GET", url, params=params)
        if self.calls <= self.failures:
            return httpx.Response(500, request=request, text="server error")
        return httpx.Response(200, request=request, json=self.payload)

@pytest.mark.asyncio
async def test_get_macro_snapshot():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/data/macro")
    assert response.status_code == 200
    data = response.json()
    assert "fed_funds_rate" in data
    assert "yield_curve" in data


def test_redact_fred_url_hides_api_key():
    url = "https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&api_key=secret-key&file_type=json"

    redacted = _redact_fred_url(url)

    assert "secret-key" not in redacted
    assert "api_key=%5Bredacted%5D" in redacted
    assert "series_id=VIXCLS" in redacted


@pytest.mark.asyncio
async def test_fetch_fred_series_retries_on_5xx(monkeypatch):
    settings.fred_api_key = "test-key"
    client = FakeFredClient(
        failures=2,
        payload={"observations": [{"value": "4.33", "date": "2026-03-07"}]},
    )
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    monkeypatch.setattr(fred_module.asyncio, "sleep", fake_sleep)

    value, obs_date = await _fetch_fred_series(client, "BAMLH0A0HYM2")

    assert value == 4.33
    assert obs_date == "2026-03-07"
    assert client.calls == 3
    assert sleep_calls == [1.0, 2.0]
