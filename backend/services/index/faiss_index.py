"""FAISS-cpu vector index for 1024-dimensional BGE-M3 embeddings.

Uses ``IndexFlatIP`` (inner-product / cosine when vectors are L2-normalised)
which matches BGE-M3's training objective.

ID mapping
----------
FAISS assigns dense sequential integer IDs (0, 1, 2, …).  We maintain a
parallel list ``_id_map`` where ``_id_map[faiss_id] = evidence_chunk_id``
so we can translate search results back to DB row identifiers.

Persistence
-----------
The index is saved to ``settings.FAISS_INDEX_PATH`` (a ``.faiss`` file)
and a companion ``.ids`` file (newline-delimited integer IDs).  Both files
must be present to reload a previously saved index.

Thread safety
-------------
``faiss`` itself is not thread-safe for concurrent writes; all writes are
serialised with a ``threading.Lock``.  Reads (search) are safe to
parallelise once the index is built.

Example
-------
>>> import numpy as np
>>> from backend.services.index.faiss_index import faiss_index_service
>>> vecs = np.random.rand(5, 1024).astype("float32")
>>> faiss_index_service.add_vectors(vecs, ids=[10, 20, 30, 40, 50])
>>> dists, ids = faiss_index_service.search(vecs[0], k=3)
>>> ids
[10, 20, 30]
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import List, Tuple

import numpy as np

from backend.app.config import settings

logger = logging.getLogger(__name__)


def _require_faiss():
    """Lazy-import FAISS and return the module, raising a helpful error if absent."""
    try:
        import faiss as _faiss  # noqa: F401

        return _faiss
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "faiss-cpu is required: pip install faiss-cpu"
        ) from exc


class FAISSIndexService:
    """In-memory FAISS flat inner-product index with EvidenceChunk ID mapping.

    Parameters
    ----------
    dim:
        Embedding dimensionality (default ``settings.EMBED_DIM`` = 1024).
    index_path:
        Filesystem path for the ``.faiss`` index file
        (default ``settings.FAISS_INDEX_PATH``).
    """

    def __init__(
        self,
        dim: int | None = None,
        index_path: Path | None = None,
    ) -> None:
        self.dim = dim or settings.EMBED_DIM
        self.index_path = Path(index_path or settings.FAISS_INDEX_PATH)
        self._id_map: List[int] = []  # FAISS sequential id → evidence_chunk_id
        self._index = None  # Lazy-init on first use
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_vectors(
        self,
        vectors: np.ndarray,
        ids: List[int],
    ) -> None:
        """Add pre-computed embedding vectors to the index.

        Vectors must already be L2-normalised (as produced by
        :class:`~backend.services.index.embeddings.EmbeddingService` with
        ``normalize_embeddings=True``).

        Args:
            vectors: Float32 array of shape ``(N, dim)``.
            ids: List of ``EvidenceChunk.id`` values, length N.

        Raises:
            ValueError: If shapes are inconsistent.
        """
        vectors = _coerce_float32(vectors)
        if vectors.ndim != 2 or vectors.shape[1] != self.dim:
            raise ValueError(
                f"Expected shape (N, {self.dim}), got {vectors.shape}."
            )
        if len(ids) != len(vectors):
            raise ValueError(
                f"ids length {len(ids)} != vectors length {len(vectors)}."
            )

        with self._lock:
            index = self._get_or_create_index()
            index.add(vectors)
            self._id_map.extend(ids)
            logger.debug(
                "Added %d vectors; index total: %d", len(ids), index.ntotal
            )

    def search(
        self,
        query_vector: np.ndarray,
        k: int = 10,
    ) -> Tuple[List[float], List[int]]:
        """Retrieve the top-*k* nearest evidence chunks for *query_vector*.

        Args:
            query_vector: Float32 array of shape ``(dim,)`` or ``(1, dim)``.
            k: Number of nearest neighbours to return.

        Returns:
            Tuple ``(distances, evidence_chunk_ids)`` both of length
            ``min(k, index.ntotal)``.  ``distances`` are inner-product
            scores (higher = more similar). Unknown FAISS IDs (-1) are
            filtered out.
        """
        if self._index is None or self._index.ntotal == 0:
            logger.warning("FAISS index is empty; returning no results.")
            return [], []

        q = _coerce_float32(query_vector)
        if q.ndim == 1:
            q = q.reshape(1, -1)

        k_clamped = min(k, self._index.ntotal)
        distances, faiss_ids = self._index.search(q, k_clamped)

        out_dists: List[float] = []
        out_ids: List[int] = []

        for dist, fid in zip(distances[0].tolist(), faiss_ids[0].tolist()):
            if fid < 0 or fid >= len(self._id_map):
                continue  # FAISS sentinel -1
            out_dists.append(dist)
            out_ids.append(self._id_map[fid])

        return out_dists, out_ids

    def save(self, path: Path | None = None) -> None:
        """Persist the index and ID map to disk.

        Args:
            path: Override for the save directory / filename base.
                Defaults to ``self.index_path``.
        """
        import faiss as _faiss  # already imported via _get_or_create_index

        target = Path(path or self.index_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            if self._index is None:
                logger.warning("Nothing to save: index not initialised.")
                return
            _faiss.write_index(self._index, str(target))
            ids_path = target.with_suffix(".ids")
            ids_path.write_text("\n".join(str(i) for i in self._id_map))
            logger.info(
                "FAISS index saved to '%s' (%d vectors).",
                target,
                self._index.ntotal,
            )

    def load(self, path: Path | None = None) -> None:
        """Load a previously saved index and ID map from disk.

        Args:
            path: Path to the ``.faiss`` file.  The companion ``.ids``
                file must exist at the same stem.

        Raises:
            FileNotFoundError: If the index file or IDs file is missing.
            RuntimeError: If FAISS cannot deserialise the file.
        """
        faiss = _require_faiss()

        target = Path(path or self.index_path)
        ids_path = target.with_suffix(".ids")

        if not target.exists():
            raise FileNotFoundError(f"FAISS index file not found: {target}")
        if not ids_path.exists():
            raise FileNotFoundError(f"FAISS IDs file not found: {ids_path}")

        try:
            loaded = faiss.read_index(str(target))
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load FAISS index from '{target}': {exc}"
            ) from exc

        raw_ids = ids_path.read_text().splitlines()
        id_map = [int(i) for i in raw_ids if i.strip()]

        with self._lock:
            self._index = loaded
            self._id_map = id_map
            logger.info(
                "FAISS index loaded from '%s' (%d vectors).",
                target,
                loaded.ntotal,
            )

    @property
    def total_vectors(self) -> int:
        """Return the number of vectors currently stored in the index."""
        if self._index is None:
            return 0
        return self._index.ntotal

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_index(self):
        """Return the FAISS index, creating it if it has not been initialised."""
        if self._index is None:
            faiss = _require_faiss()
            self._index = faiss.IndexFlatIP(self.dim)
            logger.info(
                "Created FAISS IndexFlatIP (dim=%d).", self.dim
            )
        return self._index


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _coerce_float32(arr: np.ndarray) -> np.ndarray:
    """Ensure *arr* is a contiguous float32 array (FAISS requirement)."""
    arr = np.asarray(arr, dtype=np.float32)
    return np.ascontiguousarray(arr)


# Module-level singleton.
faiss_index_service = FAISSIndexService()
