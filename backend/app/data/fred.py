"""
fred — Datenabruf von FRED API

Input:  Keine (nutzt FRED REST API)
Output: schemas/macro.MacroSnapshot
Deps:   config.py, httpx
Config: .env → FRED_API_KEY
API:    FRED (Federal Reserve Economic Data)
"""
import httpx
import json
import os
import asyncio
from typing import Optional, Tuple

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

async def _fetch_fred_series(client: httpx.AsyncClient, series_id: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Holt den neuesten gültigen Wert einer FRED-Serie.
    Scannt bis zu 10 Werktage zurück, falls der aktuellste Wert fehlt.
    
    Returns: (value, date_string) — z.B. (4.33, "2026-03-07") oder (None, None).
    """
    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}"
        f"&api_key={settings.fred_api_key}"
        f"&sort_order=desc"
        f"&limit=10"
        f"&file_type=json"
    )
    try:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        observations = data.get("observations", [])
        
        for obs in observations:
            val = obs.get("value")
            obs_date = obs.get("date", "unbekannt")
            if val and val != ".":
                try:
                    float_val = float(val)
                    logger.info(f"FRED {series_id}: Wert {float_val} vom {obs_date}")
                    return float_val, obs_date
                except ValueError:
                    continue
                    
        logger.warning(f"FRED {series_id}: Kein gültiger Wert in den letzten 10 Einträgen gefunden.")
    except Exception as e:
        logger.error(f"FRED API Fehler für {series_id}: {e}")
    return None, None

@rate_limit("fred")
async def get_macro_snapshot() -> MacroSnapshot:
    if settings.use_mock_data:
        try:
            data = load_mock_data("macro_snapshot.json")
            return MacroSnapshot(**data)
        except Exception:
            return MacroSnapshot(yield_curve="flat", regime="Neutral")
            
    async with httpx.AsyncClient(timeout=15.0) as client:
        results = await asyncio.gather(
            _fetch_fred_series(client, "FEDFUNDS"),
            _fetch_fred_series(client, "VIXCLS"),
            _fetch_fred_series(client, "BAMLH0A0HYM2"),
            _fetch_fred_series(client, "T10Y2Y"),
            _fetch_fred_series(client, "DTWEXBGS")
        )
        
    fed_funds, fed_date = results[0]
    vix, vix_date = results[1]
    high_yield, hy_date = results[2]
    yield_spread, ys_date = results[3]
    dxy, dxy_date = results[4]
    
    # Logge Zusammenfassung
    logger.info(
        f"FRED Macro Snapshot: FedFunds={fed_funds}({fed_date}), VIX={vix}({vix_date}), "
        f"HYSpread={high_yield}({hy_date}), YieldSpread={yield_spread}({ys_date}), DXY={dxy}({dxy_date})"
    )
    
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
        fed_rate=fed_funds,
        vix=vix,
        credit_spread_bps=high_yield,
        yield_curve_10y_2y=yield_spread,
        dxy=dxy,
        yield_curve=curve_status,
        regime=regime
    )
