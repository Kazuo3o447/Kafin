"""
sec_edgar — SEC EDGAR Filing Scanner für 8-K und Form 4

Input:  Ticker-Liste (aus Watchlist)
Output: Torpedo-Alerts bei kritischen Filings
Deps:   config.py, logger.py, alerts/telegram.py
Config: config/alerts.yaml → torpedo.keywords
API:    SEC EDGAR EFTS (kostenlos, 10 Requests/Sek.)
"""

import httpx
import asyncio
from datetime import datetime
from backend.app.config import settings
from backend.app.logger import get_logger

logger = get_logger(__name__)


async def check_recent_filings(ticker: str, form_types: list[str] = None) -> list[dict]:
    """
    Prüft SEC EDGAR auf neue Filings für einen Ticker.
    Returns: Liste von Filing-Dicts mit form_type, date, description, url
    """
    if form_types is None:
        form_types = ["8-K", "4"]

    if settings.use_mock_data:
        logger.debug(f"Mock: SEC EDGAR Check für {ticker}")
        return []

    filings = []

    for form_type in form_types:
        try:
            params = {
                "q": f'"{ticker}"',
                "dateRange": "custom",
                "startdt": datetime.now().strftime("%Y-%m-%d"),
                "enddt": datetime.now().strftime("%Y-%m-%d"),
                "forms": form_type
            }
            headers = {
                "User-Agent": "Kafin Trading Platform contact@kafin.dev",
                "Accept": "application/json"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://efts.sec.gov/LATEST/search-index",
                    params=params,
                    headers=headers,
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    hits = data.get("hits", {}).get("hits", [])
                    for hit in hits:
                        source = hit.get("_source", {})
                        filings.append({
                            "ticker": ticker,
                            "form_type": form_type,
                            "date": source.get("file_date", ""),
                            "description": source.get("display_names", [""])[0] if source.get("display_names") else "",
                            "url": f"https://www.sec.gov/Archives/edgar/data/{source.get('entity_id', '')}"
                        })
        except Exception as e:
            logger.error(f"SEC EDGAR Fehler für {ticker} {form_type}: {e}")

    return filings


async def scan_filings_for_watchlist(tickers: list[str]) -> list[dict]:
    """
    Scannt SEC EDGAR für alle Watchlist-Ticker.
    Bei kritischen Filings (8-K mit Torpedo-Keywords): Sofort Telegram-Alert.
    """
    logger.info(f"SEC EDGAR Scan gestartet für {len(tickers)} Ticker")

    all_filings = []
    torpedo_keywords = settings.alerts.get("torpedo", {}).get("keywords", [])

    for ticker in tickers:
        filings = await check_recent_filings(ticker)

        for filing in filings:
            all_filings.append(filing)

            description_lower = filing.get("description", "").lower()
            torpedo_hits = [kw for kw in torpedo_keywords if kw.lower() in description_lower]

            if torpedo_hits and filing.get("form_type") == "8-K":
                alert_text = (
                    f"🚨 SEC FILING ALERT: {ticker}\n\n"
                    f"Form: {filing['form_type']}\n"
                    f"Datum: {filing['date']}\n"
                    f"Beschreibung: {filing['description']}\n"
                    f"Torpedo-Keywords: {', '.join(torpedo_hits)}\n\n"
                    f"⚠️ Sofort prüfen!"
                )
                from backend.app.alerts.telegram import send_telegram_alert
                await send_telegram_alert(alert_text)

        await asyncio.sleep(0.2)

    logger.info(f"SEC EDGAR Scan abgeschlossen: {len(all_filings)} Filings gefunden")
    return all_filings
