import pytest
from backend.app.analysis.scoring import calculate_opportunity_score, calculate_torpedo_score, get_recommendation

@pytest.mark.asyncio
async def test_calculate_opportunity_score():
    data = {
        "earnings_history": {"quarters_beat": 8, "avg_surprise_percent": 10.5},
        "valuation": {"pe_ratio": 10.0, "sector_pe": 20.0},
        "short_interest": {"short_interest": 35, "days_to_cover": 6},
        "insider_activity": {"cluster_assessment": "Cluster-Käufe"}
    }
    score = await calculate_opportunity_score("AAPL", data)
    assert score.earnings_momentum == 10.0  # NEU: direkte Felder statt factors
    assert score.valuation_regime == 10.0   # NEU
    assert score.short_squeeze_potential == 10.0  # NEU
    assert score.insider_activity == 10.0   # NEU
    assert score.total_score > 5.0 # Due to weights

@pytest.mark.asyncio
async def test_calculate_torpedo_score():
    data = {
        "valuation": {"ps_ratio": 10.0},
        "insider_activity": {"cluster_assessment": "Cluster-Verkäufe"},
        "macro": {"vix": 35.0}
    }
    score = await calculate_torpedo_score("AAPL", data)
    assert score.valuation_downside == 10.0     # NEU: direkte Felder statt factors
    assert score.insider_selling == 10.0       # NEU
    assert score.macro_headwind == 10.0         # NEU
    assert score.total_score > 3.0

@pytest.mark.asyncio
async def test_decision_matrix():
    from schemas.scores import OpportunityScore, TorpedoScore
    opp_strong = OpportunityScore(ticker="TEST", total_score=8.0)  # NEU: nur Pflichtfelder
    torp_low = TorpedoScore(ticker="TEST", total_score=2.0)       # NEU
    rec1 = await get_recommendation(opp_strong, torp_low)
    assert rec1.recommendation == "strong_buy"  # NEU: interne Tokens
    
    opp_weak = OpportunityScore(ticker="TEST", total_score=2.0)   # NEU
    torp_high = TorpedoScore(ticker="TEST", total_score=8.5)      # NEU
    rec2 = await get_recommendation(opp_weak, torp_high)
    assert rec2.recommendation == "strong_short"  # NEU: interne Tokens
