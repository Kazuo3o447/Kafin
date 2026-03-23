"""
yfinance_data — Technische Daten via yfinance

Input:  ticker: str
Output: schemas/technicals.TechnicalSetup
Deps:   config.py
Config: config/settings.yaml → use_mock_data
API:    Yahoo Finance (via yfinance Bibliothek)
"""
import asyncio
import yfinance as yf
import json
import os
from datetime import datetime
from typing import Optional
import pandas as pd
from schemas.technicals import TechnicalSetup, OptionsMetrics
from schemas.options import OptionsData, OptionChainSummary
from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.cache import cache_get, cache_set
import numpy as np
import asyncio

logger = get_logger(__name__)

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "fixtures")


async def get_technical_setup(ticker: str) -> TechnicalSetup:
    """Berechnet technische Kennzahlen für einen Ticker."""
    if settings.use_mock_data:
        try:
            path = os.path.join(FIXTURES_DIR, "yfinance", f"technicals_{ticker}.json")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return TechnicalSetup(**data)
        except Exception:
            return TechnicalSetup(ticker=ticker, current_price=0.0)

    cache_key = f"yf:technicals:{ticker.upper()}"
    cached = await cache_get(cache_key)
    if cached:
        logger.debug(f"yfinance Cache-Hit für {ticker}")
        return TechnicalSetup(**cached)

    def _fetch() -> TechnicalSetup:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")

            if hist.empty:
                logger.warning(f"Keine yfinance-Daten für {ticker}")
                return TechnicalSetup(ticker=ticker, current_price=0.0)

            current_price = float(hist["Close"].iloc[-1])
            sma_50 = float(hist["Close"].tail(50).mean()) if len(hist) >= 50 else None
            sma_200 = float(hist["Close"].tail(200).mean()) if len(hist) >= 200 else None
            high_52w = float(hist["High"].max())
            low_52w = float(hist["Low"].min())

            # RSI berechnen (14 Tage)
            delta = hist["Close"].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            rsi_14 = float(rsi_series.iloc[-1]) if not rsi_series.empty else None

            # Trend bestimmen
            trend = "sideways"
            if sma_50 and sma_200:
                if current_price > sma_50 > sma_200:
                    trend = "uptrend"
                elif current_price < sma_50 < sma_200:
                    trend = "downtrend"

            distance_to_52w_high = ((current_price - high_52w) / high_52w) * 100 if high_52w else None

            # ── Performance-Werte für Research Dashboard ─────────────────
            close = hist["Close"]
            prev_close = float(close.iloc[-2]) if len(close) > 1 else current_price
            
            # 1-Tage Performance
            change_1d_pct = ((current_price - prev_close) / prev_close) * 100 if len(close) > 1 else None
            
            # 5-Tage Performance
            change_5d_pct = (
                ((current_price - float(close.iloc[-5]))
                 / float(close.iloc[-5])) * 100
                if len(close) >= 5 else None
            )
            
            # 1-Monat Performance
            change_1m_pct = (
                ((current_price - float(close.iloc[-21]))
                 / float(close.iloc[-21])) * 100
                if len(close) >= 21 else None
            )

            # ── SMA 20 ──────────────────────────────────────────────
            sma_20 = float(hist["Close"].tail(20).mean()) if len(hist) >= 20 else None

            # ── ATR (14 Tage) ────────────────────────────────────────
            # Average True Range = Maß für tägliche Kursschwankung
            high_low   = hist["High"] - hist["Low"]
            high_close = (hist["High"] - hist["Close"].shift()).abs()
            low_close  = (hist["Low"] - hist["Close"].shift()).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr_14 = float(tr.rolling(14).mean().iloc[-1]) if len(hist) >= 15 else None

            # ── MACD ─────────────────────────────────────────────────
            # Signal: MACD-Linie über/unter Signal-Linie
            # Mindestens 26 Tage für EMA-26 nötig
            if len(hist) >= 26:
                ema_12 = hist["Close"].ewm(span=12, adjust=False).mean()
                ema_26 = hist["Close"].ewm(span=26, adjust=False).mean()
                macd_line    = ema_12 - ema_26
                signal_line  = macd_line.ewm(span=9, adjust=False).mean()
                macd_val     = float(macd_line.iloc[-1])  if not macd_line.empty  else None
                macd_signal  = float(signal_line.iloc[-1]) if not signal_line.empty else None
                macd_hist_val = round(macd_val - macd_signal, 4) if macd_val and macd_signal else None
                macd_bullish  = (macd_val > macd_signal) if macd_val and macd_signal else None
            else:
                macd_val = macd_signal = macd_hist_val = macd_bullish = None

            # ── OBV (On-Balance Volume) ───────────────────────────────
            # Steigendes OBV = Käuferdruck
            close_diff = hist["Close"].diff()
            obv_direction = pd.Series(0, index=hist.index)
            obv_direction[close_diff > 0] = 1   # Steigend: +Volume
            obv_direction[close_diff < 0] = -1  # Fallend: -Volume
            # close_diff == 0: bleibt 0 (kein Volumen addiert)
            obv = (hist["Volume"] * obv_direction).cumsum()
            obv_val      = float(obv.iloc[-1])           if not obv.empty else None
            obv_5d_ago   = float(obv.iloc[-5])           if len(obv) >= 5 else None
            obv_trend    = (
                "steigend" if obv_val and obv_5d_ago and obv_val > obv_5d_ago
                else "fallend" if obv_val and obv_5d_ago
                else None
            )

            # ── RVOL (Relative Volume) ───────────────────────────────
            # Aktuelles Volumen vs. 20-Tage-Durchschnitt
            avg_vol_20 = float(hist["Volume"].tail(20).mean()) if len(hist) >= 20 else None
            last_vol   = float(hist["Volume"].iloc[-1])
            rvol       = round(last_vol / avg_vol_20, 2) if avg_vol_20 and avg_vol_20 > 0 else None

            # ── Free Float & Avg Volume (aus yfinance info) ──────────
            try:
                info         = stock.info
                float_shares = info.get("floatShares")
                avg_volume   = info.get("averageVolume") or info.get("averageDailyVolume10Day")
                shares_out   = info.get("sharesOutstanding")
                bid          = info.get("bid")
                ask          = info.get("ask")
                bid_ask_spread = round(ask - bid, 4) if bid and ask and ask > 0 else None
            except Exception:
                float_shares = avg_volume = shares_out = bid = ask = bid_ask_spread = None

            result = TechnicalSetup(
                ticker=ticker,
                current_price=current_price,
                sma_50=round(sma_50, 2) if sma_50 is not None else None,
                sma_200=round(sma_200, 2) if sma_200 is not None else None,
                rsi_14=round(rsi_14, 2) if rsi_14 is not None else None,
                high_52w=round(high_52w, 2),
                low_52w=round(low_52w, 2),
                distance_to_52w_high_percent=round(distance_to_52w_high, 2) if distance_to_52w_high is not None else None,
                trend=trend,
                above_sma50=current_price > sma_50 if sma_50 is not None else False,
                above_sma200=current_price > sma_200 if sma_200 is not None else False,
                sma_20=round(sma_20, 2) if sma_20 is not None else None,
                atr_14=round(atr_14, 2) if atr_14 is not None else None,
                macd=round(macd_val, 4) if macd_val is not None else None,
                macd_signal=round(macd_signal, 4) if macd_signal is not None else None,
                macd_histogram=macd_hist_val,
                macd_bullish=macd_bullish,
                obv=round(obv_val, 0) if obv_val is not None else None,
                obv_trend=obv_trend,
                rvol=rvol if rvol is not None else None,
                float_shares=float_shares,
                avg_volume=avg_volume,
                shares_outstanding=shares_out,
                bid_ask_spread=bid_ask_spread,
                change_1d_pct=round(change_1d_pct, 2) if change_1d_pct is not None else None,
                change_5d_pct=round(change_5d_pct, 2) if change_5d_pct is not None else None,
                change_1m_pct=round(change_1m_pct, 2) if change_1m_pct is not None else None,
            )
            return result
        except Exception as e:
            logger.error(f"yfinance Fehler für {ticker}: {e}")
            return TechnicalSetup(ticker=ticker, current_price=0.0)

    result = await asyncio.to_thread(_fetch)
    if result and result.current_price > 0:
        await cache_set(cache_key, result.dict(), ttl_seconds=300)
    return result


async def get_risk_metrics(ticker: str) -> dict:
    """
    Holt Risk-Metriken: Beta zum S&P 500.
    Beta > 1.2 = hohe Volatilität (wichtig für Contrarian-Setup).
    """
    if settings.use_mock_data:
        return {"beta": 1.35, "ticker": ticker}

    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        beta = info.get("beta")
        
        if beta is None:
            logger.warning(f"Kein Beta für {ticker} verfügbar")
            return {"beta": None, "ticker": ticker}
        
        return {
            "beta": round(float(beta), 2),
            "ticker": ticker
        }
    except Exception as e:
        logger.error(f"Risk Metrics Fehler für {ticker}: {e}")
        return {"beta": None, "ticker": ticker}


async def get_historical_volatility(ticker: str, days: int = 20) -> Optional[float]:
    """
    Berechnet historische Volatilität (annualisiert) über die letzten N Tage.
    Wird mit IV verglichen um zu sehen ob Optionen teuer/günstig sind.
    """
    if settings.use_mock_data:
        return 25.5  # Mock: 25.5% historische Vola

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{days + 10}d")  # Puffer für Feiertage
        
        if hist.empty or len(hist) < days:
            logger.warning(f"Nicht genug Daten für historische Vola: {ticker}")
            return None
        
        # Berechne tägliche Returns
        hist['returns'] = hist['Close'].pct_change()
        
        # Standardabweichung der Returns (annualisiert: sqrt(252 Trading Days))
        daily_vol = hist['returns'].std()
        annual_vol = daily_vol * np.sqrt(252) * 100  # In Prozent
        
        return round(float(annual_vol), 2)
    except Exception as e:
        logger.error(f"Historische Volatilität Fehler für {ticker}: {e}")
        return None


async def get_atm_implied_volatility(ticker: str) -> Optional[OptionsData]:
    """
    Holt die Implizite Volatilität (IV) der At-The-Money (ATM) Optionen.
    Nutzt die nächste verfügbare Expiration > 5 Tage.
    Returns: OptionsData mit IV, Volume, Put/Call Ratio, historischer Vola.
    """
    if settings.use_mock_data:
        return OptionsData(
            ticker=ticker,
            implied_volatility_atm=35.2,
            options_volume=125000,
            put_call_ratio=1.15,
            historical_volatility=28.5,
            expiration_date="2026-04-18",
            iv_percentile=75.0
        )

    try:
        stock = yf.Ticker(ticker)
        exps = getattr(stock, 'options', [])
        
        if not exps:
            logger.warning(f"Keine Optionen für {ticker} verfügbar")
            return None

        # Finde nächste Expiration > 5 Tage
        now = datetime.now()
        target_exp = None
        for exp in exps:
            exp_date = datetime.strptime(exp, "%Y-%m-%d")
            if (exp_date - now).days > 5:
                target_exp = exp
                break
        
        if not target_exp:
            logger.warning(f"Keine passende Expiration für {ticker}")
            return None
        
        opt = stock.option_chain(target_exp)
        calls = opt.calls
        puts = opt.puts
        
        if calls.empty or puts.empty:
            return None
        
        # Aktueller Kurs
        hist = stock.history(period="1d")
        if hist.empty:
            return None
        current_price = float(hist['Close'].iloc[-1])
        
        # Finde ATM Strike (nächster zum aktuellen Kurs)
        calls['distance'] = abs(calls['strike'] - current_price)
        puts['distance'] = abs(puts['strike'] - current_price)
        
        atm_call = calls.loc[calls['distance'].idxmin()]
        atm_put = puts.loc[puts['distance'].idxmin()]
        
        # Durchschnittliche IV von ATM Call und Put
        iv_call = float(atm_call['impliedVolatility'])
        iv_put = float(atm_put['impliedVolatility'])
        iv_atm = (iv_call + iv_put) / 2 * 100  # In Prozent
        
        # Put/Call Ratio (Volume)
        total_put_vol = float(puts['volume'].sum())
        total_call_vol = float(calls['volume'].sum())
        pcr = total_put_vol / total_call_vol if total_call_vol > 0 else 0.0
        
        # Gesamtvolumen
        total_volume = int(total_put_vol + total_call_vol)
        
        # Historische Volatilität zum Vergleich
        hist_vol = await get_historical_volatility(ticker, days=20)
        
        return OptionsData(
            ticker=ticker,
            implied_volatility_atm=round(iv_atm, 2),
            options_volume=total_volume,
            put_call_ratio=round(pcr, 2),
            historical_volatility=hist_vol,
            expiration_date=target_exp,
            iv_percentile=None  # TODO: Berechnung erfordert historische IV-Daten
        )
    except Exception as e:
        logger.error(f"ATM IV Fehler für {ticker}: {e}")
        return None


async def get_options_metrics(ticker: str) -> Optional[OptionsMetrics]:
    """Berechnet Options-Kennzahlen für einen Ticker (PCR, IV ATM)."""
    if settings.use_mock_data:
        return OptionsMetrics(put_call_ratio_oi=1.1, put_call_ratio_vol=0.85, implied_volatility_atm=0.25, expiration="2024-01-01")
        
    try:
        stock = yf.Ticker(ticker)
        # Check if options exist
        exps = getattr(stock, 'options', [])
        if not exps:
            return None

        # Finde nächste Expiration > 5 Tage in der Zukunft
        now = datetime.now()
        target_exp = None
        for exp in exps:
            exp_date = datetime.strptime(exp, "%Y-%m-%d")
            if (exp_date - now).days > 5:
                target_exp = exp
                break
                
        if not target_exp:
            return None
            
        opt = stock.option_chain(target_exp)
        calls = opt.calls
        puts = opt.puts
        
        if calls.empty or puts.empty:
            return None
            
        # Put/Call Ratio (Open Interest)
        total_put_oi = float(puts['openInterest'].sum())
        total_call_oi = float(calls['openInterest'].sum())
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0.0
        
        # Put/Call Ratio (Volume) - Smart Money Flow Indicator
        total_put_vol = float(puts['volume'].sum()) if 'volume' in puts.columns else 0
        total_call_vol = float(calls['volume'].sum()) if 'volume' in calls.columns else 0
        put_call_ratio_vol = round(total_put_vol / total_call_vol, 2) if total_call_vol > 0 else None
        
        # IV ATM
        # Approximiere aktuellen Kurs mittels yfinance history
        hist = stock.history(period="1d")
        if hist.empty:
             return None
        current_price = float(hist['Close'].iloc[-1])
        
        # Finde ATM Call
        calls['distance'] = abs(calls['strike'] - current_price)
        atm_call = calls.loc[calls['distance'].idxmin()]
        iv_atm = float(atm_call['impliedVolatility'])
        
        # yfinance gibt IV als Dezimal zurück (0.35 = 35%)
        # Plausibilitätsprüfung: IV sollte zwischen 0.001 und 10.0 liegen
        if iv_atm > 100:  # > 10000% ist unrealistisch, war in % statt Dezimal
            iv_atm = iv_atm / 100
        elif iv_atm < 0.001:  # < 0.1% ist unrealistisch
            iv_atm = None
        
        if iv_atm is None:
            return None
        
        return OptionsMetrics(
            put_call_ratio_oi=round(pcr, 2),
            put_call_ratio_vol=put_call_ratio_vol,
            implied_volatility_atm=round(iv_atm, 4),
            expiration=target_exp
        )
    except Exception as e:
        logger.error(f"yfinance Options Fehler für {ticker}: {e}")
        return None

async def get_short_interest_yf(ticker: str) -> Optional[dict]:
    """Short Interest via yfinance (kostenlos). Fallback für Finnhub Premium."""
    if settings.use_mock_data:
        return {"short_interest_percent": 15.5, "short_ratio": 3.2, "shares_short": 50000000}
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        short_pct = info.get("shortPercentOfFloat")
        short_pct_value = (short_pct * 100) if short_pct else 0
        
        return {
            "short_interest_percent": round(short_pct_value, 2),
            "short_ratio": info.get("shortRatio", 0),
            "shares_short": info.get("sharesShort", 0),
        }
    except Exception as e:
        logger.error(f"yfinance short interest Fehler für {ticker}: {e}")
        return None


async def get_fundamentals_yf(ticker: str) -> Optional[dict]:
    """
    Holt fundamentale Bewertungskennzahlen via yfinance.
    Dient als Fallback wenn FMP keine Daten liefert.
    """
    if settings.use_mock_data:
        return {
            "pe_ratio": 25.0,
            "ps_ratio": 5.5,
            "market_cap": 1_500_000_000_000,
            "price": 200.0,
            "eps_ttm": 8.5,
            "revenue_ttm": 210_000_000_000,
            "sector": "Technology",
            "industry": "Software",
            "forward_pe": 23.0,
            "dividend_yield": 0.008,
            "beta": 1.1,
            "fifty_two_week_high": 220.0,
            "fifty_two_week_low": 150.0,
            "analyst_target": 230.0,
            "analyst_recommendation": "buy",
            "number_of_analysts": 45,
        }

    cache_key = f"yf:fundamentals:{ticker.upper()}"
    cached = await cache_get(cache_key)
    if cached:
        logger.debug(f"yfinance Fundamentals Cache-Hit für {ticker}")
        return cached

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or not info.get("regularMarketPrice"):
            return None

        result = {
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "market_cap": info.get("marketCap"),
            "price": info.get("regularMarketPrice") or info.get("currentPrice"),
            "eps_ttm": info.get("trailingEps"),
            "revenue_ttm": info.get("totalRevenue"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "forward_pe": info.get("forwardPE"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "analyst_target": info.get("targetMeanPrice"),
            "analyst_recommendation": info.get("recommendationKey"),
            "number_of_analysts": info.get("numberOfAnalystOpinions"),
        }
        await cache_set(cache_key, result, ttl_seconds=86400)  # 24h für Fundamentals
        return result
    except Exception as e:
        logger.error(f"yfinance Fundamentals Fehler für {ticker}: {e}")
        return None

async def get_market_context() -> dict:
    """Holt die Performance der letzten 5 Handelstage für S&P 500, Nasdaq 100 und Gold."""
    if settings.use_mock_data:
        return {"sp500_perf": 1.2, "ndx_perf": 1.5, "gold_perf": -0.5}

    result = {"sp500_perf": 0.0, "ndx_perf": 0.0, "gold_perf": 0.0}
    tickers = {"^GSPC": "sp500_perf", "^NDX": "ndx_perf", "GC=F": "gold_perf"}
    
    try:
        for ticker, key in tickers.items():
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="5d")
                if not hist.empty and len(hist) >= 2:
                    first_price = float(hist["Close"].iloc[0])
                    last_price = float(hist["Close"].iloc[-1])
                    if first_price > 0:
                        perf = ((last_price - first_price) / first_price) * 100
                        result[key] = round(perf, 2)
            except Exception as e:
                logger.error(f"yfinance Fehler für Market Context {ticker}: {e}")
    except Exception as e:
        logger.error(f"Genereller yfinance Fehler in get_market_context: {e}")
        
    return result


async def get_options_oi_analysis(ticker: str) -> dict:
    """
    Berechnet Max Pain + OI-Heatmap aus yfinance option_chain.
    Max Pain = Strike wo Gesamtschmerz aller Optionskäufer maximal.
    Kein API-Key nötig.
    """
    from backend.app.cache import cache_get, cache_set
    cache_key = f"options_oi:{ticker.upper()}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    def _calc():
        import yfinance as yf
        import pandas as pd

        stock = yf.Ticker(ticker)
        exps = getattr(stock, "options", [])
        if not exps:
            return {"error": "Keine Optionsdaten"}

        # Nächsten 2 Verfallsdaten nutzen
        target_exps = exps[:2]
        results = []

        for exp in target_exps:
            try:
                chain = stock.option_chain(exp)
                calls = chain.calls[
                    ["strike","openInterest","volume"]
                ].copy()
                puts = chain.puts[
                    ["strike","openInterest","volume"]
                ].copy()

                calls.columns = ["strike","call_oi","call_vol"]
                puts.columns  = ["strike","put_oi","put_vol"]

                merged = pd.merge(
                    calls, puts, on="strike", how="outer"
                ).fillna(0)
                merged = merged.sort_values("strike")

                # Max Pain berechnen
                total_pain = []
                for price in merged["strike"]:
                    call_pain = (
                        merged[merged["strike"] < price]["call_oi"]
                        * (price - merged[merged["strike"] < price]["strike"])
                    ).sum()
                    put_pain = (
                        merged[merged["strike"] > price]["put_oi"]
                        * (merged[merged["strike"] > price]["strike"] - price)
                    ).sum()
                    total_pain.append(
                        float(call_pain + put_pain)
                    )

                merged["total_pain"] = total_pain
                max_pain_idx = merged["total_pain"].idxmin()
                max_pain_price = float(
                    merged.loc[max_pain_idx, "strike"]
                )

                # Top 5 OI-Strikes (Magnet-Level)
                merged["total_oi"] = (
                    merged["call_oi"] + merged["put_oi"]
                )
                top_oi = merged.nlargest(5, "total_oi")[
                    ["strike","call_oi","put_oi","total_oi"]
                ].to_dict("records")

                # PCR (Put/Call OI Ratio)
                total_call_oi = float(merged["call_oi"].sum())
                total_put_oi  = float(merged["put_oi"].sum())
                pcr_oi = round(
                    total_put_oi / total_call_oi, 2
                ) if total_call_oi > 0 else None

                results.append({
                    "expiry":        exp,
                    "max_pain":      round(max_pain_price, 2),
                    "top_oi_strikes": [
                        {
                            "strike":   round(r["strike"], 2),
                            "call_oi":  int(r["call_oi"]),
                            "put_oi":   int(r["put_oi"]),
                            "total_oi": int(r["total_oi"]),
                        }
                        for r in top_oi
                    ],
                    "pcr_oi":        pcr_oi,
                    "total_call_oi": int(total_call_oi),
                    "total_put_oi":  int(total_put_oi),
                })
            except Exception as e:
                results.append({"expiry": exp, "error": str(e)})

        result = {
            "ticker":  ticker.upper(),
            "expirations": results,
            "nearest_max_pain": (
                results[0]["max_pain"]
                if results and "max_pain" in results[0]
                else None
            ),
        }
        return result

    try:
        import asyncio
        result = await asyncio.to_thread(_calc)
        await cache_set(cache_key, result, ttl_seconds=14400)
        return result
    except Exception as e:
        return {"error": str(e)}


async def get_vwap(ticker: str) -> dict:
    """
    Berechnet VWAP (Volume Weighted Average Price)
    aus heutigem Intraday-1min-Daten.
    Nur sinnvoll während Börsenöffnung (09:30-16:00 ET).
    Außerhalb: gibt None zurück.
    """
    from backend.app.cache import cache_get, cache_set
    cache_key = f"vwap:{ticker.upper()}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    def _calc():
        import yfinance as yf
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # Prüfe ob Markt offen (vereinfacht)
        et = ZoneInfo("America/New_York")
        now_et = datetime.now(et)
        is_market_hours = (
            now_et.weekday() < 5
            and 9 <= now_et.hour < 16
        )

        # Hole 1T Intraday-Daten (5min für Stabilität)
        stock = yf.Ticker(ticker)
        hist = stock.history(
            period="1d", interval="5m", prepost=False
        )

        if hist.empty or len(hist) < 3:
            return {
                "vwap": None,
                "is_market_hours": is_market_hours,
                "data_points": 0,
            }

        # Typischer Preis = (High + Low + Close) / 3
        typical = (
            hist["High"] + hist["Low"] + hist["Close"]
        ) / 3
        vol = hist["Volume"]

        # VWAP = cumsum(Preis * Vol) / cumsum(Vol)
        cumulative_pv = (typical * vol).cumsum()
        cumulative_v  = vol.cumsum()
        vwap_series   = cumulative_pv / cumulative_v

        current_vwap  = float(vwap_series.iloc[-1])
        current_price = float(hist["Close"].iloc[-1])
        vwap_delta    = round(
            (current_price - current_vwap)
            / current_vwap * 100, 2
        )

        return {
            "vwap":            round(current_vwap, 2),
            "current_price":   round(current_price, 2),
            "vwap_delta_pct":  vwap_delta,
            "above_vwap":      current_price > current_vwap,
            "is_market_hours": is_market_hours,
            "data_points":     len(hist),
        }

    try:
        import asyncio
        result = await asyncio.to_thread(_calc)
        # Kurzes Cache — VWAP ändert sich ständig
        ttl = 120 if result.get("is_market_hours") else 3600
        await cache_set(cache_key, result, ttl_seconds=ttl)
        return result
    except Exception as e:
        return {"vwap": None, "error": str(e)}


async def get_earnings_history_yf(
    ticker: str, limit: int = 8
) -> dict | None:
    """
    yfinance Fallback für Earnings-Historie.
    Gibt EarningsHistorySummary-kompatibles Dict zurück
    oder None wenn keine Daten.
    """
    def _fetch():
        import yfinance as yf
        stock = yf.Ticker(ticker)

        # yfinance earnings_history
        try:
            eh = stock.earnings_history
            if eh is None or eh.empty:
                return None

            quarters = []
            for _, row in eh.iterrows():
                eps_act  = row.get("epsActual")
                eps_est  = row.get("epsEstimate")
                surp_pct = None
                if (eps_act is not None
                        and eps_est is not None
                        and eps_est != 0):
                    surp_pct = round(
                        (eps_act - eps_est)
                        / abs(eps_est) * 100, 1
                    )
                quarters.append({
                    "quarter":              str(row.name)[:7],
                    "eps_actual":           float(eps_act) if eps_act else None,
                    "eps_consensus":        float(eps_est) if eps_est else None,
                    "eps_surprise_percent": surp_pct,
                    "beat":                 surp_pct > 0 if surp_pct else None,
                })

            quarters = quarters[:limit]
            if not quarters:
                return None

            beats = sum(1 for q in quarters if q.get("beat"))
            surprises = [
                q["eps_surprise_percent"]
                for q in quarters
                if q.get("eps_surprise_percent") is not None
            ]
            avg_surp = (
                round(sum(surprises) / len(surprises), 1)
                if surprises else None
            )

            return {
                "source":          "yfinance",
                "quarters_beat":   beats,
                "total_quarters":  len(quarters),
                "avg_surprise_percent": avg_surp,
                "all_quarters":    quarters,
            }
        except Exception:
            return None

    try:
        import asyncio
        return await asyncio.to_thread(_fetch)
    except Exception:
        return None
