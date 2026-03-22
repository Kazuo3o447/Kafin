# KAFIN — Umbau-Roadmap
*Erstellt: 21. März 2026*
*Prinzip: Trading-First statt Data-First*

Das Problem in einem Satz: Kafin zeigt 40 Kennzahlen und
erwartet dass der Trader das Setup erkennt. Umgekehrt wäre
besser: Signal zuerst → Begründung → Rohdaten auf Wunsch.

---

## Phase 1 — Signal-First UX
**Priorität: HOCH | SWE-1.5 | ~1 Woche**

### P1a — Scores im Research Dashboard
**Status: ✅ ERLEDIGT (21.03.2026)**
Opportunity- und Torpedo-Score fehlen im Research-Dashboard
komplett. Nur in der Watchlist sichtbar, nur nach Audit.

Lösung:
- `api_research_dashboard` ruft `calculate_opportunity_score()` 
  und `calculate_torpedo_score()` auf
- Score-Block ganz oben im Dashboard vor allen Kennzahlen
- Format: Ampel — Opp 7.2 / Torp 3.1 / SETUP PRÜFEN
- Score-Breakdown als aufklappbares Detail (welcher Faktor wie?)
- Scores werden gecacht (600s) zusammen mit research data

✅ **Research Dashboard komplett überarbeitet (P1-P3)**
   v5.7.0 / v5.7.1 / v5.7.2

### P1b — Markets Dashboard v2
**Status: ✅ ERLEDIGT (21.03.2026)**
Granulare Echtzeit-Marktanalyse mit individuellen Refresh-Zyklen:
- 9 Datenblöcke mit separaten Refresh-Intervallen (60s/5m/10m/30m)
- Dashboard-Info Block mit Refresh-Legende (10. Block)
- Block-Header-Badges für klare Orientierung
- News + FinBERT Sentiment mit robustem Empty-State
- API-Proxy korrigiert für stabile Datenverbindung
- **Globale Indizes**: SPY, QQQ, DIA, IWM, DAX, Euro Stoxx 50, Nikkei 225, MSCI World
- **Marktbreite**: S&P 500 Top 50 statt Dow 30
- **News + FinBERT**: Kategorisierte Nachrichten mit Sentiment-Scores
- **Wirtschaftskalender**: 48h Events mit Impact-Bewertung
- **Promise.allSettled**: Robuste Parallel-Fetches
- **Timestamp-Delta**: "vor 5 min" mit Stale-Warnungen
- **BlockError**: Fallback-Komponente für API-Fehler

### P1b — Hardcoded Placeholders füllen
**Status: ✅ ERLEDIGT (21.03.2026)**
40% der Score-Gewichtung immer auf 5.0 (neutral).

Felder und echte Datenquellen:
- `sector_regime` (10%): market_overview.py liefert bereits
  11 Sektor-ETF-Performances — Sektor des Tickers vergleichen
- `guidance_trend` (15%): FMP /stable/analyst-estimates →
  EPS-Revision-Trend: rauf/runter/stabil letzte 3 Monate
- `whisper_delta` (15%): Differenz EPS-Konsens aktuell vs.
  vor 90 Tagen als Proxy (FMP estimates history)
- `leadership_instability` (10%): Finnhub News-Keywords
  "CEO" + "resign|fired|departure" letzte 90 Tage

### P1c — Firmenhintergrund integrieren
**Status: OFFEN** (nach P1b)
DeepSeek kennt nur Ticker + Company Name — kein Kontext.
FMP /stable/profile liefert kostenlos:
  CEO, Mitarbeiter, Gründung, Land, Beschreibung, Peers

Wo integrieren:
  1. Research Dashboard — neuer "Unternehmen" Block
  2. audit_report.md Prompt — Kontext-Sektion für DeepSeek
  3. Morning Briefing — CEO bei relevanten Events

---

## Phase 2 — Datenfundament stärken
**Priorität: MITTEL | SWE-1.5 | ~1 Woche** (nach Phase 1)

### P2a — TickerContext Dataclass
report_generator.py, api_research_dashboard und scoring.py
holen teils dieselben Daten unabhängig. Gemeinsames Objekt
einmal befüllen, überall übergeben. Kein Doppel-fetching.

### P2b — Earnings-Historie Fallback
**Status: ✅ ERLEDIGT (22.03.2026) v5.15.3**
FMP Mid-Cap Lücken → yfinance `ticker.earnings_history` 
als Fallback implementiert. Zusätzlich Watchlist-Earnings
Kalender im Research Dashboard.

### P2c — FinBERT Batch-Optimierung
Aktuell: sequenziell, nur Watchlist.
Ziel: asyncio.gather in Chunks, 5x schneller.
Details: docs/FUTURE.md

---

## Phase 3 — Architektur bereinigen
**Priorität: NIEDRIG | kein Trader-Mehrwert** (nach Phase 1+2)

### P3a — main.py Router-Split
3124 Zeilen → 6 Router-Dateien:
  routers/data.py, research.py, reports.py,
  watchlist.py, intelligence.py, admin.py
Reine Reorganisation, keine Logikänderung.

---

## Nicht-Ziele

- ❌ Neubau — Umbau liefert gleichwertiges Ergebnis
- ❌ Multi-User — Hobby-Projekt, ein Nutzer
- ❌ Level II Orderbook — keine kostenlose API
- ❌ Intraday-Modus — Kafka ist Swing-Trade/Earnings-Tool
- ❌ Eigene Backtesting-Engine

---

## Abgeschlossene Meilensteine (v5.x)

Vollständige Liste: STATUS.md und CHANGELOG.md

Highlights:
- ✅ Research Dashboard (5.3.0-5.3.2)
- ✅ Ticker Resolver (5.3.3)
- ✅ Extended Indicators ATR/MACD/OBV/RVOL (5.3.4-5.3.5)
- ✅ Trading Visualizations (5.3.6)
- ✅ Smart Money P/C + Yield Curve (5.3.9)
- ✅ Watchlist 55x Performance (5.3.10)

*Nächste Review: Nach Abschluss Phase 1*
