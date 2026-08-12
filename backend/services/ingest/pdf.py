"""PyMuPDF-based PDF ingestion extractor.

Extracts text from every page of a PDF document.  Long pages are split
using the same character-window strategy as :mod:`backend.services.ingest.text`.

Heading heuristic
-----------------
PyMuPDF exposes per-span font size via ``page.get_text("dict")``.
Any span whose font size exceeds ``body_size * HEADING_RATIO`` **or** whose
flags field has the bold bit (2) set is prefixed with ``## `` so downstream
chunking and retrieval can recognise headings.

Bounding-box support
--------------------
When a chunk corresponds to a single PyMuPDF block the ``bbox`` field is
populated with ``{x0, y0, x1, y1}`` coordinates in PDF points.

Example
-------
>>> import asyncio
>>> chunks = asyncio.run(PDFIngester().parse("report.pdf"))
>>> print(chunks[0].page_number, chunks[0].text[:60])
1 ## Introduction  This paper examines the evidence for ...
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None  # type: ignore

from backend.app.config import settings
from backend.services.ingest.schema import IngestChunk
from backend.services.ingest.text import _split_into_chunks

logger = logging.getLogger(__name__)

# Ratio above which a span is treated as a heading (relative to page median).
HEADING_RATIO = 1.15
# PyMuPDF bold flag bit.
BOLD_FLAG = 2


def _median_font_size(page: "fitz.Page") -> float:
    """Estimate the modal body font size for *page*.

    Collects every span's size from the structured text dict and returns
    the median, which is a robust estimate of the body-text size.

    Args:
        page: PyMuPDF page object.

    Returns:
        Median font size or 0 if no spans found.
    """
    sizes: List[float] = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                sizes.append(span.get("size", 0))
    if not sizes:
        return 0
    sizes.sort()
    return sizes[len(sizes) // 2]


def _extract_page_text(page: "fitz.Page") -> tuple[str, Optional[dict[str, float]]]:
    """Extract text from *page* applying the heading heuristic.

    Args:
        page: PyMuPDF page object.

    Returns:
        Tuple of (full page text, combined bounding box of all blocks or None).
    """
    body_size = _median_font_size(page)
    lines: List[str] = []
    bboxes: List[tuple[float, float, float, float]] = []

    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:  # Skip image blocks (type 1)
            continue

        block_lines: List[str] = []
        block_bbox = block.get("bbox")
        if block_bbox:
            bboxes.append(tuple(block_bbox))  # type: ignore[arg-type]

        for line in block.get("lines", []):
            span_parts: List[str] = []
            for span in line.get("spans", []):
                span_text = span.get("text", "").strip()
                if not span_text:
                    continue
                size = span.get("size", 0)
                flags = span.get("flags", 0)
                is_bold = bool(flags & BOLD_FLAG)
                is_large = body_size > 0 and size >= body_size * HEADING_RATIO
                if is_large or is_bold:
                    span_parts.append(f"## {span_text}")
                else:
                    span_parts.append(span_text)
            if span_parts:
                block_lines.append(" ".join(span_parts))

        if block_lines:
            lines.append("\n".join(block_lines))

    combined_text = "\n\n".join(lines).strip()

    merged_bbox: Optional[dict[str, float]] = None
    if bboxes:
        merged_bbox = {
            "x0": min(b[0] for b in bboxes),
            "y0": min(b[1] for b in bboxes),
            "x1": max(b[2] for b in bboxes),
            "y1": max(b[3] for b in bboxes),
        }

    return combined_text, merged_bbox


class PDFIngester:
    """PyMuPDF-backed PDF extractor.

    Parameters
    ----------
    chunk_size:
        Characters per chunk when splitting a long page.
    overlap:
        Overlap characters between consecutive chunks.
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        overlap: int | None = None,
    ) -> None:
        self.chunk_size = chunk_size or settings.CHUNK_SIZE_CHARS
        self.overlap = overlap or settings.CHUNK_OVERLAP_CHARS

    async def parse(self, file_path: str | Path) -> List[IngestChunk]:
        """Extract text chunks from a PDF file.

        Each physical page becomes at least one chunk.  Pages whose text
        exceeds ``chunk_size`` are further split with ``overlap`` overlap.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Ordered list of :class:`IngestChunk` objects with
            ``page_number`` and optional ``bbox`` populated.

        Raises:
            FileNotFoundError: If *file_path* does not exist.
            RuntimeError: If PyMuPDF cannot open the file.
        """
        if fitz is None:
            raise RuntimeError("PyMuPDF is required: pip install PyMuPDF")

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")

        logger.info("Ingesting PDF: %s", path)

        try:
            doc: fitz.Document = fitz.open(str(path))
        except Exception as exc:
            logger.error("PyMuPDF failed to open '%s': %s", path, exc)
            raise RuntimeError(f"Cannot open PDF '{path}': {exc}") from exc

        chunks: List[IngestChunk] = []
        global_index = 0

        try:
            for page_num in range(len(doc)):
                page: fitz.Page = doc[page_num]
                page_text, bbox = _extract_page_text(page)

                if not page_text:
                    logger.debug("Page %d of '%s' has no text; skipping.", page_num + 1, path.name)
                    continue

                if len(page_text) <= self.chunk_size:
                    chunks.append(
                        IngestChunk(
                            source_path=str(path),
                            chunk_index=global_index,
                            text=page_text,
                            modality="text",
                            page_number=page_num + 1,
                            bbox=bbox,
                        )
                    )
                    global_index += 1
                else:
                    # Long page: re-chunk while preserving page_number.
                    sub_chunks = _split_into_chunks(
                        text=page_text,
                        chunk_size=self.chunk_size,
                        overlap=self.overlap,
                        source_path=str(path),
                    )
                    for sc in sub_chunks:
                        sc.chunk_index = global_index
                        sc.page_number = page_num + 1
                        # Only the first sub-chunk gets the page bbox.
                        if global_index == chunks[-1].chunk_index + 1 if chunks else True:
                            sc.bbox = bbox
                        chunks.append(sc)
                        global_index += 1
        finally:
            doc.close()

        logger.info("Extracted %d chunks from PDF '%s'", len(chunks), path.name)
        return chunks


pdf_ingester = PDFIngester()
