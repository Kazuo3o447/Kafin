"""
Bewertungs-Schemas — Regime-kontextuelle Bewertungsdaten.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional


class ValuationData(BaseModel):
    """Bewertungskennzahlen eines Tickers."""
    ticker: str
    pe_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    pe_sector_median: Optional[float] = None
    ps_sector_median: Optional[float] = None
    pe_own_3y_median: Optional[float] = None
    ps_own_3y_median: Optional[float] = None
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    free_cash_flow_yield: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)
