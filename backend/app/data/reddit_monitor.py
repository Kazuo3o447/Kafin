"""
Reddit Retail Sentiment Monitor.
Holt Titel aus r/wallstreetbets und r/stocks,
bewertet sie mit FinBERT und berechnet eine
Retail-Smart-Money-Divergenz.

Reddit JSON-API: kostenlos, kein API-Key.
Rate-Limit: max 1 Request/2s, User-Agent erforderlich.
"""
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional

from backend.app.cache import cache_get, cache_set
from backend.app.logger import get_logger

logger = get_logger(__name__)

REDDIT_HEADERS = {
    "User-Agent": "Kafin:reddit-sentiment-monitor:1.0 (by /u/kafin_dev)",
}
SUBREDDITS = ["wallstreetbets", "stocks"]
REDDIT_BASE = "https://www.reddit.com/r/{sub}/search.json"


async def get_reddit_sentiment(
    ticker: str,
    hours: int = 24,
) -> dict:
    """
    Holt Reddit-Posts zu einem Ticker (letzte 24h)
    und bewertet sie mit FinBERT.
    Gibt Durchschnitts-Score + Mention-Count zurück.
    """
    cache_key = f"reddit:{ticker.upper()}:{hours}h"
    cached = cache_get(cache_key)
    if cached:
        return cached

    def _fetch_reddit() -> list[str]:
        """Holt Post-Titel von Reddit (sync)."""
        titles: list[str] = []
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        import httpx as _httpx

        def _fetch_titles(sub: str, endpoint: str, params: dict) -> list[str]:
            endpoint_titles: list[str] = []
            try:
                url = f"https://www.reddit.com/r/{sub}/{endpoint}"
                resp = _httpx.get(
                    url,
                    params=params,
                    headers=REDDIT_HEADERS,
                    timeout=10.0,
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                posts = data.get("data", {}).get("children", [])
                for post in posts:
                    pd = post.get("data", {})
                    created = pd.get("created_utc", 0)
                    if created:
                        post_dt = datetime.utcfromtimestamp(created)
                        if post_dt < cutoff:
                            continue
                    title = pd.get("title", "")
                    if title and ticker.upper() in title.upper():
                        endpoint_titles.append(title)
            except Exception as e:
                logger.debug(f"Reddit {sub}/{endpoint}: {e}")
            return endpoint_titles

        for sub in SUBREDDITS:
            sub_titles = _fetch_titles(
                sub,
                "search.json",
                {
                    "q": ticker.upper(),
                    "sort": "new",
                    "limit": 25,
                    "t": "day",
                    "type": "link",
                },
            )
            if not sub_titles:
                sub_titles = _fetch_titles(sub, "new.json", {"limit": 25})
            if not sub_titles:
                sub_titles = _fetch_titles(sub, "hot.json", {"limit": 25})
            titles.extend(sub_titles)

        return list(dict.fromkeys(titles))

    try:
        titles = await asyncio.to_thread(_fetch_reddit)

        if not titles:
            result = {
                "ticker":       ticker.upper(),
                "mention_count": 0,
                "avg_score":    None,
                "label":        "keine Daten",
                "source":       "reddit",
            }
            cache_set(cache_key, result, ttl_seconds=3600)
            return result

        # FinBERT-Bewertung (lokal, kostenlos)
        from backend.app.analysis.finbert import (
            analyze_sentiment_batch,
        )
        scores = await asyncio.to_thread(
            analyze_sentiment_batch, titles
        )

        valid = [s for s in scores if s is not None]
        avg = round(sum(valid) / len(valid), 3) if valid else None

        label = (
            "bullish" if (avg or 0) > 0.15
            else "bearish" if (avg or 0) < -0.15
            else "neutral"
        )

        result = {
            "ticker":        ticker.upper(),
            "mention_count": len(titles),
            "avg_score":     avg,
            "label":         label,
            "titles_sample": titles[:3],
            "source":        "reddit_wsb_stocks",
        }
        cache_set(cache_key, result, ttl_seconds=3600)
        return result

    except Exception as e:
        logger.warning(f"Reddit Sentiment Fehler: {e}")
        return {
            "ticker":       ticker.upper(),
            "mention_count": 0,
            "avg_score":    None,
            "error":        str(e),
        }


async def get_retail_smart_divergence(
    ticker: str,
    insider_activity: Optional[object] = None,
) -> dict:
    """
    Berechnet Retail vs. Smart Money Divergenz.

    Score:
      +1.0 = Retail bullisch + Insider kaufen (Bestätigung)
      -1.0 = Retail bullisch + Insider verkaufen (Torpedo)
       0.0 = kein klares Signal

    Kein Insider-Objekt → nur Reddit-Score.
    """
    reddit = await get_reddit_sentiment(ticker)
    retail_score = reddit.get("avg_score")
    mentions = reddit.get("mention_count", 0)

    if retail_score is None or mentions < 2:
        return {
            "ticker":          ticker.upper(),
            "divergence":      None,
            "signal":          "insufficient_data",
            "retail_score":    retail_score,
            "mentions":        mentions,
        }

    # Insider-Richtung
    insider_bullish = None
    if insider_activity is not None:
        is_buy  = getattr(
            insider_activity, "is_cluster_buy", False
        )
        is_sell = getattr(
            insider_activity, "is_cluster_sell", False
        )
        if is_buy:   insider_bullish = True
        if is_sell:  insider_bullish = False

    # Divergenz-Score
    retail_bullish = retail_score > 0.1
    retail_bearish = retail_score < -0.1

    signal = "neutral"
    divergence_score = 0.0

    if insider_bullish is not None:
        if retail_bullish and not insider_bullish:
            # Retail gierig, Smart Money verkauft → Torpedo
            signal = "torpedo_divergence"
            divergence_score = -1.0
        elif retail_bearish and insider_bullish:
            # Retail panickt, Smart Money kauft → Opportunity
            signal = "opportunity_divergence"
            divergence_score = +1.0
        elif retail_bullish and insider_bullish:
            signal = "confirmed_bullish"
            divergence_score = +0.5
        elif retail_bearish and not insider_bullish:
            signal = "confirmed_bearish"
            divergence_score = -0.5
    else:
        # Nur Reddit
        if retail_bullish and mentions >= 5:
            signal = "retail_hype"
            divergence_score = -0.3  # Vorsicht
        elif retail_bearish and mentions >= 5:
            signal = "retail_panic"
            divergence_score = +0.2  # Contrarian

    return {
        "ticker":            ticker.upper(),
        "divergence_score":  divergence_score,
        "signal":            signal,
        "retail_score":      retail_score,
        "retail_label":      reddit.get("label"),
        "mentions":          mentions,
        "insider_bullish":   insider_bullish,
    }
