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
    historical_volatility_20d: Optional[float] = None  # 20-Tage historische Volatilität (%)
    historical_volatility_60d: Optional[float] = None  # 60-Tage historische Volatilität (%)
    beta: Optional[float] = None  # Beta zum S&P 500
    sma_20: Optional[float] = None
    atr_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    macd_bullish: Optional[bool] = None
    obv: Optional[float] = None
    obv_trend: Optional[str] = None
    rvol: Optional[float] = None
    float_shares: Optional[int] = None
    avg_volume: Optional[int] = None
    shares_outstanding: Optional[int] = None
    bid_ask_spread: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

class OptionsMetrics(BaseModel):
    """Options-Kennzahlen via yfinance."""
    put_call_ratio_oi: float = 0.0
    put_call_ratio_vol: Optional[float] = None
    implied_volatility_atm: float = 0.0
    expiration: str = ""
    model_config = ConfigDict(from_attributes=True)
