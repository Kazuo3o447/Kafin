"""
opportunity_scanner — Findet interessante Earnings-Setups außerhalb der Watchlist

Input:  Earnings-Kalender (nächste 7 Tage)
Output: Liste mit Top-Kandidaten + Kurz-Analyse
Deps:   finnhub.py, yfinance_data.py, deepseek.py
Config: Keine
API:    Finnhub (Earnings Calendar), Yahoo Finance (yfinance)
"""

from __future__ import annotations

import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict

from backend.app.logger import get_logger
from backend.app.data.finnhub import get_earnings_calendar
from backend.app.analysis.deepseek import call_deepseek

logger = get_logger(__name__)


async def scan_upcoming_opportunities(days_ahead: int = 7, max_results: int = 5) -> List[Dict]:
    """Scannt den Earnings-Kalender und findet spannende Setups."""
    today = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    logger.info(f"Opportunity-Scanner: {today} bis {future}")

    try:
        calendar = await get_earnings_calendar(today, future)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Earnings-Kalender Fehler: {exc}")
        return []

    if not calendar:
        return []

    candidates: List[Dict] = []
    for event in calendar:
        ticker = getattr(event, "ticker", getattr(event, "symbol", None))
        if not ticker:
            continue

        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            mcap = info.get("marketCap", 0)
            if not mcap or mcap < 10_000_000_000:
                continue

            hist = stock.history(period="3mo")
            if hist.empty or len(hist) < 20:
                continue

            close = hist["Close"]
            current = float(close.iloc[-1])

            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = float((100 - (100 / (1 + rs))).iloc[-1])

            returns = close.pct_change().tail(20)
            volatility = float(returns.std() * (252 ** 0.5) * 100)

            sma50 = float(close.tail(50).mean()) if len(close) >= 50 else None
            above_sma50 = current > sma50 if sma50 else None

            interest_score = 0
            if rsi < 35:
                interest_score += 3
            elif rsi > 70:
                interest_score += 2
            if volatility > 40:
                interest_score += 2
            if mcap > 100_000_000_000:
                interest_score += 1

            try:
                earnings_history = getattr(stock, "earnings_history", None)
                if earnings_history is not None and len(earnings_history) > 0:
                    interest_score += 1
            except Exception:  # noqa: BLE001
                pass

            if interest_score >= 2:
                candidates.append({
                    "ticker": ticker,
                    "name": info.get("shortName", ticker),
                    "sector": info.get("sector", "Unknown"),
                    "market_cap_b": round(mcap / 1e9, 1),
                    "price": round(current, 2),
                    "rsi": round(rsi, 1),
                    "volatility": round(volatility, 1),
                    "above_sma50": above_sma50,
                    "interest_score": interest_score,
                    "earnings_date": getattr(event, "date", getattr(event, "report_date", "?")),
                })
        except Exception:  # noqa: BLE001
            continue

    candidates.sort(key=lambda c: c["interest_score"], reverse=True)
    top = candidates[:max_results]

    if top:
        top = await _enrich_with_analysis(top)

    logger.info(f"Opportunity-Scanner: {len(top)} Kandidaten gefunden")
    return top


async def _enrich_with_analysis(candidates: List[Dict]) -> List[Dict]:
    lines = []
    for c in candidates:
        trend_word = "über" if c.get("above_sma50") else "unter"
        lines.append(
            f"{c['ticker']} ({c['name']}): ${c['price']}, RSI {c['rsi']}, Vola {c['volatility']}%, {trend_word} SMA50, "
            f"MCap ${c['market_cap_b']}B, Earnings am {c['earnings_date']}"
        )

    prompt = (
        "Analysiere diese Aktien, die nächste Woche Earnings melden. Für jede: 1 Satz Setup-Beschreibung, "
        "1 Satz Risiko, 1 Satz ob es sich lohnt genauer hinzuschauen. Auf Deutsch, kompakt.\n\n"
        + "\n".join(lines)
    )

    try:
        result = await call_deepseek(
            "Du bist ein Trader-Scout. Bewerte Earnings-Setups kurz und präzise.",
            prompt,
        )
        if candidates:
            candidates[0]["analysis_full"] = result
        for c in candidates:
            c["analysis"] = "Analyse verfügbar"
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Opportunity-Analyse Fehler: {exc}")
        for c in candidates:
            c["analysis"] = "Analyse nicht verfügbar"

    return candidates
