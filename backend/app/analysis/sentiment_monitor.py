"""
sentiment_monitor — Erkennt Sentiment-Divergenz-Signale.

Prüft stündlich für alle Watchlist-Ticker:
  - Kurs gestiegen (>+2% in 2h)?
  - Sentiment gleichzeitig gefallen (>0.3 Punkte)?
  → Telegram-Alert: "Kurs steigt, Sentiment kippt"

Zusätzlich:
  - FinBERT vs. Web-Sentiment Divergenz (aus web_intelligence_cache)
  → Alert wenn |FinBERT - Web| > 0.4

Letzte Alert-Zeit wird in Supabase gespeichert um Spam zu vermeiden
(min. 4h zwischen Alerts pro Ticker).
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import yaml, os

from backend.app.logger import get_logger
from backend.app.memory.short_term import get_bullet_points_batch
from backend.app.alerts.telegram import send_telegram_alert
from backend.app.utils.timezone import now_mez
from backend.app.logger import get_logger

logger = get_logger(__name__)

def _load_alert_config() -> dict:
    try:
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "config", "alerts.yaml"
        )
        with open(os.path.abspath(config_path)) as f:
            return yaml.safe_load(f).get("sentiment_monitor", {})
    except Exception:
        return {}

_cfg = _load_alert_config()
ALERT_COOLDOWN_HOURS     = _cfg.get("cooldown_hours", 4)
PRICE_RISE_THRESHOLD     = _cfg.get("price_rise_threshold", 2.0)
SENTIMENT_DROP_THRESHOLD = _cfg.get("sentiment_drop_threshold", 0.30)
DIVERGENCE_THRESHOLD     = _cfg.get("divergence_threshold", 0.40)


async def _get_price_change_2h(ticker: str) -> Optional[float]:
    """
    Holt 2h-Kursveränderung via yfinance.
    Gibt Prozent zurück oder None wenn keine Daten.
    """
    try:
        def _fetch():
            import yfinance as yf
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d", interval="1h")
            if hist.empty or len(hist) < 2:
                return None
            p_now = float(hist["Close"].iloc[-1])
            p_2h_ago = float(hist["Close"].iloc[-2])
            if p_2h_ago <= 0:
                return None
            return round(((p_now - p_2h_ago) / p_2h_ago) * 100, 2)

        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.debug(f"Price 2h {ticker}: {e}")
        return None


async def _get_recent_sentiment_delta(ticker: str) -> Optional[float]:
    """
    Berechnet Sentiment-Delta der letzten 2 Stunden.
    Vergleicht neueste News-Stichpunkte mit älteren.
    Gibt negative Zahl zurück wenn Sentiment gefallen.
    """
    try:
        bullets = await get_bullet_points(ticker)
        if not bullets or len(bullets) < 2:
            return None

        now = datetime.now(timezone.utc)
        cutoff_2h = now - timedelta(hours=2)
        cutoff_6h = now - timedelta(hours=6)

        recent_scores = []
        older_scores = []

        for b in bullets:
            score = b.get("sentiment_score")
            created_str = b.get("created_at")
            if score is None or not created_str:
                continue
            try:
                created = datetime.fromisoformat(
                    created_str.replace("Z", "+00:00")
                )
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created >= cutoff_2h:
                    recent_scores.append(float(score))
                elif created >= cutoff_6h:
                    older_scores.append(float(score))
            except Exception:
                continue

        if not recent_scores or not older_scores:
            return None

        avg_recent = sum(recent_scores) / len(recent_scores)
        avg_older = sum(older_scores) / len(older_scores)
        return round(avg_recent - avg_older, 3)  # Negativ = Sentiment fällt

    except Exception as e:
        logger.debug(f"Sentiment delta {ticker}: {e}")
        return None


async def _get_web_divergence(ticker: str) -> Optional[tuple[float, float, str]]:
    """
    Liest FinBERT vs. Web-Sentiment aus web_intelligence_cache.
    Gibt (finbert_score, web_score, divergence_text) oder None zurück.
    """
    try:
        from backend.app.db import get_supabase_client
        db = get_supabase_client()
        if not db:
            return None

        # Web-Score aus Cache
        res = (
            db.table("web_intelligence_cache")
            .select("summary, searched_at")
            .eq("ticker", ticker.upper())
            .execute()
        )
        rows = res.data if res and res.data else []
        if not rows:
            return None

        cache_row = rows[0]
        # Nur frische Cache-Einträge nutzen (max 12h alt)
        searched_str = cache_row.get("searched_at", "")
        if searched_str:
            try:
                searched = datetime.fromisoformat(
                    searched_str.replace("Z", "+00:00")
                )
                if searched.tzinfo is None:
                    searched = searched.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - searched > timedelta(hours=12):
                    return None
            except Exception:
                pass

        # FinBERT aus News-Memory
        bullets = await get_bullet_points(ticker)
        if not bullets:
            return None
        scores = [
            float(b.get("sentiment_score", 0))
            for b in bullets
            if b.get("sentiment_score") is not None
        ]
        if not scores:
            return None
        finbert_avg = round(sum(scores) / len(scores), 3)

        # Web-Score via DeepSeek aus Cache-Summary
        summary = cache_row.get("summary", "")
        if not summary or len(summary) < 20:
            return None

        try:
            from backend.app.data.web_search import get_web_sentiment_score
            web_score, web_label = await get_web_sentiment_score(
                ticker=ticker
            )
        except Exception:
            return None

        divergence = abs(finbert_avg - web_score)
        if divergence < DIVERGENCE_THRESHOLD:
            return None

        direction = "bärisch" if finbert_avg > web_score else "bullisch"
        text = (
            f"News {'+' if finbert_avg >= 0 else ''}{finbert_avg:.2f} "
            f"aber Web-Diskurs {'+' if web_score >= 0 else ''}{web_score:.2f} "
            f"({direction})"
        )
        return finbert_avg, web_score, text

    except Exception as e:
        logger.debug(f"Web divergence {ticker}: {e}")
        return None


async def _check_alert_cooldown(ticker: str) -> bool:
    """
    Prüft ob in letzten ALERT_COOLDOWN_HOURS bereits ein
    Sentiment-Alert für diesen Ticker gesendet wurde.
    Gibt True zurück wenn Alert erlaubt (kein Cooldown aktiv).
    """
    try:
        from backend.app.db import get_supabase_client
        db = get_supabase_client()
        if not db:
            return True

        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=ALERT_COOLDOWN_HOURS)
        ).isoformat()

        res = (
            db.table("system_logs")
            .select("created_at")
            .eq("component", "sentiment_monitor")
            .eq("message", f"alert_sent:{ticker.upper()}")
            .gte("created_at", cutoff)
            .limit(1)
            .execute()
        )
        rows = res.data if res and res.data else []
        return len(rows) == 0  # True = kein Cooldown = Alert erlaubt

    except Exception as e:
        logger.debug(f"Cooldown check {ticker}: {e}")
        return True


async def _log_alert_sent(ticker: str) -> None:
    """Speichert dass Alert gesendet wurde (für Cooldown-Check)."""
    try:
        from backend.app.db import get_supabase_client
        db = get_supabase_client()
        if db:
            db.table("system_logs").insert({
                "component": "sentiment_monitor",
                "level": "WARNING",
                "message": f"alert_sent:{ticker.upper()}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
    except Exception as e:
        logger.debug(f"Log alert {ticker}: {e}")


async def check_sentiment_divergence() -> dict:
    """
    Hauptfunktion — prüft alle Watchlist-Ticker.
    Wird von n8n stündlich aufgerufen.
    """
    logger.info("Sentiment Monitor: Starte Divergenz-Check")

    wl = await get_watchlist()
    if not wl:
        return {"status": "ok", "alerts_sent": 0, "checked": 0}

    async def _check_single(item: dict) -> dict:
        ticker = item.get("ticker", "").upper()
        if not ticker:
            return {"ticker": ticker, "sent": False}
        try:
            if not await _check_alert_cooldown(ticker):
                return {"ticker": ticker, "sent": False, "reason": "cooldown"}

            alert_parts = []

            price_change, sentiment_delta = await asyncio.gather(
                _get_price_change_2h(ticker),
                _get_recent_sentiment_delta(ticker),
                return_exceptions=True,
            )

            if (
                isinstance(price_change, float)
                and isinstance(sentiment_delta, float)
                and price_change >= PRICE_RISE_THRESHOLD
                and sentiment_delta <= -SENTIMENT_DROP_THRESHOLD
            ):
                alert_parts.append(
                    f"📈 Kurs +{price_change:.1f}% (2h) aber "
                    f"Sentiment {sentiment_delta:+.2f} — "
                    f"mögliches lokales Top"
                )
                logger.warning(
                    f"[{ticker}] Divergenz: Kurs +{price_change:.1f}% | "
                    f"Sentiment {sentiment_delta:+.2f}"
                )

            divergence_result = await _get_web_divergence(ticker)
            if divergence_result:
                _, _, div_text = divergence_result
                alert_parts.append(f"⚖️ Sentiment-Divergenz: {div_text}")

            if not alert_parts:
                return {"ticker": ticker, "sent": False}

            company = item.get("company_name", ticker)
            message = (
                f"🚨 <b>SENTIMENT ALERT: {ticker}</b>\n"
                f"<i>{company}</i>\n\n"
                + "\n\n".join(alert_parts)
                + f"\n\n⏰ {now_mez().strftime('%d.%m.%Y %H:%M')} CET"
                + f"\n🔗 /watchlist/{ticker}"
            )
            success = await send_telegram_alert(message)
            if success:
                await _log_alert_sent(ticker)
                return {"ticker": ticker, "sent": True}
        except Exception as e:
            logger.warning(f"Sentiment Monitor {ticker}: {e}")
        return {"ticker": ticker, "sent": False}

    # Parallel in 5er-Chunks (yfinance Rate-Limit respektieren)
    CHUNK_SIZE = 5
    results_all = []
    for i in range(0, len(wl), CHUNK_SIZE):
        chunk = wl[i:i + CHUNK_SIZE]
        chunk_results = await asyncio.gather(
            *[_check_single(item) for item in chunk],
            return_exceptions=True,
        )
        results_all.extend(chunk_results)

    alerts_sent = sum(
        1 for r in results_all
        if isinstance(r, dict) and r.get("sent")
    )
    checked = len(wl)

    logger.info(
        f"Sentiment Monitor: {checked} geprüft, {alerts_sent} Alerts"
    )
    return {
        "status": "ok",
        "checked": checked,
        "alerts_sent": alerts_sent,
    }
