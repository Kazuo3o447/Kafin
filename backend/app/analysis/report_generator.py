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
    
    # Wirtschaftskalender: Nächste 7 Tage
    try:
        calendar_events = await get_economic_calendar(days_back=0, days_forward=7)
    except Exception as e:
        logger.error(f"Fehler beim Abrufen des Wirtschaftskalenders: {e}")
        calendar_events = []
    
    # Top-3 Events formatieren
    upcoming_str = "Keine anstehenden Events bekannt."
    if calendar_events:
        top_events = calendar_events[:3]
        lines = []
        for ev in top_events:
            est_str = f" (Erwartung: {ev.get('estimate', 'N/A')}{ev.get('unit', '')})" if ev.get('estimate') is not None else ""
            lines.append(f"- {ev.get('date', '?')}: {ev.get('event', '?')}{est_str}")
        upcoming_str = "\n".join(lines)
    
    sys_prompt, user_tmpl = _read_prompt(MACRO_PROMPT_PATH)
    
    # Replace placeholders
    user_prompt = user_tmpl \
        .replace("{{fed_rate}}", str(getattr(macro, "fed_rate", "N/A"))) \
        .replace("{{vix}}", str(getattr(macro, "vix", "N/A"))) \
        .replace("{{credit_spread}}", str(getattr(macro, "credit_spread_bps", "N/A"))) \
        .replace("{{yield_spread}}", str(getattr(macro, "yield_curve_10y_2y", "N/A"))) \
        .replace("{{dxy}}", str(getattr(macro, "dxy", "N/A"))) \
        .replace("{{upcoming_events}}", upcoming_str)
        
    result = await call_deepseek(sys_prompt, user_prompt)
    return result

async def generate_audit_report(ticker: str) -> str:
    """
    Generiert einen detaillierten, unternehmensspezifischen Audit-Report,
    indem Daten aus Finnhub, FMP, YFinance und eigenen Scores aggregiert und 
    via DeepSeek im Fließtext formuliert werden.
    """
    logger.info(f"Generating Audit Report for {ticker}")
    
    # 1. Fetch data
    estimates = await get_analyst_estimates(ticker)
    history = await get_earnings_history(ticker)
    profile = await get_company_profile(ticker)
    metrics = await get_key_metrics(ticker)
    short_interest = await get_short_interest(ticker)
    insiders = await get_insider_transactions(ticker)
    technicals = await get_technical_setup(ticker)
    
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
        "news_memory": news_memory if news_memory else []
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
        .replace("{{last_eps_actual}}", "0.0") \
        .replace("{{last_eps_consensus}}", "0.0") \
        .replace("{{last_surprise}}", "0.0") \
        .replace("{{last_reaction}}", "0.0") \
        .replace("{{pe_ratio}}", str(getattr(metrics, "pe_ratio", "N/A")) if metrics else "N/A") \
        .replace("{{pe_sector_median}}", "15.0") \
        .replace("{{pe_own_3y_median}}", "18.0") \
        .replace("{{ps_ratio}}", str(getattr(metrics, "ps_ratio", "N/A")) if metrics else "N/A") \
        .replace("{{market_cap}}", str(getattr(metrics, "market_cap", "N/A")) if metrics else "N/A") \
        .replace("{{current_price}}", str(getattr(technicals, "current_price", "N/A")) if technicals else "N/A") \
        .replace("{{trend}}", str(getattr(technicals, "trend", "N/A")) if technicals else "N/A") \
        .replace("{{sma50_status}}", "Über" if technicals and technicals.above_sma50 else "Unter") \
        .replace("{{sma50_distance}}", "0.0") \
        .replace("{{sma200_status}}", "Über" if technicals and technicals.above_sma200 else "Unter") \
        .replace("{{sma200_distance}}", "0.0") \
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

    wl = await get_watchlist()
    tickers = [item["ticker"] for item in wl]

    all_bullets = []
    for ticker in tickers:
        bullets = await get_bullet_points(ticker)
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        recent = [b for b in bullets if str(b.get("date", "")) >= str(cutoff)]
        all_bullets.extend(recent)

    # GENERAL_MACRO: Globale Wirtschaftsevents immer einbeziehen
    macro_bullets = await get_bullet_points("GENERAL_MACRO")
    cutoff_macro = (datetime.now() - timedelta(days=7)).isoformat()
    macro_recent = [b for b in macro_bullets if str(b.get("date", "")) >= str(cutoff_macro)]
    all_bullets.extend(macro_recent)

    if not all_bullets:
        return "Keine bemerkenswerten Events in dieser Woche."

    # Sortiere: Material-Events zuerst, dann nach absolutem Sentiment
    all_bullets.sort(key=lambda x: (
        -int(x.get("is_material", False)),
        -abs(float(x.get("sentiment_score", 0)))
    ))

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
    logger.info(f"Generating Sunday Report for {len(tickers)} tickers")
    
    # 1. Makro-Header
    header = await generate_macro_header()
    
    # 2. Wochenzusammenfassung (NEU)
    weekly = await generate_weekly_summary()
    
    # 3. Audit-Reports
    reports = []
    for t in tickers:
        r = await generate_audit_report(t)
        reports.append(r)
        
    full_report = f"# KAFIN SONNTAGS-REPORT\n\n"
    full_report += f"## MAKRO-REGIME\n\n{header}\n\n---\n\n"
    full_report += f"## WOCHENZUSAMMENFASSUNG\n\n{weekly}\n\n---\n\n"
    full_report += f"## AUDIT-REPORTS\n\n"
    full_report += "\n\n---\n\n".join(reports)
    
    return full_report
