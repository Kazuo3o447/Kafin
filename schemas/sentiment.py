from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class NewsBulletPoint(BaseModel):
    headline: str
    summary: str
    category: Optional[str] = None
    url: Optional[str] = None
    timestamp: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class ShortInterestData(BaseModel):
    ticker: str
    short_interest: float
    days_to_cover: float
    trend: str
    squeeze_risk: str
    model_config = ConfigDict(from_attributes=True)

class InsiderActivity(BaseModel):
    ticker: str
    is_cluster_buy: bool
    is_cluster_sell: bool
    buy_volume_90d: float
    sell_volume_90d: float
    model_config = ConfigDict(from_attributes=True)
