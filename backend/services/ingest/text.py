"""Plain-text and Markdown file ingestion extractor.

Supported formats: ``.txt``, ``.md`` (and any UTF-8 text file).

The extractor reads the file with automatic encoding detection
(UTF-8 first, then Latin-1 as a safe fallback), then splits
the content into overlapping character-level chunks sized at
:attr:`~backend.app.config.Settings.CHUNK_SIZE_CHARS` with
:attr:`~backend.app.config.Settings.CHUNK_OVERLAP_CHARS` overlap.

Example
-------
>>> import asyncio
>>> chunks = asyncio.run(TextIngester().parse("notes.txt"))
>>> chunks[0].text[:40]
'This is the first chunk of the document.'
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from backend.app.config import settings
from backend.services.ingest.schema import IngestChunk

logger = logging.getLogger(__name__)

_ENCODINGS = ("utf-8", "latin-1")


def _read_file(path: Path) -> str:
    """Read *path* trying multiple encodings in order.

    Args:
        path: Path to the text file.

    Returns:
        Decoded file contents.

    Raises:
        ValueError: If the file cannot be decoded with any known encoding.
    """
    for enc in _ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(
        f"Cannot decode '{path}' with any of {_ENCODINGS}."
    )


def _split_into_chunks(
    text: str,
    chunk_size: int,
    overlap: int,
    source_path: str,
) -> List[IngestChunk]:
    """Split *text* into overlapping character-level windows.

    Args:
        text: Full file content as a single string.
        chunk_size: Maximum characters per chunk.
        overlap: Number of characters to repeat at the start of each
            subsequent chunk (sliding window).
        source_path: Origin file path stored in every chunk.

    Returns:
        Ordered list of :class:`IngestChunk` objects.
    """
    chunks: List[IngestChunk] = []

    if not text.strip():
        logger.warning("Empty or whitespace-only file: %s", source_path)
        return chunks

    start = 0
    index = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        raw = text[start:end]

        # Prefer to break at a newline boundary to avoid mid-sentence cuts.
        if end < text_len:
            last_nl = raw.rfind("\n")
            if last_nl > chunk_size // 2:
                end = start + last_nl + 1
                raw = text[start:end]

        chunk_text = raw.strip()
        if chunk_text:
            chunks.append(
                IngestChunk(
                    source_path=source_path,
                    chunk_index=index,
                    text=chunk_text,
                    modality="text",
                )
            )
            index += 1

        if end >= text_len:
            break

        # Advance with overlap
        next_start = end - overlap
        if next_start <= start:
            next_start = start + 1  # Guard against infinite loop
        start = next_start

    return chunks


class TextIngester:
    """Synchronous-ready, async-wrapped plain-text extractor.

    Parameters
    ----------
    chunk_size:
        Characters per chunk (defaults to ``settings.CHUNK_SIZE_CHARS``).
    overlap:
        Overlap characters (defaults to ``settings.CHUNK_OVERLAP_CHARS``).
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        overlap: int | None = None,
    ) -> None:
        self.chunk_size = chunk_size or settings.CHUNK_SIZE_CHARS
        self.overlap = overlap or settings.CHUNK_OVERLAP_CHARS

    async def parse(self, file_path: str | Path) -> List[IngestChunk]:
        """Parse a plain-text or Markdown file into evidence chunks.

        This coroutine does its heavy-lifting synchronously (file I/O is
        small enough that thread-off-loading is not needed for text files),
        but is declared ``async`` so it integrates uniformly with the
        async ingest router.

        Args:
            file_path: Path to the ``.txt`` or ``.md`` file.

        Returns:
            Ordered list of :class:`IngestChunk` objects, one per window.
            Returns an empty list if the file is empty or unreadable.

        Raises:
            FileNotFoundError: If *file_path* does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Text file not found: {path}")

        logger.info("Ingesting text file: %s", path)

        try:
            content = _read_file(path)
        except ValueError as exc:
            logger.error("Encoding error for '%s': %s", path, exc)
            return []

        chunks = _split_into_chunks(
            text=content,
            chunk_size=self.chunk_size,
            overlap=self.overlap,
            source_path=str(path),
        )

        logger.info("Extracted %d chunks from '%s'", len(chunks), path.name)
        return chunks


text_ingester = TextIngester()
