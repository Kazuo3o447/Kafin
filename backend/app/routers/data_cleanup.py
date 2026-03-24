"""
Data Cleanup Router - Massenlösch-Endpunkte für einzelne Ticker
"""

from fastapi import APIRouter, HTTPException
from backend.app.logger import get_logger
from backend.app.db import get_supabase_client
from backend.app.cache import cache_invalidate_prefix

router = APIRouter()
logger = get_logger(__name__)


@router.delete("/api/data/cleanup/{ticker}")
async def cleanup_ticker_data(ticker: str):
    """
    Löscht alle Daten zu einem Ticker aus allen Tabellen.
    
    Gelöschte Tabellen:
    - audit_reports
    - decision_snapshots  
    - long_term_memory
    - short_term_memory
    - shadow_trades
    - earnings_reviews
    - performance_tracking
    - score_history
    
    Cache wird ebenfalls invalidiert.
    """
    ticker = ticker.upper().strip()
    logger.info(f"[Cleanup] Starte Daten-Aufräum für {ticker}")
    
    db = get_supabase_client()
    if not db:
        raise HTTPException(status_code=500, detail="Datenbank nicht verfügbar")
    
    cleanup_results = {}
    total_deleted = 0
    
    try:
        # 1. Audit Reports löschen
        try:
            result = await db.table("audit_reports").delete().eq("ticker", ticker).execute_async()
            deleted = len(result.data) if result.data else 0
            cleanup_results["audit_reports"] = deleted
            total_deleted += deleted
            logger.info(f"[Cleanup] {deleted} audit_reports für {ticker} gelöscht")
        except Exception as e:
            logger.error(f"[Cleanup] Fehler bei audit_reports für {ticker}: {e}")
            cleanup_results["audit_reports"] = f"Error: {e}"
        
        # 2. Decision Snapshots löschen
        try:
            result = await db.table("decision_snapshots").delete().eq("ticker", ticker).execute_async()
            deleted = len(result.data) if result.data else 0
            cleanup_results["decision_snapshots"] = deleted
            total_deleted += deleted
            logger.info(f"[Cleanup] {deleted} decision_snapshots für {ticker} gelöscht")
        except Exception as e:
            logger.error(f"[Cleanup] Fehler bei decision_snapshots für {ticker}: {e}")
            cleanup_results["decision_snapshots"] = f"Error: {e}"
        
        # 3. Long Term Memory löschen
        try:
            result = await db.table("long_term_memory").delete().eq("ticker", ticker).execute_async()
            deleted = len(result.data) if result.data else 0
            cleanup_results["long_term_memory"] = deleted
            total_deleted += deleted
            logger.info(f"[Cleanup] {deleted} long_term_memory für {ticker} gelöscht")
        except Exception as e:
            logger.error(f"[Cleanup] Fehler bei long_term_memory für {ticker}: {e}")
            cleanup_results["long_term_memory"] = f"Error: {e}"
        
        # 4. Short Term Memory löschen
        try:
            result = await db.table("short_term_memory").delete().eq("ticker", ticker).execute_async()
            deleted = len(result.data) if result.data else 0
            cleanup_results["short_term_memory"] = deleted
            total_deleted += deleted
            logger.info(f"[Cleanup] {deleted} short_term_memory für {ticker} gelöscht")
        except Exception as e:
            logger.error(f"[Cleanup] Fehler bei short_term_memory für {ticker}: {e}")
            cleanup_results["short_term_memory"] = f"Error: {e}"
        
        # 5. Shadow Trades löschen
        try:
            result = await db.table("shadow_trades").delete().eq("ticker", ticker).execute_async()
            deleted = len(result.data) if result.data else 0
            cleanup_results["shadow_trades"] = deleted
            total_deleted += deleted
            logger.info(f"[Cleanup] {deleted} shadow_trades für {ticker} gelöscht")
        except Exception as e:
            logger.error(f"[Cleanup] Fehler bei shadow_trades für {ticker}: {e}")
            cleanup_results["shadow_trades"] = f"Error: {e}"
        
        # 6. Earnings Reviews löschen
        try:
            result = await db.table("earnings_reviews").delete().eq("ticker", ticker).execute_async()
            deleted = len(result.data) if result.data else 0
            cleanup_results["earnings_reviews"] = deleted
            total_deleted += deleted
            logger.info(f"[Cleanup] {deleted} earnings_reviews für {ticker} gelöscht")
        except Exception as e:
            logger.error(f"[Cleanup] Fehler bei earnings_reviews für {ticker}: {e}")
            cleanup_results["earnings_reviews"] = f"Error: {e}"
        
        # 7. Performance Tracking löschen
        try:
            result = await db.table("performance_tracking").delete().eq("ticker", ticker).execute_async()
            deleted = len(result.data) if result.data else 0
            cleanup_results["performance_tracking"] = deleted
            total_deleted += deleted
            logger.info(f"[Cleanup] {deleted} performance_tracking für {ticker} gelöscht")
        except Exception as e:
            logger.error(f"[Cleanup] Fehler bei performance_tracking für {ticker}: {e}")
            cleanup_results["performance_tracking"] = f"Error: {e}"
        
        # 8. Score History löschen
        try:
            result = await db.table("score_history").delete().eq("ticker", ticker).execute_async()
            deleted = len(result.data) if result.data else 0
            cleanup_results["score_history"] = deleted
            total_deleted += deleted
            logger.info(f"[Cleanup] {deleted} score_history für {ticker} gelöscht")
        except Exception as e:
            logger.error(f"[Cleanup] Fehler bei score_history für {ticker}: {e}")
            cleanup_results["score_history"] = f"Error: {e}"
        
        # 9. Cache invalidieren
        try:
            await cache_invalidate_prefix(f"chart:{ticker}")
            await cache_invalidate_prefix(f"research:{ticker}")
            await cache_invalidate_prefix(f"audit:{ticker}")
            logger.info(f"[Cleanup] Cache für {ticker} invalidiert")
            cleanup_results["cache"] = "invalidated"
        except Exception as e:
            logger.error(f"[Cleanup] Fehler bei Cache-Invalidierung für {ticker}: {e}")
            cleanup_results["cache"] = f"Error: {e}"
        
        logger.info(f"[Cleanup] Daten-Aufräum für {ticker} abgeschlossen. {total_deleted} Datensätze gelöscht")
        
        return {
            "status": "success",
            "ticker": ticker,
            "total_deleted": total_deleted,
            "details": cleanup_results
        }
        
    except Exception as e:
        logger.error(f"[Cleanup] Unerwarteter Fehler für {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup fehlgeschlagen: {e}")


@router.get("/api/data/cleanup/{ticker}/preview")
async def preview_ticker_data(ticker: str):
    """
    Zeigt Vorschau wie viele Datensätze für einen Ticker existieren,
    bevor sie gelöscht werden.
    """
    ticker = ticker.upper().strip()
    
    db = get_supabase_client()
    if not db:
        raise HTTPException(status_code=500, detail="Datenbank nicht verfügbar")
    
    preview = {}
    total_records = 0
    
    tables_to_check = [
        "audit_reports",
        "decision_snapshots", 
        "long_term_memory",
        "short_term_memory",
        "shadow_trades",
        "earnings_reviews",
        "performance_tracking",
        "score_history"
    ]
    
    for table in tables_to_check:
        try:
            result = await db.table(table).select("id").eq("ticker", ticker).execute_async()
            count = len(result.data) if result.data else 0
            preview[table] = count
            total_records += count
        except Exception as e:
            logger.error(f"[Preview] Fehler bei {table} für {ticker}: {e}")
            preview[table] = f"Error: {e}"
    
    return {
        "ticker": ticker,
        "total_records": total_records,
        "tables": preview
    }
