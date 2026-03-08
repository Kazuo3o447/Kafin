"""
Technische Analyse Schemas.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional


class TechnicalSetup(BaseModel):
    """Technische Kennzahlen eines Tickers."""
    ticker: str
    current_price: float
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    rsi_14: Optional[float] = None
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    distance_to_52w_high_percent: Optional[float] = None
    trend: str = "sideways"
    above_sma50: bool = False
    above_sma200: bool = False
    model_config = ConfigDict(from_attributes=True)
