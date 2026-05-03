import pytest
import json
import os
from datetime import datetime
from backend.app.memory.short_term import save_bullet_points, get_bullet_points, get_supabase_client
from backend.app.analysis.scoring import calculate_opportunity_score, calculate_torpedo_score
from schemas.sentiment import NewsBulletPoint
from backend.app.config import settings

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
FIXTURE_PATH = os.path.join(ROOT_DIR, "fixtures", "deepseek", "narrative_variants.json")

# Stelle sicher, dass Mock-Modus für DB an ist
settings.use_mock_data = True

@pytest.fixture
def mock_deepseek_responses():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.mark.asyncio
async def test_narrative_shift_parsing(mock_deepseek_responses):
    """Testet ob das Pydantic-Schema die neuen JSON-Strukturen fehlerfrei parst."""
    # Fall 1: Dividende
    div_data = mock_deepseek_responses["dividend_raise"]
    div_model = NewsBulletPoint(
        ticker="AAPL",
        headline="Apple raises dividend",
        is_narrative_shift=div_data["is_narrative_shift"],
        shift_type=div_data["shift_type"],
        shift_confidence=div_data["shift_confidence"],
        shift_reasoning=div_data["shift_reasoning"],
        bullet_points=div_data["bullet_points"]
    )
    assert div_model.is_narrative_shift is False
    assert div_model.shift_type == "None"
    
    # Fall 2: Partnerschaft
    part_data = mock_deepseek_responses["partnership"]
    part_model = NewsBulletPoint(
        ticker="AAPL",
        headline="Exklusive Microsoft Azure Partnerschaft",
        is_narrative_shift=part_data["is_narrative_shift"],
        shift_type=part_data["shift_type"],
        shift_confidence=part_data["shift_confidence"],
        shift_reasoning=part_data["shift_reasoning"],
        bullet_points=part_data["bullet_points"]
    )
    assert part_model.is_narrative_shift is True
    assert part_model.shift_type == "Strategic-Partnership"

@pytest.mark.asyncio
async def test_scoring_integration_positive_shift(mock_deepseek_responses):
    """Prüft ob ein positiver Shift das Valuation Regime im Scoring erhöht."""
    part_data = mock_deepseek_responses["partnership"]
    
    base_data_ctx = {
        "valuation": {"pe_ratio": 20, "pe_sector_median": 20}, # Fair valued -> base vr = 5.0
        "news_memory": []
    }
    
    score_before = await calculate_opportunity_score("TEST1", base_data_ctx)
    vr_before = score_before.valuation_regime
    
    # Füge den Shift dem Speicher hinzu
    base_data_ctx["news_memory"] = [{
        "is_narrative_shift": part_data["is_narrative_shift"],
        "shift_type": part_data["shift_type"]
    }]
    
    score_after = await calculate_opportunity_score("TEST1", base_data_ctx)
    vr_after = score_after.valuation_regime
    
    assert vr_after > vr_before
    assert vr_after == min(10.0, vr_before + 2.0)

@pytest.mark.asyncio
async def test_scoring_integration_torpedo_shift(mock_deepseek_responses):
    """Prüft ob ein Downsizing Shift die Torpedo-Faktoren drastisch ansteigen lässt."""
    down_data = mock_deepseek_responses["downsizing"]
    
    base_data_ctx = {
        "news_memory": []
    }
    
    score_before = await calculate_torpedo_score("TEST2", base_data_ctx)
    gd_before = score_before.guidance_deceleration
    eg_before = score_before.expectation_gap
    
    base_data_ctx["news_memory"] = [{
        "is_narrative_shift": down_data["is_narrative_shift"],
        "shift_type": down_data["shift_type"]
    }]
    
    score_after = await calculate_torpedo_score("TEST2", base_data_ctx)
    gd_after = score_after.guidance_deceleration
    eg_after = score_after.expectation_gap
    
    assert gd_after > gd_before
    assert eg_after > eg_before
    assert gd_after == min(10.0, gd_before + 2.0)
    assert eg_after == min(10.0, eg_before + 2.0)
