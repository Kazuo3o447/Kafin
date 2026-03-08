"""
Pydantic Schemas für SEC EDGAR Filings (8-K, 10-Q)
"""
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List

class SecFiling(BaseModel):
    """Repräsentiert ein SEC Filing (z.B. 8-K oder 10-Q)"""
    ticker: str = Field(..., description="Aktien-Ticker (z.B. AAPL)")
    form_type: str = Field(..., description="Filing Typ (z.B. '8-K' oder '10-Q')")
    filing_date: str = Field(..., description="Filing Datum im Format YYYY-MM-DD")
    accession_number: str = Field(..., description="SEC Accession Number")
    report_url: str = Field(..., description="URL zum Übersichts-Report auf SEC.gov")
    primary_doc_url: str = Field(..., description="URL zum primären Dokument (.htm)")
    description: Optional[str] = Field(None, description="Kurzbeschreibung oder primäre Formular-Info")

class SecFilingsResponse(BaseModel):
    """Response-Model für SEC Filings Abfragen"""
    ticker: str = Field(..., description="Aktien-Ticker")
    cik: str = Field(..., description="Central Index Key (CIK)")
    filings: List[SecFiling] = Field(default_factory=list, description="Liste der gefundenen Filings")
