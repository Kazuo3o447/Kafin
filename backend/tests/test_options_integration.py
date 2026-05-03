import pytest
from backend.app.analysis.scoring import calculate_opportunity_score, calculate_torpedo_score

@pytest.mark.asyncio
async def test_options_flow_contrarian_signal():
    """Testet, dass ein hohes Put/Call Ratio (PCR > 1.2) den Opportunity-Score erhöht."""
    data_ctx = {
        "options": {"put_call_ratio_oi": 1.5, "implied_volatility_atm": 0.3}
    }
    
    opp_score = await calculate_opportunity_score("AAPL", data_ctx)
    assert opp_score.options_flow == 7.0
    
@pytest.mark.asyncio
async def test_expectation_gap_high_iv():
    """Testet, dass eine hohe Implied Volatility (IV > 80%) den Torpedo-Score (Risk) erhöht."""
    data_ctx = {
        "options": {"put_call_ratio_oi": 0.8, "implied_volatility_atm": 0.95}
    }
    
    torp_score = await calculate_torpedo_score("AAPL", data_ctx)
    assert torp_score.expectation_gap == 7.0
