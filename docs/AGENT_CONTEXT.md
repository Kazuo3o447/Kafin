# KAFIN — Agent Context

Dieses Dokument beschreibt den aktuellen Stand und die Architektur von Kafin für AI-Agenten.

---

## Aktuelle Version
**Version**: 5.8.0 (Watchlist: Trading-Werkzeug)
**Stand**: 2026-03-21

---

## Architektur-Überblick

### Backend (Python/FastAPI)
- **Docker Container**: `kafin-backend` auf Port 8000
- **API-Dokumentation**: http://localhost:8000/docs
- **Wichtige Module**:
  - `backend/app/data/market_overview.py` - Marktübersicht + Sektoren
  - `backend/app/data/finnhub.py` - News-Daten
  - `backend/app/analysis/finbert.py` - Sentiment-Analyse

### Frontend (Next.js/React)
- **Docker Container**: `kafin-frontend` auf Port 3000
- **Source-Mount**: `./frontend/src:/app/src` (Live-Reload)
- **API-Proxy**: `INTERNAL_API_URL=http://kafin-backend:8000`

### Datenquellen
- **Marktdaten**: Yahoo Finance (yfinance)
- **News**: Finnhub (Free Tier: 60 Calls/Min)
- **Sentiment**: FinBERT (lokal, transformers)

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

### Markets Dashboard v2 (/markets)
- **Granulare Refresh-Zyklen**: 9 Blöcke mit individuellen Intervallen
- **Vollständige UI**: Alle Datenblöcke mit Block-Labels und Timestamps
- **Sektoren Rotation-Story**: automatisch erkannt (Defensiv vs. Offensiv Gap > 2%)
- **VIX Term Structure**: Contango/Backwardation sichtbar
- **Info-Seite**: `/markets/info` mit vollständiger Dokumentation
- **Robuste Fehlerbehandlung**: BlockError-Komponenten + Fallback-Texte

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
