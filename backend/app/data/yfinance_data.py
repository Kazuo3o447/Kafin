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
from schemas.technicals import TechnicalSetup
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
