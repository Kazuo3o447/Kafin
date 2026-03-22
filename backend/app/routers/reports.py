from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Optional

from backend.app.logger import get_logger
from backend.app.memory.watchlist import get_watchlist
from backend.app.analysis.report_generator import generate_audit_report, generate_sunday_report, generate_morning_briefing
from backend.app.analysis.post_earnings_review import run_post_earnings_review
from backend.app.data.fmp import get_earnings_history

logger = get_logger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])

# In-Memory latest report for the mocked endpoint
_latest_report = ""

@router.post("/generate/{ticker}")
async def api_generate_report(ticker: str):
    """
    Generiert einen einzelnen Audit-Report für den angegebenen Ticker.
    Der Report wird über DeepSeek erstellt und im Arbeitsspeicher gespeichert.
    """
    logger.info(f"[Report] Starte Audit-Report für {ticker}...")
    global _latest_report
    try:
        report_text = await generate_audit_report(ticker)
        _latest_report = report_text
        logger.info(f"[Report] Audit-Report für {ticker} erfolgreich generiert ({len(report_text)} Zeichen).")
        return {"status": "success", "report": report_text}
    except Exception as e:
        logger.error(f"[Report] Fehler beim Generieren des Audit-Reports für {ticker}: {e}")
        return {"status": "error", "message": str(e)}

@router.post("/generate-sunday")
async def api_generate_sunday_report():
    """
    Erstellt den wöchentlichen Sonntags-Report und schickt ihn via Telegram.
    """
    logger.info("[SundayReport] Starte wöchentlichen Sonntags-Report...")
    
    wl = await get_watchlist()
    tickers = [item["ticker"] for item in wl]
    logger.info(f"[SundayReport] Watchlist geladen. {len(tickers)} Ticker: {tickers}")
    
    global _latest_report
    
    try:
        report_text = await generate_sunday_report(tickers)
        _latest_report = report_text
        logger.info(f"[SundayReport] Report generiert. Größe: {len(report_text)} Zeichen.")
    except Exception as e:
        logger.error(f"[SundayReport] Fehler beim Generieren des Reports: {e}")
        return {"status": "error", "message": str(e)}

    # TELEGRAM-VERSAND
    try:
        from backend.app.alerts.telegram import send_telegram_alert
        
        MAX_CHUNK = 4000
        chunks = [report_text[i:i+MAX_CHUNK] for i in range(0, len(report_text), MAX_CHUNK)]
        
        logger.info(f"[SundayReport] Sende Report via Telegram ({len(chunks)} Nachrichten)...")
        for idx, chunk in enumerate(chunks):
            prefix = f"📊 <b>KAFIN SUNDAY REPORT</b> ({idx+1}/{len(chunks)})\n\n" if idx == 0 else f"<b>[Fortsetzung {idx+1}/{len(chunks)}]</b>\n\n"
            success = await send_telegram_alert(prefix + chunk)
            if not success:
                logger.warning(f"[SundayReport] Telegram-Versand Chunk {idx+1} fehlgeschlagen.")
        
        logger.info("[SundayReport] Telegram-Versand abgeschlossen.")
    except Exception as e:
        logger.error(f"[SundayReport] Telegram-Versand fehlgeschlagen: {e}")
        
    return {"status": "success", "report": report_text}

@router.post("/generate-morning")
async def api_generate_morning_briefing():
    """Generiert das tägliche Morning Briefing."""
    logger.info("[MorningBriefing] Starte Morning Briefing...")
    global _latest_report
    try:
        report = await generate_morning_briefing()
        _latest_report = report
        logger.info(f"[MorningBriefing] Briefing generiert. Größe: {len(report)} Zeichen.")
    except Exception as e:
        logger.error(f"[MorningBriefing] Fehler: {e}")
        return {"status": "error", "message": str(e)}

    # Per Telegram senden
    try:
        from backend.app.alerts.telegram import send_telegram_alert

        MAX_CHUNK = 4000
        chunks = [report[i:i+MAX_CHUNK] for i in range(0, len(report), MAX_CHUNK)]
        logger.info(f"[MorningBriefing] Sende via Telegram ({len(chunks)} Nachrichten)...")
        for idx, chunk in enumerate(chunks):
            prefix = f"📊 <b>KAFIN MORNING BRIEFING</b> ({idx+1}/{len(chunks)})\n\n" if idx == 0 else f"<b>[Fortsetzung {idx+1}/{len(chunks)}]</b>\n\n"
            await send_telegram_alert(prefix + chunk)
        logger.info("[MorningBriefing] Telegram-Versand abgeschlossen.")
    except Exception as e:
        logger.error(f"[MorningBriefing] Telegram-Versand fehlgeschlagen: {e}")

    return {"status": "success", "report": report}

@router.get("/latest")
async def api_get_latest_report():
    logger.info("[Report] API Call: get-latest-report")
    return {"report": _latest_report}

@router.post("/post-earnings-review/{ticker}")
async def api_post_earnings_review(ticker: str, quarter: str | None = None):
    """Führt einen Post-Earnings-Review für einen Ticker durch."""
    logger.info(f"API Call: post-earnings-review for {ticker}")
    review = await run_post_earnings_review(ticker, quarter)
    return {"status": "success", "review": review}

@router.get("/morning-archive")
async def api_morning_archive(days: int = 7):
    """Letzte N Morning Briefings aus daily_snapshots."""
    try:
        from backend.app.database import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT date, briefing_summary
                FROM daily_snapshots
                WHERE briefing_summary IS NOT NULL
                ORDER BY date DESC
                LIMIT $1
            """, days)
        return {
            "reports": [
                {
                    "date":   str(r["date"]),
                    "report": r["briefing_summary"],
                }
                for r in rows
            ]
        }
    except Exception as e:
        return {"reports": [], "error": str(e)}

@router.post("/scan-earnings-results")
async def api_scan_earnings_results():
    """Scannt nach neuen Earnings und triggert Post-Earnings-Reviews."""
    logger.info("API Call: scan-earnings-results")
    
    wl = await get_watchlist()
    reviews_triggered = []
    now = datetime.utcnow()

    for item in wl:
        ticker = item.get("ticker")
        if not ticker:
            continue
        try:
            history = await get_earnings_history(ticker, limit=1)
            if history and history.last_quarter:
                earnings_date = getattr(history.last_quarter, "earnings_date", None)
                if isinstance(earnings_date, datetime):
                    if earnings_date.tzinfo is None:
                        from datetime import timezone as _tz
                        earnings_date = earnings_date.replace(tzinfo=_tz.utc)
                    from datetime import timezone as _tz
                    now = datetime.now(_tz.utc)
                    days_ago = abs((now - earnings_date).days)
                    if days_ago <= 3:
                        result = await run_post_earnings_review(ticker)
                        reviews_triggered.append({"ticker": ticker, "result": result})
                        logger.info(f"Post-Earnings Review getriggert für {ticker}")
                        
                        # Peer-Reaktions-Alert wenn Kursreaktion bekannt
                        try:
                            if isinstance(result, dict):
                                reaction = result.get("reaction_1d")
                                if reaction is not None and abs(float(reaction)) >= 2.0:
                                    from backend.app.analysis.peer_monitor import (
                                        send_peer_reaction_alert,
                                    )
                                    await send_peer_reaction_alert(
                                        reporter=ticker,
                                        move_pct=float(reaction),
                                        report_timing="after_hours",
                                    )
                        except Exception as e:
                            logger.debug(f"Peer Reaction Auto-Alert {ticker}: {e}")
        except Exception as e:
            logger.debug(f"Earnings-Scan für {ticker}: {e}")

    return {
        "status": "success",
        "reviews_triggered": len(reviews_triggered),
        "details": reviews_triggered,
    }
