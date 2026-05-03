# Kafin Architektur

## Übersicht

Kafin ist eine moderne Earnings-Trading-Plattform mit KI-Unterstützung, gebaut auf Next.js 15 und FastAPI mit einem fokussierten Dark Mode Dashboard.

## Tech Stack

### Frontend
- **Framework**: Next.js 15 mit App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS v4 mit CSS-Variablen
- **UI Components**: Lucide Icons, Lightweight Charts
- **State Management**: React Hooks, Client-Side Caching
- **API Client**: Custom fetch wrapper mit Error Handling
- **Charts**: TradingView Lightweight Charts mit Overlays

### Backend
- **Runtime**: Python 3.11
- **Framework**: FastAPI (Modular Architecture via APIRouter)
- **Database**: PostgreSQL 16 + pgvector (lokal)
- **Database Client**: asyncpg (hochperformantes Connection Pooling)
- **Cache**: Redis (Session + API + Usage Buffer)
- **Logging**: structlog mit In-Memory Buffer
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2) - lokal
- **Data Processing**: pandas, yfinance, Finnhub API
- **Usage Tracking**: Redis-Puffer + PostgreSQL Aggregation
- **Prompt Quality**: v0.4 mit vollständigen Platzhalter-Befüllung

### Infrastructure
- **Container**: Docker & Docker Compose
- **Automation**: n8n Workflows
- **Deployment**: Local Docker

## Frontend Architektur

### Design System (Dark Mode)
```css
/* CSS Variablen für konsistentes Dark Theme */
:root {
  --bg-primary:   #0B0F1A;   /* Seiten-Hintergrund */
  --bg-secondary: #111827;   /* Karten, Sidebar */
  --bg-tertiary:  #1A2235;   /* Inputs, Tabellen-Header */
  --text-primary:   #F1F5F9;  /* Hauptinhalt, Zahlen */
  --text-secondary: #94A3B8;  /* Labels, Beschriftungen */
  --accent-blue:   #3B82F6;  /* Primär-Aktion, Navigation */
  --accent-green:  #10B981;  /* Positiv, Buy */
  --accent-red:    #F43F5E;  /* Negativ, Short, Alarm */
}
```

### Page Struktur
```
src/app/
├── page.tsx              # Dashboard
├── watchlist/
│   ├── page.tsx          # Watchlist Management
│   └── [ticker]/
│       └── page.tsx      # Ticker Detail mit Chart
├── news/
│   └── page.tsx          # 2-Spalten News-Feed
├── performance/
│   └── page.tsx          # Track Record & Shadow
├── earnings/
│   └── page.tsx          # Earnings Radar
├── reports/
│   └── page.tsx          # Reports Generierung
└── layout.tsx            # Root Layout
```

### Key Components
```
src/components/
├── sidebar.tsx           # Navigation (220px, Dark Mode)
├── CacheStatus.tsx       # Cache UI Indicator
├── InteractiveChart.tsx  # TradingView Charts
└── CommandPalette.tsx    # Cmd+K Quick Search
```

### 2-Spalten News-Layout
```typescript
// News-Page: Linke Spalte (220px) + Rechte Spalte (flex-1)
<aside className="w-[220px] shrink-0 space-y-4">
  {/* Filter + Scan Buttons */}
</aside>
<main className="flex-1 min-w-0 space-y-4">
  {/* News + Google News + Signale */}
</main>
```

### API Layer mit Error Handling
```typescript
// src/lib/api.ts
export const api = {
  getWatchlist: () => fetchJSON<WatchlistItem[]>('/api/watchlist'),
  addTicker: (data: WatchlistItemCreate) => 
    fetchJSON('/api/watchlist', { method: 'POST', body: JSON.stringify(data) }),
  // ...
}
```

## Backend Architektur

### Modular Router Structure (backend/app/)
- **main.py**: Zentraler Entrypoint, Middleware-Konfiguration und Router-Registrierung.
- **routers/**: Fachlich getrennte API-Module:
  - `data.py`: Marktdaten, Research, Technicals, Fundamentals.
  - `news.py`: News-Pipeline, Google News Scans, SEC Edgar.
  - `analysis.py`: FinBERT, Signale, RAG Search, Market-Audit.
  - `reports.py`: Generierung von Audit-, Morning- und Sunday-Reports.
  - `watchlist.py`: Management der Ticker-Watchlist.
  - `shadow.py`: Shadow Portfolio Tracking und Trade-Management.
  - `logs.py`: System-Logs, Filtering und Export.
  - `system.py`: Health-Checks, Diagnostics, n8n/Telegram Setup.
  - `web_intelligence.py`: Batch-Verarbeitung und Deep-Search Integration.
- **admin/**: Admin-Panel UI (HTML) und operative Admin-Endpunkte.

### Robust Watchlist API
```python
class WatchlistItemCreate(BaseModel):
    ticker: str
    company_name: Optional[str] = None  # Robuster: Optional
    sector: Optional[str] = "Unknown"   # Mit Default
    notes: Optional[str] = ""
    cross_signals: Optional[List[str]] = []

@watchlist_router.post("")
async def api_add_watchlist_item(item: WatchlistItemCreate):
    # Fallback für fehlende Felder
    company_name = item.company_name or item.ticker.upper()
    sector = item.sector or "Unknown"
    return await add_ticker(item.ticker, company_name, sector, ...)
```

### Chart Intelligence System
```python
# OHLCV mit Overlays
GET /api/chart/ohlcv/{ticker}?period=1y&interval=1d
GET /api/chart/overlays/{ticker}  # Earnings, Torpedo, Insider

# Response Format
{
  "candles": [{"time": "2024-01-01", "open": 150, "high": 155, "low": 149, "close": 152}],
  "sma_50": [{"time": "2024-01-01", "value": 148.5}],
  "sma_200": [{"time": "2024-01-01", "value": 145.2}]
}
```

### Database Stack
- **PostgreSQL 16**: Haupt-Datenbank im Docker-Container.
- **pgvector**: Erweiterung für Vektor-Operationen (Semantische Suche).
- **asyncpg**: Asynchroner Treiber für maximale Performance.
- **QueryBuilder**: Custom Abstraktionsschicht für SQL-Abfragen.

## Data Flow

### Modern Frontend Flow
```
User Action → Loading/Error States → API Call → Response
├── Validation: Ticker Format (A-Z, 1-5 chars)
├── Loading: Spinner im Button
├── Error: Klare Fehlermeldungen (409, 422, 404)
└── Success: Cache invalidieren, UI aktualisieren
```

### Chart Data Flow
```
Ticker Page Mount → InteractiveChart → API Calls
├── GET /api/chart/ohlcv/{ticker} → Candlestick + SMA
├── GET /api/chart/overlays/{ticker} → Events (Earnings, Torpedo)
├── Error Handling: "Keine Daten für XYZ"
└── Render: Lightweight Charts mit Markern
```

### Backend Processing
```
API Request → FastAPI Route → Business Logic
├── Input Validation (Pydantic Models)
├── Data Layer → External APIs / Database
├── Analysis Layer → AI Processing (FinBERT, DeepSeek)
├── Cache Layer → Redis (optional)
└── Response → JSON mit Error Details
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
  version: "6.0"  # Dark Mode Update
  
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
- **Error Boundaries**: Graceful Error Handling
- **Lazy Loading**: Charts und schwere Komponenten
- **CSS Variables**: Optimiertes Dark Mode Rendering

### Backend
- **Parallel Processing**: asyncio.gather für yfinance Calls
- **Fast Info**: yfinance.fast_info statt .info (10x schneller)
- **Thread Pool**: CPU-intensive Tasks auslagern
- **Connection Pooling**: Supabase Verbindungen

## UI/UX Architecture

### Dark Mode Design System
- **CSS Variables**: Zentrales Theme Management
- **Typography**: Inter (Text) + JetBrains Mono (Zahlen)
- **Cards**: Konsistente Border-Radius und Shadows
- **Badges**: Farbige Status-Indikatoren
- **Transitions**: Smooth 0.15s Übergänge

### Responsive Layout
- **Desktop Focus**: Feste Spaltenbreiten (220px + flex-1)
- **Sidebar**: Schmal (224px) mit Online-Indikator
- **News-Layout**: 2-Spalten ohne Tab-Wechsel
- **Charts**: Automatische Integration auf Detailseiten

### Error Handling UX
- **Form Validation**: Real-time Feedback
- **Loading States**: Spinner und Disabled States
- **Error Messages**: Klare, kontextbezogene Hinweise
- **Fallbacks**: Graceful Degradation bei fehlenden Daten

### Security
- **Environment Variables**: Alle API-Keys und DB-Credentials in `.env`.
- **API Key Protection**: Zentrales Management über `backend/app/config.py`.
- **CORS Configuration**: Erlaubte Origins für Frontend und lokale Entwicklung.
- **Input Validation**: Strenge Pydantic-Modelle für alle API-Anfragen.

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
- User-Friendly Error Messages

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
- TypeScript Compile Check (`npx tsc --noEmit`)
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

**Version**: 6.1.5 - Modular Architecture & PostgreSQL Migration Complete
**Last Updated**: 2026-03-22
