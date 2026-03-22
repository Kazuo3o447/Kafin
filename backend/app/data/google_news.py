"""
google_news — Google News RSS Feed Scanner

Input:  Dynamische Suchbegriffe (Watchlist + Custom Keywords)
Output: Gefilterte Nachrichten von vertrauenswürdigen Quellen
Deps:   config.py, logger.py, db.py, feedparser
Config: settings.environment (nur Logging)
API:    Google News RSS
"""

from __future__ import annotations

from typing import List, Dict, Optional, Set
import calendar
from urllib.parse import quote

import feedparser

from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.db import get_supabase_client
from backend.app.cache import cache_get, cache_set

logger = get_logger(__name__)

TRUSTED_SOURCES = {
    "reuters", "bloomberg", "cnbc", "wsj", "wall street journal",
    "financial times", "ft.com", "associated press", "ap news",
    "bbc", "marketwatch", "yahoo finance", "barrons", "seeking alpha",
    "benzinga", "the motley fool", "investor's business daily",
    "handelsblatt", "manager magazin", "wirtschaftswoche",
    "the guardian", "nytimes", "new york times", "washington post",
    "politico", "the hill", "axios", "cnn", "fortune",
}

BLOCKED_DOMAINS = {
    "blogspot", "medium.com", "substack.com", "reddit.com",
    "tiktok", "pinterest", "facebook", "instagram", "buzzfeed",
    "dailymail", "thesun.co.uk", "nypost.com/gossip",
}

RSS_BASE = "https://news.google.com/rss"


def _search_url(query: str) -> str:
    return f"{RSS_BASE}/search?q={quote(query)}&hl=en&gl=US&ceid=US:en"


def _topic_url(topic: str) -> str:
    return f"{RSS_BASE}/headlines/section/topic/{topic}?hl=en&gl=US&ceid=US:en"


def _is_trusted(source: str, url: str) -> bool:
    combined = f"{source} {url}".lower()
    for blocked in BLOCKED_DOMAINS:
        if blocked in combined:
            return False
    for trusted in TRUSTED_SOURCES:
        if trusted in combined:
            return True
    return False


def _extract_source(title: str) -> str:
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return "Unknown"


def _clean_title(title: str) -> str:
    if " - " in title:
        return title.rsplit(" - ", 1)[0].strip()
    return title


def _parse_feed(url: str, max_results: int = 15) -> List[Dict]:
    try:
        feed = feedparser.parse(url)
        results: List[Dict] = []
        for entry in feed.entries[: max_results * 3]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("published", "")
            published_parsed = entry.get("published_parsed")
            source = _extract_source(title)
            headline = _clean_title(title)

            timestamp = 0
            if published_parsed:
                try:
                    timestamp = int(calendar.timegm(published_parsed))
                except Exception:
                    timestamp = 0

            if not headline or not link:
                continue

            if not _is_trusted(source, link):
                continue

            results.append(
                {
                    "headline": headline,
                    "source": source,
                    "url": link,
                    "published": published,
                    "timestamp": timestamp,
                }
            )
            if len(results) >= max_results:
                break
        return results
    except Exception as exc:  # pragma: no cover
        logger.error(f"Google News RSS Fehler: {exc}")
        return []


async def get_custom_search_terms() -> List[Dict]:
    """Lädt aktive benutzerdefinierte Suchbegriffe aus Supabase."""
    try:
        db = get_supabase_client()
        if db:
            result = await (
                db.table("custom_search_terms")
                .select("*")
                .eq("is_active", True)
                .order("created_at", desc=True)
                .execute_async()
            )
            return result.data if result and result.data else []
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Custom Search Terms Fehler: {exc}")
    return []


async def add_custom_search_term(term: str, category: str = "custom") -> bool:
    """Fügt einen neuen Suchbegriff hinzu oder aktiviert ihn erneut."""
    try:
        db = get_supabase_client()
        if db:
            await db.table("custom_search_terms").upsert(
                {
                    "term": term,
                    "category": category,
                    "is_active": True,
                },
                on_conflict="term",
            ).execute_async()
            logger.info(f"Suchbegriff hinzugefügt: '{term}' ({category})")
            return True
    except Exception as exc:  # pragma: no cover
        logger.error(f"Suchbegriff hinzufügen Fehler: {exc}")
    return False


async def remove_custom_search_term(term: str) -> bool:
    """Deaktiviert einen bestehenden Suchbegriff."""
    try:
        db = get_supabase_client()
        if db:
            await db.table("custom_search_terms").update({"is_active": False}).eq("term", term).execute_async()
            logger.info(f"Suchbegriff deaktiviert: '{term}'")
            return True
    except Exception as exc:  # pragma: no cover
        logger.error(f"Suchbegriff entfernen Fehler: {exc}")
    return False


def _add_news_item(
    collection: List[Dict],
    seen: set,
    news_list: List[Dict],
    category: str,
    related_ticker: Optional[str] = None,
) -> None:
    for news in news_list:
        key = news.get("headline")
        if not key or key in seen:
            continue
        seen.add(key)
        enriched = dict(news)
        enriched["category"] = category
        if related_ticker:
            enriched["related_ticker"] = related_ticker
        collection.append(enriched)


async def scan_google_news(watchlist_items: Optional[List[Dict]] = None) -> List[Dict]:
    """Haupt-Scan über Topics, Custom Terms und Watchlist-Ticker."""
    watchlist_scope = "market"
    if watchlist_items:
        watchlist_scope = ",".join(sorted({str(item.get("ticker", "")).upper() for item in watchlist_items if item.get("ticker")})) or "market"

    cache_key = f"gnews:scan:{watchlist_scope}"
    cached = cache_get(cache_key)
    if cached:
        logger.debug("Google News aus Cache")
        return cached

    all_news: List[Dict] = []
    seen: Set[str] = set()

    # 1. Topic Feeds (Business + World)
    for topic in ["BUSINESS", "WORLD"]:
        topic_news = _parse_feed(_topic_url(topic), max_results=12)
        _add_news_item(all_news, seen, topic_news, topic.lower())

    # 2. Custom Keywords
    custom_terms = await get_custom_search_terms()
    for term_entry in custom_terms:
        term = term_entry.get("term", "")
        if not term:
            continue
        category = term_entry.get("category", "custom")
        news = _parse_feed(_search_url(term), max_results=5)
        _add_news_item(all_news, seen, news, category)

    # 3. Watchlist Items
    if watchlist_items:
        for item in watchlist_items:
            ticker = item.get("ticker", "")
            company = item.get("company_name", "")
            short_name = company.split(" ")[0].split(",")[0] if company else ticker
            if short_name and short_name != ticker:
                query = f'"{ticker}" OR "{short_name}"'
            else:
                query = f'"{ticker}"'
            watchlist_news = _parse_feed(_search_url(query), max_results=5)
            _add_news_item(all_news, seen, watchlist_news, "watchlist", related_ticker=ticker)

    logger.info(
        f"Google News Scan ({settings.environment}): {len(all_news)} Artikel von vertrauenswürdigen Quellen"
    )
    cache_set(cache_key, all_news, ttl_seconds=600)
    return all_news
