import yaml
import os
from typing import Optional
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

    # technical_setup — aus echten yfinance-Daten
    technical_setup = 5.0
    tech = data.get("technicals", {})
    if isinstance(tech, dict) and tech:
        trend = tech.get("trend", "sideways")
        rsi = tech.get("rsi_14")
        above_50 = tech.get("above_sma50", False)
        above_200 = tech.get("above_sma200", False)
        dist_52w = tech.get("distance_to_52w_high_percent")

        if trend == "uptrend" and above_50 and above_200:
            technical_setup = 8.0
        elif trend == "uptrend":
            technical_setup = 7.0
        elif trend == "downtrend" and not above_200:
            technical_setup = 2.0
        elif trend == "downtrend":
            technical_setup = 3.0

        # RSI-Modifikator
        if rsi is not None:
            if 40 <= rsi <= 60:
                technical_setup = min(10.0, technical_setup + 1.0)  # Neutral = gut für Entry
            elif rsi > 75:
                technical_setup = max(0.0, technical_setup - 2.0)  # Überkauft
            elif rsi < 30:
                technical_setup = min(10.0, technical_setup + 1.5)  # Überverkauft = konträr bullisch

        # 52W-Hoch-Nähe als Bonus
        if dist_52w is not None and dist_52w > -5.0:
            technical_setup = min(10.0, technical_setup + 1.0)  # Nahe am Hoch = Momentum

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

    # technical_downtrend — aus echten yfinance-Daten
    technical_downtrend = 5.0
    tech = data.get("technicals", {})
    if isinstance(tech, dict) and tech:
        trend = tech.get("trend", "sideways")
        rsi = tech.get("rsi_14")
        above_200 = tech.get("above_sma200", False)
        dist_52w = tech.get("distance_to_52w_high_percent")

        if trend == "downtrend" and not above_200:
            technical_downtrend = 9.0
        elif trend == "downtrend":
            technical_downtrend = 7.0
        elif trend == "uptrend" and above_200:
            technical_downtrend = 1.0
        elif trend == "sideways":
            technical_downtrend = 4.0

        # RSI-Divergenz als Warnung
        if rsi is not None and rsi > 80:
            technical_downtrend = min(10.0, technical_downtrend + 2.0)  # Extrem überkauft = Rückschlagrisiko

        # Weit vom 52W-Hoch = bereits unter Druck
        if dist_52w is not None and dist_52w < -25.0:
            technical_downtrend = min(10.0, technical_downtrend + 1.5)

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
                eg_score = min(10.0, eg_score + 2.0)
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


def calculate_quality_score(
    debt_to_equity: Optional[float],
    current_ratio: Optional[float],
    free_cash_flow_yield: Optional[float],
    pe_ratio: Optional[float] = None
) -> float:
    """
    Berechnet Quality-Score (0-10) basierend auf fundamentalen Kennzahlen.
    
    Logik:
    - Debt-to-Equity < 1.5 = gut (3 Punkte)
    - Current Ratio > 1.2 = gut (3 Punkte)
    - Free Cash Flow Yield > 0 = gut (4 Punkte)
    - Value Trap Detection: Hohe Schulden + negativer FCF = harte Strafe (-5 Punkte)
    
    Returns: Score zwischen 0-10
    """
    score = 0.0
    
    # 1. Debt-to-Equity Check (3 Punkte)
    if debt_to_equity is not None:
        if debt_to_equity < 1.0:
            score += 3.0  # Sehr gesund
        elif debt_to_equity < 1.5:
            score += 2.0  # Akzeptabel
        elif debt_to_equity < 2.5:
            score += 1.0  # Erhöht
        else:
            score += 0.0  # Kritisch
    else:
        score += 1.5  # Neutral wenn keine Daten
    
    # 2. Current Ratio Check (3 Punkte)
    if current_ratio is not None:
        if current_ratio > 2.0:
            score += 3.0  # Sehr liquide
        elif current_ratio > 1.2:
            score += 2.5  # Gesund
        elif current_ratio > 1.0:
            score += 1.5  # Knapp
        else:
            score += 0.0  # Liquiditätsprobleme
    else:
        score += 1.5  # Neutral wenn keine Daten
    
    # 3. Free Cash Flow Yield Check (4 Punkte)
    if free_cash_flow_yield is not None:
        if free_cash_flow_yield > 0.05:  # > 5%
            score += 4.0  # Starker FCF
        elif free_cash_flow_yield > 0.02:  # > 2%
            score += 3.0  # Positiver FCF
        elif free_cash_flow_yield > 0:
            score += 2.0  # Leicht positiv
        else:
            score += 0.0  # Negativer FCF = Problem
    else:
        score += 2.0  # Neutral wenn keine Daten
    
    # 4. Value Trap Detection (Strafe)
    # Hohe Schulden + negativer FCF = klassische Value Trap
    if (debt_to_equity is not None and debt_to_equity > 2.0 and 
        free_cash_flow_yield is not None and free_cash_flow_yield < 0):
        score = max(0.0, score - 5.0)
        logger.warning(f"Value Trap erkannt: D/E={debt_to_equity:.2f}, FCF Yield={free_cash_flow_yield:.4f}")
    
    # Zusätzliche Strafe: Sehr hohe Schulden + kein FCF-Wachstum
    if (debt_to_equity is not None and debt_to_equity > 3.0):
        score = max(0.0, score - 2.0)
        logger.warning(f"Kritische Verschuldung: D/E={debt_to_equity:.2f}")
    
    return min(10.0, round(score, 2))


def calculate_mismatch_score(
    sentiment_score: float,
    quality_score: float,
    beta: float,
    iv_atm: Optional[float] = None,
    hist_vol: Optional[float] = None
) -> float:
    """
    Berechnet Mismatch-Score - die Kernmetrik für Contrarian-Trading-Opportunities.
    
    Trigger-Logik:
    - Sentiment extrem negativ (< -0.5) = Market überreagiert
    - Quality Score hoch (> 6/10) = Fundamentals intakt
    - Beta hoch (> 1.2) = Volatile Aktie mit starker Bewegung
    - IV vs. Hist Vol Spread = Optionen-Timing
    
    Returns: Score zwischen 0-100 (je höher desto stärker die Contrarian-Opportunity)
    """
    score = 0.0
    
    # 1. Sentiment-Check (max 40 Punkte)
    # Je negativer das Sentiment, desto höher die Contrarian-Chance
    if sentiment_score < -0.7:
        score += 40.0  # Extremer Pessimismus
    elif sentiment_score < -0.5:
        score += 30.0  # Starker Pessimismus
    elif sentiment_score < -0.3:
        score += 20.0  # Moderater Pessimismus
    elif sentiment_score < -0.1:
        score += 10.0  # Leichter Pessimismus
    else:
        score += 0.0  # Kein negativer Sentiment = kein Contrarian-Setup
    
    # 2. Quality-Check (max 30 Punkte)
    # Fundamentals müssen intakt sein, sonst ist es eine Value Trap
    if quality_score >= 8.0:
        score += 30.0  # Exzellente Fundamentals
    elif quality_score >= 6.0:
        score += 25.0  # Gute Fundamentals
    elif quality_score >= 4.0:
        score += 15.0  # Akzeptable Fundamentals
    else:
        score += 0.0  # Schwache Fundamentals = Value Trap Gefahr
    
    # 3. Beta-Check (max 20 Punkte)
    # Hohe Volatilität = größere Chancen aber auch Risiken
    if beta >= 1.5:
        score += 20.0  # Sehr volatile Aktie
    elif beta >= 1.2:
        score += 15.0  # Volatile Aktie
    elif beta >= 1.0:
        score += 10.0  # Durchschnittliche Volatilität
    else:
        score += 5.0  # Niedrige Volatilität = weniger attraktiv für Contrarian-Plays
    
    # 4. Options-Timing (max 10 Punkte Bonus)
    # IV vs. Historical Vol Spread gibt Hinweis auf Options-Pricing
    if iv_atm is not None and hist_vol is not None:
        iv_spread = iv_atm - hist_vol
        
        if iv_spread > 10.0:
            # IV deutlich höher als historische Vola = Optionen teuer
            score += 0.0  # Kein Bonus, Options zu teuer
            logger.info(f"IV zu teuer: {iv_atm:.2f}% vs. Hist {hist_vol:.2f}% (Spread: +{iv_spread:.2f}%)")
        elif iv_spread > 5.0:
            score += 5.0  # Leicht erhöhte IV
        elif iv_spread < -5.0:
            # IV niedriger als historische Vola = Optionen günstig!
            score += 10.0  # Bonus für günstige Options
            logger.info(f"IV günstig: {iv_atm:.2f}% vs. Hist {hist_vol:.2f}% (Spread: {iv_spread:.2f}%)")
        else:
            score += 7.0  # Neutrale IV
    
    # 5. Contrarian-Boost
    # Wenn alle Kriterien erfüllt sind, extra Boost
    if sentiment_score < -0.5 and quality_score > 6.0 and beta > 1.2:
        score = min(100.0, score + 10.0)
        logger.info(f"🎯 CONTRARIAN SETUP: Sentiment={sentiment_score:.2f}, Quality={quality_score:.1f}, Beta={beta:.2f}")
    
    return min(100.0, round(score, 2))
