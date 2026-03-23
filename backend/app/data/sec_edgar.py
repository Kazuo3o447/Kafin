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


async def get_latest_filings(
    ticker: str,
    form_type: str = "10-Q",
    limit: int = 2,
) -> list[dict]:
    """
    Holt die neuesten Filings für einen Ticker.
    Erweitert die Suche auf die letzten 90 Tage für 10-Q/10-K.
    """
    if settings.use_mock_data:
        logger.debug(f"Mock: get_latest_filings für {ticker}")
        return []

    filings = []

    try:
        # Für 10-Q/10-K suchen wir in den letzten 90 Tagen
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)

        params = {
            "q": f'"{ticker}"',
            "dateRange": "custom",
            "startdt": start_date.strftime("%Y-%m-%d"),
            "enddt": end_date.strftime("%Y-%m-%d"),
            "forms": form_type
        }
        headers = {
            "User-Agent": "Kafin Trading Platform contact@kafin.dev",
            "Accept": "application/json"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://efts.sec.gov/LATEST/search-index",
                params=params,
                headers=headers,
            )

            if response.status_code == 200:
                data = response.json()
                hits = data.get("hits", {}).get("hits", [])
                
                # Sortieren nach Datum (neueste zuerst)
                hits.sort(key=lambda x: x.get("_source", {}).get("file_date", ""), reverse=True)
                
                for hit in hits[:limit]:
                    source = hit.get("_source", {})
                    
                    # Bessere URL für den Filing-Text
                    entity_id = source.get("entity_id", "")
                    file_date = source.get("file_date", "")
                    
                    # Versuche, die Detail-URL zu finden
                    filing_url = f"https://www.sec.gov/Archives/edgar/data/{entity_id}"
                    
                    filings.append({
                        "ticker": ticker,
                        "form_type": form_type,
                        "date": file_date,
                        "description": source.get("display_names", [""])[0] if source.get("display_names") else "",
                        "url": filing_url,
                        "entity_id": entity_id,
                    })

    except Exception as e:
        logger.error(f"get_latest_filings Fehler für {ticker}: {e}")

    return filings


async def get_10q_sections(
    ticker: str,
    index: int = 0,
) -> dict | None:
    """
    Holt die relevanten Abschnitte eines 10-Q von SEC EDGAR.
    index=0 = neuestes, index=1 = vorheriges.

    Gibt zurück:
      {
        "ticker": "NVDA",
        "period": "2025-Q3",
        "filing_date": "2025-11-20",
        "sections": {
          "mda": "...",        # Management Discussion
          "risk_factors": "...",
          "outlook": "...",
        },
        "total_chars": 45000,
      }
    """
    headers = {
        "User-Agent": (
            "Kafin Trading Platform "
            "contact@kafin.dev"
        ),
        "Accept": "application/json",
    }

    # ── Einfacherer, zuverlässigerer Ansatz ──────────
    # Nutze sec.gov company facts API
    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers=headers,
        ) as client:
            # Company search für CIK
            search = await client.get(
                "https://efts.sec.gov/LATEST/search-index",
                params={
                    "q":     f'"{ticker}"',
                    "forms": "10-Q",
                    "dateRange": "custom",
                    "startdt": "2020-01-01",
                    "enddt": "2099-01-01",
                },
            )
            if search.status_code != 200:
                return None

            sdata = search.json()
            hits  = (
                sdata.get("hits", {})
                .get("hits", [])
            )
            if len(hits) <= index:
                logger.info(
                    f"Nur {len(hits)} 10-Q Filings "
                    f"für {ticker} gefunden"
                )
                return None

            hit    = hits[index]
            source = hit.get("_source", {})

            # Direkter Link zum Filing-Dokument
            # EDGAR gibt Akzessionsnummer zurück
            accession_raw = hit.get("_id", "")
            # Format: 0001234567-23-123456
            acc = accession_raw.replace("-", "")
            cik = str(source.get("entity_id", ""))

            if not acc or not cik:
                return None

            # Index-Seite des Filings
            index_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik}/{acc}/{accession_raw}-index.htm"
            )
            idx_resp = await client.get(index_url)

            # Suche 10-Q Dokument in Index
            doc_url = None
            if idx_resp.status_code == 200:
                import re
                # Finde htm/html Dokument das nicht index ist
                matches = re.findall(
                    r'href="(/Archives/edgar/data/'
                    r'[^"]+\.htm)"',
                    idx_resp.text,
                )
                for m in matches:
                    if "index" not in m.lower():
                        doc_url = (
                            "https://www.sec.gov" + m
                        )
                        break

            if not doc_url:
                logger.warning(
                    f"10-Q Dokument nicht in Index "
                    f"für {ticker}"
                )
                return None

            # Dokument laden
            doc_resp = await client.get(doc_url)
            if doc_resp.status_code != 200:
                return None

            raw_html = doc_resp.text

    except Exception as e:
        logger.warning(
            f"10-Q EDGAR Fetch Fehler {ticker}: {e}"
        )
        return None

    # ── HTML → Relevante Abschnitte extrahieren ───────
    sections = _extract_10q_sections(raw_html)
    period   = source.get("period_of_report", "")
    file_date = source.get("file_date", "")

    total = sum(len(v) for v in sections.values())
    logger.info(
        f"10-Q Abschnitte für {ticker} "
        f"({period}): {total} Zeichen"
    )

    return {
        "ticker":       ticker.upper(),
        "period":       period,
        "filing_date":  file_date,
        "sections":     sections,
        "total_chars":  total,
        "doc_url":      doc_url,
    }


def _extract_10q_sections(html: str) -> dict:
    """
    Extrahiert MD&A, Risk Factors und Outlook
    aus dem rohen 10-Q HTML.
    Gibt maximal 30.000 Zeichen pro Abschnitt zurück.
    """
    import re

    # HTML-Tags entfernen
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Abschnitt-Muster: typische 10-Q Überschriften
    SECTION_PATTERNS = {
        "mda": [
            r"ITEM\s*2[\.\s]+MANAGEMENT.S DISCUSSION",
            r"Management.s Discussion and Analysis",
            r"MD&A",
        ],
        "risk_factors": [
            r"ITEM\s*1A[\.\s]+RISK FACTORS",
            r"Risk Factors",
            r"RISK FACTORS",
        ],
        "outlook": [
            r"ITEM\s*3[\.\s]+",  # oft nach MDA
            r"FORWARD[- ]LOOKING",
            r"OUTLOOK",
            r"GUIDANCE",
            r"LIQUIDITY AND CAPITAL",
        ],
    }

    MAX_CHARS = 30_000  # Pro Abschnitt
    sections: dict[str, str] = {}

    text_upper = text.upper()

    for section_name, patterns in SECTION_PATTERNS.items():
        start_pos = None

        for pattern in patterns:
            match = re.search(
                pattern, text_upper
            )
            if match:
                start_pos = match.start()
                break

        if start_pos is None:
            sections[section_name] = ""
            continue

        # Nächsten Abschnitt als Ende suchen
        end_pos = len(text)
        next_item = re.search(
            r"ITEM\s*\d+[A-Z]?[\.\s]",
            text_upper[start_pos + 100:],
        )
        if next_item:
            end_pos = (
                start_pos + 100 + next_item.start()
            )

        section_text = text[
            start_pos : start_pos + MAX_CHARS
        ]
        sections[section_name] = section_text.strip()

    return sections
