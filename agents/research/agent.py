from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from agents.common import DeepSeekClient, LLMRequest, MASTER_PROMPT
from agents.research.schema import ResearchCard, SCORE_WEIGHTS


class ResearchAgent:
    """Creates conservative research cards from already validated data.

    This first implementation deliberately avoids inventing values. All numeric content comes from
    the local snapshot. Qualitative fields remain cautious until the DeepSeek-backed research path
    is wired in.
    """

    def __init__(self, allow_llm: bool = True, evidence_dir: Path | None = None) -> None:
        self.allow_llm = allow_llm
        self.evidence_dir = evidence_dir or Path("research/evidence")

    def run(self, ticker: str, snapshot: dict[str, Any]) -> ResearchCard:
        metrics = snapshot.get("metrics", {})
        company_sentiment = snapshot.get("sentiment", {}).get("company", {})
        market_sentiment = snapshot.get("sentiment", {}).get("market", {})
        news_digest = snapshot.get("news", {}).get("company", [])[:5]
        score_breakdown = _score_from_snapshot(snapshot)
        score = min(100, sum(score_breakdown.values()))
        hard_blockers = list(snapshot.get("quality_errors", []))
        catalysts = _extract_catalysts(news_digest)
        bull_case = ["Kennzahlen-Snapshot ist vollstaendig genug fuer eine erste Research-Card."]
        bear_case = ["Qualitative Moat-, Wettbewerbs- und Bewertungsanalyse benoetigt DeepSeek- und Quellenlauf."]

        if company_sentiment.get("label") == "positive":
            bull_case.append("Aktuelle Nachrichtenlage ist laut FinBERT ueberwiegend positiv.")
        elif company_sentiment.get("label") == "negative":
            bear_case.append("Aktuelle Nachrichtenlage ist laut FinBERT ueberwiegend negativ.")

        if market_sentiment.get("label") == "negative":
            bear_case.append("Gesamtmarkt-Sentiment ist aktuell negativ und kann das Setup belasten.")

        llm_analysis = self._build_qualitative_analysis(
            ticker=ticker,
            snapshot=snapshot,
            company_sentiment=company_sentiment,
            market_sentiment=market_sentiment,
            news_digest=news_digest,
        )

        if llm_analysis.get("bull_case"):
            bull_case = _merge_unique(llm_analysis["bull_case"], bull_case)
        if llm_analysis.get("bear_case"):
            bear_case = _merge_unique(llm_analysis["bear_case"], bear_case)
        open_questions = _merge_unique(
            llm_analysis.get("open_questions", []),
            [
                "Welche Quellen belegen Wachstum, Moat und Bewertungsannahmen?",
                "Welche Red-Team-Gegenbeispiele gibt es im selben Sektor?",
            ],
        )
        falsification_tests = _merge_unique(
            llm_analysis.get("falsification_tests", []),
            [
                "Score um mindestens 20 Punkte senken, falls Umsatzwachstum oder Marge klar verfehlt.",
                "Gate auf Red setzen, falls Verwaesserung oder SBC nicht belegt werden kann.",
            ],
        )

        gate = "Green" if score >= 70 and not hard_blockers else "Yellow"
        confidence = "medium" if score >= 70 and not hard_blockers else "low"

        return ResearchCard(
            ticker=ticker.upper(),
            company_name=snapshot.get("company_name", "unknown"),
            exchange=snapshot.get("exchange", "unknown"),
            sector=snapshot.get("sector", "unknown"),
            industry=snapshot.get("industry", "unknown"),
            category=_category_for(score, hard_blockers),
            growth_research_score=score,
            gate=gate,
            confidence=confidence,
            thesis_summary=llm_analysis.get("thesis_summary") or (
                "Lokale Phase-1-Research-Card auf Basis validierter Snapshot-Daten. "
                "Diese Card ist keine Kaufempfehlung und kein Trade-Signal."
            ),
            technical_assessment=llm_analysis.get("technical_assessment", ""),
            bull_case=bull_case,
            bear_case=bear_case,
            key_metrics=metrics,
            score_breakdown=score_breakdown,
            moat_assessment={
                "rating": "Unknown",
                "sources": [],
                "evidence": [],
                "threats": ["Moat wurde im Scaffold noch nicht qualitativ belegt."],
            },
            catalysts=catalysts,
            red_flags=hard_blockers,
            hard_blockers=hard_blockers,
            open_questions=open_questions,
            falsification_tests=falsification_tests,
            company_sentiment=company_sentiment,
            market_sentiment=market_sentiment,
            news_digest=news_digest,
            llm_metadata=llm_analysis.get("llm_metadata", {}),
            source_list=snapshot.get("sources", []),
            handoff_to_trade_engine=gate == "Green",
        )

    def _build_qualitative_analysis(
        self,
        *,
        ticker: str,
        snapshot: dict[str, Any],
        company_sentiment: dict[str, Any],
        market_sentiment: dict[str, Any],
        news_digest: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.allow_llm:
            return {}

        try:
            client = DeepSeekClient()
            response = client.chat(
                LLMRequest(
                    system_prompt=MASTER_PROMPT,
                    user_prompt=_build_llm_prompt(
                        ticker=ticker,
                        snapshot=snapshot,
                        company_sentiment=company_sentiment,
                        market_sentiment=market_sentiment,
                        news_digest=news_digest,
                    ),
                    temperature=0.2,
                    max_tokens=900,
                )
            )
        except Exception as exc:
            return {"llm_metadata": {"provider": "deepseek", "error": str(exc)}}

        metadata = {
            "provider": "deepseek",
            "model": response.model,
            "usage": response.raw.get("usage", {}),
            "response_id": response.raw.get("id"),
        }
        trace_path = self._persist_llm_trace(ticker=ticker, response=response.raw, metadata=metadata)
        if trace_path is not None:
            metadata["trace_path"] = str(trace_path)

        parsed = _parse_llm_json(response.content)
        parsed["llm_metadata"] = metadata
        return parsed

    def _persist_llm_trace(self, ticker: str, response: dict[str, Any], metadata: dict[str, Any]) -> Path | None:
        directory = self.evidence_dir / "llm"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{ticker.upper()}_{date.today().isoformat()}_research_llm.json"
        payload = {"metadata": metadata, "response": response}
        try:
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        except OSError:
            return None
        return path


def _score_from_snapshot(snapshot: dict[str, Any]) -> dict[str, int]:
    metrics = snapshot.get("metrics", {})
    return {
        "growth_market": _bounded_score(metrics.get("revenue_growth_5y"), 0.0, 0.4, SCORE_WEIGHTS["growth_market"]),
        "unit_economics_margins": _bounded_score(metrics.get("fcf_margin_5y"), -0.1, 0.25, SCORE_WEIGHTS["unit_economics_margins"]),
        "quality_moat": _bounded_score(metrics.get("roic"), 0.0, 0.25, SCORE_WEIGHTS["quality_moat"]),
        "valuation": _inverse_score(metrics.get("ev_to_sales"), 20.0, 3.0, SCORE_WEIGHTS["valuation"]),
        "capital_discipline_dilution": _inverse_score(metrics.get("sbc_to_revenue"), 0.25, 0.02, SCORE_WEIGHTS["capital_discipline_dilution"]),
        "catalysts_revisions_sentiment": _sentiment_score(snapshot.get("sentiment", {}).get("company", {}), snapshot.get("news", {}).get("company", [])),
        "risk_fragility": _inverse_score(metrics.get("net_debt_to_ebitda"), 5.0, 0.0, SCORE_WEIGHTS["risk_fragility"]),
    }


def _sentiment_score(sentiment: dict[str, Any], news_items: list[dict[str, Any]]) -> int:
    score = float(sentiment.get("score", 0.0) or 0.0)
    news_bonus = min(0.15, 0.03 * len(news_items))
    normalized = max(-1.0, min(1.0, score + news_bonus if score > 0 else score - news_bonus if score < 0 else 0.0))
    return round(((normalized + 1) / 2) * SCORE_WEIGHTS["catalysts_revisions_sentiment"])


def _extract_catalysts(news_items: list[dict[str, Any]]) -> list[str]:
    catalysts = []
    for item in news_items[:5]:
        title = str(item.get("title", "")).strip()
        label = item.get("sentiment_label", "neutral")
        if title:
            catalysts.append(f"[{label}] {title}")
    return catalysts


def _build_llm_prompt(
    *,
    ticker: str,
    snapshot: dict[str, Any],
    company_sentiment: dict[str, Any],
    market_sentiment: dict[str, Any],
    news_digest: list[dict[str, Any]],
) -> str:
    payload = {
        "ticker": ticker.upper(),
        "company_name": snapshot.get("company_name"),
        "sector": snapshot.get("sector"),
        "industry": snapshot.get("industry"),
        "metrics": snapshot.get("metrics", {}),
        "company_sentiment": company_sentiment,
        "market_sentiment": market_sentiment,
        "news_digest": news_digest,
        "market_regime": snapshot.get("market_regime"),
        "macro": snapshot.get("macro", {}),
    }
    return (
        "Erzeuge eine qualitative Growth-Research-Einschaetzung und eine fundierte Charttechnik-Auswertung "
        "auf Basis der gelieferten Daten (RSI, gleitende Durchschnitte, Widerstaende/Unterstuetzungen). "
        "Antworte ausschliesslich als JSON mit folgenden Schluesseln: "
        "thesis_summary, technical_assessment, bull_case, bear_case, open_questions, falsification_tests. "
        "bull_case, bear_case, open_questions und falsification_tests muessen Arrays aus kurzen deutschen Saetzen sein. "
        "thesis_summary und technical_assessment als Strings. Keine Markdown-Ausgabe ausserhalb des JSON-Blocks.\n\n"
        f"Input:\n{json.dumps(payload, ensure_ascii=True)}"
    )

def _parse_llm_json(content: str) -> dict[str, Any]:
    raw = content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        "thesis_summary": parsed.get("thesis_summary"),
        "technical_assessment": parsed.get("technical_assessment"),
        "bull_case": _ensure_string_list(parsed.get("bull_case")),
        "bear_case": _ensure_string_list(parsed.get("bear_case")),
        "open_questions": _ensure_string_list(parsed.get("open_questions")),
        "falsification_tests": _ensure_string_list(parsed.get("falsification_tests")),
    }


def _ensure_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _merge_unique(*value_lists: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for values in value_lists:
        for value in values:
            key = value.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(key)
    return merged


def _bounded_score(value: Any, low: float, high: float, max_points: int) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0
    if numeric <= low:
        return 0
    if numeric >= high:
        return max_points
    return round(max_points * ((numeric - low) / (high - low)))


def _inverse_score(value: Any, bad: float, good: float, max_points: int) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0
    if numeric <= good:
        return max_points
    if numeric >= bad:
        return 0
    return round(max_points * ((bad - numeric) / (bad - good)))


def _category_for(score: int, hard_blockers: list[str]) -> str:
    if hard_blockers:
        return "Too Hard"
    if score >= 85:
        return "Quality Growth"
    if score >= 70:
        return "Transitional"
    if score >= 50:
        return "Hype/Risk"
    return "Ignore"
