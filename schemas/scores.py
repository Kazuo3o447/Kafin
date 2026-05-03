"""
Scoring-Schemas — Output der Scoring-Engine.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional


class OpportunityScore(BaseModel):
    """Detaillierter Opportunity-Score."""
    ticker: str = ""
    total_score: float = 0.0
    earnings_momentum: float = 0.0
    whisper_delta: float = 0.0
    valuation_regime: float = 0.0
    guidance_trend: float = 0.0
    technical_setup: float = 0.0
    sector_regime: float = 0.0
    short_squeeze_potential: float = 0.0
    insider_activity: float = 0.0
    options_flow: float = 0.0
    beta: Optional[float] = None
    quality_score: Optional[float] = None
    mismatch_score: Optional[float] = None
    data_completeness: float = 1.0   # 0.0–1.0: Anteil verfügbarer Datenpunkte
    missing_fields: list[str] = []   # Liste der fehlenden Felder für Report
    model_config = ConfigDict(from_attributes=True)


class TorpedoScore(BaseModel):
    """Detaillierter Torpedo-Score."""
    ticker: str = ""
    total_score: float = 0.0
    valuation_downside: float = 0.0
    expectation_gap: float = 0.0
    insider_selling: float = 0.0
    guidance_deceleration: float = 0.0
    leadership_instability: float = 0.0
    technical_downtrend: float = 0.0
    macro_headwind: float = 0.0
    data_completeness: float = 1.0
    missing_fields: list[str] = []
    model_config = ConfigDict(from_attributes=True)


class AuditRecommendation(BaseModel):
    """Finale Empfehlung."""
    ticker: str = ""
    opportunity_score: Optional[OpportunityScore] = None
    torpedo_score: Optional[TorpedoScore] = None
    recommendation: str = "hold"
    recommendation_label: str = "Kein Trade"
    reasoning: str = ""
    options_suggestion: Optional[str] = None
    data_completeness: float = 1.0
    low_confidence: bool = False     # True wenn < 50% Daten
    macro_warning: Optional[str] = None   # NEU — Makro-Regime-Gate Warnung
    model_config = ConfigDict(from_attributes=True)
