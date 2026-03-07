from pydantic import BaseModel
from typing import Optional, Dict

class OpportunityScore(BaseModel):
    total_score: float
    factors: Dict[str, float]

class TorpedoScore(BaseModel):
    total_score: float
    factors: Dict[str, float]

class AuditRecommendation(BaseModel):
    recommendation: str  # Strong Buy, Buy, Hold, Short, Strong Short
    reasoning: str
