from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.app.logger import get_logger
from backend.app.cache import cache_get, cache_set
from backend.app.analysis.shadow_portfolio import (
    get_shadow_portfolio_summary,
    get_weekly_shadow_report,
    open_shadow_trade,
)
from backend.app.db import get_supabase_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api/shadow", tags=["shadow"])

class ManualTradeRequest(BaseModel):
    ticker: str
    direction: str          # "long" | "short"
    trade_reason: str       # aus Dropdown
    opportunity_score: float = 5.0
    torpedo_score: float = 5.0
    notes: str | None = None

VALID_TRADE_REASONS = [
    "IV Mismatch",
    "Sentiment Divergenz",
    "Relative Stärke",
    "Sympathy Play",
    "Earnings Beat erwartet",
    "Torpedo erkannt",
    "Technisches Breakout",
    "Contrarian Setup",
    "Reddit vs. Insider Divergenz",
    "Max Pain Magnet",
    "Short Squeeze Setup",
]

@router.get("/portfolio")
async def api_shadow_portfolio_summary():
    cache_key = "shadow_portfolio_summary"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    result = await get_shadow_portfolio_summary()
    await cache_set(cache_key, result, ttl_seconds=120)
    return result

@router.get("/portfolio/trades")
async def api_shadow_portfolio_trades(status: str = "all"):
    try:
        db = get_supabase_client()
        if db is None:
            raise ValueError("Supabase nicht verfügbar")
        query = db.table("shadow_trades").select("*").order("created_at", desc=True)
        if status in ("open", "closed"):
            query = query.eq("status", status)
        result = await query.limit(100).execute_async()
        data = result.data or []
        return {"trades": data, "count": len(data)}
    except Exception as exc:
        return {"trades": [], "count": 0, "error": str(exc)}

@router.get("/portfolio/weekly-report")
async def api_shadow_portfolio_weekly():
    report = await get_weekly_shadow_report()
    return {"report": report}

@router.post("/manual-trade")
async def api_manual_shadow_trade(req: ManualTradeRequest):
    """Manueller Shadow-Trade mit Trade-Grund."""
    if req.trade_reason not in VALID_TRADE_REASONS:
        raise HTTPException(
            status_code=400,
            detail=f"Ungültiger Grund. Erlaubt: {VALID_TRADE_REASONS}"
        )

    rec_map = {
        "long":  "STRONG BUY",
        "short": "STRONG SELL",
    }
    ticker = req.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker darf nicht leer sein")

    direction = req.direction.strip().lower()
    if direction not in rec_map:
        raise HTTPException(
            status_code=400,
            detail="Ungültige Richtung. Erlaubt: long, short",
        )
    rec = rec_map[direction]

    result = await open_shadow_trade(
        ticker=ticker,
        recommendation=rec,
        opportunity_score=req.opportunity_score,
        torpedo_score=req.torpedo_score,
        trade_reason=req.trade_reason,
        manual_entry=True,
    )
    return result

@router.get("/trade-reasons")
async def api_trade_reasons():
    """Liste aller validen Trade-Gründe."""
    return {"reasons": VALID_TRADE_REASONS}
