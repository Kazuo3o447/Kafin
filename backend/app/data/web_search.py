"""
Web Intelligence via Tavily API.
Cache-aware: prüft zuerst web_intelligence_cache in Supabase.
Prio-System steuert Refresh-Frequenz.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import httpx

from backend.app.config import settings
from backend.app.logger import get_logger

logger = get_logger(__name__)

TAVILY_URL = "https://api.tavily.com/search"

# TTL je nach Prio (in Stunden)
PRIO_TTL_HOURS = {
    1: 8,    # Prio 1: alle 8h refreshen (3x täglich)
    2: 24,   # Prio 2: täglich
    3: 168,  # Prio 3: wöchentlich
    4: 9999, # Prio 4: nie automatisch (nur manuell via Report)
}


def _auto_prio_from_days(days_to_earnings: Optional[int]) -> int:
    """Berechnet automatische Prio aus Tagen bis Earnings."""
    if days_to_earnings is None:
        return 4
    if days_to_earnings <= 3:
        return 1
    if days_to_earnings <= 7:
        return 2
    if days_to_earnings <= 14:
        return 3
    return 4


async def _tavily_search(query: str, max_results: int = 2) -> list[str]:
    """
    Einzelne Tavily-Suchanfrage.
    Gibt Text-Snippets zurück. Kein HTML-Parsing nötig.
    """
    if not settings.tavily_api_key:
        return []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                TAVILY_URL,
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                    "include_answer": True,
                    "include_raw_content": False,
                },
            )
            response.raise_for_status()
            data = response.json()

            snippets = []
            if data.get("answer"):
                snippets.append(data["answer"])
            for result in data.get("results", [])[:max_results]:
                content = result.get("content", "").strip()
                if content and len(content) > 30:
                    title = result.get("title", "Quelle")
                    snippets.append(f"[{title}] {content[:300]}")
            return snippets

    except httpx.TimeoutException:
        logger.warning(f"Tavily Timeout: {query[:60]}")
        return []
    except Exception as e:
        logger.warning(f"Tavily Fehler '{query[:60]}': {e}")
        return []


async def _fetch_from_tavily(
    ticker: str,
    company_name: str,
    prio: int,
) -> tuple[list[str], str]:
    """
    Macht 1-3 Tavily-Suchen je nach Prio.
    Gibt (raw_snippets, summary_text) zurück.
    Prio 1: 3 Suchen | Prio 2-3: 1 Suche | Prio 4: keine
    """
    if prio == 4:
        return [], ""

    name = company_name or ticker
    queries_by_prio = {
        1: [
            f"{ticker} {name} earnings analyst sentiment 2026",
            f"{ticker} options flow unusual activity earnings",
            f"{ticker} earnings preview wall street forecast",
        ],
        2: [
            f"{ticker} {name} earnings preview analyst 2026",
        ],
        3: [
            f"{ticker} {name} stock outlook earnings",
        ],
    }

    queries = queries_by_prio.get(prio, queries_by_prio[3])
    labels = ["Analyst-Sentiment", "Options-Flow", "Earnings-Preview"]

    # Parallel ausführen
    results = await asyncio.gather(
        *[_tavily_search(q) for q in queries],
        return_exceptions=True,
    )

    raw_snippets = []
    summary_lines = []

    for i, result in enumerate(results):
        if isinstance(result, Exception) or not result:
            continue
        label = labels[i] if i < len(labels) else "News"
        for snippet in result:
            if snippet and len(snippet) > 20:
                raw_snippets.append({"label": label, "text": snippet})
                summary_lines.append(f"• [{label}] {snippet[:200]}")

    summary = "\n".join(summary_lines[:6])
    return raw_snippets, summary


async def get_web_intelligence(
    ticker: str,
    company_name: str = "",
    days_to_earnings: Optional[int] = None,
    manual_prio: Optional[int] = None,
    force_refresh: bool = False,
) -> str:
    """
    Gibt Web-Intelligence-Text für einen Ticker zurück.

    Ablauf:
    1. Effektive Prio berechnen (manuell > auto)
    2. Cache in Supabase prüfen
    3. Cache frisch → direkt zurückgeben
    4. Cache abgelaufen oder leer → Tavily-Suche → Cache updaten

    Rückgabe: Formatierter String für DeepSeek-Prompt.
    Fallback: Leerer String wenn nichts verfügbar.
    """
    # Prio bestimmen
    auto_prio = _auto_prio_from_days(days_to_earnings)
    effective_prio = manual_prio if manual_prio is not None else auto_prio

    # Prio 4 und kein Force → keine Suche
    if effective_prio == 4 and not force_refresh:
        return ""

    # Cache prüfen
    if not force_refresh:
        try:
            from backend.app.db import get_supabase_client
            db = get_supabase_client()
            if db:
                res = (
                    db.table("web_intelligence_cache")
                    .select("summary, expires_at, prio")
                    .eq("ticker", ticker.upper())
                    .execute()
                )
                rows = res.data if res and res.data else []
                if rows:
                    row = rows[0]
                    expires_str = row.get("expires_at")
                    if expires_str:
                        try:
                            from datetime import timezone as _tz
                            expires = datetime.fromisoformat(
                                expires_str.replace("Z", "+00:00")
                            )
                            if expires.tzinfo is None:
                                expires = expires.replace(tzinfo=_tz.utc)
                            now = datetime.now(_tz.utc)
                            if now < expires:
                                cached_summary = row.get("summary", "")
                                if cached_summary:
                                    logger.debug(
                                        f"Web Intelligence Cache HIT: {ticker}"
                                    )
                                    return cached_summary
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"Cache-Check Fehler {ticker}: {e}")

    # Cache MISS → Tavily-Suche
    logger.info(f"Web Intelligence: Tavily-Suche für {ticker} (Prio {effective_prio})")
    raw_snippets, summary = await _fetch_from_tavily(
        ticker, company_name, effective_prio
    )

    if not summary:
        return "Keine Web-Intelligence verfügbar."

    # Cache schreiben
    try:
        from backend.app.db import get_supabase_client
        db = get_supabase_client()
        if db:
            from datetime import timezone as _tz
            _now = datetime.now(_tz.utc)
            ttl_hours = PRIO_TTL_HOURS.get(effective_prio, 24)
            expires_at = _now + timedelta(hours=ttl_hours)
            db.table("web_intelligence_cache").upsert(
                {
                    "ticker": ticker.upper(),
                    "prio": effective_prio,
                    "summary": summary,
                    "raw_snippets": raw_snippets,
                    "searched_at": _now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                },
                on_conflict="ticker",
            ).execute()
            logger.debug(f"Web Intelligence Cache gespeichert: {ticker}")
    except Exception as e:
        logger.warning(f"Cache-Write Fehler {ticker}: {e}")

    return summary


async def get_web_sentiment_score(
    ticker: str,
    company_name: str = "",
    days_to_earnings: Optional[int] = None,
    manual_prio: Optional[int] = None,
) -> tuple[float, str]:
    """
    Berechnet einen Sentiment-Score aus Web-Intelligence.

    Ruft DeepSeek mit den Tavily-Snippets auf und bekommt einen
    strukturierten Score zurück.

    Returns:
        (score, label) wobei:
        score: -1.0 bis +1.0
        label: "bullisch" | "neutral" | "bärisch"
    """
    # Web-Snippets laden (nutzt Cache wenn vorhanden)
    summary = await get_web_intelligence(
        ticker=ticker,
        company_name=company_name,
        days_to_earnings=days_to_earnings,
        manual_prio=manual_prio,
    )

    if not summary or summary.startswith("Keine Web-Intelligence"):
        return 0.0, "neutral"

    # DeepSeek: strukturierter Score aus Snippets
    try:
        from backend.app.analysis.deepseek import call_deepseek

        sys_prompt = (
            "Du bist ein Finanzanalyst. Antworte NUR mit einem "
            "JSON-Objekt, kein weiterer Text, keine Erklärung."
        )

        user_prompt = (
            f"Analysiere das Markt-Sentiment für {ticker} aus diesen "
            f"Web-Snippets:\n\n{summary}\n\n"
            "Antworte NUR mit diesem JSON:\n"
            '{"score": <float zwischen -1.0 und 1.0>, '
            '"label": "<bullisch|neutral|bärisch>", '
            '"reasoning": "<max 1 Satz>"}'
        )

        result = await call_deepseek(sys_prompt, user_prompt,
                                     model="deepseek-chat")

        import json
        import re
        # Sucht erstes { bis letztes } — robust gegen Prefix-Text
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if not match:
            logger.warning(f"Kein JSON in DeepSeek-Antwort: {result[:100]}")
            return 0.0, "neutral"
        parsed = json.loads(match.group())
        score = float(parsed.get("score", 0.0))
        label = parsed.get("label", "neutral")

        # Bounds prüfen
        score = max(-1.0, min(1.0, score))
        if label not in ("bullisch", "neutral", "bärisch"):
            label = "neutral"

        logger.info(
            f"Web Sentiment {ticker}: {score:.2f} ({label})"
        )
        return score, label

    except Exception as e:
        logger.warning(f"Web Sentiment Score {ticker}: {e}")
        return 0.0, "neutral"
