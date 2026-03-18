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
    now = datetime.now()
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
    )

    prediction_correct = _evaluate_prediction(
        recommendation=pre_report.get("recommendation", "unknown"),
        reaction_1d=stock_reaction_1d,
        surprise=actual_surprise,
    )

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
            db.table("earnings_reviews").upsert(review_record, on_conflict="ticker,quarter").execute()
            logger.info(f"Earnings Review gespeichert: {ticker} {quarter}")
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

    return {
        "ticker": ticker,
        "quarter": quarter,
        "prediction_correct": prediction_correct,
        "actual_surprise": actual_surprise,
        "reaction_1d": stock_reaction_1d,
        "review": review_text,
        "lessons": lessons,
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
        result = (
            db.table("audit_reports")
            .select("ticker, recommendation, opportunity_score, torpedo_score, report_text, created_at")
            .eq("ticker", ticker)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
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
) -> Tuple[str, str]:
    system_prompt, user_template = _read_prompt(POST_EARNINGS_PROMPT_PATH)

    insights = await get_insights(ticker)
    long_term_str = "\n".join(
        [f"[{i.get('category', '?')}] {i.get('insight', '')}" for i in insights[:5]]
    ) or "Keine historischen Erkenntnisse vorhanden."

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

        result = db.table("performance_tracking").select("*").eq("period", period).execute()

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
            db.table("performance_tracking").upsert(record, on_conflict="period").execute()
        else:
            new_record = {
                "period": period,
                "total_predictions": 1,
                "correct_predictions": 1 if prediction_correct else 0,
                "wrong_predictions": 0 if prediction_correct else 1,
                "accuracy_percent": 100.0 if prediction_correct else 0.0,
            }
            db.table("performance_tracking").insert(new_record).execute()

        logger.info(f"Performance-Tracking aktualisiert für {period}")
    except Exception as exc:
        logger.error(f"Performance-Tracking Fehler: {exc}")
