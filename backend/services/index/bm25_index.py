"""BM25 full-text sparse index service using rank-bm25."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class BM25IndexService:
    """Manages full-text sparse BM25 indexing for keyword retrieval.

    Uses BM25Okapi from the rank-bm25 library to score documents against
    a query using term-frequency / inverse-document-frequency weighting.
    """

    def __init__(self) -> None:
        self.corpus_ids: List[int] = []
        self.corpus_tokens: List[List[str]] = []
        self._bm25: Optional[BM25Okapi] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_index(self, evidence_items: List[Tuple[int, str]]) -> None:
        """Tokenize and index text evidence chunks.

        Args:
            evidence_items: List of (evidence_id, text) tuples to index.
        """
        if not evidence_items:
            logger.warning("BM25 build_index called with empty corpus. Index not built.")
            self.corpus_ids = []
            self.corpus_tokens = []
            self._bm25 = None
            return

        self.corpus_ids = [eid for eid, _ in evidence_items]
        self.corpus_tokens = [self._tokenize(text) for _, text in evidence_items]
        self._bm25 = BM25Okapi(self.corpus_tokens)

        logger.info("BM25 index built with %d documents.", len(self.corpus_ids))

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Perform BM25 scoring search against the indexed corpus.

        Args:
            query: Raw query string.
            top_k: Maximum number of results to return.

        Returns:
            List of (evidence_id, score) tuples sorted by score descending.
            Only results with score > 0 are included.
        """
        if self._bm25 is None or not self.corpus_ids:
            logger.debug("BM25 search called but index is not built. Returning [].")
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            logger.debug("BM25 query tokenized to empty list. Returning [].")
            return []

        scores = self._bm25.get_scores(query_tokens)

        # Pair each corpus id with its score, filter zeros, sort descending
        scored: List[Tuple[int, float]] = [
            (self.corpus_ids[i], float(scores[i]))
            for i in range(len(scores))
            if scores[i] > 0.0
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        results = scored[:top_k]
        logger.debug("BM25 search for '%s': %d results (top_k=%d).", query, len(results), top_k)
        return results

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple whitespace + lowercase tokenizer."""
        return text.lower().split()


bm25_index_service = BM25IndexService()
