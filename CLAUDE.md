# KAFIN — CLAUDE.md

## ⚠️ Wichtige Fallstricke (zuerst lesen)

### Ports
- Backend extern: **http://localhost:8002** (NICHT 8000!)
- Docker intern: http://kafin-backend:8000
- Frontend: http://localhost:3000

### Datenbank
- Es gibt **kein Supabase mehr** — nur lokales PostgreSQL 16
- `get_supabase_client()` = Compatibility-Shim → gibt PostgreSQL-Client
- Echter Container: `kafin-postgres` 

### Kritische Bugs (gefixt in v7.8.0, aber Kontext wichtig)
- Shadow Trades öffneten sich nie: TRADE_SIGNALS erwartete "STRONG BUY"
  aber scoring.py lieferte "strong_buy" — gefixt durch beide Formate
- News erschienen nie im Research: bullet_points ≠ bullet_text — gefixt
- 4 n8n-Workflows zeigten auf http://api:8000 (existiert nicht) — gefixt

### Sunday Report
- **DEPRECATED** seit v7.0 — durch Pre/After-Market Briefing ersetzt
- Endpoint bleibt als Fallback, Workflow wird nicht mehr deployt

### Journal
- `/journal` leitet weiter auf `/performance?tab=my_trades` 
- Echte Tabelle: `real_trades` (nicht `trade_journal`)

### Bot-Referenz
- `bot.md` ist die kanonische Beschreibung des Trading-Bots: Datenquellen, Scoring, Review-Flow, Snapshot-/Learning-Kurve und Explainability.
- **Aktueller Modus**: Audit-Sammlung & Baseline-Phase — der Bot sammelt Decision Snapshots, bevor Gewichtungen kalibriert werden.
- Wenn du den Bot änderst, halte `bot.md`, `STATUS.md`, `CHANGELOG.md` und `FUTURE.md` synchron.

## Kafin — KI-gestützte Earnings-Trading-Plattform

## Was ist Kafin?
Eine Plattform, die Finanzdaten sammelt, mit einer KI-Kaskade analysiert und wöchentliche Audit-Reports mit Handlungsempfehlungen für Aktien-Earnings und Bitcoin generiert. Der Trader entscheidet — Kafin empfiehlt.

## Architektur
- Backend: Python FastAPI auf NUC (ZimaOS + Docker)
- Datenbank: PostgreSQL 16 + pgvector (lokal)
- Frontend: Next.js (lokal mit Docker)
- KI: FinBERT (lokal) → DeepSeek API → Groq API
- Alerts: Telegram Bot + E-Mail via n8n
- Bitcoin: CoinGlass API für Derivate-Daten

## Datenquellen (kostenlos + unlimitiert)
- **FMP**: Finanzkennzahlen, Earnings, Analyst-Grades
- **Finnhub**: News, Short Interest, Insider-Transaktionen  
- **yfinance**: Kursdaten, technische Indikatoren, Fallback Earnings
- **Twelve Data**: ADX, Stochastic, IV Percentile (Free Tier: 800/Tag)
- **FRED**: Makro-Daten (VIX, Yield Curve, Fed Funds, Consumer Sentiment)
- **Reddit Monitor**: Retail Sentiment (gecacht 1h)
- **Fear & Greed Index**: CNN Money Makro-Kontext
- **FINRA**: Short Volume Ratio (täglich)
- **Tavily**: Web-Enrichment Fallback (Budget-kontrolliert)

## AI-Modell-Stack (festgelegt — Stand März 2026)

Kafin verwendet ausschließlich folgende Modelle:

| Aufgabe                        | Modell                  | API        |
|-------------------------------|-------------------------|------------|
| Report-Generierung (komplex)  | deepseek-reasoner       | DeepSeek   |
| Chat / Kurzanalysen           | deepseek-chat           | DeepSeek   |
| News-Extraktion (schnell)     | llama-3.1-8b-instant    | Groq       |

**Nicht mehr verwendet / explizit ausgeschlossen:**
- ~~Kimi / moonshot-v1~~ — entfernt, kein aktiver API-Key, kein Use-Case
- Keine Broad-Index-Shorts (SH, PSQ, SQQQ) als Empfehlung

Fallback-Kaskade:
1. Groq (kostenlos, schnell) → für News-Extraktion
2. DeepSeek Chat → für mittlere Analysen
3. DeepSeek Reasoner → für vollständige Audit-Reports

Frontier-Fallback (manuell): nur wenn DeepSeek API down ist,
temporär auf einen anderen Provider wechseln. Nie fest verdrahten.

## Regeln für Agenten

### Bevor du arbeitest
1. Lies die README.md im Modulordner, an dem du arbeitest
2. Lies die relevanten Schemas in schemas/
3. Lies die API-Docs in docs/apis/ wenn du eine externe API nutzt
4. Prüfe STATUS.md ob abhängige Module fertig sind
5. Lies `bot.md`, wenn du an Scoring, Review-Flow, Decision-Snapshots oder Datenquellen arbeitest

### Code-Konventionen
- Python 3.11+, Type Hints überall
- Naming: snake_case für Variablen/Funktionen, PascalCase für Klassen
- Kommentare und Docs: Deutsch
- Code und Variablen: Englisch
- HTTP-Client: httpx (nicht requests, nicht aiohttp)
- Schemas: Pydantic v2 Models aus schemas/
- Datenbank: PostgreSQL 16 via Compatibility-Shim aus `backend/app/db.py` (`get_supabase_client()` → lokaler DB-Client)
- Config: Alles aus config/ laden, nie hardcoden
- Secrets: Aus Environment-Variablen via backend/app/config.py, NIE im Code
- Nutze NUR Bibliotheken aus requirements.txt

### Datei-Header
Jede .py-Datei beginnt mit:
"""
[Modulname] — [Kurzbeschreibung]

Input:  [Was kommt rein? Welches Schema?]
Output: [Was kommt raus? Welches Schema?]
Deps:   [Welche anderen Module werden genutzt?]
Config: [Welche Config-Werte werden gelesen?]
API:    [Welche externe API? Oder "Keine"]
"""

### Error-Handling
- Jeder externe API-Call in try/except
- Bei Fehler: logger.error() mit Kontext (API, Ticker, Endpoint)
- Rate-Limit-Fehler: Retry mit Backoff via zentralen Rate-Limiter
- Fehlende Daten: None zurückgeben + loggen, nie stilles Verschlucken

### Mock-Daten
- Prüfe config/settings.yaml → use_mock_data: true/false
- Wenn true: Lade aus fixtures/ statt echte API-Calls
- Jedes Daten-Modul MUSS beide Pfade unterstützen

### Tests
- Jedes Modul bekommt test_[modul].py
- Mindestens ein Smoke-Test gegen Mock-Daten
- Tests nutzen IMMER Mock-Daten

## Verzeichnisstruktur
docs/           → Spezifikation, API-Docs
config/         → YAML-Dateien für konfigurierbare Werte
schemas/        → Pydantic Models als Verträge zwischen Modulen
prompts/        → KI-Prompts als Markdown, versioniert
fixtures/       → Mock-Daten (echte API-Responses als JSON)
backend/app/    → FastAPI-Anwendung
backend/app/data/       → Daten-Module (eine Datei pro API)
backend/app/analysis/   → KI-Kaskade + Scoring + Report-Generator
backend/app/memory/     → Gedächtnis-System (PostgreSQL CRUD via Compatibility-Shim)
backend/app/alerts/     → Telegram + E-Mail
database/       → SQL-Schema-Definitionen
tests/          → Test-Dateien

## Neue Routers (v6.4.0)
- `routers/journal.py` — Trade-Journal CRUD
- `routers/data.py` — Signal Feed (`/api/data/signals/feed`, `/api/data/signal-feed-config`)
- `routers/reports.py` — Pre/After-Market Briefing (`/api/reports/generate-after-market`, `/api/reports/briefing-archive`)

## Neue API-Endpunkte (v7.1.0)
- GET  /api/data/watchlist-momentum     — Rel. Stärke Ranking vs. SPY
- GET  /api/data/btc/snapshot           — Bitcoin Derivate-Snapshot
- POST /api/reports/generate-session-plan — Session-Plan (Reasoner)
- POST /api/reports/generate-btc        — BTC KI-Lagebericht
- GET  /api/reports/btc-latest          — Letzter BTC-Report

## Neue DB-Spalten (v7.1.0, daily_snapshots)
- session_plan TEXT
- session_plan_generated_at TIMESTAMPTZ
- btc_report TEXT
- btc_report_generated_at TIMESTAMPTZ

## Neue API-Endpunkte (v7.2.0)
- GET  /api/data/alpaca/account          — Paper Trading Account
- GET  /api/data/alpaca/positions        — Offene Positionen
- POST /api/data/alpaca/paper-trade      — Order platzieren
- GET  /api/data/real-trades             — Echte Trades
- POST /api/data/real-trades             — Trade erfassen
- PUT  /api/data/real-trades/{id}        — Exit eintragen
- GET  /api/data/decision-snapshots      — Alle Snapshots
- POST /api/data/decision-snapshots/update-outcomes — T+1/5/20 updaten

## Neue API-Endpunkte (v7.3.0)
- GET  /api/data/lernpfade-stats          — Lernpfade Performance-Statistiken (earnings + momentum)
- POST /api/reports/trigger-earnings-audits — Earnings Auto-Trigger (täglich 08:10)

## Neue DB-Tabellen (v7.2.0)
- `real_trades`          — Echte Trades des Traders
- `decision_snapshots`   — Kafin-Entscheidungskontext + Outcomes

## Wichtige Architektur-Entscheidungen
- Journal existiert NICHT als separate Seite — ist Tab 3 in Performance
- Shadow Portfolio = KI-simulierte Trades (automatisch)
- Real Trades = vom Trader manuell/per Alpaca eröffnet
- Decision Snapshots = unveränderlicher Tatort-Foto jeder Kafin-Empfehlung
- Alpaca nur Paper Trading — ALPACA_BASE_URL=https://paper-api.alpaca.markets

## Robustheitsfixes (v7.1.1)
- BTC-Lagebericht nutzt Safe-Formatting für fehlende Snapshot-/CoinGlass-Daten
- Momentum-Ranking behandelt 0.0-Veränderungen korrekt als gültige Werte

## Neue API-Endpunkte (v6.4.0)
- GET  /api/data/peer-comparison/{ticker}   — Peer-Metriken parallel
- GET  /api/data/watchlist-correlation      — 30T Korrelationsmatrix
- GET  /api/data/market-overview            — Marktübersicht für Dashboard
- GET  /api/data/market-breadth             — Marktbreite / SMA50 / SMA200
- GET  /api/data/intermarket                — Cross-Asset-Signale
- GET  /api/data/market-news-sentiment      — Markt-News + Sentiment
- GET  /api/data/economic-calendar          — Wirtschaftskalender
- GET  /api/data/fear-greed                 — Fear & Greed Score
- POST /api/market-audit                    — Gesamtmarkt-Analyse mit DeepSeek
- GET  /api/data/signals/feed               — Signal Feed / Anomaly-Feed
- GET  /api/data/signal-feed-config         — Signal-Feed-Konfiguration lesen
- POST /api/data/signal-feed-config         — Signal-Feed-Konfiguration speichern
- POST /api/reports/generate-after-market   — After-Market Briefing generieren
- GET  /api/reports/briefing-archive        — Pre/After-Market Briefing-Archiv
- POST /api/analysis/chat/{ticker}          — Multi-Turn AI-Chat
- GET  /api/journal                         — Trade-Journal lesen
- POST /api/journal                         — Trade-Journal schreiben
- PUT  /api/journal/{id}                    — Exit eintragen
- DELETE /api/journal/{id}                  — Eintrag löschen

## Frontend API-Regeln
- Browser-Requests nutzen relative `/api/...`-Pfade und laufen über die Next-Rewrites.
- Wenn eine Datei lokal eine Backend-URL braucht, ist `http://localhost:8000` der Standard; `8001` ist nur der Docker-Host-Port.

## Routing-Fixes (23.03.2026)
- Die Market-Dashboard-Endpoints sind wieder über `backend/app/routers/data.py` verfügbar.
- Der Market-Audit bleibt im `analysis`-Router unter `POST /api/market-audit`.
- `VolumeProfile`, Diagnostik-Handler und Report-Handler sollen die API über relative Routen oder definierte Proxy-URLs ansprechen.

## Neue DB-Tabelle (v6.4.0)
- `trade_journal` — Echte Trades mit Entry/Exit/P&L/These

## Twelve Data (v7.4.0)
- Client: `backend/app/data/twelvedata.py` 
- Funktion: ADX + Stochastic als TD-Enrichment auf TechnicalSetup
- Cache: 4 Stunden (Key: `td:adx:{TICKER}:14`, `td:stoch:{TICKER}`)
- Budget: Free Tier 800/Tag — Kafin nutzt ~30-50
- Konfiguration: TWELVE_DATA_API_KEY in .env
- Nicht ersetzen: yfinance für RSI, MACD, ATR, OBV — die bleiben
- Diagnostics: /api/diagnostics/full → services.twelve_data

## Makro-Regime-Gate (v7.5.0)
- Funktion: Risk Off (VIX > 30) degradiert STRONG BUY → WATCH
- Elevated VIX (25–30): STRONG BUY → BUY MIT ABSICHERUNG  
- Shorts bleiben unverändert (Short-Bias in Risk-Off oft korrekt)
- Implementation: `get_recommendation()` mit `macro_regime`/`vix` Parametern
- Makro-Warnung: sichtbar im Audit-Report mit Erklärung
- Konfiguration: `config/scoring.yaml` → `macro_regime_gate`

## ATR-basierte Stops (v7.5.0)
- Shadow Portfolio: 1.5× ATR statt pauschal -8%
- Sicherheitsprüfung: min 2% Abstand (verhindert sofortige Ausstoppung)
- Fallback: ±8% wenn kein ATR verfügbar
- Implementation: `open_shadow_trade(atr_14=...)` Parameter
- Multiplier: 1.5× (konfigurierbar in `scoring.yaml`)

## Options-Flow Boost (v7.5.0)
- Kontext: Vor Earnings (≤5T) wird Options-Flow von 5%→12% hochgewichtet
- Budget-Neutralität: Valuation 15%→11%, Technical 10%→7%
- Smart-Money Fokus: Unusual Options Activity ist frühestes Signal vor Earnings
- Implementation: `calculate_opportunity_score()` mit `_weights` Kopie
- Logging: `[Options-Boost aktiv: EC=3T]` im Score-Breakdown

## Journal-Redirect (v7.5.0)
- /journal → /performance?tab=my_trades (eine Quelle der Wahrheit)
- Performance Page: `?tab=my_trades` öffnet direkt Tab 3
- Router: `router.replace()` (keine History-Einträge)
- Ziel: Dopplung vermeiden, bestehende Links保持

## Alpaca Market Data (v7.6.0)
- Client: `backend/app/data/alpaca_data.py` 
- URL: https://data.alpaca.markets (NICHT paper-api!)
- Keys: Dieselben ALPACA_API_KEY / ALPACA_SECRET_KEY
- Free Tier: IEX-Daten, 15-Min-Delay, nur US-Aktien
- Hauptfunktionen:
  - `get_snapshots(tickers)` — Batch, 1 Call für alle
  - `get_bars(ticker, days, timeframe)` — OHLCV
  - `get_latest_quote(ticker)` — Bid/Ask
- Cache: 60s (Snapshots), 300s (Bars), 30s (Quotes)
- Fallback: yfinance wenn Alpaca nicht konfiguriert oder 403
- yfinance bleibt primär für: Options, Fundamentals, ATR/MACD-Berechnung
- Voraussetzung: Market Data Scope in Alpaca API Keys aktiviert

## Aktuelle Fixes & Betriebsnotizen (Prompts 36–40)
- **Signal Feed Enhancements**: Catalyst Clash Warning, Short Availability Badges und Earnings Live-Modus sind im Feed aktiv.
- **News Pipeline**: `bullet_points` wird als Array gerendert; `news_processor.py` hat einen file-sicheren Prompt-Pfad, ETF-spezifische Relevanz und Google-News-Fallback.
- **Monitoring**: `GET /api/n8n/status` ist der dedizierte n8n-Health-Check; `diagnostics/full` führt `n8n` und `alpaca_data` separat.
- **Shadow Trades**: `shadow_portfolio.py` normalisiert Prompt-Labels (`strong_buy`, `buy_hedge`, `strong_short`, `potential_short`) korrekt auf long/short.
- **n8n Workflows**: Die JSON-Workflows referenzieren `http://kafin-backend:8000` statt `http://api:8000`.
- **Dokumenten-Quelle der Wahrheit**: Aktueller Stand und Roadmap sind in `STATUS.md` und `docs/FUTURE.md`; Änderungen werden dort mitgezogen.

## Journal vs Real Trades
- `/journal` Page → Redirect auf `/performance?tab=my_trades` 
- `real_trades` Tabelle = echte Quelle (seit v7.2.0)
- `trade_journal` Tabelle = alt, `journal.py` Router = Legacy
- Performance Tab 3 "Meine Trades" = aktuelle UI

## Wichtige Dateien / APIs
| Datei / API | Ort | Beschreibung |
|-------------|-----|--------------|
| ... | ... | ... |
| Frontend | `frontend/src/app/research/[ticker]/page.tsx` | 'Trade prüfen' modal for manual trade review, displaying reasoner's decision and allowing execution with error handling. |
| ... | ... | ... |

## Aktuelle Features
- **Trade Prüfen Modal v7.8.0**: Frontend-Modal für manuelle Trade-Überprüfung und Ausführung basierend auf Reasoner-Entscheidungen, inklusive Fehlerbehandlung und Ladezuständen.
