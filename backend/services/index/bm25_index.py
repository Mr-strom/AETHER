"""rank-bm25 full-text index service stub."""

from typing import Sequence


class BM25IndexService:
    """Manages full-text sparse BM25 indexing for keyword retrieval."""

    def __init__(self):
        self.corpus_ids: list[int] = []
        self.corpus_tokens: list[list[str]] = []

    def build_index(self, evidence_items: list[tuple[int, str]]) -> None:
        """Tokenize and index text evidence chunks."""
        # Stub implementation
        pass

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Perform BM25 scoring search."""
        # Stub implementation
        return []


bm25_index_service = BM25IndexService()
