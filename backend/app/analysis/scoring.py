import yaml
import os
from schemas.scores import OpportunityScore, TorpedoScore, AuditRecommendation
from backend.app.logger import get_logger
from backend.app.config import settings

logger = get_logger(__name__)

def _load_scoring_config() -> dict:
    return settings.scoring

async def calculate_opportunity_score(ticker: str, data: dict) -> OpportunityScore:
    """
    Berechnet den Opportunity-Score basierend auf positiven Katalysatoren.
    """
    scoring_config = _load_scoring_config()
    weights = scoring_config.get("opportunity_score", {})
    
    # earnings_momentum
    em = 0.0
    history = data.get("earnings_history")
    quarters_beat = getattr(history, "quarters_beat", 0) if not isinstance(history, dict) else history.get("quarters_beat", 0) if history else 0
    avg_surprise = getattr(history, "avg_surprise_percent", 0.0) if not isinstance(history, dict) else history.get("avg_surprise_percent", 0.0) if history else 0.0
    if quarters_beat == 8 and avg_surprise > 0:
        em = 10.0
    elif quarters_beat == 0:
        em = 0.0
    else:
        em = (quarters_beat / 8.0) * 10.0

    # whisper_delta
    whisper_delta = 5.0 

    # valuation_regime
    vr = 5.0
    val = data.get("valuation")
    pe = getattr(val, "pe_ratio", None) if not isinstance(val, dict) else val.get("pe_ratio") if val else None
    sector_pe = getattr(val, "pe_sector_median", 15.0) if not isinstance(val, dict) else val.get("pe_sector_median", 15.0) if val else 15.0
    if pe and sector_pe:
        if pe < sector_pe * 0.8: vr = 10.0
        elif pe > sector_pe * 2.0: vr = 0.0
        else: vr = 5.0

    # Narrative Intelligence: Positive Regime Shifts
    news_memory = data.get("news_memory", [])
    for news in news_memory:
        shift_type = news.get("shift_type", "None")
        if news.get("is_narrative_shift", False):
            if shift_type in ["Market-Expansion", "Strategic-Partnership", "Disruptive Pivot"]:
                vr = min(10.0, vr + 2.0)
                logger.debug(f"[{ticker}] Positive Narrative Shift erkannt ({shift_type}). Valuation Regime +2.0 auf {vr}")
                break

    # guidance_trend
    guidance_trend = 5.0

    # technical_setup
    technical_setup = 5.0

    # sector_regime
    sector_regime = 5.0

    # short_squeeze_potential
    ss = 0.0
    si_data = data.get("short_interest")
    si_pct = getattr(si_data, "short_interest_percent", 0.0) if not isinstance(si_data, dict) else si_data.get("short_interest_percent", 0.0) if si_data else 0.0
    dtc = getattr(si_data, "days_to_cover", 0.0) if not isinstance(si_data, dict) else si_data.get("days_to_cover", 0.0) if si_data else 0.0
    
    if si_pct > 30 and dtc > 5: ss = 10.0
    elif 15 <= si_pct <= 30: ss = 5.0
    elif si_pct < 10: ss = 0.0
    else: ss = 2.5

    # insider_activity
    ia_score = 5.0
    ia = data.get("insider_activity")
    assessment = getattr(ia, "assessment", "") if not isinstance(ia, dict) else ia.get("assessment", "") if ia else ""
    if assessment == "bullish": ia_score = 10.0
    elif assessment == "bearish": ia_score = 0.0

    # options_flow
    of_score = 5.0
    options = data.get("options", {})
    pcr = options.get("put_call_ratio_oi", 0.0) if isinstance(options, dict) else 0.0
    if pcr > 1.2:
        of_score = min(10.0, of_score + 2.0)  # Konträr-Signal

    total_score = (
        em * weights.get("earnings_momentum", 0) +
        whisper_delta * weights.get("whisper_delta", 0) +
        vr * weights.get("valuation_regime", 0) +
        guidance_trend * weights.get("guidance_trend", 0) +
        technical_setup * weights.get("technical_setup", 0) +
        sector_regime * weights.get("sector_regime", 0) +
        ss * weights.get("short_squeeze_potential", 0) +
        ia_score * weights.get("insider_activity", 0) +
        of_score * weights.get("options_flow", 0)
    )
    
    return OpportunityScore(
        ticker=ticker,
        total_score=round(total_score, 2),
        earnings_momentum=round(em, 2),
        whisper_delta=round(whisper_delta, 2),
        valuation_regime=round(vr, 2),
        guidance_trend=round(guidance_trend, 2),
        technical_setup=round(technical_setup, 2),
        sector_regime=round(sector_regime, 2),
        short_squeeze_potential=round(ss, 2),
        insider_activity=round(ia_score, 2),
        options_flow=round(of_score, 2)
    )

async def calculate_torpedo_score(ticker: str, data: dict) -> TorpedoScore:
    """
    Berechnet den Torpedo-Score basierend auf negativen Risikofaktoren.
    """
    scoring_config = _load_scoring_config()
    weights = scoring_config.get("torpedo_score", {})
    
    # valuation_downside
    vd = 0.0
    val = data.get("valuation")
    ps = getattr(val, "ps_ratio", None) if not isinstance(val, dict) else val.get("ps_ratio") if val else None
    sector_ps = getattr(val, "ps_sector_median", 3.0) if not isinstance(val, dict) else val.get("ps_sector_median", 3.0) if val else 3.0
    if ps:
        if ps > sector_ps * 3.0: vd = 10.0
        elif ps > sector_ps * 1.5: vd = 5.0
        elif ps < sector_ps: vd = 0.0

    # expectation_gap
    eg_score = 5.0
    options = data.get("options", {})
    iv_atm = options.get("implied_volatility_atm", 0.0) if isinstance(options, dict) else 0.0
    if iv_atm > 0.80:
        eg_score = min(10.0, eg_score + 2.0)

    # insider_selling
    isa_score = 0.0
    ia = data.get("insider_activity")
    assessment = getattr(ia, "assessment", "") if not isinstance(ia, dict) else ia.get("assessment", "") if ia else ""
    if assessment == "bearish": isa_score = 10.0

    # guidance_deceleration
    guidance_deceleration = 5.0

    # leadership_instability
    leadership_instability = 0.0

    # technical_downtrend
    technical_downtrend = 5.0

    # macro_headwind
    mh = 0.0
    macro = data.get("macro")
    vix = getattr(macro, "vix", 0.0) if not isinstance(macro, dict) else macro.get("vix", 0.0) if macro else 0.0
    if vix > 30: mh = 10.0
    elif vix < 15: mh = 0.0
    else: mh = 5.0

    # Narrative Intelligence: Torpedo Signals via Downsizing
    news_memory = data.get("news_memory", [])
    for news in news_memory:
        shift_type = news.get("shift_type", "None")
        if news.get("is_narrative_shift", False):
            if shift_type == "Strategic-Downsizing":
                guidance_deceleration = min(10.0, guidance_deceleration + 2.0)
                expectation_gap = min(10.0, expectation_gap + 2.0)
                logger.warning(f"[{ticker}] 🚨 Negative Narrative Shift erkannt ({shift_type}). Torpedo-Scores erhöht!")
                break

    total_score = (
        vd * weights.get("valuation_downside", 0) +
        eg_score * weights.get("expectation_gap", 0) +
        isa_score * weights.get("insider_selling", 0) +
        guidance_deceleration * weights.get("guidance_deceleration", 0) +
        leadership_instability * weights.get("leadership_instability", 0) +
        technical_downtrend * weights.get("technical_downtrend", 0) +
        mh * weights.get("macro_headwind", 0)
    )
    
    return TorpedoScore(
        ticker=ticker,
        total_score=round(total_score, 2),
        valuation_downside=round(vd, 2),
        expectation_gap=round(eg_score, 2),
        insider_selling=round(isa_score, 2),
        guidance_deceleration=round(guidance_deceleration, 2),
        leadership_instability=round(leadership_instability, 2),
        technical_downtrend=round(technical_downtrend, 2),
        macro_headwind=round(mh, 2)
    )

async def get_recommendation(opportunity: OpportunityScore, torpedo: TorpedoScore) -> AuditRecommendation:
    """
    Kombiniert Opportunity- und Torpedo-Scores in eine finale Empfehlung (Buy, Hold, Short etc.).
    """
    scoring_config = _load_scoring_config()
    thresholds = scoring_config.get("thresholds", {})
    
    opp = opportunity.total_score
    torp = torpedo.total_score
    
    rec = "hold"
    rec_label = "Kein Trade"
    reason = "Weder starke Opportunität noch gefährliche Torpedos."
    
    sb_min_opp = thresholds.get("strong_buy_min_opportunity", 7.0)
    sb_max_torp = thresholds.get("strong_buy_max_torpedo", 3.0)
    ss_max_opp = thresholds.get("strong_short_max_opportunity", 3.0)
    ss_min_torp = thresholds.get("strong_short_min_torpedo", 7.0)
    watch_min_torp = thresholds.get("watch_min_torpedo", 7.0)

    if opp >= sb_min_opp and torp <= sb_max_torp:
        rec = "strong_buy"
        rec_label = "Strong Buy"
        reason = "Hohe Opportunität bei geringem Torpedo-Risiko."
    elif opp >= sb_min_opp - 1.0 and torp <= sb_max_torp + 1.0:
        rec = "buy_hedge" 
        rec_label = "Buy mit Absicherung"
        reason = "Gute Opportunität, aber absicherungswürdiges Risiko."
    elif opp <= ss_max_opp and torp >= ss_min_torp:
        rec = "strong_short"
        rec_label = "Strong Short"
        reason = "Sehr schwache Dynamik kombiniert mit gefährlichen Torpedos."
    elif opp <= ss_max_opp + 1.0 and torp >= ss_min_torp - 1.0:
        rec = "potential_short"
        rec_label = "Potentieller Short"
        reason = "Schwache Opportunität und erhöhtes Risiko."
    elif torp >= watch_min_torp:
        rec = "watch"
        rec_label = "Beobachten"
        reason = "Hohes Risiko, aber Opportunität ist unklar. Beobachten."
    elif opp < 4.0 and torp < 4.0:
        rec = "ignore"
        rec_label = "Ignorieren"
        reason = "Keine Signale."
        
    return AuditRecommendation(
        ticker=opportunity.ticker,
        opportunity_score=opportunity,
        torpedo_score=torpedo,
        recommendation=rec,
        recommendation_label=rec_label,
        reasoning=reason
    )
