# KAFIN — Priorisierte TODO-Liste
*Letzte Aktualisierung: 22.03.2026*
*Prinzip: Trading-Mehrwert zuerst. Architektur zuletzt.*

---

## 🔴 BATCH 1 — Sofort (Daten die Trades verbessern)
- [x] Max Pain + OI-Heatmap (yfinance, kein API-Key)
- [x] Options OI pro Strike im Research Dashboard
- [x] Pre/Post-Market Kursdaten (yfinance prepost=True)
- [x] Groq → News-Extraction statt DeepSeek Chat

## 🟠 BATCH 2 — Diese Woche
- [x] Post-Earnings Kontext-Alert (Telegram)
- [x] P1c — Firmenprofil (CEO, Mitarbeiter, Peers)
- [x] FINRA Short Volume (täglich, kostenlos)
- [x] Fear & Greed Score (Frontend)
- [x] Watchlist P1 Auto-Update bei neuer Prio
- [x] DeepSeek Prompts aktualisiert (v0.3)
- [x] Prompt TODO-Platzhalter befüllt (v0.4)
- [x] Reddit Retail Sentiment Backend
- [x] Sympathy Play Radar
- [x] Shadow Trading Journal Phase A (Trade-Grund Dropdown)
- [x] Integration Layer (Reddit + Fear & Greed verbinden)
- [⛔] GEX Proxy → BLOCKIERT (Tradier API fehlt)

## 🟡 BATCH 3 — Nächste Woche
- [x] Marktbreite 5T/20T Verlauf (Supabase history)
- [x] VWAP Intraday
- [x] Options OI Chart (Heatmap)
- [ ] P2a TickerContext Dataclass (kein Trader-Mehrwert,
      aber spart API-Calls)
- [x] P2b Earnings-Historie Fallback (yfinance)
- [x] Earnings-Kalender im Research Dashboard
- [ ] 10-Q Filing RAG (Gemini Flash)
- [x] Shadow Trading Journal Phase A (Trade-Grund Dropdown)

## 🟢 BATCH 4 — Technische Schuld (wenn Zeit)
- [x] PostgreSQL + pgvector Docker Setup
- [x] DB Client Drop-in Adapter (K6-2)
- [x] Backend DB Switch (K6-3)
- [x] pgvector Embedding Pipeline (K6-4)
- [x] RAG Query Endpoint (K6-5)
- [ ] P3a main.py Router-Split (3124 Zeilen → 6 Dateien)
- [ ] SYSTEM_LOGS Cleanup (1 SQL-Statement)
- [ ] SECTOR_TO_ETF Duplikation → shared utils
- [ ] P2c FinBERT Batch-Optimierung
- [ ] Shadow Trading Journal Phase B (KI-Lernschleife)

## ❌ NICHT UMSETZEN (ohne Polygon.io Key)
- Level II Orderbook

---
*Abgearbeitete Items werden in FUTURE.md als ✅ markiert*
