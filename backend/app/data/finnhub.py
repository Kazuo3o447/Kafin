"""
finnhub — Datenabruf von Finnhub API
"""
import httpx
import json
import os
import time
from typing import List
from datetime import datetime, timedelta

from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.rate_limiter import rate_limit
from schemas.earnings import EarningsExpectation
from typing import Optional
from schemas.sentiment import NewsBulletPoint, ShortInterestData, InsiderActivity, SocialSentiment

logger = get_logger(__name__)

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "fixtures", "finnhub")


@rate_limit("finnhub")
async def get_economic_calendar(days_back: int = 7, days_forward: int = 7) -> list[dict]:
    """
    Ruft den globalen Wirtschaftskalender von Finnhub ab.
    Filtert auf High-Impact Events (impact == 'high') für die Region US.
    
    Returns: Liste von Dicts mit event, date, estimate, actual, unit, impact, country.
    """
    now = datetime.now()
    from_date = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
    to_date = (now + timedelta(days=days_forward)).strftime("%Y-%m-%d")

    if settings.use_mock_data:
        logger.debug("Mock: Wirtschaftskalender wird simuliert")
        return [
            {"event": "US CPI MoM", "date": from_date, "estimate": 0.3, "actual": 0.4, "unit": "%", "impact": "high", "country": "US"},
            {"event": "US Nonfarm Payrolls", "date": to_date, "estimate": 200, "actual": None, "unit": "K", "impact": "high", "country": "US"},
            {"event": "US Initial Jobless Claims", "date": from_date, "estimate": 220, "actual": 215, "unit": "K", "impact": "high", "country": "US"},
        ]

    url = f"https://finnhub.io/api/v1/calendar/economic?from={from_date}&to={to_date}&token={settings.finnhub_api_key}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    events_raw = data.get("economicCalendar", [])

    # Filter: Nur High-Impact US Events
    filtered = []
    for ev in events_raw:
        impact = str(ev.get("impact", "")).lower()
        country = str(ev.get("country", "")).upper()
        if impact == "high" and country == "US":
            filtered.append({
                "event": ev.get("event", "Unknown"),
                "date": ev.get("time", ev.get("date", "")),
                "estimate": ev.get("estimate"),
                "actual": ev.get("actual"),
                "unit": ev.get("unit", ""),
                "impact": "high",
                "country": "US"
            })

    logger.info(f"Wirtschaftskalender: {len(filtered)} High-Impact US Events von {len(events_raw)} total")
    return filtered

def load_mock_data(filename: str):
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@rate_limit("finnhub")
async def get_earnings_calendar(from_date: str, to_date: str) -> List[EarningsExpectation]:
    if settings.use_mock_data:
        data = load_mock_data("earnings_calendar.json")
        return [
            EarningsExpectation(
                ticker=item.get("symbol", item.get("ticker", "")),
                report_date=item.get("date") or item.get("report_date"),
                eps_consensus=item.get("epsEstimate") or item.get("eps_consensus"),
                revenue_consensus=item.get("revenueEstimate") or item.get("revenue_consensus"),
            )
            for item in data
            if item.get("symbol") or item.get("ticker")
        ]
    
    url = f"https://finnhub.io/api/v1/calendar/earnings?from={from_date}&to={to_date}&token={settings.finnhub_api_key}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json().get("earningsCalendar", [])
        return [
            EarningsExpectation(
                ticker=item.get("symbol"),
                report_date=item.get("date"),
                eps_consensus=item.get("epsEstimate"),
                revenue_consensus=item.get("revenueEstimate"),
            ) for item in data if item.get("symbol")
        ]

@rate_limit("finnhub")
async def get_company_news(ticker: str, from_date: str, to_date: str) -> List[NewsBulletPoint]:
    if settings.use_mock_data:
        try:
            data = load_mock_data(f"company_news_{ticker}.json")
            return [NewsBulletPoint(**item) for item in data]
        except Exception:
            return []
            
    url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from_date}&to={to_date}&token={settings.finnhub_api_key}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        return [
            NewsBulletPoint(
                headline=item.get("headline"),
                summary=item.get("summary"),
                category=item.get("category"),
                url=item.get("url"),
                timestamp=datetime.fromtimestamp(item.get("datetime")) if item.get("datetime") else None
            ) for item in data
        ]

@rate_limit("finnhub")
async def get_short_interest(ticker: str) -> ShortInterestData:
    if settings.use_mock_data:
        try:
            data = load_mock_data(f"short_interest_{ticker}.json")
            return ShortInterestData(**data)
        except Exception:
            return ShortInterestData(ticker=ticker, short_interest=0, days_to_cover=0, trend="stable", squeeze_risk="low")
    
    try:
        url = f"https://finnhub.io/api/v1/stock/short-interest?symbol={ticker}&token={settings.finnhub_api_key}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            info = data.get("data", [])
            if not info:
                 return ShortInterestData(ticker=ticker, short_interest=0, days_to_cover=0, trend="stable", squeeze_risk="low")

            latest = info[0]
            short_interest = latest.get("shortInterest", 0)
            avg_volume = latest.get("volume", 1)
            days_to_cover = short_interest / avg_volume if avg_volume > 0 else 0
            
            trend = "stable"
            if len(info) >= 4:
                if info[0].get("shortInterest", 0) > info[3].get("shortInterest", 0):
                    trend = "increasing"
                elif info[0].get("shortInterest", 0) < info[3].get("shortInterest", 0):
                    trend = "decreasing"
                    
            percent_of_float = latest.get("shortPercentOfFloat", 0)
            if percent_of_float > 20:
                sq_risk = "high"
            elif percent_of_float >= 10:
                sq_risk = "medium"
            else:
                sq_risk = "low"
            
            return ShortInterestData(
                ticker=ticker,
                short_interest=short_interest,
                days_to_cover=days_to_cover,
                trend=trend,
                squeeze_risk=sq_risk
            )
    except Exception as e:
        logger.debug(f"Finnhub short-interest Fehler für {ticker}: {e} - Fallback auf yfinance")
        return None

@rate_limit("finnhub")
async def get_insider_transactions(ticker: str) -> InsiderActivity:
    if settings.use_mock_data:
        try:
            data = load_mock_data(f"insider_transactions_{ticker}.json")
            return InsiderActivity(**data)
        except Exception:
            return InsiderActivity(ticker=ticker, is_cluster_buy=False, is_cluster_sell=False, buy_volume_90d=0, sell_volume_90d=0)
    
    try:
        url = f"https://finnhub.io/api/v1/stock/insider-transactions?symbol={ticker}&token={settings.finnhub_api_key}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            txs = data.get("data", [])
        
        now_ts = time.time()
        days_90_ts = now_ts - (90 * 24 * 3600)
        
        buy_vol = 0
        sell_vol = 0
        insiders_bought = set()
        insiders_sold = set()
        
        for tx in txs:
           tx_date_str = tx.get("transactionDate")
           if tx_date_str:
               # e.g. "2021-03-01"
               try:
                   tx_ts = datetime.strptime(tx_date_str, "%Y-%m-%d").timestamp()
                   if tx_ts >= days_90_ts:
                       shares = tx.get("share", 0)
                       name = tx.get("name")
                       if shares > 0:
                           buy_vol += shares
                           insiders_bought.add(name)
                       elif shares < 0:
                           sell_vol += abs(shares)
                           insiders_sold.add(name)
               except ValueError:
                   pass
                       
        # 3+ Insider innerhalb der letzten Zeit
        is_cluster_buy = len(insiders_bought) >= 3
        is_cluster_sell = len(insiders_sold) >= 3
        
        return InsiderActivity(
             ticker=ticker,
             is_cluster_buy=is_cluster_buy,
             is_cluster_sell=is_cluster_sell,
             buy_volume_90d=buy_vol,
             sell_volume_90d=sell_vol
        )
    except Exception as e:
        logger.warning(f"Finnhub insider-transactions Fehler für {ticker}: {e}")
        return InsiderActivity(ticker=ticker, is_cluster_buy=False, is_cluster_sell=False, buy_volume_90d=0, sell_volume_90d=0)

@rate_limit("finnhub")
async def get_insider_transactions_list(ticker: str) -> List[dict]:
    """
    Ruft rohe Insider-Transaktionen für Chart-Overlays ab.
    """
    if settings.use_mock_data:
        return [
            {
                "time": "2025-10-05",
                "type": "insider",
                "direction": "buy",
                "name": "John Smith",
                "role": "Director",
                "amount_usd": 340000,
                "pct_of_holdings": 3.1
            }
        ]

    try:
        url = f"https://finnhub.io/api/v1/stock/insider-transactions?symbol={ticker}&token={settings.finnhub_api_key}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            txs = data.get("data", [])

        results = []
        for tx in txs:
            # Finnhub fields: name, share, change, transactionDate, transactionPrice
            # We need: time, type="insider", direction, name, role, amount_usd, pct_of_holdings
            
            shares = tx.get("share", 0) # This might be total shares held or change? 
            # Actually 'change' is the amount changed. 'share' is usually the holding after?
            # Finnhub API: 'change': Number of shares transacted. 'share': Number of shares held after the transaction.
            change = tx.get("change", 0)
            price = tx.get("transactionPrice", 0)
            
            if change == 0:
                continue

            direction = "buy" if change > 0 else "sell"
            amount_usd = abs(change) * price
            
            # Simple pct calculation if 'share' is post-transaction holding
            holding_after = tx.get("share", 0)
            holding_before = holding_after - change
            pct = 0.0
            if holding_before > 0:
                pct = (abs(change) / holding_before) * 100
            
            results.append({
                "time": tx.get("transactionDate"),
                "type": "insider",
                "direction": direction,
                "name": tx.get("name"),
                "role": "Insider", # Finnhub doesn't always give role in this endpoint easily, sometimes in other fields? 
                # Checking API docs: API v1/stock/insider-transactions returns 'name', 'share', 'change', 'filingDate', 'transactionDate', 'transactionPrice', 'symbol'.
                # Doesn't explicitly have 'role' in the basic response? 
                # Wait, prompt example has "role": "Director".
                # If Finnhub doesn't provide it, I'll default to "Insider".
                "amount_usd": round(amount_usd, 2),
                "pct_of_holdings": round(pct, 2)
            })
            
        return results

    except Exception as e:
        logger.warning(f"Finnhub insider-list Fehler für {ticker}: {e}")
        return []

    """Ruft Finnhub Social Sentiment der letzten 7 Tage ab."""
    if settings.use_mock_data:
        return SocialSentiment(reddit_mentions=150, twitter_mentions=300, social_score=0.35)
        
    now = datetime.now()
    from_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    url = f"https://finnhub.io/api/v1/stock/social-sentiment?symbol={ticker}&from={from_date}&token={settings.finnhub_api_key}"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            reddit = data.get("reddit", [])
            twitter = data.get("twitter", [])
            
            # Aggregation über die letzten 7 Tage
            r_mentions = sum(r.get("mention", 0) for r in reddit)
            t_mentions = sum(t.get("mention", 0) for t in twitter)
            total_mentions = r_mentions + t_mentions
            
            if total_mentions == 0:
                return None
                
            r_score = sum(r.get("score", 0) * r.get("mention", 0) for r in reddit)
            t_score = sum(t.get("score", 0) * t.get("mention", 0) for t in twitter)
            
            avg_score = (r_score + t_score) / total_mentions
            
            return SocialSentiment(
                reddit_mentions=r_mentions,
                twitter_mentions=t_mentions,
                social_score=round(avg_score, 4)
            )
        except Exception as e:
            logger.debug(f"Finnhub Social Sentiment Fehler für {ticker}: {e}")
            return None

