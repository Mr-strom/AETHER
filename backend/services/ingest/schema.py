"""Shared dataclass for ingestion pipeline output.

All ingest extractors return a list of :class:`IngestChunk` objects.
These are then persisted to the database and indexed by the embedding service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class IngestChunk:
    """Standardized evidence unit produced by every ingest extractor.

    Attributes:
        source_path: Absolute path string of the origin file.
        chunk_index: Zero-based chunk position within its source.
        text: Extracted / cleaned text content of the chunk.
        modality: Always ``"text"`` for text-only extractors.
        page_number: 1-based page number for PDFs; ``None`` otherwise.
        char_count: Length of ``text`` in characters.
        embedding_id: Populated after FAISS indexing (FAISS internal int id).
        bbox: Bounding-box dict ``{x0, y0, x1, y1}`` for PDF blocks; else ``None``.
        extra: Any extractor-specific metadata (heading level, table id, …).
    """

    source_path: str
    chunk_index: int
    text: str
    modality: str = "text"
    page_number: Optional[int] = None
    char_count: int = 0
    embedding_id: Optional[int] = None
    bbox: Optional[dict[str, float]] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.char_count:
            self.char_count = len(self.text)
