# CHANGELOG

Alle wichtigen Änderungen am Kafin Projekt werden hier dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de-DE/1.0.0/)
und dieses Projekt hält sich an [Semantic Versioning](https://semver.org/lang/de/).

## [5.0.0] - 2026-03-18

### Added
- **Client-Side Navigation Caching** - Modul-level Map Cache mit TTL
- **CacheStatus Komponente** - UI Indikator für Cache-Alter und Refresh
- **cachedFetch Utility** - Wrapper für API-Calls mit Caching
- **Intelligente Cache-Invalidierung** - Bei manuellen Aktionen
- **Performance Optimierung** - Sofortige Seitenwechsel

### Frontend Changes
- `frontend/src/lib/clientCache.ts` - Cache-Modul
- `frontend/src/components/CacheStatus.tsx` - UI Komponente
- Dashboard Integration mit Cache-Status
- Watchlist Cache-Invalidierung bei add/remove
- News Cache-Invalidierung bei Scans
- Performance Seite mit 5-minütiger Cache

### Backend Changes
- Keine Breaking Changes
- Bestehende API Endpoints bleiben unverändert

### Performance
- Seitenwechsel ohne API-Latenz bei Cache-Hit
- Reduzierte Server-Last durch Caching
- Bessere User Experience bei Navigation

### Documentation
- README.md mit Phase 5 Details
- ARCHITECTURE_COMPLETE.md mit vollständiger Architektur
- SPEC_COMPLETE.md mit detaillierter Spezifikation

## [4.0.0] - 2026-03-18

### Added
- **Signal Intelligence Engine** - Technische Signale (RSI, Volumen, SMA)
- **Opportunity Scanner** - Earnings-Setup-Erkennung
- **Chart Analyst** - DeepSeek technische Analyse
- **Google News Integration** - Watchlist-basierte News
- **Narrative Shift Detection** - Fundamentale Veränderungen
- **Shadow Portfolio** - Papiertrading mit Live-Daten

### Frontend Changes
- Dashboard mit Watchlist Heatmap und Sparklines
- News Seite mit Google News & Signals Tabs
- Performance Seite mit Track Record & Shadow Portfolio
- Earnings Radar Seite
- Command Palette (Cmd+K) für Quick Search
- Settings Seite für Custom Search Terms

### Backend Changes
- Neue API Endpoints:
  - `/api/signals/scan` - Technische Signale
  - `/api/opportunities` - Earnings Opportunities
  - `/api/chart-analysis/{ticker}` - Chart Analyse
  - `/api/google-news/scan` - Google News Scanner
  - `/api/shadow/portfolio` - Shadow Portfolio
- Shadow Portfolio Tabellen in Datenbank
- DeepSeek Integration für technische Analyse

### Database Changes
- `shadow_trades` Tabelle für Papiertrading
- `narrative_shifts` Tabelle für Narrative Changes
- `signal_alerts` Tabelle für technische Signale

### Automation
- n8n Workflows für News Pipeline
- Morning Briefing Automatisierung
- Post-Earnings Review Automatisierung
- Sunday Report Automatisierung

## [3.0.0] - 2026-03-15

### Added
- **Delta Tracking** - Score-Veränderungen über Zeit
- **Sektor-Konzentrations-Warnungen**
- **Earnings Countdown Timer**
- **Enriched Watchlist API**
- **Mini-Charts (Sparklines)**

### Frontend Changes
- Watchlist Heatmap mit Deltas
- Sektor-Verteilungs-Anzeige
- Earnings Countdown pro Ticker
- Sparkline Charts im Dashboard

### Backend Changes
- `/api/watchlist/enriched` Endpoint
- `/api/data/sparkline/{ticker}` Endpoint
- Delta-Berechnung in Watchlist Service
- Sektor-Analyse Logik

### Performance
- Optimierte Watchlist Queries
- Parallele API Calls im Dashboard
- Reduzierte Ladezeiten

## [2.0.0] - 2026-03-12

### Added
- **Morning Briefing Generator** - Täglicher Marktkommentar
- **Post-Earnings Review** - Automatische Analyse nach Quartalsberichten
- **Report Archive** - Historische Reports
- **Telegram Integration** - Report Versand

### Backend Changes
- `/api/reports/latest` Endpoint
- `/api/reports/generate` Endpoint
- DeepSeek Integration für Reports
- Report Template System

### Automation
- Daily Morning Briefing (08:00)
- Post-Earnings Review (22:00)
- Sunday Report (19:00)

### Database Changes
- `audit_reports` Tabelle
- `earnings_reviews` Tabelle

## [1.0.0] - 2026-03-10

### Added
- **Initial Release** - Basis Plattform
- Next.js 15 Frontend mit Tailwind CSS
- FastAPI Backend mit Supabase
- Docker Containerisierung
- Basis Watchlist Management
- Market Data Integration (Finnhub)
- Admin Panel UI

### Features
- Watchlist CRUD Operations
- Basic Market Overview
- Company Profile Pages
- Settings Management
- User Authentication

### Infrastructure
- Docker Compose Setup
- Redis Cache Layer
- n8n Automation Basis
- Structured Logging
- Error Handling

### Database
- Supabase Integration
- Basis Schema
- Watchlist Tabelle
- User Management

## [0.9.0] - 2026-03-08

### Added
- **Project Setup** - Initial Projektstruktur
- Development Environment
- Basis Dependencies

### Infrastructure
- Git Repository
- Docker Basis-Images
- Development Scripts
- Documentation Structure

---

## Versionierungs-Schema

- **MAJOR**: Breaking Changes, neue Hauptfunktionen
- **MINOR**: Neue Features, abwärtskompatible Änderungen
- **PATCH**: Bugfixes, kleine Verbesserungen

## Release-Prozess

1. **Development** - Feature Branches
2. **Testing** - Unit & Integration Tests
3. **Documentation** - README & API Docs
4. **Release** - Git Tag & Release Notes
5. **Deployment** - Docker Compose Update

---

**Version**: 5.0.0  
**Letztes Update**: 2026-03-18
