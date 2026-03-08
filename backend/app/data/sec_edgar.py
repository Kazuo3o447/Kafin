"""
sec_edgar — SEC EDGAR Filing Extraktor
Liest 8-K und 10-Q (und ähnliche) Filings direkt von den SEC-Servern aus.

Input:  Aktien-Ticker
Output: Liste von SEC-Filings (SecFiling Pydantic Models)
Deps:   httpx, tenacity, logger, schemas.sec
Config: User-Agent für SEC (hardcoded Kafin bot)
API:    SEC EDGAR REST API (company_tickers.json und submissions.json)
"""
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from backend.app.logger import get_logger
from schemas.sec import SecFiling, SecFilingsResponse

logger = get_logger(__name__)

# Die SEC erwartet einen spezifischen User-Agent mit Kontakt-Info
SEC_USER_AGENT = "Kafin-Bot/1.0 (compliance@kafin.local)"
HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate"
}

# In-Memory Cache für CIK Mapping (reduziert API Calls an die SEC)
_cik_mapping_cache: Dict[str, str] = {}


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=30), retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)))
async def _fetch_url_json(url: str, client: httpx.AsyncClient) -> dict:
    """Holt JSON von einer URL mit Exponential Backoff bei Fehlern."""
    logger.debug(f"Fetching SEC EDGAR URL: {url}")
    response = await client.get(url, headers=HEADERS, timeout=10.0)
    response.raise_for_status()
    return response.json()

async def get_cik_for_ticker(ticker: str, client: httpx.AsyncClient) -> Optional[str]:
    """Sucht die CIK (Central Index Key) für einen Ticker aus der SEC Mapping Datei."""
    ticker_upper = ticker.upper()
    if ticker_upper in _cik_mapping_cache:
        return _cik_mapping_cache[ticker_upper]
        
    url = "https://www.sec.gov/files/company_tickers.json"
    try:
        data = await _fetch_url_json(url, client)
        # Die Datenstruktur ist ein Objekt mit Index-Keys (0, 1, 2...)
        for key, value in data.items():
            if value.get("ticker") == ticker_upper:
                # CIK muss 10-stellig sein für die Submissions-API (mit führenden Nullen)
                cik_str = str(value.get("cik_str")).zfill(10)
                _cik_mapping_cache[ticker_upper] = cik_str
                return cik_str
        
        logger.warning(f"CIK für Ticker {ticker_upper} nicht gefunden.")
        return None
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der SEC Ticker-Mapping: {e}")
        return None

async def get_recent_filings(ticker: str, forms: List[str] = ["8-K", "10-Q"], limit: int = 10) -> SecFilingsResponse:
    """
    Holt die neuesten SEC-Filings (spezifische Forms) für einen Ticker.
    Standard: Sucht nach 8-K (Current Report) und 10-Q (Quarterly Report).
    """
    ticker = ticker.upper()
    
    async with httpx.AsyncClient() as client:
        cik = await get_cik_for_ticker(ticker, client)
        if not cik:
            return SecFilingsResponse(ticker=ticker, cik="", filings=[])
            
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        
        try:
            data = await _fetch_url_json(url, client)
            recent_filings = data.get("filings", {}).get("recent", {})
            
            if not recent_filings or not recent_filings.get("accessionNumber"):
                return SecFilingsResponse(ticker=ticker, cik=cik, filings=[])
                
            filing_results: List[SecFiling] = []
            
            # Die Listen in recent_filings haben alle dieselbe Länge (Spalten im Array)
            for i in range(len(recent_filings.get("accessionNumber", []))):
                form_type = recent_filings.get("form", [])[i]
                
                if form_type in forms:
                    acc_num = recent_filings.get("accessionNumber", [])[i]
                    acc_num_no_dashes = acc_num.replace("-", "")
                    primary_doc = recent_filings.get("primaryDocument", [])[i]
                    date = recent_filings.get("filingDate", [])[i]
                    desc = recent_filings.get("primaryDocDescription", [])[i]
                    
                    # URLs aufbauen nach SEC-Standard
                    base_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_num_no_dashes}"
                    report_url = f"{base_url}/{acc_num}-index.htm"
                    primary_doc_url = f"{base_url}/{primary_doc}" if primary_doc else report_url
                    
                    filing = SecFiling(
                        ticker=ticker,
                        form_type=form_type,
                        filing_date=date,
                        accession_number=acc_num,
                        report_url=report_url,
                        primary_doc_url=primary_doc_url,
                        description=desc
                    )
                    filing_results.append(filing)
                    
                    if len(filing_results) >= limit:
                        break
                        
            return SecFilingsResponse(ticker=ticker, cik=cik, filings=filing_results)
            
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der SEC Filings (Submissions) für {ticker}: {e}")
            return SecFilingsResponse(ticker=ticker, cik=cik, filings=[])

# Einfacher Test-Run bei lokalem Execute
if __name__ == "__main__":
    import asyncio
    
    async def main():
        print("Teste SEC Edgar Scanner für AAPL...")
        res = await get_recent_filings("AAPL", ["8-K"])
        print(f"Gefundene Filings: {len(res.filings)}")
        for f in res.filings:
            print(f"- {f.filing_date}: {f.form_type} ({f.description})")
            print(f"  URL: {f.primary_doc_url}")
            
    asyncio.run(main())
