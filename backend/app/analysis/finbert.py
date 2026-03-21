"""
finbert — Lokale Sentiment-Analyse für Finanznachrichten

Input:  headline: str oder list[str]
Output: float (-1 bis +1) oder list[float]
Deps:   config.py, logger.py
Config: config/settings.yaml → use_mock_data, config/alerts.yaml → finbert.relevance_threshold
API:    Keine (lokales Modell)
"""

from backend.app.config import settings
from backend.app.logger import get_logger

logger = get_logger(__name__)

_model = None
_tokenizer = None
_finbert_available = True


def _load_model():
    """Lädt FinBERT einmalig in den Speicher. Lazy-Init für schnellen Container-Start."""
    global _model, _tokenizer, _finbert_available
    if _model is None:
        try:
            logger.info("Lade FinBERT-Modell... (einmalig, dauert ~10 Sekunden)")
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch  # noqa: F401

            _tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
            _model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
            _model.eval()
            _finbert_available = True
            logger.info("FinBERT geladen und bereit.")
        except ImportError:
            _finbert_available = False
            _model = None
            _tokenizer = None
            logger.warning("FinBERT nicht verfügbar — torch oder transformers fehlt")
        except Exception as exc:
            _finbert_available = False
            _model = None
            _tokenizer = None
            logger.warning("FinBERT konnte nicht geladen werden — neutraler Fallback aktiv: %s", exc)


def analyze_sentiment(text: str) -> float:
    """
    Berechnet einen Sentiment-Score für einen einzelnen Text.
    Returns: float von -1.0 (sehr negativ) bis +1.0 (sehr positiv). 0.0 = neutral.
    """
    if settings.use_mock_data:
        text_lower = text.lower()
        negative_keywords = ["investigation", "miss", "downgrade", "loss", "decline", "lawsuit", "resign", "cut", "warning"]
        positive_keywords = ["beat", "upgrade", "raise", "growth", "record", "surge", "expand", "strong"]
        neg_count = sum(1 for kw in negative_keywords if kw in text_lower)
        pos_count = sum(1 for kw in positive_keywords if kw in text_lower)
        if pos_count > neg_count:
            return 0.6
        elif neg_count > pos_count:
            return -0.6
        return 0.0

    _load_model()
    if not _finbert_available or _model is None or _tokenizer is None:
        return 0.0

    import torch
    inputs = _tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
    with torch.no_grad():
        outputs = _model(**inputs)
        probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
    positive = probabilities[0][0].item()
    negative = probabilities[0][1].item()
    score = positive - negative
    return round(score, 4)


def analyze_sentiment_batch(texts: list[str]) -> list[float]:
    """Berechnet Sentiment-Scores für eine Liste von Texten. Effizienter als Einzelaufrufe."""
    if settings.use_mock_data:
        return [analyze_sentiment(t) for t in texts]

    _load_model()
    if not _finbert_available or _model is None or _tokenizer is None:
        return [0.0 for _ in texts]

    import torch
    inputs = _tokenizer(texts, return_tensors="pt", truncation=True, max_length=512, padding=True)
    with torch.no_grad():
        outputs = _model(**inputs)
        probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
    scores = []
    for i in range(len(texts)):
        positive = probabilities[i][0].item()
        negative = probabilities[i][1].item()
        scores.append(round(positive - negative, 4))
    return scores
