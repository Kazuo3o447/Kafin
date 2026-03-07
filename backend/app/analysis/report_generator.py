import os
from datetime import datetime
from backend.app.logger import get_logger
from backend.app.data.finnhub import get_company_news, get_short_interest, get_insider_transactions
from backend.app.data.fmp import get_company_profile, get_analyst_estimates, get_earnings_history, get_key_metrics
from backend.app.data.fred import get_macro_snapshot
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
    logger.info("Generating Macro Header")
    macro = await get_macro_snapshot()
    
    sys_prompt, user_tmpl = _read_prompt(MACRO_PROMPT_PATH)
    
    # Replace placeholders
    user_prompt = user_tmpl \
        .replace("{{fed_rate}}", str(macro.fed_funds_rate)) \
        .replace("{{vix}}", str(macro.vix)) \
        .replace("{{credit_spread}}", str(macro.high_yield_spread)) \
        .replace("{{yield_spread}}", str(macro.yield_curve_10y_2y)) \
        .replace("{{dxy}}", str(macro.dxy))
        
    result = await call_deepseek(sys_prompt, user_prompt)
    return result

async def generate_audit_report(ticker: str) -> str:
    logger.info(f"Generating Audit Report for {ticker}")
    
    # 1. Fetch data
    estimates = await get_analyst_estimates(ticker)
    history = await get_earnings_history(ticker)
    profile = await get_company_profile(ticker)
    metrics = await get_key_metrics(ticker)
    short_interest = await get_short_interest(ticker)
    insiders = await get_insider_transactions(ticker)
    
    now = datetime.now()
    month_ago = now.replace(day=max(1, now.day - 30)) if now.day > 1 else now # rough 30 days
    news_list = await get_company_news(ticker, month_ago.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))
    
    macro = await get_macro_snapshot()
    
    # Assemble data context for scoring
    # Note: Using dicts for scores matching the implemented logic
    data_ctx = {
        "earnings_history": history.dict(),
        "valuation": metrics.dict() if metrics else profile.dict(),
        "short_interest": short_interest.dict(),
        "insider_activity": insiders.dict(),
        "macro": macro.dict()
    }
    
    # 2. Scores
    opp_score = await calculate_opportunity_score(ticker, data_ctx)
    torp_score = await calculate_torpedo_score(ticker, data_ctx)
    rec = await get_recommendation(opp_score, torp_score)
    
    # 3. Prompt replacement
    sys_prompt, user_tmpl = _read_prompt(AUDIT_PROMPT_PATH)
    
    # Format news
    news_str = "\n".join([f"- {n.headline}: {n.summary[:100]}..." for n in news_list[:5]])
    if not news_str: news_str = "Keine relevanten Nachrichten in den letzten 30 Tagen."
    
    user_prompt = user_tmpl \
        .replace("{{ticker}}", ticker) \
        .replace("{{company_name}}", estimates.company_name if hasattr(estimates, "company_name") else ticker) \
        .replace("{{report_date}}", str(estimates.date)) \
        .replace("{{report_timing}}", "Unknown") \
        .replace("{{eps_consensus}}", str(estimates.eps_consensus)) \
        .replace("{{revenue_consensus}}", str(estimates.revenue_consensus)) \
        .replace("{{quarters_beat}}", str(history.quarters_beat)) \
        .replace("{{total_quarters}}", str(history.quarters_beat + history.quarters_missed)) \
        .replace("{{avg_surprise}}", str(history.avg_surprise_percent)) \
        .replace("{{last_eps_actual}}", "0.0") \
        .replace("{{last_eps_consensus}}", "0.0") \
        .replace("{{last_surprise}}", "0.0") \
        .replace("{{last_reaction}}", "0.0") \
        .replace("{{pe_ratio}}", getattr(metrics, "pe_ratio", "N/A") if metrics else "N/A") \
        .replace("{{pe_sector_median}}", "15.0") \
        .replace("{{pe_own_3y_median}}", "18.0") \
        .replace("{{ps_ratio}}", getattr(metrics, "ps_ratio", "N/A") if metrics else "N/A") \
        .replace("{{market_cap}}", getattr(metrics, "market_cap", "N/A") if metrics else "N/A") \
        .replace("{{current_price}}", "N/A") \
        .replace("{{trend}}", "N/A") \
        .replace("{{sma50_status}}", "N/A") \
        .replace("{{sma50_distance}}", "0.0") \
        .replace("{{sma200_status}}", "N/A") \
        .replace("{{sma200_distance}}", "0.0") \
        .replace("{{rsi}}", "50") \
        .replace("{{support}}", "N/A") \
        .replace("{{resistance}}", "N/A") \
        .replace("{{distance_52w_high}}", "0.0") \
        .replace("{{short_interest}}", str(short_interest.short_interest)) \
        .replace("{{days_to_cover}}", str(short_interest.days_to_cover)) \
        .replace("{{si_trend}}", short_interest.trend) \
        .replace("{{squeeze_risk}}", short_interest.squeeze_risk) \
        .replace("{{insider_buys}}", str(insiders.cluster_buys)) \
        .replace("{{insider_buy_value}}", str(insiders.total_buy_volume_90d)) \
        .replace("{{insider_sells}}", str(insiders.cluster_sells)) \
        .replace("{{insider_sell_value}}", str(insiders.total_sell_volume_90d)) \
        .replace("{{insider_assessment}}", insiders.cluster_assessment) \
        .replace("{{news_bullet_points}}", news_str) \
        .replace("{{opportunity_score}}", str(opp_score.total_score)) \
        .replace("{{torpedo_score}}", str(torp_score.total_score))
        
    result = await call_deepseek(sys_prompt, user_prompt)
    if "MOCK_REPORT:" in result:
        # Erweitere den Mock-Bericht um unsere Daten zur Validierung
        return f"{result}\n\n[MOCK DATA CHECK]\nTicker: {ticker}\nEmpfehlung: {rec.recommendation} ({rec.reasoning})\nOS: {opp_score.total_score} | TS: {torp_score.total_score}"
        
    return result

async def generate_sunday_report(tickers: list[str]) -> str:
    logger.info(f"Generating Sunday Report for {len(tickers)} tickers")
    
    header = await generate_macro_header()
    
    reports = []
    for t in tickers:
        r = await generate_audit_report(t)
        reports.append(r)
        
    full_report = f"# KAFIN SUNDAY REPORT\n\n{header}\n\n---\n\n"
    full_report += "\n\n---\n\n".join(reports)
    
    return full_report
