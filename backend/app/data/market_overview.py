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


def _batch_download(
    symbols: list[str],
    period: str = "6mo",
) -> dict[str, object]:
    """
    Lädt Historien für alle Symbole in EINEM
    yfinance.download() Call.
    Gibt {symbol: DataFrame} zurück.

    yfinance.download() mit group_by="ticker" liefert
    MultiIndex: (Field, Ticker) oder (Ticker, Field)
    je nach Version. Wir normalisieren das.
    """
    import yfinance as yf
    import pandas as pd

    if not symbols:
        return {}

    try:
        download_kwargs = {
            "tickers": symbols,
            "period": period,
            "interval": "1d",
            "auto_adjust": True,
            "progress": False,
            "threads": True,
            "group_by": "ticker",
        }

        try:
            raw = yf.download(**download_kwargs, multi_level_index=True)
        except TypeError:
            raw = yf.download(**download_kwargs)

        result = {}

        if len(symbols) == 1:
            # Einzelner Ticker: kein MultiIndex
            sym = symbols[0]
            if not raw.empty:
                result[sym] = raw
            return result

        # Mehrere Ticker: MultiIndex (Ticker, Field)
        # oder (Field, Ticker) — normalisieren
        if isinstance(raw.columns, pd.MultiIndex):
            # Prüfe Reihenfolge der Level
            if raw.columns.get_level_values(0)[0] in symbols:
                # Level 0 = Ticker
                for sym in symbols:
                    if sym in raw.columns.get_level_values(0):
                        df = raw[sym].dropna(how="all")
                        if not df.empty:
                            result[sym] = df
            else:
                # Level 1 = Ticker (Field, Ticker)
                for sym in symbols:
                    try:
                        df = raw.xs(sym, axis=1, level=1).dropna(
                            how="all"
                        )
                        if not df.empty:
                            result[sym] = df
                    except KeyError:
                        pass

            if result:
                return result

        # Fallback: falls yfinance nur Teilmengen oder Single-Frames liefert,
        # benutze die vorhandenen Spalten soweit möglich.
        for sym in symbols:
            if sym in getattr(raw, "columns", []):
                try:
                    df = raw.xs(sym, axis=1, level=1).dropna(how="all")
                except Exception:
                    df = raw[[sym]].dropna(how="all")
                if not df.empty:
                    result[sym] = df

        return result

    except Exception as e:
        logger.error(f"_batch_download Fehler: {e}")
        return {}


def _analyze_from_hist(
    ticker_symbol: str,
    hist,    # DataFrame
    name: str = "",
) -> dict:
    """
    Berechnet technische Analyse aus VORHANDENEM
    DataFrame (kein neuer yfinance-Call).
    Identische Logik wie _analyze_ticker().
    """
    try:
        if hist is None or hist.empty or len(hist) < 5:
            return {"error": f"Keine Daten für {ticker_symbol}"}

        close = hist["Close"]
        current = float(close.iloc[-1])
        prev_close = float(close.iloc[-2]) if len(close) > 1 else current

        perf_1d = ((current - prev_close) / prev_close) * 100
        perf_5d = (
            ((current - float(close.iloc[-5]))
             / float(close.iloc[-5])) * 100
            if len(close) >= 5 else 0
        )
        perf_1m = (
            ((current - float(close.iloc[-21]))
             / float(close.iloc[-21])) * 100
            if len(close) >= 21 else 0
        )

        sma_20 = float(close.tail(20).mean())
        sma_50 = float(close.tail(50).mean()) if len(close) >= 50 else None
        sma_200 = float(close.tail(200).mean()) if len(close) >= 200 else None

        rsi = None
        if len(close) >= 15:
            rsi = float(_calc_rsi(close))

        high_52w = float(hist["High"].max())
        low_52w = float(hist["Low"].min())
        dist_high = ((current - high_52w) / high_52w) * 100

        trend = "sideways"
        if sma_50 and sma_200:
            if current > sma_50 > sma_200:
                trend = "uptrend"
            elif current < sma_50 < sma_200:
                trend = "downtrend"
        elif sma_50:
            trend = "uptrend" if current > sma_50 else "downtrend"

        support = float(hist["Low"].tail(20).min())
        resistance = float(hist["High"].tail(20).max())

        return {
            "name": name,
            "price": round(current, 2),
            "change_1d_pct": round(perf_1d, 2),
            "change_5d_pct": round(perf_5d, 2),
            "change_1m_pct": round(perf_1m, 2),
            "sma_20": round(sma_20, 2),
            "sma_50": round(sma_50, 2) if sma_50 else None,
            "sma_200": round(sma_200, 2) if sma_200 else None,
            "rsi_14": round(rsi, 1) if rsi else None,
            "trend": trend,
            "above_sma50": (current > sma_50) if sma_50 else None,
            "above_sma200": (current > sma_200) if sma_200 else None,
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "dist_52w_high_pct": round(dist_high, 1),
        }
    except Exception as e:
        logger.error(f"Analyse-Fehler für {ticker_symbol}: {e}")
        return {"error": str(e)}

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

    logger.info("Erstelle Marktübersicht (Batch-Download)...")

    # ALLE Symbole in EINEM Download
    all_symbols = (
        list(INDICES.keys())
        + list(SECTOR_ETFS.keys())
        + list(MACRO_TICKERS.keys())
    )
    # Deduplizieren (falls Überschneidungen)
    all_symbols = list(dict.fromkeys(all_symbols))

    # Ein einziger HTTP-Request statt 24 einzelne
    hist_data = await asyncio.to_thread(
        _batch_download, all_symbols, "1y"
    )

    result = {
        "timestamp": datetime.now().isoformat(),
        "indices": {},
        "sectors": {},
        "macro": {},
    }

    # Indizes aus Batch-Daten
    for symbol, name in INDICES.items():
        hist = hist_data.get(symbol)
        data = _analyze_from_hist(symbol, hist, name)
        result["indices"][symbol] = data

    # Sektoren aus Batch-Daten
    for symbol, name in SECTOR_ETFS.items():
        hist = hist_data.get(symbol)
        data = _analyze_from_hist(symbol, hist, name)
        result["sectors"][symbol] = data

    # Sortiere Sektoren nach 5-Tages-Performance (stärkste zuerst)
    sorted_sectors = sorted(
        result["sectors"].items(),
        key=lambda x: x[1].get("change_5d_pct", 0) if x[1].get("change_5d_pct") is not None else x[1].get("perf_5d", 0),
        reverse=True
    )
    result["sector_ranking_5d"] = [
        {"symbol": s, "name": d["name"], "perf_5d": d.get("change_5d_pct", 0) if d.get("change_5d_pct") is not None else d.get("perf_5d", 0)}
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

    # Makro-Proxys aus Batch-Daten
    for symbol, name in MACRO_TICKERS.items():
        hist = hist_data.get(symbol)
        data = _analyze_from_hist(symbol, hist, name)
        result["macro"][symbol] = data

    logger.info(
        f"Marktübersicht erstellt ({len(hist_data)} Ticker)"
    )
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


async def save_daily_snapshot(
    market_data: dict,
    macro_data,
    regime: str = "neutral",
    breadth_data: dict | None = None,
    briefing_summary: str | None = None,
):
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
            "composite_regime_score": None,  # Placeholder for future frontend calculation backend storage
            # HINWEIS: Falls DB-Fehler → SQL ausführen:
            # ALTER TABLE daily_snapshots
            #   ADD COLUMN IF NOT EXISTS pct_above_sma50 FLOAT,
            #   ADD COLUMN IF NOT EXISTS pct_above_sma200 FLOAT;
            "pct_above_sma50": (
                breadth_data.get("pct_above_sma50")
                if breadth_data else None
            ),
            "pct_above_sma200": (
                breadth_data.get("pct_above_sma200")
                if breadth_data else None
            ),
            "briefing_summary": briefing_summary,
        }

        try:
            await db.table("daily_snapshots").upsert(record, on_conflict="date").execute_async()
        except Exception as exc:
            error_text = str(exc).lower()
            if "pct_above_sma50" in error_text or "pct_above_sma200" in error_text or "column" in error_text:
                fallback_record = {
                    k: v for k, v in record.items()
                    if k not in {"pct_above_sma50", "pct_above_sma200"}
                }
                logger.warning(
                    "daily_snapshots breadth columns fehlen noch; speichere Snapshot ohne breadth-Felder."
                )
                await db.table("daily_snapshots").upsert(fallback_record, on_conflict="date").execute_async()
            else:
                raise
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
        result = await db.table("daily_snapshots") \
            .select("*") \
            .lt("date", date.today().isoformat()) \
            .order("date", desc=True) \
            .limit(1) \
            .execute_async()

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
        above_50 = above_200 = advancing = declining = total = 0

        # EIN Batch-Download statt 50 einzelne Calls
        hist_data = _batch_download(SP500_TOP50, period="1y")

        for ticker in SP500_TOP50:
            try:
                hist = hist_data.get(ticker)
                if hist is None or hist.empty or len(hist) < 10:
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
        }

    result = await asyncio.to_thread(_calc_breadth)

    # Historische Werte aus daily_snapshots
    pct_5d_ago = None
    pct_20d_ago = None
    try:
        from backend.app.db import get_supabase_client
        from datetime import date, timedelta
        db = get_supabase_client()
        if db:
            today = date.today()
            d20 = (today - timedelta(days=40)).isoformat()

            rows = await (
                db.table("daily_snapshots")
                .select("date,pct_above_sma50")
                .gte("date", d20)
                .order("date", desc=False)
                .execute_async()
            )
            if rows.data:
                valid_rows = [
                    r for r in rows.data
                    if r.get("pct_above_sma50") is not None
                ]

                # 5 Handelstage zurück = 6. letzter Snapshot (heute + 5 frühere Handelstage)
                if len(valid_rows) >= 6:
                    pct_5d_ago = valid_rows[-6]["pct_above_sma50"]

                # 20 Handelstage zurück = 21. letzter Snapshot
                if len(valid_rows) >= 21:
                    pct_20d_ago = valid_rows[-21]["pct_above_sma50"]
    except Exception as e:
        logger.debug(f"Breadth-History Fehler: {e}")

    # Update result with historical values
    result["pct_above_sma50_5d_ago"] = pct_5d_ago
    result["pct_above_sma50_20d_ago"] = pct_20d_ago

    # Add trend calculation
    breadth_trend = None
    if pct_5d_ago is not None and result:
        delta = result["pct_above_sma50"] - pct_5d_ago
        breadth_trend = (
            "steigend" if delta > 3
            else "fallend" if delta < -3
            else "stabil"
        )
    result["breadth_trend_5d"] = breadth_trend

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
        INTERMARKET = {
            "SPY":    "S&P 500",
            "TLT":    "20Y Treasuries",
            "GLD":    "Gold",
            "USO":    "Öl (WTI)",
            "UUP":    "US Dollar",
            "^VIX":   "VIX",
            "^VIX3M": "VIX 3-Monat",
            "EEM":    "Emerging Markets",
            "HYG":    "High Yield Bonds",
        }
        symbols = list(INTERMARKET.keys())

        # EIN Batch-Download statt 9 einzelne Calls
        hist_data = _batch_download(symbols, period="3mo")

        results = {}
        for symbol, name in INTERMARKET.items():
            try:
                hist = hist_data.get(symbol)
                if hist is None or hist.empty:
                    continue

                close = hist["Close"]
                current = float(close.iloc[-1])
                prev = float(close.iloc[-2])
                week_ago = (
                    float(close.iloc[-5])
                    if len(close) >= 5 else current
                )
                month_ago = (
                    float(close.iloc[-21])
                    if len(close) >= 21 else current
                )
                sma20 = float(close.tail(20).mean())

                results[symbol] = {
                    "name": name,
                    "price": round(current, 2),
                    "change_1d": round(
                        ((current - prev) / prev) * 100, 2
                    ),
                    "change_1w": round(
                        ((current - week_ago) / week_ago) * 100, 2
                    ),
                    "change_1m": round(
                        ((current - month_ago) / month_ago) * 100, 2
                    ),
                    "above_sma20": current > sma20,
                    "trend_1m": (
                        "steigend" if current > month_ago
                        else "fallend"
                    ),
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
    from backend.app.data.google_news import scan_google_news
    from backend.app.analysis.finbert import analyze_sentiment_batch
    from datetime import datetime

    cache_key = "market:news_sentiment"
    cached = cache_get(cache_key)
    if cached:
        return cached

    def _source_weight(origin: str, source: str) -> float:
        source_lower = source.lower()
        if origin == "finnhub":
            return 1.0
        if any(q in source_lower for q in ["reuters", "bloomberg", "ap", "associated press", "ft", "financial times"]):
            return 1.1
        if any(q in source_lower for q in ["cnbc", "wsj", "wall street journal", "marketwatch", "yahoo"]):
            return 1.0
        return 0.9

    def _label(score: float) -> str:
        if score > 0.15:
            return "bullish"
        if score < -0.15:
            return "bearish"
        return "neutral"

    def _categorize_google(category: str, headline: str) -> str:
        if category in {"business", "world"}:
            return category
        headline_lower = headline.lower()
        if any(k in headline_lower for k in ["fed", "federal reserve", "fomc", "powell", "rate", "monetary", "quantitative"]):
            return "fed_rates"
        if any(k in headline_lower for k in ["cpi", "inflation", "gdp", "unemployment", "jobs", "payroll", "pmi", "retail sales", "consumer", "housing", "deficit"]):
            return "macro_data"
        if any(k in headline_lower for k in ["tariff", "sanction", "trade war", "china", "geopolit", "conflict", "war", "opec", "supply chain", "ukraine", "taiwan"]):
            return "geopolitics"
        return category or "market_general"

    def _normalize_item(item: dict, origin: str) -> dict | None:
        if not isinstance(item, dict):
            return None

        headline = str(item.get("headline", "")).strip()
        if not headline:
            return None

        timestamp = 0
        raw_ts = item.get("timestamp")
        if raw_ts is None:
            raw_ts = item.get("datetime")
        if isinstance(raw_ts, (int, float)):
            timestamp = int(raw_ts)
            if origin == "finnhub" and timestamp > 10_000_000_000:
                timestamp = int(timestamp / 1000)
        elif isinstance(raw_ts, str):
            try:
                timestamp = int(float(raw_ts))
            except Exception:
                timestamp = 0

        if timestamp and timestamp < (datetime.now().timestamp() - 86400):
            return None

        source = str(item.get("source", "")).strip() or origin
        url = str(item.get("url", "")).strip()
        category = str(item.get("category", "")).strip() or "market_general"
        if origin == "google_news":
            category = _categorize_google(category, headline)

        return {
            "headline": headline,
            "category": category,
            "source": source,
            "timestamp": timestamp,
            "url": url,
            "origin": origin,
            "source_weight": _source_weight(origin, source),
        }

    try:
        # Finnhub General News — kostenlos, Englisch
        # category="general" = breite Marktnachrichten
        news_raw = await get_general_news("general", min_id=0)
    except Exception:
        news_raw = []

    try:
        google_news_raw = await scan_google_news([])
    except Exception:
        google_news_raw = []

    if not news_raw and not google_news_raw:
        return {"categories": {}, "headlines": [], "error": "no_data"}

    combined = []
    seen: set[str] = set()
    for origin, items in (("finnhub", news_raw or []), ("google_news", google_news_raw or [])):
        for item in items[:80]:
            normalized = _normalize_item(item, origin)
            if not normalized:
                continue
            dedupe_key = normalized["url"].lower() if normalized["url"] else normalized["headline"].lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            combined.append(normalized)

    if not combined:
        return {"categories": {}, "headlines": [], "error": "no_data"}

    combined.sort(key=lambda x: (x.get("timestamp", 0), abs(x.get("source_weight", 1.0))), reverse=True)
    combined = combined[:36]

    # FinBERT Sentiment pro Headline
    categories = {
        "fed_rates": [],
        "macro_data": [],
        "geopolitics": [],
        "market_general": [],
        "business": [],
        "world": [],
    }

    try:
        # Alle Headlines auf einmal (Batch ist effizienter)
        all_headlines = [h["headline"] for h in combined]
        scores = analyze_sentiment_batch(all_headlines)

        for i, item in enumerate(combined):
            score = scores[i] if i < len(scores) else 0.0
            item["sentiment_score"] = round(score, 3)
            categories.setdefault(item["category"], []).append(score)
            categories.setdefault("market_general", [])

    except Exception:
        for item in combined:
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

    bullish = sum(1 for item in combined if item.get("sentiment_score", 0.0) > 0.15)
    bearish = sum(1 for item in combined if item.get("sentiment_score", 0.0) < -0.15)
    neutral = len(combined) - bullish - bearish

    source_breakdown = {}
    for origin in {item["origin"] for item in combined}:
        origin_items = [item for item in combined if item["origin"] == origin]
        origin_scores = [item.get("sentiment_score", 0.0) for item in origin_items]
        if origin_scores:
            avg_score = round(sum(origin_scores) / len(origin_scores), 3)
            source_breakdown[origin] = {
                "count": len(origin_items),
                "score": avg_score,
                "label": _label(avg_score),
            }

    weighted_score_total = 0.0
    weighted_score_denominator = 0.0
    for item in combined:
        score = float(item.get("sentiment_score", 0.0))
        weight = float(item.get("source_weight", 1.0))
        weighted_score_total += score * weight
        weighted_score_denominator += weight

    overall_score = round(weighted_score_total / weighted_score_denominator, 3) if weighted_score_denominator else 0.0

    result = {
        "headlines": sorted(
            combined,
            key=lambda x: (abs(x.get("sentiment_score", 0)), x.get("timestamp", 0)),
            reverse=True  # Stärkste Signale zuerst
        )[:12],
        "category_sentiment": category_sentiment,
        "overall_sentiment": {
            "score": overall_score,
            "label": _label(overall_score),
            "bullish": bullish,
            "bearish": bearish,
            "neutral": neutral,
            "sample_size": len(combined),
            "source_counts": {
                "finnhub": len([item for item in combined if item["origin"] == "finnhub"]),
                "google_news": len([item for item in combined if item["origin"] == "google_news"]),
            },
        },
        "source_breakdown": source_breakdown,
        "total_analyzed": len(combined),
        "fetched_at": datetime.now().isoformat(),
    }

    cache_set(cache_key, result, ttl_seconds=600)
    return result
