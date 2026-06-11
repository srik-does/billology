"""Local embedding generation via fastembed.

Embeddings are generated on the backend (inside the trust boundary) — no text
leaves the device for embedding (Principle IV). The output dimension is asserted
against the configured pgvector dimension to prevent a silent column mismatch.
"""

from __future__ import annotations

from functools import lru_cache

from src.config import get_settings


@lru_cache
def _model():
    # Imported lazily so the package can be imported without the (heavy) model
    # weights being loaded until an embedding is actually requested.
    from fastembed import TextEmbedding

    settings = get_settings()
    return TextEmbedding(model_name=settings.embedding_model)


def embed(text: str) -> list[float]:
    """Return the embedding vector for ``text`` and assert its dimension."""
    settings = get_settings()
    vector = list(next(iter(_model().embed([text]))))
    if len(vector) != settings.embedding_dim:
        raise ValueError(
            f"Embedding dim {len(vector)} != configured EMBEDDING_DIM "
            f"{settings.embedding_dim}; update the pgvector column or config."
        )
    return [float(x) for x in vector]
