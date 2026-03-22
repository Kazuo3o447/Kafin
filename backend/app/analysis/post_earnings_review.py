"""
post_earnings_review — Automatischer Vergleich: Was hat Kafin empfohlen vs. was ist passiert?

Input:  Ticker, Quartals-Ergebnis
Output: Review-Analyse, Langzeit-Insights, Performance-Update
Deps:   deepseek.py, memory/long_term.py, fmp.py, yfinance_data.py
Config: Keine
API:    DeepSeek, FMP, yfinance
"""

import os
from datetime import datetime
from typing import Optional, Tuple

from backend.app.logger import get_logger
from backend.app.analysis.deepseek import call_deepseek
from backend.app.memory.long_term import save_insight, get_insights
from backend.app.db import get_supabase_client
from backend.app.analysis.shadow_portfolio import close_shadow_trade
from backend.app.alerts.telegram import send_post_earnings_alert
from backend.app.utils.timezone import now_mez, mez_timestamp

logger = get_logger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
POST_EARNINGS_PROMPT_PATH = os.path.join(ROOT_DIR, "prompts", "post_earnings.md")


def _read_prompt(path: str) -> Tuple[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    parts = content.split("SYSTEM:")
    if len(parts) < 2:
        return "", content

    subparts = parts[1].split("USER_TEMPLATE:")
    system_prompt = subparts[0].strip()
    user_prompt = subparts[1].strip() if len(subparts) > 1 else ""
    return system_prompt, user_prompt


def _current_quarter() -> str:
    now = now_mez()
    quarter = (now.month - 1) // 3 + 1
    return f"Q{quarter}_{now.year}"


async def run_post_earnings_review(ticker: str, quarter: Optional[str] = None) -> dict:
    """
    Führt einen Post-Earnings-Review für einen Ticker durch.
    """
    if quarter is None:
        quarter = _current_quarter()

    logger.info(f"Post-Earnings Review für {ticker} ({quarter})")

    pre_report = await _get_last_audit_report(ticker)
    if not pre_report:
        logger.warning(f"Kein vorheriger Audit-Report für {ticker} gefunden.")
        pre_report = {
            "recommendation": "unknown",
            "opportunity_score": 0,
            "torpedo_score": 0,
            "report_text": "Kein Report vorhanden",
            "created_at": None,
        }

    from backend.app.data.fmp import get_earnings_history

    history = await get_earnings_history(ticker, limit=1)
    actual_eps = None
    actual_eps_consensus = None
    actual_surprise = None
    actual_revenue = None
    actual_revenue_consensus = None

    if history and history.last_quarter:
        last = history.last_quarter
        actual_eps = getattr(last, "eps_actual", None)
        actual_eps_consensus = getattr(last, "eps_consensus", None)
        actual_surprise = getattr(last, "eps_surprise_percent", None)
        actual_revenue = getattr(last, "revenue_actual", None)
        actual_revenue_consensus = getattr(last, "revenue_consensus", None)

    # After-Hours Reaktion
    ah_change_pct = None
    try:
        import yfinance as yf
        import asyncio
        def _fetch_ah():
            hist = yf.Ticker(ticker).history(
                period="5d", interval="1h", prepost=True
            )
            if hist.empty or len(hist) < 2:
                return None
            # Suche den ersten AH-Balken nach Marktschluss
            # AH = nach 16:00 ET = 22:00-02:00 CET/CEST
            for i in range(len(hist)-1, 0, -1):
                idx = hist.index[i]
                if hasattr(idx, 'hour'):
                    # In CET/CEST: AH ist 22:00-23:59 oder 00:00-02:00
                    if (idx.hour >= 22) or (idx.hour <= 2):
                        ah_close = float(hist["Close"].iloc[i])
                        reg_close = float(hist["Close"].iloc[i-1])
                        if reg_close > 0:
                            return round(
                                (ah_close - reg_close) / reg_close * 100, 2
                            )
            return None
        ah_change_pct = await asyncio.to_thread(_fetch_ah)
    except Exception:
        pass

    stock_price_pre = None
    stock_reaction_1d = None
    stock_reaction_5d = None

    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo")
        if len(hist) >= 7:
            stock_price_pre = float(hist["Close"].iloc[-7])
            price_1d_after = float(hist["Close"].iloc[-6])
            price_5d_after = float(hist["Close"].iloc[-2])
            stock_reaction_1d = ((price_1d_after - stock_price_pre) / stock_price_pre) * 100
            stock_reaction_5d = ((price_5d_after - stock_price_pre) / stock_price_pre) * 100
    except Exception as exc:
        logger.warning(f"Kursreaktion für {ticker} nicht verfügbar: {exc}")

    review_text, lessons = await _generate_review(
        ticker=ticker,
        quarter=quarter,
        pre_recommendation=pre_report.get("recommendation", "unknown"),
        pre_opp_score=pre_report.get("opportunity_score", 0),
        pre_torp_score=pre_report.get("torpedo_score", 0),
        actual_eps=actual_eps,
        actual_consensus=actual_eps_consensus,
        actual_surprise=actual_surprise,
        reaction_1d=stock_reaction_1d,
        reaction_5d=stock_reaction_5d,
        ah_change_pct=ah_change_pct,
    )

    prediction_correct = _evaluate_prediction(
        recommendation=pre_report.get("recommendation", "unknown"),
        reaction_1d=stock_reaction_1d,
        surprise=actual_surprise,
    )

    # Historische Win-Rate aus past_trades
    win_rate = None
    try:
        db = get_supabase_client()
        if db:
            trades = await (
                db.table("shadow_trades")
                .select("outcome_correct")
                .eq("ticker", ticker)
                .eq("status", "closed")
                .limit(10)
                .execute_async()
            )
            if trades.data and len(trades.data) >= 3:
                wins = sum(
                    1 for t in trades.data
                    if t.get("outcome_correct") is True
                )
                win_rate = round(wins / len(trades.data) * 100)
    except Exception:
        pass

    review_record = {
        "ticker": ticker,
        "quarter": quarter,
        "pre_earnings_score_opportunity": pre_report.get("opportunity_score"),
        "pre_earnings_score_torpedo": pre_report.get("torpedo_score"),
        "pre_earnings_recommendation": pre_report.get("recommendation"),
        "pre_earnings_report_date": pre_report.get("created_at"),
        "actual_eps": actual_eps,
        "actual_eps_consensus": actual_eps_consensus,
        "actual_surprise_percent": actual_surprise,
        "actual_revenue": actual_revenue,
        "actual_revenue_consensus": actual_revenue_consensus,
        "stock_price_pre": stock_price_pre,
        "stock_reaction_1d_percent": stock_reaction_1d,
        "stock_reaction_5d_percent": stock_reaction_5d,
        "prediction_correct": prediction_correct,
        "score_accuracy": "correct" if prediction_correct else "wrong",
        "review_text": review_text,
        "lessons_learned": lessons,
    }

    try:
        db = get_supabase_client()
        if db:
            await db.table("earnings_reviews").upsert(review_record, on_conflict="ticker,quarter").execute_async()
            logger.info(f"Earnings Review gespeichert: {ticker} {quarter}")
            try:
                await close_shadow_trade(ticker=ticker, quarter=quarter)
            except Exception as shadow_err:  # noqa: BLE001
                logger.debug(f"Shadow Trade Close (non-critical): {shadow_err}")
    except Exception as exc:
        logger.error(f"Earnings Review Speicher-Fehler: {exc}")

    if lessons:
        await save_insight(
            ticker=ticker,
            category="earnings_pattern",
            insight=lessons,
            confidence=0.6 if prediction_correct else 0.3,
            source="post_earnings_review",
            quarter=quarter,
        )

    await _update_performance_tracking(quarter, prediction_correct)

    # Telegram Alert
    try:
        await send_post_earnings_alert(
            ticker=ticker,
            company_name=ticker,  # Fallback
            eps_actual=actual_eps,
            eps_consensus=actual_eps_consensus,
            eps_surprise_pct=actual_surprise,
            revenue_actual=actual_revenue,
            revenue_consensus=actual_revenue_consensus,
            ah_change_pct=ah_change_pct,
            expected_move_pct=None,  # Could be calculated from options
            rsi=None,  # Could be fetched from technicals
            opp_score=pre_report.get("opportunity_score"),
            torpedo_score=pre_report.get("torpedo_score"),
            win_rate=win_rate,
            recommendation=pre_report.get("pre_earnings_recommendation"),
        )
    except Exception as e:
        logger.warning(f"Post-Earnings Alert Fehler: {e}")

    # Watchlist-Prio nach Earnings aktualisieren
    try:
        from backend.app.db import get_supabase_client
        db = get_supabase_client()
        if db:
            # Hole aktuelle Watchlist-Einträge
            wl = await db.table("watchlist") \
                   .select("ticker,web_prio,notes") \
                   .eq("ticker", ticker.upper()) \
                   .execute_async()

            if wl.data:
                entry = wl.data[0]

                # Neue Prio berechnen
                new_prio = entry.get("web_prio")
                eps_surp = actual_surprise or 0
                ah = ah_change_pct or 0

                # Beat + AH-Dip → P1 (sofort watchen)
                if eps_surp > 5 and ah < -2:
                    new_prio = 1
                # Starker Beat + positiver AH → P2
                elif eps_surp > 5 and ah > 2:
                    new_prio = min(
                        entry.get("web_prio") or 3, 2
                    )
                # Miss + AH-Rallye → vorsichtig P1
                elif eps_surp < -5 and ah > 3:
                    new_prio = 1
                # Starker Miss → P4 (reduzieren)
                elif eps_surp < -10:
                    new_prio = max(
                        entry.get("web_prio") or 2, 3
                    )

                # Notiz-Update
                from backend.app.utils.timezone import now_mez
                date_str = now_mez().strftime("%Y-%m-%d")
                note_tag = (
                    f"[Post-Earnings {date_str}: "
                    f"EPS {eps_surp:+.1f}%, "
                    f"AH {ah:+.1f}%]"
                )
                old_notes = entry.get("notes") or ""
                # Alten Post-Earnings-Tag ersetzen
                import re
                old_notes = re.sub(
                    r"\[Post-Earnings[^\]]*\]",
                    "", old_notes
                ).strip()
                new_notes = (
                    f"{old_notes} {note_tag}".strip()
                    if old_notes else note_tag
                )

                # Nur updaten wenn sich etwas ändert
                updates: dict = {"notes": new_notes}
                if (new_prio is not None
                        and new_prio != entry.get("web_prio")):
                    updates["web_prio"] = new_prio
                    logger.info(
                        f"Watchlist-Prio {ticker}: "
                        f"{entry.get('web_prio')} → {new_prio}"
                    )

                await db.table("watchlist") \
                  .update(updates) \
                  .eq("ticker", ticker.upper()) \
                  .execute_async()

                # Cache invalidieren
                from backend.app.cache import cache_invalidate
                cache_invalidate("watchlist:enriched:v2")
                cache_invalidate(f"research_dashboard_{ticker.upper()}")
                cache_invalidate_prefix("earnings_radar_")

    except Exception as e:
        logger.warning(
            f"Watchlist-Update nach Earnings Fehler: {e}"
        )

    return {
        "ticker": ticker,
        "quarter": quarter,
        "prediction_correct": prediction_correct,
        "actual_surprise": actual_surprise,
        "reaction_1d": stock_reaction_1d,
        "review": review_text,
        "lessons": lessons,
        "ah_change_pct": ah_change_pct,
        "historical_win_rate": win_rate,
    }


def _evaluate_prediction(recommendation: str, reaction_1d: Optional[float], surprise: Optional[float]) -> bool:
    if reaction_1d is None:
        return False

    bullish = {"strong_buy", "buy", "buy_hedge"}
    bearish = {"strong_short", "short", "potential_short"}
    neutral = {"hold", "watch", "ignore"}

    if recommendation in bullish:
        return reaction_1d > 0
    if recommendation in bearish:
        return reaction_1d < 0
    if recommendation in neutral:
        return abs(reaction_1d) < 5
    return False


async def _get_last_audit_report(ticker: str) -> Optional[dict]:
    try:
        db = get_supabase_client()
        if db is None:
            return None
        result = await (
            db.table("audit_reports")
            .select("ticker, recommendation, opportunity_score, torpedo_score, report_text, created_at")
            .eq("ticker", ticker)
            .order("created_at", desc=True)
            .limit(1)
            .execute_async()
        )
        if result.data:
            return result.data[0]
    except Exception as exc:
        logger.debug(f"Audit-Report für {ticker} nicht in DB: {exc}")
    return None


async def _generate_review(
    ticker: str,
    quarter: str,
    pre_recommendation: str,
    pre_opp_score: float,
    pre_torp_score: float,
    actual_eps: Optional[float],
    actual_consensus: Optional[float],
    actual_surprise: Optional[float],
    reaction_1d: Optional[float],
    reaction_5d: Optional[float],
    ah_change_pct: Optional[float],
) -> Tuple[str, str]:
    system_prompt, user_template = _read_prompt(POST_EARNINGS_PROMPT_PATH)

    insights = await get_insights(ticker)
    long_term_str = "\n".join(
        [f"[{i.get('category', '?')}] {i.get('insight', '')}" for i in insights[:5]]
    ) or "Keine historischen Erkenntnisse vorhanden."

    # Fear & Greed
    fg_score_val = "N/A"
    fg_label_val = "N/A"
    try:
        from backend.app.data.fear_greed import (
            get_fear_greed_score
        )
        fg = await get_fear_greed_score()
        fg_score_val = str(round(fg.get("score", 50)))
        fg_label_val = fg.get("label", "N/A")
    except Exception:
        pass

    # Expected Move aus letzten Options-Daten
    exp_move_val = "N/A"
    try:
        if ah_change_pct is not None:
            # Aus pre_report falls vorhanden
            em = pre_report.get("expected_move_pct")
            if em:
                exp_move_val = f"{em:.1f}"
    except Exception:
        pass

    user_prompt = (
        user_template
        .replace("{{ticker}}", ticker)
        .replace("{{quarter}}", quarter)
        .replace("{{pre_recommendation}}", pre_recommendation)
        .replace("{{pre_opp_score}}", str(pre_opp_score))
        .replace("{{pre_torp_score}}", str(pre_torp_score))
        .replace("{{actual_eps}}", _fmt(actual_eps))
        .replace("{{actual_consensus}}", _fmt(actual_consensus))
        .replace("{{actual_surprise}}", _fmt(actual_surprise))
        .replace("{{reaction_1d}}", _fmt(reaction_1d))
        .replace("{{reaction_5d}}", _fmt(reaction_5d))
        .replace("{{ah_change_pct}}", (
            f"{ah_change_pct:+.1f}" if ah_change_pct else "N/A"
        ))
        .replace("{{expected_move_pct}}", exp_move_val)
        .replace("{{fear_greed_score}}", fg_score_val)
        .replace("{{fear_greed_label}}", fg_label_val)
        .replace("{{long_term_insights}}", long_term_str)
    )

    try:
        result = await call_deepseek(system_prompt, user_prompt, model="deepseek-reasoner")
        if "---LESSONS---" in result:
            review, lessons = result.split("---LESSONS---", 1)
            return review.strip(), lessons.strip()
        return result, "Keine spezifische Lektion extrahiert."
    except Exception as exc:
        logger.error(f"DeepSeek Review-Fehler: {exc}")
        return "Review-Generierung fehlgeschlagen.", "Keine Lektion verfügbar."


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


async def _update_performance_tracking(period: str, prediction_correct: bool):
    try:
        db = get_supabase_client()
        if db is None:
            return

        result = await db.table("performance_tracking").select("*").eq("period", period).execute_async()

        if result.data:
            record = result.data[0]
            record["total_predictions"] = (record.get("total_predictions") or 0) + 1
            if prediction_correct:
                record["correct_predictions"] = (record.get("correct_predictions") or 0) + 1
            else:
                record["wrong_predictions"] = (record.get("wrong_predictions") or 0) + 1
            total = record["total_predictions"]
            correct = record.get("correct_predictions", 0)
            record["accuracy_percent"] = (correct / total * 100) if total > 0 else 0
            await db.table("performance_tracking").upsert(record, on_conflict="period").execute_async()
        else:
            new_record = {
                "period": period,
                "total_predictions": 1,
                "correct_predictions": 1 if prediction_correct else 0,
                "wrong_predictions": 0 if prediction_correct else 1,
                "accuracy_percent": 100.0 if prediction_correct else 0.0,
            }
            await db.table("performance_tracking").insert(new_record).execute_async()

        logger.info(f"Performance-Tracking aktualisiert für {period}")
    except Exception as exc:
        logger.error(f"Performance-Tracking Fehler: {exc}")
