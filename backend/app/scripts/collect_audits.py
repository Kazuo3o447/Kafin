#!/usr/bin/env python3
"""
collect_audits — Skript zum systematischen Sammeln von Audit-Reports
für die Kalibrierungs-Baseline

Verwendung:
    python -m backend.app.scripts.collect_audits

Erzeugt Audit-Reports für alle aktiven Watchlist-Ticker und speichert
Decision Snapshots für die spätere Kalibrierung.
"""

import asyncio
import sys
from pathlib import Path

# Backend-Path hinzufügen
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.app.memory.watchlist import get_watchlist
from backend.app.analysis.report_generator import generate_audit_report, _save_decision_snapshot
from backend.app.logger import get_logger

logger = get_logger(__name__)

async def collect_audits_for_watchlist():
    """Sammelt Audits für alle aktiven Watchlist-Ticker."""
    
    # Watchlist laden
    wl = await get_watchlist()
    active_tickers = [item["ticker"] for item in wl if item.get("is_active", True)]
    
    logger.info(f"Starte Audit-Sammlung für {len(active_tickers)} Ticker: {active_tickers}")
    
    results = []
    
    for ticker in active_tickers:
        try:
            logger.info(f"Generiere Audit für {ticker}...")
            
            # Audit-Report generieren
            report_text = await generate_audit_report(ticker)
            
            if report_text.startswith("Fehler:"):
                logger.error(f"Audit für {ticker} fehlgeschlagen: {report_text}")
                results.append({"ticker": ticker, "status": "error", "message": report_text})
                continue
            
            # Decision Snapshot manuell speichern
            # Wir extrahieren die Scores aus dem Report-Text, da wir direkten Zugriff haben
            opportunity_score = 0.0
            torpedo_score = 0.0
            recommendation = "unknown"
            
            # Einfache Text-Extraktion der Scores
            lines = report_text.split('\n')
            for line in lines:
                if "Opportunity Score:" in line:
                    try:
                        opportunity_score = float(line.split(":")[-1].strip().split()[0])
                    except:
                        pass
                elif "Torpedo Score:" in line:
                    try:
                        torpedo_score = float(line.split(":")[-1].strip().split()[0])
                    except:
                        pass
                elif "EMPFEHLUNG" in line:
                    if "BUY" in line.upper():
                        recommendation = "buy"
                    elif "SHORT" in line.upper():
                        recommendation = "short"
                    elif "HOLD" in line.upper():
                        recommendation = "hold"
            
            # Snapshot speichern
            snapshot_result = await _save_decision_snapshot(
                ticker=ticker,
                opportunity_score=opportunity_score,
                torpedo_score=torpedo_score,
                recommendation=recommendation,
                prompt_text="Auto-generated via collect_audits.py",
                report_text=report_text,
                raw_data={"collection_method": "batch_script"}
            )
            
            if snapshot_result.get("success"):
                logger.info(f"✅ {ticker}: Audit + Snapshot gespeichert")
                results.append({"ticker": ticker, "status": "success", "snapshot_id": snapshot_result.get("id")})
            else:
                logger.error(f"❌ {ticker}: Audit OK, aber Snapshot fehlgeschlagen: {snapshot_result.get('reason')}")
                results.append({"ticker": ticker, "status": "partial", "reason": snapshot_result.get('reason')})
            
        except Exception as e:
            logger.error(f"❌ {ticker}: Komplett fehlgeschlagen: {e}")
            results.append({"ticker": ticker, "status": "error", "message": str(e)})
        
        # Kurze Pause zwischen Ticker
        await asyncio.sleep(1)
    
    # Zusammenfassung
    successful = len([r for r in results if r["status"] == "success"])
    partial = len([r for r in results if r["status"] == "partial"])
    failed = len([r for r in results if r["status"] == "error"])
    
    logger.info(f"\n=== AUDIT-SAMMLUNG ABGESCHLOSSEN ===")
    logger.info(f"Erfolgreich: {successful}")
    logger.info("Teilweise erfolgreich (Audit OK, Snapshot fehlgeschlagen): {partial}")
    logger.info(f"Fehlgeschlagen: {failed}")
    
    for result in results:
        if result["status"] != "success":
            logger.warning(f"{result['ticker']}: {result['status']} - {result.get('message', result.get('reason', 'Unknown'))}")
    
    return results

if __name__ == "__main__":
    asyncio.run(collect_audits_for_watchlist())
