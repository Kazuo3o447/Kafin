from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


SCORE_WEIGHTS = {
    "growth_market": 18,
    "unit_economics_margins": 14,
    "quality_moat": 18,
    "valuation": 14,
    "capital_discipline_dilution": 12,
    "catalysts_revisions_sentiment": 12,
    "risk_fragility": 12,
}


@dataclass
class ResearchCard:
    ticker: str
    company_name: str = "unknown"
    exchange: str = "unknown"
    sector: str = "unknown"
    industry: str = "unknown"
    research_date: str = field(default_factory=lambda: date.today().isoformat())
    category: str = "Too Hard"
    growth_research_score: int = 0
    gate: str = "Yellow"
    confidence: str = "low"
    thesis_summary: str = ""
    technical_assessment: str = ""
    bull_case: list[str] = field(default_factory=list)
    bear_case: list[str] = field(default_factory=list)
    key_metrics: dict[str, Any] = field(default_factory=dict)
    score_breakdown: dict[str, int] = field(default_factory=dict)
    moat_assessment: dict[str, Any] = field(default_factory=dict)
    catalysts: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    hard_blockers: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    falsification_tests: list[str] = field(default_factory=list)
    company_sentiment: dict[str, Any] = field(default_factory=dict)
    market_sentiment: dict[str, Any] = field(default_factory=dict)
    news_digest: list[dict[str, Any]] = field(default_factory=list)
    llm_metadata: dict[str, Any] = field(default_factory=dict)
    source_list: list[dict[str, Any]] = field(default_factory=list)
    handoff_to_trade_engine: bool = False
    status: str = "research_complete"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        metrics_rows = []
        for name, value in sorted(self.key_metrics.items()):
            metrics_rows.append(f"| {name} | {value if value is not None else 'unknown'} | local snapshot |")
        metrics_table = "\n".join(metrics_rows) if metrics_rows else "| unknown | unknown | unknown |"

        return f"""# Research Card: {self.company_name} ({self.ticker})

## 1. Kurzfazit
- Kategorie: {self.category}
- Growth Research Score: {self.growth_research_score}
- Gate: {self.gate}
- Confidence: {self.confidence}
- Handoff an Trade-Engine: {'ja' if self.handoff_to_trade_engine else 'nein'}

## 2. Investment-/Research-These
{self.thesis_summary or 'unknown'}

## 2.1 Technische Analyse & Chartbild
{self.technical_assessment or 'Noch keine dedizierte Chart-Bewertung verfuegbar.'}

## 3. Warum ist die Aktie interessant?
{_format_list(self.bull_case)}

## 4. Wichtigste Kennzahlen
| Kennzahl | Wert | Quelle |
|---|---:|---|
{metrics_table}

## 5. Wachstum
{self.score_breakdown.get('growth_market', 0)} von {SCORE_WEIGHTS['growth_market']} Punkten.

## 6. Unit Economics und Margen
{self.score_breakdown.get('unit_economics_margins', 0)} von {SCORE_WEIGHTS['unit_economics_margins']} Punkten.

## 7. Moat
Rating: {self.moat_assessment.get('rating', 'Unknown')}

## 8. Bewertung
{self.score_breakdown.get('valuation', 0)} von {SCORE_WEIGHTS['valuation']} Punkten.

## 9. Kapitaldisziplin und Verwaesserung
{self.score_breakdown.get('capital_discipline_dilution', 0)} von {SCORE_WEIGHTS['capital_discipline_dilution']} Punkten.

## 10. Katalysatoren und Revisionen
{_format_list(self.catalysts)}

## 11. Sentiment
- Unternehmen: {self.company_sentiment.get('label', 'unknown')} ({self.company_sentiment.get('score', 'unknown')})
- Markt: {self.market_sentiment.get('label', 'unknown')} ({self.market_sentiment.get('score', 'unknown')})

## 11.1 LLM Audit
- Provider: {self.llm_metadata.get('provider', 'unknown')}
- Modell: {self.llm_metadata.get('model', 'unknown')}
- Input-Tokens: {self.llm_metadata.get('usage', {}).get('prompt_tokens', 'unknown')}
- Output-Tokens: {self.llm_metadata.get('usage', {}).get('completion_tokens', 'unknown')}

## 12. News Digest
{_format_news(self.news_digest)}

## 13. Risiken
{_format_list(self.bear_case + self.red_flags)}

## 14. Red-Team-Kritik
Noch nicht eingebettet. Siehe separaten Red-Team-Report.

## 15. Falsifikationspunkte
{_format_list(self.falsification_tests)}

## 16. Offene Fragen
{_format_list(self.open_questions)}

## 17. Entscheidung
{'an Trade-Screener uebergeben' if self.handoff_to_trade_engine else 'Research Only / nicht freigegeben'}
"""

    def write_files(self, cards_dir: Path) -> tuple[Path, Path]:
        cards_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{self.ticker.upper()}_{self.research_date}"
        markdown_path = cards_dir / f"{stem}.md"
        json_path = cards_dir / f"{stem}.json"
        markdown_path.write_text(self.to_markdown(), encoding="utf-8")
        json_path.write_text(self.to_json(), encoding="utf-8")
        return markdown_path, json_path


def _format_list(values: list[str]) -> str:
    if not values:
        return "- unknown"
    return "\n".join(f"- {value}" for value in values)


def _format_news(items: list[dict[str, Any]]) -> str:
    if not items:
        return "- unknown"
    lines = []
    for item in items[:5]:
        label = item.get("sentiment_label", "unknown")
        title = item.get("title", "unknown")
        source = item.get("source", "unknown")
        lines.append(f"- [{label}] {title} ({source})")
    return "\n".join(lines)
