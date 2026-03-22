# Kafin Trading Platform

Eine KI-gestützte Earnings-Trading-Plattform mit fortgeschrittener Signal Intelligence und modernem Dark Mode Dashboard.

## 🚀 Aktuelle Features (März 2026)

### Core Funktionalität
- **Watchlist Management**: Hinzufügen/Entfernen von Tickern mit automatischer Datenanreicherung
- **Real-time News**: FinBERT-gestützte Sentiment-Analyse mit Material-Event-Detection
- **Chart Intelligence**: Interaktive Kurs-Charts mit SMA-Overlays und Event-Markern
- **KI-Analysen**: Groq (News-Extraktion) + DeepSeek (Reports) mit automatischem Fallback
- **Automatisierung**: n8n-Workflows für tägliche Briefings und wöchentliche Reports
- **System Monitoring**: Live Status Dashboard mit Service-Health und Latenz-Tracking
- **Persistent Logging**: RotatingFileHandler mit Docker-Volume-Persistenz

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
- **Status Dashboard**: http://localhost:3000/status
- **Hacker Terminal**: http://localhost:3000/terminal
- **API Dokumentation**: http://localhost:8000/docs
- **n8n Workflows**: http://localhost:5678

## 📊 Plattform-Architektur

### Backend (FastAPI)
- **API-Endpunkte**: RESTful APIs für Watchlist, News, Charts, Reports
- **Datenanreicherung**: yfinance, Finnhub, FRED, SEC EDGAR Integration
- **KI-Verarbeitung**: FinBERT Sentiment, DeepSeek Analysen
- **Automatisierung**: n8n Workflow Integration
- **Logging**: RotatingFileHandler mit 10MB Limit, 5 Backups, persistente Docker-Volumes
- **Monitoring**: Diagnostics-Endpoint mit Latenz-Tracking und isolierter Fehlerbehandlung

### Frontend (Next.js 15)
- **Framework**: TypeScript, Tailwind CSS v4, App Router
- **Design-System**: Dark Mode mit CSS-Variablen
- **State Management**: React Hooks, Client-Side Caching
- **Charts**: Lightweight Charts mit Overlays und Markern

### Datenbank (Supabase)
- **Watchlist**: Ticker und Metadaten
- **News**: Stichpunkte und Sentiment-Daten
- **Reports**: Morning Briefings und Analysen
- **Performance**: Tracking und Historie

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
- **Morning Briefing**: Mo-Fr 07:00 Uhr
- **News-Pipeline**: Mo-Fr 13:00-22:30 (alle 30min)
- **Wochenend-News**: Sa-So 10/14/18/22 Uhr
- **Sonntags-Report**: Sonntag 19:00 Uhr
- **Post-Earnings Review**: Mo-Fr 22:00 Uhr

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

**Version**: 6.0 - Dark Mode & UX Overhaul Complete  
**Letztes Update**: 2026-03-18  
**Status**: Production Ready
