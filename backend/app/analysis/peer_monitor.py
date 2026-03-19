"""
peer_monitor — Sector Peer Review System.

Zwei Funktionen:
1. check_peer_earnings_today():
   Prüft ob ein Cross-Signal-Ticker heute oder morgen reported.
   → Telegram-Alert: "AMD meldet morgen — NVDA könnte reagieren"

2. calculate_peer_reaction(reporter, move_pct):
   Nach Earnings eines Tickers: berechnet erwartete Peer-Reaktion
   basierend auf historischer 30-Tage Beta-Korrelation.
   → Telegram-Alert: "NVDA +8% AH — erwartet: AMD +4.1%, SMCI +5.3%"
"""
import asyncio
from datetime import datetime, timedelta, date, timezone
from typing import Optional

from backend.app.memory.watchlist import get_watchlist
from backend.app.alerts.telegram import send_telegram_alert
from backend.app.logger import get_logger

logger = get_logger(__name__)

# Cooldown zwischen Peer-Alerts (Stunden)
PEER_ALERT_COOLDOWN_HOURS = 12


async def _calculate_beta(
    ticker: str, reference: str, days: int = 30
) -> Optional[float]:
    """
    Berechnet einfache Preis-Korrelation (Beta-Näherung) zwischen
    ticker und reference über die letzten 30 Tage.
    Beta > 1: ticker bewegt sich stärker als reference.
    """
    try:
        def _fetch():
            import yfinance as yf
            import pandas as pd

            t = yf.Ticker(ticker)
            r = yf.Ticker(reference)
            hist_t = t.history(period=f"{days + 5}d")["Close"]
            hist_r = r.history(period=f"{days + 5}d")["Close"]

            if hist_t.empty or hist_r.empty:
                return None

            # Auf gleiche Daten trimmen
            combined = pd.DataFrame({"t": hist_t, "r": hist_r}).dropna()
            if len(combined) < 5:
                return None

            returns_t = combined["t"].pct_change().dropna()
            returns_r = combined["r"].pct_change().dropna()

            if returns_r.var() == 0:
                return None

            beta = returns_t.cov(returns_r) / returns_r.var()
            return round(float(beta), 2)

        return await asyncio.to_thread(_fetch)

    except Exception as e:
        logger.debug(f"Beta {ticker}/{reference}: {e}")
        return None


async def _check_alert_cooldown(key: str) -> bool:
    """Prüft Cooldown via system_logs. True = Alert erlaubt."""
    try:
        from backend.app.db import get_supabase_client
        db = get_supabase_client()
        if not db:
            return True
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(hours=PEER_ALERT_COOLDOWN_HOURS)
        ).isoformat()
        res = (
            db.table("system_logs")
            .select("created_at")
            .eq("component", "peer_monitor")
            .eq("message", f"alert_sent:{key}")
            .gte("created_at", cutoff)
            .limit(1)
            .execute()
        )
        rows = res.data if res and res.data else []
        return len(rows) == 0
    except Exception:
        return True


async def _log_alert(key: str) -> None:
    """Speichert Alert-Zeitstempel für Cooldown."""
    try:
        from backend.app.db import get_supabase_client
        db = get_supabase_client()
        if db:
            db.table("system_logs").insert({
                "component": "peer_monitor",
                "level": "INFO",
                "message": f"alert_sent:{key}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
    except Exception:
        pass


async def check_peer_earnings_today() -> dict:
    """
    Prüft ob Cross-Signal-Ticker in den nächsten 2 Tagen reporten.
    Wenn ja → Alert an Watchlist-Ticker-Besitzer.

    Ablauf:
    1. Earnings-Kalender der nächsten 2 Tage laden
    2. Für jeden Watchlist-Ticker: cross_signal_tickers prüfen
    3. Wenn ein Cross-Signal in den Earnings ist → Alert
    """
    from backend.app.data.finnhub import get_earnings_calendar

    today = date.today()
    in_2_days = today + timedelta(days=2)

    try:
        calendar = await get_earnings_calendar(
            today.isoformat(), in_2_days.isoformat()
        )
    except Exception as e:
        logger.warning(f"Peer Monitor Kalender: {e}")
        return {"status": "error", "alerts_sent": 0}

    # Reporting-Ticker aus Kalender
    reporting_today = {
        getattr(e, "ticker", "").upper(): {
            "report_date": str(getattr(e, "report_date", today)),
            "report_timing": getattr(e, "report_timing", None),
            "eps_consensus": getattr(e, "eps_consensus", None),
        }
        for e in (calendar or [])
        if getattr(e, "ticker", None)
    }

    if not reporting_today:
        return {"status": "ok", "alerts_sent": 0, "checked": 0}

    wl = await get_watchlist()
    alerts_sent = 0

    for item in wl:
        wl_ticker = item.get("ticker", "").upper()
        cross_signals = item.get("cross_signal_tickers") or \
                        item.get("cross_signals") or []

        for peer in cross_signals:
            peer_upper = peer.upper()
            if peer_upper not in reporting_today:
                continue

            # Cooldown prüfen
            cooldown_key = f"{wl_ticker}_{peer_upper}_pre"
            if not await _check_alert_cooldown(cooldown_key):
                continue

            peer_data = reporting_today[peer_upper]
            timing = peer_data.get("report_timing") or ""
            timing_str = (
                "Pre-Market 🌅" if timing == "pre_market"
                else "After-Hours 🌙" if timing == "after_hours"
                else ""
            )
            eps_str = (
                f"EPS-Konsens: ${peer_data['eps_consensus']:.2f}"
                if peer_data.get("eps_consensus")
                else ""
            )
            date_str = peer_data["report_date"]
            days_until = (
                date.fromisoformat(date_str) - today
            ).days if date_str else 0

            when = "HEUTE" if days_until == 0 else "MORGEN"

            message = (
                f"🔗 <b>PEER EARNINGS: {peer_upper} meldet {when}</b>\n"
                f"Relevant für deinen Watchlist-Ticker: "
                f"<b>{wl_ticker}</b>\n\n"
                f"📅 {date_str} {timing_str}\n"
                f"{eps_str + chr(10) if eps_str else ''}"
                f"\nHistorische Reaktion: {wl_ticker} bewegt sich "
                f"oft nach {peer_upper}-Earnings.\n"
                f"⚠️ Positionierung prüfen!"
            )

            success = await send_telegram_alert(message)
            if success:
                await _log_alert(cooldown_key)
                alerts_sent += 1
                logger.info(
                    f"Peer Alert: {peer_upper} meldet {when} "
                    f"— relevant für {wl_ticker}"
                )

    return {
        "status": "ok",
        "alerts_sent": alerts_sent,
        "reporting_today": list(reporting_today.keys()),
    }


async def send_peer_reaction_alert(
    reporter: str,
    move_pct: float,
    report_timing: str = "after_hours",
) -> dict:
    """
    Nach Earnings eines Tickers: berechnet und meldet erwartete
    Peer-Reaktion basierend auf Beta-Korrelation.

    reporter: Ticker der gerade reported hat (z.B. "NVDA")
    move_pct: Kursreaktion in % (z.B. +8.5 oder -4.2)
    """
    wl = await get_watchlist()
    alerts_sent = 0
    peer_results = []

    # Welche Watchlist-Ticker haben reporter als Cross-Signal?
    affected_pairs = []
    for item in wl:
        wl_ticker = item.get("ticker", "").upper()
        cross_signals = item.get("cross_signal_tickers") or \
                        item.get("cross_signals") or []
        if reporter.upper() in [c.upper() for c in cross_signals]:
            affected_pairs.append((wl_ticker, item))

    if not affected_pairs:
        return {"status": "ok", "alerts_sent": 0, "no_peers": True}

    # Beta für alle betroffenen Ticker parallel berechnen
    betas = await asyncio.gather(
        *[_calculate_beta(wl_t, reporter.upper())
          for wl_t, _ in affected_pairs],
        return_exceptions=True,
    )

    peer_lines = []
    for (wl_ticker, _), beta in zip(affected_pairs, betas):
        if isinstance(beta, Exception) or beta is None:
            peer_lines.append(f"• {wl_ticker}: Beta N/A")
            peer_results.append({"ticker": wl_ticker, "beta": None})
            continue

        expected_move = round(move_pct * beta, 1)
        direction = "📈" if expected_move >= 0 else "📉"
        peer_lines.append(
            f"• <b>{wl_ticker}</b>: Beta {beta:.2f} → "
            f"erwartet {direction} "
            f"{'+' if expected_move >= 0 else ''}{expected_move:.1f}%"
        )
        peer_results.append({
            "ticker": wl_ticker,
            "beta": beta,
            "expected_move_pct": expected_move,
        })

    if not peer_lines:
        return {"status": "ok", "alerts_sent": 0}

    # Cooldown prüfen
    cooldown_key = f"{reporter.upper()}_post_{date.today().isoformat()}"
    if not await _check_alert_cooldown(cooldown_key):
        return {"status": "ok", "alerts_sent": 0, "cooldown": True}

    reporter_direction = "📈" if move_pct >= 0 else "📉"
    timing_str = (
        "🌙 After-Hours" if report_timing == "after_hours"
        else "🌅 Pre-Market" if report_timing == "pre_market"
        else ""
    )

    message = (
        f"🔗 <b>PEER REACTION: {reporter.upper()} "
        f"{reporter_direction} {'+' if move_pct >= 0 else ''}"
        f"{move_pct:.1f}% {timing_str}</b>\n\n"
        f"Erwartete Reaktion deiner Watchlist-Peers:\n"
        + "\n".join(peer_lines)
        + "\n\n<i>Basierend auf 30-Tage Beta-Korrelation.</i>"
        + f"\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')} CET"
    )

    success = await send_telegram_alert(message)
    if success:
        await _log_alert(cooldown_key)
        alerts_sent += 1

    return {
        "status": "ok",
        "alerts_sent": alerts_sent,
        "reporter": reporter,
        "move_pct": move_pct,
        "peers": peer_results,
    }
