#!/usr/bin/env python3
"""
collect_audits_final — Sammelt Audits direkt aus Research-Daten

Verwendung:
    python backend/app/scripts/collect_audits_final.py
"""

import asyncio
import aiohttp
import json
from typing import List, Dict

async def collect_audits_from_research():
    """Sammelt Audits direkt aus Research-Daten und erstellt Decision Snapshots."""
    
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
            print(f"🔄 Sammle Research-Daten für {ticker}...")
            
            # Research-Daten holen
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}/api/data/research/{ticker}") as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"❌ {ticker}: Research API Fehler {response.status}: {error_text}")
                        results.append({"ticker": ticker, "status": "error", "message": f"Research API {response.status}"})
                        continue
                    
                    research_data = await response.json()
                    print(f"✅ {ticker}: Research-Daten erhalten")
            
            # Scores aus Research-Daten extrahieren
            fundamentals = research_data.get("fundamentals", {})
            technicals = research_data.get("technicals", {})
            sentiment = research_data.get("sentiment", {})
            
            # Einfache Score-Berechnung basierend auf verfügbaren Daten
            opportunity_score = 0.0
            torpedo_score = 0.0
            
            # Opportunity Score Faktoren
            if fundamentals.get("pe_ratio") and fundamentals["pe_ratio"] < 20:
                opportunity_score += 2.0
            if technicals.get("rsi_14") and technicals["rsi_14"] < 35:
                opportunity_score += 1.5
            if sentiment.get("overall") == "bullish":
                opportunity_score += 1.0
            
            # Torpedo Score Faktoren
            if fundamentals.get("pe_ratio") and fundamentals["pe_ratio"] > 30:
                torpedo_score += 2.0
            if technicals.get("rsi_14") and technicals["rsi_14"] > 70:
                torpedo_score += 1.5
            if sentiment.get("overall") == "bearish":
                torpedo_score += 1.0
            
            # Empfehlung basierend auf Scores
            if opportunity_score >= 3.0 and torpedo_score <= 1.0:
                recommendation = "buy"
            elif opportunity_score >= 2.0 and torpedo_score <= 2.0:
                recommendation = "hold"
            elif torpedo_score >= 3.0:
                recommendation = "short"
            else:
                recommendation = "hold"
            
            print(f"📊 {ticker}: Opp={opportunity_score:.1f}, Torp={torpedo_score:.1f}, Rec={recommendation}")
            
            # Decision Snapshot erstellen
            snapshot_payload = {
                "ticker": ticker,
                "opportunity_score": opportunity_score,
                "torpedo_score": torpedo_score,
                "recommendation": recommendation,
                "prompt_text": f"Research-based audit for {ticker}",
                "report_text": f"Research-based analysis for {ticker}. Company: {research_data.get('company_name')}. Sector: {research_data.get('sector')}. Price: ${research_data.get('price')}. Opportunity Score: {opportunity_score:.1f}. Torpedo Score: {torpedo_score:.1f}. Recommendation: {recommendation}.",
                "model_used": "research-data",
                "trade_type": "momentum",
                "data_quality_flag": "good",
                "price_at_decision": research_data.get("price"),
                "rsi_at_decision": technicals.get("rsi_14"),
                "macro_regime": "unknown",
                "vix": None
            }
            
            # Versuche, den Snapshot zu speichern (wenn der Endpunkt verfügbar ist)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{base_url}/api/data/decision-snapshots",
                        json=snapshot_payload,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        if response.status == 200:
                            snapshot_result = await response.json()
                            if snapshot_result.get("success"):
                                print(f"💾 {ticker}: Decision Snapshot gespeichert")
                                results.append({
                                    "ticker": ticker, 
                                    "status": "success", 
                                    "opp_score": opportunity_score,
                                    "torp_score": torpedo_score,
                                    "recommendation": recommendation
                                })
                            else:
                                print(f"⚠️ {ticker}: Snapshot Speichern fehlgeschlagen")
                                results.append({"ticker": ticker, "status": "partial", "message": "Snapshot save failed"})
                        else:
                            print(f"⚠️ {ticker}: Snapshot Endpunkt nicht verfügbar (Status {response.status})")
                            results.append({"ticker": ticker, "status": "partial", "message": "Snapshot endpoint unavailable"})
            except Exception as e:
                print(f"⚠️ {ticker}: Snapshot Fehler: {e}")
                results.append({"ticker": ticker, "status": "partial", "message": str(e)})
        
        except Exception as e:
            print(f"❌ {ticker}: Komplett fehlgeschlagen: {e}")
            results.append({"ticker": ticker, "status": "error", "message": str(e)})
        
        # Kurze Pause
        await asyncio.sleep(0.5)
    
    # Zusammenfassung
    successful = len([r for r in results if r["status"] == "success"])
    partial = len([r for r in results if r["status"] == "partial"])
    failed = len([r for r in results if r["status"] == "error"])
    
    print(f"\n=== ZUSAMMENFASSUNG ===")
    print(f"✅ Vollständig erfolgreich: {successful}")
    print(f"⚠️  Teilweise erfolgreich: {partial}")
    print(f"❌ Fehlgeschlagen: {failed}")
    
    # Score-Verteilung
    all_successful = [r for r in results if r["status"] == "success"]
    if all_successful:
        opp_scores = [r["opp_score"] for r in all_successful]
        torp_scores = [r["torp_score"] for r in all_successful]
        print(f"\n📈 Score-Verteilung:")
        print(f"   Opportunity: {min(opp_scores):.1f} - {max(opp_scores):.1f} (Ø {sum(opp_scores)/len(opp_scores):.1f})")
        print(f"   Torpedo: {min(torp_scores):.1f} - {max(torp_scores):.1f} (Ø {sum(torp_scores)/len(torp_scores):.1f})")
        
        print(f"\n📋 Gesammelte Daten:")
        for r in all_successful:
            print(f"   {r['ticker']}: {r['recommendation']} (Opp: {r['opp_score']:.1f}, Torp: {r['torp_score']:.1f})")
    
    return results

if __name__ == "__main__":
    asyncio.run(collect_audits_from_research())
