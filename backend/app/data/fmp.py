"""
fmp — Datenabruf von Financial Modeling Prep API

Input:  Ticker-Symbole
Output: Pydantic-Schemas (ValuationData, EarningsExpectation, EarningsHistorySummary)
Deps:   config.py, httpx, schemas
Config: .env → FMP_API_KEY
API:    FMP (https://financialmodelingprep.com)

WICHTIG: Alle Endpoints nutzen /stable/ mit symbol= als Query-Parameter.
Jeder Call ist fehlertolerant — bei 400/403/404 wird None oder ein leeres Schema zurückgegeben.
KEINE MOCK DATEN ERLAUBT - IMMER ECHTE API-DATEN VERWENDEN.
"""
import httpx
from typing import Optional
from datetime import datetime

from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.rate_limiter import rate_limit
from schemas.valuation import ValuationData
from schemas.earnings import EarningsExpectation, EarningsHistorySummary, EarningsHistory

logger = get_logger(__name__)

FMP_BASE = "https://financialmodelingprep.com"


async def _fmp_get(endpoint: str, params: dict = None) -> list | dict | None:
    """
    Zentraler FMP-API-Call mit Fehlertoleranz.
    Gibt die JSON-Response zurück oder None bei jedem Fehler.
    """
    if params is None:
        params = {}
    params["apikey"] = settings.fmp_api_key

    url = f"{FMP_BASE}{endpoint}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                
                # Usage tracken (nach erfolgreichem Response)
                try:
                    from backend.app.analysis.usage_tracker import track_call
                    track_call(api_name="fmp")
                except Exception:
                    pass
                
                return data
            else:
                # Debug statt Warning für erwartete Fehler (Plan-Limits, Premium-Features)
                logger.debug(f"FMP {endpoint} HTTP {response.status_code} für params={params}")
                return None
    except httpx.TimeoutException:
        logger.warning(f"FMP {endpoint} Timeout")
        return None
    except Exception as e:
        logger.error(f"FMP {endpoint} Fehler: {e}")
        return None


@rate_limit("fmp")
async def get_company_profile(ticker: str) -> ValuationData | None:
    """Holt das Firmenprofil. Probiert /stable/ dann /api/v3/ als Fallback."""
    # Versuch 1: /stable/ mit symbol= Parameter
    data = await _fmp_get("/stable/profile", {"symbol": ticker})

    # Versuch 2: /api/v3/ mit Ticker im Pfad (Fallback)
    if data is None:
        data = await _fmp_get(f"/api/v3/profile/{ticker}")

    if data is None:
        logger.error(f"FMP Profil für {ticker} nicht verfügbar - API-Fehler oder Rate Limit.")
        return None

    if isinstance(data, list) and data:
        data = data[0]
    elif isinstance(data, list):
        return None

    return ValuationData(
        ticker=ticker,
        sector=data.get("sector"),
        industry=data.get("industry"),
        pe_ratio=data.get("pe") or data.get("peRatio"),
        market_cap=data.get("mktCap") or data.get("marketCap"),
    )


@rate_limit("fmp")
async def get_analyst_estimates(ticker: str) -> EarningsExpectation | None:
    """Holt Analysten-Schätzungen."""
    # /stable/ ohne limit (manche Plans unterstützen limit nicht)
    data = await _fmp_get("/stable/analyst-estimates", {"symbol": ticker})

    # Fallback: /api/v3/
    if data is None:
        data = await _fmp_get(f"/api/v3/analyst-estimates/{ticker}")

    if not data:
        logger.error(f"FMP Analyst Estimates für {ticker} nicht verfügbar - API-Fehler oder Rate Limit.")
        return None

    if isinstance(data, list) and data:
        data = data[0]

    d_str = data.get("date", "2026-01-01")
    try:
        dt = datetime.strptime(d_str, "%Y-%m-%d").date()
    except ValueError:
        dt = datetime.now().date()

    return EarningsExpectation(
        ticker=ticker,
        report_date=dt,
        eps_consensus=data.get("estimatedEpsAvg"),
        revenue_consensus=data.get("estimatedRevenueAvg"),
        analyst_count=data.get("numberAnalystEstimatedRevenue"),
    )


@rate_limit("fmp")
async def get_earnings_history(ticker: str, limit: int = 8) -> EarningsHistorySummary | None:
    """Holt historische Earnings-Surprises."""
    data = await _fmp_get("/stable/earnings-surprises", {"symbol": ticker})
    if data is None:
        data = await _fmp_get(f"/api/v3/earnings-surprises/{ticker}")
    if not data:
        logger.error(f"FMP Earnings History für {ticker} nicht verfügbar - API-Fehler oder Rate Limit.")
        return None

    if not isinstance(data, list):
        return None

    data = data[:limit]

    beats = 0
    misses = 0
    surprises = []
    all_quarters = []

    for q in data:
        actual = q.get("actualEarningResult")
        est = q.get("estimatedEarning")
        q_date = q.get("date", "")

        if actual is not None and est is not None:
            if actual >= est:
                beats += 1
            else:
                misses += 1

            surprise_pct = ((actual - est) / abs(est)) * 100 if est != 0 else 0
            surprises.append(surprise_pct)

            all_quarters.append(EarningsHistory(
                ticker=ticker,
                quarter=q_date,
                eps_actual=actual,
                eps_consensus=est,
                eps_surprise_percent=round(surprise_pct, 2),
            ))

    avg_surprise = sum(surprises) / len(surprises) if surprises else 0.0

    return EarningsHistorySummary(
        ticker=ticker,
        quarters_beat=beats,
        quarters_missed=misses,
        avg_surprise_percent=round(avg_surprise, 2),
        last_quarter=all_quarters[0] if all_quarters else None,
        all_quarters=all_quarters,
    )


@rate_limit("fmp")
async def get_key_metrics(ticker: str) -> ValuationData | None:
    """Holt Key Metrics (TTM)."""
    data = await _fmp_get("/stable/key-metrics-ttm", {"symbol": ticker})
    if data is None:
        data = await _fmp_get(f"/api/v3/key-metrics-ttm/{ticker}")
    if not data:
        logger.error(f"FMP Key Metrics für {ticker} nicht verfügbar - API-Fehler oder Rate Limit.")
        return None
    if isinstance(data, list) and data:
        data = data[0]

    # Profil für Sektor laden
    profile = await get_company_profile(ticker)

    return ValuationData(
        ticker=ticker,
        sector=profile.sector if profile else None,
        industry=profile.industry if profile else None,
        pe_ratio=data.get("peRatioTTM"),
        ps_ratio=data.get("priceToSalesRatioTTM"),
        market_cap=data.get("marketCapTTM"),
        debt_to_equity=data.get("debtToEquityTTM"),
        current_ratio=data.get("currentRatioTTM"),
        free_cash_flow_yield=data.get("freeCashFlowYieldTTM"),
    )


@rate_limit("fmp")
async def get_analyst_grades(ticker: str) -> list[dict]:
    """Holt Analysten Upgrades/Downgrades."""
    data = await _fmp_get("/stable/grades", {"symbol": ticker, "limit": 5})
    if data is None:
        data = await _fmp_get(f"/api/v3/grade/{ticker}", {"limit": 5})

    if isinstance(data, list):
        return data[:5]
    logger.error(f"FMP Analyst Grades für {ticker} nicht verfügbar - API-Fehler oder Rate Limit.")
    return []


@rate_limit("fmp")
async def get_price_target_consensus(ticker: str) -> dict | None:
    """Holt Price Target Konsens."""
    data = await _fmp_get("/stable/price-target-consensus", {"symbol": ticker})
    if data is None:
        data = await _fmp_get(f"/api/v4/price-target-consensus", {"symbol": ticker})

    if isinstance(data, list) and data:
        return data[0]
    elif isinstance(data, dict) and data:
        return data
    logger.error(f"FMP Price Target Consensus für {ticker} nicht verfügbar - API-Fehler oder Rate Limit.")
    return None


async def get_sector_pe(sector: str) -> float:
    """Gibt den geschätzten Sektor-Median P/E zurück."""
    defaults = {
        "Technology": 28.0,
        "Healthcare": 22.0,
        "Financial Services": 14.0,
        "Consumer Cyclical": 20.0,
        "Consumer Defensive": 20.0,
        "Industrials": 18.0,
        "Energy": 12.0,
        "Utilities": 16.0,
        "Real Estate": 20.0,
        "Communication Services": 22.0,
        "Basic Materials": 15.0,
    }
    return defaults.get(sector, 18.0)
