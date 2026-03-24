# Async/Blocking Konsistenz & Performance Guide

## Problem Statement

Das Kafin Backend verwendet FastAPI mit asyncio. Blockierende I/O-Aufrufe (wie yfinance API calls) können die Event Loop blockieren und die Performance beeinträchtigen.

## Lösung: Async/Non-Blocking Pattern

### 1. Async Functions mit `asyncio.to_thread`

Alle blockierenden I/O-Operationen werden in `asyncio.to_thread()` wrapped:

```python
async def get_risk_metrics(ticker: str) -> dict:
    try:
        def _fetch():
            stock = yf.Ticker(ticker)
            info = stock.info
            beta = info.get("beta")
            
            if beta is None:
                return {"beta": None, "ticker": ticker}
            
            return {
                "beta": round(float(beta), 2),
                "ticker": ticker
            }
        
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error(f"Risk Metrics Fehler für {ticker}: {e}")
        return {"beta": None, "ticker": ticker}
```

### 2. Batch-Downloads für Performance

Multiple yfinance Calls werden gebündelt:

```python
async def get_market_context() -> dict:
    tickers = {"^GSPC": "sp500_perf", "^NDX": "ndx_perf", "GC=F": "gold_perf"}
    
    def _fetch_all():
        import yfinance as yf
        hist = yf.download(
            list(tickers.keys()),
            period="5d",
            group_by="ticker",
            auto_adjust=True,
            progress=False
        )
        return hist
    
    hist = await asyncio.to_thread(_fetch_all)
    # ... process results
```

### 3. Korrekte async/await Kette

Async functions werden korrekt aufgerufen:

```python
# ✅ Korrekt
result = await get_market_breadth()

# ❌ Falsch (würde Coroutine zurückgeben)
result = get_market_breadth()
```

## Gefixte Funktionen

### Market Breadth Fix
- **Problem**: `get_market_breadth()` rief `_batch_download()` mit `asyncio.to_thread()` auf, obwohl `_batch_download()` bereits async ist
- **Fehler**: `TypeError: object of type 'coroutine' has no len()`
- **Lösung**: Direkter `await _batch_download()` ohne Wrapper

### yfinance Functions (7 Stück)
Alle folgenden Funktionen wurden von synchron zu non-blocking konvertiert:

1. `get_risk_metrics()` - Beta-Berechnung
2. `get_historical_volatility()` - Volatilitätsberechnung
3. `get_atm_implied_volatility()` - Options-IV
4. `get_options_metrics()` - Options-Kennzahlen
5. `get_short_interest_yf()` - Short Interest
6. `get_fundamentals_yf()` - Fundamentaldaten
7. `get_market_context()` - Batch-Download Optimierung

## Performance Benefits

### Vorher
- 3 separate yfinance Calls in `get_market_context()`
- Blockierende I/O in Event Loop
- Potenzielle Timeout-Probleme bei langsamen APIs

### Nachher
- 1 Batch-Call für alle Ticker
- Non-Blocking Execution im Thread-Pool
- Bessere Concurrency und Responsiveness

## Best Practices

### 1. Immer `asyncio.to_thread` verwenden
Für alle blockierenden Operationen:
- yfinance API calls
- File I/O (falls nicht async)
- CPU-intensive Berechnungen

### 2. Batch-Operationen bevorzugen
- Multiple Ticker in einem `yfinance.download()` Call
- Parallel Processing mit `asyncio.gather()`

### 3. Error Handling im Thread
Exceptions im Thread werden nicht automatisch propagiert:

```python
def _fetch():
    try:
        # blocking operation
        return result
    except Exception as e:
        logger.error(f"Thread error: {e}")
        return None

result = await asyncio.to_thread(_fetch)
```

### 4. Cache-Strategie
Non-blocking Calls profitieren von Caching:

```python
cache_key = f"yf:fundamentals:{ticker.upper()}"
cached = await cache_get(cache_key)
if cached:
    return cached

result = await asyncio.to_thread(_fetch)
await cache_set(cache_key, result, ttl_seconds=86400)
```

## Testing

### Async Function Tests
```python
import pytest
from httpx import AsyncClient

async def test_market_breadth():
    async with AsyncClient() as client:
        response = await client.get("/api/data/market-breadth")
        assert response.status_code == 200
        data = response.json()
        assert "pct_above_sma50" in data
        assert "breadth_signal" in data
```

### Performance Tests
```python
import time
import asyncio

async def test_concurrent_requests():
    start = time.time()
    tasks = [
        client.get("/api/data/market-breadth")
        for _ in range(10)
    ]
    responses = await asyncio.gather(*tasks)
    duration = time.time() - start
    
    assert duration < 5.0  # Should complete quickly
    assert all(r.status_code == 200 for r in responses)
```

## Monitoring

### Async Performance Metrics
- Response Times für API Endpoints
- Thread Pool Usage
- Event Loop Latency

### Logging
```python
logger.info(f"Market Breadth: Starting batch download for {len(symbols)} symbols")
logger.info(f"Market Breadth: Batch download returned data for {len(hist_data)} symbols")
```

## Zusammenfassung

Durch die Umstellung auf non-blocking I/O und Batch-Operationen:
- **Keine Event Loop Blockierung** mehr
- **Bessere Performance** durch parallele Verarbeitung
- **Stabiler Error Handling** im Thread-Pool
- **Optimierte Resource Usage** für yfinance API calls

Das Backend skaliert jetzt besser und kann mehr parallele Anfragen verarbeiten ohne die Responsiveness zu beeinträchtigen.
