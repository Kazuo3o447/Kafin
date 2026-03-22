"""
signal_scanner — Scannt Watchlist-Ticker auf technische und Score-basierte Signale

Input:  Watchlist-Ticker
Output: Liste gefundener Signale + Telegram-Alerts
Deps:   yfinance_data.py, scoring.py, telegram.py, memory.watchlist
Config: config/alerts.yaml → signal_thresholds
API:    Yahoo Finance (yfinance)
"""

from __future__ import annotations

import yfinance as yf
from datetime import datetime
from typing import List, Dict

from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.alerts.telegram import send_telegram_alert
from backend.app.memory.watchlist import get_watchlist
from backend.app.db import get_supabase_client
from backend.app.cache import cache_get, cache_set

logger = get_logger(__name__)


async def scan_all_signals() -> List[Dict]:
    """Scannt alle Watchlist-Ticker auf technische Signale."""
    watchlist = await get_watchlist()
    signals_found: List[Dict] = []

    for item in watchlist:
        ticker = item.get("ticker")
        if not ticker:
            continue
        try:
            ticker_signals = await _check_ticker_signals(ticker)
            if ticker_signals:
                signals_found.extend(ticker_signals)
                for signal in ticker_signals:
                    await send_telegram_alert(signal["alert_text"])
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Signal-Scan für {ticker} fehlgeschlagen: {exc}")

    logger.info(f"Signal-Scan: {len(signals_found)} Signale für {len(watchlist)} Ticker")
    return signals_found


async def _check_ticker_signals(ticker: str) -> List[Dict]:
    """Prüft einen einzelnen Ticker auf alle definierten Signal-Typen."""
    signals: List[Dict] = []

    try:
        cache_key = f"signals:{ticker.upper()}"
        if cache_get(cache_key):
            return []

        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo")
        if hist.empty or len(hist) < 5:
            return signals

        close = hist["Close"]
        volume = hist["Volume"]
        current_price = float(close.iloc[-1])
        prev_close = float(close.iloc[-2])
        change_pct = ((current_price - prev_close) / prev_close) * 100

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1])

        # SMAs
        sma_20 = float(close.tail(20).mean())
        sma_50 = float(close.tail(50).mean()) if len(close) >= 50 else None

        # Volumen
        avg_volume = float(volume.tail(20).mean())
        current_volume = float(volume.iloc[-1])
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # SIGNAL 1: RSI Extrem
        if rsi <= 30:
            signals.append({
                "ticker": ticker,
                "type": "rsi_oversold",
                "alert_text": (
                    f"📉 RSI-Signal: {ticker}\nRSI = {rsi:.0f} (überverkauft)\n"
                    f"Kurs: ${current_price:.2f} ({change_pct:+.1f}%)\n"
                    "→ Potenzielle Kaufgelegenheit prüfen"
                ),
            })
        elif rsi >= 70:
            signals.append({
                "ticker": ticker,
                "type": "rsi_overbought",
                "alert_text": (
                    f"📈 RSI-Signal: {ticker}\nRSI = {rsi:.0f} (überkauft)\n"
                    f"Kurs: ${current_price:.2f} ({change_pct:+.1f}%)\n"
                    "→ Gewinnmitnahme oder Stop-Loss prüfen"
                ),
            })

        # SIGNAL 2: Starke Kursbewegung
        if abs(change_pct) >= 3.0:
            direction = "📈" if change_pct > 0 else "📉"
            signals.append({
                "ticker": ticker,
                "type": "large_move",
                "alert_text": (
                    f"{direction} Große Bewegung: {ticker}\n{change_pct:+.1f}% heute (${current_price:.2f})\n"
                    f"Volumen: {volume_ratio:.1f}x Durchschnitt\n→ Ursache prüfen"
                ),
            })

        # SIGNAL 3: Volumen-Anomalie
        if volume_ratio >= 2.5:
            signals.append({
                "ticker": ticker,
                "type": "volume_spike",
                "alert_text": (
                    f"🔊 Volumen-Spike: {ticker}\n{volume_ratio:.1f}x normales Volumen\n"
                    f"Kurs: ${current_price:.2f} ({change_pct:+.1f}%)\n→ Institutionelle Aktivität möglich"
                ),
            })

        # SIGNAL 4: SMA50 Cross
        if sma_50 and len(close) >= 51:
            prev_avg_50 = float(close.tail(51).head(50).mean())
            prev_above = float(close.iloc[-2]) > prev_avg_50
            curr_above = current_price > sma_50

            if not prev_above and curr_above:
                signals.append({
                    "ticker": ticker,
                    "type": "sma50_cross_up",
                    "alert_text": (
                        f"🔼 SMA50-Cross UP: {ticker}\n"
                        f"Kurs ${current_price:.2f} über SMA50 (${sma_50:.2f})\n→ Bullisches Signal"
                    ),
                })
            elif prev_above and not curr_above:
                signals.append({
                    "ticker": ticker,
                    "type": "sma50_cross_down",
                    "alert_text": (
                        f"🔽 SMA50-Cross DOWN: {ticker}\n"
                        f"Kurs ${current_price:.2f} unter SMA50 (${sma_50:.2f})\n→ Bärisches Signal"
                    ),
                })

        # SIGNAL 5: Score-Veränderung
        try:
            db = get_supabase_client()
            if db:
                result = await (
                    db.table("score_history")
                    .select("*")
                    .eq("ticker", ticker)
                    .order("date", desc=True)
                    .limit(2)
                    .execute_async()
                )
                data = result.data if result and result.data else []
                if len(data) >= 2:
                    today = data[0]
                    yesterday = data[1]
                    torp_delta = (today.get("torpedo_score") or 0) - (yesterday.get("torpedo_score") or 0)
                    if torp_delta >= 2.0:
                        signals.append({
                            "ticker": ticker,
                            "type": "torpedo_spike",
                            "alert_text": (
                                f"🚨 Torpedo-Score Anstieg: {ticker}\n"
                                f"{yesterday.get('torpedo_score', 0):.1f} → {today.get('torpedo_score', 0):.1f} (+{torp_delta:.1f})\n"
                                "→ Risiko hat sich deutlich erhöht!"
                            ),
                        })
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Score-History Check {ticker}: {exc}")

        cache_set(cache_key, True, ttl_seconds=300)

    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Signal-Check für {ticker} fehlgeschlagen: {exc}")

    return signals
