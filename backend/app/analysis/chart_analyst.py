"""
chart_analyst — DeepSeek analysiert technische Daten und liefert konkrete Levels

Input:  Ticker (oder Watchlist Top-N)
Output: Handlungsempfehlungen inkl. Kauf-/Stop-/Zielzonen
Deps:   yfinance_data (für technische Kennzahlen), deepseek, memory.watchlist
Config: Keine
API:    Yahoo Finance (yfinance)
"""

from __future__ import annotations

from typing import List, Dict

import yfinance as yf

from backend.app.logger import get_logger
from backend.app.analysis.deepseek import call_deepseek

logger = get_logger(__name__)


async def analyze_chart(ticker: str) -> Dict:
    """Erstellt eine detaillierte technische Analyse für einen Ticker."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")
        if hist.empty:
            return {"ticker": ticker, "error": "Keine Daten verfügbar"}

        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        volume = hist["Volume"]

        current = float(close.iloc[-1])
        sma_20 = float(close.tail(20).mean())
        sma_50 = float(close.tail(50).mean()) if len(close) >= 50 else None
        sma_200 = float(close.tail(200).mean()) if len(close) >= 200 else None

        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss_val = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss_val
        rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else None

        support_20d = float(low.tail(20).min())
        resistance_20d = float(high.tail(20).max())
        support_50d = float(low.tail(50).min()) if len(low) >= 50 else support_20d
        resistance_50d = float(high.tail(50).max()) if len(high) >= 50 else resistance_20d

        high_52w = float(high.max())
        low_52w = float(low.min())

        vol_20d_avg = float(volume.tail(20).mean())
        vol_5d_avg = float(volume.tail(5).mean())
        vol_ratio = vol_5d_avg / vol_20d_avg if vol_20d_avg else 1.0
        vol_trend = "steigend" if vol_ratio > 1.2 else "fallend" if vol_ratio < 0.8 else "normal"

        trend = "seitwärts"
        if sma_50 and sma_200:
            if current > sma_50 > sma_200:
                trend = "Aufwärtstrend"
            elif current < sma_50 < sma_200:
                trend = "Abwärtstrend"

        last_5_days: List[str] = []
        for idx in range(-5, 0):
            if abs(idx) <= len(close):
                day_close = float(close.iloc[idx])
                prev_idx = idx - 1
                prev_close_val = float(close.iloc[prev_idx]) if abs(prev_idx) <= len(close) else day_close
                change = ((day_close - prev_close_val) / prev_close_val) * 100 if prev_close_val else 0
                last_5_days.append(f"${day_close:.2f} ({change:+.1f}%)")

        data_prompt = f"""Technische Analyse: {ticker}
KURS: ${current:.2f} | TREND: {trend} | RSI(14): {rsi:.1f if rsi is not None else 'N/A'}
SMA20: ${sma_20:.2f} | SMA50: ${sma_50:.2f if sma_50 else 'N/A'} | SMA200: ${sma_200:.2f if sma_200 else 'N/A'}
SUPPORT: ${support_20d:.2f} (20T) | RESISTANCE: ${resistance_20d:.2f} (20T)
52W: ${low_52w:.2f} — ${high_52w:.2f} ({((current-low_52w)/(high_52w-low_52w)*100):.0f}% der Range)
VOLUMEN: {vol_trend} ({vol_ratio:.1f}x)
LETZTE 5 TAGE: {' → '.join(last_5_days)}

Erstelle die Analyse EXAKT so:
TREND: [1 Satz]
MOMENTUM: [1 Satz]
LEVELS:
• Kaufzone: $X — $Y [Begründung]
• Stop-Loss: $X [Begründung]
• Kursziel 1: $X [Begründung]
• Kursziel 2: $X [Begründung]
HANDLUNG: [Kaufen/Halten/Reduzieren + Bedingung]
RISIKO: [1 Satz]
"""

        analysis_text = await call_deepseek(
            "Du bist ein technischer Analyst. Liefere KONKRETE Preis-Levels. Keine vagen Aussagen. Deutsch. Max 12 Zeilen.",
            data_prompt,
            model="deepseek-reasoner",
        )

        return {
            "ticker": ticker,
            "price": round(current, 2),
            "rsi": round(rsi, 1) if rsi is not None else None,
            "trend": trend,
            "support": round(support_20d, 2),
            "resistance": round(resistance_20d, 2),
            "analysis": analysis_text,
            "volume_trend": vol_trend,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Chart-Analyse Fehler für {ticker}: {exc}")
        return {"ticker": ticker, "error": str(exc)}


async def analyze_top_watchlist(limit: int = 5) -> List[Dict]:
    """Analysiert die Top-N Watchlist-Ticker."""
    from backend.app.memory.watchlist import get_watchlist

    watchlist = await get_watchlist()
    results: List[Dict] = []

    for item in watchlist[:limit]:
        ticker = item.get("ticker")
        if not ticker:
            continue
        results.append(await analyze_chart(ticker))

    return results
