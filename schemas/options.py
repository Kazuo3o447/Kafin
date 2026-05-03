"""
Options-Schemas — Optionsdaten für Contrarian-Trading.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional


class OptionsData(BaseModel):
    """Optionsdaten für einen Ticker."""
    ticker: str = ""
    implied_volatility_atm: Optional[float] = None  # IV der ATM-Optionen (%)
    options_volume: Optional[int] = None  # Gesamtvolumen
    put_call_ratio: Optional[float] = None  # Put/Call Ratio
    historical_volatility: Optional[float] = None  # Historische Volatilität (%) zum Vergleich
    expiration_date: Optional[str] = None  # Nächste Expiration für IV-Berechnung
    iv_percentile: Optional[float] = None  # IV Percentile (0-100) - wie teuer ist die IV historisch?
    model_config = ConfigDict(from_attributes=True)


class OptionChainSummary(BaseModel):
    """Zusammenfassung einer Options-Chain."""
    ticker: str = ""
    calls_volume: Optional[int] = None
    puts_volume: Optional[int] = None
    calls_open_interest: Optional[int] = None
    puts_open_interest: Optional[int] = None
    atm_strike: Optional[float] = None
    avg_call_iv: Optional[float] = None
    avg_put_iv: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)
