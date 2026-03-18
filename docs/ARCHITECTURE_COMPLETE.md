# Kafin Architektur

## Übersicht

Kafin ist eine Next.js 15 Full-Stack Plattform für Earnings-basiertes Trading mit KI-Unterstützung.

## Tech Stack

### Frontend
- **Framework**: Next.js 15 mit App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: Lucide Icons, Recharts
- **State Management**: React Hooks
- **API Client**: Custom fetch wrapper
- **Caching**: Client-side Map mit TTL

### Backend
- **Runtime**: Python 3.11
- **Framework**: FastAPI
- **Database**: Supabase (PostgreSQL)
- **Cache**: Redis
- **Logging**: structlog mit In-Memory Buffer
- **Async**: AsyncIO
- **Testing**: pytest

### Infrastructure
- **Container**: Docker & Docker Compose
- **Automation**: n8n Workflows
- **Deployment**: Local Docker

## Frontend Architektur

### Client-Side Caching
```typescript
// frontend/src/lib/clientCache.ts
const cache = new Map<string, CacheEntry<unknown>>()

export async function cachedFetch<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttlSeconds = 60
): Promise<{ data: T; fromCache: boolean }>
```

- **Module-level Map**: Überlebt Next.js Navigation
- **TTL-basiert**: Automatische Invalidierung
- **Kein localStorage**: Nur für aktuelle Session
- **CacheStatus UI**: Zeigt Cache-Alter und Refresh

### Page Struktur
```
src/app/
├── page.tsx              # Dashboard
├── watchlist/
│   └── page.tsx          # Watchlist Management
├── news/
│   └── page.tsx          # News & Signals
├── performance/
│   └── page.tsx          # Track Record & Shadow
├── earnings/
│   └── page.tsx          # Earnings Radar
└── layout.tsx            # Root Layout
```

### Components
```
src/components/
├── CacheStatus.tsx       # Cache UI Indicator
├── CommandPalette.tsx   # Cmd+K Quick Search
├── sidebar.tsx          # Navigation
└── ...
```

### API Layer
```typescript
// src/lib/api.ts
export const api = {
  getWatchlist: () => fetchJSON<WatchlistItem[]>('/api/watchlist'),
  getPerformance: () => fetchJSON<PerformanceData>('/api/performance'),
  // ...
}
```

## Backend Architektur

### FastAPI Structure
```
backend/app/
├── main.py               # FastAPI App & Routes
├── data/                 # Data Providers
│   ├── finnhub.py        # Market Data
│   ├── fmp.py            # Financial Metrics
│   ├── yfinance_data.py  # Technical Data
│   └── coinglass.py      # Crypto Data
├── analysis/             # AI Analysis
│   ├── chart_analyst.py  # DeepSeek Analysis
│   ├── report_generator.py # Morning Briefing
│   ├── post_earnings_review.py # Post-Earnings
│   └── shadow_portfolio.py # Shadow Trading
├── alerts/               # Signal Engine
│   ├── signal_scanner.py # Technical Signals
│   ├── opportunity_scanner.py # Earnings Setups
│   └── narrative_shift_detector.py # Narrative Changes
├── data/                 # External APIs
│   ├── deepseek.py       # LLM Integration
│   ├── finnhub.py        # Market Data
│   └── google_news.py    # News Aggregation
└── config.py             # Settings Management
```

### Database Schema
```sql
-- Core Tables
watchlist                 -- User Watchlist
audit_reports            -- AI Analysis
earnings_reviews         -- Post-Earnings Analysis
shadow_trades           -- Shadow Portfolio
narrative_shifts        -- Narrative Changes
signal_alerts           -- Technical Signals
```

### API Endpoints
```python
# Market Data
GET /api/data/macro                    -- Macro Snapshot
GET /api/data/market-overview          -- Indices & Sectors
GET /api/data/sparkline/{ticker}       -- Mini Charts

# Watchlist
GET /api/watchlist                      -- Basic Watchlist
GET /api/watchlist/enriched            -- With Scores/Deltas
POST /api/watchlist                     -- Add Ticker
DELETE /api/watchlist/{ticker}          -- Remove Ticker

# Analysis
GET /api/chart-analysis/{ticker}        -- DeepSeek Analysis
GET /api/opportunities                  -- Earnings Setups
POST /api/signals/scan                  -- Technical Signals

# Performance
GET /api/performance                    -- Track Record
GET /api/shadow/portfolio               -- Shadow Portfolio

# Reports
GET /api/reports/latest                 -- Morning Briefing
POST /api/reports/generate              -- Generate Report
```

## Data Flow

### Client-Side Caching Flow
```
User Action → cachedFetch() → Check Cache
├── Cache Hit → Return Cached Data (Instant)
└── Cache Miss → API Call → Cache Result → Return Data
```

### Backend Processing
```
API Request → FastAPI Route → Business Logic
├── Data Layer → External APIs / Database
├── Analysis Layer → AI Processing
├── Cache Layer → Redis (optional)
└── Response → JSON Response
```

### Automation Workflows (n8n)
```
Schedule → n8n Workflow → API Calls → Database Update
├── News Pipeline (30min)
├── Morning Briefing (08:00)
├── Post-Earnings Review (22:00)
└── Sunday Report (19:00)
```

## Configuration Management

### Environment Variables (.env)
```bash
# Database
SUPABASE_URL=...
SUPABASE_KEY=...

# APIs
FINNHUB_API_KEY=...
FMP_API_KEY=...
DEEPSEEK_API_KEY=...

# Services
REDIS_URL=...
```

### YAML Configuration
```yaml
# config/settings.yaml
app:
  name: "Kafin"
  version: "5.0"
  
# config/apis.yaml
apis:
  finnhub:
    base_url: "https://finnhub.io/api/v1"
  deepseek:
    model: "deepseek-chat"
```

## Performance Optimizations

### Frontend
- **Client-Side Caching**: Redundante API-Calls vermeiden
- **Lazy Loading**: Charts und schwere Komponenten
- **Code Splitting**: Next.js automatische Optimierung
- **Image Optimization**: Next.js Image Component

### Backend
- **Redis Caching**: Häufige API-Antworten
- **Async Processing**: Non-blocking I/O
- **Connection Pooling**: Supabase Verbindungen
- **Batch Processing**: Bulk API Calls

## Security

### Authentication
- Supabase Auth Integration
- JWT Token Management
- API Key Protection

### Data Protection
- Input Validation (Pydantic)
- SQL Injection Prevention
- CORS Configuration
- Rate Limiting (optional)

## Monitoring & Logging

### Structured Logging
```python
import structlog
logger = structlog.get_logger()

logger.info("API call", 
           endpoint="/api/watchlist",
           duration_ms=150,
           cache_hit=True)
```

### Error Handling
- Global Exception Handler
- Detailed Error Responses
- Client-Side Error Boundaries

## Deployment

### Docker Compose
```yaml
services:
  kafin-backend:
    build: ./backend
    ports: ["8000:8000"]
    
  kafin-frontend:
    build: ./frontend
    ports: ["3000:3000"]
    
  redis:
    image: redis:alpine
    ports: ["6379:6379"]
```

### Development Workflow
1. Backend: `uvicorn main:app --reload`
2. Frontend: `npm run dev`
3. Database: Supabase Local
4. Automation: n8n Docker

## Testing Strategy

### Frontend
- TypeScript Compile Check
- Component Testing (React Testing Library)
- E2E Testing (Playwright)

### Backend
- Unit Tests (pytest)
- Integration Tests
- API Testing (FastAPI TestClient)

## Future Architecture Considerations

### Scalability
- Horizontal Scaling with Load Balancer
- Database Read Replicas
- CDN Integration
- Microservices Migration

### Features
- Real-time WebSocket Updates
- Mobile App (React Native)
- Advanced Analytics Dashboard
- Multi-user Support

---

**Version**: 5.0  
**Last Updated**: 2026-03-18
