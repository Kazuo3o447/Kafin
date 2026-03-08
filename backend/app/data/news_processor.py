"""
news_processor — Zentrale News-Verarbeitungs-Pipeline

Input:  Ticker-Liste (aus Watchlist)
Output: Gefilterte, bewertete News-Stichpunkte in Supabase + Telegram-Alerts
Deps:   finnhub.py, finbert.py, deepseek.py, memory/short_term.py, alerts/telegram.py
Config: config/alerts.yaml (Schwellenwerte, Torpedo-Keywords)
API:    Finnhub (News), DeepSeek (Stichpunkte)
"""

import asyncio
from datetime import datetime, timedelta
from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.data.finnhub import get_company_news
from backend.app.analysis.finbert import analyze_sentiment_batch
from backend.app.analysis.deepseek import call_deepseek
from backend.app.memory.short_term import save_bullet_points, get_existing_urls
from backend.app.alerts.telegram import send_telegram_alert, format_narrative_shift_alert

logger = get_logger(__name__)

# Rate Limiting für DeepSeek (Phase 3A Extension)
_DEEPSEEK_CALLS: dict[str, list[datetime]] = {}
_SPIKE_ALERTS_SENT: set[str] = set()


def _load_torpedo_keywords() -> list[str]:
    alerts_config = settings.alerts
    return alerts_config.get("torpedo", {}).get("keywords", [])

TORPEDO_KEYWORDS = _load_torpedo_keywords()


async def process_news_for_ticker(ticker: str) -> dict:
    """
    Verarbeitet News für einen einzelnen Ticker durch die dreistufige Pipeline.

    Stufe 1: News von Finnhub abrufen (nur für diesen Ticker)
    Stufe 2: FinBERT-Sentiment berechnen, nach Relevanz filtern
    Stufe 3: DeepSeek extrahiert Stichpunkte für relevante News

    Returns: dict mit ticker, total_fetched, passed_finbert, bullets_saved, alerts_sent
    """
    stats = {
        "ticker": ticker,
        "total_fetched": 0,
        "passed_finbert": 0,
        "bullets_saved": 0,
        "alerts_sent": 0
    }

    now = datetime.now()
    from_date = (now - timedelta(hours=24)).strftime("%Y-%m-%d")
    to_date = now.strftime("%Y-%m-%d")

    # STUFE 1: News abrufen
    try:
        news_list = await get_company_news(ticker, from_date, to_date)
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der News für {ticker}: {e}")
        return stats

    if not news_list:
        logger.debug(f"Keine neuen News für {ticker}")
        return stats

    stats["total_fetched"] = len(news_list)

    # Duplikate filtern
    existing_urls = await get_existing_urls(ticker)
    new_news = [n for n in news_list if getattr(n, "url", "") not in existing_urls]

    if not new_news:
        logger.debug(f"Keine neuen (nicht-duplikat) News für {ticker}")
        return stats

    # STUFE 2: FinBERT-Sentiment
    headlines = [n.headline for n in new_news]
    sentiment_scores = analyze_sentiment_batch(headlines)

    relevance_threshold = settings.alerts.get("finbert", {}).get("relevance_threshold", 0.3)

    relevant_news = []
    for news_item, score in zip(new_news, sentiment_scores):
        if abs(score) >= relevance_threshold:
            relevant_news.append((news_item, score))

    stats["passed_finbert"] = len(relevant_news)

    if not relevant_news:
        logger.debug(f"Keine relevanten News für {ticker} nach FinBERT-Filter")
        return stats

    # Torpedo-Check (Keyword-Matching, KEIN KI-Call nötig)
    for news_item, score in relevant_news:
        combined_text = f"{news_item.headline} {news_item.summary}".lower()
        torpedo_hit = [kw for kw in TORPEDO_KEYWORDS if kw.lower() in combined_text]

        if torpedo_hit:
            logger.warning(f"TORPEDO erkannt für {ticker}: {torpedo_hit}")
            alert_text = (
                f"🚨 TORPEDO-ALARM: {ticker}\n\n"
                f"Keywords: {', '.join(torpedo_hit)}\n"
                f"Headline: {news_item.headline}\n"
                f"Sentiment: {score:.2f}\n"
                f"Quelle: {getattr(news_item, 'source', 'N/A')}\n\n"
                f"⚠️ Empfehlung prüfen!"
            )
            await send_telegram_alert(alert_text)
            stats["alerts_sent"] += 1

    # STUFE 3: DeepSeek extrahiert Stichpunkte
    now_dt = datetime.now()
    cutoff = now_dt - timedelta(hours=1)
    
    if ticker not in _DEEPSEEK_CALLS:
        _DEEPSEEK_CALLS[ticker] = []
        
    # Cleanup alter Calls
    _DEEPSEEK_CALLS[ticker] = [t for t in _DEEPSEEK_CALLS[ticker] if t > cutoff]

    for news_item, score in relevant_news:
        # Rate Limiting: Max 5 Calls pro Stunde
        if len(_DEEPSEEK_CALLS[ticker]) >= 5:
            logger.warning(f"Rate Limit erreicht für {ticker}: >5 DeepSeek-Calls in der letzten Stunde.")
            if ticker not in _SPIKE_ALERTS_SENT:
                alert_text = f"⚙️ <b>NEWS SPIKE ALERT: {ticker}</b>\n\nMehr als 5 relevante Nachrichten in 1h. DeepSeek-Extraktion für diesen Zyklus pausiert (Kostenbremse)."
                await send_telegram_alert(alert_text)
                _SPIKE_ALERTS_SENT.add(ticker)
            break
            
        _SPIKE_ALERTS_SENT.discard(ticker) # Reset bei normalem Volumen
        _DEEPSEEK_CALLS[ticker].append(datetime.now())
        
        try:
            extracted_data = await _extract_bullet_points(ticker, news_item)
            bullet_points = extracted_data.get("bullet_points", [])
            category = _categorize_news(news_item.headline, news_item.summary)

            is_torpedo_kw = bool([kw for kw in TORPEDO_KEYWORDS if kw.lower() in f"{news_item.headline} {news_item.summary}".lower()])
            
            # Narrative Intelligence Check
            is_narrative_shift = extracted_data.get("is_narrative_shift", False)
            shift_type = extracted_data.get("shift_type", "None")
            shift_reasoning = extracted_data.get("shift_reasoning", "")
            
            if is_narrative_shift and shift_type != "None":
                alert_text = format_narrative_shift_alert(
                    ticker=ticker,
                    shift_type=shift_type,
                    reasoning=shift_reasoning,
                    headline=news_item.headline,
                    url=getattr(news_item, "url", "")
                )
                await send_telegram_alert(alert_text)
                stats["alerts_sent"] += 1

            await save_bullet_points(
                ticker=ticker,
                date=getattr(news_item, "timestamp", datetime.now()),
                source=getattr(news_item, "source", "finnhub"),
                bullet_points=bullet_points,
                sentiment_score=score,
                category=category,
                url=getattr(news_item, "url", ""),
                is_material=is_torpedo_kw,
                is_narrative_shift=is_narrative_shift,
                shift_type=shift_type,
                shift_confidence=extracted_data.get("shift_confidence"),
                shift_reasoning=shift_reasoning
            )
            stats["bullets_saved"] += 1

        except Exception as e:
            logger.error(f"Fehler bei Stichpunkt-Extraktion für {ticker}: {e}")

    # Bei stark negativen News (< -0.5): Alert (ohne Fallback aus Extraktion)
    for news_item, score in relevant_news:
        if score < -0.5:
            alert_text = (
                f"📉 Stark negative News: {ticker}\n\n"
                f"{news_item.headline}\n"
                f"Sentiment: {score:.2f}\n"
                f"Quelle: {getattr(news_item, 'source', 'N/A')}"
            )
            await send_telegram_alert(alert_text)
            stats["alerts_sent"] += 1
        elif score > 0.5:
            alert_text = (
                f"📈 Stark positive News: {ticker}\n\n"
                f"{news_item.headline}\n"
                f"Sentiment: {score:.2f}\n"
                f"Quelle: {getattr(news_item, 'source', 'N/A')}"
            )
            await send_telegram_alert(alert_text)
            stats["alerts_sent"] += 1

    logger.info(f"News-Pipeline {ticker}: {stats['total_fetched']} geholt, {stats['passed_finbert']} relevant, {stats['bullets_saved']} gespeichert, {stats['alerts_sent']} Alerts")
    return stats


async def _extract_bullet_points(ticker: str, news_item) -> dict:
    """Nutzt DeepSeek um Stichpunkte und Narrative Shifts aus einer Nachricht zu extrahieren."""
    import os
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    PROMPT_PATH = os.path.join(ROOT_DIR, "prompts", "news_extraction.md")
    
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        parts = content.split("SYSTEM:")
        subparts = parts[1].split("USER_TEMPLATE:")
        system_prompt = subparts[0].strip()
        user_tmpl = subparts[1].strip()
        user_prompt = user_tmpl.replace("{{ticker}}", ticker).replace("{{headline}}", news_item.headline).replace("{{summary}}", news_item.summary)
    except Exception as e:
        logger.error(f"Fehler beim Laden des news_extraction Prompts: {e}")
        return {"bullet_points": [news_item.headline]}

    result = await call_deepseek(system_prompt, user_prompt)

    try:
        import json
        clean = result.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        
        if isinstance(data, dict) and "bullet_points" in data:
            data["bullet_points"] = data["bullet_points"][:5]
            return data
        elif isinstance(data, list):
            return {"bullet_points": data[:5]}
            
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"DeepSeek JSON-Parse-Fehler: {e}. Nutze Headline als Fallback.")

    return {"bullet_points": [news_item.headline]}


def _categorize_news(headline: str, summary: str) -> str:
    """Kategorisiert eine Nachricht basierend auf Keywords. Kein KI-Call nötig."""
    combined = f"{headline} {summary}".lower()

    if any(kw in combined for kw in ["earnings", "revenue", "eps", "quarterly", "results"]):
        return "earnings"
    elif any(kw in combined for kw in ["guidance", "outlook", "forecast", "expects"]):
        return "guidance"
    elif any(kw in combined for kw in ["ceo", "cfo", "appointed", "resign", "depart"]):
        return "management"
    elif any(kw in combined for kw in ["sec", "fda", "investigation", "lawsuit", "regulatory"]):
        return "regulatory"
    elif any(kw in combined for kw in ["upgrade", "downgrade", "price target", "analyst"]):
        return "analyst"
    elif any(kw in combined for kw in ["acquisition", "merger", "deal", "partnership"]):
        return "corporate"
    else:
        return "general"


async def run_news_pipeline(tickers: list[str]) -> list[dict]:
    """
    Führt die News-Pipeline für alle Watchlist-Ticker aus.
    Wird alle 30 Minuten von n8n aufgerufen.
    """
    logger.info(f"News-Pipeline gestartet für {len(tickers)} Ticker")

    results = []
    for ticker in tickers:
        result = await process_news_for_ticker(ticker)
        results.append(result)
        await asyncio.sleep(1)

    total_fetched = sum(r["total_fetched"] for r in results)
    total_relevant = sum(r["passed_finbert"] for r in results)
    total_alerts = sum(r["alerts_sent"] for r in results)

    logger.info(f"News-Pipeline abgeschlossen: {total_fetched} geholt, {total_relevant} relevant, {total_alerts} Alerts")
    
    # -------------------------------------------------------------
    # MAKRO-KALENDER: Globale Events unter GENERAL_MACRO speichern
    # -------------------------------------------------------------
    try:
        macro_stats = await process_macro_calendar()
        logger.info(f"Makro-Kalender: {macro_stats['events_saved']} Events gespeichert")
    except Exception as e:
        logger.error(f"Fehler beim Makro-Kalender: {e}")

    # -------------------------------------------------------------
    # TORPEDO-MONITOR: Prüft bestehende Empfehlungen
    # -------------------------------------------------------------
    try:
        from backend.app.analysis.torpedo_monitor import check_torpedo_updates
        await check_torpedo_updates()
    except Exception as e:
        logger.error(f"Fehler im Torpedo-Monitor: {e}")
        
    return results


async def process_macro_calendar() -> dict:
    """
    Ruft den Wirtschaftskalender ab und speichert High-Impact Events
    unter dem Pseudo-Ticker GENERAL_MACRO im Kurzzeit-Gedächtnis.
    """
    from backend.app.data.finnhub import get_economic_calendar
    
    stats = {"events_fetched": 0, "events_saved": 0}
    
    try:
        events = await get_economic_calendar(days_back=7, days_forward=7)
        stats["events_fetched"] = len(events)
    except Exception as e:
        logger.error(f"Fehler beim Abrufen des Wirtschaftskalenders: {e}")
        return stats
    
    if not events:
        logger.info("Keine High-Impact Makro-Events gefunden")
        return stats
    
    # Deduplizierung: Prüfe ob URLs/Events schon gespeichert
    existing_urls = await get_existing_urls("GENERAL_MACRO")
    
    for ev in events:
        event_id = f"macro_{ev.get('event', '')}_{ev.get('date', '')}"
        if event_id in existing_urls:
            continue
        
        actual = ev.get("actual")
        estimate = ev.get("estimate")
        unit = ev.get("unit", "")
        
        if actual is not None and estimate is not None:
            bullet = f"{ev['event']}: Actual {actual}{unit} vs. Est. {estimate}{unit}"
        elif estimate is not None:
            bullet = f"{ev['event']}: Erwartung {estimate}{unit} (noch ausstehend)"
        else:
            bullet = f"{ev['event']}: {ev.get('date', '?')}"
        
        await save_bullet_points(
            ticker="GENERAL_MACRO",
            date=datetime.now(),
            source="finnhub_calendar",
            bullet_points=[bullet],
            sentiment_score=0.0,
            category="macro",
            url=event_id,
            is_material=True
        )
        stats["events_saved"] += 1
    
    logger.info(f"Makro-Kalender: {stats['events_saved']} neue Events unter GENERAL_MACRO gespeichert")
    return stats
