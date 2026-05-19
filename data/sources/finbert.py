from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any


@dataclass(frozen=True)
class SentimentResult:
    label: str
    score: float
    model: str
    reason: str | None = None


class FinBERTClassifier:
    """Lazy FinBERT wrapper with a deterministic fallback.

    The primary path uses `ProsusAI/finbert` via transformers. If the runtime does not have the
    model dependencies yet, the classifier falls back to a tiny keyword heuristic so snapshot
    generation still succeeds and records that FinBERT was unavailable.
    """

    model_name = "ProsusAI/finbert"

    def __init__(self) -> None:
        self._pipeline = None
        self._load_error: str | None = None

    def classify(self, text: str) -> SentimentResult:
        content = (text or "").strip()
        if not content:
            return SentimentResult(label="neutral", score=0.0, model=self.model_name, reason="empty_text")

        pipeline = self._ensure_pipeline()
        if pipeline is None:
            return self._fallback(content)

        raw = pipeline(content[:3500], truncation=True)[0]
        label = _normalize_label(str(raw.get("label", "neutral")))
        confidence = float(raw.get("score", 0.0))
        signed_score = _signed_score(label, confidence)
        return SentimentResult(label=label, score=signed_score, model=self.model_name)

    def batch_classify(self, texts: list[str]) -> list[SentimentResult]:
        return [self.classify(text) for text in texts]

    def summarize(self, results: list[SentimentResult]) -> dict[str, Any]:
        if not results:
            return {
                "label": "neutral",
                "score": 0.0,
                "counts": {"positive": 0, "neutral": 0, "negative": 0},
                "model": self.model_name,
                "reason": "no_texts",
            }

        counts = {"positive": 0, "neutral": 0, "negative": 0}
        reasons = []
        for result in results:
            counts[result.label] = counts.get(result.label, 0) + 1
            if result.reason:
                reasons.append(result.reason)

        average_score = round(mean(result.score for result in results), 4)
        label = "positive" if average_score >= 0.15 else "negative" if average_score <= -0.15 else "neutral"
        return {
            "label": label,
            "score": average_score,
            "counts": counts,
            "model": self.model_name,
            "reason": reasons[0] if reasons else None,
        }

    def _ensure_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        if self._load_error is not None:
            return None

        try:
            from transformers import pipeline

            self._pipeline = pipeline(
                "text-classification",
                model=self.model_name,
                tokenizer=self.model_name,
            )
        except Exception as exc:  # pragma: no cover - depends on local ML runtime
            self._load_error = str(exc)
            return None

        return self._pipeline

    def _fallback(self, text: str) -> SentimentResult:
        positive_terms = ("beat", "surge", "growth", "raise", "upgrade", "strong", "profit")
        negative_terms = ("miss", "cut", "downgrade", "fraud", "probe", "weak", "loss")
        lowered = text.lower()
        positive_hits = sum(term in lowered for term in positive_terms)
        negative_hits = sum(term in lowered for term in negative_terms)

        if positive_hits > negative_hits:
            return SentimentResult(
                label="positive",
                score=min(0.6, 0.15 * positive_hits),
                model=self.model_name,
                reason="finbert_unavailable_fallback",
            )
        if negative_hits > positive_hits:
            return SentimentResult(
                label="negative",
                score=max(-0.6, -0.15 * negative_hits),
                model=self.model_name,
                reason="finbert_unavailable_fallback",
            )
        return SentimentResult(
            label="neutral",
            score=0.0,
            model=self.model_name,
            reason="finbert_unavailable_fallback",
        )


def _normalize_label(raw_label: str) -> str:
    label = raw_label.strip().lower()
    if "pos" in label:
        return "positive"
    if "neg" in label:
        return "negative"
    return "neutral"


def _signed_score(label: str, confidence: float) -> float:
    if label == "positive":
        return round(confidence, 4)
    if label == "negative":
        return round(-confidence, 4)
    return 0.0