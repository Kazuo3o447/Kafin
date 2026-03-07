"""
fred — Datenabruf von FRED API
"""
import httpx
import json
import os
import asyncio
from typing import Optional

from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.rate_limiter import rate_limit
from schemas.macro import MacroSnapshot

logger = get_logger(__name__)

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "fixtures", "fred")

def load_mock_data(filename: str):
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

async def _fetch_fred_series(client: httpx.AsyncClient, series_id: str) -> Optional[float]:
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={settings.fred_api_key}&sort_order=desc&limit=1&file_type=json"
    try:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        observations = data.get("observations", [])
        if observations:
            val = observations[0].get("value")
            if val and val != ".":
                return float(val)
    except Exception as e:
        logger.error(f"Error fetching FRED series {series_id}: {e}")
    return None

@rate_limit("fred")
async def get_macro_snapshot() -> MacroSnapshot:
    if settings.use_mock_data:
        try:
            data = load_mock_data("macro_snapshot.json")
            return MacroSnapshot(**data)
        except Exception:
            return MacroSnapshot(yield_curve="flat", regime="Neutral")
            
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            _fetch_fred_series(client, "FEDFUNDS"),
            _fetch_fred_series(client, "VIXCLS"),
            _fetch_fred_series(client, "BAMLH0A0HYM2"),
            _fetch_fred_series(client, "T10Y2Y"),
            _fetch_fred_series(client, "DTWEXBGS")
        )
        
    fed_funds, vix, high_yield, yield_spread, dxy = results
    
    curve_status = "flat"
    if yield_spread is not None:
        if yield_spread > 0.1:
            curve_status = "positive"
        elif yield_spread < -0.1:
            curve_status = "inverted"
            
    regime = "Neutral"
    v = vix or 20.0
    s = high_yield or 4.0
    
    if v > 25 or s > 5.0:
        regime = "Risk Off"
    elif v < 15 and s < 3.5:
        regime = "Risk On"
        
    return MacroSnapshot(
        fed_funds_rate=fed_funds,
        vix=vix,
        high_yield_spread=high_yield,
        yield_spread_10y_2y=yield_spread,
        dxy=dxy,
        yield_curve=curve_status,
        regime=regime
    )
