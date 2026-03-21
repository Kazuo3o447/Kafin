"""
Score Backfill - Neu berechnen der Score-History nach P1b

Verwendung:
- POST /api/admin/scores/backfill
- Optional: ?tickers=AAPL,MSFT (sonst alle Watchlist-Ticker)
- Optional: ?days=7 (default: 7 Tage zurück)
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from typing import Optional, List
import asyncio

from backend.app.logger import get_logger
from backend.app.db import get_supabase_client
from backend.app.analysis.scoring import calculate_opportunity_score, calculate_torpedo_score
from backend.app.data.fmp import get_analyst_grades
from backend.app.data.market_overview import get_market_overview
from backend.app.data.yfinance_data import get_technical_setup, get_fundamentals_yf
from backend.app.data.fmp import get_company_profile, get_key_metrics, get_earnings_history
from backend.app.data.finnhub import get_short_interest, get_insider_transactions
from backend.app.memory.short_term import get_bullet_points
from backend.app.data.yfinance_data import get_options_metrics
from backend.app.memory.watchlist import get_watchlist

router = APIRouter()
logger = get_logger(__name__)

# Sektor zu ETF Mapping (aus scoring.py)
_SECTOR_TO_ETF = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Energy": "XLE",
    "Healthcare": "XLV",
    "Health Care": "XLV",
    "Utilities": "XLU",
    "Industrials": "XLI",
    "Communication Services": "XLC",
    "Communication": "XLC",
    "Consumer Cyclical": "XLY",
    "Consumer Discretionary": "XLY",
    "Consumer Defensive": "XLP",
    "Consumer Staples": "XLP",
    "Basic Materials": "XLB",
    "Materials": "XLB",
    "Real Estate": "XLRE",
}

@router.post("/backfill")
async def backfill_scores(
    tickers: Optional[str] = None,
    days: int = 7
):
    """
    Berechnet Score-History für angegebene Ticker neu.
    
    Args:
        tickers: Komma-separierte Liste von Ticker-Symbolen
        days: Anzahl Tage zurück für die History (default: 7)
    
    Returns:
        JSON mit Ergebnissen und Statistik
    """
    logger.info(f"Score Backfill gestartet: tickers={tickers}, days={days}")
    
    try:
        # Ticker bestimmen
        if tickers:
            ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        else:
            watchlist = await get_watchlist()
            ticker_list = [item.get("ticker", "").upper() for item in watchlist if item.get("ticker")]
        
        if not ticker_list:
            raise HTTPException(status_code=400, detail="Keine Ticker gefunden")
        
        # Daten vorladen (market_overview für alle Ticker gleich)
        market_ov = await get_market_overview()
        
        # Ergebnisse sammeln
        results = {
            "processed": 0,
            "success": 0,
            "failed": 0,
            "details": [],
            "errors": []
        }
        
        # Pro Ticker verarbeiten
        for ticker in ticker_list:
            try:
                result = await _backfill_single_ticker(ticker, days, market_ov)
                results["processed"] += 1
                if result["success"]:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                results["details"].append(result)
            except Exception as e:
                results["failed"] += 1
                error_msg = f"{ticker}: {str(e)}"
                results["errors"].append(error_msg)
                logger.error(f"Backfill Fehler für {ticker}: {e}")
        
        logger.info(f"Backfill abgeschlossen: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Backfill Prozess fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=f"Backfill fehlgeschlagen: {str(e)}")

async def _backfill_single_ticker(ticker: str, days: int, market_ov: dict) -> dict:
    """Verarbeitet einen einzelnen Ticker"""
    try:
        # Daten parallel laden
        results = await asyncio.gather(
            get_technical_setup(ticker),
            get_fundamentals_yf(ticker),
            get_company_profile(ticker),
            get_key_metrics(ticker),
            get_earnings_history(ticker, limit=8),
            get_short_interest(ticker),
            get_insider_transactions(ticker),
            get_bullet_points(ticker),
            get_options_metrics(ticker),
            get_analyst_grades(ticker),
            return_exceptions=True
        )
        
        def safe(idx):
            r = results[idx]
            return None if isinstance(r, Exception) else r
        
        tech = safe(0)
        yf_fund = safe(1)
        profile = safe(2)
        metrics = safe(3)
        history = safe(4)
        short_int = safe(5)
        insiders = safe(6)
        news_mem = safe(7) or []
        options = safe(8)
        analyst_grades = safe(9) or []
        
        # Sektor bestimmen
        sector = (
            getattr(profile, "sector", None) if profile else None
        ) or (
            (yf_fund.get("sector") if yf_fund else None)
        ) or "Unknown"
        
        # data_ctx aufbauen (wie in main.py)
        valuation_ctx = {}
        if metrics:
            valuation_ctx = metrics.dict() if hasattr(metrics, 'dict') else metrics
        elif profile:
            valuation_ctx = profile.dict() if hasattr(profile, 'dict') else profile
        elif yf_fund:
            valuation_ctx = {
                "ticker": ticker,
                "pe_ratio": yf_fund.get("pe_ratio"),
                "ps_ratio": yf_fund.get("ps_ratio"),
                "market_cap": yf_fund.get("market_cap"),
                "sector": yf_fund.get("sector"),
            }
        
        data_ctx = {
            "earnings_history": history.dict() if history else {},
            "valuation": valuation_ctx,
            "short_interest": short_int.dict() if short_int else {},
            "insider_activity": insiders.dict() if insiders else {},
            "technicals": tech.dict() if tech else {},
            "news_memory": news_mem if news_mem else [],
            "options": options.dict() if options else {},
            # NEU: für guidance_trend + deceleration
            "analyst_grades": analyst_grades or [],
            # NEU: für sector_regime
            "sector_ranking": market_ov.get("sector_ranking_5d", []) if market_ov else [],
            "ticker_sector": sector,
        }
        
        # Scores berechnen
        opp_score = await calculate_opportunity_score(ticker, data_ctx)
        torp_score = await calculate_torpedo_score(ticker, data_ctx)
        
        # In DB speichern
        db = get_supabase_client()
        if not db:
            return {"ticker": ticker, "success": False, "error": "Keine DB-Verbindung"}
        
        # Für jeden Tag in den letzten `days` Tagen einen Eintrag erstellen
        today = datetime.now().date()
        entries_created = 0
        
        for days_ago in range(days):
            date = today - timedelta(days=days_ago)
            
            # Prüfen ob Eintrag schon existiert
            existing = (
                db.table("score_history")
                .select("id")
                .eq("ticker", ticker)
                .eq("date", date.isoformat())
                .execute()
            )
            
            if existing and existing.data:
                # Eintrag überschreiben
                db.table("score_history").update({
                    "opportunity_score": opp_score.total_score,
                    "torpedo_score": torp_score.total_score,
                    "price": getattr(tech, "current_price", None) if tech else None,
                    "rsi": getattr(tech, "rsi_14", None) if tech else None,
                    "trend": getattr(tech, "trend", None) if tech else None,
                }).eq("ticker", ticker).eq("date", date.isoformat()).execute()
            else:
                # Neuer Eintrag
                db.table("score_history").insert({
                    "ticker": ticker,
                    "date": date.isoformat(),
                    "opportunity_score": opp_score.total_score,
                    "torpedo_score": torp_score.total_score,
                    "price": getattr(tech, "current_price", None) if tech else None,
                    "rsi": getattr(tech, "rsi_14", None) if tech else None,
                    "trend": getattr(tech, "trend", None) if tech else None,
                }).execute()
            
            entries_created += 1
        
        return {
            "ticker": ticker,
            "success": True,
            "entries_created": entries_created,
            "opportunity_score": opp_score.total_score,
            "torpedo_score": torp_score.total_score,
            "new_factors": {
                "whisper_delta": opp_score.whisper_delta,
                "guidance_trend": opp_score.guidance_trend,
                "sector_regime": opp_score.sector_regime,
                "guidance_deceleration": torp_score.guidance_deceleration,
                "leadership_instability": torp_score.leadership_instability,
            }
        }
        
    except Exception as e:
        return {"ticker": ticker, "success": False, "error": str(e)}
