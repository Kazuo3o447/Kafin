# Kafin Changelog

Alle wichtigen Änderungen, Bugfixes und Features nach Version.

## [5.0] - 2026-03-19 - Sentiment-Aggregator

### 🚀 Neue Features
- **Composite Sentiment**: Gewichteter Score aus drei Quellen
  (FinBERT 40% + Web 40% + Social 20%)
- **Divergenz-Erkennung**: Automatisch wenn |FinBERT - Web| > 0.4
  — "Buy the Rumor"-Warnung im Report
- **Torpedo-Score Integration**: Sentiment-Divergenz erhöht
  expectation_gap automatisch (+2.5 bei Divergenz, +1.5 bei
  stark bärischem Web-Diskurs)
- **get_web_sentiment_score()**: DeepSeek analysiert Tavily-Snippets
  und gibt strukturierten -1.0 bis +1.0 Score zurück
- **Audit-Report**: Neue SENTIMENT-ANALYSE Sektion mit allen drei
  Quellen und Divergenz-Warnung

## [4.9] - 2026-03-19 - Web Intelligence Batch + Prio-UI

### 🚀 Neue Features
- **Batch-Endpoint**: POST /api/web-intelligence/batch — von n8n
  täglich aufrufbar, überspringt Prio-4-Ticker automatisch
- **Einzel-Refresh**: POST /api/web-intelligence/refresh/{ticker}
- **Prio-Dropdown**: Direkt in Watchlist-Tabelle, inline speichernd
  (Auto / P1 3×/Tag / P2 täglich / P3 wöchentlich / P4 pausiert)
- **Web-Scan Button**: Manueller Batch-Trigger in der Watchlist-UI
- **API-Key-Check**: Batch gibt klare Fehlermeldung wenn Key fehlt

## [4.8] - 2026-03-19 - Web Intelligence Fundament

### 🚀 Neue Features
- **web_intelligence_cache**: Neue Supabase-Tabelle mit TTL je Prio
- **watchlist.web_prio**: Manuelles Prio-Feld (NULL=Auto, 1-4=manuell)
- **web_search.py**: Cache-aware Tavily-Modul mit Prio-System
  (Prio 1: 3 Suchen/8h | Prio 2: 1 Suche/24h | Prio 3: wöchentlich)
- **Audit-Report**: {{web_intelligence}} aus Cache oder Live-Suche
- **DeepSeek-Prompt**: Web-Sentiment vs. News-Sentiment Divergenz-Analyse

## [4.7] - 2026-03-19 - Hotfix Expected Move & Score Sort

### 🐛 Bugfixes
- **Expected Move**: replace()-Aufrufe für {{expected_move}} und
  {{price_change_30d}} fehlten — DeepSeek bekam ungeparste Platzhalter
- **IV-Felder**: {{iv_atm}}, {{hist_vol_20d}}, {{iv_spread}},
  {{put_call_ratio}} jetzt einzeln befüllt statt über {{options_metrics}}
- **Score Sort**: TypeError bei None-Datum in _fetch_all_scores_sync
  durch 'or ""' Fallback behoben
- **Event-Loop**: yfinance 30d-History in asyncio.to_thread ausgelagert

## [4.6] - 2026-03-19 - Expected Move & Pre-Earnings Intelligence

### 🚀 Neue Features
- **Expected Move**: Automatische Berechnung aus IV × sqrt(Tage/365)
  — zeigt ±X% und ±$Y direkt im Audit-Report
- **30-Tage-Performance**: Pre-Earnings-Rally-Erkennung im Report
  — warnt bei "Buy the Rumor"-Setups (>+10% in 30 Tagen)
- **DeepSeek-Prompt**: Explizite Anweisung für Break-Even-Levels
  und Pre-Earnings-Positioning-Analyse

## [4.5] - 2026-03-19 - Hotfix Score Query & Caching

### 🐛 Bugfixes
- **Batch Score Query**: Sortierung jetzt pro Ticker in Python
  statt global in Supabase — Delta-Berechnung korrekt
- **fetchJSON Cache**: revalidate von 300s auf 60s reduziert
- **ChartWrapper**: TypeScript Props-Interface ergänzt

## [4.4] - 2026-03-19 - Charts sichtbar

### 🐛 Bugfixes
- **InteractiveChart**: War importiert aber nie gerendert — jetzt
  sichtbar auf jeder Ticker-Detailseite direkt beim Öffnen
- **dynamic() Import**: lightweight-charts via ssr:false geladen —
  verhindert Server-Side-Rendering-Konflikt
- **Fetch-Caching**: cache:"no-store" durch revalidate:300 ersetzt —
  Ticker-Seiten laden deutlich schneller beim zweiten Besuch

## [4.3] - 2026-03-19 - Schnellsuche Windows-Fix

### 🐛 Bugfixes
- **Schnellsuche**: Sidebar-Button öffnet Palette jetzt auf Windows
  (Custom Event statt KeyboardEvent mit metaKey)
- **Leere Snapshot-Anzeige**: Klare Fehlermeldung wenn kein US-Kurs
  verfügbar statt leerem "$—"

## [4.2] - 2026-03-19 - Bug Fixes & Stabilisierung

### 🐛 Bugfixes
- **watchlist_router registriert**: Router war nie mit app.include_router()
  verbunden — POST/PUT/DELETE Watchlist-Routen gaben 404 zurück
- **Enriched Endpoint Performance**: stock.info ersetzt durch stock.fast_info,
  alle Ticker parallel via asyncio.gather, Score-History als Batch-Query
- **Leere Watchlist beim Seitenwechsel**: Race Condition im Frontend durch
  cacheGet-Sofortprüfung behoben, useCallback Dependencies bereinigt
- **Earnings-Radar leer**: Feldname-Bug in finnhub.py (date → report_date)
  und in api_earnings_radar (getattr "date" → "report_date") behoben
- **Watchlist-Kacheln keine Daten**: fast_info Feldabrufe einzeln abgesichert,
  change_pct Fallback via 2-Tage-History implementiert
- **Dark Mode**: CSS-Variablen auf dunkles Theme umgestellt (#0B0F1A)
- **Sidebar**: Neu gestaltet, schlanker (w-56), aktive Linie statt Block

### 🔌 Neue Features
- **Shadow Portfolio**: Automatisches Paper-Trading auf Basis von KI-Signalen
- **Earnings-Radar**: Neuer Kalender mit Watchlist-Markierung
- **Schnellsuche (Cmd+K)**: CommandPalette für Ticker-Lookup
- **Track Record**: Ticker-spezifische KI-Trefferquote auf Detailseite
- **Client-Side Cache**: Navigationscache verhindert Neu-Laden bei Seitenwechsel

## [4.1] - 2026-03-18 - Chart Intelligence System

### 🚀 Neue Features
- **Interaktive TradingView Lightweight Charts**
  - Candlestick-Chart mit Volume-Histogramm für alle Watchlist-Ticker
  - Timeframe-Toggle: 6 Monate (Tageskerzen) / 2 Jahre (Wochenkerzen)
  - SMA 50 (blau gestrichelt) und SMA 200 (lila gestrichelt) als Overlays
  - ResizeObserver für responsive Chart-Breite

- **Vollständiges Overlay-System**
  - Earnings-Events: blau (Pre-Market) / lila (After-Hours) mit EPS-Surprise und Reaktion
  - Torpedo-Alerts: rote Marker an Tagen mit material-relevanten News
  - Narrative-Shifts: amber-farbene Marker bei erkannten Paradigma-Wechseln
  - Insider-Transaktionen: grüne Dreiecke (Kauf) / rote Dreiecke (Verkauf)
  - Floating Tooltip mit Event-Details bei Cursor-Hover

- **KI-generierte Chart-Levels (auf Abruf)**
  - Strukturiertes JSON-Output von DeepSeek (kein Freitext mehr)
  - Support-Levels: grün gestrichelt, Stärke (strong/moderate/weak)
  - Resistance-Levels: rot gestrichelt, Stärke
  - Entry-Zone: grüner Preisbereich
  - Stop-Loss: rote Linie (durchgezogen)
  - Target 1 + Target 2: grün gepunktet
  - Bias (bullish/bearish/neutral), Analysis-Text, Key-Risk

### 🔌 Neue API-Endpoints
- `GET /api/data/ohlcv/{ticker}?period=6mo&interval=1d` — OHLCV + SMA50/200
- `GET /api/data/chart-overlays/{ticker}` — Alle Chart-Events aus Supabase

### 🛠️ Verbesserungen
- `chart_analyst.py`: DeepSeek gibt jetzt strukturiertes JSON zurück
  mit Fallback auf berechnete Levels bei Parse-Fehler
- `ChartAnalysisSection.tsx`: Vollständig neu gebaut mit lightweight-charts
- Legacy-Felder (support, resistance, analysis) bleiben für Abwärtskompatibilität

## [4.0] - 2026-03-18 - Signal Intelligence Complete

### 🚀 Neue Features
- **Signal Intelligence Suite**:
  - Smart Alerts (RSI, Volumen, SMA, Score-Deltas)
  - Opportunity Scanner für Earnings-Setups
  - Chart Analyst mit DeepSeek technische Analyse
  - Google News Integration mit Custom Keywords
  - Narrative Intelligence für fundamentale Shifts

- **Frontend Erweiterungen**:
  - Watchlist Heatmap mit Deltas & Sparklines
  - Opportunity-Sektion mit Top-Setups
  - Sektor-Konzentrations-Warnungen
  - Google News & Signals Tabs
  - Chart-Analyse-Button pro Ticker
  - Settings-Seite für Search Terms

- **Backend API Endpoints**:
  - `/api/signals/scan` - Technische Signale
  - `/api/opportunities` - Earnings Opportunities  
  - `/api/chart-analysis/{ticker}` - Chart Analyse
  - `/api/google-news/scan` - Google News Scanner
  - `/api/watchlist/enriched` - Watchlist mit Deltas
  - `/api/data/sparkline/{ticker}` - Mini-Charts
  - `/api/news/scan-weekend` - Wochenend-News

### 🛠️ Verbesserungen
- Redis Cache Layer für yfinance, Market Overview, Google News
- n8n Workflows für vollautomatisierte Pipelines
- Score-History Tabelle für Delta-Tracking
- Contrarian Opportunities Scanner
- Enhanced Error Handling mit HTML Escaping

### 🐛 Bugfixes
- **Kritisch**: Variable `lt_memory` nicht definiert in `report_generator.py` → behoben
- **Kritisch**: Fehlender Platzhalter `{{contrarian_setups}}` in Morning Briefing → behoben  
- **Kritisch**: Circular Import Risk `report_generator.py` ↔ `main.py` → eliminiert
- **Wichtig**: Fehlender Import `get_bullet_points` in `main.py` → hinzugefügt
- **Wichtig**: HTML Escaping für Telegram-Nachrichten → implementiert
- **Wichtig**: Fehlender API Endpoint `/api/news/scan-weekend` im Frontend → ergänzt
- **Wichtig**: Supabase Schema Consistency für `short_term_memory` → Migration erstellt

### 📊 Datenbank
- Neue Tabelle: `score_history` für Score-Delta-Tracking
- Neue Tabelle: `custom_search_terms` für Google News Keywords
- Migration: `short_term_memory` +5 Spalten für Narrative Intelligence
- Indexe für Performance optimiert

### 🔄 Automatisierung (n8n)
- News-Pipeline: Mo-Fr 13:00-22:30 (alle 30min)
- Wochenend-News: Sa-So 10/14/18/22 Uhr  
- Morning Briefing: Mo-Fr 08:00 Uhr
- Sonntags-Report: Sonntag 19:00 Uhr
- Post-Earnings Review: Mo-Fr 22:00 Uhr

### 📚 Dokumentation
- README.md komplett überarbeitet
- Migration SQL in `database/migrations/`
- API-Dokumentation aktualisiert
- Quick Start Guide hinzugefügt

---

## [3.0] - 2026-03-10 - Feedback Loop & Web Dashboard

### 🚀 Neue Features
- Langzeit-Gedächtnis für persistente Insights
- Post-Earnings Reviews mit Performance Tracking
- Next.js Web Dashboard mit Bloomberg-Terminal Design
- Daily Snapshots für Regime-Erkennung
- n8n Workflow Automatisierung

### 🐛 Bugfixes
- FRED Fallback für lückenlose Makro-Daten
- Platzhalter-Dynamik in Reports
- Error Handling für einzelne API-Fehler

---

## [2.0] - 2026-03-05 - Real-Time Monitoring & Alerts

### 🚀 Neue Features  
- FinBERT Sentiment Analyse
- News Pipeline mit Finnhub Integration
- SEC Edgar Scanner
- Narrative Intelligence Modul
- Globaler Wirtschaftskalender
- Options & Social Sentiment Analyse
- Torpedo Monitor

### 🐛 Bugfixes
- 5 kritische Fixes für Makro-Daten
- Prompt-Resilience verbessert

---

## [1.0] - 2026-02-28 - Foundation

### 🚀 Initiale Features
- FastAPI Backend Setup
- Supabase Datenbank Integration
- Finnhub & FMP API Integration
- FRED Makro-Daten
- DeepSeek KI Integration
- Telegram Bot Alerts
- Admin Panel UI
- Weekly Audit Reports
