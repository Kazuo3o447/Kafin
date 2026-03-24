import os
import json
import asyncio
from datetime import datetime, timedelta, timezone
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
from backend.app.memory.short_term import _calc_sentiment_from_bullets
from backend.app.analysis.shadow_portfolio import open_shadow_trade
from schemas.valuation import ValuationData

logger = get_logger(__name__)

# Max. gleichzeitige DeepSeek-Calls (Rate Limit Schutz)
_DEEPSEEK_SEMAPHORE = asyncio.Semaphore(3)


def _fmt(value, date, unit="", fallback="Nicht verfügbar"):
    """Formatiert einen FRED-Wert für den Prompt. Verhindert dass 'None' an die KI geht."""
    if value is None:
        return fallback
    result = f"{value}{unit}"
    if date:
        result += f" (Stand: {date})"
    return result


def _valuation_from_fundamentals(ticker: str, fundamentals: dict) -> ValuationData:
    """Kleiner lokaler Fallback für Profil-/Bewertungsdaten aus yfinance."""
    return ValuationData(
        ticker=ticker,
        sector=fundamentals.get("sector"),
        industry=fundamentals.get("industry"),
        pe_ratio=fundamentals.get("pe_ratio") or fundamentals.get("forward_pe"),
        ps_ratio=fundamentals.get("ps_ratio"),
        market_cap=fundamentals.get("market_cap"),
        debt_to_equity=fundamentals.get("debt_to_equity"),
        current_ratio=fundamentals.get("current_ratio"),
        free_cash_flow_yield=fundamentals.get("free_cash_flow_yield"),
    )

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

    result = await call_deepseek(sys_prompt, user_prompt, model="deepseek-reasoner")
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
        try:
            yf_fundamentals = await get_fundamentals_yf(ticker)
            if yf_fundamentals:
                profile = _valuation_from_fundamentals(ticker, yf_fundamentals)
                logger.info(f"[{ticker}] Profil-Fallback via yfinance aktiviert")
        except Exception as exc:
            logger.debug(f"[{ticker}] Profil-Fallback via yfinance fehlgeschlagen: {exc}")
        if not profile:
            logger.warning(f"Ticker-Validierung fehlgeschlagen für {ticker}.")
            return f"Fehler: Ticker '{ticker}' ist ungültig (kein Profil gefunden)."

    # Daten laden — jeder Call einzeln abgesichert
    estimates = None
    try:
        estimates = await get_analyst_estimates(ticker)
    except Exception as e:
        logger.warning(f"Analyst estimates für {ticker}: {e}")

    # Analyst Grades für guidance_trend/deceleration
    audit_grades = None
    try:
        from backend.app.data.fmp import get_analyst_grades
        audit_grades = await get_analyst_grades(ticker)
    except Exception as e:
        logger.warning(f"Analyst grades für {ticker}: {e}")

    history = None
    try:
        history = await get_earnings_history(ticker)
    except Exception as e:
        logger.warning(f"Earnings history für {ticker}: {e}")

    # yfinance Fallback wenn FMP keine Earnings-History liefert
    if not history:
        try:
            from backend.app.data.yfinance_data import get_earnings_history_yf
            from schemas.earnings import EarningsHistorySummary
            yf_hist_raw = await get_earnings_history_yf(ticker)
            if yf_hist_raw:
                history = EarningsHistorySummary(
                    ticker=ticker,
                    quarters_beat=yf_hist_raw.get("quarters_beat", 0),
                    total_quarters=yf_hist_raw.get("total_quarters", 0),
                    avg_surprise_percent=yf_hist_raw.get("avg_surprise_percent"),
                    all_quarters=yf_hist_raw.get("all_quarters", []),
                )
                logger.info(
                    f"[{ticker}] Earnings-History via yfinance: "
                    f"{history.quarters_beat}/{history.total_quarters} Beats"
                )
        except Exception as e:
            logger.debug(f"yfinance Earnings-History Fallback {ticker}: {e}")

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

    # ── Relative Stärke + Trade Setup Daten laden ─────────────────
    from backend.app.data.market_overview import get_market_overview
    from backend.app.analysis.chart_analyst import analyze_chart
    import asyncio
    
    market_ov_result, chart_result = await asyncio.gather(
        get_market_overview(),
        analyze_chart(ticker),
        return_exceptions=True,
    )
    
    def safe_extra(r, default):
        return default if isinstance(r, Exception) else r
    
    market_ov = safe_extra(market_ov_result, {})
    chart_data = safe_extra(chart_result, {})

    # ── Expected Move Berechnung ──────────────────────────────
    expected_move_pct: float | None = None
    expected_move_usd: float | None = None
    price_change_30d: float | None = None

    try:
        import math
        from datetime import date as date_cls

        # Tage bis Earnings berechnen
        earnings_dt = getattr(estimates, "report_date", None) if estimates else None
        if earnings_dt and hasattr(earnings_dt, "toordinal"):
            days_to_earnings = max(1, (earnings_dt - date_cls.today()).days)
        elif earnings_dt:
            try:
                from datetime import datetime as dt_cls
                earnings_dt_parsed = dt_cls.strptime(str(earnings_dt), "%Y-%m-%d").date()
                days_to_earnings = max(1, (earnings_dt_parsed - date_cls.today()).days)
            except Exception:
                days_to_earnings = 1
        else:
            days_to_earnings = 1

        # IV aus options holen
        iv = getattr(options, "implied_volatility_atm", None) if options else None

        # Aktueller Preis aus technicals
        current_price = getattr(technicals, "current_price", None) if technicals else None

        if iv and iv > 0 and current_price and current_price > 0:
            # Formel: Preis × IV × sqrt(Tage / 365)
            expected_move_pct = round(iv * math.sqrt(days_to_earnings / 365) * 100, 1)
            expected_move_usd = round(current_price * iv * math.sqrt(days_to_earnings / 365), 2)

    except Exception as e:
        logger.debug(f"Expected Move Berechnung {ticker}: {e}")

    # ── 30-Tage-Kursperformance (Pre-Earnings Rally) ──────────
    try:
        def _fetch_30d_change(t: str) -> float | None:
            import yfinance as yf
            stock = yf.Ticker(t)
            hist = stock.history(period="35d")
            if hist.empty or len(hist) < 2:
                return None
            p0 = float(hist["Close"].iloc[0])
            p1 = float(hist["Close"].iloc[-1])
            if p0 <= 0:
                return None
            return round(((p1 - p0) / p0) * 100, 1)

        price_change_30d = await asyncio.to_thread(
            _fetch_30d_change, ticker
        )
    except Exception as e:
        logger.debug(f"30d Price Change {ticker}: {e}")

    # ── Relative Stärke berechnen ───────────────────────────────
    SECTOR_TO_ETF = {
        "Technology": "XLK", "Financial Services": "XLF",
        "Financials": "XLF", "Energy": "XLE",
        "Healthcare": "XLV", "Health Care": "XLV",
        "Utilities": "XLU", "Industrials": "XLI",
        "Communication Services": "XLC", "Communication": "XLC",
        "Consumer Cyclical": "XLY",
        "Consumer Discretionary": "XLY",
        "Consumer Defensive": "XLP",
        "Consumer Staples": "XLP",
        "Basic Materials": "XLB", "Materials": "XLB",
        "Real Estate": "XLRE",
    }

    ticker_sector = (
        getattr(profile, "sector", None)
        or getattr(metrics, "sector", None)
        or (yf_fundamentals.get("sector") if yf_fundamentals else None)
        or "Unknown"
    )

    indices_data = market_ov.get("indices", {})
    spy = indices_data.get("SPY", {})
    sector_etf_sym = SECTOR_TO_ETF.get(ticker_sector, None)
    sector_etf = indices_data.get(sector_etf_sym, {}) if sector_etf_sym else {}

    # price_change_30d aus technicals oder yf_fundamentals
    ticker_1m = (
        getattr(technicals, "price_change_30d", None)
        if technicals else None
    ) or (
        yf_fundamentals.get("price_change_30d")
        if yf_fundamentals else None
    )
    ticker_5d = (
        yf_fundamentals.get("change_5d_pct")
        if yf_fundamentals else None
    )

    ticker_1d_pct = None
    try:
        import yfinance as yf

        def _fetch_1d_change(t: str) -> float | None:
            stock = yf.Ticker(t)
            fast_info = getattr(stock, "fast_info", None)
            if not fast_info:
                return None
            change_pct = getattr(fast_info, "regular_market_day_change_percent", None)
            if change_pct is None:
                return None
            return round(float(change_pct) * 100, 2)

        ticker_1d_pct = await asyncio.to_thread(_fetch_1d_change, ticker)
    except Exception:
        ticker_1d_pct = None

    def rs(a, b):
        if a is None or b is None: return "N/A"
        diff = a - b
        sign = "+" if diff >= 0 else ""
        return f"{sign}{diff:.1f}%"

    rel_str = (
        f"vs. S&P 500 (SPY):\n"
        f"  1T: Ticker {f'{ticker_1d_pct:+.1f}%' if ticker_1d_pct is not None else 'N/A'} "
        f"vs SPY {spy.get('change_1d_pct', 'N/A')}% "
        f"→ Alpha: {rs(ticker_1d_pct, spy.get('change_1d_pct'))}\n"
        f"  5T: Ticker {ticker_5d or 'N/A'}% "
        f"vs SPY {spy.get('change_5d_pct', 'N/A')}% "
        f"→ Alpha: {rs(ticker_5d, spy.get('change_5d_pct'))}\n"
        f"  20T: Ticker {ticker_1m or 'N/A'}% "
        f"vs SPY {spy.get('change_1m_pct', 'N/A')}% "
        f"→ Alpha: {rs(ticker_1m, spy.get('change_1m_pct'))}\n"
    )

    if sector_etf_sym:
        rel_str += (
            f"\nvs. Sektor-ETF {sector_etf_sym} ({ticker_sector}):\n"
            f"  5T: Ticker {ticker_5d or 'N/A'}% "
            f"vs {sector_etf_sym} {sector_etf.get('change_5d_pct', 'N/A')}% "
            f"→ Alpha: {rs(ticker_5d, sector_etf.get('change_5d_pct'))}\n"
            f"  20T: Ticker {ticker_1m or 'N/A'}% "
            f"vs {sector_etf_sym} {sector_etf.get('change_1m_pct', 'N/A')}% "
            f"→ Alpha: {rs(ticker_1m, sector_etf.get('change_1m_pct'))}\n"
        )

    # ── Chart-Analyse aufbereiten ───────────────────────────────
    if chart_data and not chart_data.get("error"):
        entry = chart_data.get("entry_zone", {})
        entry_low = entry.get("low")
        entry_high = entry.get("high")
        stop_loss = chart_data.get("stop_loss")
        target_1 = chart_data.get("target_1")
        target_2 = chart_data.get("target_2")

        def _fmt_price(value):
            return f"${value:.2f}" if isinstance(value, (int, float)) else "N/A"

        chart_str = (
            f"Entry-Zone: {_fmt_price(entry_low)}"
            f" – {_fmt_price(entry_high)}\n"
            f"Stop-Loss: {_fmt_price(stop_loss)}\n"
            f"Target 1: {_fmt_price(target_1)}\n"
            f"Target 2: {_fmt_price(target_2)}\n"
            f"Bias: {chart_data.get('bias', 'N/A')}\n"
            f"Hauptrisiko: {chart_data.get('key_risk', 'N/A')}\n"
        )
        
        # NEU: Begründungen ergänzen
        if chart_data.get("why_entry"):
            chart_str += (
                f"Entry-Begründung: "
                f"{chart_data['why_entry']}\n"
            )
        if chart_data.get("why_stop"):
            chart_str += (
                f"Stop-Begründung: "
                f"{chart_data['why_stop']}\n"
            )
        if chart_data.get("trend_context"):
            chart_str += (
                f"Trend-Kontext: "
                f"{chart_data['trend_context']}\n"
            )
        if chart_data.get("falling_knife_risk"):
            chart_str += (
                f"Falling-Knife-Risiko: "
                f"{chart_data['falling_knife_risk']}\n"
            )
        if chart_data.get("floor_scenario"):
            chart_str += (
                f"Floor-Szenario: "
                f"{chart_data['floor_scenario']}\n"
            )
        if chart_data.get("turnaround_conditions"):
            chart_str += (
                f"Turnaround-Bedingungen: "
                f"{chart_data['turnaround_conditions']}\n"
            )
        if chart_data.get("key_risk"):
            chart_str += (
                f"Hauptrisiko: "
                f"{chart_data['key_risk']}\n"
            )
        supports = chart_data.get("support_levels", [])
        if supports:
            chart_str += "Support-Level: " + ", ".join(
                f"${s['price']:.2f} ({s['label']}, {s['strength']})"
                for s in supports[:3]
            ) + "\n"
        resistances = chart_data.get("resistance_levels", [])
        if resistances:
            chart_str += "Resistance-Level: " + ", ".join(
                f"${r['price']:.2f} ({r['label']}, {r['strength']})"
                for r in resistances[:3]
            ) + "\n"
        
        # R:R berechnen
        try:
            entry_mid = (
                (chart_data["entry_zone"]["low"]
                 + chart_data["entry_zone"]["high"]) / 2
            ) if chart_data.get("entry_zone") else None
            denominator = (
                entry_mid - chart_data["stop_loss"]
                if entry_mid is not None and chart_data.get("stop_loss") is not None
                else None
            )
            rr = (
                (chart_data["target_1"] - entry_mid) / denominator
                if entry_mid is not None
                and chart_data.get("stop_loss") is not None
                and chart_data.get("target_1") is not None
                and denominator is not None
                and abs(denominator) > 0.01
                else None
            )
            if rr is not None:
                chart_str += f"R:R Verhältnis: 1:{rr:.1f}\n"
        except Exception:
            pass
    else:
        chart_str = "Chart-Analyse nicht verfügbar."

    social = None  # Finnhub Social Sentiment nicht verfügbar (kein Free-Tier Endpoint)
    
    # ── Web Intelligence (Cache-aware) ───────────────────────
    # Sichere Initialisierung vor try-Blöcken
    _company_name = getattr(estimates, "company_name", ticker) \
        if estimates else ticker
    _days_to_earnings = None
    _manual_prio = None
    
    web_intelligence = ""
    try:
        from backend.app.data.web_search import get_web_intelligence
        from backend.app.data.web_search import _auto_prio_from_days

        # Tage bis Earnings berechnen
        _earnings_dt = getattr(estimates, "report_date", None) \
            if estimates else None
        _days_to_earnings = None
        if _earnings_dt:
            try:
                from datetime import date as _date_cls
                _earnings_date = (
                    _earnings_dt if hasattr(_earnings_dt, "toordinal")
                    else _date_cls.fromisoformat(str(_earnings_dt))
                )
                _days_to_earnings = (_earnings_date - _date_cls.today()).days
            except Exception:
                pass

        # web_prio aus Watchlist holen
        _manual_prio = None
        try:
            from backend.app.db import get_supabase_client as _get_db
            _db = _get_db()
            if _db:
                _wl_res = await (
                    _db.table("watchlist")
                    .select("web_prio")
                    .eq("ticker", ticker.upper())
                    .execute_async()
                )
                _wl_rows = _wl_res.data if _wl_res and _wl_res.data else []
                if _wl_rows and _wl_rows[0].get("web_prio") is not None:
                    _manual_prio = int(_wl_rows[0]["web_prio"])
        except Exception:
            pass

        _company_name = getattr(estimates, "company_name", ticker) \
            if estimates else ticker

        web_intelligence = await get_web_intelligence(
            ticker=ticker,
            company_name=_company_name,
            days_to_earnings=_days_to_earnings,
            manual_prio=_manual_prio,
            force_refresh=False,
        )
        if web_intelligence:
            logger.info(f"Web Intelligence geladen für {ticker}")
    except Exception as e:
        logger.warning(f"Web Intelligence {ticker}: {e}")
        web_intelligence = ""

    now = datetime.now()
    month_ago = now - timedelta(days=30)

    # 1.5 Try getting news from memory first, else fallback to Finnhub
    from backend.app.memory.short_term import get_bullet_points
    news_memory = await get_bullet_points(ticker)
    
    google_news_for_ticker: list[str] = []
    if news_memory:
        for nm in news_memory:
            source = str(nm.get("source", ""))
            if source.startswith("google_news:"):
                bp_data = nm.get("bullet_points", [])
                if isinstance(bp_data, list):
                    google_news_for_ticker.extend(bp_data)
                elif isinstance(bp_data, str):
                    google_news_for_ticker.append(bp_data)

    news_list = None
    if not news_memory:
        news_list = await get_company_news(ticker, month_ago.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))
    
    # ── Composite Sentiment Score ─────────────────────────────
    # Einheitliche Aggregation mit der Plattform-Helper-Logik
    ticker_sent = _calc_sentiment_from_bullets(news_memory or [])
    finbert_sentiment = ticker_sent["avg"]

    # Web-Sentiment-Score (proaktiv, aktueller Marktdiskurs)
    web_sentiment_score = 0.0
    web_sentiment_label = "neutral"
    try:
        if web_intelligence and not web_intelligence.startswith(
            "Keine"
        ):
            from backend.app.data.web_search import (
                get_web_sentiment_score,
            )
            web_sentiment_score, web_sentiment_label = (
                await get_web_sentiment_score(
                    ticker=ticker,
                    company_name=_company_name,
                    days_to_earnings=_days_to_earnings,
                    manual_prio=_manual_prio,
                )
            )
    except Exception as e:
        logger.warning(f"Web Sentiment Score {ticker}: {e}")

    # Gewichteter Composite Score
    # FinBERT: 50% (zuverlässig, viele Datenpunkte)
    # Web:     50% (proaktiv, hohe Relevanz für Earnings)
    
    # Reddit Retail Sentiment (kostenlos, gecacht 1h)
    reddit_data = {}
    social_score_raw = 0.0
    try:
        from backend.app.data.reddit_monitor import get_reddit_sentiment
        reddit_data = await get_reddit_sentiment(ticker, hours=24)
        social_score_raw = reddit_data.get("avg_score") or 0.0
        logger.debug(
            f"[{ticker}] Reddit: score={social_score_raw:+.2f}, "
            f"mentions={reddit_data.get('mention_count', 0)}"
        )
    except Exception as e:
        logger.debug(f"Reddit Sentiment {ticker}: {e}")

    composite_sentiment = round(
        finbert_sentiment * 0.5
        + web_sentiment_score * 0.5,
        3,
    )

    # Divergenz erkennen
    sentiment_divergence = False
    divergence_text = ""
    if abs(finbert_sentiment - web_sentiment_score) > 0.4:
        sentiment_divergence = True
        if finbert_sentiment > 0.2 and web_sentiment_score < -0.2:
            divergence_text = (
                f"⚠ Sentiment-Divergenz: News bullisch "
                f"({finbert_sentiment:+.2f}) aber Web-Diskurs "
                f"bärisch ({web_sentiment_score:+.2f}) — "
                f"klassisches 'Good News Already Priced In'-Setup"
            )
        elif finbert_sentiment < -0.2 and web_sentiment_score > 0.2:
            divergence_text = (
                f"⚠ Sentiment-Divergenz: News bärisch "
                f"({finbert_sentiment:+.2f}) aber Analysten "
                f"optimistisch ({web_sentiment_score:+.2f}) — "
                f"mögliches Contrarian-Setup"
            )

    logger.info(
        f"Sentiment {ticker}: FinBERT={finbert_sentiment:+.2f} | "
        f"Web={web_sentiment_score:+.2f} ({web_sentiment_label}) | "
        f"Social={social_score_raw:+.2f} | "
        f"Composite={composite_sentiment:+.2f}"
        + (" | DIVERGENZ" if sentiment_divergence else "")
    )
    
    from backend.app.data.fear_greed import get_fear_greed_score
    
    macro, fear_greed_data = await asyncio.gather(
        get_macro_snapshot(),
        get_fear_greed_score(),
        return_exceptions=True,
    )
    if isinstance(macro, Exception):
        macro = None
    if isinstance(fear_greed_data, Exception):
        fear_greed_data = {}
    
    # Assemble data context for scoring
    valuation_ctx = {}
    if metrics:
        valuation_ctx = _model_to_dict(metrics)
    elif profile:
        valuation_ctx = _model_to_dict(profile)
    elif yf_fundamentals:
        valuation_ctx = {
            "ticker": ticker,
            "pe_ratio": yf_fundamentals.get("pe_ratio"),
            "ps_ratio": yf_fundamentals.get("ps_ratio"),
            "market_cap": yf_fundamentals.get("market_cap"),
            "sector": yf_fundamentals.get("sector"),
        }

    data_ctx = {
        "earnings_history": _model_to_dict(history),
        "valuation": valuation_ctx,
        "short_interest": _model_to_dict(short_interest),
        "insider_activity": _model_to_dict(insiders),
        "macro": _model_to_dict(macro),
        "technicals": _model_to_dict(technicals),
        "news_memory": news_memory if news_memory else [],
        "options": _model_to_dict(options),
        "social": _model_to_dict(social),
        "composite_sentiment": composite_sentiment,
        "web_sentiment_score": web_sentiment_score,
        "finbert_sentiment": finbert_sentiment,
        "sentiment_divergence": sentiment_divergence,
        # NEU: für guidance_trend + deceleration
        "analyst_grades": audit_grades or [],
        # NEU: für sector_regime
        "sector_ranking": market_ov.get("sector_ranking_5d", []) if market_ov else [],
        "ticker_sector": (
            getattr(profile, "sector", None)
            or (yf_fundamentals.get("sector") if yf_fundamentals else None)
            or "Unknown"
        ),
        # NEU: Reddit Sentiment
        "reddit_sentiment": social_score_raw,
        "reddit_mentions": reddit_data.get("mention_count", 0),
        "reddit_label": reddit_data.get("label", "keine Daten"),
        # NEU: Fear & Greed Score
        "fear_greed_score": fear_greed_data.get("score", 50.0),
        "fear_greed_label": fear_greed_data.get("label", "Neutral"),
    }
    
    # 2. Scores
    opp_score = await calculate_opportunity_score(ticker, data_ctx)
    torp_score = await calculate_torpedo_score(ticker, data_ctx)
    
    # 2.1 Makro-Daten für Regime-Gate
    _macro_regime = getattr(macro, "regime", None) if macro else None
    _vix = getattr(macro, "vix", None) if macro else None
    
    rec = await get_recommendation(
        opp_score, 
        torp_score,
        macro_regime=_macro_regime,
        vix=_vix,
    )
    
    # 2.5 Langzeit-Gedächtnis laden
    lt_memory = ""
    try:
        lt_insights = await get_all_insights_for_report(ticker)
        if lt_insights:
            lt_memory = "\n".join([f"- {ins.get('insight_text', '')}" for ins in lt_insights[:5]])
        else:
            lt_memory = "Keine Langzeit-Insights vorhanden."
    except Exception as e:
        logger.debug(f"Langzeit-Gedächtnis für {ticker}: {e}")
        lt_memory = "Langzeit-Gedächtnis nicht verfügbar."
    
    # 3. Prompt replacement
    sys_prompt, user_tmpl = _read_prompt(AUDIT_PROMPT_PATH)
    
    # Format news with sentiment scores
    if news_memory:
        news_items = []
        for nm in news_memory[:8]:
            bullet = nm.get("bullet_points", "")
            raw_score = nm.get("sentiment_score", 0.0)
            try:
                score = float(raw_score) if raw_score is not None else 0.0
                direction = (
                    "bullish" if score > 0.2
                    else "bearish" if score < -0.2
                    else "neutral"
                )
                score_str = f"[{score:+.2f} {direction}]"
            except (TypeError, ValueError):
                score = None
                score_str = "[?]"

            if isinstance(bullet, list):
                for b in bullet[:2]:
                    news_items.append(f"{score_str} {b}")
            elif isinstance(bullet, str) and bullet:
                news_items.append(f"{score_str} {bullet}")

        news_str = "\n".join(news_items[:7])

        if ticker_sent["count"] > 0:
            news_str = (
                f"Aggregiertes News-Sentiment: {ticker_sent['avg']:+.2f}"
                f" ({ticker_sent['trend']}, {ticker_sent['count']} Artikel)\n\n"
                + news_str
            )
    else:
        # Fallback: Finnhub ohne Scores
        if news_list:
            news_str = "\n".join([
                f"[?] {n.headline}: {n.summary[:80]}..."
                for n in news_list[:5]
            ])
        else:
            news_str = "Keine relevanten Nachrichten."

    if google_news_for_ticker:
        gn_scored = "\n".join([
            f"[extern] {n}" for n in google_news_for_ticker[:3]
        ])
        news_str += f"\n\nGoogle News (Zusatz):\n{gn_scored}"
    
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

    # Get beta from yf_fundamentals or metrics
    beta_val = None
    if yf_fundamentals and yf_fundamentals.get("beta"):
        beta_val = yf_fundamentals["beta"]
    elif metrics and hasattr(metrics, "beta"):
        beta_val = getattr(metrics, "beta", None)
    
    # Calculate quality_score and mismatch_score
    quality_score_val = None
    mismatch_score_val = None
    if metrics and all(hasattr(metrics, attr) for attr in ["debt_to_equity", "current_ratio", "free_cash_flow_yield", "pe_ratio"]):
        from backend.app.analysis.scoring import calculate_quality_score, calculate_mismatch_score
        
        quality_score_val = calculate_quality_score(
            debt_to_equity=getattr(metrics, "debt_to_equity", None),
            current_ratio=getattr(metrics, "current_ratio", None),
            free_cash_flow_yield=getattr(metrics, "free_cash_flow_yield", None),
            pe_ratio=getattr(metrics, "pe_ratio", None)
        )
        # For mismatch_score we need sentiment, beta, IV - use finbert_sentiment as approximation
        mismatch_score_val = calculate_mismatch_score(
            sentiment_score=finbert_sentiment,
            quality_score=quality_score_val,
            beta=beta_val,
            iv_atm=getattr(options, "implied_volatility_atm", None) if options else None,
            hist_vol=getattr(options, "historical_volatility", None) if options else None
        )
    
    # Get free_cash_flow_yield
    fcf_yield_val = None
    if metrics and hasattr(metrics, "free_cash_flow_yield"):
        fcf_yield_val = getattr(metrics, "free_cash_flow_yield", None)
    elif yf_fundamentals and yf_fundamentals.get("fcf_yield"):
        fcf_yield_val = yf_fundamentals["fcf_yield"]
    
    # sentiment_score_7d - use finbert_sentiment as approximation
    sentiment_7d_val = finbert_sentiment
    
    # is_contrarian_setup
    is_contrarian_val = "Ja" if (finbert_sentiment < -0.3 and beta_val and beta_val > 1.2) else "Nein"

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
        .replace("{{options_metrics}}", f"PCR: {getattr(options, 'put_call_ratio_oi', 'N/A')} | IV ATM: {(getattr(options, 'implied_volatility_atm', 0) or 0) * 100:.1f}%" if options else "N/A") \
        .replace("{{social_sentiment}}", f"Score: {getattr(social, 'social_score', 'N/A')} (Reddit: {getattr(social, 'reddit_mentions', 'N/A')}, Twitter: {getattr(social, 'twitter_mentions', 'N/A')})" if social else "N/A") \
        .replace("{{news_bullet_points}}", news_str) \
        .replace("{{long_term_memory}}", lt_memory) \
        .replace(
            "{{web_intelligence}}",
            web_intelligence or "Keine Web-Intelligence verfügbar."
        ) \
        .replace("{{opportunity_score}}", str(opp_score.total_score if opp_score else 0.0)) \
        .replace("{{torpedo_score}}", str(torp_score.total_score if torp_score else 0.0)) \
        .replace(
            "{{iv_atm}}",
            f"{(getattr(options, 'implied_volatility_atm', 0) or 0) * 100:.1f}"
            if options else "N/A"
        ) \
        .replace(
            "{{hist_vol_20d}}",
            f"{(getattr(options, 'historical_volatility', 0) or 0) * 100:.1f}"
            if options else "N/A"
        ) \
        .replace(
            "{{iv_spread}}",
            f"{((getattr(options, 'implied_volatility_atm', 0) or 0) - (getattr(options, 'historical_volatility', 0) or 0)) * 100:.1f}"
            if options else "N/A"
        ) \
        .replace(
            "{{put_call_ratio}}",
            str(getattr(options, 'put_call_ratio_oi', 'N/A'))
            if options else "N/A"
        ) \
        .replace(
            "{{expected_move}}",
            f"±{expected_move_pct}% (±${expected_move_usd})"
            if expected_move_pct and expected_move_usd
            else "N/A (keine IV-Daten)"
        ) \
        .replace(
            "{{price_change_30d}}",
            f"{'+' if (price_change_30d or 0) >= 0 else ''}"
            f"{price_change_30d}%"
            if price_change_30d is not None
            else "N/A"
        ) \
        .replace(
            "{{finbert_sentiment}}",
            f"{finbert_sentiment:+.2f}"
        ) \
        .replace(
            "{{web_sentiment}}",
            f"{web_sentiment_score:+.2f}"
        ) \
        .replace(
            "{{web_sentiment_label}}",
            web_sentiment_label
        ) \
        .replace(
            "{{social_score}}",
            f"{social_score_raw:+.2f}"
        ) \
        .replace(
            "{{composite_sentiment}}",
            f"{composite_sentiment:+.2f}"
        ) \
        .replace(
            "{{divergence_warning}}",
            divergence_text if divergence_text else "Keine Divergenz erkannt"
        ) \
        .replace("{{beta}}", str(beta_val) if beta_val else "N/A") \
        .replace("{{quality_score}}", f"{quality_score_val:.1f}" if quality_score_val else "N/A") \
        .replace("{{mismatch_score}}", f"{mismatch_score_val:.0f}" if mismatch_score_val else "N/A") \
        .replace("{{free_cash_flow_yield}}", f"{fcf_yield_val:.2f}%" if fcf_yield_val else "N/A") \
        .replace("{{sentiment_score_7d}}", f"{sentiment_7d_val:+.2f}") \
        .replace("{{is_contrarian_setup}}", is_contrarian_val) \
        .replace("{{debt_to_equity}}", str(getattr(metrics, "debt_to_equity", "N/A")) if metrics else "N/A") \
        .replace("{{current_ratio}}", str(getattr(metrics, "current_ratio", "N/A")) if metrics else "N/A") \
        .replace("{{relative_strength}}", rel_str) \
        .replace("{{chart_analysis}}", chart_str)
    
    # Max Pain (aus options_oi wenn verfügbar)
    max_pain_val = "N/A"
    try:
        from backend.app.data.yfinance_data import (
            get_options_oi_analysis
        )
        oi_data = await get_options_oi_analysis(ticker)
        if oi_data and oi_data.get("nearest_max_pain"):
            max_pain_val = f"${oi_data['nearest_max_pain']:.2f}"
            # PCR aus erstem Expiry
            exp = next(
                (e for e in oi_data.get("expirations", [])
                 if not e.get("error")), {}
            )
            pcr_oi_val = (
                f"{exp['pcr_oi']:.2f}"
                if exp.get("pcr_oi") else "N/A"
            )
        else:
            pcr_oi_val = "N/A"
    except Exception:
        pcr_oi_val = "N/A"

    # Squeeze-Signal aus FINRA + Short Interest
    squeeze_val = "N/A"
    try:
        from backend.app.data.finra import (
            get_squeeze_signal
        )
        si_pct = getattr(short_interest, "short_interest_pct", None)
        squeeze = await get_squeeze_signal(ticker, si_pct)
        squeeze_val = squeeze.get("signal", "N/A")
        finra_ratio_val = (
            f"{squeeze.get('short_volume_ratio', 0):.1%}"
            if squeeze.get("short_volume_ratio") else "N/A"
        )
    except Exception:
        finra_ratio_val = "N/A"

    # Firmenprofil (CEO, Mitarbeiter, Peers)
    ceo_val       = "N/A"
    employees_val = "N/A"
    peers_val     = "N/A"
    try:
        if profile:
            ceo_val       = getattr(profile, "ceo", None) or "N/A"
            emp           = getattr(profile, "fullTimeEmployees", None)
            employees_val = (
                f"{int(emp):,}" if emp else "N/A"
            )
            raw_peers     = getattr(profile, "peers", []) or []
            peers_val     = ", ".join(
                str(p).upper() for p in raw_peers[:5]
            ) if raw_peers else "N/A"
    except Exception:
        pass

    user_prompt = user_prompt \
        .replace("{{max_pain}}", max_pain_val) \
        .replace("{{pcr_oi}}", pcr_oi_val) \
        .replace("{{squeeze_signal}}", squeeze_val) \
        .replace("{{finra_short_ratio}}", finra_ratio_val) \
        .replace("{{ceo}}", ceo_val) \
        .replace("{{employees}}", employees_val) \
        .replace("{{peers}}", peers_val)
    
    # Sicherheitsnetz: alle verbleibenden unfilled Placeholders mit N/A ersetzen
    import re
    user_prompt = re.sub(r"\{\{[^}]+\}\}", "N/A", user_prompt)
    
    # Makro-Warnung in den Report-Kontext einbauen
    macro_gate_note = ""
    if rec and getattr(rec, "macro_warning", None):
        macro_gate_note = (
            f"\n\n⚠️ MAKRO-REGIME-GATE AKTIV:\n{rec.macro_warning}\n"
            f"Die Empfehlung wurde automatisch angepasst. "
            f"Erkläre dem Trader warum das Makro-Umfeld trotz "
            f"starker Fundamentaldaten eine Absicherung erfordert.\n"
        )
        user_prompt = user_prompt + macro_gate_note
        
    result = await call_deepseek(sys_prompt, user_prompt, model="deepseek-reasoner")
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
            # Versuche das Earnings-Datum aus Estimates zu holen
            e_date = getattr(estimates, "report_date", None) if estimates else None
            if not e_date or e_date == "Unknown":
                e_date = datetime.now().strftime("%Y-%m-%d")  # Fallback
            elif hasattr(e_date, "strftime"):
                e_date = e_date.strftime("%Y-%m-%d")

            await db.table("audit_reports").insert({
                "ticker": ticker,
                "report_type": "audit",
                "report_date": datetime.now().strftime("%Y-%m-%d"),
                "earnings_date": str(e_date),
                "recommendation": rec.recommendation if rec else "unknown",
                "opportunity_score": opp_score.total_score if opp_score else 0,
                "torpedo_score": torp_score.total_score if torp_score else 0,
                "report_text": mock_response,   # ← NEU
                "prompt_version": "0.4",       # ← NEU
                "created_at": datetime.now().isoformat()
            }).execute_async()
            logger.info(f"Audit-Report für {ticker} in Supabase gespeichert")
            
            # Decision Snapshot für Learning-Modul erstellen
            try:
                # Tage bis Earnings berechnen (für trade_type)
                earnings_countdown = None
                if estimates and hasattr(estimates, 'report_date') and estimates.report_date:
                    try:
                        from datetime import date as date_type
                        earnings_date = (
                            estimates.report_date if hasattr(estimates.report_date, "toordinal")
                            else date_type.fromisoformat(str(estimates.report_date))
                        )
                        earnings_countdown = (earnings_date - date_type.today()).days
                    except Exception:
                        pass

                await _save_decision_snapshot(
                    ticker=ticker,
                    opportunity_score=opp_score.total_score if opp_score else 0,
                    torpedo_score=torp_score.total_score if torp_score else 0,
                    recommendation=rec.recommendation if rec else "unknown",
                    prompt_text=user_prompt[:8000],  # auf 8000 Zeichen kappen
                    report_text=mock_response,
                    raw_data={
                        "valuation": valuation_ctx,
                        "technicals": _model_to_dict(technicals),
                        "short_interest": _model_to_dict(short_interest),
                        "insiders": _model_to_dict(insiders),
                        "options": _model_to_dict(options),
                        "earnings_history": _model_to_dict(history),
                        "news_memory": news_memory if news_memory else [],
                        "social": _model_to_dict(social),
                        "macro": _model_to_dict(macro),
                        "chart_analysis": chart_data,
                        "relative_strength": {
                            "spy_1d_pct": spy.get("change_1d_pct"),
                            "spy_5d_pct": spy.get("change_5d_pct"),
                            "spy_1m_pct": spy.get("change_1m_pct"),
                            "sector_etf_5d_pct": sector_etf.get("change_5d_pct"),
                            "sector_etf_1m_pct": sector_etf.get("change_1m_pct"),
                            "ticker_1d_pct": ticker_1d_pct,
                            "ticker_5d_pct": ticker_5d,
                            "ticker_1m_pct": ticker_1m,
                        },
                        "expected_move": {
                            "pct": expected_move_pct,
                            "usd": expected_move_usd,
                        },
                        "price_change_30d": price_change_30d,
                        "fear_greed": fear_greed_data,
                        "reddit_sentiment": reddit_data,
                        "earnings_countdown": earnings_countdown,
                    },
                    earnings_countdown=earnings_countdown,
                )
            except Exception as snap_err:
                logger.error(f"Decision Snapshot für {ticker} konnte nicht gespeichert werden: {snap_err}")
                logger.error(f"Snapshot Details - Opp: {opp_score.total_score if opp_score else 0}, Torp: {torp_score.total_score if torp_score else 0}, Rec: {rec.recommendation if rec else 'unknown'}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Redis Cache für Research invalidieren
            try:
                from backend.app.cache import cache_invalidate
                await cache_invalidate(f"research:{ticker.upper()}")
                await cache_invalidate(f"research:{ticker.upper()}:v2")
                logger.info(f"Research Cache für {ticker} invalidiert")
            except Exception:
                pass
            # WICHTIG: Kein automatischer Shadow-Trade mehr aus einem Research/Report-Run.
            # Die Trade-Entscheidung wird manuell über den Review-Button ausgelöst.
            # Die finale Entscheidungsgrundlage liegt bereits im decision_snapshots-Record.
    except Exception as e:
        logger.debug(f"Audit-Report DB-Speicher: {e}")

    # Score-History speichern für Delta-Tracking
    try:
        from datetime import date as date_type
        from backend.app.db import get_supabase_client

        db = get_supabase_client()
        if db:
            await db.table("score_history").upsert({
                "ticker": ticker,
                "date": date_type.today().isoformat(),
                "opportunity_score": opp_score.total_score if opp_score else None,
                "torpedo_score": torp_score.total_score if torp_score else None,
                "price": getattr(technicals, "current_price", None) if technicals else None,
                "rsi": getattr(technicals, "rsi_14", None) if technicals else None,
                "trend": getattr(technicals, "trend", None) if technicals else None,
            }, on_conflict="ticker,date").execute_async()
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
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        recent = [b for b in bullets if b.get("date", "") >= cutoff]
        for b in recent:
            bp_text = " | ".join(b["bullet_points"]) if isinstance(b.get("bullet_points"), list) else str(b.get("bullet_points", ""))
            ticker_bullets.append(f"[{ticker}] ({b.get('category', 'general')}) {bp_text}")

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
    """Wöchentlicher Audit-Report nur für Watchlist-Ticker."""
    logger.info(f"Sunday Audit Report: {len(tickers)} Ticker: {tickers}")

    if not tickers:
        logger.warning("Keine Ticker für Audit-Reports.")
        return "# KAFIN SUNDAY REPORT / SONNTAGS-AUDIT\n\nKeine Ticker in der Watchlist."

    performance_summary = ""
    try:
        db = get_supabase_client()
        if db:
            perf = await db.table("performance_tracking").select("*").order("period", desc=True).limit(1).execute_async()
            if perf.data:
                p = perf.data[0]
                accuracy = p.get("accuracy_percent", 0)
                total = p.get("total_predictions", 0)
                performance_summary = f"Bisherige Trefferquote: {accuracy:.0f}% ({total} Reviews)"
    except Exception as exc:
        logger.debug(f"Performance Summary nicht verfügbar: {exc}")

    async def _safe_audit(t: str) -> str:
        async with _DEEPSEEK_SEMAPHORE:
            try:
                return await generate_audit_report(t)
            except Exception as e:
                logger.error(f"Audit-Report für {t} fehlgeschlagen: {e}")
                return f"## {t}\n\nReport-Generierung fehlgeschlagen: {str(e)}"

    reports = await asyncio.gather(*[_safe_audit(t) for t in tickers])
    reports = list(reports)

    full_report = "# KAFIN SUNDAY REPORT / SONNTAGS-AUDIT\n\n"
    if performance_summary:
        full_report += f"📊 {performance_summary}\n\n---\n\n"
    full_report += "## AUDIT-REPORTS\n\n"
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

    wl = await get_watchlist()
    wl_tickers = [item["ticker"] for item in wl]

    # 3b. Google News (Politik, Geopolitik, Watchlist-spezifisch)
    google_news_str = "Keine Google News verfügbar."
    try:
        from backend.app.data.google_news import scan_google_news

        wl_items = [
            {"ticker": item.get("ticker", ""), "company_name": item.get("company_name", "")}
            for item in wl
        ]
        google_results = await scan_google_news(wl_items)

        if google_results:
            by_category = {}
            for gn in google_results[:20]:
                cat = gn.get("category", "general")
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(f"[{gn.get('source', '??')}] {gn['headline']}")

            lines = []
            for cat, items in by_category.items():
                lines.append(f"--- {cat.upper()} ---")
                for item in items[:5]:
                    lines.append(f"  - {item}")
            google_news_str = "\n".join(lines)
    except Exception as e:
        logger.debug(f"Google News für Morning Briefing: {e}")

    # 4. Watchlist-News aus dem Gedächtnis (letzte 24h)
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
    from backend.app.data.fmp import get_analyst_grades, get_price_target_consensus, get_analyst_estimates

    analyst_lines = []
    cutoff_7d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    for ticker in wl_tickers[:10]:
        try:
            grades = await get_analyst_grades(ticker) or []
            pt = await get_price_target_consensus(ticker)
            estimates = await get_analyst_estimates(ticker)

            yf_fundamentals = None
            if not grades or not pt or not estimates:
                try:
                    yf_fundamentals = await get_fundamentals_yf(ticker)
                except Exception as e:
                    logger.debug(f"yfinance Fundamentals für {ticker}: {e}")

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
            elif yf_fundamentals and yf_fundamentals.get("analyst_target"):
                rec = yf_fundamentals.get("analyst_recommendation") or "unknown"
                n_analysts = yf_fundamentals.get("number_of_analysts") or "n/a"
                analyst_lines.append(
                    f"[{ticker}] yfinance PT-Fallback: ${float(yf_fundamentals['analyst_target']):.0f} "
                    f"({rec}, {n_analysts} Analysts)"
                )

            if estimates:
                eps_est = getattr(estimates, "eps_consensus", None)
                rev_est = getattr(estimates, "revenue_consensus", None)
                report_date = getattr(estimates, "report_date", None)
                if eps_est is not None or rev_est is not None:
                    pieces = []
                    if eps_est is not None:
                        pieces.append(f"EPS ${eps_est:.2f}")
                    if rev_est is not None:
                        pieces.append(f"Revenue ${float(rev_est):,.0f}")
                    suffix = f" am {report_date}" if report_date else ""
                    analyst_lines.append(f"[{ticker}] Analysten-Schätzung{suffix}: " + " | ".join(pieces))

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

    # Fear & Greed für Morning Briefing
    fg_score_mb  = "N/A"
    fg_label_mb  = "N/A"
    try:
        from backend.app.data.fear_greed import (
            get_fear_greed_score
        )
        fg_mb = await get_fear_greed_score()
        fg_score_mb = str(round(fg_mb.get("score", 50)))
        fg_label_mb = fg_mb.get("label", "N/A")
    except Exception:
        pass

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

    # Contrarian-Setups laden (falls vorhanden) - inline um Circular Import zu vermeiden
    contrarian_str = "Keine Contrarian-Opportunities gefunden."
    try:
        from backend.app.memory.short_term import get_bullet_points as get_memory_for_ticker
        from backend.app.data.yfinance_data import get_risk_metrics
        from backend.app.data.fmp import get_key_metrics
        from backend.app.data.yfinance_data import get_atm_implied_volatility
        from backend.app.analysis.scoring import calculate_quality_score, calculate_mismatch_score
        
        opportunities = []
        for item in wl[:5]:  # Nur Top 5 prüfen für Performance
            ticker = item.get("ticker")
            try:
                news_memory = await get_memory_for_ticker(ticker)
                if not news_memory:
                    continue
                recent_bullets = news_memory[:7]
                sentiment_scores = [b.get("sentiment_score", 0) for b in recent_bullets if b.get("sentiment_score") is not None]
                if not sentiment_scores:
                    continue
                avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
                if avg_sentiment >= -0.5:
                    continue
                risk_data = await get_risk_metrics(ticker)
                beta = risk_data.get("beta")
                if beta is None or beta < 1.2:
                    continue
                key_metrics = await get_key_metrics(ticker)
                if not key_metrics:
                    continue
                quality_score = calculate_quality_score(
                    debt_to_equity=key_metrics.debt_to_equity,
                    current_ratio=key_metrics.current_ratio,
                    free_cash_flow_yield=key_metrics.free_cash_flow_yield,
                    pe_ratio=key_metrics.pe_ratio
                )
                if quality_score < 6.0:
                    continue
                options_data = await get_atm_implied_volatility(ticker)
                iv_atm = options_data.implied_volatility_atm if options_data else None
                hist_vol = options_data.historical_volatility if options_data else None
                mismatch_score = calculate_mismatch_score(
                    sentiment_score=avg_sentiment,
                    quality_score=quality_score,
                    beta=beta,
                    iv_atm=iv_atm,
                    hist_vol=hist_vol
                )
                if mismatch_score < 50.0:
                    continue
                material_count = sum(1 for b in recent_bullets if b.get("is_material", False))
                opportunities.append({
                    "ticker": ticker,
                    "mismatch_score": mismatch_score,
                    "sentiment_7d": round(avg_sentiment, 2),
                    "quality_score": quality_score,
                    "beta": beta,
                    "material_news_count": material_count,
                })
            except Exception:
                continue
        
        if opportunities:
            opportunities.sort(key=lambda x: x["mismatch_score"], reverse=True)
            contrarian_lines = []
            for opp in opportunities[:3]:
                contrarian_lines.append(
                    f"• {opp['ticker']} — Mismatch: {opp['mismatch_score']:.0f}/100 | "
                    f"Beta: {opp['beta']:.1f} | Quality: {opp['quality_score']:.1f}/10 | "
                    f"Sentiment 7T: {opp['sentiment_7d']:.2f} ({opp['material_news_count']} Material Events)"
                )
            contrarian_str = "\n".join(contrarian_lines)
    except Exception as e:
        logger.debug(f"Contrarian-Opportunities nicht verfügbar: {e}")

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
        .replace("{{fear_greed_score}}", fg_score_mb) \
        .replace("{{fear_greed_label}}", fg_label_mb) \
        .replace("{{analyst_ratings}}", analyst_str) \
        .replace("{{general_news}}", general_news_str) \
        .replace("{{watchlist_news}}", watchlist_news_str) \
        .replace("{{google_news}}", google_news_str) \
        .replace("{{macro_events}}", macro_events_str) \
        .replace("{{todays_events}}", todays_events_str) \
        .replace("{{yesterday_snapshot}}", yesterday_str) \
        .replace("{{contrarian_setups}}", contrarian_str)

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

        # Breadth-Daten für Snapshot sammeln
        breadth = None
        try:
            from backend.app.data.market_overview import get_market_breadth
            breadth = await get_market_breadth()
        except Exception as e:
            logger.debug(f"Breadth für Snapshot nicht geladen: {e}")

        await save_daily_snapshot(market, macro, regime, breadth_data=breadth, briefing_summary=result)
    except Exception as e:
        logger.warning(f"Snapshot-Speicherung fehlgeschlagen: {e}")

    return result


async def generate_after_market_report() -> str:
    """
    After-Market Report — täglich 22:15 CET.
    Vollständiges Tagesbild nach US-Markt-Schluss.
    Nutzt DeepSeek Chat (nicht Reasoner — strukturierter Bericht,
    kein offenes Reasoning nötig).
    """
    from backend.app.data.market_overview import get_market_overview, get_yesterday_snapshot, save_daily_snapshot
    from backend.app.data.fred import get_macro_snapshot
    from backend.app.memory.short_term import get_bullet_points
    from backend.app.memory.watchlist import get_watchlist
    from backend.app.database import get_pool
    from datetime import timedelta

    logger.info("Generiere After-Market Report…")

    # 1. Marktdaten
    market  = await get_market_overview()
    macro   = await get_macro_snapshot()
    wl      = await get_watchlist()
    wl_tickers = [item["ticker"] for item in wl]

    # 2. Earnings-Reaktionen heute aus earnings_reviews + score_history
    earnings_today: list[str] = []
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            today_str = datetime.now().strftime("%Y-%m-%d")
            rows = await conn.fetch("""
                SELECT ticker, actual_eps, consensus_eps, actual_surprise_percent,
                       stock_reaction_1d_percent, recommendation
                FROM earnings_reviews
                WHERE DATE(created_at) = $1
                ORDER BY created_at DESC
                LIMIT 10
            """, today_str)
        for r in rows:
            t = r["ticker"]
            surprise = r.get("actual_surprise_percent")
            reaction = r.get("stock_reaction_1d_percent")
            surprise_str = f"Surprise {surprise:+.1f}%" if surprise is not None else "Surprise: N/A"
            reaction_str = f"Reaktion {reaction:+.1f}%" if reaction is not None else "Reaktion: N/A"
            earnings_today.append(f"[{t}] {surprise_str} | {reaction_str}")
    except Exception as e:
        logger.warning(f"After-market earnings query: {e}")

    # 3. Score-Veränderungen heute (Ticker mit signifikanten Deltas)
    score_changes: list[str] = []
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            today_str = datetime.now().strftime("%Y-%m-%d")
            yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            rows = await conn.fetch("""
                SELECT t.ticker,
                       t.opportunity_score as opp_today,
                       t.torpedo_score as torp_today,
                       y.opportunity_score as opp_yest,
                       y.torpedo_score as torp_yest
                FROM score_history t
                LEFT JOIN score_history y ON t.ticker = y.ticker
                    AND DATE(y.date) = $2
                WHERE DATE(t.date) = $1
                  AND (
                    ABS(COALESCE(t.opportunity_score,0) - COALESCE(y.opportunity_score,0)) >= 1.0
                    OR
                    ABS(COALESCE(t.torpedo_score,0) - COALESCE(y.torpedo_score,0)) >= 1.0
                  )
                ORDER BY ABS(COALESCE(t.torpedo_score,0) - COALESCE(y.torpedo_score,0)) DESC
                LIMIT 8
            """, today_str, yesterday_str)
        for r in rows:
            t = r["ticker"]
            opp_d = (r["opp_today"] or 0) - (r["opp_yest"] or 0)
            torp_d = (r["torp_today"] or 0) - (r["torp_yest"] or 0)
            score_changes.append(
                f"[{t}] Opp {opp_d:+.1f} | Torpedo {torp_d:+.1f}"
            )
    except Exception as e:
        logger.warning(f"After-market score query: {e}")

    # 4. Neue Material Events heute
    material_today: list[str] = []
    try:
        cutoff = (datetime.now() - timedelta(hours=10)).isoformat()
        bullets = await get_bullet_points("GENERAL_MACRO")
        for b in bullets:
            if b.get("date", "") >= cutoff and b.get("is_material"):
                bp_text = " | ".join(b["bullet_points"]) if isinstance(b.get("bullet_points"), list) else str(b.get("bullet_points", ""))
                material_today.append(bp_text[:120])
    except Exception:
        pass

    # 5. Offene Journal-Positionen
    open_pos_lines: list[str] = []
    try:
        from backend.app.database import get_pool as _get_pool
        _pool = await _get_pool()
        async with _pool.acquire() as _conn:
            _rows = await _conn.fetch("""
                SELECT ticker, direction, entry_price, shares,
                       stop_price, target_price, entry_date
                FROM trade_journal
                WHERE exit_date IS NULL
                ORDER BY entry_date DESC
                LIMIT 10
            """)
        for r in _rows:
            t  = r["ticker"]
            d  = r["direction"].upper()
            ep = r.get("entry_price") or 0
            sh = r.get("shares") or 0
            st = r.get("stop_price")
            tg = r.get("target_price")
            capital = round(ep * sh, 0)
            line = f"[{t}] {d} | Entry ${ep:.2f} × {sh} Shares (${capital:,.0f})"
            if st:
                line += f" | Stop ${st:.2f}"
            if tg:
                line += f" | Ziel ${tg:.2f}"
            open_pos_lines.append(line)
    except Exception as e:
        logger.warning(f"After-market open positions: {e}")

    # 6. Morgen im Fokus — Earnings der nächsten 2 Tage
    upcoming: list[str] = []
    try:
        from backend.app.data.finnhub import get_earnings_calendar
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        cal = await get_earnings_calendar(tomorrow, day_after)
        for event in (cal or [])[:6]:
            t_sym = getattr(event, "ticker", getattr(event, "symbol", "?"))
            if t_sym.upper() in [x.upper() for x in wl_tickers]:
                upcoming.append(f"[WATCHLIST] {t_sym}: {getattr(event, 'date', '?')}")
            else:
                upcoming.append(f"{t_sym}: {getattr(event, 'date', '?')}")
    except Exception:
        pass

    # Markt-Zusammenfassung aufbauen
    indices_str = ""
    if market and hasattr(market, "get"):
        idxs = market.get("indices", {})
        for sym, data in list(idxs.items())[:4]:
            p = data.get("price")
            c = data.get("change_1d_pct")
            indices_str += f"{sym}: ${p:.2f} ({c:+.2f}%)\n" if p and c else f"{sym}: N/A\n"

    # Makro-String
    macro = _model_to_dict(macro)
    macro_str = (
        f"VIX: {macro.get('vix','?')} | "
        f"Credit Spread: {macro.get('credit_spread_bps','?')}bp | "
        f"Yield Curve: {macro.get('yield_curve_10y_2y','?')}% | "
        f"DXY: {macro.get('dxy','?')} | "
        f"Fed Rate: {macro.get('fed_rate','?')}%"
    ) if macro else "Makro-Daten nicht verfügbar."

    # ── Prompt ──────────────────────────────────────────────────
    SYSTEM = """Du bist ein Senior-Marktanalyst bei einem Hedge Fund. Es ist 22:15 CET —
der US-Markt hat soeben geschlossen. Du erstellst das tägliche After-Market Briefing
auf Deutsch für den Portfolio Manager.

STRUKTUR (exakt einhalten, 5 Blöcke):

MARKTSCHLUSS: [Regime] — [1 Satz was heute dominiert hat]
• [Index-Zusammenfassung: was war die Hauptbewegung, was war der Grund?]
• [Divergenzen: Growth vs Value? Small vs Large Cap?]

EARNINGS-REAKTIONEN:
[Falls Watchlist-Titel gemeldet haben: Reaktion vs. Expected Move — war es besser/schlechter als erwartet?]
[Falls keine: "Keine Watchlist-Earnings heute."]

SCORE-VERÄNDERUNGEN:
[Welche Ticker haben heute signifikante Opp/Torpedo-Shifts erlebt? Was treibt das?]
[Falls keine: "Keine signifikanten Score-Veränderungen."]

MORGEN IM FOKUS:
[Welche Earnings/Events morgen? Welches Watchlist-Setup ist für morgen am attraktivsten?]
[Konkrete Tickers nennen, nicht abstrakt.]

HANDLUNGSEMPFEHLUNG:
[Eine konkrete Empfehlung für morgen. Was vorbereiten? Was vermeiden?]
[KEINE breiten Index-Shorts. Sektor-ETF-Puts, Einzeltitel, Pair-Trades wenn bärisch.]

OFFENE POSITIONEN — falls vorhanden:
Prüfe explizit ob die heutigen Marktentwicklungen die offenen Positionen
betreffen. Stop anpassen? Position schließen? Trailing Stop sinnvoll?
Nenne konkrete Ticker und konkrete Preislevels.

ABSOLUT REGELN:
- Maximal 40 Zeilen. Kein Fülltext.
- Jede Zeile: Information oder Einordnung.
- Sprache: Deutsch. Ton: direkt, kein Hedging."""

    USER = f"""DATUM: {datetime.now().strftime('%d.%m.%Y')}

MARKTDATEN (US-Schluss):
{indices_str}

MAKRO:
{macro_str}

EARNINGS HEUTE (aus DB):
{chr(10).join(earnings_today) if earnings_today else 'Keine Earnings-Daten heute.'}

OFFENE POSITIONEN ({len(open_pos_lines)} Trades):
{chr(10).join(open_pos_lines) if open_pos_lines else 'Keine offenen Positionen.'}

EARNINGS MORGEN/ÜBERMORGEN:
{chr(10).join(upcoming) if upcoming else 'Keine bekannten Earnings.'}

Erstelle das After-Market Briefing."""

    result = await call_deepseek(
        system_prompt=SYSTEM,
        user_prompt=USER,
        model="deepseek-chat",
        temperature=0.3,
        max_tokens=1800,
    )

    # In DB speichern (neues Feld in daily_snapshots)
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            today_str = datetime.now().strftime("%Y-%m-%d")
            await conn.execute("""
                UPDATE daily_snapshots
                SET after_market_summary = $1
                WHERE date = $2
            """, result, today_str)
    except Exception as e:
        logger.warning(f"After-market save error: {e}")

    return result


async def generate_session_plan() -> str:
    """
    Täglicher Session-Plan — max 3 aktionierbare Setups.
    DeepSeek Reasoner: Watchlist-Scores + Chart-Levels + Signal Feed.
    Täglich 08:05 CET nach dem Pre-Market Briefing.
    """
    from backend.app.memory.watchlist import get_watchlist
    from backend.app.data.fred import get_macro_snapshot
    from backend.app.cache import cache_get
    from backend.app.analysis.chart_analyst import analyze_chart
    from backend.app.db import get_supabase_client

    logger.info("Generiere Session Plan...")

    wl = await get_watchlist()
    wl_tickers = [item["ticker"] for item in wl]

    macro: dict = {}
    try:
        m = await get_macro_snapshot()
        macro = _model_to_dict(m)
    except Exception:
        pass

    # Aktive Signale aus Cache (P1+P2 nur)
    active_signals: list[dict] = []
    try:
        feed = await cache_get("signals:feed")
        if feed:
            active_signals = [s for s in (feed.get("signals") or [])
                              if s.get("priority") in [1, 2]][:8]
    except Exception:
        pass

    # Top-Kandidaten: Opp>=6, Torpedo<=5, max 5 Ticker
    scored: list[dict] = []
    db = get_supabase_client()
    if db:
        try:
            rows = (await db.table("score_history")
                    .select("ticker,opportunity_score,torpedo_score")
                    .in_("ticker", wl_tickers)
                    .order("date", desc=True)
                    .limit(len(wl_tickers) * 2)
                    .execute_async()).data or []
            seen: set = set()
            for row in rows:
                t = row.get("ticker", "").upper()
                if t in seen:
                    continue
                seen.add(t)
                opp  = row.get("opportunity_score") or 0
                torp = row.get("torpedo_score") or 10
                if opp >= 6 and torp <= 5:
                    scored.append({"ticker": t, "opp": opp, "torp": torp})
            scored.sort(key=lambda x: x["opp"] - x["torp"], reverse=True)
            scored = scored[:5]
        except Exception as e:
            logger.warning(f"Session plan scores: {e}")

    # Chart-Levels parallel laden
    chart_levels: dict[str, dict] = {}
    if scored:
        async def _get_lvl(t: str):
            try:
                return t, await analyze_chart(t)
            except Exception:
                return t, {}
        results = await asyncio.gather(*[_get_lvl(x["ticker"]) for x in scored])
        for t, lv in results:
            if lv and not lv.get("error"):
                chart_levels[t] = lv

    macro_str = (
        f"Regime: {macro.get('regime','?')} | VIX: {macro.get('vix','?')} | "
        f"Fed: {macro.get('fed_rate','?')}% | "
        f"Credit: {macro.get('credit_spread_bps','?')}bp"
    )

    setup_lines: list[str] = []
    for s in scored:
        t   = s["ticker"]
        lv  = chart_levels.get(t, {})
        ez  = lv.get("entry_zone") or {}
        sl  = lv.get("stop_loss")
        t1  = lv.get("target_1")
        t2  = lv.get("target_2")
        bias = lv.get("bias", "neutral")
        line = (
            f"{t}: Opp={s['opp']:.1f} Torp={s['torp']:.1f} Bias={bias}"
            + (f" | Entry ${ez.get('low',0):.2f}-${ez.get('high',0):.2f}" if ez else "")
            + (f" | Stop ${sl:.2f}" if sl else "")
            + (f" | T1 ${t1:.2f}" if t1 else "")
            + (f" | T2 ${t2:.2f}" if t2 else "")
        )
        setup_lines.append(line)

    sig_lines = [
        f"[P{s.get('priority')}] {s.get('ticker')}: {s.get('headline','')}"
        for s in active_signals
    ]

    today = datetime.now().strftime("%d.%m.%Y")
    SYSTEM = f"""Du bist Head-of-Trading. Es ist 08:05 CET.
Erstelle den Session-Plan für heute — exakt 3 aktionierbare Setups.
Makro: {macro_str}

FORMAT (exakt einhalten, max 25 Zeilen):

SESSION PLAN {today}

SETUP 1: [TICKER] — [5 Wörter Empfehlung]
Thesis: [1 Satz]
Entry: $X.XX–$X.XX | Stop: $X.XX | Ziel 1: $X.XX | Ziel 2: $X.XX
R:R: 1:X | Katalysator: [Was macht heute den Unterschied?]

SETUP 2: [TICKER] — [Empfehlung]
[gleiche Struktur]

SETUP 3: [TICKER] — [Empfehlung]
[gleiche Struktur]

HEUTE MEIDEN: [Ticker] — [1-Satz Begründung]

REGEL: Niemals SH/PSQ/SQQQ. Bei bärisch: Sektor-ETF-Puts oder Pair-Trades."""

    USER = (
        f"SETUPS ({len(setup_lines)} Kandidaten):\n"
        + ("\n".join(setup_lines) if setup_lines else "Keine qualifizierten Setups.")
        + f"\n\nAKTIVE SIGNALE:\n"
        + ("\n".join(sig_lines) if sig_lines else "Keine aktiven Signale.")
        + "\n\nSession Plan:"
    )

    result = await call_deepseek(SYSTEM, USER, model="deepseek-reasoner", max_tokens=1000)

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            today_str = datetime.now().strftime("%Y-%m-%d")
            await conn.execute("""
                INSERT INTO daily_snapshots (date, session_plan, session_plan_generated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (date) DO UPDATE
                SET session_plan = $2,
                    session_plan_generated_at = NOW()
            """, today_str, result)
    except Exception as e:
        logger.warning(f"Session plan save: {e}")

    return result


async def generate_btc_report() -> str:
    """
    Bitcoin-Lagebericht — DeepSeek Chat.
    Ersetzt den BTC-Teil des früheren Sunday Reports.
    Wird im After-Market Briefing als eigener Block gezeigt.
    """
    from backend.app.data.coinglass import get_full_btc_snapshot

    logger.info("Generiere BTC Report...")

    snapshot = await get_full_btc_snapshot()
    price_d  = snapshot.get("price") or {}
    oi_d     = snapshot.get("open_interest") or {}
    fund_d   = snapshot.get("funding_rate") or {}
    ls_d     = snapshot.get("long_short") or {}
    liq_d    = snapshot.get("liquidations") or {}
    dxy      = snapshot.get("dxy")

    def _fmt_currency(value) -> str:
        try:
            if value is None or value == "N/A":
                return "N/A"
            return f"${float(value):,.0f}"
        except Exception:
            return "N/A"

    def _fmt_pct(value, digits: int = 2, signed: bool = True) -> str:
        try:
            if value is None or value == "N/A":
                return "N/A"
            value = float(value)
            prefix = "+" if signed and value > 0 else ""
            return f"{prefix}{value:.{digits}f}%"
        except Exception:
            return "N/A"

    SYSTEM = """Du bist Bitcoin-Derivate-Analyst.
Erstelle einen präzisen BTC-Lagebericht in max 20 Zeilen.

FORMAT:
BTC LAGEBERICHT [Datum]

KURS & TREND: [Kurs, 7T-Trend, Interpretation]
OPEN INTEREST: [OI in Mrd $, Veränderung 24h, was bedeutet das?]
FUNDING RATE: [Rate, Interpretation — wer zahlt?]
LONG/SHORT RATIO: [Retail-Sentiment — bullish oder bearish?]
LIQUIDATIONSCLUSTER: [nächste wichtige Levels falls verfügbar]
DXY-KORRELATION: [DXY steigend = BTC Gegenwind / fallend = Rückenwind]

EINSCHÄTZUNG: [Long / Short / Abwarten] + konkrete Begründung
SCHLÜSSEL-LEVELS: [wichtige Support/Resistance für die nächsten 7 Tage]

REGEL: Niemals "einfach kaufen/verkaufen" — immer Level und Begründung.
Sprache: Deutsch."""

    USER = f"""BITCOIN DATEN:
Kurs: {_fmt_currency(price_d.get('price'))} | 7T: {_fmt_pct(price_d.get('change_7d_pct'), 2)} | Trend: {price_d.get('trend', 'N/A')}
14T Hoch: {_fmt_currency(price_d.get('high_14d'))} | 14T Tief: {_fmt_currency(price_d.get('low_14d'))}

Open Interest: {_fmt_currency(oi_d.get('total_oi_usd'))} | 24h: {_fmt_pct(oi_d.get('change_24h_pct'), 2)}
Funding Rate: {_fmt_pct(fund_d.get('avg_funding_rate_pct'), 4)} ({fund_d.get('interpretation', 'N/A')})
Long/Short: {ls_d.get('long_pct', 'N/A')}% Long / {ls_d.get('short_pct', 'N/A')}% Short
Liquidationscluster: {liq_d.get('note', 'Daten nicht verfügbar') if not liq_d.get('available') else 'Verfügbar'}
DXY: {dxy or 'N/A'}

BTC Lagebericht:"""

    result = await call_deepseek(SYSTEM, USER, model="deepseek-chat",
                               temperature=0.3, max_tokens=600)

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            today_str = datetime.now().strftime("%Y-%m-%d")
            await conn.execute("""
                INSERT INTO daily_snapshots (date, btc_report, btc_report_generated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (date) DO UPDATE
                SET btc_report = $2, btc_report_generated_at = NOW()
            """, today_str, result)
    except Exception as e:
        logger.warning(f"BTC report save: {e}")

    return result


def _model_to_dict(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {"value": value}


def _safe_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _rank_components(components: dict, labels: dict[str, str], limit: int = 4) -> list[dict]:
    ranked: list[dict] = []
    for key, raw_value in components.items():
        value = _safe_float(raw_value)
        if value is None:
            continue
        ranked.append(
            {
                "key": key,
                "label": labels.get(key, key.replace("_", " ").title()),
                "value": round(value, 2),
            }
        )
    ranked.sort(key=lambda item: item["value"], reverse=True)
    return ranked[:limit]


def _extract_json_object(text: str) -> dict | None:
    if not text:
        return None

    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1]).strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    candidate = stripped[start:end + 1]
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _normalize_review_recommendation(value: str | None, fallback: str) -> str:
    if not value:
        return fallback

    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    alias_map = {
        "strongbuy": "strong_buy",
        "strong_buy": "strong_buy",
        "buy": "buy_hedge",
        "buy_hedge": "buy_hedge",
        "watch": "watch",
        "hold": "hold",
        "ignore": "ignore",
        "strongshort": "strong_short",
        "strong_short": "strong_short",
        "short": "strong_short",
        "potentialshort": "potential_short",
        "potential_short": "potential_short",
    }
    return alias_map.get(normalized, fallback)


async def generate_trade_review_decision(ticker: str) -> dict:
    """
    Erstellt eine Reasoner-gestützte Trade-Review-Entscheidung für einen Ticker.
    Die Funktion sammelt den aktuellen Research-Kontext, berechnet die internen
    Scores und lässt DeepSeek Reasoner die finale Einschätzung mit Begründung
    formulieren.
    """
    ticker = ticker.upper().strip()
    if not ticker:
        raise ValueError("Ticker darf nicht leer sein.")

    logger.info(f"[TradeReview] Starte Trade-Review für {ticker}")

    profile = await get_company_profile(ticker)
    if not profile:
        try:
            yf_fundamentals = await get_fundamentals_yf(ticker)
            if yf_fundamentals:
                profile = _valuation_from_fundamentals(ticker, yf_fundamentals)
                logger.info(f"[TradeReview] Profil-Fallback via yfinance für {ticker} aktiviert")
        except Exception as exc:
            logger.debug(f"[TradeReview] Profil-Fallback via yfinance fehlgeschlagen: {exc}")
        if not profile:
            raise ValueError(f"Ticker '{ticker}' ist ungültig (kein Profil gefunden).")

    estimates = None
    try:
        estimates = await get_analyst_estimates(ticker)
    except Exception as e:
        logger.warning(f"[TradeReview] Analyst estimates für {ticker}: {e}")

    earnings_countdown = None
    if estimates is not None:
        try:
            from datetime import date as date_type
            report_date = getattr(estimates, "report_date", None)
            if report_date:
                parsed_date = report_date if hasattr(report_date, "toordinal") else date_type.fromisoformat(str(report_date))
                earnings_countdown = (parsed_date - date_type.today()).days
        except Exception as e:
            logger.debug(f"[TradeReview] Earnings countdown für {ticker}: {e}")

    audit_grades = []
    try:
        from backend.app.data.fmp import get_analyst_grades
        audit_grades = await get_analyst_grades(ticker)
    except Exception as e:
        logger.warning(f"[TradeReview] Analyst grades für {ticker}: {e}")

    history = None
    try:
        history = await get_earnings_history(ticker)
    except Exception as e:
        logger.warning(f"[TradeReview] Earnings history für {ticker}: {e}")

    metrics = None
    try:
        metrics = await get_key_metrics(ticker)
    except Exception as e:
        logger.warning(f"[TradeReview] Key metrics für {ticker}: {e}")

    if not metrics or not getattr(metrics, "pe_ratio", None):
        try:
            yf_fundamentals = await get_fundamentals_yf(ticker)
        except Exception as e:
            logger.warning(f"[TradeReview] yfinance Fundamentals für {ticker}: {e}")
            yf_fundamentals = None
    else:
        yf_fundamentals = None

    short_interest = None
    try:
        short_interest = await get_short_interest(ticker)
    except Exception as e:
        logger.warning(f"[TradeReview] Short interest für {ticker}: {e}")

    if short_interest is None:
        try:
            from backend.app.data.yfinance_data import get_short_interest_yf
            yf_si = await get_short_interest_yf(ticker)
        except Exception as e:
            logger.warning(f"[TradeReview] Short interest yfinance Fallback für {ticker}: {e}")
            yf_si = None
        if yf_si:
            from schemas.sentiment import ShortInterestData
            short_interest = ShortInterestData(
                ticker=ticker,
                short_interest=yf_si.get("shares_short", 0),
                short_interest_percent=yf_si.get("short_interest_percent", 0),
                days_to_cover=yf_si.get("short_ratio", 0),
                trend="stable",
                squeeze_risk="medium" if yf_si.get("short_interest_percent", 0) > 15 else "low",
            )

    insiders = None
    try:
        insiders = await get_insider_transactions(ticker)
    except Exception as e:
        logger.warning(f"[TradeReview] Insider transactions für {ticker}: {e}")

    technicals = None
    try:
        technicals = await get_technical_setup(ticker)
    except Exception as e:
        logger.warning(f"[TradeReview] Technicals für {ticker}: {e}")

    options = None
    try:
        from backend.app.data.yfinance_data import get_options_metrics
        options = await get_options_metrics(ticker)
    except Exception as e:
        logger.warning(f"[TradeReview] Options für {ticker}: {e}")

    from backend.app.data.market_overview import get_market_overview
    from backend.app.analysis.chart_analyst import analyze_chart
    from backend.app.data.fred import get_macro_snapshot
    from backend.app.data.fear_greed import get_fear_greed_score
    from backend.app.data.reddit_monitor import get_reddit_sentiment
    from backend.app.memory.short_term import get_bullet_points

    market_ov_result, chart_result, macro_result, fear_greed_result, reddit_result = await asyncio.gather(
        get_market_overview(),
        analyze_chart(ticker),
        get_macro_snapshot(),
        get_fear_greed_score(),
        get_reddit_sentiment(ticker, hours=24),
        return_exceptions=True,
    )

    def _safe_result(result, default):
        return default if isinstance(result, Exception) else result

    market_ov = _safe_result(market_ov_result, {})
    chart_data = _safe_result(chart_result, {})
    macro = _safe_result(macro_result, {})
    fear_greed_data = _safe_result(fear_greed_result, {})
    reddit_data = _safe_result(reddit_result, {})

    now = datetime.now()
    month_ago = now - timedelta(days=30)
    news_memory = await get_bullet_points(ticker)
    news_list = None
    if not news_memory:
        try:
            news_list = await get_company_news(
                ticker,
                month_ago.strftime("%Y-%m-%d"),
                now.strftime("%Y-%m-%d"),
            )
        except Exception as e:
            logger.warning(f"[TradeReview] Company news für {ticker}: {e}")

    valuation_ctx = {}
    if metrics:
        valuation_ctx = _model_to_dict(metrics)
    elif profile:
        valuation_ctx = _model_to_dict(profile)
    elif yf_fundamentals:
        valuation_ctx = {
            "ticker": ticker,
            "pe_ratio": yf_fundamentals.get("pe_ratio"),
            "ps_ratio": yf_fundamentals.get("ps_ratio"),
            "market_cap": yf_fundamentals.get("market_cap"),
            "sector": yf_fundamentals.get("sector"),
        }

    market_indices = market_ov.get("indices", {}) if isinstance(market_ov, dict) else {}
    spy = market_indices.get("SPY", {}) if isinstance(market_indices, dict) else {}
    sector = (
        getattr(profile, "sector", None)
        or getattr(metrics, "sector", None)
        or (yf_fundamentals.get("sector") if yf_fundamentals else None)
        or "Unknown"
    )

    data_ctx = {
        "earnings_history": _model_to_dict(history),
        "valuation": valuation_ctx,
        "short_interest": _model_to_dict(short_interest),
        "insider_activity": _model_to_dict(insiders),
        "macro": _model_to_dict(macro),
        "technicals": _model_to_dict(technicals),
        "news_memory": news_memory if news_memory else [],
        "news_list": news_list or [],
        "options": _model_to_dict(options),
        "social": _model_to_dict(reddit_data),
        "composite_sentiment": _safe_float(reddit_data.get("avg_score") if isinstance(reddit_data, dict) else None, 0.0),
        "web_sentiment_score": 0.0,
        "finbert_sentiment": 0.0,
        "sentiment_divergence": False,
        "analyst_grades": _model_to_dict(audit_grades) if isinstance(audit_grades, dict) else audit_grades or [],
        "sector_ranking": market_ov.get("sector_ranking_5d", []) if isinstance(market_ov, dict) else [],
        "ticker_sector": sector,
        "reddit_sentiment": reddit_data.get("avg_score", 0.0) if isinstance(reddit_data, dict) else 0.0,
        "reddit_mentions": reddit_data.get("mention_count", 0) if isinstance(reddit_data, dict) else 0,
        "reddit_label": reddit_data.get("label", "keine Daten") if isinstance(reddit_data, dict) else "keine Daten",
        "fear_greed_score": fear_greed_data.get("score", 50.0) if isinstance(fear_greed_data, dict) else 50.0,
        "fear_greed_label": fear_greed_data.get("label", "Neutral") if isinstance(fear_greed_data, dict) else "Neutral",
        "earnings_countdown": earnings_countdown,
    }

    opp_score = await calculate_opportunity_score(ticker, data_ctx)
    torp_score = await calculate_torpedo_score(ticker, data_ctx)

    if not isinstance(macro, dict):
        macro = {}
    _macro_regime = macro.get("regime")
    _vix = _safe_float(macro.get("vix"), None)
    _credit_spread_bps = _safe_float(macro.get("credit_spread_bps"), None)

    rec = await get_recommendation(
        opp_score,
        torp_score,
        macro_regime=_macro_regime,
        vix=_vix,
    )

    opportunity_components = {
        "earnings_momentum": opp_score.earnings_momentum,
        "whisper_delta": opp_score.whisper_delta,
        "valuation_regime": opp_score.valuation_regime,
        "guidance_trend": opp_score.guidance_trend,
        "technical_setup": opp_score.technical_setup,
        "sector_regime": opp_score.sector_regime,
        "short_squeeze_potential": opp_score.short_squeeze_potential,
        "insider_activity": opp_score.insider_activity,
        "options_flow": opp_score.options_flow,
    }
    torpedo_components = {
        "valuation_downside": torp_score.valuation_downside,
        "expectation_gap": torp_score.expectation_gap,
        "insider_selling": torp_score.insider_selling,
        "guidance_deceleration": torp_score.guidance_deceleration,
        "leadership_instability": torp_score.leadership_instability,
        "technical_downtrend": torp_score.technical_downtrend,
        "macro_headwind": torp_score.macro_headwind,
    }

    component_labels = {
        "earnings_momentum": "Earnings Momentum",
        "whisper_delta": "Whisper Delta",
        "valuation_regime": "Valuation Regime",
        "guidance_trend": "Guidance Trend",
        "technical_setup": "Technical Setup",
        "sector_regime": "Sector Regime",
        "short_squeeze_potential": "Short Squeeze Potential",
        "insider_activity": "Insider Activity",
        "options_flow": "Options Flow",
    }
    torpedo_labels = {
        "valuation_downside": "Valuation Downside",
        "expectation_gap": "Expectation Gap",
        "insider_selling": "Insider Selling",
        "guidance_deceleration": "Guidance Deceleration",
        "leadership_instability": "Leadership Instability",
        "technical_downtrend": "Technical Downtrend",
        "macro_headwind": "Macro Headwind",
    }

    top_drivers = _rank_components(opportunity_components, component_labels, limit=4)
    top_risks = _rank_components(torpedo_components, torpedo_labels, limit=4)

    prompt_payload = {
        "ticker": ticker,
        "company": _model_to_dict(profile),
        "scores": {
            "opportunity_score": round(_safe_float(opp_score.total_score, 0.0), 1),
            "torpedo_score": round(_safe_float(torp_score.total_score, 0.0), 1),
            "base_recommendation": rec.recommendation,
            "base_recommendation_label": rec.recommendation_label,
            "base_reasoning": rec.reasoning,
        },
        "top_drivers": top_drivers,
        "top_risks": top_risks,
        "macro": {
            "regime": _macro_regime,
            "vix": _vix,
            "credit_spread_bps": _credit_spread_bps,
        },
        "market_context": {
            "spy": spy,
            "sector": sector,
            "sector_ranking_5d": market_ov.get("sector_ranking_5d", []) if isinstance(market_ov, dict) else [],
        },
        "technicals": _model_to_dict(technicals),
        "options": _model_to_dict(options),
        "earnings": _model_to_dict(history),
        "valuation": valuation_ctx,
        "insiders": _model_to_dict(insiders),
        "short_interest": _model_to_dict(short_interest),
        "news_memory": news_memory if news_memory else [],
        "news_list": news_list or [],
        "reddit": reddit_data if isinstance(reddit_data, dict) else {},
        "fear_greed": fear_greed_data if isinstance(fear_greed_data, dict) else {},
        "chart_analysis": chart_data if isinstance(chart_data, dict) else {},
    }

    system_prompt = (
        "Du bist ein erfahrener Aktien-Research- und Risiko-Analyst. "
        "Nutze die bereitgestellten Daten und gib ausschließlich gültiges JSON zurück. "
        "Antworte konservativ, wenn Daten lückenhaft sind."
    )
    user_prompt = (
        f"Erstelle für {ticker} eine Trade-Review-Entscheidung.\n\n"
        "Gib ausschließlich dieses JSON-Schema zurück:\n"
        "{\n"
        '  "recommendation": "strong_buy|buy_hedge|hold|watch|ignore|strong_short|potential_short",\n'
        '  "recommendation_label": "kurzer lesbarer Titel",\n'
        '  "thesis": "maximal 4 Sätze",\n'
        '  "key_bull_points": ["...", "..."],\n'
        '  "key_risks": ["...", "..."],\n'
        '  "execution_note": "kurze Handlungsanweisung",\n'
        '  "confidence": 0-100\n'
        "}\n\n"
        "Nutze die Daten unten als Grundlage und vermeide unnötige Floskeln.\n\n"
        f"{json.dumps(prompt_payload, ensure_ascii=False, indent=2, default=str)}"
    )

    reasoner_text = await call_deepseek(
        system_prompt,
        user_prompt,
        model="deepseek-reasoner",
        temperature=0.0,
        max_tokens=1400,
    )

    parsed = _extract_json_object(reasoner_text)
    final_recommendation = rec.recommendation
    final_label = rec.recommendation_label
    final_reasoning = rec.reasoning
    key_bull_points: list[str] = []
    key_risks: list[str] = []
    execution_note = ""
    confidence = None

    if parsed:
        final_recommendation = _normalize_review_recommendation(
            parsed.get("recommendation"),
            final_recommendation,
        )
        final_label = str(
            parsed.get("recommendation_label")
            or parsed.get("label")
            or final_label
        )
        final_reasoning = str(
            parsed.get("thesis")
            or parsed.get("reasoning")
            or parsed.get("summary")
            or final_reasoning
        )
        key_bull_points = parsed.get("key_bull_points") or parsed.get("bull_points") or []
        key_risks = parsed.get("key_risks") or parsed.get("risks") or []
        execution_note = str(parsed.get("execution_note") or parsed.get("next_step") or "")
        confidence = parsed.get("confidence")

    if not key_bull_points:
        key_bull_points = [item["label"] for item in top_drivers[:3]] or ["Keine klaren bullischen Treiber erkennbar."]
    if not key_risks:
        key_risks = [item["label"] for item in top_risks[:3]] or ["Keine klaren Hauptrisiken erkennbar."]

    price_at_decision = _safe_float(getattr(technicals, "current_price", None), None)
    rsi_at_decision = _safe_float(getattr(technicals, "rsi_14", None), None)
    iv_atm_at_decision = _safe_float(getattr(options, "implied_volatility_atm", None), None)

    earnings_date = None
    if estimates is not None:
        raw_earnings_date = getattr(estimates, "report_date", None)
        if raw_earnings_date:
            earnings_date = raw_earnings_date

    raw_data = {
        "context": prompt_payload,
        "scores": {
            "opportunity": _model_to_dict(opp_score),
            "torpedo": _model_to_dict(torp_score),
        },
        "components": {
            "opportunity": opportunity_components,
            "torpedo": torpedo_components,
        },
        "parsed_reasoner": parsed or {},
        "top_drivers": top_drivers,
        "top_risks": top_risks,
        "model_used": "deepseek-reasoner",
        "macro_regime": _macro_regime,
        "vix": _vix,
        "credit_spread_bps": _credit_spread_bps,
        "price_at_decision": price_at_decision,
        "rsi_at_decision": rsi_at_decision,
        "iv_atm_at_decision": iv_atm_at_decision,
        "earnings_date": str(earnings_date) if earnings_date else None,
        "earnings_countdown": earnings_countdown,
    }

    return {
        "ticker": ticker,
        "recommendation": final_recommendation,
        "recommendation_label": final_label,
        "reasoning": final_reasoning,
        "confidence": confidence,
        "opportunity_score": round(_safe_float(opp_score.total_score, 0.0), 1),
        "torpedo_score": round(_safe_float(torp_score.total_score, 0.0), 1),
        "prompt_text": user_prompt,
        "decision_text": reasoner_text,
        "model_used": "deepseek-reasoner",
        "top_drivers": top_drivers,
        "top_risks": top_risks,
        "raw_data": raw_data,
        "price_at_decision": price_at_decision,
        "rsi_at_decision": rsi_at_decision,
        "iv_atm_at_decision": iv_atm_at_decision,
        "macro_regime": _macro_regime,
        "vix": _vix,
        "credit_spread_bps": _credit_spread_bps,
        "earnings_date": str(earnings_date) if earnings_date else None,
        "earnings_countdown": earnings_countdown,
        "key_bull_points": key_bull_points,
        "key_risks": key_risks,
        "execution_note": execution_note,
    }


async def _save_decision_snapshot(
    *,
    ticker: str,
    opportunity_score: float,
    torpedo_score: float,
    recommendation: str,
    prompt_text: str,
    report_text: str,
    raw_data: dict | None = None,
    earnings_countdown: int | None = None,
    **extra,
) -> dict:
    """Speichert einen unveränderlichen Decision Snapshot in der DB."""
    from backend.app.db import get_supabase_client

    db = get_supabase_client()
    if not db:
        logger.warning(f"[DecisionSnapshot] DB nicht verfügbar für {ticker}")
        return {"success": False, "reason": "db_unavailable"}

    raw_data = raw_data or {}
    model_used = extra.get("model_used") or raw_data.get("model_used") or "deepseek-reasoner"
    price_at_decision = extra.get("price_at_decision", raw_data.get("price_at_decision"))
    rsi_at_decision = extra.get("rsi_at_decision", raw_data.get("rsi_at_decision"))
    iv_atm_at_decision = extra.get("iv_atm_at_decision", raw_data.get("iv_atm_at_decision"))
    macro_regime = extra.get("macro_regime", raw_data.get("macro_regime"))
    vix = extra.get("vix", raw_data.get("vix"))
    credit_spread_bps = extra.get("credit_spread_bps", raw_data.get("credit_spread_bps"))
    earnings_date = extra.get("earnings_date", raw_data.get("earnings_date"))

    top_drivers = extra.get("top_drivers") or raw_data.get("top_drivers") or []
    top_risks = extra.get("top_risks") or raw_data.get("top_risks") or []

    prompt_snapshot = prompt_text.strip()
    report_snapshot = report_text.strip()
    if report_snapshot:
        prompt_snapshot = f"{prompt_snapshot}\n\n--- Reasoner Decision ---\n{report_snapshot}"

    payload = {
        "ticker": ticker.upper(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "opportunity_score": round(_safe_float(opportunity_score, 0.0), 1),
        "torpedo_score": round(_safe_float(torpedo_score, 0.0), 1),
        "recommendation": recommendation,
        "macro_regime": macro_regime,
        "vix": vix,
        "credit_spread_bps": credit_spread_bps,
        "top_drivers": top_drivers,
        "top_risks": top_risks,
        "price_at_decision": price_at_decision,
        "rsi_at_decision": rsi_at_decision,
        "iv_atm_at_decision": iv_atm_at_decision,
        "earnings_date": earnings_date,
        "prompt_snapshot": prompt_snapshot[:12000],
        "model_used": model_used,
        "trade_type": "earnings" if earnings_countdown is not None else "momentum",
        "earnings_countdown_at_decision": earnings_countdown,
        "data_quality_flag": raw_data.get("data_quality_flag"),
    }

    try:
        await db.table("decision_snapshots").insert(payload).execute_async()
        logger.info(f"[DecisionSnapshot] Gespeichert für {ticker}")
        return {"success": True}
    except Exception as exc:
        msg = str(exc)
        logger.warning(f"[DecisionSnapshot] Speichern fehlgeschlagen für {ticker}: {exc}")
        return {"success": False, "reason": msg}
