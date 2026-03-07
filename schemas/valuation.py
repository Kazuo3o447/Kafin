from pydantic import BaseModel, ConfigDict
from typing import Optional

class ValuationData(BaseModel):
    ticker: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    pe_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    market_cap: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)
