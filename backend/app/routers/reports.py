from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import Optional

from backend.app.logger import get_logger
from backend.app.memory.watchlist import get_watchlist
from backend.app.analysis.report_generator import generate_audit_report, generate_sunday_report, generate_morning_briefing, generate_after_market_report, generate_trade_review_decision
from backend.app.analysis.post_earnings_review import run_post_earnings_review
from backend.app.data.fmp import get_earnings_history
from backend.app.analysis.report_generator import _save_decision_snapshot

logger = get_logger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])

# In-Memory latest report for the mocked endpoint
_latest_report = ""

@router.post("/generate/{ticker}")
async def api_generate_report(ticker: str):
    """
    Generiert einen einzelnen Audit-Report für den angegebenen Ticker.
    Der Report wird über DeepSeek erstellt und Scores direkt zurückgegeben.
    """
    logger.info(f"[Report] Starte Audit-Report für {ticker}...")
    global _latest_report
    try:
        report_text = await generate_audit_report(ticker)
        _latest_report = report_text
        logger.info(f"[Report] Audit-Report für {ticker} erfolgreich generiert ({len(report_text)} Zeichen).")
        
        # Scores direkt aus dem Report extrahieren (ohne DB)
        scores = {"recommendation": None, "opportunity_score": None, "torpedo_score": None}
        
        # Versuche Scores aus dem Report-Text zu parsen
        try:
            import re
            # Suche nach Empfehlungsmustern
            rec_patterns = [
                r"(?:EMPFEHLUNG|RECOMMENDATION):\s*(.*?)(?:\n|$)",
                r"(?:STRONG\s+BUY|BUY|STRONG\s+SHORT|SHORT|HOLD|WATCH)",
                r"^\*?\*?(STRONG\s+BUY|BUY|STRONG\s+SHORT|SHORT|HOLD|WATCH)\*?\*?\s*[:\-]?\s*(.*?)(?:\n|$)"
            ]
            
            for pattern in rec_patterns:
                match = re.search(pattern, report_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    if "STRONG BUY" in match.group(0).upper():
                        scores["recommendation"] = "strong_buy"
                        break
                    elif "STRONG SHORT" in match.group(0).upper():
                        scores["recommendation"] = "strong_short"
                        break
                    elif "BUY" in match.group(0).upper():
                        scores["recommendation"] = "buy_hedge"
                        break
                    elif "HOLD" in match.group(0).upper() or "WATCH" in match.group(0).upper():
                        scores["recommendation"] = "hold"
                        break
            
            # Opportunity Score aus MOCK_DATA_CHECK extrahieren
            mock_check = re.search(r"OS:\s*([\d\.]+)", report_text)
            if mock_check:
                scores["opportunity_score"] = float(mock_check.group(1))
            
            # Torpedo Score aus MOCK_DATA_CHECK extrahieren  
            mock_check = re.search(r"TS:\s*([\d\.]+)", report_text)
            if mock_check:
                scores["torpedo_score"] = float(mock_check.group(1))
                
            logger.info(f"[Report] Scores aus Report extrahiert: {scores}")
            
        except Exception as e:
            logger.warning(f"[Report] Score-Extraktion fehlgeschlagen: {e}")
        
        return {"status": "success", "report": report_text, **scores}
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


@router.post("/trigger-earnings-audits")
async def api_trigger_earnings_audits():
    """
    Täglich 08:10 via n8n.
    Prüft Watchlist auf Ticker mit earnings_countdown ≤ 5.
    Generiert Audit-Report + öffnet Shadow Trade wenn noch kein
    offener Trade für diesen Ticker/Quarter existiert.
    Gibt zurück: welche Ticker verarbeitet wurden.
    """
    import asyncio

    from backend.app.analysis.shadow_portfolio import open_shadow_trade, _current_quarter
    from backend.app.db import get_supabase_client

    logger.info("[Auto-Trigger] Earnings-Audit-Check gestartet")

    wl = await get_watchlist()
    processed = []
    skipped = []
    errors = []

    db = get_supabase_client()

    for item in wl:
        ticker = (item.get("ticker") or "").upper()
        if not ticker:
            continue

        ec = item.get("earnings_countdown")
        if ec is None or ec < 0 or ec > 5:
            skipped.append({"ticker": ticker, "reason": f"earnings_countdown={ec}"})
            continue

        already_open = False
        if db:
            try:
                quarter = _current_quarter()
                existing = await (
                    db.table("shadow_trades")
                    .select("id")
                    .eq("ticker", ticker)
                    .eq("quarter", quarter)
                    .eq("status", "open")
                    .execute_async()
                )
                already_open = bool(getattr(existing, "data", None))
            except Exception as e:
                logger.warning(f"Shadow trade check {ticker}: {e}")

        if already_open:
            skipped.append({"ticker": ticker, "reason": "shadow_trade_already_open"})
            continue

        try:
            logger.info(f"[Auto-Trigger] Generiere Audit-Report: {ticker} (Earnings in {ec}T)")
            report_text = await generate_audit_report(ticker)

            if isinstance(report_text, str) and report_text.startswith("Fehler:"):
                errors.append({"ticker": ticker, "error": report_text})
                continue

            rec = None
            opp = None
            torp = None

            if db:
                try:
                    audit_row = await (
                        db.table("audit_reports")
                        .select("recommendation, opportunity_score, torpedo_score")
                        .eq("ticker", ticker)
                        .eq("report_type", "audit")
                        .order("created_at", desc=True)
                        .limit(1)
                        .execute_async()
                    )
                    latest = (audit_row.data or [{}])[0]
                    rec = latest.get("recommendation")
                    opp = latest.get("opportunity_score")
                    torp = latest.get("torpedo_score")
                except Exception as e:
                    logger.warning(f"Audit score lookup {ticker}: {e}")

            opp_val = float(opp or 0)
            torp_val = float(torp or 10)
            rec_val = str(rec or "").upper()

            # ATR für Stop-Loss berechnen
            _tech = None
            try:
                from backend.app.data.yfinance_data import get_technical_setup
                _tech = await get_technical_setup(ticker)
            except Exception:
                pass
            _atr = getattr(_tech, "atr_14", None) if _tech else None

            trade_result = None
            if rec_val in ("STRONG BUY", "BUY") and opp_val >= 6.5 and torp_val <= 4.5:
                trade_result = await open_shadow_trade(
                    ticker=ticker,
                    recommendation=rec_val,
                    opportunity_score=opp_val,
                    torpedo_score=torp_val,
                    trade_reason=f"auto_earnings_trigger_T{ec}",
                    manual_entry=False,
                    atr_14=_atr,   # NEU
                )
            elif rec_val in ("STRONG SHORT", "SHORT") and torp_val >= 6.5 and opp_val <= 4.5:
                trade_result = await open_shadow_trade(
                    ticker=ticker,
                    recommendation=rec_val,
                    opportunity_score=opp_val,
                    torpedo_score=torp_val,
                    trade_reason=f"auto_earnings_trigger_T{ec}",
                    manual_entry=False,
                    atr_14=_atr,   # NEU
                )

            processed.append({
                "ticker": ticker,
                "ec": ec,
                "rec": rec_val or None,
                "opp": opp_val,
                "torp": torp_val,
                "trade": trade_result or "skipped_no_strong_signal",
            })

        except Exception as e:
            logger.error(f"[Auto-Trigger] Fehler {ticker}: {e}")
            errors.append({"ticker": ticker, "error": str(e)})

        await asyncio.sleep(3)

    summary = {
        "processed": len(processed),
        "skipped": len(skipped),
        "errors": len(errors),
        "detail": {"processed": processed, "skipped": skipped, "errors": errors},
    }
    logger.info(
        f"[Auto-Trigger] Abgeschlossen: {summary['processed']} verarbeitet, "
        f"{summary['skipped']} übersprungen, {summary['errors']} Fehler"
    )
    return summary

@router.post("/scan-earnings-results")
async def api_scan_earnings_results():
    """Scannt nach neuen Earnings und triggert Post-Earnings-Reviews."""
    logger.info("API Call: scan-earnings-results")
    
    wl = await get_watchlist()
    reviews_triggered = []
    now = datetime.now(timezone.utc)

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

# ── After-Market Generate ──────────────────────────────────────
@router.post("/generate-after-market")
async def api_generate_after_market():
    """Generiert After-Market Report (22:15 CET Trigger)."""
    logger.info("[Report] After-Market Report generieren")
    try:
        report = await generate_after_market_report()
        return {"status": "success", "report": report}
    except Exception as e:
        logger.error(f"After-Market Report Fehler: {e}")
        return {"status": "error", "message": str(e), "report": ""}

# ── Briefing Archive (Pre + After) ────────────────────────────
@router.get("/briefing-archive")
async def api_briefing_archive(days: int = 7):
    """Letzte N Tage Pre-Market + After-Market Briefings."""
    try:
        from backend.app.database import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT date, briefing_summary, after_market_summary
                FROM daily_snapshots
                WHERE briefing_summary IS NOT NULL
                   OR after_market_summary IS NOT NULL
                ORDER BY date DESC
                LIMIT $1
            """, days)
        return {
            "reports": [
                {
                    "date":          str(r["date"]),
                    "pre_market":    r["briefing_summary"],
                    "after_market":  r["after_market_summary"],
                }
                for r in rows
            ]
        }
    except Exception as e:
        return {"reports": [], "error": str(e)}

@router.post("/review-trade/{ticker}")
async def api_review_trade(ticker: str):
    """Manueller Trade-Review-Trigger: Sendet vollständigen Kontext an DeepSeek Reasoner,
       speichert Decision Snapshot und gibt Entscheidung zurück. Keine Trade-Ausführung hier."""
    try:
        # Hole den vollständigen Research-Kontext und erzeuge Review-Entscheidung
        review_result = await generate_trade_review_decision(ticker)  # Neue oder angepasste Funktion
        
        # Speichere Decision Snapshot
        await _save_decision_snapshot(
            ticker=ticker,
            opportunity_score=review_result.get("opportunity_score", 0.0),
            torpedo_score=review_result.get("torpedo_score", 0.0),
            recommendation=review_result.get("recommendation", "unknown"),
            prompt_text=review_result.get("prompt_text", ""),
            report_text=review_result.get("decision_text", ""),
            raw_data=review_result.get("raw_data", {}),
        )
        
        return {"status": "success", "decision": review_result}
    except Exception as e:
        logger.error(f"Trade-Review für {ticker} fehlgeschlagen: {e}")
        return {"status": "error", "message": str(e)}
