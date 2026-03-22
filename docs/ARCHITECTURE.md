# Kafin Architektur

## System-Übersicht

Kafin ist eine quantitative Handelsplattform für Aktienanalyse und automatisierte Reports. Die Plattform besteht aus einem Backend (FastAPI), Frontend (Next.js) und Automation-Layer (n8n).

## Infrastruktur

### Hardware & Umgebung
- **Version**: v6.1.5
- **Umgebung**: production (Docker Swarm)
- **Hardware**: NUC i3 / 16GB RAM / ZimaOS
- **Container**: Backend (FastAPI) + Frontend (Next.js) + n8n
- **Datenbank**: PostgreSQL 16 + pgvector (lokal)
- **Cache**: Redis (Session + API Cache + Usage Buffer)

### Backend-Struktur (Modular)
Das Backend ist modular aufgebaut, um die monolithische `main.py` zu vermeiden:
- `app/main.py`: Zentraler Entrypoint, Middleware und Router-Registrierung.
- `app/routers/`: Fachlich getrennte Endpunkte (data, news, reports, watchlist, analysis, shadow, logs, system).
- `app/admin/`: Admin-Panel UI und Admin-spezifische API-Operationen.

### Docker-Architektur
```
kafin-frontend    → Next.js 16, React 18, TypeScript
kafin-backend     → FastAPI, Python 3.11, asyncio
kafin-redis       → Redis 7.x (Session + Cache)
kafin-n8n         → n8n Automation Platform
```

## Datenflüsse & APIs

### Marktdaten-Quellen (Real-time)
- **yfinance** — Preise, Technicals, Fundamentals
- **Finnhub** — News, Economic Calendar, Insider
- **FMP** — Financial Modeling Prep (Earnings)
- **FRED** — Makro-Indikatoren (Zinsen, spreads)
- **FinBERT** — Sentiment Analysis (DL-Model)
- **Google News RSS** — General News Feed
- **SEC EDGAR** — Filings, 8-K, 10-Q/K

### Verarbeitung & Storage
- **Daily Snapshots** — Preis- + Indikator-Status
- **Macro Snapshots** — FRED-Zeitreihen
- **Short-term Memory** — News + Sentiment
- **Audit Reports** — Generierte Berichte
- **Watchlist** — Benutzer-Ticker
- **Scoring History** — Opportunity/Torpedo Scores
- **API Usage** — Token-Counter + Call-Tracking (Redis + PostgreSQL)
- **Log Buffer** — In-Memory (letzten 500)

## Konfigurationspunkte

### Backend Config
- `config/scoring.yaml` — Score-Gewichtungen
- `config/.env` — API Keys, Supabase
- `backend/app/logger.py` — Module-Definition
- `docker-compose.yml` — Container-Setup
- `n8n/workflows/` — Automation-Definitionen

### Frontend Config
- `frontend/src/app/globals.css` — Design Tokens
- `frontend/src/lib/api.ts` — API-Client
- `frontend/next.config.ts` — Proxy + Build
- `frontend/src/components/` — UI-Komponenten
- `frontend/src/app/` — Seiten & API-Routes

## Feature-Matrix

### Core Features
- Marktdashboard (9 Kacheln)
- Watchlist + Research
- Earnings-Radar
- News-Feed + Sentiment
- Performance-Analyse
- Reports (PDF)

### Advanced Features
- Composite Regime Scoring
- Position Sizer (Risk)
- Expected Move Calculator
- Market Breadth Analysis
- Intermarket Signals
- Economic Calendar

### System Features
- Command Center (Settings)
- Module-Status Monitoring
- Log-Viewer (Global)
- API-Diagnostics
- Telegram-Integration
- Automated Reports

## Tech Stack

### Backend
- **Python 3.11** — Haupt-Sprache
- **FastAPI** — REST API Framework (Modular via APIRouter)
- **asyncio** — Asynchrone Verarbeitung
- **asyncpg** — Hochperformanter PostgreSQL Client
- **Transformers** — FinBERT ML-Model (lokal)
- **sentence-transformers** — all-MiniLM-L6-v2 für lokale Embeddings

### Frontend
- **React 18** — UI Framework
- **Next.js 16** — Full-Stack Framework
- **TypeScript** — Type Safety
- **TailwindCSS** — Styling
- **Lucide** — Icon Library

### Daten & Cache
- **PostgreSQL** — Haupt-Datenbank (via Supabase)
- **Redis** — Session + API Cache
- **In-Memory** — Log Buffer (500 entries)

### Automation
- **n8n** — Workflow Automation
- **Docker Swarm** — Container Orchestration
- **Telegram Bot** — Notifications

## Wichtige Pfade & Endpoints

### Frontend-Routen
- `/` — Marktdashboard
- `/markets` — Detaillierte Marktanalyse
- `/watchlist` — Watchlist Management
- `/research` — Stock Research
- `/earnings` — Earnings-Radar
- `/news` — News-Feed
- `/performance` — Performance-Analyse
- `/reports` — Berichte
- `/settings` — Command Center
- `/logs` — System-Logs (Live)

### API-Endpoints
- `/api/diagnostics/*` — Health-Checks
- `/api/logs/*` — Log-Management
- `/api/data/*` — Datenzugriff
- `/api/reports/*` — Report-Generierung
- `/api/news/*` — News-Verarbeitung

### Wichtige Dateien
- `docker-compose logs -f` — Container Logs
- `config/scoring.yaml` — Score-Konfiguration
- `backend/app/logger.py` — Logging-Konfiguration

## n8n Automation Zeitpläne

### Werktag (Mo-Fr)
- **08:00** — Morning Briefing (Watchlist)
- **13:00-22:30** alle 30 Min — News-Pipeline
- **22:00** — Sonntags-Report Vorbereitung

### Wochenende
- **Sa/So 10/14/18/22** — News-Pipeline
- **So 19:00** — Sonntags-Report (PDF)

### Kontinuierlich
- **alle 10 Min** — SEC EDGAR Scan

## Datenbank-Schema

### Haupttabellen
- `watchlist` — Benutzer-Ticker
- `daily_snapshots` — Tägliche Daten
- `macro_snapshots` — Makro-Daten
- `short_term_memory` — News/Sentiment
- `audit_reports` — Generierte Berichte

### Scoring & History
- `scoring_history` — Opportunity/Torpedo Scores
- `regime_history` — Markregime-Daten

## Monitoring & Logging

### Module-Status
- Real-time Status aller Backend-Module
- Letzte Aktivität pro Modul
- Error-Tracking mit Drilldown

### Log-Management
- In-Memory Buffer (letzten 500 entries)
- Log-Level Filterung (error/warning/info)
- Export-Funktion
- Auto-Clear Option

## Sicherheit & Performance

### API-Sicherheit
- Environment-basierte API Keys
- Rate Limiting (via Redis)
- CORS-Konfiguration
- Input Validation

### Performance
- Redis Caching für API-Aufrufe
- Batch-Processing für yfinance
- Asyncio für parallele Verarbeitung
- Optimierte Docker Images

## Entwicklung & Wartung

### Local Development
```bash
# Backend starten
cd backend && python -m uvicorn app.main:app --reload

# Frontend starten
cd frontend && npm run dev

# Docker Stack
docker-compose up -d
```

### Deployment
```bash
# Build & Deploy
docker-compose build
docker-compose up -d

# Logs überwachen
docker-compose logs -f
```

### Troubleshooting
- `/settings` → Command Center für System-Status
- `/logs` → Live Log-Viewer
- `docker-compose ps` → Container-Status
- `docker-compose logs <service>` → Service-Logs
