"""BGE-M3 text embedding service — singleton with lazy loading.

The model is loaded **once** on first use and kept in memory for the
lifetime of the process.  This reflects the TRD's "always resident"
requirement for BGE-M3.

Batch processing
----------------
:meth:`EmbeddingService.embed_texts` splits input into batches of
``settings.EMBED_BATCH_SIZE`` (default 32) to stay within model RAM
limits and avoid OOM on long ingest jobs.

Dimensions
----------
BGE-M3's dense output is **1024-dimensional**.  The service validates
this at runtime and raises :exc:`RuntimeError` if the shape is unexpected.

Empty-string handling
---------------------
Empty or whitespace-only strings are replaced with a sentinel phrase
(``" "`` / single space) so the model always receives valid input.  The
caller receives the corresponding zero-ish vector; it will rank low in
FAISS searches but will not cause crashes.

Example
-------
>>> from backend.services.index.embeddings import embedding_service
>>> vecs = embedding_service.embed_texts(["hello world"])
>>> len(vecs[0])
1024
"""

from __future__ import annotations

import logging
import threading
from typing import List

import numpy as np

from backend.app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentinel used in place of empty strings to prevent model errors.
# ---------------------------------------------------------------------------
_EMPTY_SENTINEL = " "


class EmbeddingService:
    """Singleton BGE-M3 embedding service.

    The underlying ``SentenceTransformer`` model is loaded lazily on the
    first call to :meth:`embed_texts` or :meth:`embed_query`.

    Thread safety
    -------------
    A ``threading.Lock`` prevents concurrent initialisation from loading
    the model twice.
    """

    def __init__(self) -> None:
        self._model = None  # type: ignore[assignment]
        self._lock = threading.Lock()
        self._model_name = settings.EMBED_MODEL_NAME
        self._batch_size = settings.EMBED_BATCH_SIZE
        self._expected_dim = settings.EMBED_DIM

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_loaded(self) -> bool:
        """Return True if the embedding model has been loaded."""
        return self._model is not None

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Compute dense embeddings for a batch of text strings.

        Args:
            texts: List of text strings to embed.  Empty strings are
                replaced with a single whitespace sentinel so the model
                always receives valid input.

        Returns:
            List of 1024-dimensional float vectors, one per input string.
            Preserves input order.

        Raises:
            RuntimeError: If the model returns an unexpected embedding
                dimension.
        """
        if not texts:
            return []

        model = self._get_model()

        # Replace empty strings
        cleaned = [t if t.strip() else _EMPTY_SENTINEL for t in texts]

        all_vectors: List[np.ndarray] = []

        for batch_start in range(0, len(cleaned), self._batch_size):
            batch = cleaned[batch_start : batch_start + self._batch_size]
            vecs: np.ndarray = model.encode(
                batch,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=self._batch_size,
            )
            if vecs.ndim == 1:
                vecs = vecs.reshape(1, -1)
            if vecs.shape[1] != self._expected_dim:
                raise RuntimeError(
                    f"Unexpected embedding dim: got {vecs.shape[1]}, "
                    f"expected {self._expected_dim}."
                )
            all_vectors.append(vecs)

        result = np.vstack(all_vectors)  # (N, 1024)
        return result.tolist()

    def embed_query(self, query: str) -> List[float]:
        """Compute a single query embedding.

        Convenience wrapper around :meth:`embed_texts` for single-string
        use-cases (retrieval path).

        Args:
            query: The query string.

        Returns:
            1024-dimensional float vector.
        """
        vecs = self.embed_texts([query or _EMPTY_SENTINEL])
        return vecs[0]

    def is_loaded(self) -> bool:
        """Return ``True`` if the model is currently loaded into memory."""
        return self._model is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_model(self):
        """Return the loaded model, initialising it if necessary (thread-safe)."""
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                logger.info(
                    "Loading embedding model '%s' …", self._model_name
                )
                try:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(
                        self._model_name,
                        trust_remote_code=True,
                    )
                    logger.info(
                        "Embedding model '%s' loaded successfully.",
                        self._model_name,
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to load embedding model '%s': %s",
                        self._model_name,
                        exc,
                    )
                    raise RuntimeError(
                        f"Cannot load embedding model '{self._model_name}': {exc}"
                    ) from exc
        return self._model


# Module-level singleton — import this in other modules.
embedding_service = EmbeddingService()
