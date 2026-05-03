"""
Embedding-Service für pgvector RAG.

Nutzt sentence-transformers lokal auf dem NUC.
Modell: all-MiniLM-L6-v2 (384 Dimensionen)
  - 22MB klein, schnell auf CPU
  - Gut für semantische Ähnlichkeit bei kurzen Texten
  - Multilingual genug für Deutsch/Englisch Mix

Läuft als asyncio.to_thread (CPU-bound).
"""
import asyncio
from typing import Optional
from backend.app.logger import get_logger

logger = get_logger(__name__)

# Lazy-Load des Modells (teuer beim ersten Import)
_model = None
MODEL_NAME = "all-MiniLM-L6-v2"


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import (
                SentenceTransformer
            )
            logger.info(
                f"Lade Embedding-Modell: {MODEL_NAME}"
            )
            _model = SentenceTransformer(MODEL_NAME)
            logger.info("Embedding-Modell geladen.")
        except ImportError:
            logger.warning(
                "sentence-transformers nicht installiert."
                " Embeddings deaktiviert."
            )
            return None
    return _model


def _embed_sync(text: str) -> Optional[list[float]]:
    """Generiert Embedding für einen Text (sync)."""
    model = _get_model()
    if model is None:
        return None
    try:
        vec = model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vec.tolist()
    except Exception as e:
        logger.debug(f"Embedding Fehler: {e}")
        return None


def _embed_batch_sync(
    texts: list[str],
) -> list[Optional[list[float]]]:
    """Batch-Embedding für mehrere Texte."""
    model = _get_model()
    if model is None:
        return [None] * len(texts)
    try:
        vecs = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return [v.tolist() for v in vecs]
    except Exception as e:
        logger.debug(f"Batch-Embedding Fehler: {e}")
        return [None] * len(texts)


async def embed_text(
    text: str,
) -> Optional[list[float]]:
    """Async wrapper für Embedding."""
    return await asyncio.to_thread(_embed_sync, text)


async def embed_batch(
    texts: list[str],
) -> list[Optional[list[float]]]:
    """Async wrapper für Batch-Embedding."""
    return await asyncio.to_thread(
        _embed_batch_sync, texts
    )


async def save_embedding(
    table: str,
    record_id: str,
    text: str,
) -> bool:
    """
    Generiert Embedding und speichert in DB.
    Wird nach INSERT in short_term_memory,
    long_term_memory, audit_reports aufgerufen.
    """
    vec = await embed_text(text)
    if vec is None:
        return False

    try:
        from backend.app.database import get_pool
        import json
        pool = await get_pool()
        async with pool.acquire() as conn:
            # pgvector erwartet Liste als String: [0.1, 0.2, ...]
            vec_str = "[" + ",".join(
                f"{v:.6f}" for v in vec
            ) + "]"
            await conn.execute(
                f'UPDATE "{table}" SET embedding = $1::vector '
                f'WHERE id = $2::uuid',
                vec_str, record_id,
            )
        return True
    except Exception as e:
        logger.debug(
            f"Embedding-Save Fehler [{table}]: {e}"
        )
        return False
