"""
market_overview — Tägliche Index- und Sektor-Chartanalyse

Input:  Keine (feste Index-Liste)
Output: dict mit Index-Technicals und Sektor-Performance
Deps:   yfinance, config.py, logger.py
Config: config/settings.yaml → use_mock_data
API:    Yahoo Finance (via yfinance, kostenlos)
"""

import yfinance as yf
import json
import os
import asyncio
from datetime import datetime
from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.cache import cache_get, cache_set

logger = get_logger(__name__)

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "fixtures")

# Indizes die wir täglich tracken
INDICES = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
    "DIA": "Dow Jones",
    "IWM": "Russell 2000",
    "^GDAXI": "DAX",
    "^STOXX50E": "Euro Stoxx 50",
    "^N225": "Nikkei 225",
    "URTH": "MSCI World",
}

# Sektor-ETFs für Rotationsanalyse
SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLU": "Utilities",
    "XLI": "Industrials",
    "XLC": "Communication",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLB": "Materials",
    "XLRE": "Real Estate",
}

# S&P 500 Top 50 nach Marktkapitalisierung (XLG-Komponenten)
SP500_TOP50 = [
    "NVDA","AAPL","MSFT","AMZN","META","GOOGL","GOOG","BRK-B","AVGO",
    "TSLA","JPM","LLY","UNH","V","XOM","MA","COST","HD","PG","JNJ",
    "ABBV","WMT","BAC","NFLX","KO","CRM","CVX","MRK","ORCL","ACN",
    "AMD","MCD","TMO","ABT","PEP","ADBE","CSCO","LIN","DIS","DHR",
    "WFC","TXN","PM","AMGN","IBM","ISRG","GE","INTU","CAT","NOW"
]


# Wichtige Makro-Proxys
MACRO_TICKERS = {
    "^VIX": "VIX (Angst-Index)",
    "TLT": "20Y+ Treasuries",
    "UUP": "US-Dollar",
    "GLD": "Gold",
    "USO": "Öl (WTI)",
}


def _calc_rsi(prices, period=14):
    """Berechnet RSI aus einer Preisserie."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return (100 - (100 / (1 + rs))).iloc[-1]


def _analyze_ticker(ticker_symbol: str) -> dict:
    """Technische Analyse für einen einzelnen Ticker."""
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="6mo")

        if hist.empty or len(hist) < 20:
            return {"error": f"Keine Daten für {ticker_symbol}"}

        close = hist["Close"]
        current = float(close.iloc[-1])
        prev_close = float(close.iloc[-2]) if len(close) > 1 else current

        # Performance-Berechnung
        perf_1d = ((current - prev_close) / prev_close) * 100
        perf_5d = ((current - float(close.iloc[-5])) / float(close.iloc[-5])) * 100 if len(close) >= 5 else 0
        perf_1m = ((current - float(close.iloc[-21])) / float(close.iloc[-21])) * 100 if len(close) >= 21 else 0

        # Moving Averages
        sma_20 = float(close.tail(20).mean())
        sma_50 = float(close.tail(50).mean()) if len(close) >= 50 else None
        sma_200 = float(close.tail(200).mean()) if len(close) >= 200 else None

        # RSI
        rsi = float(_calc_rsi(close)) if len(close) >= 15 else None

        # High/Low
        high_52w = float(hist["High"].max())
        low_52w = float(hist["Low"].min())
        dist_high = ((current - high_52w) / high_52w) * 100

        # Trend
        trend = "sideways"
        if sma_50 and sma_200:
            if current > sma_50 > sma_200:
                trend = "uptrend"
            elif current < sma_50 < sma_200:
                trend = "downtrend"
        elif sma_50:
            if current > sma_50:
                trend = "uptrend"
            else:
                trend = "downtrend"

        # Support/Resistance (vereinfacht: 20-Tage Low/High)
        support = float(hist["Low"].tail(20).min())
        resistance = float(hist["High"].tail(20).max())

        return {
            "price": round(current, 2),
            "change_1d_pct": round(perf_1d, 2),
            "change_5d_pct": round(perf_5d, 2),
            "change_1m_pct": round(perf_1m, 2),
            "sma_20": round(sma_20, 2),
            "sma_50": round(sma_50, 2) if sma_50 else None,
            "sma_200": round(sma_200, 2) if sma_200 else None,
            "rsi_14": round(rsi, 1) if rsi else None,
            "trend": trend,
            "above_sma50": current > sma_50 if sma_50 else None,
            "above_sma200": current > sma_200 if sma_200 else None,
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "dist_52w_high_pct": round(dist_high, 1),
        }
    except Exception as e:
        logger.error(f"Analyse-Fehler für {ticker_symbol}: {e}")
        return {"error": str(e)}


async def get_market_overview() -> dict:
    """
    Erstellt die komplette Marktübersicht:
    - Index-Technicals (SPY, QQQ, DIA, IWM)
    - Sektor-Rotation (11 Sektor-ETFs mit 1d/5d/1m Performance)
    - Makro-Proxys (VIX, Treasuries, Dollar, Gold, Öl)
    """
    if settings.use_mock_data:
        try:
            path = os.path.join(FIXTURES_DIR, "market_overview.json")
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return {"error": "Mock-Daten nicht verfügbar"}

    cache_key = "market:overview:v2"
    cached = cache_get(cache_key)
    if cached:
        logger.debug("Marktübersicht aus Cache")
        return cached

    logger.info("Erstelle Marktübersicht...")

    result = {"timestamp": datetime.now().isoformat(), "indices": {}, "sectors": {}, "macro": {}}

    # Indizes
    for symbol, name in INDICES.items():
        data = _analyze_ticker(symbol)
        data["name"] = name
        result["indices"][symbol] = data
        logger.debug(f"Index {symbol}: {data.get('price', 'N/A')} ({data.get('change_1d_pct', 'N/A')}%)")

    # Sektoren
    for symbol, name in SECTOR_ETFS.items():
        data = _analyze_ticker(symbol)
        data["name"] = name
        result["sectors"][symbol] = data

    # Sortiere Sektoren nach 5-Tages-Performance (stärkste zuerst)
    sorted_sectors = sorted(
        result["sectors"].items(),
        key=lambda x: x[1].get("change_5d_pct", 0),
        reverse=True
    )
    result["sector_ranking_5d"] = [
        {"symbol": s, "name": d["name"], "perf_5d": d.get("change_5d_pct", 0)}
        for s, d in sorted_sectors
    ]

    # Rotations-Story automatisch berechnen
    DEFENSIVE_SECTORS = {"XLU", "XLV", "XLP"}
    OFFENSIVE_SECTORS = {"XLK", "XLC", "XLY"}

    defensive_avg = 0.0
    offensive_avg = 0.0
    def_count = off_count = 0

    for item in result["sector_ranking_5d"]:
        sym = item["symbol"]
        perf = item.get("perf_5d", 0)
        if sym in DEFENSIVE_SECTORS:
            defensive_avg += perf
            def_count += 1
        elif sym in OFFENSIVE_SECTORS:
            offensive_avg += perf
            off_count += 1

    if def_count: defensive_avg /= def_count
    if off_count: offensive_avg /= off_count

    gap = defensive_avg - offensive_avg
    if gap > 2.0:
        story = "Defensive Rotation — Geld fließt von Growth nach Defensiv (Risk-Off)"
        story_signal = "risk_off"
    elif gap < -2.0:
        story = "Offensive Rotation — Growth und Zykliker führen (Risk-On)"
        story_signal = "risk_on"
    else:
        story = "Neutrale Rotation — kein klares Muster"
        story_signal = "neutral"

    result["rotation_story"] = story
    result["rotation_signal"] = story_signal
    result["defensive_avg_5d"] = round(defensive_avg, 2)
    result["offensive_avg_5d"] = round(offensive_avg, 2)

    # Makro-Proxys
    for symbol, name in MACRO_TICKERS.items():
        data = _analyze_ticker(symbol)
        data["name"] = name
        result["macro"][symbol] = data

    logger.info("Marktübersicht erstellt.")
    cache_set(cache_key, result, ttl_seconds=300)
    return result


async def get_general_market_news() -> list[dict]:
    """
    Holt allgemeine Marktnachrichten von Finnhub (Geopolitik, Politik, Fed etc.).
    Endpoint: GET /news?category=general
    Kostenlos im Free Tier.
    """
    if settings.use_mock_data:
        return [{"headline": "Mock: Fed signals continued rate cuts", "source": "mock", "summary": "", "url": "", "datetime": 0}]

    import httpx
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={settings.finnhub_api_key}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            news = response.json()

            # Nimm die 15 neuesten, filtere auf relevante Quellen
            filtered = []
            for n in news[:30]:
                source = n.get("source", "").lower()
                # Priorisiere Qualitätsquellen
                if any(s in source for s in ["reuters", "bloomberg", "cnbc", "wsj", "ft", "associated press", "yahoo"]):
                    filtered.append({
                        "headline": n.get("headline", ""),
                        "summary": n.get("summary", "")[:200],
                        "source": n.get("source", ""),
                        "url": n.get("url", ""),
                        "datetime": n.get("datetime", 0)
                    })
                if len(filtered) >= 10:
                    break

            # Falls nicht genug Qualitätsquellen: Auffüllen mit allen
            if len(filtered) < 5:
                for n in news[:15]:
                    if n.get("headline", "") not in [f["headline"] for f in filtered]:
                        filtered.append({
                            "headline": n.get("headline", ""),
                            "summary": n.get("summary", "")[:200],
                            "source": n.get("source", ""),
                            "url": n.get("url", ""),
                            "datetime": n.get("datetime", 0)
                        })
                    if len(filtered) >= 10:
                        break

            logger.info(f"Allgemeine Marktnachrichten: {len(filtered)} geladen")
            return filtered
    except Exception as e:
        logger.error(f"Fehler beim Laden allgemeiner Nachrichten: {e}")
        return []


async def save_daily_snapshot(market_data: dict, macro_data, regime: str = "neutral"):
    """Speichert den Tages-Snapshot für den Vergleich am nächsten Tag."""
    from backend.app.db import get_supabase_client
    from datetime import date

    try:
        db = get_supabase_client()
        if db is None:
            logger.warning("Supabase nicht verfügbar, Snapshot nicht gespeichert.")
            return

        indices = market_data.get("indices", {})
        ranking = market_data.get("sector_ranking_5d", [])

        record = {
            "date": date.today().isoformat(),
            "spy_price": indices.get("SPY", {}).get("price"),
            "spy_change_pct": indices.get("SPY", {}).get("change_1d_pct"),
            "qqq_price": indices.get("QQQ", {}).get("price"),
            "qqq_change_pct": indices.get("QQQ", {}).get("change_1d_pct"),
            "dia_price": indices.get("DIA", {}).get("price"),
            "iwm_price": indices.get("IWM", {}).get("price"),
            "vix": market_data.get("macro", {}).get("^VIX", {}).get("price") if isinstance(market_data.get("macro", {}).get("^VIX", {}), dict) else None,
            "credit_spread": getattr(macro_data, "credit_spread_bps", None) if macro_data else None,
            "yield_spread": getattr(macro_data, "yield_curve_10y_2y", None) if macro_data else None,
            "dxy": market_data.get("macro", {}).get("UUP", {}).get("price"),
            "top_sector": ranking[0]["name"] if ranking else None,
            "bottom_sector": ranking[-1]["name"] if ranking else None,
            "regime": regime,
        }

        db.table("daily_snapshots").upsert(record, on_conflict="date").execute()
        logger.info(f"Tages-Snapshot gespeichert/aktualisiert für {date.today()}")
    except Exception as e:
        logger.error(f"Fehler beim Speichern des Tages-Snapshots: {e}")


async def get_yesterday_snapshot() -> dict | None:
    """Holt den Snapshot von gestern (oder dem letzten verfügbaren Handelstag)."""
    from backend.app.db import get_supabase_client
    from datetime import date

    try:
        db = get_supabase_client()
        if db is None:
            return None

        # Versuche die letzten 3 Tage (für Wochenenden/Feiertage)
        result = db.table("daily_snapshots") \
            .select("*") \
            .lt("date", date.today().isoformat()) \
            .order("date", desc=True) \
            .limit(1) \
            .execute()

        if result.data:
            return result.data[0]
    except Exception as e:
        logger.error(f"Fehler beim Laden des gestrigen Snapshots: {e}")
    return None


async def get_market_breadth() -> dict:
    """
    Berechnet Marktbreite: Anteil S&P 500 Aktien über SMA50/SMA200.
    Nutzt S&P 500 Top 50 nach Marktkapitalisierung.

    Gibt zurück:
    - pct_above_sma50: Prozent der Titel über SMA50
    - pct_above_sma200: Prozent der Titel über SMA200
    - breadth_signal: "stark" | "neutral" | "schwach"
    - advance_decline: Steigende vs. fallende Titel heute (aus sample)
    - breadth_index: "S&P 500 Top 50 (Marktkapitalisierung)"
    # NEU: letzte Woche und letzten Monat aus Cache/Supabase
    # Wenn nicht verfügbar: None — Frontend zeigt "—"
    - pct_above_sma50_5d_ago: None,   # Placeholder
    - pct_above_sma50_20d_ago: None,  # Placeholder
    """
    DOW_COMPONENTS = [
        "AAPL","MSFT","AMZN","NVDA","GOOGL","META","TSLA","BRK-B",
        "JPM","V","UNH","XOM","JNJ","WMT","PG","MA","HD","CVX",
        "MRK","ABBV","KO","PEP","AVGO","TMO","COST","ACN","MCD",
        "BAC","LLY","ORCL"
    ]

    cache_key = "market:breadth"
    cached = cache_get(cache_key)
    if cached:
        return cached

    def _calc_breadth():
        above_50 = 0
        above_200 = 0
        advancing = 0
        declining = 0
        total = 0

        for ticker in SP500_TOP50:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="1y")
                if hist.empty or len(hist) < 10:
                    continue

                close = hist["Close"]
                current = float(close.iloc[-1])
                prev = float(close.iloc[-2])

                if len(close) >= 50:
                    sma50 = float(close.tail(50).mean())
                    if current > sma50:
                        above_50 += 1
                if len(close) >= 200:
                    sma200 = float(close.tail(200).mean())
                    if current > sma200:
                        above_200 += 1

                if current > prev:
                    advancing += 1
                else:
                    declining += 1
                total += 1
            except Exception:
                continue

        if total == 0:
            return {"error": "Keine Daten"}

        pct_50 = round((above_50 / total) * 100, 1)
        pct_200 = round((above_200 / total) * 100, 1)

        signal = "neutral"
        if pct_50 >= 70:
            signal = "stark"
        elif pct_50 <= 40:
            signal = "schwach"

        return {
            "pct_above_sma50": pct_50,
            "pct_above_sma200": pct_200,
            "breadth_signal": signal,
            "advancing": advancing,
            "declining": declining,
            "sample_size": total,
            "breadth_index": "S&P 500 Top 50 (Marktkapitalisierung)",
            "pct_above_sma50_5d_ago": None,   # Placeholder
            "pct_above_sma50_20d_ago": None,  # Placeholder
        }

    result = await asyncio.to_thread(_calc_breadth)
    cache_set(cache_key, result, ttl_seconds=1800)  # 30 Minuten
    return result


async def get_intermarket_signals() -> dict:
    """
    Berechnet Cross-Asset-Signale für Regime-Erkennung.
    Alle Daten kostenlos via yfinance.

    Signale:
    - risk_on_off: Aktien vs. Anleihen Verhältnis (SPY/TLT)
    - dollar_direction: DXY-Trend (bullisch = Druck auf EM + Commodities)
    - gold_signal: Gold-Trend (steigend = Unsicherheit / Inflation)
    - oil_signal: Öl-Trend (Energiesektor-Proxy)
    - vix_term_structure: VIX vs. VIX3M (Contango = Ruhe, Backwardation = Panik)
    """
    INTERMARKET = {
        "SPY":  "S&P 500",
        "TLT":  "20Y Treasuries",
        "GLD":  "Gold",
        "USO":  "Öl (WTI)",
        "UUP":  "US Dollar",
        "^VIX": "VIX",
        "^VIX3M": "VIX 3-Monat",
        "EEM":  "Emerging Markets",
        "HYG":  "High Yield Bonds",
    }

    cache_key = "market:intermarket:v2"
    cached = cache_get(cache_key)
    if cached:
        return cached

    def _fetch():
        results = {}
        for symbol, name in INTERMARKET.items():
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(period="3mo")
                if hist.empty:
                    continue
                close = hist["Close"]
                current = float(close.iloc[-1])
                prev = float(close.iloc[-2])
                week_ago = float(close.iloc[-5]) if len(close) >= 5 else current
                month_ago = float(close.iloc[-21]) if len(close) >= 21 else current
                sma20 = float(close.tail(20).mean())

                results[symbol] = {
                    "name": name,
                    "price": round(current, 2),
                    "change_1d": round(((current - prev) / prev) * 100, 2),
                    "change_1w": round(((current - week_ago) / week_ago) * 100, 2),
                    "change_1m": round(((current - month_ago) / month_ago) * 100, 2),
                    "above_sma20": current > sma20,
                    "trend_1m": "steigend" if current > month_ago else "fallend",
                }
            except Exception:
                continue
        return results

    data = await asyncio.to_thread(_fetch)

    # Regime-Signale berechnen
    spy = data.get("SPY", {})
    tlt = data.get("TLT", {})
    gld = data.get("GLD", {})
    vix = data.get("^VIX", {})
    vix3m = data.get("^VIX3M", {})
    hyg = data.get("HYG", {})

    signals = {}

    # Risk-On/Off: Aktien vs. Anleihen
    if spy.get("change_1w") is not None and tlt.get("change_1w") is not None:
        if spy["change_1w"] > 0 and tlt["change_1w"] < 0:
            signals["risk_appetite"] = "risk_on"
        elif spy["change_1w"] < 0 and tlt["change_1w"] > 0:
            signals["risk_appetite"] = "risk_off"
        else:
            signals["risk_appetite"] = "mixed"

    # VIX Struktur: Backwardation = Panik, Contango = Ruhe
    if vix.get("price") is not None and vix3m.get("price") is not None:
        vix_val = vix["price"]
        vix3m_val = vix3m["price"]
        if vix_val > vix3m_val * 1.05:
            signals["vix_structure"] = "backwardation"  # Panik
            signals["vix_note"] = f"VIX {vix_val:.1f} > VIX3M {vix3m_val:.1f} — erhöhte Kurzfrist-Angst"
        elif vix_val < vix3m_val * 0.95:
            signals["vix_structure"] = "contango"  # Normal
            signals["vix_note"] = f"VIX {vix_val:.1f} < VIX3M {vix3m_val:.1f} — Markt erwartet höhere Volatilität erst später"
        else:
            signals["vix_structure"] = "flat"
            signals["vix_note"] = "VIX-Kurve flach"

    # HYG (High Yield) als Credit-Signal
    if hyg.get("change_1w") is not None:
        if hyg["change_1w"] < -1.5:
            signals["credit_signal"] = "warnung"
            signals["credit_note"] = "High Yield Bonds unter Druck — Kreditmarkt zeigt Stress"
        elif hyg["change_1w"] > 0.5:
            signals["credit_signal"] = "gesund"
            signals["credit_note"] = "High Yield stabil — kein Kreditstress"
        else:
            signals["credit_signal"] = "neutral"

    # ── Energie-Stress-Signal ────────────────────────────────
    # USO = Oil ETF (WTI Proxy). Starker Anstieg = Inflationsdruck
    # Historisch: Öl +>20% in einem Monat → negativ für breite Märkte
    uso = data.get("USO", {})
    uso_1m = uso.get("change_1m")
    uso_1w = uso.get("change_1w")

    if uso_1m is not None:
        if uso_1m > 20:
            signals["energy_stress"] = "schock"
            signals["energy_note"] = (
                f"USO +{uso_1m:.1f}% (1M) — Energie-Schock. "
                f"Historisch negativ für breite Märkte. "
                f"Inflationsdruck erhöht. Fed kann nicht senken."
            )
        elif uso_1m > 10:
            signals["energy_stress"] = "erhöht"
            signals["energy_note"] = (
                f"USO +{uso_1m:.1f}% (1M) — Energie erhöht. "
                f"Marginaler Inflationsdruck."
            )
        elif uso_1m < -10:
            signals["energy_stress"] = "entspannt"
            signals["energy_note"] = (
                f"USO {uso_1m:.1f}% (1M) — Energie fällt. "
                f"Disinflationär, positiv für Margen."
            )
        else:
            signals["energy_stress"] = "neutral"
            signals["energy_note"] = f"USO {uso_1m:.1f}% (1M) — Energie neutral."

    # Stagflations-Warnung: Energie steigt + Markt fällt
    spy = data.get("SPY", {})
    if (
        uso_1m is not None
        and spy.get("change_1m") is not None
        and uso_1m > 15
        and spy["change_1m"] < -3
    ):
        signals["stagflation_warning"] = True
        signals["stagflation_note"] = (
            f"STAGFLATIONS-MUSTER: Öl +{uso_1m:.1f}% aber "
            f"S&P {spy['change_1m']:.1f}% (1M). "
            f"Erhöhtes Risiko für anhaltenden Abschwung."
        )
    else:
        signals["stagflation_warning"] = False

    result = {"assets": data, "signals": signals}
    cache_set(cache_key, result, ttl_seconds=600)
    return result


async def get_market_news_for_sentiment() -> dict:
    """
    Holt Marktnachrichten und bereitet sie für FinBERT auf.

    WICHTIG für FinBERT-Qualität:
    - Nur Englisch (FinBERT auf englische Finanztexte trainiert)
    - Nur Headlines, kein Fließtext (kürzer = klarer für FinBERT)
    - Gefiltert nach Markt-Relevanz (nicht jede News)
    - Kategorisiert nach Themenbereich für Aggregation

    Kategorien:
    - "fed_rates": Fed, Zinsen, Geldpolitik, FOMC
    - "macro_data": CPI, GDP, Jobs, Inflation, PMI
    - "geopolitics": Handelskrieg, Sanktionen, Konflikte die Märkte bewegen
    - "earnings_sector": Quartalszahlen die Sektoren bewegen
    - "market_general": Allgemeine Marktbewegungen

    Keywords für Kategorisierung (case-insensitive):
    FED_KEYWORDS = ["fed", "federal reserve", "fomc", "powell",
                    "rate", "interest rate", "monetary policy",
                    "rate hike", "rate cut", "quantitative"]
    MACRO_KEYWORDS = ["cpi", "inflation", "gdp", "unemployment",
                      "jobs report", "payroll", "pmi", "retail sales",
                      "consumer confidence", "housing"]
    GEO_KEYWORDS = ["tariff", "sanction", "trade war", "china",
                    "geopolitical", "conflict", "war", "opec",
                    "supply chain"]
    """
    from backend.app.data.finnhub import get_general_news
    from datetime import datetime, timedelta

    cache_key = "market:news_sentiment"
    cached = cache_get(cache_key)
    if cached:
        return cached

    try:
        # Finnhub General News — kostenlos, Englisch
        # category="general" = breite Marktnachrichten
        news_raw = await get_general_news("general", min_id=0)
    except Exception:
        news_raw = []

    if not news_raw:
        return {"categories": {}, "headlines": [], "error": "no_data"}

    FED_KW = ["fed","federal reserve","fomc","powell","rate","monetary","quantitative"]
    MACRO_KW = ["cpi","inflation","gdp","unemployment","jobs","payroll","pmi",
                "retail sales","consumer","housing","deficit"]
    GEO_KW = ["tariff","sanction","trade war","china","geopolit","conflict",
               "war","opec","supply chain","ukraine","taiwan"]

    def categorize(headline: str) -> str:
        h = headline.lower()
        if any(k in h for k in FED_KW): return "fed_rates"
        if any(k in h for k in MACRO_KW): return "macro_data"
        if any(k in h for k in GEO_KW): return "geopolitics"
        return "market_general"

    # Nur Headlines, max 24h alt, max 30 Items
    cutoff = datetime.now().timestamp() - 86400
    headlines = []
    for item in (news_raw or [])[:60]:
        if not isinstance(item, dict): continue
        headline = item.get("headline", "")
        timestamp = item.get("datetime", 0)
        if not headline or timestamp < cutoff: continue
        source = item.get("source", "")
        # Nur bekannte Qualitätsquellen
        if not any(q in source.lower() for q in [
            "reuters","bloomberg","cnbc","wsj","ft","marketwatch",
            "ap","yahoo","seekingalpha","barron"
        ]):
            continue
        headlines.append({
            "headline": headline,  # Nur Headline, kein Summary
            "category": categorize(headline),
            "source": source,
            "timestamp": timestamp,
            "url": item.get("url", ""),
        })
        if len(headlines) >= 30: break

    # FinBERT Sentiment pro Headline
    categories = {
        "fed_rates": [],
        "macro_data": [],
        "geopolitics": [],
        "market_general": [],
    }

    try:
        from backend.app.analysis.finbert import analyze_sentiment_batch
        # Alle Headlines auf einmal (Batch ist effizienter)
        all_headlines = [h["headline"] for h in headlines]
        scores = analyze_sentiment_batch(all_headlines)

        for i, item in enumerate(headlines):
            score = scores[i] if i < len(scores) else 0.0
            item["sentiment_score"] = round(score, 3)
            categories[item["category"]].append(score)

    except Exception:
        for item in headlines:
            item["sentiment_score"] = 0.0

    # Aggregiertes Sentiment pro Kategorie
    category_sentiment = {}
    for cat, scores in categories.items():
        if scores:
            avg = round(sum(scores) / len(scores), 3)
            category_sentiment[cat] = {
                "score": avg,
                "count": len(scores),
                "label": (
                    "bullish" if avg > 0.15
                    else "bearish" if avg < -0.15
                    else "neutral"
                )
            }

    result = {
        "headlines": sorted(
            headlines,
            key=lambda x: abs(x.get("sentiment_score", 0)),
            reverse=True  # Stärkste Signale zuerst
        )[:12],
        "category_sentiment": category_sentiment,
        "total_analyzed": len(headlines),
        "fetched_at": datetime.now().isoformat(),
    }

    cache_set(cache_key, result, ttl_seconds=600)
    return result
