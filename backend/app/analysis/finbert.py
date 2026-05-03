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
            import torch
            import os

            # NUC i3: 4 Kerne. 2 für FinBERT, 2 für System.
            # set_num_threads steuert intra-op Parallelismus
            # set_num_interop_threads steuert inter-op
            torch.set_num_threads(2)
            torch.set_num_interop_threads(1)
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            if torch.backends.mps.is_available():
                device = "mps"
            
            logger.info(f"Nutze Device: {device}")

            # Nutze /app/model_cache wenn vorhanden,
            # sonst HuggingFace Default
            cache_dir = (
                "/app/model_cache"
                if os.path.isdir("/app/model_cache")
                else None
            )
            
            _tokenizer = AutoTokenizer.from_pretrained(
                "ProsusAI/finbert",
                cache_dir=cache_dir,
            )
            _model = AutoModelForSequenceClassification.from_pretrained(
                "ProsusAI/finbert",
                cache_dir=cache_dir,
            )
            _model.to(device)
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
    device = next(_model.parameters()).device
    inputs = _tokenizer(text, return_tensors="pt", truncation=True, max_length=64, padding=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = _model(**inputs)
        probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
    
    positive = probabilities[0][0].item()
    negative = probabilities[0][1].item()
    score = positive - negative
    return round(score, 4)


def analyze_sentiment_batch(
    texts: list[str],
    batch_size: int = 16,
) -> list[float]:
    """Batch-Sentiment mit Chunk-Verarbeitung."""
    if settings.use_mock_data:
        return [analyze_sentiment(t) for t in texts]

    _load_model()
    if not _finbert_available or _model is None:
        return [0.0] * len(texts)

    import torch
    import time
    t0 = time.perf_counter()
    
    all_scores: list[float] = []

    # In Chunks verarbeiten
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        try:
            inputs = _tokenizer(
                chunk,
                return_tensors="pt",
                truncation=True,
                max_length=64,
                padding=True,
            )
            device = next(_model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = _model(**inputs)
                probs = torch.nn.functional.softmax(
                    outputs.logits, dim=-1
                )
            for j in range(len(chunk)):
                pos = probs[j][0].item()
                neg = probs[j][1].item()
                # Neutral (idx 2) bewusst ignoriert —
                # Score repräsentiert Netto-Sentiment
                all_scores.append(
                    round(pos - neg, 4)
                )
        except Exception as e:
            logger.warning(
                f"FinBERT Chunk {i}-{i+batch_size}"
                f" Fehler: {e}"
            )
            all_scores.extend([0.0] * len(chunk))

    elapsed = (time.perf_counter() - t0) * 1000
    if len(texts) > 1:
        logger.debug(
            f"FinBERT Batch {len(texts)} Texte: "
            f"{elapsed:.0f}ms "
            f"({elapsed/len(texts):.1f}ms/Text)"
        )
    
    return all_scores


async def analyze_sentiment_async(
    text: str,
) -> float:
    """Async-sicherer Wrapper für Event-Loop-Kontext."""
    import asyncio
    return await asyncio.to_thread(
        analyze_sentiment, text
    )

async def analyze_sentiment_batch_async(
    texts: list[str],
) -> list[float]:
    """Async-sicherer Wrapper für Batch."""
    import asyncio
    return await asyncio.to_thread(
        analyze_sentiment_batch, texts
    )
