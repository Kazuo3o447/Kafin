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

import json
import re

import yfinance as yf

from backend.app.cache import cache_get, cache_set
from backend.app.logger import get_logger
from backend.app.analysis.deepseek import call_deepseek

logger = get_logger(__name__)


async def analyze_chart(
    ticker: str,
    pre_market_price: float | None = None,
    pre_market_change: float | None = None,
) -> Dict:
    """Erstellt eine detaillierte technische Analyse für einen Ticker."""
    try:
        cache_key = f"chart_analysis:{ticker.upper()}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

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

        rsi_str = f"{rsi:.1f}" if rsi is not None else "N/A"
        sma_50_str = f"${sma_50:.2f}" if sma_50 else "N/A"
        sma_200_str = f"${sma_200:.2f}" if sma_200 else "N/A"

        # Pre-Market String
        pre_market_str = (
            f"PRE-MARKET: ${pre_market_price:.2f} "
            f"({pre_market_change:+.1f}%)\n"
            if pre_market_price is not None and pre_market_change is not None
            else ""
        )

        data_prompt = f"""Technische Analyse: {ticker}
{pre_market_str}KURS: ${current:.2f} | TREND: {trend} | RSI(14): {rsi_str}
SMA20: ${sma_20:.2f} | SMA50: {sma_50_str} | SMA200: {sma_200_str}
SUPPORT: ${support_20d:.2f} (20T) | RESISTANCE: ${resistance_20d:.2f} (20T)
52W: ${low_52w:.2f} — ${high_52w:.2f} ({((current-low_52w)/(high_52w-low_52w)*100):.0f}% der Range)
VOLUMEN: {vol_trend} ({vol_ratio:.1f}x)
LETZTE 5 TAGE: {' → '.join(last_5_days)}

Erstelle ein JSON-Objekt mit folgender Struktur:
{{
  "trend_analysis": "kurzer Text",
  "momentum_analysis": "kurzer Text",
  "levels": {{
    "buy_zone": {{"min": 100.0, "max": 105.0, "reason": "Text"}},
    "stop_loss": {{"price": 98.0, "reason": "Text"}},
    "targets": [
      {{"price": 115.0, "reason": "Text"}},
      {{"price": 125.0, "reason": "Text"}}
    ]
  }},
  "action": {{
    "recommendation": "BUY/HOLD/SELL",
    "condition": "Text"
  }},
  "risk_assessment": "Text"
}}
"""

        system_prompt = (
            "Du bist ein technischer Analyst. Analysiere die gegebenen Marktdaten und antworte "
            "AUSSCHLIESSLICH mit einem validen JSON-Objekt. Kein Text vor oder nach dem JSON. "
            "Keine Markdown-Backticks. Kein Kommentar. Alle Preise als Zahlen (nicht als Strings). "
            "Deutsch für Textfelder. "
            "Schreibe bei why_entry, why_stop, trend_context, floor_scenario und turnaround_conditions "
            "VOLLSTÄNDIGE 2-3 Sätze. Keine Abkürzungen. Der Trader muss das Setup verstehen ohne die Rohdaten zu sehen."
        )

        user_prompt = data_prompt + """

Antworte NUR mit diesem JSON (alle Felder Pflicht):
{
  "support_levels": [
    {"price": 0.00, "strength": "strong", "label": "20T-Tief"},
    {"price": 0.00, "strength": "moderate", "label": "SMA 50"}
  ],
  "resistance_levels": [
    {"price": 0.00, "strength": "strong", "label": "52W-Hoch"},
    {"price": 0.00, "strength": "weak", "label": "Vorwoche-Hoch"}
  ],
  "entry_zone": {"low": 0.00, "high": 0.00},
  "stop_loss": 0.00,
  "target_1": 0.00,
  "target_2": 0.00,
  "analysis_text": "3-4 Sätze narrative Einordnung",
  "bias": "bullish",
  "key_risk": "1 Satz Hauptrisiko",
  "why_entry": "1-2 Sätze: Warum genau diese Entry-Zone? Welche technische Struktur liegt dort?",
  "why_stop": "1-2 Sätze: Warum genau dieser Stop? Welches Level wird damit geschützt?",
  "trend_context": "1-2 Sätze: Ist der Trend intakt oder gebrochen? Wo stehen SMA50/200 relativ zum Kurs?",
  "floor_scenario": "1-2 Sätze: Wenn der Stop reisst — wo ist der nächste harte Support? Was wäre dann das Kursziel?",
  "turnaround_conditions": "1-2 Sätze: Was muss passieren damit sich ein Abwärtstrend dreht? Welche Signale brauchst du?",
  "falling_knife_risk": "low|medium|high"
}

strength: "strong"|"moderate"|"weak"
bias: "bullish"|"bearish"|"neutral"
falling_knife_risk: "low"|"medium"|"high"
Alle Preise als Zahlen. Kein Markdown."""

        raw_response = await call_deepseek(
            system_prompt,
            user_prompt,
            model="deepseek-chat",
            max_tokens=2048,    # war 512 → mehr Platz für Begründungen
            temperature=0.2,
        )

        ai_data = None
        parse_error = False
        cleaned = (raw_response or "").strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            ai_data = json.loads(cleaned) if cleaned else {}
        except (json.JSONDecodeError, Exception) as exc:  # noqa: BLE001
            logger.warning(f"Chart-Analyst JSON-Parse-Fehler für {ticker}: {exc}")
            parse_error = True

        if not parse_error and ai_data is None:
            parse_error = True

        if not parse_error:
            result = {
                "ticker": ticker,
                "price": round(current, 2),
                "rsi": round(rsi, 1) if rsi is not None else None,
                "trend": trend,
                "volume_trend": vol_trend,
                "sma_50": round(sma_50, 2) if sma_50 else None,
                "sma_200": round(sma_200, 2) if sma_200 else None,
                "support_levels": ai_data.get("support_levels", []),
                "resistance_levels": ai_data.get("resistance_levels", []),
                "entry_zone": ai_data.get("entry_zone", {}),
                "stop_loss": ai_data.get("stop_loss"),
                "target_1": ai_data.get("target_1"),
                "target_2": ai_data.get("target_2"),
                "analysis_text": ai_data.get("analysis_text", ""),
                "bias": ai_data.get("bias", "neutral"),
                "key_risk": ai_data.get("key_risk", ""),
                "why_entry":             ai_data.get("why_entry", ""),
                "why_stop":              ai_data.get("why_stop", ""),
                "trend_context":         ai_data.get("trend_context", ""),
                "floor_scenario":        ai_data.get("floor_scenario", ""),
                "turnaround_conditions": ai_data.get("turnaround_conditions", ""),
                "falling_knife_risk":    ai_data.get("falling_knife_risk", "medium"),
                "support": round(support_20d, 2),
                "resistance": round(resistance_20d, 2),
                "analysis": ai_data.get("analysis_text", ""),
                "error": False,
            }
            await cache_set(cache_key, result, ttl_seconds=600)
            return result

        fallback_support_levels = [
            {"price": round(support_20d, 2), "strength": "moderate", "label": "20T-Tief"},
            {"price": round(support_50d, 2), "strength": "weak", "label": "50T-Tief"},
        ]
        fallback_resistance_levels = [
            {"price": round(resistance_20d, 2), "strength": "moderate", "label": "20T-Hoch"},
            {"price": round(resistance_50d, 2), "strength": "weak", "label": "50T-Hoch"},
        ]

        return {
            "ticker": ticker,
            "price": round(current, 2),
            "rsi": round(rsi, 1) if rsi is not None else None,
            "trend": trend,
            "volume_trend": vol_trend,
            "sma_50": round(sma_50, 2) if sma_50 else None,
            "sma_200": round(sma_200, 2) if sma_200 else None,
            "support_levels": fallback_support_levels,
            "resistance_levels": fallback_resistance_levels,
            "entry_zone": {"low": round(support_20d, 2), "high": round(current * 1.01, 2)},
            "stop_loss": round(support_50d * 0.97, 2),
            "target_1": round(resistance_20d, 2),
            "target_2": round(resistance_50d, 2),
            "analysis_text": (raw_response or "")[:500],
            "bias": "neutral",
            "key_risk": "JSON-Parse-Fehler — Rohantwort in analysis_text",
            "why_entry": "",
            "why_stop": "",
            "trend_context": "",
            "floor_scenario": "",
            "turnaround_conditions": "",
            "falling_knife_risk": "medium",
            "support": round(support_20d, 2),
            "resistance": round(resistance_20d, 2),
            "analysis": (raw_response or "")[:500],
            "error": True,
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
