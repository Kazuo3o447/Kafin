import os
from datetime import datetime
from backend.app.logger import get_logger
from backend.app.data.finnhub import get_company_news, get_short_interest, get_insider_transactions, get_economic_calendar
from backend.app.data.fmp import (
    get_company_profile,
    get_analyst_estimates,
    get_earnings_history,
    get_key_metrics,
    get_sector_pe,
)
from backend.app.data.fred import get_macro_snapshot
from backend.app.data.yfinance_data import get_technical_setup, get_fundamentals_yf
from backend.app.analysis.scoring import calculate_opportunity_score, calculate_torpedo_score, get_recommendation
from backend.app.analysis.deepseek import call_deepseek
from backend.app.memory.long_term import get_all_insights_for_report

logger = get_logger(__name__)


def _fmt(value, date, unit="", fallback="Nicht verfügbar"):
    """Formatiert einen FRED-Wert für den Prompt. Verhindert dass 'None' an die KI geht."""
    if value is None:
        return fallback
    result = f"{value}{unit}"
    if date:
        result += f" (Stand: {date})"
    return result

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
AUDIT_PROMPT_PATH = os.path.join(ROOT_DIR, "prompts", "audit_report.md")
MACRO_PROMPT_PATH = os.path.join(ROOT_DIR, "prompts", "macro_header.md")

def _read_prompt(path: str) -> tuple[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    parts = content.split("SYSTEM:")
    if len(parts) < 2: return "", content
    
    subparts = parts[1].split("USER_TEMPLATE:")
    system_prompt = subparts[0].strip()
    user_prompt = subparts[1].strip() if len(subparts) > 1 else ""
    return system_prompt, user_prompt

async def generate_macro_header() -> str:
    """
    Generiert den wöchentlichen Makro-Lagebericht basierend auf aktuellen FRED-Daten,
    dem Wirtschaftskalender und dem DeepSeek-Modell.
    """
    logger.info("Generating Macro Header")
    macro = await get_macro_snapshot()
    
    from backend.app.data.yfinance_data import get_market_context
    market_ctx = await get_market_context()
    
    # Wirtschaftskalender: Nächste 7 Tage (Earnings)
    from backend.app.data.finnhub import get_earnings_calendar
    from datetime import timedelta
    
    now = datetime.now()
    next_week = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")

    try:
        calendar = await get_earnings_calendar(today, next_week)
        # Filtere auf bekannte/große Unternehmen (Market Cap > 50 Mrd oder Watchlist)
        from backend.app.memory.watchlist import get_watchlist
        wl = await get_watchlist()
        wl_tickers = {item["ticker"] for item in wl}

        upcoming_str = ""
        shown = 0
        for event in calendar:
            if shown >= 5:
                break
            ticker = getattr(event, "ticker", getattr(event, "symbol", ""))
            if ticker in wl_tickers:
                date = getattr(event, "report_date", getattr(event, "date", ""))
                upcoming_str += f"- {ticker}: Earnings am {date}\n"
                shown += 1

        if not upcoming_str:
            upcoming_str = "Keine Watchlist-Earnings in der kommenden Woche."
    except Exception as e:
        logger.error(f"Fehler beim Laden der Earnings-Kalender-Vorschau: {e}")
        upcoming_str = "Earnings-Kalender konnte nicht geladen werden."
        
    # GENERAL_MACRO Stichpunkte
    from backend.app.memory.short_term import get_bullet_points
    macro_bullets_raw = await get_bullet_points("GENERAL_MACRO")
    macro_bullets_str = "\n".join([
        " | ".join(b["bullet_points"]) if isinstance(b.get("bullet_points"), list) else str(b.get("bullet_points", ""))
        for b in macro_bullets_raw[:10]
    ])
    if not macro_bullets_str:
        macro_bullets_str = "Keine Makro-Stichpunkte verfügbar."
    
    sys_prompt, user_tmpl = _read_prompt(MACRO_PROMPT_PATH)
    
    # Replace placeholders
    user_prompt = user_tmpl \
        .replace("{{fed_rate}}", _fmt(macro.fed_rate, macro.fed_rate_date, "%")) \
        .replace("{{vix}}", _fmt(macro.vix, macro.vix_date)) \
        .replace("{{credit_spread}}", _fmt(macro.credit_spread_bps, macro.credit_spread_date, " Bp")) \
        .replace("{{yield_spread}}", _fmt(macro.yield_curve_10y_2y, macro.yield_curve_date)) \
        .replace("{{dxy}}", _fmt(macro.dxy, macro.dxy_date)) \
        .replace("{{sp500_perf}}", str(market_ctx.get('sp500_perf', 0.0))) \
        .replace("{{ndx_perf}}", str(market_ctx.get('ndx_perf', 0.0))) \
        .replace("{{gold_perf}}", str(market_ctx.get('gold_perf', 0.0))) \
        .replace("{{upcoming_events}}", upcoming_str) \
        .replace("{{macro_bullets}}", macro_bullets_str)

    if "{{" in user_prompt:
        unreplaced = [p for p in user_prompt.split("{{") if "}}" in p]
        logger.warning(f"Unreplaced Platzhalter im Makro-Prompt: {[p.split('}}')[0] for p in unreplaced]}")

    logger.debug(f"Makro-Prompt an DeepSeek:\n{user_prompt[:500]}...")

    result = await call_deepseek(sys_prompt, user_prompt)
    return result

async def generate_audit_report(ticker: str) -> str:
    """
    Generiert einen detaillierten, unternehmensspezifischen Audit-Report,
    indem Daten aus Finnhub, FMP, YFinance und eigenen Scores aggregiert und 
    via DeepSeek im Fließtext formuliert werden.
    """
    logger.info(f"Generating Audit Report for {ticker}")
    
    profile = await get_company_profile(ticker)
    if not profile:
        logger.warning(f"Ticker-Validierung fehlgeschlagen für {ticker}.")
        return f"Fehler: Ticker '{ticker}' ist ungültig (kein Profil gefunden)."

    # Daten laden — jeder Call einzeln abgesichert
    estimates = None
    try:
        estimates = await get_analyst_estimates(ticker)
    except Exception as e:
        logger.warning(f"Analyst estimates für {ticker}: {e}")

    history = None
    try:
        history = await get_earnings_history(ticker)
    except Exception as e:
        logger.warning(f"Earnings history für {ticker}: {e}")

    metrics = None
    try:
        metrics = await get_key_metrics(ticker)
    except Exception as e:
        logger.warning(f"Key metrics für {ticker}: {e}")

    # yfinance Fallback für fehlende Fundamentaldaten
    yf_fundamentals = None
    if not metrics or not getattr(metrics, "pe_ratio", None):
        try:
            from backend.app.data.yfinance_data import get_fundamentals_yf
            yf_fundamentals = await get_fundamentals_yf(ticker)
            if yf_fundamentals:
                logger.info(
                    f"yfinance Fallback für {ticker}: P/E={yf_fundamentals.get('pe_ratio')}, MCap={yf_fundamentals.get('market_cap')}"
                )
        except Exception as e:
            logger.debug(f"yfinance Fallback für {ticker} fehlgeschlagen: {e}")

    short_interest = None
    try:
        short_interest = await get_short_interest(ticker)
    except Exception as e:
        logger.warning(f"Short interest für {ticker}: {e}")

    # Fallback auf yfinance wenn Finnhub short-interest fehlschlägt (403 Premium)
    if short_interest is None:
        from backend.app.data.yfinance_data import get_short_interest_yf
        from schemas.sentiment import ShortInterestData
        try:
            yf_si = await get_short_interest_yf(ticker)
        except Exception as e:
            logger.warning(f"Short interest yfinance Fallback für {ticker}: {e}")
            yf_si = None
        if yf_si:
            short_interest = ShortInterestData(
                ticker=ticker,
                short_interest=yf_si.get("shares_short", 0),
                short_interest_percent=yf_si.get("short_interest_percent", 0),
                days_to_cover=yf_si.get("short_ratio", 0),
                trend="stable",
                squeeze_risk="medium" if yf_si.get("short_interest_percent", 0) > 15 else "low"
            )
        else:
            short_interest = ShortInterestData(ticker=ticker, short_interest=0, days_to_cover=0, trend="stable", squeeze_risk="low")

    insiders = None
    try:
        insiders = await get_insider_transactions(ticker)
    except Exception as e:
        logger.warning(f"Insider transactions für {ticker}: {e}")

    technicals = None
    try:
        technicals = await get_technical_setup(ticker)
    except Exception as e:
        logger.warning(f"Technicals für {ticker}: {e}")

    options = None
    try:
        from backend.app.data.yfinance_data import get_options_metrics
        options = await get_options_metrics(ticker)
    except Exception as e:
        logger.warning(f"Options für {ticker}: {e}")

    social = None
    try:
        from backend.app.data.finnhub import get_social_sentiment
        social = await get_social_sentiment(ticker)
    except Exception as e:
        logger.warning(f"Social sentiment für {ticker}: {e}")
    
    now = datetime.now()
    month_ago = now.replace(day=max(1, now.day - 30)) if now.day > 1 else now # rough 30 days
    
    # 1.5 Try getting news from memory first, else fallback to Finnhub
    from backend.app.memory.short_term import get_bullet_points
    news_memory = await get_bullet_points(ticker)
    
    news_list = None
    if not news_memory:
        news_list = await get_company_news(ticker, month_ago.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))
    
    macro = await get_macro_snapshot()
    
    # Assemble data context for scoring
    valuation_ctx = {}
    if metrics:
        valuation_ctx = metrics.dict()
    elif profile:
        valuation_ctx = profile.dict()
    elif yf_fundamentals:
        valuation_ctx = {
            "ticker": ticker,
            "pe_ratio": yf_fundamentals.get("pe_ratio"),
            "ps_ratio": yf_fundamentals.get("ps_ratio"),
            "market_cap": yf_fundamentals.get("market_cap"),
            "sector": yf_fundamentals.get("sector"),
        }

    data_ctx = {
        "earnings_history": history.dict() if history else {},
        "valuation": valuation_ctx,
        "short_interest": short_interest.dict() if short_interest else {},
        "insider_activity": insiders.dict() if insiders else {},
        "macro": macro.dict() if macro else {},
        "technicals": technicals.dict() if technicals else {},
        "news_memory": news_memory if news_memory else [],
        "options": options.dict() if options else {},
        "social": social.dict() if social else {}
    }
    
    # 2. Scores
    opp_score = await calculate_opportunity_score(ticker, data_ctx)
    torp_score = await calculate_torpedo_score(ticker, data_ctx)
    rec = await get_recommendation(opp_score, torp_score)
    
    # 3. Prompt replacement
    sys_prompt, user_tmpl = _read_prompt(AUDIT_PROMPT_PATH)
    
    # Format news
    if news_memory:
        import json
        bullets = []
        for nm in news_memory[:5]:
            try:
                # bp kann String oder JSON-String Liste sein
                bp_data = nm.get("bullet_points")
                if isinstance(bp_data, str):
                    try: 
                        parsed = json.loads(bp_data)
                        if isinstance(parsed, list): bullets.extend(parsed)
                        else: bullets.append(str(parsed))
                    except:
                        bullets.append(bp_data)
                elif isinstance(bp_data, list):
                    bullets.extend(bp_data)
            except Exception as e:
                logger.error(f"Fehler beim Parsen der Memory-Stichpunkte: {e}")
                
        if bullets:
            news_str = "\n".join([f"- {b}" for b in bullets[:7]]) # max 7 Stichpunkte
        else:
             news_str = "Keine relevanten Nachrichten in den letzten 30 Tagen."
    else:
        news_str = "\n".join([f"- {n.headline}: {n.summary[:100]}..." for n in news_list[:5]]) if news_list else "Keine relevanten Nachrichten in den letzten 30 Tagen."
    
    # Letzte Earnings aus History extrahieren
    last_actual = "N/A"
    last_consensus = "N/A"
    last_surprise = "N/A"
    last_reaction = "N/A"
    if history and history.last_quarter:
        lq = history.last_quarter
        last_actual = str(getattr(lq, "eps_actual", "N/A"))
        last_consensus = str(getattr(lq, "eps_consensus", "N/A"))
        last_surprise = f"{getattr(lq, 'eps_surprise_percent', 0.0):.1f}"
        last_reaction = str(getattr(lq, "stock_reaction_1d", "N/A"))

    # SMA-Distances berechnen
    sma50_dist = "N/A"
    sma200_dist = "N/A"
    if technicals:
        cp = getattr(technicals, "current_price", None)
        s50 = getattr(technicals, "sma_50", None)
        s200 = getattr(technicals, "sma_200", None)
        if cp and cp > 0 and s50:
            sma50_dist = f"{((cp - s50) / s50 * 100):.1f}"
        if cp and cp > 0 and s200:
            sma200_dist = f"{((cp - s200) / s200 * 100):.1f}"

    # Sektor-P/E ermitteln
    sector_pe_str = "N/A"
    if profile and profile.sector:
        try:
            sector_pe_val = await get_sector_pe(profile.sector)
            sector_pe_str = f"{sector_pe_val:.1f}" if sector_pe_val else "N/A"
        except Exception:
            pass

    # 3-Jahres Median P/E Fallback
    pe_own_median_str = str(round(getattr(metrics, "pe_ratio", 18.0), 1)) if metrics and getattr(metrics, "pe_ratio", None) else "N/A"

    # Bewertungs-Fallbacks für Prompt
    pe_val = None
    if metrics and getattr(metrics, "pe_ratio", None):
        pe_val = metrics.pe_ratio
    elif yf_fundamentals and yf_fundamentals.get("pe_ratio"):
        pe_val = yf_fundamentals["pe_ratio"]
    pe_str = f"{pe_val:.1f}" if pe_val else "N/A"

    ps_val = None
    if metrics and getattr(metrics, "ps_ratio", None):
        ps_val = metrics.ps_ratio
    elif yf_fundamentals and yf_fundamentals.get("ps_ratio"):
        ps_val = yf_fundamentals["ps_ratio"]
    ps_str = f"{ps_val:.1f}" if ps_val else "N/A"

    mcap_val = None
    if metrics and getattr(metrics, "market_cap", None):
        mcap_val = metrics.market_cap
    elif yf_fundamentals and yf_fundamentals.get("market_cap"):
        mcap_val = yf_fundamentals["market_cap"]
    mcap_str = f"{mcap_val / 1e9:.1f}" if mcap_val and mcap_val > 0 else "N/A"

    eps_consensus_val = getattr(estimates, "eps_consensus", None) if estimates else None
    if not eps_consensus_val and yf_fundamentals:
        eps_consensus_val = yf_fundamentals.get("eps_ttm")
    eps_consensus_str = f"{eps_consensus_val:.2f}" if eps_consensus_val else "N/A"

    rev_consensus_val = getattr(estimates, "revenue_consensus", None) if estimates else None
    if not rev_consensus_val and yf_fundamentals:
        rev_consensus_val = yf_fundamentals.get("revenue_ttm")
    rev_consensus_str = (
        f"{rev_consensus_val / 1e9:.1f}B" if rev_consensus_val and rev_consensus_val > 1e6 else "N/A"
    )

    user_prompt = user_tmpl \
        .replace("{{ticker}}", ticker) \
        .replace("{{company_name}}", getattr(estimates, "company_name", ticker) if estimates else ticker) \
        .replace("{{report_date}}", str(getattr(estimates, "report_date", "Unknown")) if estimates else "Unknown") \
        .replace("{{report_timing}}", "Unknown") \
        .replace("{{eps_consensus}}", eps_consensus_str) \
        .replace("{{revenue_consensus}}", rev_consensus_str) \
        .replace("{{quarters_beat}}", str(getattr(history, "quarters_beat", "0")) if history else "0") \
        .replace("{{total_quarters}}", str((getattr(history, "quarters_beat", 0) + getattr(history, "quarters_missed", 0))) if history else "0") \
        .replace("{{avg_surprise}}", str(getattr(history, "avg_surprise_percent", "0.0")) if history else "0.0") \
        .replace("{{last_eps_actual}}", last_actual) \
        .replace("{{last_eps_consensus}}", last_consensus) \
        .replace("{{last_surprise}}", last_surprise) \
        .replace("{{last_reaction}}", last_reaction) \
        .replace("{{pe_ratio}}", pe_str) \
        .replace("{{pe_sector_median}}", sector_pe_str) \
        .replace("{{pe_own_3y_median}}", pe_own_median_str) \
        .replace("{{ps_ratio}}", ps_str) \
        .replace("{{market_cap}}", mcap_str) \
        .replace("{{current_price}}", str(getattr(technicals, "current_price", "N/A")) if technicals else "N/A") \
        .replace("{{trend}}", str(getattr(technicals, "trend", "N/A")) if technicals else "N/A") \
        .replace("{{sma50_status}}", "Über" if technicals and technicals.above_sma50 else "Unter") \
        .replace("{{sma50_distance}}", sma50_dist) \
        .replace("{{sma200_status}}", "Über" if technicals and technicals.above_sma200 else "Unter") \
        .replace("{{sma200_distance}}", sma200_dist) \
        .replace("{{rsi}}", str(getattr(technicals, "rsi_14", "N/A")) if technicals else "N/A") \
        .replace("{{support}}", str(getattr(technicals, "support_level", "N/A")) if technicals else "N/A") \
        .replace("{{resistance}}", str(getattr(technicals, "resistance_level", "N/A")) if technicals else "N/A") \
        .replace("{{distance_52w_high}}", str(getattr(technicals, "distance_to_52w_high_percent", "0.0")) if technicals else "0.0") \
        .replace("{{short_interest}}", str(getattr(short_interest, "short_interest_percent", "0.0")) if short_interest else "0.0") \
        .replace("{{days_to_cover}}", str(getattr(short_interest, "days_to_cover", "0.0")) if short_interest else "0.0") \
        .replace("{{si_trend}}", str(getattr(short_interest, "short_interest_trend", "stable")) if short_interest else "stable") \
        .replace("{{squeeze_risk}}", str(getattr(short_interest, "squeeze_risk", "low")) if short_interest else "low") \
        .replace("{{insider_buys}}", str(getattr(insiders, "total_buys", "0")) if insiders else "0") \
        .replace("{{insider_buy_value}}", str(getattr(insiders, "total_buy_value", "0.0")) if insiders else "0.0") \
        .replace("{{insider_sells}}", str(getattr(insiders, "total_sells", "0")) if insiders else "0") \
        .replace("{{insider_sell_value}}", str(getattr(insiders, "total_sell_value", "0.0")) if insiders else "0.0") \
        .replace("{{insider_assessment}}", str(getattr(insiders, "assessment", "normal")) if insiders else "normal") \
        .replace("{{options_metrics}}", f"PCR: {getattr(options, 'put_call_ratio_oi', 'N/A')} | IV ATM: {getattr(options, 'implied_volatility_atm', 0) * 100:.1f}%" if options else "N/A") \
        .replace("{{social_sentiment}}", f"Score: {getattr(social, 'social_score', 'N/A')} (Reddit: {getattr(social, 'reddit_mentions', 'N/A')}, Twitter: {getattr(social, 'twitter_mentions', 'N/A')})" if social else "N/A") \
        .replace("{{news_bullet_points}}", news_str) \
        .replace("{{long_term_memory}}", lt_memory) \
        .replace("{{opportunity_score}}", str(opp_score.total_score if opp_score else 0.0)) \
        .replace("{{torpedo_score}}", str(torp_score.total_score if torp_score else 0.0))
        
    result = await call_deepseek(sys_prompt, user_prompt)
    if "MOCK_REPORT:" in result:
        # Erweitere den Mock-Bericht um unsere Daten zur Validierung
        mock_response = f"{result}\n\n[MOCK DATA CHECK]\nTicker: {ticker}\nEmpfehlung: {rec.recommendation if rec else 'N/A'} ({rec.reasoning if rec else 'N/A'})\nOS: {opp_score.total_score if opp_score else 0.0} | TS: {torp_score.total_score if torp_score else 0.0}"
    else:
        mock_response = result

    # Report in Supabase speichern
    try:
        from backend.app.db import get_supabase_client

        db = get_supabase_client()
        if db:
            db.table("audit_reports").insert({
                "ticker": ticker,
                "report_type": "audit",
                "recommendation": rec.recommendation if rec else "unknown",
                "opportunity_score": opp_score.total_score if opp_score else 0,
                "torpedo_score": torp_score.total_score if torp_score else 0,
                "report_text": mock_response[:2000],
                "created_at": datetime.now().isoformat()
            }).execute()
            logger.info(f"Audit-Report für {ticker} in Supabase gespeichert")
    except Exception as e:
        logger.debug(f"Audit-Report DB-Speicher: {e}")

    # Score-History speichern für Delta-Tracking
    try:
        from datetime import date as date_type
        from backend.app.db import get_supabase_client

        db = get_supabase_client()
        if db:
            db.table("score_history").upsert({
                "ticker": ticker,
                "date": date_type.today().isoformat(),
                "opportunity_score": opp_score.total_score if opp_score else None,
                "torpedo_score": torp_score.total_score if torp_score else None,
                "price": getattr(technicals, "current_price", None) if technicals else None,
                "rsi": getattr(technicals, "rsi_14", None) if technicals else None,
                "trend": getattr(technicals, "trend", None) if technicals else None,
            }, on_conflict="ticker,date").execute()
    except Exception as e:
        logger.debug(f"Score-History Speicher-Fehler: {e}")

    return mock_response

async def generate_weekly_summary() -> str:
    """
    Generiert eine Zusammenfassung der wichtigsten Events der Woche.
    Basiert auf allen News-Stichpunkten im Kurzzeit-Gedächtnis der letzten 7 Tage.
    """
    from backend.app.memory.short_term import get_bullet_points
    from backend.app.memory.watchlist import get_watchlist
    from datetime import timedelta
    from dateutil.parser import parse as parse_date

    cutoff_dt = datetime.now() - timedelta(days=7)

    # 1. GENERAL_MACRO: Globale Wirtschaftsevents ganz oben (als Kontext priorisiert)
    macro_bullets = await get_bullet_points("GENERAL_MACRO")
    macro_recent = []
    for b in macro_bullets:
        try:
            bullet_date = parse_date(str(b.get("date", "2000-01-01")))
            if bullet_date.tzinfo:
                bullet_date = bullet_date.replace(tzinfo=None)
            if bullet_date >= cutoff_dt:
                macro_recent.append(b)
        except Exception:
            pass

    # 2. Watchlist Ticker
    wl = await get_watchlist()
    tickers = [item["ticker"] for item in wl]

    ticker_bullets = []
    for ticker in tickers:
        bullets = await get_bullet_points(ticker)
        recent = []
        for b in bullets:
            try:
                bullet_date = parse_date(str(b.get("date", "2000-01-01")))
                if bullet_date.tzinfo:
                    bullet_date = bullet_date.replace(tzinfo=None)
                if bullet_date >= cutoff_dt:
                    recent.append(b)
            except Exception:
                pass
        ticker_bullets.extend(recent)

    # Sortiere NUR die Ticker-Events nach Material/Sentiment
    ticker_bullets.sort(key=lambda x: (
        -int(x.get("is_material", False)),
        -abs(float(x.get("sentiment_score", 0)))
    ))

    # Füge zusammen: Macro immer zuerst, dann die sortierten Ticker-News
    all_bullets = macro_recent + ticker_bullets

    if not all_bullets:
        logger.info("Kurzzeit-Gedächtnis leer. Versuche Finnhub-News direkt als Fallback.")
        from backend.app.data.finnhub import get_company_news

        fallback_news = []
        cutoff_str = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        today_str = datetime.now().strftime("%Y-%m-%d")

        for ticker in tickers[:10]:
            try:
                news = await get_company_news(ticker, cutoff_str, today_str)
                if news:
                    for n in news[:3]:
                        headline = getattr(n, "headline", str(n)) if not isinstance(n, dict) else n.get("headline", str(n))
                        fallback_news.append(f"- [{ticker}] {headline}")
                        logger.debug(f"Fallback-News für {ticker}: {headline[:60]}")
            except Exception as e:
                logger.warning(f"Finnhub-News Fallback für {ticker} fehlgeschlagen: {e}")

        if not fallback_news:
            logger.warning("Auch Finnhub-Fallback hat keine News geliefert.")
            return "News-Pipeline noch nicht aktiv und Finnhub-Fallback hat keine Daten geliefert. Bitte News-Scan manuell über das Admin-Panel starten."

        events_text = "\n".join(fallback_news[:20])
        logger.info(f"Fallback: {len(fallback_news)} News-Headlines aus Finnhub geholt.")
    else:
        events_text = "\n".join([
            f"- [{b.get('ticker', '?')}] ({b.get('category', 'general')}) Sentiment {float(b.get('sentiment_score', 0)):.2f}: " +
            (" | ".join(b["bullet_points"]) if isinstance(b.get("bullet_points"), list) else str(b.get("bullet_points", "")))
            for b in all_bullets[:30]
        ])

    system_prompt = (
        "Du bist ein Finanzanalyst und erstellst eine Wochenzusammenfassung auf Deutsch. "
        "Fasse die wichtigsten Events der Woche zusammen. Priorisiere nach Marktrelevanz. "
        "Gruppiere nach Themen (z.B. Earnings, Regulatorisches, Makro). "
        "Maximal 10-15 Sätze. Sei direkt und konkret."
    )

    user_prompt = f"Hier sind die wichtigsten Nachrichten-Stichpunkte der letzten 7 Tage:\n\n{events_text}\n\nErstelle eine kompakte Wochenzusammenfassung auf Deutsch."

    result = await call_deepseek(system_prompt, user_prompt)
    return result

async def generate_sunday_report(tickers: list[str]) -> str:
    """
    Erstellt den wöchentlichen kompletten Sunday-Report, der den 
    Makro-Header sowie die Audit-Reports der abgefragten Ticker aggregiert.
    """
    logger.info(f"Sunday Report: {len(tickers)} Ticker erhalten: {tickers}")
    
    # Pre-Flight Check: Makro-Events für die nächste Woche holen und ins Gedächtnis schreiben
    try:
        from backend.app.data.macro_processor import fetch_global_macro_events
        await fetch_global_macro_events()
        logger.info("Pre-Flight Check: fetch_global_macro_events abgeschlossen.")
    except Exception as e:
        logger.error(f"Fehler beim Pre-Flight Check (Wirtschaftskalender): {e}")

    if not tickers:
        logger.warning("Keine Ticker für Audit-Reports. Prüfe Watchlist.")
    
    # 1. Makro-Header
    header = await generate_macro_header()
    
    # 2. Wochenzusammenfassung (NEU)
    weekly = await generate_weekly_summary()
    
    # 3. Audit-Reports
    reports = []
    for t in tickers:
        try:
            r = await generate_audit_report(t)
            reports.append(r)
        except Exception as e:
            logger.error(f"Audit-Report für {t} fehlgeschlagen: {e}")
            reports.append(f"## {t}\n\nReport-Generierung fehlgeschlagen: {str(e)}")
        
    full_report = f"# KAFIN SONNTAGS-REPORT\n\n"
    full_report += f"## MAKRO-REGIME\n\n{header}\n\n---\n\n"
    full_report += f"## WOCHENZUSAMMENFASSUNG\n\n{weekly}\n\n---\n\n"
    full_report += f"## AUDIT-REPORTS\n\n"
    full_report += "\n\n---\n\n".join(reports)
    
    return full_report


async def generate_morning_briefing() -> str:
    """
    Generiert das tägliche Morning Briefing.
    Aggregiert: Index-Technicals, Sektorrotation, Makro-Daten, allgemeine News,
    Watchlist-News aus dem Gedächtnis, Wirtschaftskalender.
    """
    from backend.app.data.market_overview import get_market_overview, get_general_market_news, save_daily_snapshot, get_yesterday_snapshot
    from backend.app.data.fred import get_macro_snapshot
    from backend.app.data.finnhub import get_earnings_calendar, get_economic_calendar
    from backend.app.memory.short_term import get_bullet_points
    from backend.app.memory.watchlist import get_watchlist
    from datetime import timedelta

    logger.info("Generiere Morning Briefing...")

    # 1. Marktübersicht (Indizes + Sektoren + Makro-Proxys)
    market = await get_market_overview()

    # 2. FRED Makro-Daten
    macro = await get_macro_snapshot()

    # 2b. Gestriger Snapshot für Vergleich
    yesterday = await get_yesterday_snapshot()
    if yesterday:
        yesterday_str = (
            f"Datum: {yesterday.get('date', 'N/A')}\n"
            f"SPY: ${yesterday.get('spy_price', 'N/A')} ({yesterday.get('spy_change_pct', 0):+.1f}%)\n"
            f"QQQ: ${yesterday.get('qqq_price', 'N/A')} ({yesterday.get('qqq_change_pct', 0):+.1f}%)\n"
            f"VIX: {yesterday.get('vix', 'N/A')}\n"
            f"Credit Spread: {yesterday.get('credit_spread', 'N/A')}\n"
            f"Yield Spread: {yesterday.get('yield_spread', 'N/A')}\n"
            f"DXY: {yesterday.get('dxy', 'N/A')}\n"
            f"Stärkster Sektor: {yesterday.get('top_sector', 'N/A')}\n"
            f"Schwächster Sektor: {yesterday.get('bottom_sector', 'N/A')}\n"
            f"Regime: {yesterday.get('regime', 'N/A')}"
        )
    else:
        yesterday_str = "Kein Vergleichs-Snapshot verfügbar (erster Tag oder Datenbankfehler)."

    # 3. Allgemeine Nachrichten (Geopolitik, Politik)
    general_news = await get_general_market_news()

    # 4. Watchlist-News aus dem Gedächtnis (letzte 24h)
    wl = await get_watchlist()
    wl_tickers = [item["ticker"] for item in wl]
    watchlist_news = []
    for ticker in wl_tickers:
        bullets = await get_bullet_points(ticker)
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        recent = [b for b in bullets if b.get("date", "") >= cutoff]
        for b in recent:
            bp_text = " | ".join(b["bullet_points"]) if isinstance(b.get("bullet_points"), list) else str(b.get("bullet_points", ""))
            watchlist_news.append(f"[{ticker}] ({b.get('category', 'general')}) {bp_text}")

    # 5. GENERAL_MACRO Events (letzte 48h)
    macro_events_raw = await get_bullet_points("GENERAL_MACRO")
    cutoff_48h = (datetime.now() - timedelta(hours=48)).isoformat()
    macro_events = []
    for b in macro_events_raw:
        if b.get("date", "") >= cutoff_48h:
            bp_text = " | ".join(b["bullet_points"]) if isinstance(b.get("bullet_points"), list) else str(b.get("bullet_points", ""))
            macro_events.append(bp_text)

    # 7. Analysten-Ratings für Watchlist-Ticker (letzte 7 Tage)
    from backend.app.data.fmp import get_analyst_grades, get_price_target_consensus

    analyst_lines = []
    cutoff_7d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    for ticker in wl_tickers[:10]:
        try:
            grades = await get_analyst_grades(ticker)
            pt = await get_price_target_consensus(ticker)

            # Nur Ratings der letzten 7 Tage
            recent_grades = [g for g in grades if g.get("date", "") >= cutoff_7d]
            for g in recent_grades:
                company = g.get("gradingCompany", "Unbekannt")
                prev = g.get("previousGrade", "?")
                new = g.get("newGrade", "?")
                action = g.get("action", "?")
                date = g.get("date", "?")
                analyst_lines.append(f"[{ticker}] {company}: {prev} → {new} ({action}) am {date}")

            # Price Target nur wenn vorhanden
            if pt and pt.get("targetConsensus"):
                consensus = pt["targetConsensus"]
                low = pt.get("targetLow", 0)
                high = pt.get("targetHigh", 0)
                analyst_lines.append(f"[{ticker}] PT-Konsens: ${consensus:.0f} (Range: ${low:.0f}-${high:.0f})")

        except Exception as e:
            logger.debug(f"Analysten-Daten für {ticker} nicht verfügbar: {e}")

    if analyst_lines:
        analyst_str = "\n".join(analyst_lines)
        logger.info(f"Analysten-Daten: {len(analyst_lines)} Einträge für Watchlist geladen")
    else:
        analyst_str = "Keine aktuellen Analysten-Änderungen für Watchlist-Ticker."
        logger.info("Keine Analysten-Daten verfügbar")

    # 6. Wirtschaftskalender heute
    today_str = datetime.now().strftime("%Y-%m-%d")
    todays_events_str = "Keine Termine heute."
    try:
        # Earnings heute
        earnings_today = await get_earnings_calendar(today_str, today_str)
        earnings_wl = [e for e in earnings_today if getattr(e, "ticker", getattr(e, "symbol", "")) in set(wl_tickers)]

        # Wirtschaftskalender
        econ_cal = []
        try:
            econ_cal = await get_economic_calendar(today_str, today_str)
        except Exception:
            pass

        parts = []
        if earnings_wl:
            parts.append("Earnings: " + ", ".join([getattr(e, "ticker", getattr(e, "symbol", "?")) for e in earnings_wl]))
        if econ_cal:
            for ev in econ_cal[:5]:
                parts.append(f"{ev.get('event', 'Event')}: {ev.get('estimate', 'N/A')} (vorher: {ev.get('prev', 'N/A')})")
        if parts:
            todays_events_str = "\n".join(parts)
    except Exception as e:
        logger.warning(f"Kalender-Fehler: {e}")

    # === Prompt zusammenbauen ===

    # Index-Daten formatieren
    index_lines = []
    for sym, data in market.get("indices", {}).items():
        if "error" not in data:
            index_lines.append(
                f"{data.get('name', sym)}: ${data['price']} ({data['change_1d_pct']:+.1f}% Tag, {data['change_5d_pct']:+.1f}% Woche) | "
                f"Trend: {data['trend']} | RSI: {data.get('rsi_14', 'N/A')} | "
                f"SMA50: {'darüber' if data.get('above_sma50') else 'darunter'} | "
                f"SMA200: {'darüber' if data.get('above_sma200') else 'darunter'} | "
                f"52W-Hoch: {data.get('dist_52w_high_pct', 'N/A')}%"
            )
    index_str = "\n".join(index_lines) if index_lines else "Index-Daten nicht verfügbar."

    # Sektor-Ranking formatieren
    sector_lines = []
    for item in market.get("sector_ranking_5d", []):
        sector_lines.append(f"{item['name']} ({item['symbol']}): {item['perf_5d']:+.1f}% (5T)")
    sector_str = "\n".join(sector_lines) if sector_lines else "Sektor-Daten nicht verfügbar."

    # Makro-Proxys formatieren
    macro_proxy_lines = []
    for sym, data in market.get("macro", {}).items():
        if "error" not in data:
            macro_proxy_lines.append(f"{data.get('name', sym)}: ${data['price']} ({data['change_1d_pct']:+.1f}% Tag)")
    macro_proxy_str = "\n".join(macro_proxy_lines) if macro_proxy_lines else "Makro-Proxy-Daten nicht verfügbar."

    # Nachrichten formatieren
    general_news_str = "\n".join([f"- [{n['source']}] {n['headline']}" for n in general_news[:10]]) if general_news else "Keine allgemeinen Nachrichten geladen."
    watchlist_news_str = "\n".join([f"- {n}" for n in watchlist_news[:10]]) if watchlist_news else "Keine Watchlist-News in den letzten 24h."
    macro_events_str = "\n".join([f"- {e}" for e in macro_events[:5]]) if macro_events else "Keine GENERAL_MACRO Events in den letzten 48h."

    # FRED-Daten formatieren (mit None-Schutz)
    fed_str = _fmt(macro.fed_rate, getattr(macro, "fed_rate_date", None), "%")
    vix_str = _fmt(macro.vix, getattr(macro, "vix_date", None))
    cs_str = _fmt(macro.credit_spread_bps, getattr(macro, "credit_spread_date", None), " Bp")
    ys_str = _fmt(macro.yield_curve_10y_2y, getattr(macro, "yield_curve_date", None))
    dxy_str = _fmt(macro.dxy, getattr(macro, "dxy_date", None))

    # Prompt laden und befüllen
    MORNING_PROMPT_PATH = os.path.join(ROOT_DIR, "prompts", "morning_briefing.md")
    sys_prompt, user_tmpl = _read_prompt(MORNING_PROMPT_PATH)

    # Sicherheitsnetz: Alle Template-Variablen müssen definiert sein
    if 'analyst_str' not in locals():
        analyst_str = "Analysten-Daten nicht verfügbar."
    if 'yesterday_str' not in locals():
        yesterday_str = "Kein Vergleichs-Snapshot verfügbar."
    if 'watchlist_news_str' not in locals():
        watchlist_news_str = "Keine Watchlist-News."
    if 'macro_events_str' not in locals():
        macro_events_str = "Keine Makro-Events."
    if 'general_news_str' not in locals():
        general_news_str = "Keine allgemeinen Nachrichten."
    if 'todays_events_str' not in locals():
        todays_events_str = "Keine Termine heute."

    user_prompt = user_tmpl \
        .replace("{{date}}", datetime.now().strftime("%d.%m.%Y")) \
        .replace("{{index_data}}", index_str) \
        .replace("{{sector_ranking}}", sector_str) \
        .replace("{{macro_data}}", macro_proxy_str) \
        .replace("{{fed_rate}}", fed_str) \
        .replace("{{vix}}", vix_str) \
        .replace("{{credit_spread}}", cs_str) \
        .replace("{{yield_spread}}", ys_str) \
        .replace("{{dxy}}", dxy_str) \
        .replace("{{analyst_ratings}}", analyst_str) \
        .replace("{{general_news}}", general_news_str) \
        .replace("{{watchlist_news}}", watchlist_news_str) \
        .replace("{{macro_events}}", macro_events_str) \
        .replace("{{todays_events}}", todays_events_str) \
        .replace("{{yesterday_snapshot}}", yesterday_str)

    # Platzhalter-Check
    if "{{" in user_prompt:
        unreplaced = [p.split("}}")[0] for p in user_prompt.split("{{")[1:]]
        logger.warning(f"Unreplaced Platzhalter im Morning-Prompt: {unreplaced}")

    logger.info(f"Morning Briefing Prompt: {len(user_prompt)} Zeichen an DeepSeek")
    result = await call_deepseek(sys_prompt, user_prompt)

    # Tages-Snapshot speichern für den Vergleich morgen
    try:
        # Regime aus dem Briefing extrahieren (grobe Heuristik)
        regime = "neutral"
        spy_data = market.get("indices", {}).get("SPY", {})
        vix_data = market.get("macro", {}).get("^VIX", {})
        vix_price = vix_data.get("price", 20) if isinstance(vix_data, dict) else 20
        if vix_price and vix_price > 25:
            regime = "risk-off"
        elif spy_data.get("change_1d_pct", 0) > 1.0 and vix_price < 18:
            regime = "risk-on"
        elif spy_data.get("change_1d_pct", 0) < -1.0:
            regime = "risk-off"
        else:
            regime = "range-bound"

        await save_daily_snapshot(market, macro, regime)
    except Exception as e:
        logger.warning(f"Snapshot-Speicherung fehlgeschlagen: {e}")

    return result
