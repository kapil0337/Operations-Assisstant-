"""Singleton SentenceTransformer — eager-loaded at startup, lazy-fallback for tests."""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

_model = None
_lock = threading.Lock()


def get_model():
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is None:
            from app.config import get_settings
            from sentence_transformers import SentenceTransformer
            settings = get_settings()
            logger.info("Loading embedding model %s ...", settings.embedding_model)
            _model = SentenceTransformer(settings.embedding_model)
            logger.info("Embedding model ready.")
    return _model


def embed_text(text: str) -> list[float]:
    vector = get_model().encode(text, normalize_embeddings=True)
    return vector.tolist()
