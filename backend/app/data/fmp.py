"""
fmp — Datenabruf von FMP API
"""
import httpx
import json
import os
from typing import List, Optional
from datetime import datetime

from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.rate_limiter import rate_limit
from schemas.valuation import ValuationData
from schemas.earnings import EarningsExpectation, EarningsHistory, EarningsHistorySummary

logger = get_logger(__name__)

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "fixtures", "fmp")

def load_mock_data(filename: str):
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@rate_limit("fmp")
async def get_company_profile(ticker: str) -> ValuationData:
    if settings.use_mock_data:
        try:
            data = load_mock_data(f"profile_{ticker}.json")
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            elif isinstance(data, list):
                return ValuationData(ticker=ticker)
        except Exception:
            return ValuationData(ticker=ticker)
    else:
        url = f"https://financialmodelingprep.com/stable/profile/{ticker}?apikey={settings.fmp_api_key}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            res_data = response.json()
            if not res_data:
                return ValuationData(ticker=ticker)
            data = res_data[0]
            
    return ValuationData(
        ticker=ticker,
        sector=data.get("sector"),
        industry=data.get("industry")
    )

@rate_limit("fmp")
async def get_analyst_estimates(ticker: str) -> EarningsExpectation:
    if settings.use_mock_data:
        try:
            data = load_mock_data(f"analyst_estimates_{ticker}.json")
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            elif isinstance(data, list):
                return EarningsExpectation(ticker=ticker, date=datetime.now().date())
        except Exception:
            return EarningsExpectation(ticker=ticker, date=datetime.now().date())
    else:
        url = f"https://financialmodelingprep.com/stable/analyst-estimates/{ticker}?apikey={settings.fmp_api_key}&limit=1"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            res_data = response.json()
            if not res_data:
                return EarningsExpectation(ticker=ticker, date=datetime.now().date())
            data = res_data[0]
            
    d_str = data.get("date", "2026-01-01")
    try:
        dt = datetime.strptime(d_str, "%Y-%m-%d").date()
    except ValueError:
        dt = datetime.now().date()
        
    return EarningsExpectation(
        ticker=ticker,
        date=dt,
        eps_consensus=data.get("estimatedEpsAvg"),
        revenue_consensus=data.get("estimatedRevenueAvg")
    )

@rate_limit("fmp")
async def get_earnings_history(ticker: str, limit: int = 8) -> EarningsHistorySummary:
    if settings.use_mock_data:
        try:
            data = load_mock_data(f"earnings_surprises_{ticker}.json")
        except Exception:
            data = []
    else:
        url = f"https://financialmodelingprep.com/stable/earnings-surprises/{ticker}?apikey={settings.fmp_api_key}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
    data = data[:limit]
    
    beats = 0
    misses = 0
    surprises = []
    all_quarters = []
    
    for q in data:
        actual = q.get("actualEarningResult")
        est = q.get("estimatedEarning")
        if actual is not None and est is not None:
            if actual >= est:
                beats += 1
            else:
                misses += 1
                
            if est != 0:
                surprise_pct = ((actual - est) / abs(est)) * 100
            else:
                surprise_pct = 0
            surprises.append(surprise_pct)

            all_quarters.append(EarningsHistory(
                ticker=ticker,
                quarter=q.get("date", "Unknown"),
                eps_actual=actual,
                eps_consensus=est,
                eps_surprise_percent=round(surprise_pct, 2),
            ))
            
    avg_surprise = sum(surprises) / len(surprises) if surprises else 0.0
    last_quarter = all_quarters[0] if all_quarters else None
    
    return EarningsHistorySummary(
        ticker=ticker,
        quarters_beat=beats,
        quarters_missed=misses,
        avg_surprise_percent=avg_surprise,
        last_quarter=last_quarter,
        all_quarters=all_quarters
    )

@rate_limit("fmp")
async def get_key_metrics(ticker: str) -> ValuationData:
    if settings.use_mock_data:
        try:
            data = load_mock_data(f"key_metrics_{ticker}.json")
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            elif isinstance(data, list):
                return ValuationData(ticker=ticker)
        except Exception:
            return ValuationData(ticker=ticker)
    else:
        url = f"https://financialmodelingprep.com/stable/key-metrics-ttm/{ticker}?apikey={settings.fmp_api_key}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            res_data = response.json()
            if not res_data:
                 return ValuationData(ticker=ticker)
            data = res_data[0]
            
    profile = await get_company_profile(ticker)
    
    return ValuationData(
        ticker=ticker,
        sector=profile.sector,
        industry=profile.industry,
        pe_ratio=data.get("peRatioTTM"),
        ps_ratio=data.get("priceToSalesRatioTTM"),
        market_cap=data.get("marketCapTTM")
    )

@rate_limit("fmp")
async def get_sector_pe(sector: str) -> float | None:
    """Holt den Median P/E eines Sektors von FMP."""
    # Branchenweite Defaults
    defaults = {"Technology": 28.0, "Healthcare": 22.0, "Financial Services": 14.0, "Consumer Cyclical": 20.0, "Industrials": 18.0, "Energy": 12.0, "Utilities": 16.0, "Real Estate": 20.0, "Communication Services": 22.0, "Consumer Defensive": 20.0, "Basic Materials": 15.0}

    if settings.use_mock_data:
        return defaults.get(sector, 18.0)

    try:
        url = f"https://financialmodelingprep.com/stable/sector-performance?apikey={settings.fmp_api_key}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                # FMP Sector Performance gibt keine P/E direkt
                # Fallback auf Defaults
                pass
    except Exception as e:
        logger.error(f"Sektor-P/E Fehler: {e}")

    return defaults.get(sector, 18.0)
