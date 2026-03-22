"""
Fear & Greed Score — Composite aus 5 Indikatoren.
Alle Daten aus vorhandenen Quellen. Kein API-Key.

Skala: 0 = Extreme Fear, 100 = Extreme Greed
  0-25:  Extreme Fear
  26-45: Fear
  46-55: Neutral
  56-75: Greed
  76-100: Extreme Greed
"""
import asyncio
from backend.app.cache import cache_get, cache_set
from backend.app.logger import get_logger

logger = get_logger(__name__)


def _label(score: float) -> str:
    if score <= 25:  return "Extreme Fear"
    if score <= 45:  return "Fear"
    if score <= 55:  return "Neutral"
    if score <= 75:  return "Greed"
    return "Extreme Greed"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


async def get_fear_greed_score() -> dict:
    """
    Berechnet Fear & Greed aus 5 Komponenten:
      1. VIX (30% Gewicht)
      2. Marktbreite SMA50 (20%)
      3. Put/Call Ratio aus HYG/TLT (20%)
      4. Credit Spread (20%)
      5. Momentum SPY 5T (10%)
    """
    cache_key = "fear_greed:v1"
    cached = cache_get(cache_key)
    if cached:
        return cached

    from backend.app.data.fred import get_macro_snapshot
    from backend.app.data.market_overview import (
        get_market_breadth,
        get_intermarket_signals,
    )

    macro, breadth, intermarket = await asyncio.gather(
        get_macro_snapshot(),
        get_market_breadth(),
        get_intermarket_signals(),
        return_exceptions=True,
    )

    components: dict[str, dict] = {}
    total_weight = 0.0
    weighted_sum = 0.0

    # ── 1. VIX (30%) ──────────────────────────────
    # VIX < 12 = Extreme Greed, VIX > 35 = Extreme Fear
    vix = None
    if not isinstance(macro, Exception):
        vix = getattr(macro, "vix", None)
    if vix is not None:
        # Invertiert: niedriger VIX = hoher Score
        raw = _clamp((35 - vix) / (35 - 10) * 100, 0, 100)
        components["vix"] = {
            "value": round(vix, 1),
            "score": round(raw, 1),
            "weight": 0.30,
            "label": "VIX",
        }
        weighted_sum += raw * 0.30
        total_weight  += 0.30

    # ── 2. Marktbreite SMA50 (20%) ────────────────
    # >70% = Greed, <30% = Fear
    pct50 = None
    if not isinstance(breadth, Exception):
        pct50 = breadth.get("pct_above_sma50")
    if pct50 is not None:
        raw = _clamp(pct50, 0, 100)
        components["breadth"] = {
            "value": round(pct50, 1),
            "score": round(raw, 1),
            "weight": 0.20,
            "label": "Marktbreite SMA50",
        }
        weighted_sum += raw * 0.20
        total_weight  += 0.20

    # ── 3. Safe Haven: TLT vs SPY (20%) ──────────
    # SPY besser als TLT = Greed; TLT besser = Fear
    if not isinstance(intermarket, Exception):
        assets = intermarket.get("assets", {})
        spy = assets.get("SPY", {})
        tlt = assets.get("TLT", {})
        spy_1w = spy.get("change_1w")
        tlt_1w = tlt.get("change_1w")
        if spy_1w is not None and tlt_1w is not None:
            diff = spy_1w - tlt_1w  # -10 to +10 typical
            raw = _clamp((diff + 10) / 20 * 100, 0, 100)
            components["safe_haven"] = {
                "value": round(diff, 2),
                "score": round(raw, 1),
                "weight": 0.20,
                "label": "SPY vs TLT (1W)",
            }
            weighted_sum += raw * 0.20
            total_weight  += 0.20

    # ── 4. Credit Spread (20%) ────────────────────
    # < 3.0% = Greed, > 6.0% = Fear
    cs = None
    if not isinstance(macro, Exception):
        cs = getattr(macro, "credit_spread_bps", None)
    if cs is not None:
        cs_pct = cs / 100  # bps → %
        raw = _clamp((6.0 - cs_pct) / (6.0 - 3.0) * 100, 0, 100)
        components["credit_spread"] = {
            "value": round(cs, 0),
            "score": round(raw, 1),
            "weight": 0.20,
            "label": "Credit Spread (bps)",
        }
        weighted_sum += raw * 0.20
        total_weight  += 0.20

    # ── 5. SPY Momentum 5T (10%) ─────────────────
    # +3% = Greed, -3% = Fear
    if not isinstance(intermarket, Exception):
        assets = intermarket.get("assets", {})
        spy_5d = assets.get("SPY", {}).get("change_1w")
        if spy_5d is not None:
            raw = _clamp((spy_5d + 5) / 10 * 100, 0, 100)
            components["momentum"] = {
                "value": round(spy_5d, 2),
                "score": round(raw, 1),
                "weight": 0.10,
                "label": "SPY Momentum 5T",
            }
            weighted_sum += raw * 0.10
            total_weight  += 0.10

    # ── Composite ─────────────────────────────────
    if total_weight > 0:
        score = round(weighted_sum / total_weight, 1)
    else:
        score = 50.0  # Fallback Neutral

    result = {
        "score":      score,
        "label":      _label(score),
        "components": components,
        "coverage":   round(total_weight, 2),
    }
    cache_set(cache_key, result, ttl_seconds=1800)
    return result
