"""
main — FastAPI Entrypoint

Input:  HTTP Requests (REST)
Output: HTTP Responses (JSON)
Deps:   FastAPI, config, logger, schemas, admin
Config: app_name, environment
API:    Keine externen (nur intern)
"""
from fastapi import FastAPI
from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.admin import router as admin_router
from schemas.base import HealthCheckResponse

logger = get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend API für die Kafin Earnings-Trading-Plattform",
)

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starter {settings.app_name} im [{settings.environment}] Modus.")
    logger.info("Admin Panel is available at /admin")
    if settings.use_mock_data:
        logger.warning("Mock-Data-Modus ist AKTIV. Es werden keine echten APIs aufgerufen.")

app.include_router(admin_router)

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Prüft, ob die API erreichbar ist."""
    return HealthCheckResponse(status="ok", version="1.0.0")

from fastapi import APIRouter
from typing import List

from backend.app.data.finnhub import (
    get_earnings_calendar, get_company_news, get_short_interest, get_insider_transactions
)
from backend.app.data.fmp import (
    get_company_profile, get_analyst_estimates, get_earnings_history, get_key_metrics
)
from backend.app.data.fred import get_macro_snapshot

from schemas.earnings import EarningsExpectation, EarningsHistorySummary
from schemas.sentiment import NewsBulletPoint, ShortInterestData, InsiderActivity
from schemas.valuation import ValuationData
from schemas.macro import MacroSnapshot

data_router = APIRouter(prefix="/api/data", tags=["data"])

@data_router.get("/earnings-calendar", response_model=List[EarningsExpectation])
async def api_earnings_calendar(from_date: str, to_date: str):
    logger.info(f"API Call: earnings-calendar {from_date} to {to_date}")
    return await get_earnings_calendar(from_date, to_date)

@data_router.get("/company/{ticker}/news", response_model=List[NewsBulletPoint])
async def api_company_news(ticker: str, from_date: str = "2026-01-01", to_date: str = "2026-12-31"):
    logger.info(f"API Call: company-news for {ticker}")
    return await get_company_news(ticker, from_date, to_date)

@data_router.get("/company/{ticker}/short-interest", response_model=ShortInterestData)
async def api_short_interest(ticker: str):
    logger.info(f"API Call: short-interest for {ticker}")
    return await get_short_interest(ticker)

@data_router.get("/company/{ticker}/insiders", response_model=InsiderActivity)
async def api_insiders(ticker: str):
    logger.info(f"API Call: insiders for {ticker}")
    return await get_insider_transactions(ticker)

@data_router.get("/company/{ticker}/profile", response_model=ValuationData)
async def api_profile(ticker: str):
    logger.info(f"API Call: profile for {ticker}")
    return await get_company_profile(ticker)

@data_router.get("/company/{ticker}/estimates", response_model=EarningsExpectation)
async def api_estimates(ticker: str):
    logger.info(f"API Call: estimates for {ticker}")
    return await get_analyst_estimates(ticker)

@data_router.get("/company/{ticker}/earnings-history", response_model=EarningsHistorySummary)
async def api_earnings_history(ticker: str):
    logger.info(f"API Call: earnings-history for {ticker}")
    return await get_earnings_history(ticker)

@data_router.get("/macro", response_model=MacroSnapshot)
async def api_macro():
    logger.info(f"API Call: macro snapshot")
    return await get_macro_snapshot()

from backend.app.memory.watchlist import (
    get_watchlist, add_ticker, remove_ticker, update_ticker, get_earnings_this_week
)
from pydantic import BaseModel
from typing import Optional, List

# Watchlist Router
watchlist_router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

class WatchlistItemCreate(BaseModel):
    ticker: str
    company_name: str
    sector: str
    notes: Optional[str] = ""
    cross_signals: Optional[List[str]] = []

class WatchlistItemUpdate(BaseModel):
    company_name: Optional[str] = None
    sector: Optional[str] = None
    notes: Optional[str] = None
    cross_signals: Optional[List[str]] = None

@watchlist_router.get("")
async def api_get_watchlist():
    logger.info("API Call: get-watchlist")
    return await get_watchlist()

@watchlist_router.post("")
async def api_add_watchlist_item(item: WatchlistItemCreate):
    logger.info(f"API Call: add-watchlist-item {item.ticker}")
    return await add_ticker(
        item.ticker, item.company_name, item.sector, item.notes, item.cross_signals
    )

@watchlist_router.get("/earnings-this-week")
async def api_watchlist_earnings_this_week():
    logger.info("API Call: watchlist-earnings-this-week")
    from datetime import datetime, timedelta
    now = datetime.now()
    end_of_week = now + timedelta(days=7)
    from_date = now.strftime("%Y-%m-%d")
    to_date = end_of_week.strftime("%Y-%m-%d")
    
    cal = await get_earnings_calendar(from_date, to_date)
    wl = await get_watchlist()
    return await get_earnings_this_week(wl, cal)

@watchlist_router.put("/{ticker}")
async def api_update_watchlist_item(ticker: str, item: WatchlistItemUpdate):
    logger.info(f"API Call: update-watchlist-item {ticker}")
    update_data = {k: v for k, v in item.dict().items() if v is not None}
    return await update_ticker(ticker, **update_data)

@watchlist_router.delete("/{ticker}")
async def api_remove_watchlist_item(ticker: str):
    logger.info(f"API Call: remove-watchlist-item {ticker}")
    success = await remove_ticker(ticker)
    if success:
         return {"status": "success"}
    return {"status": "error"}

from backend.app.analysis.report_generator import generate_audit_report, generate_sunday_report

# Report Router
reports_router = APIRouter(prefix="/api/reports", tags=["reports"])

# In-Memory latest report for the mocked endpoint
_latest_report = ""

@reports_router.post("/generate/{ticker}")
async def api_generate_report(ticker: str):
    logger.info(f"API Call: generate-report for {ticker}")
    global _latest_report
    report_text = await generate_audit_report(ticker)
    _latest_report = report_text
    return {"status": "success", "report": report_text}

@reports_router.post("/generate-sunday")
async def api_generate_sunday_report():
    logger.info("API Call: generate-sunday-report")
    wl = await get_watchlist()
    tickers = [item["ticker"] for item in wl]
    
    global _latest_report
    report_text = await generate_sunday_report(tickers)
    _latest_report = report_text
    
    # Fire and forget email logic (to be implemented)
    import asyncio
    try:
        from backend.app.alerts.email import send_sunday_report
        asyncio.create_task(send_sunday_report(report_text))
    except ImportError:
        logger.warning("Email module not yet implemented.")
        
    return {"status": "success", "report": report_text}

@reports_router.get("/latest")
async def api_get_latest_report():
    logger.info("API Call: get-latest-report")
    return {"report": _latest_report}

app.include_router(data_router)
app.include_router(watchlist_router)
app.include_router(reports_router)
