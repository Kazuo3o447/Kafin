# Kafin Frontend

Modernes Dark Mode Dashboard für die Kafin Trading Platform, gebaut mit Next.js 15 und TypeScript.

## 🚀 Features

### UI/UX
- **Dark Mode Design**: Konsistentes Theme mit CSS-Variablen
- **2-Spalten News-Layout**: Kein Tab-Wechsel mehr nötig
- **Automatische Charts**: Direkte Anzeige auf Ticker-Detailseiten
- **Responsive Sidebar**: Schmale Navigation mit Online-Indikator
- **Error Handling**: Klare Fehlermeldungen und Loading-States

### Pages
- **Dashboard**: Marktübersicht, Watchlist-Heatmap, Morning Briefing
- **Watchlist**: Ticker-Management mit Detailansichten und Charts
- **News**: 2-Spalten-Layout mit Filter/Scans und integriertem Feed
- **Performance**: Track Record und Shadow Portfolio
- **Reports**: Morning Briefing, Sonntags-Report, Post-Earnings Reviews
- **Settings**: System-Status, API-Tests, Live-Logs

### Components
- **InteractiveChart**: TradingView Lightweight Charts mit Overlays
- **Sidebar**: Navigation mit CMD+K Schnellsuche
- **CacheStatus**: Client-Side Caching Indikator
- **Modal**: Verbessertes Ticker-Hinzufügen mit Validierung

## 🛠️ Tech Stack

- **Framework**: Next.js 15 mit App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS v4 mit CSS-Variablen
- **Icons**: Lucide React
- **Charts**: TradingView Lightweight Charts
- **State Management**: React Hooks
- **API Client**: Custom fetch wrapper

## 📦 Dependencies

```json
{
  "dependencies": {
    "next": "15.0.0",
    "react": "^18.2.0",
    "typescript": "^5.0.0",
    "tailwindcss": "^4.0.0",
    "lucide-react": "^0.263.1",
    "lightweight-charts": "^4.1.0"
  }
}
```

## 🚀 Getting Started

### Prerequisites
- Node.js 18+ 
- Backend API running on http://localhost:8000

### Installation

```bash
# 1. Dependencies installieren
npm install

# 2. Umgebungsvariablen konfigurieren
cp .env.example .env.local
# Backend URL und andere Settings anpassen

# 3. Development Server starten
npm run dev

# 4. Browser öffnen
# http://localhost:3000
```

### Environment Variables

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## 📁 Projektstruktur

```
src/
├── app/                    # Next.js App Router
│   ├── page.tsx           # Dashboard
│   ├── watchlist/         # Watchlist Pages
│   ├── news/              # News-Page mit 2-Spalten
│   ├── performance/      # Performance Tracking
│   ├── reports/           # Reports Generierung
│   ├── settings/          # System Settings
│   ├── layout.tsx         # Root Layout
│   └── globals.css        # Dark Mode Styles
├── components/            # Reusable Components
│   ├── sidebar.tsx        # Navigation
│   ├── InteractiveChart.tsx # Charts
│   └── CacheStatus.tsx    # Caching UI
├── lib/                   # Utilities
│   ├── api.ts            # API Client
│   └── clientCache.ts    # Client-Side Cache
└── types/                 # TypeScript Definitions
    └── api.ts            # API Types
```

## 🎨 Design System

### CSS Variables (Dark Mode)
```css
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

### Typography
- **Text**: Inter Font (lesbar, modern)
- **Zahlen**: JetBrains Mono (präzise, monospace)

### Layout Patterns
- **Cards**: `rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)]`
- **Buttons**: `px-4 py-2 rounded-lg bg-[var(--accent-blue)] text-white`
- **Inputs**: `px-3 py-2 rounded-lg bg-[var(--bg-tertiary)] border border-[var(--border)]`

## 🔧 API Integration

### Client-Side Caching
```typescript
import { cachedFetch } from '@/lib/clientCache';

// Cached API Call mit TTL
const { data, fromCache } = await cachedFetch(
  'watchlist:list',
  () => api.getWatchlist(),
  60 // 60 Sekunden TTL
);
```

### Error Handling
```typescript
try {
  await api.addTicker(tickerData);
  setAddError(null);
  closeModal();
} catch (err: any) {
  if (err.message.includes('409')) {
    setAddError('Ticker bereits auf Watchlist');
  } else {
    setAddError('Fehler beim Hinzufügen');
  }
}
```

## 📊 Chart Integration

### InteractiveChart Component
```typescript
<InteractiveChart 
  ticker="AAPL"
  timeframe="6M"
  showVolume={true}
  showSMA={true}
/>
```

### Chart Features
- **Candlestick Charts**: OHLCV Daten
- **SMA Overlays**: 50/200 Perioden
- **Event Markers**: Earnings, Torpedo, Insider
- **Error Handling**: Graceful Fallback bei fehlenden Daten

## 🚀 Deployment

### Docker Build
```bash
# Frontend Container bauen
docker build -t kafin-frontend .

# Mit Docker Compose starten
docker-compose up -d kafin-frontend
```

### Production Build
```bash
# Build für Production
npm run build

# Production Server starten
npm start
```

## 🧪 Testing

### Type Checking
```bash
# TypeScript Compile Check
npx tsc --noEmit
```

### Linting
```bash
# ESLint Check
npm run lint

# Lint Fix
npm run lint:fix
```

## 📝 Development Notes

### Performance Optimierungen
- **Client-Side Caching**: Redundante API-Calls vermeiden
- **Lazy Loading**: Charts und schwere Komponenten
- **Code Splitting**: Next.js automatische Optimierung

### Best Practices
- **TypeScript**: Strikte Typen für API Responses
- **Error Boundaries**: Graceful Error Handling
- **Loading States**: Spinner und Disabled States
- **Accessibility**: ARIA Labels und Keyboard Navigation

---

**Version**: 6.0 - Dark Mode & UX Overhaul  
**Last Updated**: 2026-03-18
