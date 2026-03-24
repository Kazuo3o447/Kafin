#!/usr/bin/env python3
"""
collect_audits_api — Sammelt Audits über die Backend-API

Verwendung:
    python backend/app/scripts/collect_audits_api.py
"""

import asyncio
import aiohttp
import json
from typing import List, Dict

async def collect_audits_via_api():
    """Sammelt Audits über die REST-API."""
    
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
            
            # Audit-Report generieren
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
                    
                    print(f"✅ {ticker}: Audit erfolgreich")
                    results.append({"ticker": ticker, "status": "success", "report_length": len(audit_result.get("report", ""))})
        
        except Exception as e:
            print(f"❌ {ticker}: Komplett fehlgeschlagen: {e}")
            results.append({"ticker": ticker, "status": "error", "message": str(e)})
        
        # Kurze Pause
        await asyncio.sleep(1)
    
    # Prüfen ob Snapshots gespeichert wurden
    print("\n🔍 Prüfe Decision Snapshots...")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/api/data/decision-snapshots?limit=20") as response:
            if response.status == 200:
                snapshots_data = await response.json()
                snapshot_count = snapshots_data.get("total", 0)
                print(f"📊 Gespeicherte Decision Snapshots: {snapshot_count}")
                
                if snapshot_count > 0:
                    print("📋 Snapshots:")
                    for snapshot in snapshots_data.get("snapshots", [])[:5]:
                        print(f"  - {snapshot['ticker']}: {snapshot['recommendation']} (Opp: {snapshot['opportunity_score']}, Torp: {snapshot['torpedo_score']})")
    
    # Zusammenfassung
    successful = len([r for r in results if r["status"] == "success"])
    failed = len([r for r in results if r["status"] == "error"])
    
    print(f"\n=== ZUSAMMENFASSUNG ===")
    print(f"✅ Erfolgreich: {successful}")
    print(f"❌ Fehlgeschlagen: {failed}")
    
    return results

if __name__ == "__main__":
    asyncio.run(collect_audits_via_api())
