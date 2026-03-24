"""
Makro- und Bitcoin-Schemas.
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class MacroSnapshot(BaseModel):
    """Wöchentlicher Makro-Snapshot."""
    date: Optional[datetime] = None
    fed_funds_rate: Optional[float] = None
    fed_rate: Optional[float] = None
    fed_rate_date: Optional[str] = None
    fed_expectation: Optional[str] = None
    vix: Optional[float] = None
    vix_date: Optional[str] = None
    credit_spread_bps: Optional[float] = None
    credit_spread_date: Optional[str] = None
    yield_curve_10y_2y: Optional[float] = None
    yield_curve_date: Optional[str] = None
    yield_curve: str = "positive"
    dxy: Optional[float] = None
    dxy_date: Optional[str] = None
    regime: str = "cautious"
    index_shorts_recommended: bool = False
    instrument_suggestions: Optional[str] = None
    geopolitical_notes: Optional[str] = None
    yield_curve_10y2y: Optional[float] = None
    high_yield_spread: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)


class BitcoinSnapshot(BaseModel):
    """Wöchentlicher Bitcoin-Snapshot."""
    date: Optional[datetime] = None
    price: Optional[float] = None
    price_7d_change_percent: Optional[float] = None
    open_interest_usd: Optional[float] = None
    open_interest_trend: str = "stable"
    funding_rate: Optional[float] = None
    long_short_ratio: Optional[float] = None
    liquidation_cluster_long: Optional[float] = None
    liquidation_cluster_short: Optional[float] = None
    dxy: Optional[float] = None
    recommendation: str = "wait"
    reasoning: str = ""
    key_support: Optional[float] = None
    key_resistance: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)
