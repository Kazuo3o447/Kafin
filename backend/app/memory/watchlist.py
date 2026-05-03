"""
watchlist — Verwaltung der Watchlist (Supabase)

Input:  Ticker-Daten
Output: Watchlist-Einträge (Dicts)
Deps:   supabase, config, logger, tenacity
Config: supabase_url, supabase_key aus settings
API:    Supabase REST API
"""
from typing import List, Dict, Any
import asyncio

from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.db import get_supabase_client

logger = get_logger(__name__)

# Mock-Daten (nur aktiv, wenn use_mock_data = True)
_mock_watchlist = [
    {"ticker": "AAPL", "company_name": "Apple Inc.", "sector": "Technology", "notes": "AI supercycle", "cross_signals": []},
    {"ticker": "MSFT", "company_name": "Microsoft", "sector": "Technology", "notes": "Azure growth", "cross_signals": []},
    {"ticker": "NVDA", "company_name": "Nvidia", "sector": "Technology", "notes": "Data center earnings", "cross_signals": ["AI"]},
]


async def _fetch_watchlist_async() -> List[Dict[str, Any]]:
    client = get_supabase_client()
    response = await client.table("watchlist").select("*").execute_async()
    return response.data

def _fetch_watchlist_sync() -> List[Dict[str, Any]]:
    client = get_supabase_client()
    response = client.table("watchlist").select("*").execute()
    return response.data

async def _insert_ticker_async(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    client = get_supabase_client()
    response = await client.table("watchlist").insert(item).execute_async()
    return response.data

def _insert_ticker_sync(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    client = get_supabase_client()
    response = client.table("watchlist").insert(item).execute()
    return response.data

async def _delete_ticker_async(ticker: str) -> List[Dict[str, Any]]:
    client = get_supabase_client()
    response = await client.table("watchlist").delete().eq("ticker", ticker).execute_async()
    return response.data

def _delete_ticker_sync(ticker: str) -> List[Dict[str, Any]]:
    client = get_supabase_client()
    response = client.table("watchlist").delete().eq("ticker", ticker).execute()
    return response.data

async def _update_ticker_async(ticker: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
    client = get_supabase_client()
    response = await client.table("watchlist").update(data).eq("ticker", ticker).execute_async()
    return response.data


async def get_watchlist() -> List[Dict[str, Any]]:
    if settings.use_mock_data:
        return _mock_watchlist

    try:
        data = await _fetch_watchlist_async()
        # Feld-Mapping von SQL Array zu erwartetem Listen-Feld
        for item in data:
            if "cross_signal_tickers" in item:
                item["cross_signals"] = item.pop("cross_signal_tickers")
        return data
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Watchlist aus Supabase: {e}")
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

    # Supabase Insert
    db_item = {
        "ticker": ticker.upper(),
        "company_name": company_name,
        "sector": sector,
        "notes": notes,
        # TODO: Fix cross_signals array handling for PostgreSQL
        # "cross_signal_tickers": list(cross_signals)
    }
    
    try:
        data = await _insert_ticker_async(db_item)
        if data:
            result = data[0]
            if "cross_signal_tickers" in result:
                result["cross_signals"] = result.pop("cross_signal_tickers")
            return result
        return new_item
    except Exception as e:
        logger.error(f"Fehler beim Speichern des Tickers {ticker} in Supabase: {e}")
        return {}

async def remove_ticker(ticker: str) -> bool:
    if settings.use_mock_data:
        global _mock_watchlist
        initial_len = len(_mock_watchlist)
        _mock_watchlist = [item for item in _mock_watchlist if item["ticker"] != ticker.upper()]
        return len(_mock_watchlist) < initial_len

    try:
        data = await _delete_ticker_async(ticker.upper())
        return len(data) > 0
    except Exception as e:
        logger.error(f"Fehler beim Löschen des Tickers {ticker} aus Supabase: {e}")
        return False

async def update_ticker(ticker: str, **kwargs) -> Dict[str, Any]:
    if settings.use_mock_data:
        for item in _mock_watchlist:
            if item["ticker"] == ticker.upper():
                item.update(kwargs)
                return item
        return {}

    # Feld-Mapping für Supabase Update
    db_kwargs = kwargs.copy()
    if "cross_signals" in db_kwargs:
        db_kwargs["cross_signal_tickers"] = db_kwargs.pop("cross_signals")
        
    try:
        data = await _update_ticker_async(ticker.upper(), db_kwargs)
        if data:
            result = data[0]
            if "cross_signal_tickers" in result:
                result["cross_signals"] = result.pop("cross_signal_tickers")
            return result
        return {}
    except Exception as e:
        logger.error(f"Fehler beim Aktualisieren des Tickers {ticker} in Supabase: {e}")
        return {}

async def get_earnings_this_week(watchlist: List[Dict[str, Any]], calendar: List[Any]) -> List[Dict[str, Any]]:
    """
    Vergleicht die Watchlist mit dem Earnings-Kalender und filtert.
    `calendar` repräsentiert die Liste der `EarningsExpectation` Objekte.
    """
    reporting_tickers = [getattr(item, "ticker", item.get("ticker", "")) if isinstance(item, dict) else item.ticker for item in calendar]
    
    this_week = []
    for wl_item in watchlist:
        if wl_item.get("ticker") in reporting_tickers:
           this_week.append(wl_item)
           
    return this_week
