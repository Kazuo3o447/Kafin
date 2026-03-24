import yaml
import os
from typing import Optional
from schemas.scores import OpportunityScore, TorpedoScore, AuditRecommendation
from backend.app.logger import get_logger
from backend.app.config import settings

logger = get_logger(__name__)

# Sektor zu ETF Mapping für sector_regime
_SECTOR_TO_ETF = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Energy": "XLE",
    "Healthcare": "XLV",
    "Health Care": "XLV",
    "Utilities": "XLU",
    "Industrials": "XLI",
    "Communication Services": "XLC",
    "Communication": "XLC",
    "Consumer Cyclical": "XLY",
    "Consumer Discretionary": "XLY",
    "Consumer Defensive": "XLP",
    "Consumer Staples": "XLP",
    "Basic Materials": "XLB",
    "Materials": "XLB",
    "Real Estate": "XLRE",
}

def _normalize_grade(grade_str) -> str:
    """Normalisiert Analyst-Grade Strings für Vergleiche."""
    if not grade_str:
        return ""
    return str(grade_str).strip().lower()

_BULLISH_GRADES = frozenset([
    "strong buy", "buy", "outperform", "overweight", "accumulate"
])
_BEARISH_GRADES = frozenset([
    "sell", "underperform", "underweight", "reduce", "strong sell"
])

def _load_scoring_config() -> dict:
    return settings.scoring

async def calculate_opportunity_score(ticker: str, data: dict) -> OpportunityScore:
    """
    Berechnet den Opportunity-Score basierend auf positiven Katalysatoren.
    """
    scoring_config = _load_scoring_config()
    weights = scoring_config.get("opportunity_score", {})
    
    # ── Data Completeness Tracking ────────────────────────────────
    _missing: list[str] = []
    _total_fields = 9  # Anzahl gewichteter Eingabe-Dimensionen

    def _track(field_name: str, value_present: bool):
        if not value_present:
            _missing.append(field_name)
    
    # earnings_momentum
    em = 5.0  # Neutral-Default bei fehlenden Daten
    history = data.get("earnings_history")
    _track("earnings_momentum", history is not None)
    quarters_beat = getattr(history, "quarters_beat", 0) if not isinstance(history, dict) else history.get("quarters_beat", 0) if history else 0
    avg_surprise = getattr(history, "avg_surprise_percent", 0.0) if not isinstance(history, dict) else history.get("avg_surprise_percent", 0.0) if history else 0.0

    if history is None or quarters_beat is None:
        em = 5.0  # Keine Daten = neutral, nicht bullish oder bearish
    elif quarters_beat == 8 and avg_surprise > 0:
        em = 10.0
    elif quarters_beat == 0:
        em = 0.0
    else:
        em = (quarters_beat / 8.0) * 10.0

    # whisper_delta: Proxy über historische Beat-Konsistenz
    # Je mehr Quartale beaten + je höher avg_surprise,
    # desto höher der implizite Whisper über Konsens.
    whisper_delta = 5.0  # Neutral-Start
    _track("whisper_delta", data.get("earnings_history") is not None)
    try:
        history = data.get("earnings_history")
        qb = (
            getattr(history, "quarters_beat", None)
            if not isinstance(history, dict)
            else history.get("quarters_beat")
        ) if history else None
        avg_s = (
            getattr(history, "avg_surprise_percent", None)
            if not isinstance(history, dict)
            else history.get("avg_surprise_percent")
        ) if history else None

        if qb is not None and avg_s is not None:
            # 8/8 Beats mit hohem Surprise = Whisper
            # deutlich über Konsens = starkes Signal
            if qb >= 7 and avg_s >= 10.0:
                whisper_delta = 9.0
            elif qb >= 6 and avg_s >= 5.0:
                whisper_delta = 7.5
            elif qb >= 5 and avg_s >= 2.0:
                whisper_delta = 6.0
            elif qb >= 4:
                whisper_delta = 5.0
            elif qb <= 2 or avg_s < 0:
                whisper_delta = 2.0
            elif qb == 0:
                whisper_delta = 0.0  # 0/8 Beats = sehr schwach
            else:
                whisper_delta = 4.0
    except Exception:
        whisper_delta = 5.0 

    # valuation_regime
    vr = 5.0
    val = data.get("valuation")
    _track("valuation_regime", val is not None and (
        getattr(val, "pe_ratio", None) or
        (val.get("pe_ratio") if isinstance(val, dict) else None)
    ) is not None)
    pe = getattr(val, "pe_ratio", None) if not isinstance(val, dict) else val.get("pe_ratio") if val else None
    sector_pe = (getattr(val, "pe_sector_median", None) or 15.0) if not isinstance(val, dict) else (val.get("pe_sector_median") or 15.0) if val else 15.0
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

    # guidance_trend: Analyst-Upgrade/Downgrade Trend
    # Mehr Upgrades = Analysten erhöhen Erwartungen
    # = Management liefert positive Signale
    guidance_trend = 5.0
    grades = data.get("analyst_grades", [])
    _track("guidance_trend", bool(grades and len(grades) >= 3))
    try:
        if grades and len(grades) > 0:
            # Mindest-Sample-Gate: erst ab 3 Grades ein Signal
            if len(grades) < 3:
                guidance_trend = 5.0  # neutral bei zu kleinem Sample
            else:
                # Robuste Key-Normalisierung (camelCase + lowercase)
                def normalize_grade(grade_str):
                    if not grade_str:
                        return ""
                    return str(grade_str).strip().lower()
                
                upgrades = sum(
                    1 for g in grades
                    if normalize_grade(g.get("newGrade")) in ["strong buy", "buy", "outperform",
                        "overweight", "accumulate"]
                    and normalize_grade(g.get("previousGrade")) not in ["strong buy", "buy", "outperform",
                            "overweight", "accumulate"]
                )
                downgrades = sum(
                    1 for g in grades
                    if normalize_grade(g.get("newGrade")) in ["sell", "underperform", "underweight",
                        "reduce", "strong sell"]
                    and normalize_grade(g.get("previousGrade")) not in ["sell", "underperform", "underweight",
                            "reduce", "strong sell"]
                )
                holds = len(grades) - upgrades - downgrades

                # Recency-Weighting: neuere Grades zählen mehr
                # (vereinfacht: bei 5 Grades, die letzten 3 zählen doppelt)
                def _parse_grade_date(g: dict) -> str:
                    return g.get("date", g.get("gradedDate", g.get("updatedDate", "")))

                try:
                    grades_sorted = sorted(
                        grades,
                        key=_parse_grade_date,
                        reverse=True  # Neueste zuerst
                    )
                except Exception:
                    grades_sorted = grades  # Fallback unsortiert

                recent_grades = grades_sorted[:3] if len(grades_sorted) >= 3 else grades_sorted
                recent_upgrades = sum(
                    1 for g in recent_grades
                    if normalize_grade(g.get("newGrade")) in ["strong buy", "buy", "outperform",
                        "overweight", "accumulate"]
                    and normalize_grade(g.get("previousGrade")) not in ["strong buy", "buy", "outperform",
                            "overweight", "accumulate"]
                )
                recent_downgrades = sum(
                    1 for g in recent_grades
                    if normalize_grade(g.get("newGrade")) in ["sell", "underperform", "underweight",
                        "reduce", "strong sell"]
                    and normalize_grade(g.get("previousGrade")) not in ["sell", "underperform", "underweight",
                            "reduce", "strong sell"]
                )

                # Weighted score: recent = 2x, older = 1x
                weighted_upgrades = upgrades + recent_upgrades
                weighted_downgrades = downgrades + recent_downgrades

                if weighted_upgrades >= 4:
                    guidance_trend = 9.0
                elif weighted_upgrades >= 3 and weighted_downgrades == 0:
                    guidance_trend = 8.0
                elif weighted_upgrades > weighted_downgrades:
                    guidance_trend = 7.0
                elif weighted_downgrades > weighted_upgrades:
                    guidance_trend = 3.0
                elif weighted_downgrades >= 3:
                    guidance_trend = 1.5
                else:
                    guidance_trend = 5.0  # neutral
    except Exception:
        guidance_trend = 5.0

    # technical_setup — aus echten yfinance-Daten
    technical_setup = 5.0
    tech = data.get("technicals", {})
    _track("technical_setup", bool(tech))
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

        # ADX-Modifikator: Trendstärke bestätigt oder widerlegt Setup
        adx = tech.get("adx_14") if isinstance(tech, dict) else getattr(tech, "adx_14", None)
        adx_strength = tech.get("adx_trend_strength") if isinstance(tech, dict) else getattr(tech, "adx_trend_strength", None)

        if adx is not None:
            if adx >= 30:
                # Starker bestätigter Trend — Setup ist valide
                technical_setup = min(10.0, technical_setup + 1.5)
            elif adx >= 20:
                # Moderater Trend — leichter Bonus
                technical_setup = min(10.0, technical_setup + 0.5)
            elif adx < 15:
                # Kein Trend — technisches Setup ist unsicher
                technical_setup = max(0.0, technical_setup - 1.0)

        # Stochastic-Modifikator: Momentum-Confirmation
        stoch_k = tech.get("stoch_k") if isinstance(tech, dict) else getattr(tech, "stoch_k", None)
        stoch_signal = tech.get("stoch_signal") if isinstance(tech, dict) else getattr(tech, "stoch_signal", None)

        if stoch_signal == "bullish_cross":
            # Stoch kreuzt aufwärts: starkes Kauf-Signal
            technical_setup = min(10.0, technical_setup + 1.0)
        elif stoch_signal == "oversold":
            # Überverkauft: möglicher Bounce — kontextuell bullisch
            technical_setup = min(10.0, technical_setup + 0.5)
        elif stoch_signal == "bearish_cross":
            # Stoch kreuzt abwärts: Warnung
            technical_setup = max(0.0, technical_setup - 0.5)
        elif stoch_signal == "overbought":
            # Überkauft: kein guter Entry-Punkt
            technical_setup = max(0.0, technical_setup - 1.0)

    # sector_regime: Sektor-ETF 5T-Performance
    # als Rücken- oder Gegenwind für den Ticker
    sector_regime = 5.0
    _track("sector_regime", bool(
        data.get("sector_ranking") and data.get("ticker_sector")
    ))
    try:
        sector_ranking = data.get("sector_ranking", [])
        ticker_sector = data.get("ticker_sector", "")
        sector_etf = _SECTOR_TO_ETF.get(ticker_sector)

        if sector_etf and sector_ranking:
            # Suche den Sektor-ETF in der Ranking-Liste
            sector_entry = next(
                (s for s in sector_ranking
                 if s.get("symbol") == sector_etf),
                None
            )
            if sector_entry:
                perf_5d = sector_entry.get("perf_5d", 0.0)
                # Sektor-Performance → Rückenwind/Gegenwind
                if perf_5d >= 3.0:
                    sector_regime = 9.0   # starker Rückenwind
                elif perf_5d >= 1.5:
                    sector_regime = 7.5   # Rückenwind
                elif perf_5d >= 0.5:
                    sector_regime = 6.5   # leichter Rückenwind
                elif perf_5d >= -0.5:
                    sector_regime = 5.0   # neutral
                elif perf_5d >= -1.5:
                    sector_regime = 3.5   # leichter Gegenwind
                elif perf_5d >= -3.0:
                    sector_regime = 2.0   # Gegenwind
                else:
                    sector_regime = 1.0   # starker Gegenwind
    except Exception:
        sector_regime = 5.0

    # short_squeeze_potential       
    ss = 5.0  # Neutral wenn keine Daten
    si_data = data.get("short_interest")
    _track("short_squeeze_potential", si_data is not None)
    if si_data is None:
        ss = 5.0
    else:
        si_pct = getattr(si_data, "short_interest_percent", 0.0) if not isinstance(si_data, dict) else si_data.get("short_interest_percent", si_data.get("short_interest", 0.0)) if si_data else 0.0
        dtc = getattr(si_data, "days_to_cover", 0.0) if not isinstance(si_data, dict) else si_data.get("days_to_cover", 0.0) if si_data else 0.0
        
        if si_pct > 30 and dtc > 5: ss = 10.0
        elif 15 <= si_pct <= 30: ss = 5.0
        elif si_pct < 10: ss = 0.0
        else: ss = 2.5

    # insider_activity
    ia_score = 5.0
    ia = data.get("insider_activity")
    _track("insider_activity", ia is not None)
    assessment = getattr(ia, "assessment", "") if not isinstance(ia, dict) else ia.get("assessment", "") if ia else ""
    cluster_assessment = getattr(ia, "cluster_assessment", "") if not isinstance(ia, dict) else ia.get("cluster_assessment", "") if ia else ""
    assessment_text = f"{assessment} {cluster_assessment}".strip().lower()
    if "bullish" in assessment_text or "kauf" in assessment_text or "käuf" in assessment_text or "buy" in assessment_text:
        ia_score = 10.0
    elif "bearish" in assessment_text or "verkauf" in assessment_text or "verkäuf" in assessment_text or "sell" in assessment_text:
        ia_score = 0.0

    # options_flow
    of_score = 5.0
    options = data.get("options", {})
    _track("options_flow", bool(options))
    pcr = options.get("put_call_ratio_oi", 0.0) if isinstance(options, dict) else 0.0
    if pcr > 1.2:
        of_score = min(10.0, of_score + 2.0)  # Konträr-Signal

    # ── Kontextueller Options-Flow-Boost vor Earnings ─────────────
    # Unusual Options Activity ist das früheste Smart-Money-Signal
    # vor Earnings. 5% Standardgewicht unterschätzt das massiv.
    # Wenn Earnings in ≤ 5 Tagen: Budget von Valuation und Technical umschichten.
    #
    # Budget-Neutralität: +7% auf options_flow
    #                     −4% von valuation_regime
    #                     −3% von technical_setup
    # Summe aller Gewichte bleibt 1.0.
    earnings_countdown = data.get("earnings_countdown")
    _weights = dict(weights)  # Kopie — Original nicht mutieren

    if (
        earnings_countdown is not None
        and isinstance(earnings_countdown, (int, float))
        and 0 <= earnings_countdown <= 5
    ):
        _weights["options_flow"]     = 0.12   # statt 0.05 (+7%)
        _weights["valuation_regime"] = 0.11   # statt 0.15 (-4%)
        _weights["technical_setup"]  = 0.07   # statt 0.10 (-3%)
        logger.debug(
            f"[{ticker}] Options-Flow-Boost aktiv: Earnings in {earnings_countdown}T "
            f"— options_flow 5%→12%, valuation 15%→11%, technical 10%→7%"
        )
    else:
        _weights = weights  # Standard-Gewichte aus scoring.yaml
    # ── Ende Options-Flow-Boost ──────────────────────────────────

    total_score = (
        em * _weights.get("earnings_momentum", 0) +
        whisper_delta * _weights.get("whisper_delta", 0) +
        vr * _weights.get("valuation_regime", 0) +
        guidance_trend * _weights.get("guidance_trend", 0) +
        technical_setup * _weights.get("technical_setup", 0) +
        sector_regime * _weights.get("sector_regime", 0) +
        ss * _weights.get("short_squeeze_potential", 0) +
        ia_score * _weights.get("insider_activity", 0) +
        of_score * _weights.get("options_flow", 0)
    )

    logger.debug(
        f"[{ticker}] Opp-Score {total_score:.2f} | "
        f"whisper={whisper_delta:.1f} "
        f"guidance={guidance_trend:.1f} "
        f"sector={sector_regime:.1f} "
        f"em={em:.1f} tech={technical_setup:.1f}"
        f"{' [Options-Boost aktiv: EC=' + str(earnings_countdown) + 'T]' if earnings_countdown is not None and 0 <= earnings_countdown <= 5 else ''}"
    )
    
    # ── Completeness berechnen ────────────────────────────────────
    data_completeness = round(
        1.0 - (len(_missing) / _total_fields), 2
    )
    logger.debug(
        f"[{ticker}] Opp Completeness: {data_completeness:.0%} "
        f"— fehlend: {_missing or 'keine'}"
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
        options_flow=round(of_score, 2),
        data_completeness=data_completeness,
        missing_fields=_missing,
    )

async def calculate_torpedo_score(ticker: str, data: dict) -> TorpedoScore:
    """
    Berechnet den Torpedo-Score basierend auf negativen Risikofaktoren.
    """
    scoring_config = _load_scoring_config()
    weights = scoring_config.get("torpedo_score", {})
    
    # ── Data Completeness Tracking ────────────────────────────────
    _missing: list[str] = []
    _total_fields = 7  # Torpedo hat 7 Dimensionen

    def _track(field_name: str, value_present: bool):
        if not value_present:
            _missing.append(field_name)
    
    # valuation_downside
    vd = 4.0  # VORHER: 0.0 — IPO/fehlende Daten = leicht erhöhtes Risiko
    val = data.get("valuation")
    _track("valuation_downside", val is not None and (
        getattr(val, "ps_ratio", None) or
        (val.get("ps_ratio") if isinstance(val, dict) else None)
    ) is not None)
    if val is None:
        vd = 4.0  # Explizit: keine Bewertungsdaten = Vorsicht
    else:
        ps = getattr(val, "ps_ratio", None) if not isinstance(val, dict) else val.get("ps_ratio") if val else None
        sector_ps = (getattr(val, "ps_sector_median", None) or 3.0) if not isinstance(val, dict) else (val.get("ps_sector_median") or 3.0) if val else 3.0
        if ps:
            if ps > sector_ps * 3.0: vd = 10.0
            elif ps > sector_ps * 1.5: vd = 5.0
            elif ps < sector_ps: vd = 0.0

    # expectation_gap — erweitert um Web-Sentiment
    eg_score = 5.0
    options = data.get("options", {})
    _track("expectation_gap", bool(options and (
        options.get("implied_volatility_atm") if isinstance(options, dict) else False
    )))
    iv_atm = (
        options.get("implied_volatility_atm", 0.0)
        if isinstance(options, dict) else 0.0
    )
    if iv_atm > 0.80:
        eg_score = min(10.0, eg_score + 2.0)

    # Web-Sentiment-Divergenz erhöht Torpedo
    # (bullische News + bärischer Web-Diskurs = "Buy the Rumor")
    web_sent = data.get("web_sentiment_score", 0.0)
    finbert_sent = data.get("finbert_sentiment", 0.0)
    divergence = data.get("sentiment_divergence", False)

    if divergence and finbert_sent > 0.2 and web_sent < -0.2:
        # Klassisches Abverkauf-nach-Beat Setup
        eg_score = min(10.0, eg_score + 2.5)
        logger.warning(
            f"[{ticker}] 🚨 Sentiment-Divergenz: "
            f"Torpedo expectation_gap +2.5 auf {eg_score:.1f}"
        )
    elif web_sent < -0.4:
        # Web-Diskurs stark bärisch — unabhängig von FinBERT
        eg_score = min(10.0, eg_score + 1.5)
        logger.info(
            f"[{ticker}] Web-Sentiment bärisch ({web_sent:.2f}): "
            f"expectation_gap +1.5 auf {eg_score:.1f}"
        )

    # insider_selling
    isa_score = 0.0
    ia = data.get("insider_activity")
    assessment = getattr(ia, "assessment", "") if not isinstance(ia, dict) else ia.get("assessment", "") if ia else ""
    cluster_assessment = getattr(ia, "cluster_assessment", "") if not isinstance(ia, dict) else ia.get("cluster_assessment", "") if ia else ""
    assessment_text = f"{assessment} {cluster_assessment}".strip().lower()
    if "bearish" in assessment_text or "verkauf" in assessment_text or "verkäuf" in assessment_text or "sell" in assessment_text:
        isa_score = 10.0

    # Reddit-Verstärker: Retail gierig + Insider verkauft
    # = verstärktes Torpedo-Signal
    reddit_score = data.get("reddit_sentiment")
    reddit_mentions = data.get("reddit_mentions", 0)
    if (reddit_score is not None
            and reddit_score > 0.2   # Retail bullisch
            and reddit_mentions >= 5
            and isa_score > 0.5):    # Insider verkauft
        # Max 20% Verstärkung
        isa_score = min(10.0, isa_score * 1.2)
        logger.debug(
            f"Reddit-Divergenz Verstärker aktiv: "
            f"retail={reddit_score:.2f}, "
            f"mentions={reddit_mentions}"
        )

    # guidance_deceleration: Analyst-Downgrade Druck
    # Downgrades = Analysten sehen Risiken die der
    # Markt noch nicht eingepreist hat
    guidance_deceleration = 5.0
    try:
        grades = data.get("analyst_grades", [])
        if grades and len(grades) > 0:
            # Mindest-Sample-Gate: erst ab 3 Grades ein Signal
            if len(grades) < 3:
                guidance_deceleration = 5.0  # neutral bei zu kleinem Sample
            else:
                # Robuste Key-Normalisierung (camelCase + lowercase)
                def normalize_grade(grade_str):
                    if not grade_str:
                        return ""
                    return str(grade_str).strip().lower()
                
                upgrades_t = sum(
                    1 for g in grades
                    if normalize_grade(g.get("newGrade")) in ["strong buy", "buy", "outperform",
                        "overweight", "accumulate"]
                    and normalize_grade(g.get("previousGrade")) not in ["strong buy", "buy", "outperform",
                            "overweight", "accumulate"]
                )
                downgrades_t = sum(
                    1 for g in grades
                    if normalize_grade(g.get("newGrade")) in ["sell", "underperform", "underweight",
                        "reduce", "strong sell"]
                    and normalize_grade(g.get("previousGrade")) not in ["sell", "underperform", "underweight",
                            "reduce", "strong sell"]
                )

                # Recency-Weighting: neuere Grades zählen mehr
                def _parse_grade_date(g: dict) -> str:
                    return g.get("date", g.get("gradedDate", g.get("updatedDate", "")))

                try:
                    grades_sorted = sorted(
                        grades,
                        key=_parse_grade_date,
                        reverse=True  # Neueste zuerst
                    )
                except Exception:
                    grades_sorted = grades  # Fallback unsortiert

                recent_grades = grades_sorted[:3] if len(grades_sorted) >= 3 else grades_sorted
                recent_upgrades_t = sum(
                    1 for g in recent_grades
                    if normalize_grade(g.get("newGrade")) in ["strong buy", "buy", "outperform",
                        "overweight", "accumulate"]
                    and normalize_grade(g.get("previousGrade")) not in ["strong buy", "buy", "outperform",
                            "overweight", "accumulate"]
                )
                recent_downgrades_t = sum(
                    1 for g in recent_grades
                    if normalize_grade(g.get("newGrade")) in ["sell", "underperform", "underweight",
                        "reduce", "strong sell"]
                    and normalize_grade(g.get("previousGrade")) not in ["sell", "underperform", "underweight",
                            "reduce", "strong sell"]
                )

                # Weighted score: recent = 2x, older = 1x
                weighted_upgrades_t = upgrades_t + recent_upgrades_t
                weighted_downgrades_t = downgrades_t + recent_downgrades_t

                # Torpedo: Downgrades erhöhen den Score
                if weighted_downgrades_t >= 4:
                    guidance_deceleration = 9.0
                elif weighted_downgrades_t >= 3 and weighted_upgrades_t == 0:
                    guidance_deceleration = 8.0
                elif weighted_downgrades_t > weighted_upgrades_t:
                    guidance_deceleration = 7.0
                elif weighted_upgrades_t > weighted_downgrades_t:
                    guidance_deceleration = 2.0
                elif weighted_upgrades_t >= 3:
                    guidance_deceleration = 1.0
                else:
                    guidance_deceleration = 5.0
    except Exception:
        guidance_deceleration = 5.0

    # leadership_instability: Management-Unruhe
    # news_processor.py erkennt bereits CEO/CFO-Keywords
    # und setzt shift_type = "management".
    # Diese Einträge liegen in news_memory.
    # Einer der stärksten Torpedo-Signale überhaupt —
    # CEO-Wechsel vor Earnings = massives Risiko.
    leadership_instability = 0.0
    try:
        news_memory = data.get("news_memory", [])
        management_events = []

        # Freshness-Check: nur Events der letzten 30 Tage
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=30)
        
        for nm in news_memory:
            st = nm.get("shift_type", "")
            is_shift = nm.get("is_narrative_shift", False)
            
            # Freshness-Filter
            event_date_str = nm.get("date", "")
            try:
                if event_date_str:
                    event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
                    if event_date < cutoff_date:
                        continue  # Event zu alt
            except Exception:
                pass  # Wenn Datum nicht parsebar, behalten wir es

            # Direkter Management-Shift aus news_processor
            if st == "management" and is_shift:
                management_events.append(nm)
                continue

            # Zusätzlicher Text-Scan der Bullet Points
            # falls shift_type nicht gesetzt
            bullets = nm.get("bullet_points", [])
            if isinstance(bullets, list):
                text = " ".join(bullets).lower()
            elif isinstance(bullets, str):
                text = bullets.lower()
            else:
                text = ""

            MGMT_KW = [
                "ceo", "cfo", "chief executive",
                "chief financial", "resigned", "resign",
                "appointed", "departure", "steps down",
                "terminated", "fired", "ousted",
                "management change", "executive change",
            ]
            if any(kw in text for kw in MGMT_KW):
                management_events.append(nm)

        # Unknown-State: keine News in den letzten 30 Tagen
        if not news_memory:
            leadership_instability = 0.0  # explizit "keine Daten"
        elif not management_events and len(news_memory) > 0:
            # News vorhanden, aber keine Management-Events
            leadership_instability = 0.0  # sauber
        else:
            # Schweregrad anhand Anzahl und Sentiment
            if len(management_events) >= 3:
                leadership_instability = 9.0
            elif len(management_events) == 2:
                leadership_instability = 7.0
            elif len(management_events) == 1:
                # Sentiment des Events: negativ = schwerer
                ev = management_events[0]
                sent = ev.get("sentiment_score", 0.0)
                if isinstance(sent, str):
                    try: sent = float(sent)
                    except: sent = 0.0
                if sent < -0.4:
                    leadership_instability = 8.0
                elif sent < -0.1:
                    leadership_instability = 6.0
                else:
                    leadership_instability = 4.0  # neutral
            else:
                leadership_instability = 0.0
    except Exception:
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
    mh = 5.0  # Neutral-Default wenn keine Macro-Daten
    macro = data.get("macro")
    vix = getattr(macro, "vix", None) if not isinstance(macro, dict) else macro.get("vix") if macro else None

    if vix is not None:
        if vix >= 35:  mh = 10.0
        elif vix > 25: mh = 8.0
        elif vix > 20: mh = 6.0
        elif vix > 15: mh = 4.0
        else:          mh = 1.0   # VIX < 15 = ruhiger Markt = niedriges Headwind

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

    logger.debug(
        f"[{ticker}] Torp-Score {total_score:.2f} | "
        f"guidance_dec={guidance_deceleration:.1f} "
        f"leadership={leadership_instability:.1f} "
        f"vd={vd:.1f} tech={technical_downtrend:.1f}"
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

async def get_recommendation(
    opportunity: OpportunityScore, 
    torpedo: TorpedoScore,
    macro_regime: str | None = None,   # NEU: "Risk Off" | "Risk On" | "Neutral"
    vix: float | None = None,          # NEU: aktueller VIX-Wert
) -> AuditRecommendation:
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

    # ── Makro-Regime-Gate ─────────────────────────────────────────
    # Bei Risk-Off-Regime werden bullische Empfehlungen degradiert.
    # Begründung: Selbst starke Einzeltitel fallen im Marktcrash.
    # VIX > 25: erhöhte Vorsicht. "Risk Off" (VIX > 30): Schutz aktiv.
    #
    # Shorts bleiben — in Risk-Off ist Short-Bias oft richtig.
    # Nur Long-Empfehlungen werden gebremst.
    macro_warning = None

    is_risk_off = (
        (macro_regime is not None and macro_regime.lower() in ("risk off", "risk_off"))
        or (vix is not None and vix > 30)
    )
    is_elevated_vix = vix is not None and 25 < vix <= 30

    if is_risk_off and rec in ("strong_buy", "buy_hedge"):
        rec = "watch"
        rec_label = "Beobachten"
        macro_warning = (
            f"⚠️ Makro-Regime-Gate aktiv: Risk Off"
            + (f" (VIX {vix:.0f})" if vix else "")
            + f" — Long-Empfehlung auf WATCH degradiert. "
            f"Original-Score: Opp {opp:.1f}/Torp {torp:.1f}."
        )
        reason = macro_warning

    elif is_elevated_vix and rec == "strong_buy":
        rec = "buy_hedge"
        rec_label = "Buy mit Absicherung"
        macro_warning = (
            f"⚠️ Erhöhte Volatilität (VIX {vix:.0f}) — "
            f"STRONG BUY zu 'Buy mit Absicherung' herabgestuft."
        )
        reason = f"{reason} {macro_warning}"
    # ── Ende Makro-Regime-Gate ───────────────────────────────────
        
    return AuditRecommendation(
        ticker=opportunity.ticker,
        opportunity_score=opportunity,
        torpedo_score=torpedo,
        recommendation=rec,
        recommendation_label=rec_label,
        reasoning=reason,
        macro_warning=macro_warning,   # NEU — None wenn kein Gate aktiv
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
    beta = beta if beta is not None else 1.0
    
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
