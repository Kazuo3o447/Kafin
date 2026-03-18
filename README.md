# Kafin Trading Platform

Eine KI-gestützte Earnings-Trading-Plattform mit fortgeschrittener Signal Intelligence.

## 🚀 Phase 4: Signal Intelligence (Abgeschlossen)

### Neue Features
- **Smart Alerts**: RSI, Volumen, SMA & Score-basierte Signale
- **Opportunity Scanner**: Automatische Earnings-Setup-Erkennung  
- **Chart Analyst**: DeepSeek technische Analyse mit konkreten Levels
- **Google News Integration**: Dynamische News aus Watchlist + Custom Keywords
- **Delta Tracking**: Score-Veränderungen über Zeit
- **Narrative Intelligence**: Erkennung fundamentaler Unternehmensänderungen

### Frontend Erweiterungen
- Dashboard mit Watchlist Heatmap (Deltas, Sparklines, Earnings Countdown)
- Opportunity-Sektion mit Top Earnings-Setups
- Sektor-Konzentrations-Warnungen
- News-Seite mit Google News & Signals Tabs
- Chart-Analyse-Button pro Ticker
- Settings-Seite für Custom Search Terms

### Backend Erweiterungen
- **Neue API Endpoints**:
  - `/api/signals/scan` - Technische Signale
  - `/api/opportunities` - Earnings Opportunities
  - `/api/chart-analysis/{ticker}` - Chart Analyse
  - `/api/google-news/scan` - Google News Scanner
  - `/api/watchlist/enriched` - Watchlist mit Deltas
  - `/api/data/sparkline/{ticker}` - Mini-Charts
  - `/api/news/scan-weekend` - Wochenend-News

### Automatisierung (n8n)
- **News-Pipeline**: Mo-Fr 13:00-22:30 (alle 30min)
- **Wochenend-News**: Sa-So 10/14/18/22 Uhr
- **Morning Briefing**: Mo-Fr 08:00 Uhr
- **Sonntags-Report**: Sonntag 19:00 Uhr
- **Post-Earnings Review**: Mo-Fr 22:00 Uhr

## 📊 Plattform-Setup
- [x] Backend Projekt-Shell
- [x] Konfigurations-Management (settings.yaml, .env)
- [x] Zentraler structslog Logger mit In-Memory-Buffer
- [x] Admin-Panel UI (/admin)
- [x] Supabase Datenbank-Integration
- [x] FastAPI Backend mit CORS
- [x] Next.js Frontend mit Tailwind CSS
- [x] Docker Containerisierung
- [x] n8n Workflow Automatisierung
- [x] Redis Cache Layer
- [x] Signal Intelligence Features

## 🛠️ Quick Start

```bash
# 1. Supabase Migration ausführen (wichtig!)
# Siehe: database/migrations/add_narrative_shift_columns.sql

# 2. Backend starten
docker-compose up -d kafin-backend

# 3. Frontend starten (optional)
docker-compose up -d kafin-frontend

# 4. n8n Dashboard
# http://localhost:5678 (admin/changeme)
```

## 📚 Dokumentation
- `Plattform-Spezifikation-v2.md` - Detaillierte Spezifikation
- `database/schema.sql` - Datenbank-Schema
- `prompts/` - KI-Prompt-Templates
- `database/migrations/` - Schema-Migrationen

## 🔧 Konfiguration
- `.env` - API Keys und Secrets
- `config/settings.yaml` - Plattform-Einstellungen
- `config/apis.yaml` - API-Konfiguration

## 🐛 Bugfixes (Latest Release)
- Variable `lt_memory` nicht definiert → behoben
- Circular Import Risk → eliminiert  
- HTML Escaping für Telegram → hinzugefügt
- Fehlende API Endpoints → ergänzt
- Supabase Schema Consistency → Migration erstellt

---

**Version**: 4.0 - Signal Intelligence Complete  
**Letztes Update**: 2026-03-18
