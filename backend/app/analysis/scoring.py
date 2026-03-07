import yaml
import os
from schemas.scores import OpportunityScore, TorpedoScore, AuditRecommendation
from backend.app.logger import get_logger

logger = get_logger(__name__)

SCORING_YAML_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "config", "scoring.yaml")

def _load_weights() -> dict:
    with open(SCORING_YAML_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["weights"]

async def calculate_opportunity_score(ticker: str, data: dict) -> OpportunityScore:
    weights = _load_weights()["opportunity"]
    factors = {}
    
    # earnings_momentum
    em = 0.0
    history = data.get("earnings_history", {})
    quarters_beat = history.get("quarters_beat", 0)
    avg_surprise = history.get("avg_surprise_percent", 0.0)
    if quarters_beat == 8 and avg_surprise > 0:
        em = 10.0
    elif quarters_beat == 0:
        em = 0.0
    else:
        em = (quarters_beat / 8.0) * 10.0
    factors["earnings_momentum"] = em

    # whisper_delta (Mock impl, requires actual estimates vs whisper logic)
    whisper_delta = 5.0 # Default if unknown
    factors["whisper_delta"] = whisper_delta

    # valuation_regime
    vr = 5.0
    val = data.get("valuation", {})
    pe = val.get("pe_ratio")
    sector_pe = val.get("sector_pe", 15.0) # Mock median fallback
    if pe and sector_pe:
        if pe < sector_pe * 0.8: vr = 10.0
        elif pe > sector_pe * 2.0: vr = 0.0
        else: vr = 5.0
    factors["regime_valuation"] = vr

    # guidance_trend (mocked, missing actual struct structure)
    factors["forward_guidance"] = 5.0

    # technical_setup (Mocked)
    factors["technical_setup"] = 5.0

    # sector_regime
    factors["sector_regime"] = 5.0

    # short_squeeze_potential
    ss = 0.0
    si_data = data.get("short_interest", {})
    si_pct = getattr(si_data, "short_interest", 0) if not isinstance(si_data, dict) else si_data.get("short_interest", 0)
    dtc = getattr(si_data, "days_to_cover", 0) if not isinstance(si_data, dict) else si_data.get("days_to_cover", 0)
    
    if si_pct > 30 and dtc > 5: ss = 10.0
    elif 15 <= si_pct <= 30: ss = 5.0
    elif si_pct < 10: ss = 0.0
    else: ss = 2.5
    factors["short_squeeze"] = ss

    # insider_activity
    ia_score = 5.0
    ia = data.get("insider_activity", {})
    assessment = getattr(ia, "cluster_assessment", "") if not isinstance(ia, dict) else ia.get("cluster_assessment", "")
    if assessment == "Cluster-Käufe": ia_score = 10.0
    elif assessment == "Cluster-Verkäufe": ia_score = 0.0
    factors["insider_activity"] = ia_score

    # options_flow
    factors["options_flow"] = 5.0

    total_score = sum(factors[k] * weights.get(k, 0) for k in factors)
    
    return OpportunityScore(total_score=round(total_score, 2), factors=factors)

async def calculate_torpedo_score(ticker: str, data: dict) -> TorpedoScore:
    weights = _load_weights()["torpedo"]
    factors = {}
    
    # valuation_downside
    vd = 0.0
    val = data.get("valuation", {})
    ps = val.get("ps_ratio")
    sector_ps = 3.0 # Mock median
    if ps:
        if ps > sector_ps * 3.0: vd = 10.0
        elif ps > sector_ps * 1.5: vd = 5.0
        elif ps < sector_ps: vd = 0.0
    factors["valuation_fall_height"] = vd

    # expectation_gap
    factors["expectation_gap"] = 5.0

    # insider_selling
    isa_score = 0.0
    ia = data.get("insider_activity", {})
    assessment = getattr(ia, "cluster_assessment", "") if not isinstance(ia, dict) else ia.get("cluster_assessment", "")
    if assessment == "Cluster-Verkäufe": isa_score = 10.0
    factors["insider_selling"] = isa_score

    # guidance_slowdown
    factors["guidance_slowdown"] = 5.0

    # leadership_instability
    factors["leadership_instability"] = 0.0

    # technical_downtrend
    factors["technical_downtrend"] = 5.0

    # macro_headwinds
    mh = 0.0
    macro = data.get("macro", {})
    vix = getattr(macro, "vix", 0) if not isinstance(macro, dict) else macro.get("vix", 0)
    if vix > 30: mh = 10.0
    elif vix < 15: mh = 0.0
    else: mh = 5.0
    factors["macro_headwinds"] = mh

    total_score = sum(factors[k] * weights.get(k, 0) for k in factors)
    
    return TorpedoScore(total_score=round(total_score, 2), factors=factors)

async def get_recommendation(opportunity: OpportunityScore, torpedo: TorpedoScore) -> AuditRecommendation:
    # Basic Threshold config mock (todo: move to scoring.yaml)
    opp = opportunity.total_score
    torp = torpedo.total_score
    
    rec = "Hold"
    reason = "Neutral."
    
    if opp > 7.5 and torp < 4.0:
        rec = "Strong Buy"
        reason = "Hohe Opportunität bei geringem Torpedo-Risiko."
    elif opp > 6.0 and torp < 5.0:
        rec = "Buy"
        reason = "Gute Opportunität bei vertretbarem Risiko."
    elif opp < 4.0 and torp > 6.0:
        rec = "Short"
        reason = "Schwache Opportunität bei hohem Risiko."
    elif opp < 3.0 and torp > 7.5:
        rec = "Strong Short"
        reason = "Sehr schwache Dynamik kombiniert mit gefährlichen Torpedos."
        
    return AuditRecommendation(recommendation=rec, reasoning=reason)
