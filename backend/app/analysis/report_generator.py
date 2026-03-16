import os
from datetime import datetime
from backend.app.logger import get_logger
from backend.app.data.finnhub import get_company_news, get_short_interest, get_insider_transactions, get_economic_calendar
from backend.app.data.fmp import get_company_profile, get_analyst_estimates, get_earnings_history, get_key_metrics
from backend.app.data.fred import get_macro_snapshot
from backend.app.data.yfinance_data import get_technical_setup
from backend.app.analysis.scoring import calculate_opportunity_score, calculate_torpedo_score, get_recommendation
from backend.app.analysis.deepseek import call_deepseek

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

    estimates = await get_analyst_estimates(ticker)
    history = await get_earnings_history(ticker)
    metrics = await get_key_metrics(ticker)
    short_interest = await get_short_interest(ticker)
    insiders = await get_insider_transactions(ticker)
    technicals = await get_technical_setup(ticker)
    
    from backend.app.data.yfinance_data import get_options_metrics
    options = await get_options_metrics(ticker)
    
    from backend.app.data.finnhub import get_social_sentiment
    social = await get_social_sentiment(ticker)
    
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
    data_ctx = {
        "earnings_history": history.dict() if history else {},
        "valuation": metrics.dict() if metrics else profile.dict() if profile else {},
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
    
    # KORREKTUR 5: Letztes Quartal aus Earnings-History extrahieren
    last_actual = "N/A"
    last_consensus = "N/A"
    last_surprise = "N/A"
    last_reaction = "N/A"

    if history:
        all_q = getattr(history, "all_quarters", [])
        if all_q and len(all_q) > 0:
            last_q = all_q[0]  # Neuestes Quartal
            last_actual = str(getattr(last_q, "eps_actual", "N/A"))
            last_consensus = str(getattr(last_q, "eps_consensus", "N/A"))
            last_surprise = str(getattr(last_q, "eps_surprise_percent", "N/A"))
            last_reaction = str(getattr(last_q, "stock_reaction_1d", "N/A"))
        elif hasattr(history, "last_quarter") and history.last_quarter:
            lq = history.last_quarter
            last_actual = str(getattr(lq, "eps_actual", "N/A"))
            last_consensus = str(getattr(lq, "eps_consensus", "N/A"))
            last_surprise = str(getattr(lq, "eps_surprise_percent", "N/A"))
            last_reaction = str(getattr(lq, "stock_reaction_1d", "N/A"))

    # KORREKTUR 4c: Sektor-Median P/E aus FMP holen
    sector_pe_str = "N/A"
    if profile and hasattr(profile, "sector"):
        try:
            from backend.app.data.fmp import get_sector_pe
            sector_pe = await get_sector_pe(profile.sector)
            sector_pe_str = str(round(sector_pe, 1)) if sector_pe else "N/A"
        except Exception:
            sector_pe_str = "N/A"

    # KORREKTUR 4d: 3-Jahres-Median P/E — Pragmatischer Fallback auf aktuelles P/E
    pe_own_median_str = str(round(getattr(metrics, "pe_ratio", 18.0), 1)) if metrics and getattr(metrics, "pe_ratio", None) else "N/A"

    # KORREKTUR 6: SMA-Distance berechnen statt hardcoded 0.0
    sma50_dist = "N/A"
    sma200_dist = "N/A"
    if technicals and technicals.current_price and technicals.current_price > 0:
        if technicals.sma_50:
            sma50_dist = f"{((technicals.current_price - technicals.sma_50) / technicals.sma_50 * 100):.1f}"
        if technicals.sma_200:
            sma200_dist = f"{((technicals.current_price - technicals.sma_200) / technicals.sma_200 * 100):.1f}"

    user_prompt = user_tmpl \
        .replace("{{ticker}}", ticker) \
        .replace("{{company_name}}", getattr(estimates, "company_name", ticker) if estimates else ticker) \
        .replace("{{report_date}}", str(getattr(estimates, "date", "Unknown")) if estimates else "Unknown") \
        .replace("{{report_timing}}", "Unknown") \
        .replace("{{eps_consensus}}", str(getattr(estimates, "eps_consensus", "0.0")) if estimates else "0.0") \
        .replace("{{revenue_consensus}}", str(getattr(estimates, "revenue_consensus", "0.0")) if estimates else "0.0") \
        .replace("{{quarters_beat}}", str(getattr(history, "quarters_beat", "0")) if history else "0") \
        .replace("{{total_quarters}}", str((getattr(history, "quarters_beat", 0) + getattr(history, "quarters_missed", 0))) if history else "0") \
        .replace("{{avg_surprise}}", str(getattr(history, "avg_surprise_percent", "0.0")) if history else "0.0") \
        .replace("{{last_eps_actual}}", last_actual) \
        .replace("{{last_eps_consensus}}", last_consensus) \
        .replace("{{last_surprise}}", last_surprise) \
        .replace("{{last_reaction}}", last_reaction) \
        .replace("{{pe_ratio}}", str(getattr(metrics, "pe_ratio", "N/A")) if metrics else "N/A") \
        .replace("{{pe_sector_median}}", sector_pe_str) \
        .replace("{{pe_own_3y_median}}", pe_own_median_str) \
        .replace("{{ps_ratio}}", str(getattr(metrics, "ps_ratio", "N/A")) if metrics else "N/A") \
        .replace("{{market_cap}}", str(getattr(metrics, "market_cap", "N/A")) if metrics else "N/A") \
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
        .replace("{{options_metrics}}", f"PCR: {options.put_call_ratio_oi} | IV ATM: {options.implied_volatility_atm * 100:.1f}%" if options else "N/A") \
        .replace("{{social_sentiment}}", f"Score: {social.social_score} (Reddit: {social.reddit_mentions}, Twitter: {social.twitter_mentions})" if social else "N/A") \
        .replace("{{news_bullet_points}}", news_str) \
        .replace("{{opportunity_score}}", str(opp_score.total_score if opp_score else 0.0)) \
        .replace("{{torpedo_score}}", str(torp_score.total_score if torp_score else 0.0))
        
    result = await call_deepseek(sys_prompt, user_prompt)
    if "MOCK_REPORT:" in result:
        # Erweitere den Mock-Bericht um unsere Daten zur Validierung
        return f"{result}\n\n[MOCK DATA CHECK]\nTicker: {ticker}\nEmpfehlung: {rec.recommendation if rec else 'N/A'} ({rec.reasoning if rec else 'N/A'})\nOS: {opp_score.total_score if opp_score else 0.0} | TS: {torp_score.total_score if torp_score else 0.0}"
        
    return result

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
