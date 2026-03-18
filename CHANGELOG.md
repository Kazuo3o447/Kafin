# Kafin Changelog

Alle wichtigen Änderungen, Bugfixes und Features nach Version.

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
