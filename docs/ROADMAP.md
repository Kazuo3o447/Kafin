# KAFIN — Umbau-Roadmap
*Erstellt: 21. März 2026*
*Ziel: Trading-First Architektur statt Data-First*

---

## Das Problem in einem Satz

Kafin zeigt dir 40 Kennzahlen und erwartet dass du das
Setup erkennst. Ein Trading-Tool sollte umgekehrt denken:
erst das Signal, dann die Begründung, dann die Rohdaten.

---

## Phase 1 — Signal-First UX
**Priorität: HOCH | Aufwand: ~1 Woche | Modell: SWE-1.5**
*Höchster Trader-Mehrwert, keine Architektur-Änderungen nötig*

### P1a — Scores im Research Dashboard
**Status: OFFEN**
**Problem:** Opportunity- und Torpedo-Score existieren nur
in der Watchlist, nach einem Audit-Report, für Watchlist-Ticker.
Im Research-Dashboard — der wichtigsten Seite — gibt es keine Scores.
**Lösung:** `api_research_dashboard` ruft `calculate_opportunity_score()` 
und `calculate_torpedo_score()` auf. Score-Block erscheint
ganz oben im Dashboard, VOR allen Kennzahlen.
**Format:** Großes Ampel-Element: Opp 7.2 / Torp 3.1 / Empfehlung: SETUP

### P1b — Hardcoded Placeholders füllen
**Status: OFFEN**
**Problem:** 40% der Score-Gewichtung immer neutral hardcoded.
Betroffene Felder und Lösung:
- `sector_regime` (10%): Aus `market_overview.py` — Sektor-Performance
  bereits vorhanden, fließt nur nicht in Score
- `guidance_trend` (15%): Aus FMP `/stable/analyst-estimates` —
  EPS-Revisions-Trend der letzten 3 Monate (rauf/runter/stabil)
- `whisper_delta` (15%): Approximation aus EPS-Konsens-Veränderung
  zwischen letzten beiden Quartalen als Proxy
- `leadership_instability` (10%): Aus Finnhub News-Scan auf
  Keywords "CEO", "CFO", "resignation", "fired" in letzten 90 Tagen

### P1c — Unternehmenshintergrund (FMP Free)
**Status: OFFEN**
**Problem:** DeepSeek kennt bei einem Audit-Report nur Ticker
und Company Name — kein Geschäftsmodell, kein CEO, keine Historie.
**Lösung:** FMP `/stable/profile` liefert kostenlos:
  CEO, Mitarbeiterzahl, Gründungsjahr, Land, Beschreibung (150 Wörter),
  Website, Börse, IPO-Datum, Peers-Liste
Diese Daten fließen in:
  1. Research Dashboard (neuer "Unternehmen" Block)
  2. Audit-Report Prompt (DeepSeek bekommt Kontext)
  3. Morning Briefing (CEO-Erwähnung bei Events)

---

## Phase 2 — Datenfundament stärken
**Priorität: MITTEL | Aufwand: ~1 Woche | Modell: SWE-1.5**

### P2a — Gemeinsames Datenkontext-Objekt
**Status: OFFEN**
**Problem:** `report_generator.py`, `api_research_dashboard` 
und `calculate_opportunity_score` holen teilweise dieselben
Daten unabhängig voneinander. Abweichungen möglich.
**Lösung:** `TickerContext` Dataclass — wird einmal befüllt,
an alle Module übergeben. Kein doppeltes yfinance-fetching.

### P2b — Earnings-Historie Fallback
**Status: OFFEN**
**Problem:** FMP liefert Surprise-Historie für Mid-Caps oft nicht.
yfinance `ticker.earnings_history` ist verfügbar aber ungenutzt.
**Lösung:** Fallback-Kette: FMP → yfinance earnings_history

### P2c — FinBERT Optimierung
**Status: OFFEN**
**Problem:** FinBERT läuft nur für Watchlist-Ticker, sequenziell,
ohne Sektor-Kontext. Batch-Processing würde 5x beschleunigen.
**Details:** Siehe FUTURE.md → FinBERT Optimization

---

## Phase 3 — Architektur bereinigen
**Priorität: NIEDRIG (kein Trader-Mehrwert) | Aufwand: 2 Tage**
*Erst nach Phase 1+2 angehen*

### P3a — main.py aufteilen
**Status: OFFEN**
**Problem:** 3.124 Zeilen, 68 Endpoints in einer Datei.
**Lösung:** Router-Dateien:
  - `routers/data.py` → Marktdaten-Endpoints
  - `routers/research.py` → Research-Dashboard Endpoint
  - `routers/reports.py` → Reports, Morning, Sunday
  - `routers/watchlist.py` → Watchlist CRUD
  - `routers/intelligence.py` → Web, Peer, Sentiment
  - `routers/admin.py` → Admin, Diagnostics, Logs
**Wichtig:** Funktionalität bleibt 100% identisch.
Nur Dateiorganisation ändert sich.

---

## Nicht-Ziele (bewusst ausgeschlossen)

- ❌ Kompletter Neubau — zu viel Aufwand, gleiche Ergebnisse
- ❌ Multi-User-System — Hobby-Projekt, ein Nutzer
- ❌ Level II Orderbook — keine kostenlose API verfügbar
- ❌ Intraday-Trading-Modus — Kafin ist für Swing-Trades/Earnings
- ❌ Eigene Backtesting-Engine — zu komplex für den Mehrwert

---

## Bekannte Grenzen (API-Plan bedingt)

- FMP Free: 250 Calls/Tag → Batch-Processing muss sparsam sein
- Finnhub Free: Kein Short Interest (nur yfinance Fallback)
- yfinance: PEG Ratio seit Juni 2025 kaputt (FMP als Primärquelle)
- Europäische Ticker: Deutlich weniger Daten als US-Ticker

---

## Abgeschlossene Meilensteine

- ✅ Research Dashboard /research/[ticker] (März 2026)
- ✅ Ticker Resolver für internationale Titel (März 2026)
- ✅ ATR, MACD, OBV, RVOL, SMA20 Indikatoren (März 2026)
- ✅ 52W Range Bar, Volume Profile, PEG Gauge (März 2026)
- ✅ Sentiment Divergenz Alerts (März 2026)
- ✅ Peer Earnings Monitor (März 2026)
- ✅ Smart Money: Put/Call Ratio Volumen (März 2026)
- ✅ Watchlist Performance: 127s → 2.3s (März 2026)

---

*Nächste Review: Nach Abschluss Phase 1*
*Verantwortlich: Ruben (Projektinhaber)*
