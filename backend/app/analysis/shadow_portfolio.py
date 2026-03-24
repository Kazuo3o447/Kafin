from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

import asyncio
import yfinance as yf

from backend.app.db import get_supabase_client
from backend.app.utils.timezone import now_mez
from backend.app.logger import get_logger

logger = get_logger(__name__)


def _current_quarter() -> str:
    now = now_mez()
    quarter = (now.month - 1) // 3 + 1
    return f"Q{quarter}_{now.year}"


def _normalize_trade_signal(recommendation: str) -> str:
    return recommendation.strip().upper().replace("_", " ")


async def _get_next_trading_day_close(ticker: str, after_date: datetime) -> float | None:
    try:
        def _fetch():
            stock = yf.Ticker(ticker)
            start = after_date.date()
            end = start + timedelta(days=7)
            return stock.history(start=str(start), end=str(end))

        hist = await asyncio.to_thread(_fetch)
        if hist.empty:
            logger.warning(f"Keine Kursdaten für {ticker} ab {after_date.date()}")
            return None
        return round(float(hist["Close"].iloc[0]), 4)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"_get_next_trading_day_close Fehler {ticker}: {exc}")
        return None


TRADE_SIGNALS = {
    "STRONG BUY": "long",
    "BUY MIT ABSICHERUNG": "long",
    "STRONG SHORT": "short",
    "POTENTIELLER SHORT": "short",
    "strong_buy": "long",
    "buy_hedge": "long",
    "strong_short": "short",
    "potential_short": "short",
    "STRONG BUY": "long",
    "BUY HEDGE": "long",
    "STRONG SHORT": "short",
    "POTENTIAL SHORT": "short",
}


async def open_shadow_trade(
    ticker: str,
    recommendation: str,
    opportunity_score: float,
    torpedo_score: float,
    audit_report_id: str | None = None,
    trade_reason: str | None = None,   # NEU
    manual_entry: bool = False,         # NEU
    atr_14: float | None = None,   # NEU — ATR aus TechnicalSetup
    reasoner_stop_loss: float | None = None,
) -> Dict[str, Any]:
    direction = TRADE_SIGNALS.get(recommendation) or TRADE_SIGNALS.get(_normalize_trade_signal(recommendation))
    if not direction:
        return {"skipped": True, "reason": f"Keine Trade-Signal-Empfehlung: {recommendation}"}

    quarter = _current_quarter()

    try:
        db = get_supabase_client()
        if db is None:
            return {"error": "Supabase nicht verfügbar"}
        existing = await (
            db.table("shadow_trades")
            .select("id")
            .eq("ticker", ticker)
            .eq("quarter", quarter)
            .eq("status", "open")
            .execute_async()
        )
        if existing.data:
            logger.info(f"Shadow Trade für {ticker}/{quarter} bereits offen — kein Duplikat")
            return {"skipped": True, "reason": "Trade bereits offen"}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Shadow Trade Duplikat-Check Fehler: {exc}")
        return {"error": str(exc)}

    entry_price = await _get_next_trading_day_close(ticker, now_mez())
    if not entry_price:
        logger.warning(f"Shadow Trade für {ticker} übersprungen: kein Entry-Preis")
        return {"skipped": True, "reason": "Entry-Preis nicht verfügbar"}

    # ALT — pauschal -8%
    # if direction == "long":
    #     stop_loss = round(entry_price * 0.92, 4)
    # else:
    #     stop_loss = round(entry_price * 1.08, 4)

    # NEU — Reasoner-Stop-Loss hat Vorrang, sonst ATR-basiert mit Fallback auf -8%
    ATR_MULTIPLIER = 1.5   # 1.5× ATR — Standardwert für Swing-Trades

    if reasoner_stop_loss and reasoner_stop_loss > 0:
        stop_loss = round(reasoner_stop_loss, 4)
        logger.info(f"Reasoner-Stop {ticker}: Exit-Anker ${stop_loss}")
    elif atr_14 and atr_14 > 0:
        stop_distance = round(atr_14 * ATR_MULTIPLIER, 4)
        if direction == "long":
            stop_loss = round(entry_price - stop_distance, 4)
        else:
            stop_loss = round(entry_price + stop_distance, 4)
        # Sicherheitsprüfung: Stop darf nicht unrealistisch nah sein
        pct_distance = abs(entry_price - stop_loss) / entry_price * 100
        if pct_distance < 2.0:
            # ATR zu klein (illiquider Titel) — Fallback auf 5%
            stop_loss = round(
                entry_price * (0.95 if direction == "long" else 1.05), 4
            )
        logger.info(
            f"ATR-Stop {ticker}: Entry ${entry_price} "
            f"ATR ${atr_14:.2f} × {ATR_MULTIPLIER} = "
            f"Stop ${stop_loss} ({pct_distance:.1f}%)"
        )
    else:
        # Fallback: -8% wenn kein ATR verfügbar
        if direction == "long":
            stop_loss = round(entry_price * 0.92, 4)
        else:
            stop_loss = round(entry_price * 1.08, 4)
        logger.info(
            f"Fallback-Stop {ticker}: kein ATR → ±8% = ${stop_loss}"
        )

    record = {
        "ticker": ticker,
        "quarter": quarter,
        "audit_report_id": audit_report_id,
        "signal_type": recommendation,
        "trade_direction": direction,
        "opportunity_score": round(opportunity_score, 2),
        "torpedo_score": round(torpedo_score, 2),
        "entry_price": entry_price,
        "entry_date": now_mez().isoformat(),
        "stop_loss_price": stop_loss,
        "position_size_usd": 10000,
        "status": "open",
        "trade_reason": trade_reason,  # NEU
        "manual_entry": manual_entry,  # NEU
        "created_at": now_mez().isoformat(),
    }

    try:
        db = get_supabase_client()
        if db is None:
            return {"error": "Supabase nicht verfügbar"}
        await db.table("shadow_trades").insert(record).execute_async()
        logger.info(f"Shadow Trade eröffnet: {ticker} {recommendation} @ ${entry_price}")
        return {"success": True, "ticker": ticker, "entry_price": entry_price}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Shadow Trade Insert Fehler {ticker}: {exc}")
        return {"error": str(exc)}


async def close_shadow_trade(ticker: str, quarter: str) -> Dict[str, Any]:
    try:
        db = get_supabase_client()
        if db is None:
            return {"error": "Supabase nicht verfügbar"}
        result = await (
            db.table("shadow_trades")
            .select("*")
            .eq("ticker", ticker)
            .eq("quarter", quarter)
            .eq("status", "open")
            .execute_async()
        )
        if not result.data:
            logger.info(f"Kein offener Shadow Trade für {ticker}/{quarter}")
            return {"skipped": True}
        trade = result.data[0]
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Shadow Trade Lookup Fehler {ticker}: {exc}")
        return {"error": str(exc)}

    exit_price = await _get_next_trading_day_close(ticker, now_mez() - timedelta(days=1))
    if not exit_price:
        logger.warning(f"Exit-Preis für {ticker} nicht verfügbar — Trade bleibt offen")
        return {"skipped": True, "reason": "Exit-Preis nicht verfügbar"}

    entry_price = trade.get("entry_price", 0)
    direction = trade.get("trade_direction", "long")
    stop_loss = trade.get("stop_loss_price")
    position_size = trade.get("position_size_usd", 10000)

    exit_reason = "post_earnings"
    actual_exit_price = exit_price

    if stop_loss and entry_price:
        try:
            entry_dt = datetime.fromisoformat(trade["entry_date"])
            
            def _fetch_stop_loss_check():
                return yf.Ticker(ticker).history(
                    start=entry_dt.date().isoformat(),
                    end=now_mez().date().isoformat(),
                )
            
            hist = await asyncio.to_thread(_fetch_stop_loss_check)
            if not hist.empty:
                if direction == "long":
                    min_low = float(hist["Low"].min())
                    if min_low <= stop_loss:
                        actual_exit_price = stop_loss
                        exit_reason = "stop_loss"
                else:
                    max_high = float(hist["High"].max())
                    if max_high >= stop_loss:
                        actual_exit_price = stop_loss
                        exit_reason = "stop_loss"
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Stop-Loss-Check Fehler {ticker}: {exc} — nutze Exit-Preis")

    # Wenn der Exit stark vom prognostizierten Stop-Loss abweicht, wird der
    # Reasoner-Stop als fairer Exit-Anker genommen (Gap-/Deviation-Schutz).
    if stop_loss and entry_price and exit_reason != "stop_loss":
        deviation_pct = abs(exit_price - stop_loss) / stop_loss * 100
        if deviation_pct >= 10.0:
            actual_exit_price = stop_loss
            exit_reason = "reasoner_stop_loss_deviation"

    if not entry_price:
        return {"error": "Entry-Preis fehlt"}

    if direction == "long":
        pnl_percent = ((actual_exit_price - entry_price) / entry_price) * 100
    else:
        pnl_percent = ((entry_price - actual_exit_price) / entry_price) * 100

    pnl_usd = (pnl_percent / 100) * position_size
    prediction_correct = pnl_percent > 0

    update_data = {
        "exit_price": round(actual_exit_price, 4),
        "exit_date": now_mez().isoformat(),
        "exit_reason": exit_reason,
        "pnl_usd": round(pnl_usd, 2),
        "pnl_percent": round(pnl_percent, 2),
        "prediction_correct": prediction_correct,
        "status": "closed",
    }

    try:
        db = get_supabase_client()
        if db is None:
            return {"error": "Supabase nicht verfügbar"}
        await db.table("shadow_trades").update(update_data).eq("id", trade["id"]).execute_async()
        logger.info(
            f"Shadow Trade geschlossen: {ticker} {quarter} PnL={pnl_percent:+.1f}% ({exit_reason})"
        )
        return {"success": True, "pnl_percent": pnl_percent, "exit_reason": exit_reason}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Shadow Trade Close Fehler {ticker}: {exc}")
        return {"error": str(exc)}


async def get_shadow_portfolio_summary() -> Dict[str, Any]:
    try:
        db = get_supabase_client()
        if db is None:
            return {"error": "Supabase nicht verfügbar", "open_trades": [], "closed_trades": []}
        all_trades = (await db.table("shadow_trades").select("*").execute_async()).data or []
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Shadow Portfolio Summary Fehler: {exc}")
        return {"error": str(exc), "open_trades": [], "closed_trades": []}

    open_trades = [t for t in all_trades if t.get("status") == "open"]
    closed_trades = [t for t in all_trades if t.get("status") == "closed"]

    open_with_pnl: List[Dict[str, Any]] = []
    for trade in open_trades:
        try:
            current_price = await _get_next_trading_day_close(
                trade["ticker"], now_mez() - timedelta(days=1)
            )
            if current_price and trade.get("entry_price"):
                entry = trade["entry_price"]
                direction = trade.get("trade_direction", "long")
                if direction == "long":
                    unrealized_pct = ((current_price - entry) / entry) * 100
                else:
                    unrealized_pct = ((entry - current_price) / entry) * 100
                open_with_pnl.append(
                    {
                        **trade,
                        "current_price": current_price,
                        "unrealized_pct": round(unrealized_pct, 2),
                    }
                )
            else:
                open_with_pnl.append({**trade, "current_price": None, "unrealized_pct": None})
        except Exception:
            open_with_pnl.append({**trade, "current_price": None, "unrealized_pct": None})

    reviewed = [t for t in closed_trades if t.get("prediction_correct") is not None]
    correct = [t for t in reviewed if t.get("prediction_correct") is True]
    win_rate = round(len(correct) / len(reviewed) * 100, 1) if reviewed else 0.0

    signal_types = [
        "STRONG BUY",
        "BUY MIT ABSICHERUNG",
        "STRONG SHORT",
        "POTENTIELLER SHORT",
    ]
    win_rate_by_signal: Dict[str, Dict[str, Any]] = {}
    for sig in signal_types:
        sig_trades = [t for t in reviewed if t.get("signal_type") == sig]
        sig_correct = [t for t in sig_trades if t.get("prediction_correct")]
        win_rate_by_signal[sig] = {
            "total": len(sig_trades),
            "correct": len(sig_correct),
            "win_rate_pct": round(len(sig_correct) / len(sig_trades) * 100, 1)
            if sig_trades
            else 0.0,
        }

    if closed_trades:
        sorted_by_pnl = sorted(closed_trades, key=lambda t: t.get("pnl_percent") or 0)
        worst = sorted_by_pnl[0]
        best = sorted_by_pnl[-1]
    else:
        best = worst = None

    avg_pnl = (
        round(sum(t.get("pnl_percent") or 0 for t in closed_trades) / len(closed_trades), 2)
        if closed_trades
        else 0.0
    )

    return {
        "open_count": len(open_trades),
        "closed_count": len(closed_trades),
        "win_rate_pct": win_rate,
        "win_rate_by_signal": win_rate_by_signal,
        "avg_pnl_pct": avg_pnl,
        "best_trade": {"ticker": best["ticker"], "pnl_pct": best.get("pnl_percent")} if best else None,
        "worst_trade": {"ticker": worst["ticker"], "pnl_pct": worst.get("pnl_percent")} if worst else None,
        "open_trades": open_with_pnl,
        "closed_trades": sorted(
            closed_trades, key=lambda t: t.get("exit_date") or "", reverse=True
        ),
    }


async def get_weekly_shadow_report() -> str:
    summary = await get_shadow_portfolio_summary()
    if "error" in summary:
        return "Shadow Portfolio: Daten nicht verfügbar."

    lines = [
        "─── SHADOW PORTFOLIO ───",
        f"Win Rate: {summary['win_rate_pct']}% ({summary['closed_count']} abgeschlossene Trades)",
        f"Ø PnL: {summary['avg_pnl_pct']:+.1f}%",
        "",
        f"Offene Positionen ({summary['open_count']}):",
    ]

    for trade in summary.get("open_trades", [])[:5]:
        unrealized = trade.get("unrealized_pct")
        unrealized_str = f" | Unreal: {unrealized:+.1f}%" if unrealized is not None else ""
        lines.append(
            f"  • {trade['ticker']} ({trade['signal_type']}) Entry: ${trade.get('entry_price', '?')}{unrealized_str}"
        )

    closed_this_week = [
        t
        for t in summary.get("closed_trades", [])
        if t.get("exit_date")
        and datetime.fromisoformat(t["exit_date"]) > now_mez() - timedelta(days=7)
    ]

    if closed_this_week:
        lines.append(f"\nDiese Woche geschlossen ({len(closed_this_week)}):")
        for trade in closed_this_week:
            result = "✓" if trade.get("prediction_correct") else "✗"
            lines.append(
                f"  {result} {trade['ticker']} {trade.get('pnl_percent', 0):+.1f}% ({trade.get('exit_reason', '?')})"
            )

    return "\n".join(lines)


# DB-Migration nötig (in Supabase SQL Editor):
# ALTER TABLE shadow_trades
#   ADD COLUMN IF NOT EXISTS trade_reason TEXT,
#   ADD COLUMN IF NOT EXISTS manual_entry BOOLEAN
#     DEFAULT FALSE;
