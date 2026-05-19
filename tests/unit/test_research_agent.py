from __future__ import annotations

import json
from pathlib import Path

from agents.common import LLMResponse
from agents.research.agent import ResearchAgent


def test_research_agent_keeps_sentiment_and_skips_llm_when_disabled(tmp_path: Path):
    snapshot = {
        "company_name": "NVIDIA Corp",
        "sector": "Technology",
        "industry": "Semiconductors",
        "metrics": {
            "revenue_growth_5y": 0.25,
            "fcf_margin_5y": 0.12,
            "roic": 0.2,
            "ev_to_sales": 9,
            "sbc_to_revenue": 0.03,
            "net_debt_to_ebitda": 0.2,
        },
        "news": {
            "company": [{"title": "Strong demand", "sentiment_label": "positive", "source": "rss"}],
        },
        "sentiment": {
            "company": {"label": "positive", "score": 0.42},
            "market": {"label": "neutral", "score": 0.0},
        },
        "sources": [],
        "quality_errors": [],
    }

    agent = ResearchAgent(allow_llm=False, evidence_dir=tmp_path)
    card = agent.run("NVDA", snapshot)

    assert card.company_sentiment["label"] == "positive"
    assert card.news_digest[0]["title"] == "Strong demand"
    assert card.llm_metadata == {}


def test_research_agent_persists_llm_trace_when_call_succeeds(tmp_path: Path, monkeypatch):
    snapshot = {
        "company_name": "NVIDIA Corp",
        "sector": "Technology",
        "industry": "Semiconductors",
        "metrics": {
            "revenue_growth_5y": 0.25,
            "fcf_margin_5y": 0.12,
            "roic": 0.2,
            "ev_to_sales": 9,
            "sbc_to_revenue": 0.03,
            "net_debt_to_ebitda": 0.2,
        },
        "news": {
            "company": [{"title": "Strong demand", "sentiment_label": "positive", "source": "rss"}],
        },
        "sentiment": {
            "company": {"label": "positive", "score": 0.42},
            "market": {"label": "neutral", "score": 0.0},
        },
        "sources": [],
        "quality_errors": [],
    }

    def fake_chat(self, request):
        return LLMResponse(
            content=json.dumps(
                {
                    "thesis_summary": "Qualitative summary.",
                    "bull_case": ["AI Nachfrage bleibt hoch."],
                    "bear_case": ["Bewertung bleibt anspruchsvoll."],
                    "open_questions": ["Wie nachhaltig ist die Nachfrage?"],
                    "falsification_tests": ["Margen duerfen nicht einbrechen."],
                }
            ),
            model="deepseek-v4-flash",
            raw={"id": "resp-1", "usage": {"prompt_tokens": 123, "completion_tokens": 45}},
        )

    monkeypatch.setattr("agents.research.agent.DeepSeekClient.chat", fake_chat)

    agent = ResearchAgent(allow_llm=True, evidence_dir=tmp_path)
    card = agent.run("NVDA", snapshot)

    assert card.llm_metadata["model"] == "deepseek-v4-flash"
    assert card.llm_metadata["usage"]["prompt_tokens"] == 123
    trace_path = Path(card.llm_metadata["trace_path"])
    assert trace_path.exists()