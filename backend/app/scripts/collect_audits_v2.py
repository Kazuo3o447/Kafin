#!/usr/bin/env python3
"""
collect_audits_v2 — Sammelt Audits und speichert Decision Snapshots manuell

Verwendung:
    python backend/app/scripts/collect_audits_v2.py
"""

import asyncio
import aiohttp
import json
import re
from typing import List, Dict

def extract_scores_from_report(report_text: str) -> tuple:
    """Extrahiert Opportunity und Torpedo Scores aus dem Audit-Report."""
    
    opportunity_score = 0.0
    torpedo_score = 0.0
    recommendation = "hold"
    
    # Opportunity Score suchen
    opp_match = re.search(r'Opportunity[^0-9]*([0-9.]+)', report_text, re.IGNORECASE)
    if opp_match:
        try:
            opportunity_score = float(opp_match.group(1))
        except:
            pass
    
    # Torpedo Score suchen
    torp_match = re.search(r'Torpedo[^0-9]*([0-9.]+)', report_text, re.IGNORECASE)
    if torp_match:
        try:
            torpedo_score = float(torp_match.group(1))
        except:
            pass
    
    # Empfehlung extrahieren
    if re.search(r'STRONG BUY|BUY.*LONG', report_text, re.IGNORECASE):
        recommendation = "strong_buy"
    elif re.search(r'BUY|LONG', report_text, re.IGNORECASE):
        recommendation = "buy"
    elif re.search(r'STRONG SHORT|SHORT.*PUT', report_text, re.IGNORECASE):
        recommendation = "strong_short"
    elif re.search(r'SHORT|PUT', report_text, re.IGNORECASE):
        recommendation = "short"
    elif re.search(r'HOLD|WATCH|NEUTRAL', report_text, re.IGNORECASE):
        recommendation = "hold"
    
    return opportunity_score, torpedo_score, recommendation

async def collect_audits_with_manual_snapshots():
    """Sammelt Audits und speichert Decision Snapshots manuell."""
    
    base_url = "http://localhost:8002"
    
    # Watchlist-Ticker holen
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{base_url}/api/watchlist/enriched") as response:
                if response.status != 200:
                    print(f"❌ Watchlist API Fehler: {response.status}")
                    return []
                
                wl_data = await response.json()
                tickers = [item["ticker"] for item in wl_data.get("watchlist", []) if item.get("is_active", True)]
                
        except Exception as e:
            print(f"❌ Watchlist Abruf fehlgeschlagen: {e}")
            return []
    
    print(f"Starte Audit-Sammlung für {len(tickers)} Ticker: {tickers}")
    
    results = []
    
    for ticker in tickers:
        try:
            print(f"🔄 Generiere Audit für {ticker}...")
            
            # 1. Audit-Report generieren
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{base_url}/api/reports/generate/{ticker}") as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"❌ {ticker}: Audit API Fehler {response.status}: {error_text}")
                        results.append({"ticker": ticker, "status": "error", "message": f"API {response.status}"})
                        continue
                    
                    audit_result = await response.json()
                    
                    if audit_result.get("status") != "success":
                        print(f"❌ {ticker}: Audit Generierung fehlgeschlagen: {audit_result.get('message')}")
                        results.append({"ticker": ticker, "status": "error", "message": audit_result.get("message")})
                        continue
                    
                    report_text = audit_result.get("report", "")
                    print(f"✅ {ticker}: Audit erfolgreich ({len(report_text)} Zeichen)")
            
            # 2. Scores extrahieren
            opp_score, torp_score, recommendation = extract_scores_from_report(report_text)
            print(f"📊 {ticker}: Opp={opp_score}, Torp={torp_score}, Rec={recommendation}")
            
            # 3. Decision Snapshot manuell speichern
            snapshot_payload = {
                "ticker": ticker,
                "opportunity_score": opp_score,
                "torpedo_score": torp_score,
                "recommendation": recommendation,
                "prompt_text": f"Auto-generated audit for {ticker}",
                "report_text": report_text[:10000],  # Kürzen für DB
                "model_used": "deepseek-reasoner",
                "trade_type": "momentum",  # Standard, kann später angepasst werden
                "data_quality_flag": "good"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/api/data/decision-snapshots",
                    json=snapshot_payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 200:
                        snapshot_result = await response.json()
                        if snapshot_result.get("success"):
                            print(f"💾 {ticker}: Decision Snapshot gespeichert (ID: {snapshot_result.get('id')})")
                            results.append({
                                "ticker": ticker, 
                                "status": "success", 
                                "snapshot_id": snapshot_result.get("id"),
                                "opp_score": opp_score,
                                "torp_score": torp_score,
                                "recommendation": recommendation
                            })
                        else:
                            print(f"❌ {ticker}: Snapshot Speichern fehlgeschlagen")
                            results.append({"ticker": ticker, "status": "partial", "message": "Snapshot failed"})
                    else:
                        error_text = await response.text()
                        print(f"❌ {ticker}: Snapshot API Fehler {response.status}: {error_text}")
                        results.append({"ticker": ticker, "status": "partial", "message": f"Snapshot API {response.status}"})
        
        except Exception as e:
            print(f"❌ {ticker}: Komplett fehlgeschlagen: {e}")
            results.append({"ticker": ticker, "status": "error", "message": str(e)})
        
        # Kurze Pause
        await asyncio.sleep(1)
    
    # Final Check: Alle Snapshots zählen
    print("\n🔍 Final Check Decision Snapshots...")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/api/data/decision-snapshots?limit=50") as response:
            if response.status == 200:
                snapshots_data = await response.json()
                snapshot_count = snapshots_data.get("total", 0)
                print(f"📊 Gespeicherte Decision Snapshots: {snapshot_count}")
                
                if snapshot_count > 0:
                    print("📋 Aktuelle Snapshots:")
                    for snapshot in snapshots_data.get("snapshots", [])[:10]:
                        print(f"  - {snapshot['ticker']}: {snapshot['recommendation']} (Opp: {snapshot['opportunity_score']}, Torp: {snapshot['torpedo_score']})")
    
    # Zusammenfassung
    successful = len([r for r in results if r["status"] == "success"])
    partial = len([r for r in results if r["status"] == "partial"])
    failed = len([r for r in results if r["status"] == "error"])
    
    print(f"\n=== ZUSAMMENFASSUNG ===")
    print(f"✅ Vollständig erfolgreich: {successful}")
    print(f"⚠️  Teilweise erfolgreich: {partial}")
    print(f"❌ Fehlgeschlagen: {failed}")
    
    # Score-Verteilung
    if successful > 0:
        opp_scores = [r["opp_score"] for r in results if r["status"] == "success"]
        torp_scores = [r["torp_score"] for r in results if r["status"] == "success"]
        print(f"\n📈 Score-Verteilung:")
        print(f"   Opportunity: {min(opp_scores):.1f} - {max(opp_scores):.1f} (Ø {sum(opp_scores)/len(opp_scores):.1f})")
        print(f"   Torpedo: {min(torp_scores):.1f} - {max(torp_scores):.1f} (Ø {sum(torp_scores)/len(torp_scores):.1f})")
    
    return results

if __name__ == "__main__":
    asyncio.run(collect_audits_with_manual_snapshots())
