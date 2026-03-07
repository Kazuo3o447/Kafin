from pydantic import BaseModel, ConfigDict
from typing import Optional

class MacroSnapshot(BaseModel):
    fed_funds_rate: Optional[float] = None
    vix: Optional[float] = None
    high_yield_spread: Optional[float] = None
    yield_spread_10y_2y: Optional[float] = None
    dxy: Optional[float] = None
    yield_curve: str
    regime: str
    model_config = ConfigDict(from_attributes=True)
