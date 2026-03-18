# Kafin Plattform-Spezifikation v2.0

## Vision

Kafin ist eine intelligente Trading-Plattform, die sich auf Earnings-basierte Strategien spezialisiert hat. Durch KI-gesteuerte Analyse und automatisierte Signal-Verarbeitung ermöglicht sie präzise Marktein- und ausstiege.

## Kernfunktionen

### 1. Watchlist Management
- **Ticker-Verwaltung**: Hinzufügen/Entfernen von Aktien
- **Enriched Data**: Scores, Deltas, technische Indikatoren
- **Sektor-Analyse**: Konzentrations-Warnungen
- **Earnings-Countdown**: Timer für nächste Quartalsberichte

### 2. Signal Intelligence
- **Technische Signale**: RSI, Volumen, SMA Crossovers
- **Opportunity Scanner**: Earnings-Setup-Erkennung
- **Narrative Shift Detection**: Fundamentale Veränderungen
- **Score-Tracking**: Opportunity/Torpedo Scores mit Delta

### 3. KI-Analyse
- **Chart Analyst**: DeepSeek technische Analyse
- **Morning Briefing**: Täglicher Marktkommentar
- **Post-Earnings Review**: Automatische Analyse nach Quartalsberichten
- **Shadow Portfolio**: Papiertrading für Strategie-Validierung

### 4. News & Events
- **Google News Integration**: Watchlist-basierte News-Aggregation
- **Event-Scanner**: SEC-Filings, Pressemitteilungen
- **Sentiment-Analyse**: Automatische Stimmungserkennung
- **Material Events**: Wichtige Unternehmensereignisse

### 5. Performance Tracking
- **Track Record**: Historische Performance-Statistiken
- **Accuracy-Messung**: Trefferquote der Vorhersagen
- **Best/Worst Calls**: Erfolgreichste und schlechteste Trades
- **Shadow Trading**: Simulierte Trades mit Live-Daten

## Technische Architektur

### Frontend (Next.js 15)
```
src/
├── app/                    # App Router Pages
│   ├── page.tsx           # Dashboard
│   ├── watchlist/         # Watchlist Management
│   ├── news/              # News & Signals
│   ├── performance/       # Track Record
│   └── earnings/          # Earnings Radar
├── components/            # Reusable Components
│   ├── CacheStatus.tsx    # Cache Indicator
│   ├── CommandPalette.tsx # Quick Search
│   └── sidebar.tsx        # Navigation
├── lib/                   # Utilities
│   ├── api.ts            # API Client
│   └── clientCache.ts    # Client-Side Caching
└── styles/               # Tailwind CSS
```

**Key Features**:
- Client-Side Caching mit TTL
- Responsive Design
- Real-time Updates
- Progressive Web App

### Backend (FastAPI)
```
backend/app/
├── main.py                # API Routes
├── data/                  # External APIs
│   ├── finnhub.py        # Market Data
│   ├── fmp.py            # Financial Metrics
│   ├── yfinance_data.py  # Technical Data
│   └── coinglass.py      # Crypto Data
├── analysis/             # AI Processing
│   ├── chart_analyst.py  # DeepSeek Analysis
│   ├── report_generator.py # Reports
│   ├── post_earnings_review.py # Reviews
│   └── shadow_portfolio.py # Shadow Trading
├── alerts/               # Signal Engine
│   ├── signal_scanner.py # Technical Signals
│   ├── opportunity_scanner.py # Setups
│   └── narrative_shift_detector.py # Changes
└── config.py             # Settings
```

**Key Features**:
- Async Processing
- Redis Caching
- Structured Logging
- Pydantic Validation

### Database (Supabase)
```sql
-- Core Tables
CREATE TABLE watchlist (
  id SERIAL PRIMARY KEY,
  ticker VARCHAR(10) NOT NULL,
  company_name TEXT,
  sector TEXT,
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE audit_reports (
  id SERIAL PRIMARY KEY,
  ticker VARCHAR(10) NOT NULL,
  report_content TEXT,
  analysis_date TIMESTAMP DEFAULT NOW(),
  model_version VARCHAR(20)
);

CREATE TABLE earnings_reviews (
  id SERIAL PRIMARY KEY,
  ticker VARCHAR(10) NOT NULL,
  quarter VARCHAR(10),
  year INTEGER,
  actual_eps DECIMAL(10,2),
  expected_eps DECIMAL(10,2),
  surprise_pct DECIMAL(5,2),
  review_content TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE shadow_trades (
  id SERIAL PRIMARY KEY,
  ticker VARCHAR(10) NOT NULL,
  trade_type VARCHAR(10), -- 'long' or 'short'
  entry_price DECIMAL(10,2),
  entry_date TIMESTAMP,
  exit_price DECIMAL(10,2),
  exit_date TIMESTAMP,
  status VARCHAR(20), -- 'open', 'closed'
  return_pct DECIMAL(5,2),
  notes TEXT
);

CREATE TABLE narrative_shifts (
  id SERIAL PRIMARY KEY,
  ticker VARCHAR(10) NOT NULL,
  previous_narrative TEXT,
  current_narrative TEXT,
  confidence_score DECIMAL(3,2),
  shift_date TIMESTAMP DEFAULT NOW(),
  sources TEXT[]
);

CREATE TABLE signal_alerts (
  id SERIAL PRIMARY KEY,
  ticker VARCHAR(10) NOT NULL,
  signal_type VARCHAR(50), -- 'rsi', 'volume', 'sma', etc.
  signal_value DECIMAL(10,2),
  threshold DECIMAL(10,2),
  alert_date TIMESTAMP DEFAULT NOW(),
  is_active BOOLEAN DEFAULT TRUE
);
```

## API-Spezifikation

### Market Data Endpoints
```python
GET /api/data/macro
Response: {
  "regime": "RISK_ON",
  "fed_rate": 5.25,
  "vix": 18.5,
  "credit_spread_bps": 120,
  "yield_curve_10y_2y": 0.8,
  "dxy": 104.2
}

GET /api/data/market-overview
Response: {
  "indices": {
    "SPY": {"price": 450.25, "change_1d_pct": 0.8, "rsi_14": 65.2},
    "QQQ": {"price": 380.15, "change_1d_pct": 1.2, "rsi_14": 70.1}
  },
  "sector_ranking_5d": [
    {"symbol": "XLK", "name": "Technology", "perf_5d": 3.2},
    {"symbol": "XLE", "name": "Energy", "perf_5d": -1.8}
  ],
  "macro": {
    "TLT": {"price": 98.5, "change_1d_pct": -0.3},
    "GLD": {"price": 185.2, "change_1d_pct": 0.5}
  }
}

GET /api/data/sparkline/{ticker}?days=7
Response: {
  "data": [
    {"date": "2026-03-12", "price": 145.20},
    {"date": "2026-03-13", "price": 146.80},
    {"date": "2026-03-14", "price": 147.50}
  ]
}
```

### Watchlist Endpoints
```python
GET /api/watchlist
Response: [
  {
    "ticker": "AAPL",
    "company_name": "Apple Inc.",
    "sector": "Technology",
    "notes": "Strong Q4 earnings expected",
    "opportunity_score": 7.2,
    "torpedo_score": 3.1,
    "opp_delta": 0.5,
    "torp_delta": -0.2
  }
]

GET /api/watchlist/enriched
Response: {
  "watchlist": [...],
  "concentration_warning": "60% of watchlist in Technology sector",
  "sector_distribution": {
    "Technology": 6,
    "Healthcare": 2,
    "Finance": 2
  }
}

POST /api/watchlist
Request: {
  "ticker": "NVDA",
  "company_name": "NVIDIA Corporation",
  "sector": "Technology",
  "notes": "AI chip demand"
}

DELETE /api/watchlist/{ticker}
Response: {"message": "Ticker removed from watchlist"}
```

### Analysis Endpoints
```python
GET /api/chart-analysis/{ticker}
Response: {
  "ticker": "AAPL",
  "current_price": 175.50,
  "technical_setup": {
    "trend": "BULLISH",
    "rsi_14": 68.5,
    "sma_50": 172.30,
    "sma_200": 165.80,
    "high_52w": 198.23,
    "low_52w": 124.17
  },
  "analysis": "Strong bullish momentum with RSI approaching overbought levels...",
  "key_levels": {
    "support": [172.00, 168.50, 165.00],
    "resistance": [178.00, 182.50, 185.00]
  },
  "recommendation": "HOLD",
  "confidence": 0.75
}

GET /api/opportunities
Response: [
  {
    "ticker": "NFLX",
    "name": "Netflix Inc.",
    "sector": "Communication Services",
    "market_cap_b": 245.6,
    "price": 485.20,
    "rsi": 45.2,
    "volatility": 28.5,
    "interest_score": 8.7,
    "earnings_date": "2026-04-18",
    "analysis": "High volatility setup with earnings in 2 weeks..."
  }
]

POST /api/signals/scan
Response: {
  "signals_found": 15,
  "signals": [
    {
      "ticker": "AAPL",
      "signal_type": "rsi_oversold",
      "signal_value": 28.5,
      "threshold": 30.0,
      "alert_text": "RSI oversold - Potential bounce setup"
    }
  ]
}
```

### Performance Endpoints
```python
GET /api/performance
Response: [
  {
    "period": "2026-03",
    "total_reviews": 45,
    "correct_predictions": 32,
    "accuracy_pct": 71.1,
    "best_call_ticker": "NVDA",
    "best_call_return": 12.5,
    "worst_call_ticker": "META",
    "worst_call_return": -8.3
  }
]

GET /api/shadow/portfolio
Response: {
  "summary": {
    "total_trades": 28,
    "win_rate": 0.68,
    "avg_return_pct": 3.2,
    "total_return_pct": 89.6,
    "sharpe_ratio": 1.45
  },
  "open_trades": [
    {
      "ticker": "AAPL",
      "trade_type": "long",
      "entry_price": 172.50,
      "entry_date": "2026-03-10",
      "current_price": 175.50,
      "return_pct": 1.74,
      "days_held": 8
    }
  ],
  "closed_trades": [...]
}
```

### Reports Endpoints
```python
GET /api/reports/latest
Response: {
  "report": "Morning Market Briefing...\n\nMarket Overview:\n- S&P 500 showing strength...",
  "generated_at": "2026-03-18T08:00:00Z",
  "model_version": "deepseek-chat-v3"
}

POST /api/reports/generate
Response: {
  "message": "Report generation started",
  "task_id": "report_20260318_0800"
}
```

## Client-Side Caching Strategie

### Cache Keys & TTLs
```typescript
// Dashboard
'dashboard:macro'          // TTL: 120s
'dashboard:overview'       // TTL: 120s
'dashboard:report'         // TTL: 60s
'dashboard:watchlist'      // TTL: 60s
'dashboard:opportunities'  // TTL: 120s

// Watchlist
'watchlist:list'           // TTL: 60s
'watchlist:enriched'       // TTL: 60s

// News
'news:bullets'             // TTL: 120s
'news:watchlist'           // TTL: 300s
'news:memory:{ticker}'     // TTL: 120s

// Performance
'performance:data'         // TTL: 300s

// Sparklines
'sparkline:{ticker}'       // TTL: 300s
```

### Cache Invalidierung
```typescript
// Manuelle Aktionen
cacheInvalidate('watchlist:list')      // Ticker hinzugefügt/entfernt
cacheInvalidate('news:bullets')        // News Scan ausgeführt
cacheInvalidateAll()                   // Manueller Refresh

// Automatische Invalidierung (TTL)
// Cache leert sich automatisch nach Ablauf der TTL
```

## Automatisierung (n8n)

### News Pipeline
```yaml
Schedule: Mo-Fr 13:00-22:30, alle 30min
Workflow:
  1. Get Watchlist from API
  2. Fetch Google News for each ticker
  3. Analyze sentiment with DeepSeek
  4. Store in database
  5. Send alerts for material events
```

### Morning Briefing
```yaml
Schedule: Täglich 08:00
Workflow:
  1. Fetch macro data (Finnhub)
  2. Get watchlist with scores
  3. Get recent news & events
  4. Generate briefing with DeepSeek
  5. Store in database
  6. Send via Telegram
```

### Post-Earnings Review
```yaml
Schedule: Mo-Fr 22:00
Workflow:
  1. Get earnings calendar
  2. Fetch actual vs expected EPS
  3. Calculate surprise percentages
  4. Generate review with DeepSeek
  5. Store in database
  6. Update shadow trades
```

## Performance Optimierungen

### Frontend
- **Client-Side Caching**: Redundante API-Calls vermeiden
- **Lazy Loading**: Charts bei Bedarf laden
- **Code Splitting**: Next.js automatische Optimierung
- **Image Optimization**: Next.js Image Component

### Backend
- **Redis Caching**: Häufige API-Antworten zwischenspeichern
- **Async Processing**: Non-blocking I/O für externe APIs
- **Connection Pooling**: Supabase Verbindungspool
- **Batch Processing**: Bulk API Calls reduzieren Latenz

### Database
- **Indizes**: Optimierte Abfrageperformance
- **Partitioning**: Zeitbasierte Datenpartitionierung
- **Connection Pooling**: Supabase Verbindungsoptimierung

## Security & Compliance

### Authentication
- Supabase Auth für Benutzer-Management
- JWT Token für API-Zugriff
- API Key Rotation

### Data Protection
- Input Validation mit Pydantic
- SQL Injection Prevention
- CORS Configuration
- Rate Limiting

### Compliance
- GDPR-konforme Datenverarbeitung
- Data Retention Policies
- Audit Logging

## Monitoring & Logging

### Structured Logging
```python
logger.info("API request processed",
           endpoint="/api/watchlist",
           method="GET",
           status_code=200,
           duration_ms=45,
           cache_hit=True)
```

### Error Handling
- Global Exception Handler
- Detailed Error Responses
- Client-Side Error Boundaries
- Sentry Integration (optional)

## Deployment

### Docker Compose
```yaml
version: '3.8'
services:
  kafin-backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  kafin-frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  n8n:
    image: n8nio/n8n
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=changeme
```

### Environment Configuration
```bash
# .env
SUPABASE_URL=postgresql://...
SUPABASE_KEY=...

FINNHUB_API_KEY=...
FMP_API_KEY=...
DEEPSEEK_API_KEY=...

REDIS_URL=redis://localhost:6379
```

## Testing Strategy

### Frontend Tests
```typescript
// Component Tests
import { render, screen } from '@testing-library/react'
import { CacheStatus } from '@/components/CacheStatus'

test('shows cache age correctly', () => {
  render(<CacheStatus fromCache={true} ageSeconds={45} onRefresh={() => {}} refreshing={false} />)
  expect(screen.getByText(/Aus Cache · vor 45s/)).toBeInTheDocument()
})
```

### Backend Tests
```python
# API Tests
def test_get_watchlist():
    response = client.get("/api/watchlist")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_add_ticker():
    response = client.post("/api/watchlist", json={
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "sector": "Technology"
    })
    assert response.status_code == 200
```

## Future Roadmap

### Phase 6: Real-time Features
- WebSocket Integration
- Live Price Updates
- Real-time Alerts
- Push Notifications

### Phase 7: Mobile App
- React Native App
- Offline Support
- Biometric Authentication
- Mobile-specific Features

### Phase 8: Advanced Analytics
- Portfolio Analytics
- Risk Management
- Backtesting Engine
- Strategy Optimization

### Phase 9: Social Features
- Community Watchlists
- Shared Analysis
- Discussion Forums
- Expert Ratings

---

**Version**: 2.0  
**Last Updated**: 2026-03-18  
**Status**: Production Ready
