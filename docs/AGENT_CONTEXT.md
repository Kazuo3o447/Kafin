# KAFIN — Agent Context

Dieses Dokument beschreibt den aktuellen Stand und die Architektur von Kafin für AI-Agenten.

---

## Aktuelle Version
**Version**: 6.1.6 (Chart Analysis Complete Overhaul)
**Stand**: 2026-03-22
**Latest Commit**: feat: chart analysis complete overhaul v6.1.6

---

## Architektur-Überblick (v6.1.6)
Das Backend wurde von einer monolithischen `main.py` auf eine modulare Router-Struktur umgestellt.
Die Chart-Analyse wurde komplett überarbeitet mit immer sichtbaren Begründungen und ETF/Index-Unterstützung.

### Kern-Struktur (backend/app/)
- `main.py` - Minimaler Entrypoint, Middleware & Router-Registrierung
- `routers/` - Fachlich getrennte API-Endpunkte:
  - `data.py` - Marktdaten, Research, Snapshots
  - `news.py` - Google News, Scans, News-Memory
  - `analysis.py` - Signale, FinBERT, RAG, Market-Audit
  - `reports.py` - Report-Generierung (Audit, Morning, Weekly)
  - `watchlist.py` - Watchlist Management
  - `shadow.py` - Shadow Portfolio & Trades
  - `logs.py` - Log-Management & Export
  - `system.py` - Diagnostics, Health, Telegram-Test
  - `web_intelligence.py` - Web-Intelligence-Integration
- `admin/` - Admin-Panel UI & Admin-Operations
- **Docker Container**: `kafin-backend` auf Port 8000
- **API-Dokumentation**: http://localhost:8000/docs
- **Wichtige Module**:
  - `backend/app/data/market_overview.py` - Marktübersicht + Sektoren
  - `backend/app/data/finnhub.py` - News-Daten
  - `backend/app/analysis/finbert.py` - Sentiment-Analyse
  - `backend/app/memory/short_term.py` - News-Sentiment Storage + Batch-Funktionen
  - `backend/app/analysis/usage_tracker.py` - API Usage Tracking + Token Counter

### Frontend (Next.js/React)
- **Docker Container**: `kafin-frontend` auf Port 3000
- **Source-Mount**: `./frontend/src:/app/src` (Live-Reload)
- **API-Proxy**: `INTERNAL_API_URL=http://kafin-backend:8000`

### Datenquellen
- **Marktdaten**: Yahoo Finance (yfinance)
- **News**: Finnhub (Free Tier: 60 Calls/Min)
- **Sentiment**: FinBERT (lokal, transformers)

---

## Datenbank (v6.0.0+)
PostgreSQL 16 + pgvector (lokal, Docker)
Container: kafin-postgres (pgvector/pgvector:pg16)
Connection: postgresql://kafin:***@postgres:5432/kafin
Pool: asyncpg, min=2, max=10

14 Tabellen:
- watchlist, short_term_memory, long_term_memory
- macro_snapshots, btc_snapshots, audit_reports
- earnings_reviews, performance_tracking
- daily_snapshots, shadow_trades, score_history
- system_logs, web_intelligence_cache
- custom_search_terms, api_usage

pgvector (vector(384)):
- short_term_memory.embedding (HNSW)
- long_term_memory.embedding (HNSW)
- audit_reports.embedding (HNSW)
Modell: all-MiniLM-L6-v2 (lokal, 22MB)

DB Client: backend/app/database.py (Drop-in Adapter)
API-kompatibel mit Supabase-Syntax:
  db.table("x").select("*").eq("k","v").execute()
Supabase komplett abgelöst.

RAG Endpoints:
  GET /api/data/rag/similar-news?query=...
  GET /api/data/rag/similar-audits?query=...

---

## KI-Pipeline (v6.1.4)
Stufe 1: FinBERT (lokal) — Sentiment-Filter
Stufe 2: Groq llama-3.1-8b-instant — News-Extraktion
         Fallback: DeepSeek Chat
         Voraussetzung: `GROQ_API_KEY` lokal in `.env` setzen, nicht committen
Stufe 3: DeepSeek Chat — komplexe Analyse
Stufe 4: Kimi K2.5 — Earnings-Transkripte
Stufe 5: DeepSeek Reasoner — Audit-Reports

## API Usage Tracking (v6.1.3)
- **usage_tracker.py**: Redis-Puffer + DB-Flush (5min)
- **Token-Counter**: DeepSeek + Groq (input/output/total/cost)
- **Call-Counter**: FMP (250/Tag), Finnhub (60/min)
- **Endpoint**: GET /api/admin/api-usage
- **UI**: Settings → APIs → ApiUsageBlock (Echtzeit + Limits)

## Prompt Quality (v6.1.4)
- **Prompts v0.4**: Alle TODO-Platzhalter implementiert
- **audit_report.md**: Max Pain, PCR-OI, Squeeze-Signal, CEO, Mitarbeiter, Peers
- **post_earnings.md**: AH-Reaktion, Expected Move, Fear & Greed
- **morning_briefing.md**: Fear & Greed Score/Label
- **Modell-Matrix**: DeepSeek Reasoner (Audit/Torpedo), Chat (Morning/Weekly/Post-Earnings/Chart)
- **groq.py**: API-Key aus settings statt module-level env

---

## Sentiment-Integration (v5.10.0+)

### Architektur
- **Storage**: PostgreSQL `short_term_memory` Tabelle mit FinBERT-Analysen
- **Batch-Processing**: `get_bullet_points_batch()` für effiziente Queries
- **Aggregation**: `_calc_sentiment_from_bullets()` mit avg, trend, label, count, has_material
- **Market Context**: S&P-500 Sentiment via `get_market_news_for_sentiment()`

### Frontend-Komponenten
- **SentimentBlock**: Research Dashboard mit Ticker/Markt/Vergleich
- **Watchlist**: Sentiment-Spalte mit Trend-Icon und Material-Event-Indicator
- **Earnings Radar**: Pre-Earnings Sentiment für Earnings-Vorbereitung
- **Alerts**: Material News und Sentiment Drop Benachrichtigungen

### API-Integration
- **Research**: `/api/data/research/{ticker}` - Sentiment-Felder erweitert
- **Watchlist**: `/api/watchlist/enriched` - Batch-Sentiment-Enrichment
- **Earnings**: `/api/data/earnings-radar` - Pre-Earnings Sentiment
- **Background Tasks**: Sofortiger News-Scan bei neuen Ticker-Additions

### Bugfixes in v5.10.2
- **Logs**: `/api/logs` bleibt array-kompatibel für den Admin-Viewer
- **Cache-Invalidierung**: News-Scans invalidieren Research-, Watchlist- und Earnings-Caches direkt
- **Null-Safety**: Ticker ohne News erzeugen keine irreführende Market-Divergenz mehr
- **Batch-Fairness**: Sentiment-Batch lädt fehlende Ticker bei Bedarf gezielt nach
- **Ignore-Filter**: Erwartbare yfinance-404s werden in `Ignore` einsortiert

### Bugfixes in v5.10.6
- **Audit Sentiment**: `report_generator.py` nutzt die gemeinsame Helper-Logik `_calc_sentiment_from_bullets()` statt eigener Aggregation
- **Score History**: Underfilled `score_history`-Ticker werden gezielt nachgeladen, damit Weekly-Deltas stabiler sind
- **Research Deltas**: Null-Werte werden in der Delta-Anzeige nicht mehr durch truthy-Checks unterdrückt
- **Position Sizer**: Ungültige Stop-Loss-Konstellationen werden im Research-UI abgefangen

### Bugfixes in v5.10.7
- **Economic Calendar Refresh**: Der Aktualisieren-Button im Markets-Dashboard triggert jetzt den Makro-Scan und lädt den gespeicherten Kalender danach neu
- **UI Feedback**: Der Kalender-Refresh nutzt einen eigenen Loading-State statt den globalen Dashboard-Status

### Bugfixes in v5.10.8
- **Batch-Download Performance**: _batch_download() lädt alle Ticker in einem yfinance.download() Call statt 83 sequentiellen Calls
- **Market Overview**: 24 einzelne Ticker-Calls → 1 Batch-Download für alle Indizes/Sektoren/Makro
- **Market Breadth**: 50 einzelne Ticker-Calls → 1 Batch-Download für S&P 500 Top 50
- **Intermarket Signals**: 9 einzelne Ticker-Calls → 1 Batch-Download für alle Cross-Assets
- **Warm-Start**: Backend wärmt Market-Cache beim Docker-Start vor (non-blocking)
- **Frontend Optimization**: 3× getMarketOverview() → 1× fetchMarketOverview() mit gemeinsamem State

### Bugfixes in v5.10.10
- **Falsey Values**: `0.0`-Werte bleiben in Research-/Technicals-Antworten erhalten
- **Market Overview History**: `sma_200` ist mit 1y-Historie jetzt tatsächlich berechenbar
- **Design System**: Inter wird nur noch über `next/font` geladen

### Bugfixes in v5.10.11
- **Free-Tier News Coverage**: Market-Sentiment kombiniert Finnhub General News und Google News RSS, um ein robusteres 24h-Sentimentbild zu erhalten
- **Sentiment UX**: Der Markets-Block zeigt jetzt Datum/Uhrzeit, externe Links und Bullish/Bearish/Neutral-Zähler für die Marktanalyse
- **Cache Isolation**: Google-News-Caches sind nach Scope getrennt, damit Market-Sentiment nicht versehentlich durch Watchlist-Scans überschrieben wird

### Kaskade 4 (v5.15.0-5.15.4)
- **Marktbreite History**: `daily_snapshots` speichert jetzt `pct_above_sma50` / `pct_above_sma200`; historische 5T/20T-Werte kommen aus Supabase.
- **VWAP**: `get_vwap()` berechnet intraday VWAP aus 5m-Yahoo-Daten, cached 2min im Markt und 1h außerhalb; Endpoint `GET /api/data/vwap/{ticker}`.
- **Options OI Heatmap**: `OptionsOiBlock` lädt on-demand Top-Strike-OI, hebt Max Pain hervor und markiert ATM-Level.
- **P2b Earnings Fallback**: `get_earnings_history_yf()` nutzt yfinance als Fallback, wenn FMP keine Earnings-Historie liefert.
- **Sektor-Kalender**: `sector_earnings_upcoming` zeigt Watchlist-Earnings der nächsten 14 Tage im `EarningsContextBanner`.

---

## Core Concepts / Scoring

### Scoring — alle Faktoren live (nach P1b)
**Opportunity-Score (9 Faktoren):**
- `earnings_momentum`: aus EarningsHistory (beats/surprise)
- `whisper_delta`: Proxy via avg_surprise_percent + quarters_beat
- `valuation_regime`: P/E vs. Sektor-Median
- `guidance_trend`: FMP analyst_grades Upgrades
- `technical_setup`: yfinance Trend/RSI/SMA
- `sector_regime`: Sektor-ETF 5T-Performance
- `short_squeeze_potential`: Short Interest %
- `insider_activity`: Finnhub Insider Assessment
- `options_flow`: Put/Call Ratio (konträr)

**Torpedo-Score (7 Faktoren):**
- `valuation_downside`: P/S vs. Sektor-Median
- `expectation_gap`: IV + Sentiment-Divergenz
- `insider_selling`: Insider Assessment bearish
- `guidance_deceleration`: FMP analyst_grades Downgrades
- `leadership_instability`: news_memory "management" shifts
- `technical_downtrend`: yfinance Trend/RSI/SMA
- `macro_headwind`: VIX-Level

---

## Scoring-Robustness & Einschränkungen

### Quality Gates (neu in v5.9.1)
- **Analyst-Grades**: Mindest-Sample von 3 Grades erforderlich
- **Leadership-Instability**: 30-Tage Freshness-Filter
- **Key-Normalisierung**: camelCase + lowercase Robustheit

### Bekannte Einschränkungen
- **Watchlist-Scores**: Nutzen gecachte `score_history`, nicht Live-Scoring
  - Backfill erforderlich nach P1b-Deploy: `POST /api/admin/scores/backfill`
- **FMP Grade-Keys**: Abhängig von exakter API-Response-Struktur
- **News-Freshness**: `leadership_instability` nur bei aktuellen Events aussagekräftig

### Admin-Tools (neu in v5.9.1)
- **Score Backfill**: `/api/admin/scores/backfill?tickers=AAPL,MSFT&days=7`
- **Live-Scoring**: Research Dashboard nutzt immer Live-Daten
- **Debug-Logging**: Score-Breakdown in Backend-Logs (debug-level)

---

## Was funktioniert gut

### Watchlist v5.8.0 — Trading-Werkzeug
- **Alert-Streifen**: automatisch aus Watchlist-Daten — Earnings ≤5T, Torpedo-Delta >+1.5, SMA50-Bruch, RVOL Spike, Setup verbessert
- **Überblick-Kacheln**: Earnings diese Woche, Ø Opp, Torpedo-Warnung, Ticker-Count
- **Sortierbare Tabelle**: Opp, Torp, 1T%, 5T%, Earnings, RVOL — nach Klick auf Header
- **Filter-Leiste**: Earnings ≤7T, Torpedo ≥6, RVOL >1.5×, SMA-Bruch, Setup verbessert
- **Neue Spalten**: 5T%, RVOL, ATR — für Positionsgrösse
- **Score-Wochendelta**: Opp/Torp Veränderung diese Woche — Torpedo-Delta INVERTIERT (↑=rot=schlechter)
- **Zeilen-Hintergrund**: rot wenn Torpedo ≥7 oder SMA-Bruch, amber wenn Earnings ≤7T
- **Sektor-Heatmap**: Balken mit Klumpenrisiko-Warnung

### Research Dashboard Decision Core (/research/[ticker])
- **Score-Delta Anzeige**: Opportunity- und Torpedo-Scores mit Veränderung vs. gestern/letzte Woche
- **Trade Setup Block**: Chart-Analyse mit Entry Zone, Stop-Loss, Targets, Support/Resistance, Bias
  - **Anti-Falling-Knife**: Begründungsfelder why_entry/stop, trend_context, floor_scenario, turnaround_conditions
  - **Risk Assessment**: falling_knife_risk (low/medium/high) mit prominenten Warn-Bannern
- **Position Sizer Block**: Risikomanagement mit Kontogröße, Risiko-%, Aktienanzahl, R:R Verhältnis
- **On-Demand Loading**: Chart-Analyse erst auf Knopfdruck geladen (Performance-Optimierung)
- **localStorage Integration**: Kontogröße wird gespeichert und wiederhergestellt
- **Relative Stärke**: Ticker vs. SPY und Sektor-ETF (1T/5T/20T), zeigt titelspezifische Bewegung
- **Earnings Context**: Break-Even Levels, Buy-the-Rumor Warnung, EPS/Revenue Konsens
- **Technisches Bild**: Trend-Zusammenfassung, MACD Cross, OBV Käufer/Verkäufer, ATR + 52W-Position

### Research Dashboard — vollständig (nach P1-P3)
Blöcke von oben nach unten:
1. Header (Ticker, Preis, 1T/5T, Sektor, Mitarbeiter)
2. Entscheidungs-Kern (Opp/Torp Score + Delta)
3. Trade Setup (chart_analyst on demand)
4. Positionsgrössen-Rechner (localStorage)
5. Relative Stärke (vs SPY + Sektor-ETF)
6. Earnings-Kontext (Break-Even, Buy-Rumor Warning)
7. Preis & Performance
8. Bewertung
9. Technisches Bild (aufgeräumt)
10. Volumen & Marktstruktur
11. Analyst & Options
12. Earnings-Historie Tabelle
13. Insider + News-Bullets
14. KI-Analyse (DeepSeek, on demand)

### DeepSeek Audit — Input (14 Datenquellen)
Siehe CHANGELOG.md [5.7.2] für vollständige Liste.
Kritische Verbesserung P3: chart_analyst Levels +
relative_strength + FinBERT-Scores pro Schlagzeile.

### report_generator.py — Sicherheitsnetz
Alle unfilled {{...}} Placeholders werden vor
DeepSeek-Aufruf via regex auf "N/A" gesetzt.
Kein roher Placeholder-Text mehr im Prompt.

### Markets Dashboard v3 (/markets)
- **Composite Regime Header**: Prominenter Multi-Faktor Regime-Indikator (Risk-On/Neutral/Risk-Off)
- **Gewichtete Scoring**: VIX (25%), Credit Spread (20%), Yield Curve (15%), Market Breadth (20%), Risk Appetite (10%), VIX Structure (10%)
- **Visual Indicators**: Farbcodierte Anzeige mit Score, Dominant-Faktor und Mini-Dots für alle 6 Faktoren
- **Expandable Details**: Klapbarer Faktor-Grid mit Signalen, Gewichtungen und Methodik-Erklärung
- **Pure Frontend**: Berechnung läuft vollständig im Frontend, keine neue Backend-API benötigt
- **Granulare Refresh-Zyklen**: 9 Blöcke mit individuellen Intervallen
- **Economic Calendar Refresh**: On-demand Refresh stößt `runMacroScan()` an und lädt danach `/api/data/economic-calendar` neu
- **Performance-Optimierung**: Batch-Downloads statt sequentieller yfinance-Calls (83 → 3)
- **Frontend State-Sharing**: `fetchMarketOverview()` eliminiert Triple-Call auf `getMarketOverview()`
- **Vollständige UI**: Alle Datenblöcke mit Block-Labels und Timestamps

### Kaskade 3 (v5.14.0-5.14.4)
- **Fear & Greed Score**: `backend/app/data/fear_greed.py`
  - 5 Komponenten: VIX (30%), Breite (20%), TLT/SPY (20%), Credit (20%), Momentum (10%)
  - Cache 30min, GET `/api/data/fear-greed`
- **FearGreedBlock**: Neuer Markets-Block auf `/markets` direkt nach MacroDashboard
- **Watchlist P1 Auto-Update**: `post_earnings_review.py` aktualisiert `web_prio` + Notiz nach Earnings und invalidiert relevante Caches
- **DeepSeek Prompts v0.3**:
  - `news_extraction`: `is_directly_relevant`-Check + `relevance_reason`
  - `audit_report`: Max Pain, PCR-OI, Squeeze-Signal, Firmenprofil
  - `post_earnings`: AH-Reaktion + Fear & Greed Kontext
  - `morning_briefing`: Fear & Greed bei Extremen
- **Chart Analyst**: optionale `pre_market_price` / `pre_market_change` Parameter

### Batch 1 (v5.13.0)
- **Max Pain**: GET /api/data/options-oi/{ticker}, Cache 4h
  Berechnet Max Pain Preis + Top-5 OI-Strikes + Put/Call Ratio aus yfinance option_chain
- **Pre/Post-Market**: fast_info.pre_market_price
  Research Header zeigt "Pre: $142.30 (+0.8%)" wenn verfügbar
- **Groq Client**: backend/app/analysis/groq.py
  Fallback auf DeepSeek wenn GROQ_API_KEY nicht gesetzt
  News-Extraction-Limit: 20/h statt 5/h (Groq hat großzügige Limits)
- **Sektoren Rotation-Story**: automatisch erkannt (Defensiv vs. Offensiv Gap > 2%)
- **VIX Term Structure**: Contango/Backwardation sichtbar
- **Info-Seite**: `/markets/info` mit vollständiger Dokumentation
- **Robuste Fehlerbehandlung**: BlockError-Komponenten + Fallback-Texte

### Performance-Architektur Markets (v5.10.8)
- **Batch-Downloads**: `yf.download()` für N Ticker in einem HTTP-Request
- **Cache-Strategy**: overview 300s, breadth 1800s, intermarket 600s
- **Warm-Start**: `@app.on_event("startup")` → `asyncio.create_task()` für paralleles Vorladen
- **Frontend**: Shared State für Market Overview verhindert redundante API-Calls

### Backend-Features
- **Marktüberblick**: Indizes, Sektoren, Makro-Proxys
- **Intermarket-Signale**: Risk Appetite, VIX Structure, Credit, **Energie-Stress**
- **News + FinBERT**: Kategorisierte Nachrichten mit Sentiment
- **Rotation-Story**: Automatische Erkennung von Risk-On/Risk-Off
- **Stagflations-Warnung**: Wenn Öl steigt + S&P fällt gleichzeitig
- **Cache-Invalidierung**: Versionierte Cache-Keys (`market:overview:v2`, `market:intermarket:v2`) verhindern stale Signal-Daten

---

## Bekannte Einschränkungen

### Frontend
- **Marktbreite Verlauf**: `pct_above_sma50_5d_ago` = None (Placeholder)
- **News Rate-Limit**: Finnhub Free Tier begrenzt auf 60 Calls/Minute

### Backend
- **Mock-Data-Modus**: `settings.use_mock_data` für Entwicklung
- **Cache-Strategie**: 5-10 Minuten TTL für Markt-Daten

---

## Entwicklungshinweise

### Container-Kompatibilität
- Frontend verwendet `INTERNAL_API_URL` für Docker-interne Kommunikation
- Source-Mounts ermöglichen Live-Reload ohne Neubau
- API-Proxy funktioniert sowohl lokal als auch in Docker

### TypeScript-Typen
- `IndexData`:enthält `change_5d_pct` und `change_1m_pct`
- `MarketOverview`: enthält `sector_ranking_5d` mit `name` und `perf_5d`
- `IntermarketData`: enthält `assets` mit `change_1w` und `signals`

### Backend-Patterns
- Alle Markt-Datenfunktionen sind `async` und verwenden Cache
- Fehlerbehandlung mit `try/except` und Logger
- Mock-Daten über `fixtures/*.json` verfügbar

### Sympathy Play Radar
Manuell triggern nach Earnings-Meldung:
POST /api/data/sympathy-check/{REPORTER_TICKER}?move_pct={REACTION}

Oder n8n: Nach scan-earnings-results den
Sympathy-Check für jeden gemeldeten Ticker triggern.

### Kaskade 6 (v6.1.6)
- **chart_analyst.py**: Complete Overhaul mit immer sichtbaren Begründungen
  - max_tokens von 512 auf 2048 erhöht
  - Explizite Anweisung für vollständige Sätze
  - Temperature 0.2 für Konsistenz
- **Research Frontend**: Akkordeon entfernt, Begründungen immer sichtbar
  - Farbige Headers (blau/rot/grün) für why_entry/why_stop/turnaround
  - Direkte Darstellung ohne Klick erforderlich
- **ETF/Index Research**: Asset-Type Detection für SPY/QQQ/IWM/DXY etc.
  - Backend: ETF_TICKERS und INDEX_TICKERS Konstanten
  - API: /research/{ticker} liefert is_etf, is_index, asset_type
  - Frontend: Badge im Research Header (ETF=blau, Index=lila)
  - Markets Page: "Research" Button neben "⚡ Chart"
- **Audit Report Integration**: Vollständige Chart-Daten im Prompt
  - report_generator.py: chart_str enthält alle reasoning fields
  - DeepSeek Reasoner erhält why_entry, why_stop, trend_context etc.

### Kaskade 5 (v5.16.0-5.16.4)
- **reddit_monitor.py**: WSB + r/stocks JSON → FinBERT
  - Divergenz: Retail vs. Insider-Signal
  - GET `/api/data/reddit-sentiment/{ticker}`, Cache 1h
- **peer_monitor.py**: `check_sympathy_reactions()`
  - Klassifiziert Peer-Reaktionen nach Earnings
  - POST `/api/data/sympathy-check/{ticker}?move_pct=X`
  - Telegram: Relative Stärke + Sympathy Alerts
- **shadow_portfolio.py**: `trade_reason` + `manual_entry`
  - POST `/api/shadow/manual-trade` mit 11 Gründen
  - Performance: "Trade eröffnen" Modal + Dropdown
- **Integration**: Reddit im Research (Scoring + Sentiment)
  - Fear & Greed Badge im Research-Score
  - GEX aktuell als BLOCKIERT dokumentiert

---

## Nächste Schritte (aus FUTURE.md)

### Kurzfristig (2h)
- **Marktbreite History**: Tabelle `market_breadth_history` für 5T/20T Verlauf
- **General News Endpoint**: `/api/news/general` verdrahten

### Mittelfristig (3h)
- **Fear & Greed Score**: Aus VIX, Put/Call, Junk Bonds etc.

---

## Debugging-Tipps

### Frontend nicht aktualisiert?
1. Container-Logs prüfen: `docker logs kafin-frontend`
2. API-Proxy testen: `curl http://localhost:3000/api/data/market-overview`
3. Source-Mount prüfen: `docker inspect kafin-frontend`

### Backend-Daten fehlen?
1. Mock-Modus prüfen: `settings.use_mock_data`
2. Cache leeren: Redis neu starten
3. API-Dokumentation: http://localhost:8000/docs

### News nicht verfügbar?
1. Finnhub API-Key prüfen
2. Rate-Limit: 60 Calls/Minute (Free Tier)
3. Alternative: Watchlist-Ticker über FinBERT-Pipeline
