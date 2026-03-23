# Kafin — KI-gestützte Earnings-Trading-Plattform

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

### Code-Konventionen
- Python 3.11+, Type Hints überall
- Naming: snake_case für Variablen/Funktionen, PascalCase für Klassen
- Kommentare und Docs: Deutsch
- Code und Variablen: Englisch
- HTTP-Client: httpx (nicht requests, nicht aiohttp)
- Schemas: Pydantic v2 Models aus schemas/
- Datenbank: supabase-py Client aus backend/app/db.py
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
backend/app/memory/     → Gedächtnis-System (Supabase CRUD)
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
