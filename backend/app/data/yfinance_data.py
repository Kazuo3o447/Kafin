"""
yfinance_data — Technische Daten via yfinance

Input:  ticker: str
Output: schemas/technicals.TechnicalSetup
Deps:   config.py
Config: config/settings.yaml → use_mock_data
API:    Yahoo Finance (via yfinance Bibliothek)
"""
import yfinance as yf
import json
import os
from datetime import datetime
from typing import Optional
from schemas.technicals import TechnicalSetup, OptionsMetrics
from schemas.options import OptionsData, OptionChainSummary
from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.cache import cache_get, cache_set
import numpy as np

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
    cached = cache_get(cache_key)
    if cached:
        logger.debug(f"yfinance Cache-Hit für {ticker}")
        return TechnicalSetup(**cached)

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

        result = TechnicalSetup(
            ticker=ticker,
            current_price=current_price,
            sma_50=round(sma_50, 2) if sma_50 else None,
            sma_200=round(sma_200, 2) if sma_200 else None,
            rsi_14=round(rsi_14, 2) if rsi_14 else None,
            high_52w=round(high_52w, 2),
            low_52w=round(low_52w, 2),
            distance_to_52w_high_percent=round(distance_to_52w_high, 2) if distance_to_52w_high else None,
            trend=trend,
            above_sma50=current_price > sma_50 if sma_50 else False,
            above_sma200=current_price > sma_200 if sma_200 else False,
        )
        cache_set(cache_key, result.dict(), ttl_seconds=300)
        return result
    except Exception as e:
        logger.error(f"yfinance Fehler für {ticker}: {e}")
        return TechnicalSetup(ticker=ticker, current_price=0.0)


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
        return OptionsMetrics(put_call_ratio_oi=1.1, implied_volatility_atm=0.25, expiration="2024-01-01")
        
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
        
        return OptionsMetrics(
            put_call_ratio_oi=round(pcr, 2),
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
    cached = cache_get(cache_key)
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
        cache_set(cache_key, result, ttl_seconds=3600)
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
