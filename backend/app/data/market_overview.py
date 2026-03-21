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
    "URTH": "MSCI World",
    "^NDX": "Nasdaq 100 (Index)",
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

    cache_key = "market:overview"
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
    Nutzt ein repräsentatives Sample der 30 größten S&P 500 Titel
    (Dow Jones Komponenten als Proxy — alle via yfinance kostenlos).

    Gibt zurück:
    - pct_above_sma50: Prozent der Titel über SMA50
    - pct_above_sma200: Prozent der Titel über SMA200
    - breadth_signal: "stark" | "neutral" | "schwach"
    - advance_decline: Steigende vs. fallende Titel heute (aus sample)
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

        for ticker in DOW_COMPONENTS:
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

    cache_key = "market:intermarket"
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

    result = {"assets": data, "signals": signals}
    cache_set(cache_key, result, ttl_seconds=600)
    return result
