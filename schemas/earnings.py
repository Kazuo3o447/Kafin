from pydantic import BaseModel, ConfigDict
from datetime import date
from typing import Optional

class EarningsExpectation(BaseModel):
    ticker: str
    date: date
    eps_estimate: Optional[float] = None
    eps_consensus: Optional[float] = None
    revenue_estimate: Optional[float] = None
    revenue_consensus: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

class EarningsHistorySummary(BaseModel):
    ticker: str
    quarters_beat: int
    quarters_missed: int
    avg_surprise_percent: float
    model_config = ConfigDict(from_attributes=True)
