"""
Sentiment- und News-Schemas.
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class NewsBulletPoint(BaseModel):
    """Einzelner News-Eintrag."""
    ticker: Optional[str] = None
    headline: str
    summary: str = ""
    bullet_points: list[str] = []
    sentiment_score: Optional[float] = None
    category: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    timestamp: Optional[datetime] = None
    is_material: bool = False
    
    # Narrative Intelligence (Phase 3A Extension)
    is_narrative_shift: bool = False
    shift_type: Optional[str] = None # "Market-Expansion" | "Strategic-Partnership" | "Strategic-Downsizing" | "None"
    shift_confidence: Optional[float] = None # 0.0 - 1.0
    shift_reasoning: Optional[str] = None # Max 15 words
    
    model_config = ConfigDict(from_attributes=True)


class ShortInterestData(BaseModel):
    """Short-Interest-Daten."""
    ticker: str
    short_interest: float = 0.0
    short_interest_percent: float = 0.0
    days_to_cover: float = 0.0
    short_interest_trend: str = "stable"       # "rising" | "falling" | "stable"
    squeeze_risk: str = "low"                   # "low" | "medium" | "high"
    model_config = ConfigDict(from_attributes=True)


class InsiderActivity(BaseModel):
    """Insider-Transaktionen der letzten 90 Tage."""
    ticker: str
    total_buys: int = 0
    total_buy_value: float = 0.0
    total_sells: int = 0
    total_sell_value: float = 0.0
    largest_sell_percent_of_position: Optional[float] = None
    is_cluster_buy: bool = False
    is_cluster_sell: bool = False
    assessment: str = "normal"                  # "normal" | "bullish" | "bearish"
    model_config = ConfigDict(from_attributes=True)

class SocialSentiment(BaseModel):
    """Social-Media Sentiment."""
    reddit_mentions: int = 0
    twitter_mentions: int = 0
    social_score: float = 0.0
    model_config = ConfigDict(from_attributes=True)
