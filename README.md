# Kafin Trading Platform

Eine KI-gestützte Earnings-Trading-Plattform mit fortgeschrittener Signal Intelligence und modernem Dark Mode Dashboard.

## 🚀 Aktuelle Features (März 2026)

### Core Funktionalität
- **Watchlist Management**: Hinzufügen/Entfernen von Tickern mit automatischer Datenanreicherung
- **Real-time News**: FinBERT-gestützte Sentiment-Analyse mit Material-Event-Detection
- **Chart Intelligence v6.2.0**: Immer sichtbare Begründungen + ETF/Index-Unterstützung
- **KI-Analysen**: Groq (News-Extraktion) + DeepSeek (Reports) mit optimierter Modell-Matrix
- **Modular Architecture v6.2.0**: Fachlich getrennte API-Router für bessere Wartbarkeit
- **PostgreSQL 16 + pgvector**: Lokale Vektordatenbank für semantische Suche (RAG)
- **API Usage Tracking**: Echtzeit-Token-Counter und Call-Limits für alle APIs
- **Pre/After-Market Briefing**: Tägliche Briefings 08:00 und 22:15 CET (ersetzt Sunday Report)
- **System Monitoring**: Live Status Dashboard mit Service-Health und Latenz-Tracking
- **Persistent Logging**: RotatingFileHandler mit Docker-Volume-Persistenz

### AI/ML Stack (festgelegt — Stand März 2026)
- **Report-Generierung (komplex)**: `deepseek-reasoner` (DeepSeek API)
- **Chat / Kurzanalysen**: `deepseek-chat` (DeepSeek API)  
- **News-Extraktion (schnell)**: `llama-3.1-8b-instant` (Groq API)
- **Sentiment-Analyse**: FinBERT (lokal)

### Datenquellen (kostenlos + unlimitiert)
- **FMP**: Finanzkennzahlen, Earnings, Analyst-Grades
- **Finnhub**: News, Short Interest, Insider-Transaktionen
- **yfinance**: Kursdaten, technische Indikatoren, Fallback Earnings
- **FRED**: Makro-Daten (VIX, Yield Curve, Fed Funds, etc.)
- **Reddit Monitor**: Retail Sentiment (gecacht 1h)
- **Fear & Greed Index**: CNN Money Makro-Kontext
- **FINRA**: Short Volume Ratio (täglich)
- **Tavily**: Web-Enrichment Fallback (Budget-kontrolliert)

### Scoring System v6.2.0
- **Data Completeness Tracking**: Automatische Erkennung fehlender Datenpunkte
- **Confidence Gates**: Keine Trade-Empfehlungen bei <50% Datenlage
- **Multi-Source Fallbacks**: yfinance → Reddit → Web-Enrichment
- **Recency-Weighted Grades**: Analysten-Updates nach Datum sortiert
- **Macro Headwind**: VIX + Fear & Greed + Consumer Sentiment
- **Price Target Upside**: Analyst-Konsens als Rückenwind-Signal

### Chart Analysis Overhaul (v6.1.6)
- **Immer sichtbare Begründungen**: why_entry/why_stop/trend_context ohne Akkordeon-Klick
- **ETF/Index Research**: SPY/QQQ/IWM/DXY mit Asset-Type-Badges und Research-Links
- **Vollständige Audit-Prompts**: DeepSeek erhält alle Chart-Begründungen für qualitativ bessere Reports
- **Token-Optimierung**: max_tokens 2048 mit expliziten Anweisungen für vollständige Sätze

### UI/UX Highlights
- **Modern Dark Mode**: Konsistentes Design mit CSS-Variablen für alle 45+ Karten
- **2-Spalten News-Layout**: Kein Tab-Wechsel mehr nötig - alle Daten gleichzeitig sichtbar
- **Automatische Charts**: Direkte Anzeige auf Ticker-Detailseiten ohne Button-Klick
- **Verbessertes Modal**: Ticker-Hinzufügen mit Validierung, Loading-States und Error-Feedback
- **Responsive Design**: Optimiert für Desktop mit festen Spaltenbreiten und flexiblen Inhaltsbereichen
- **Hacker Terminal**: Isoliertes Live-Log-Terminal mit Grep-Suche, Auto-Scroll und Syntax-Highlighting
- **Status Dashboard**: Echtzeit-Überwachung aller Backend-Services mit Fehler-Codes und Latenz-Metriken

### Data Sources
- **Marktdaten**: yfinance (Kurse, Volumen, Indikatoren)
- **News**: Finnhub (Company & General News), Google News Integration
- **Makro**: FRED (VIX, Zinsen, Rohstoffe), Finnhub Economic Calendar
- **Regulatorisch**: SEC EDGAR (Form 8-K, 4) für Insider-Transaktionen
- **Sentiment**: FinBERT für deutsche/englische News-Analyse

### Letzte Fixes (23.03.2026)
- **Frontend JSON Errors**: Behoben von `JSON.parse: unexpected character` Fehlern in Module Status und Diagnostics durch Implementierung von `fetchJsonSafe` Helper.
- **Research Page Crash**: Guard für `quarterly_history` hinzugefügt um NU Research Dashboard Abstürze bei fehlenden Daten zu verhindern.
- **Backend Coroutine Warnings**: Alle `coroutine was never awaited` Warnungen in FMP, Finnhub und Ticker Resolver gefixt.
- **DateTime UTC Normalization**: FinBERT Pipeline Logging Errors mit offset-naive/aware datetime subtraction behoben.
- **Font Rendering Issues**: Inter Font-Konfiguration verbessert mit expliziten weights, display:swap und system-ui fallbacks um `glyf: empty gid` Warnungen zu beheben.
- **CRCL Research Data Fix**: Key-Mismatch zwischen Backend (`history`) und Frontend (`quarterly_history`) behoben. yfinance Fallback für neue/IPO-Ticker wie CRCL funktioniert jetzt korrekt und zeigt Earnings-Daten an.
- **Signal Feed**: Root-Page zeigt jetzt den Signal Feed als neues Dashboard, inklusive Settings-Tab für die Feed-Konfiguration.
- **Markets Dashboard**: Marktübersicht, Marktbreite, Intermarket, Fear & Greed, Economic Calendar und Market Audit sind wieder als API-Quellen erreichbar.
- **Frontend-API**: Browser-Requests laufen standardmäßig über relative `/api/...`-Pfade, damit lokale Dev-Setups nicht an Port-Mismatches hängen.
- **Chart/Visualisierung**: `VolumeProfile` und Ticker-Aktionsbuttons nutzen jetzt die robuste API-Routing-Schicht statt harter Host-URLs.
- **Legacy Cleanup**: Veraltete Chart-Route unter `watchlist/[ticker]` wurde entfernt.

## 🛠️ Quick Start

### Voraussetzungen
- Docker und Docker Compose
- **Alle API Keys konfiguriert** (siehe `.env.example`)
- **KEINE Mock-Daten**: `USE_MOCK_DATA=false` zwingend erforderlich
- **Funktionierende API-Keys**: Finnhub, FMP, FRED, etc.

### Installation

```bash
# 1. Repository klonen
git clone https://github.com/Kazuo3o447/Kafin.git
cd Kafin

# 2. Umgebungsvariablen konfigurieren
cp .env.example .env
# WICHTIG: Alle API Keys eintragen und USE_MOCK_DATA=false belassen

# 3. Backend starten
docker-compose up -d kafin-backend

# 4. Frontend starten
docker-compose build kafin-frontend
docker-compose up -d kafin-frontend

# 5. n8n Dashboard (optional für Automatisierung)
# http://localhost:5678 (admin/changeme)
```

### Zugriffe
- **Web Dashboard**: http://localhost:3000
- **Signal Feed**: http://localhost:3000/ (neues Dashboard)
- **Markets Dashboard**: http://localhost:3000/markets
- **Briefing**: http://localhost:3000/briefing (Pre/After-Market Briefings)
- **Status Dashboard**: http://localhost:3000/status
- **Hacker Terminal**: http://localhost:3000/terminal
- **API Dokumentation**: http://localhost:8000/docs
- **n8n Workflows**: http://localhost:5678

### Frontend API-Hinweis
- Browser-Requests laufen im Frontend primär über relative `/api/...`-Pfade und werden per Next-Rewrite an das Backend weitergereicht.
- Lokale Default-API-Ziele sind auf `http://localhost:8000` ausgerichtet; `8001` ist nur für den Docker-Host-Port relevant.

## 📊 Plattform-Architektur

### Backend (FastAPI)
- **Zentraler Entrypoint**: `main.py` für App-Init und Router-Registrierung
- **Modulare Router**: Fachlich getrennte Logik in `backend/app/routers/`
- **Datenanreicherung**: yfinance, Finnhub, FRED, SEC EDGAR Integration
- **KI-Verarbeitung**: FinBERT Sentiment, DeepSeek Analysen, lokale Embeddings
- **Automatisierung**: n8n Workflow Integration
- **Logging**: RotatingFileHandler mit 10MB Limit, 5 Backups, persistente Docker-Volumes
- **Monitoring**: Diagnostics-Endpoint mit Latenz-Tracking und isolierter Fehlerbehandlung

### Frontend (Next.js 15)
- **Framework**: TypeScript, Tailwind CSS v4, App Router
- **Design-System**: Dark Mode mit CSS-Variablen
- **State Management**: React Hooks, Client-Side Caching
- **Charts**: Lightweight Charts mit Overlays und Markern

### Datenbank (PostgreSQL)
- **Local DB**: PostgreSQL 16 mit `pgvector` Erweiterung
- **Watchlist**: Ticker und Metadaten
- **News/Memory**: Stichpunkte mit Vektor-Embeddings für RAG
- **Reports**: Morning Briefings und Analysen
- **API Usage**: Historische Verbrauchsdaten

## 📚 Dokumentation

### Wichtige Dateien
- `STATUS.md` - Detaillierter Projektstatus und Meilensteine
- `ARCHITECTURE.md` - Technische Architektur
- `database/schema.sql` - Datenbank-Schema
- `docs/apis/` - API-Dokumentationen
- `prompts/` - KI-Prompt-Templates

### Konfiguration
- `.env` - API Keys und Secrets
- `config/settings.yaml` - Plattform-Einstellungen
- `config/apis.yaml` - API-Konfiguration
- `docker-compose.yml` - Container-Konfiguration

## � Automatisierung (n8n)

### Aktive Workflows
- **Pre-Market Briefing**: Mo-Fr 08:00 CET
- **After-Market Briefing**: Mo-Fr 22:15 CET (US-Markt-Schluss)
- **News-Pipeline**: Mo-Fr 13:00-22:30 (alle 30min)
- **Wochenend-News**: Sa-So 10/14/18/22 Uhr
- **Post-Earnings Review**: Mo-Fr 22:00 Uhr

## 🐛 Letzte Fixes (23. März 2026)
- **Pre/After-Market Briefing System**: Sunday Report ersetzt durch tägliche Briefings (08:00 + 22:15 CET)
- **Signal Feed Dashboard**: Komplett neues Dashboard mit 3-Schichten UI und Action Brief
- **Briefing Page**: Neue `/briefing` Seite mit Pre/After-Market Historie und manueller Generierung
- **Backend API**: Neue Endpoints `/api/reports/generate-after-market` und `/api/reports/briefing-archive`
- **Database Schema**: `after_market_summary` Spalte zu `daily_snapshots` hinzugefügt
- **Navigation**: Sidebar um "Briefing" Link erweitert
- **Snapshot Stabilität**: `daily_snapshots.date` wird jetzt als echtes `DATE` gespeichert; gestrige Snapshots funktionieren wieder ohne `toordinal`-Fehler.
- **Morning Briefing Fallbacks**: FMP-Ausfälle werden im Analysten-Abschnitt mit yfinance-Fallbacks ergänzt, damit Price-Target- und EPS-Daten nicht leer bleiben.

## 🐛 Letzte Fixes (22. März 2026)
- **Prompt Quality v6.1.4**: Alle TODO-Platzhalter implementiert (Max Pain, CEO, Mitarbeiter, Fear & Greed, etc.)
- **DeepSeek Modell-Matrix**: Reasoner für komplexe Tasks (Audit/Torpedo), Chat für schnelle (Morning/Weekly/Post-Earnings/Chart)
- **groq.py API-Key**: Aus settings statt module-level env für bessere Lazy-Load Performance
- **API Usage Tracking**: Redis-Puffer + PostgreSQL Aggregation mit Echtzeit-Token-Countern und Call-Limits

## 🐛 Letzte Fixes (20. März 2026)
- **Bugfix**: Report-Generierung schlug aufgrund von Timeouts (DeepSeek > 120s) und fehlenden Supabase-Spalten (`report_text`) fehl. Next.js Proxy und `httpx` Timeouts auf 300s (5min) angehoben und Insert-Schema für `audit_reports` korrigiert.
- **Bugfix**: 502 Bad Gateway / Timeout bei der Audit-Report Generierung behoben. Docker-Netzwerk-Routing repariert, indem `INTERNAL_API_URL` im Frontend-Container explizit auf `http://kafin-backend:8000` gesetzt wurde.
- **Bugfix**: httpx.ReadTimeout in Finnhub Earnings-Kalender API behoben (Timeout auf 30s erhöht)
- **Bugfix**: Dead `get_social_sentiment` Import aus Report-Generator entfernt
- **Feature**: Enhanced Log-System mit Error/Warning Filtern und Live-Zählern

## 🐛 Letzte Fixes (18. März 2026)
- Backend: Watchlist-Endpunkte mit optionalen Feldern robust gemacht
- Frontend: Dark Mode Design-System implementiert
- Frontend: News-Seite auf 2-Spalten-Layout umgestellt
- Frontend: Chart-Integration und Error-Handling verbessert
- Frontend: Watchlist-Modal UX überarbeitet

## 🚀 Nächste Schritte
- Performance-Optimierung und Caching-Strategien
- Erweiterte Chart-Analysen mit weiteren Indikatoren
- Mobile Responsive Views
- Additional Data Sources (Options, Social Sentiment)

---

**Version**: 6.2.0 - Pre/After-Market Briefing System & Signal Feed Dashboard
**Letztes Update**: 2026-03-23
**Status**: Production Ready
