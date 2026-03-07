"""
watchlist — Verwaltung der Watchlist (In-Memory für Mock oder Supabase)
"""
from typing import List, Dict, Any

from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.data.finnhub import get_earnings_calendar

logger = get_logger(__name__)

# In-Memory Mock Datenbank für Watchlist
_mock_watchlist = [
    {"ticker": "AAPL", "company_name": "Apple Inc.", "sector": "Technology", "notes": "AI supercycle", "cross_signals": []},
    {"ticker": "MSFT", "company_name": "Microsoft", "sector": "Technology", "notes": "Azure growth", "cross_signals": []},
    {"ticker": "NVDA", "company_name": "Nvidia", "sector": "Technology", "notes": "Data center earnings", "cross_signals": ["AI"]},
]

async def get_watchlist() -> List[Dict[str, Any]]:
    if settings.use_mock_data:
        return _mock_watchlist
    
    # Supabase logic would go here
    # from backend.app.db import supabase
    # response = supabase.table("watchlist").select("*").execute()
    # return response.data
    logger.warning("Supabase not fully integrated. Returning empty watchlist.")
    return []

async def add_ticker(ticker: str, company_name: str, sector: str, notes: str = "", cross_signals: List[str] | None = None) -> Dict[str, Any]:
    if cross_signals is None:
        cross_signals = []
        
    new_item = {
        "ticker": ticker.upper(),
        "company_name": company_name,
        "sector": sector,
        "notes": notes,
        "cross_signals": cross_signals
    }
    
    if settings.use_mock_data:
        # Check if exists
        for idx, item in enumerate(_mock_watchlist):
            if item["ticker"] == new_item["ticker"]:
                _mock_watchlist[idx] = new_item
                return new_item
        _mock_watchlist.append(new_item)
        return new_item
        
    # Supabase logic would go here
    return new_item

async def remove_ticker(ticker: str) -> bool:
    if settings.use_mock_data:
        global _mock_watchlist
        initial_len = len(_mock_watchlist)
        _mock_watchlist = [item for item in _mock_watchlist if item["ticker"] != ticker.upper()]
        return len(_mock_watchlist) < initial_len
        
    return False

async def update_ticker(ticker: str, **kwargs) -> Dict[str, Any]:
    if settings.use_mock_data:
        for item in _mock_watchlist:
            if item["ticker"] == ticker.upper():
                item.update(kwargs)
                return item
        return {}
        
    return {}

async def get_earnings_this_week(watchlist: List[Dict[str, Any]], calendar: List[Any]) -> List[Dict[str, Any]]:
    """
    Vergleicht die Watchlist mit dem Earnings-Kalender und filtert.
    `calendar` repräsentiert die Liste der `EarningsExpectation` Ojekte.
    """
    reporting_tickers = [item.ticker for item in calendar]
    
    this_week = []
    for wl_item in watchlist:
        if wl_item["ticker"] in reporting_tickers:
           this_week.append(wl_item)
           
    return this_week
