from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any
from xml.etree import ElementTree

from dotenv import load_dotenv

from data.sources.finbert import FinBERTClassifier
from data.sources.yfinance_adapter import YFinanceAdapter


load_dotenv()

DEFAULT_MARKET_RSS_QUERIES = [
    "US stock market Federal Reserve inflation Nasdaq S&P 500",
    "AI stocks semiconductor software enterprise earnings",
]


class MultiSourceSnapshotBuilder:
    def __init__(self, timeout: float = 20.0, classifier: FinBERTClassifier | None = None) -> None:
        self.timeout = timeout
        self.classifier = classifier or FinBERTClassifier()
        self.finnhub_api_key = os.getenv("FINNHUB_API_KEY", "")
        self.fmp_api_key = os.getenv("FMP_API_KEY", "")
        self.fred_api_key = os.getenv("FRED_API_KEY", "")
        self.coinglass_api_key = os.getenv("COINGLASS_API_KEY", "")
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "")

    def fetch_market_snapshot(self) -> dict[str, Any]:
        quality_errors: list[str] = []
        sources: list[dict[str, Any]] = []
        macro = self._fetch_fred_macro(quality_errors, sources)
        fear_greed = self._fetch_coinglass_sentiment(quality_errors, sources)
        technicals = self._fetch_market_technicals(quality_errors, sources)

        news = []
        for query in DEFAULT_MARKET_RSS_QUERIES:
            news.extend(self._fetch_google_news_rss(query, quality_errors, sources, limit=8))
        news.extend(self._fetch_tavily_news("US equities macro Federal Reserve market sentiment", quality_errors, sources, limit=6))
        news = _dedupe_news(news)[:20]
        sentiment_results = self.classifier.batch_classify([_news_text(item) for item in news])
        market_sentiment = self.classifier.summarize(sentiment_results)
        for item, result in zip(news, sentiment_results, strict=False):
            item["sentiment_label"] = result.label
            item["sentiment_score"] = result.score

        market_regime = infer_market_regime(technicals, macro, fear_greed, market_sentiment)
        return {
            "ticker": "_MARKET",
            "as_of": date.today().isoformat(),
            "news": news,
            "sentiment": market_sentiment,
            "macro": macro,
            "fear_greed": fear_greed,
            "technicals": technicals,
            "market_regime": market_regime,
            "sources": sources,
            "quality_errors": quality_errors,
        }

    def fetch_snapshot(self, ticker: str, market_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
        market_snapshot = market_snapshot or self.fetch_market_snapshot()
        base = YFinanceAdapter().fetch_snapshot(ticker)
        quality_errors = list(base.get("quality_errors", []))
        sources = list(base.get("sources", []))

        fmp_bundle = self._fetch_fmp_bundle(ticker, quality_errors, sources)
        finnhub_bundle = self._fetch_finnhub_bundle(ticker, quality_errors, sources)

        company_news = []
        company_name = fmp_bundle.get("company_name") or base.get("company_name") or ticker.upper()
        company_news.extend(self._fetch_google_news_rss(f"{ticker} stock {company_name}", quality_errors, sources, limit=8))
        company_news.extend(finnhub_bundle.get("news", []))
        company_news.extend(self._fetch_tavily_news(f"{ticker} stock earnings guidance risks", quality_errors, sources, limit=6))
        company_news = _dedupe_news(company_news)[:20]

        sentiment_results = self.classifier.batch_classify([_news_text(item) for item in company_news])
        company_sentiment = self.classifier.summarize(sentiment_results)
        for item, result in zip(company_news, sentiment_results, strict=False):
            item["sentiment_label"] = result.label
            item["sentiment_score"] = result.score

        metrics = _merge_metrics(base.get("metrics", {}), fmp_bundle.get("metrics", {}), finnhub_bundle.get("metrics", {}))
        snapshot = {
            "ticker": ticker.upper(),
            "company_name": fmp_bundle.get("company_name") or finnhub_bundle.get("company_name") or base.get("company_name", "unknown"),
            "exchange": fmp_bundle.get("exchange") or finnhub_bundle.get("exchange") or base.get("exchange", "unknown"),
            "sector": fmp_bundle.get("sector") or base.get("sector", "unknown"),
            "industry": fmp_bundle.get("industry") or base.get("industry", "unknown"),
            "as_of": date.today().isoformat(),
            "metrics": metrics,
            "news": {
                "company": company_news,
                "market": market_snapshot.get("news", []),
            },
            "sentiment": {
                "company": company_sentiment,
                "market": market_snapshot.get("sentiment", {}),
            },
            "macro": market_snapshot.get("macro", {}),
            "fear_greed": market_snapshot.get("fear_greed", {}),
            "market_regime": market_snapshot.get("market_regime", "unknown"),
            "sources": sources,
            "quality_errors": quality_errors,
        }
        return snapshot

    def _fetch_fmp_bundle(
        self,
        ticker: str,
        quality_errors: list[str],
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.fmp_api_key:
            quality_errors.append("FMP_API_KEY missing")
            return {}

        profile = self._request_json(
            f"https://financialmodelingprep.com/api/v3/profile/{ticker}",
            params={"apikey": self.fmp_api_key},
            source_name="fmp_profile",
            quality_errors=quality_errors,
            sources=sources,
        )
        income = self._request_json(
            f"https://financialmodelingprep.com/api/v3/income-statement/{ticker}",
            params={"apikey": self.fmp_api_key, "period": "annual", "limit": 5},
            source_name="fmp_income_statement",
            quality_errors=quality_errors,
            sources=sources,
        )
        cashflow = self._request_json(
            f"https://financialmodelingprep.com/api/v3/cash-flow-statement/{ticker}",
            params={"apikey": self.fmp_api_key, "period": "annual", "limit": 5},
            source_name="fmp_cashflow_statement",
            quality_errors=quality_errors,
            sources=sources,
        )
        key_metrics = self._request_json(
            f"https://financialmodelingprep.com/api/v3/key-metrics/{ticker}",
            params={"apikey": self.fmp_api_key, "period": "annual", "limit": 5},
            source_name="fmp_key_metrics",
            quality_errors=quality_errors,
            sources=sources,
        )

        profile_row = profile[0] if isinstance(profile, list) and profile else {}
        income_rows = income if isinstance(income, list) else []
        cashflow_rows = cashflow if isinstance(cashflow, list) else []
        key_metric_rows = key_metrics if isinstance(key_metrics, list) else []

        latest_income = income_rows[0] if income_rows else {}
        latest_key_metrics = key_metric_rows[0] if key_metric_rows else {}

        revenues = [_safe_float(row.get("revenue")) for row in income_rows[:5] if _safe_float(row.get("revenue"))]
        gross_margins = [_ratio(row.get("grossProfit"), row.get("revenue")) for row in income_rows[:5]]
        operating_margins = [_ratio(row.get("operatingIncome"), row.get("revenue")) for row in income_rows[:5]]
        fcf_margins = [_ratio(row.get("freeCashFlow"), inc.get("revenue")) for row, inc in zip(cashflow_rows[:5], income_rows[:5], strict=False)]
        share_counts = [_safe_float(row.get("weightedAverageShsOutDil")) for row in income_rows[:3] if _safe_float(row.get("weightedAverageShsOutDil"))]
        sbc_to_revenue = [_ratio(cf.get("stockBasedCompensation"), inc.get("revenue")) for cf, inc in zip(cashflow_rows[:5], income_rows[:5], strict=False)]
        sbc_to_ocf = [_ratio(cf.get("stockBasedCompensation"), cf.get("operatingCashFlow")) for cf in cashflow_rows[:5]]

        gross_profit = _safe_float(latest_income.get("grossProfit"))
        enterprise_value = _safe_float(latest_key_metrics.get("enterpriseValue"))

        return {
            "company_name": profile_row.get("companyName"),
            "exchange": profile_row.get("exchangeShortName"),
            "sector": profile_row.get("sector"),
            "industry": profile_row.get("industry"),
            "metrics": {
                "revenue_5y": revenues[0] if revenues else None,
                "revenue_growth_5y": _cagr(revenues),
                "gross_margin_5y": _average(gross_margins),
                "operating_margin_5y": _average(operating_margins),
                "fcf_margin_5y": _average(fcf_margins),
                "roic": _safe_float(latest_key_metrics.get("roic")),
                "share_count_trend_3y": _cagr(list(reversed(share_counts))) if len(share_counts) >= 2 else None,
                "sbc_to_revenue": _average(sbc_to_revenue),
                "sbc_to_ocf": _average(sbc_to_ocf),
                "ev_to_gross_profit": (enterprise_value / gross_profit) if enterprise_value and gross_profit else None,
                "market_cap_usd": _safe_float(profile_row.get("mktCap")),
                "price": _safe_float(profile_row.get("price")),
            },
        }

    def _fetch_finnhub_bundle(
        self,
        ticker: str,
        quality_errors: list[str],
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.finnhub_api_key:
            quality_errors.append("FINNHUB_API_KEY missing")
            return {"news": []}

        profile = self._request_json(
            "https://finnhub.io/api/v1/stock/profile2",
            params={"symbol": ticker, "token": self.finnhub_api_key},
            source_name="finnhub_profile2",
            quality_errors=quality_errors,
            sources=sources,
        )
        earnings = self._request_json(
            "https://finnhub.io/api/v1/stock/earnings",
            params={"symbol": ticker, "token": self.finnhub_api_key},
            source_name="finnhub_earnings",
            quality_errors=quality_errors,
            sources=sources,
        )
        recommendations = self._request_json(
            "https://finnhub.io/api/v1/stock/recommendation",
            params={"symbol": ticker, "token": self.finnhub_api_key},
            source_name="finnhub_recommendation",
            quality_errors=quality_errors,
            sources=sources,
        )
        news = self._request_json(
            "https://finnhub.io/api/v1/company-news",
            params={
                "symbol": ticker,
                "from": (date.today() - timedelta(days=14)).isoformat(),
                "to": date.today().isoformat(),
                "token": self.finnhub_api_key,
            },
            source_name="finnhub_company_news",
            quality_errors=quality_errors,
            sources=sources,
        )
        calendar = self._request_json(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={
                "from": date.today().isoformat(),
                "to": (date.today() + timedelta(days=90)).isoformat(),
                "symbol": ticker,
                "token": self.finnhub_api_key,
            },
            source_name="finnhub_earnings_calendar",
            quality_errors=quality_errors,
            sources=sources,
        )

        earnings_rows = earnings if isinstance(earnings, list) else []
        latest_earnings = earnings_rows[0] if earnings_rows else {}
        recommendation_rows = recommendations if isinstance(recommendations, list) else []
        recommendation = recommendation_rows[0] if recommendation_rows else {}
        calendar_items = calendar.get("earningsCalendar", []) if isinstance(calendar, dict) else []
        next_earnings = calendar_items[0] if calendar_items else {}

        recommendation_score = _recommendation_score(recommendation)
        return {
            "company_name": profile.get("name") if isinstance(profile, dict) else None,
            "exchange": profile.get("exchange") if isinstance(profile, dict) else None,
            "metrics": {
                "last_earnings_surprise": _safe_float(latest_earnings.get("surprisePercent")),
                "next_earnings_date": next_earnings.get("date"),
                "analyst_recommendation_score": recommendation_score,
                "analyst_recommendation_total": sum(
                    int(recommendation.get(field, 0) or 0)
                    for field in ("strongBuy", "buy", "hold", "sell", "strongSell")
                ),
            },
            "news": [_normalize_finnhub_news(item) for item in news[:15]] if isinstance(news, list) else [],
        }

    def _fetch_fred_macro(
        self,
        quality_errors: list[str],
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.fred_api_key:
            quality_errors.append("FRED_API_KEY missing")
            return {}

        series_map = {
            "fed_funds_rate": "FEDFUNDS",
            "core_cpi": "CPILFESL",
            "unemployment_rate": "UNRATE",
            "ten_year_treasury": "DGS10",
        }
        macro: dict[str, Any] = {}
        for field_name, series_id in series_map.items():
            payload = self._request_json(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": self.fred_api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 2,
                },
                source_name=f"fred_{series_id}",
                quality_errors=quality_errors,
                sources=sources,
            )
            observations = payload.get("observations", []) if isinstance(payload, dict) else []
            macro[field_name] = _safe_float(observations[0].get("value")) if observations else None
        return macro

    def _fetch_coinglass_sentiment(
        self,
        quality_errors: list[str],
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.coinglass_api_key or self.coinglass_api_key == "mock":
            return {}

        payload = self._request_json(
            "https://open-api-v3.coinglass.com/api/index/fear-greed-history",
            headers={"CG-API-KEY": self.coinglass_api_key},
            source_name="coinglass_fear_greed",
            quality_errors=quality_errors,
            sources=sources,
        )
        data = payload.get("data", []) if isinstance(payload, dict) else []
        latest = data[0] if data else {}
        value = _safe_float(latest.get("value"))
        label = "neutral"
        if value is not None:
            label = "fear" if value < 40 else "greed" if value > 60 else "neutral"
        return {"value": value, "label": label}

    def _fetch_market_technicals(
        self,
        quality_errors: list[str],
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            import yfinance as yf

            spy_history = yf.Ticker("SPY").history(period="1y", auto_adjust=True)
            vix_history = yf.Ticker("^VIX").history(period="6mo", auto_adjust=True)
        except Exception as exc:  # pragma: no cover - external network runtime
            quality_errors.append(f"yfinance_market_technicals failed: {exc}")
            return {}

        sources.append({"name": "yfinance_market_technicals", "evidence_class": "B"})
        sma_200 = float(spy_history["Close"].tail(200).mean()) if len(spy_history) >= 200 else None
        latest_spy = float(spy_history["Close"].iloc[-1]) if not spy_history.empty else None
        latest_vix = float(vix_history["Close"].iloc[-1]) if not vix_history.empty else None
        return {
            "spy_close": latest_spy,
            "spy_sma_200": sma_200,
            "vix_close": latest_vix,
            "spy_above_sma_200": bool(latest_spy and sma_200 and latest_spy >= sma_200),
        }

    def _fetch_tavily_news(
        self,
        query: str,
        quality_errors: list[str],
        sources: list[dict[str, Any]],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        if not self.tavily_api_key:
            return []

        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "topic": "news",
            "search_depth": "basic",
            "max_results": limit,
        }
        raw = self._request_json(
            "https://api.tavily.com/search",
            method="POST",
            payload=payload,
            source_name="tavily_search",
            quality_errors=quality_errors,
            sources=sources,
        )
        results = raw.get("results", []) if isinstance(raw, dict) else []
        normalized = []
        for item in results:
            normalized.append(
                {
                    "id": item.get("url") or item.get("title"),
                    "title": item.get("title", "unknown"),
                    "summary": item.get("content", ""),
                    "url": item.get("url", ""),
                    "published_at": item.get("published_date"),
                    "source": item.get("url", "tavily"),
                    "source_type": "tavily",
                }
            )
        return normalized

    def _fetch_google_news_rss(
        self,
        query: str,
        quality_errors: list[str],
        sources: list[dict[str, Any]],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        url = (
            "https://news.google.com/rss/search?"
            + urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
        )
        try:
            xml_text = self._request_text(url)
            root = ElementTree.fromstring(xml_text)
        except Exception as exc:  # pragma: no cover - external RSS parsing
            quality_errors.append(f"google_news_rss failed: {exc}")
            return []

        sources.append({"name": "google_news_rss", "evidence_class": "C"})
        items = []
        for item in root.findall("./channel/item")[:limit]:
            items.append(
                {
                    "id": item.findtext("guid") or item.findtext("link") or item.findtext("title"),
                    "title": item.findtext("title", default="unknown"),
                    "summary": item.findtext("description", default=""),
                    "url": item.findtext("link", default=""),
                    "published_at": item.findtext("pubDate"),
                    "source": item.findtext("source", default="google_news"),
                    "source_type": "rss",
                }
            )
        return items

    def _request_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        source_name: str,
        quality_errors: list[str],
        sources: list[dict[str, Any]],
    ) -> Any:
        query_url = url
        if params:
            query_string = urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})
            query_url = f"{url}?{query_string}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            query_url,
            data=body,
            headers={"Content-Type": "application/json", **(headers or {})},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                sources.append({"name": source_name, "evidence_class": "B"})
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            quality_errors.append(f"{source_name} failed: {exc}")
            return {}

    def _request_text(self, url: str) -> str:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read().decode("utf-8", errors="replace")


def build_filter_queue_entries(
    watchlist: list[dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    market_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    market_regime = (market_snapshot or {}).get("market_regime", "unknown")

    for item in watchlist:
        ticker = str(item.get("ticker", "")).upper().strip()
        if not ticker:
            continue
        snapshot = snapshots.get(ticker, {})
        sentiment = snapshot.get("sentiment", {}).get("company", {})
        score = float(sentiment.get("score", 0.0) or 0.0)
        label = sentiment.get("label", "neutral")
        news_items = snapshot.get("news", {}).get("company", [])
        relevant_news = [news for news in news_items if news.get("sentiment_label") != "neutral"]
        if len(news_items) < 2 and abs(score) < 0.2:
            continue

        priority = "high" if abs(score) >= 0.35 or len(relevant_news) >= 3 else "medium"
        entries.append(
            {
                "ticker": ticker,
                "priority": priority,
                "reason": f"{label} sentiment {score:+.2f} with {len(news_items)} recent news items",
                "market_regime": market_regime,
                "sentiment": sentiment,
                "news_count": len(news_items),
                "note": item.get("note"),
            }
        )

    return sorted(entries, key=lambda entry: (entry["priority"] != "high", -abs(entry["sentiment"].get("score", 0.0))))


def infer_market_regime(
    technicals: dict[str, Any],
    macro: dict[str, Any],
    fear_greed: dict[str, Any],
    market_sentiment: dict[str, Any],
) -> str:
    vix = _safe_float(technicals.get("vix_close"))
    spy_above = technicals.get("spy_above_sma_200")
    fed_funds = _safe_float(macro.get("fed_funds_rate"))
    fear_value = _safe_float(fear_greed.get("value"))
    sentiment_score = _safe_float(market_sentiment.get("score")) or 0.0

    if (vix is not None and vix >= 25) or fear_value is not None and fear_value < 35:
        return "risk_off"
    if spy_above is False or sentiment_score <= -0.25:
        return "risk_off"
    if (vix is not None and vix <= 18) and spy_above and sentiment_score >= -0.05 and (fed_funds is None or fed_funds < 6.0):
        return "risk_on"
    return "neutral"


def _normalize_finnhub_news(item: dict[str, Any]) -> dict[str, Any]:
    published_at = item.get("datetime")
    if published_at:
        published_at = datetime.fromtimestamp(int(published_at), tz=UTC).isoformat()
    return {
        "id": item.get("id") or item.get("url") or item.get("headline"),
        "title": item.get("headline", "unknown"),
        "summary": item.get("summary", ""),
        "url": item.get("url", ""),
        "published_at": published_at,
        "source": item.get("source", "finnhub"),
        "source_type": "finnhub",
    }


def _merge_metrics(*metric_maps: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for metric_map in metric_maps:
        for key, value in metric_map.items():
            if value not in (None, "", "unknown"):
                merged[key] = value
            else:
                merged.setdefault(key, value)
    return merged


def _dedupe_news(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = str(item.get("url") or item.get("id") or item.get("title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _recommendation_score(row: dict[str, Any]) -> float | None:
    if not row:
        return None
    strong_buy = int(row.get("strongBuy", 0) or 0)
    buy = int(row.get("buy", 0) or 0)
    hold = int(row.get("hold", 0) or 0)
    sell = int(row.get("sell", 0) or 0)
    strong_sell = int(row.get("strongSell", 0) or 0)
    total = strong_buy + buy + hold + sell + strong_sell
    if total == 0:
        return None
    return round(((2 * strong_buy) + buy - sell - (2 * strong_sell)) / total, 4)


def _news_text(item: dict[str, Any]) -> str:
    return " ".join(part for part in [item.get("title"), item.get("summary")] if part)


def _ratio(numerator: Any, denominator: Any) -> float | None:
    num = _safe_float(numerator)
    den = _safe_float(denominator)
    if num is None or den in (None, 0):
        return None
    return round(num / den, 6)


def _average(values: list[float | None]) -> float | None:
    usable = [value for value in values if value is not None]
    if not usable:
        return None
    return round(mean(usable), 6)


def _cagr(values: list[float]) -> float | None:
    usable = [value for value in values if value not in (None, 0)]
    if len(usable) < 2:
        return None
    start = usable[-1]
    end = usable[0]
    periods = len(usable) - 1
    if start <= 0 or end <= 0 or periods <= 0:
        return None
    return round((end / start) ** (1 / periods) - 1, 6)


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, "", "None", "null", "."):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None