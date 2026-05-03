# Watchlist System Documentation

## Overview
Die Watchlist ist ein zentrales Feature des Kafin Trading Systems, das technische Indikatoren, Preisdaten und Metadaten für eine ausgewählte Liste von Aktien anzeigt.

## Architektur

### Backend (FastAPI)
- **Endpoint:** `/api/watchlist/enriched`
- **Router:** `backend/app/routers/watchlist.py`
- **Cache:** Redis (5 Minuten TTL, 10 Sekunden bei Earnings)

### Frontend (Next.js)
- **Page:** `frontend/src/app/watchlist/page.tsx`
- **API Client:** `frontend/src/lib/api.ts`
- **Cache:** Client-seitig mit `lib/clientCache.ts`

## Datenquellen

### 1. Preisdaten (Alpaca - Primär)
- Real-time Snapshots via Alpaca API
- Bid/Ask Spreads, Volume, Pre/Post-Market
- Fallback: yfinance wenn Alpaca nicht verfügbar

### 2. Technische Indikatoren (yfinance)
- **RSI (14):** Relative Strength Index
- **Trend:** Basierend auf 20-Tage SMA
- **5D Change:** 5-Tage Performance
- **SMA50:** 50-Tage Simple Moving Average
- **ATR14:** Average True Range (Volatilität)
- **RVOL:** Relative Volume (20-Tage Durchschnitt)

### 3. Metadaten
- **Company Info:** Namen, Sektoren, Industries
- **Earnings:** Datum, Countdown, Timing
- **Watchlist Metrik:** Tage seit Hinzufügung

## Datenfluss

```
Frontend Request → API Endpoint → 
1. Alpaca Batch Snapshots (Preise)
2. yfinance History (Technische Indikatoren) 
3. Database Query (Watchlist Daten)
4. Enrichment (Kombination aller Daten)
5. Cache Storage → Frontend Response
```

## Features

### Technische Indikatoren (ohne KI)
- **RSI:** Überverkauft (>70) / Überkauft (<30)
- **Trend:** Bullish (>SMA20) / Bearish (<SMA20) / Neutral (=SMA20)
- **5D Performance:** Prozentsatz der letzten 5 Tage
- **SMA50:** Vergleich mit 50-Tage Durchschnitt
- **ATR14:** Volatilitätsmaß
- **RVOL:** Relatives Volumen

### Watchlist Metriken
- **📅 X Tage:** Tage seit Hinzufügung zur Watchlist
- **Berechnung:** `heute - added_date`
- **Anzeige:** Im Namen-Bereich mit Kalender-Icon

### Visualisierung
- **Farbcodierung:** Rot/Grün für Performance
- **Mini-Balken:** Opportunity/Torpedo Scores (wenn verfügbar)
- **Icons:** ⚡ Earnings, ✗SMA unter SMA50, 📅 Tage auf Watchlist

## Caching Strategie

### Backend Cache (Redis)
- **Key:** `watchlist:enriched:v2`
- **TTL:** 300 Sekunden (Standard)
- **Earnings Mode:** 10 Sekunden TTL wenn Earnings heute
- **Invalidierung:** Manuel oder bei Datenänderungen

### Frontend Cache
- **Key:** `watchlist:enriched`
- **TTL:** 4 Minuten
- **Background Refresh:** Automatisch bei Cache-Alter

## Datenbank Schema

### watchlist Tabelle
```sql
CREATE TABLE watchlist (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    company_name VARCHAR(255),
    sector VARCHAR(100),
    industry VARCHAR(100),
    added_date TIMESTAMP DEFAULT NOW(),
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    web_prio INTEGER,
    cross_signals JSONB
);
```

### Enrichment Fields (Runtime)
- Technische Indikatoren werden live berechnet
- Preisdaten von Alpaca/yfinance
- Keine Persistierung von transienten Daten

## Performance Optimierung

### Batch Processing
- **Alpaca Snapshots:** Alle Ticker in einem Request
- **yfinance History:** 60-Tage für alle Indikatoren
- **Async Processing:** Parallele Datenabfrage

### Error Handling
- **Fallback:** yfinance wenn Alpaca fehlschlägt
- **Graceful Degradation:** Technische Indikatoren optional
- **Timeout Protection:** 30 Sekunden pro Ticker

## Configuration

### Environment Variables
```bash
# Alpaca API
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret

# Redis Cache
REDIS_URL=redis://localhost:6379

# Database
DATABASE_URL=postgresql://user:pass@localhost/kafin
```

### Docker Services
```yaml
kafin-frontend:
  build: ./frontend
  ports:
    - "3000:3000"
  environment:
    INTERNAL_API_URL: http://kafin-backend:8000

kafin-backend:
  build: ./backend
  ports:
    - "8000:8000"
  depends_on:
    - postgres
    - redis
```

## API Endpoints

### GET /api/watchlist/enriched
```json
{
  "watchlist": [
    {
      "ticker": "CRM",
      "company_name": "Salesforce Inc.",
      "sector": "Technology",
      "price": 184.06,
      "change_pct": -5.75,
      "change_5d_pct": -5.82,
      "rsi": 40.2,
      "trend": "bearish",
      "above_sma50": false,
      "atr_14": 7.95,
      "rvol": 0.64,
      "days_on_watchlist": 2,
      "added_date": "2026-03-22T17:47:12.212944"
    }
  ],
  "concentration_warning": null,
  "sector_distribution": {
    "Technology": 4,
    "Healthcare": 2,
    "Finance": 2
  }
}
```

## Troubleshooting

### Häufige Probleme
1. **Keine technischen Indikatoren:** yfinance API nicht erreichbar
2. **Veraltete Preise:** Alpaca API Limit überschritten
3. **Cache Probleme:** Redis nicht verbunden

### Debug Commands
```bash
# Backend Logs
docker logs kafin-backend --tail 50

# Cache Status
docker exec kafin-backend redis-cli info memory

# API Test
curl http://localhost:8000/api/watchlist/enriched
```

## Future Enhancements

### Geplante Features
- **Real-time WebSocket:** Live Preis-Updates
- **Custom Alerts:** Benachrichtigungen bei Schwellenwerten
- **Portfolio Integration:** Watchlist mit Shadow Trades verbinden
- **Advanced Indicators:** MACD, Bollinger Bands, etc.

### Performance
- **Database Indexing:** Optimierung für große Watchlists
- **CDN Integration:** Frontend Asset Caching
- **Microservices:** Trennung von Preis- und Indikator-Berechnung

## Dependencies

### Backend
- `fastapi` - Web Framework
- `yfinance` - Marktdaten
- `alpaca-py` - Real-time Daten
- `redis` - Caching
- `asyncpg` - PostgreSQL Driver
- `pandas` - Datenverarbeitung

### Frontend
- `nextjs` - React Framework
- `lucide-react` - Icons
- `tailwindcss` - Styling
- `moment` - Datum/Zeit

## Security

### API Keys
- Alpaca Keys in Environment Variables
- Rate Limiting für API Calls
- Input Validation für Ticker-Symbole

### Data Privacy
- Keine persönlichen Daten in Cache
- GDPR-konforme Datenverarbeitung
- Anonymisierte Logging

## Monitoring

### Metrics
- API Response Times
- Cache Hit Rates
- Error Rates per Data Source
- User Session Duration

### Alerts
- API Key Expiration
- Cache Memory Usage
- Database Connection Issues
- High Error Rates

---

*Letzte Aktualisierung: 24.03.2026*
*Version: 1.0.0*
