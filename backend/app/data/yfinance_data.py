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
from backend.app.config import settings
from backend.app.logger import get_logger

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

        return TechnicalSetup(
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
    except Exception as e:
        logger.error(f"yfinance Fehler für {ticker}: {e}")
        return TechnicalSetup(ticker=ticker, current_price=0.0)

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
