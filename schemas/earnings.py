"""
Earnings-Daten-Schemas — Verträge für alle Earnings-bezogenen Daten.
"""
from pydantic import BaseModel, ConfigDict
from datetime import date
from typing import Optional


class EarningsExpectation(BaseModel):
    """Erwartungen vor den Earnings."""
    ticker: str
    report_date: Optional[date] = None
    report_timing: Optional[str] = None       # "pre_market" | "after_hours"
    company_name: Optional[str] = None       # NEU: Unternehmensname aus Finnhub
    report_hour: Optional[str] = None        # NEU: "bmo" | "amc" | ""
    eps_consensus: Optional[float] = None
    eps_whisper: Optional[float] = None
    revenue_consensus: Optional[float] = None
    revenue_whisper: Optional[float] = None
    analyst_count: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class EarningsHistory(BaseModel):
    """Historische Earnings-Daten eines Quartals."""
    ticker: str
    quarter: str
    eps_actual: float
    eps_consensus: float
    eps_surprise_percent: float
    revenue_actual: Optional[float] = None
    revenue_consensus: Optional[float] = None
    revenue_surprise_percent: Optional[float] = None
    stock_reaction_1d: Optional[float] = None
    stock_reaction_5d: Optional[float] = None
    guidance_direction: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class EarningsHistorySummary(BaseModel):
    """Zusammenfassung der letzten 8 Quartale."""
    ticker: str
    quarters_beat: int
    quarters_missed: int
    avg_surprise_percent: float
    last_quarter: Optional[EarningsHistory] = None
    all_quarters: list[EarningsHistory] = []
    model_config = ConfigDict(from_attributes=True)
