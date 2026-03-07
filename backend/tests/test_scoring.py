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
    assert score.factors["earnings_momentum"] == 10.0
    assert score.factors["regime_valuation"] == 10.0
    assert score.factors["short_squeeze"] == 10.0
    assert score.factors["insider_activity"] == 10.0
    assert score.total_score > 5.0 # Due to weights

@pytest.mark.asyncio
async def test_calculate_torpedo_score():
    data = {
        "valuation": {"ps_ratio": 10.0},
        "insider_activity": {"cluster_assessment": "Cluster-Verkäufe"},
        "macro": {"vix": 35.0}
    }
    score = await calculate_torpedo_score("AAPL", data)
    assert score.factors["valuation_fall_height"] == 10.0
    assert score.factors["insider_selling"] == 10.0
    assert score.factors["macro_headwinds"] == 10.0
    assert score.total_score > 3.0

@pytest.mark.asyncio
async def test_decision_matrix():
    from schemas.scores import OpportunityScore, TorpedoScore
    opp_strong = OpportunityScore(total_score=8.0, factors={})
    torp_low = TorpedoScore(total_score=2.0, factors={})
    rec1 = await get_recommendation(opp_strong, torp_low)
    assert rec1.recommendation == "Strong Buy"
    
    opp_weak = OpportunityScore(total_score=2.0, factors={})
    torp_high = TorpedoScore(total_score=8.5, factors={})
    rec2 = await get_recommendation(opp_weak, torp_high)
    assert rec2.recommendation == "Strong Short"
