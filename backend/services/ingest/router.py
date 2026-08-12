"""Ingestion router: dispatch files to the correct modality extractor.

The router uses Python's ``mimetypes`` standard library for MIME detection
with an extension-based fallback table so that no external C library
(``python-magic`` / ``libmagic``) is required at runtime — keeping the
install lean on Windows where ``libmagic`` needs separate DLLs.

Routing table
-------------
==================  =======================================================
Extension           Extractor
==================  =======================================================
.txt, .md, .rst     :class:`~backend.services.ingest.text.TextIngester`
.pdf                :class:`~backend.services.ingest.pdf.PDFIngester`
.docx, .doc         :class:`~backend.services.ingest.docx.DocxIngester`
.csv, .xlsx, .xls   :class:`~backend.services.ingest.table.TableIngester`
anything else       :exc:`UnsupportedFileTypeError`
==================  =======================================================

Example
-------
>>> import asyncio
>>> from backend.services.ingest.router import ingest_router
>>> chunks = asyncio.run(ingest_router.process_file("notes.txt"))
>>> len(chunks) > 0
True
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Dict, List, Type

from backend.services.ingest.schema import IngestChunk
from backend.services.ingest.text import TextIngester
from backend.services.ingest.pdf import PDFIngester
from backend.services.ingest.docx import DocxIngester
from backend.services.ingest.table import TableIngester

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extractor lookup keyed by lowercase file extension
# ---------------------------------------------------------------------------

_EXT_MAP: Dict[str, str] = {
    # Plain text
    ".txt": "text",
    ".md": "text",
    ".rst": "text",
    ".log": "text",
    # PDF
    ".pdf": "pdf",
    # Word documents
    ".docx": "docx",
    ".doc": "docx",
    # Tabular
    ".csv": "table",
    ".xlsx": "table",
    ".xls": "table",
}


class UnsupportedFileTypeError(ValueError):
    """Raised when no extractor is registered for the given file type."""


class IngestRouter:
    """Routes a file to the correct ingestion extractor and returns chunks.

    Extractors are instantiated once at class construction and reused for
    every call, avoiding repeated model/library initialisation overhead.
    """

    def __init__(self) -> None:
        self._text = TextIngester()
        self._pdf = PDFIngester()
        self._docx = DocxIngester()
        self._table = TableIngester()

    def _detect_extractor_key(self, path: Path) -> str:
        """Determine the extractor key for *path*.

        First consults :data:`_EXT_MAP` (extension-based).  If the
        extension is not in the table the MIME type is inspected as a
        last resort.

        Args:
            path: The file to classify.

        Returns:
            One of ``"text"``, ``"pdf"``, ``"docx"``, ``"table"``.

        Raises:
            UnsupportedFileTypeError: If no extractor is found.
        """
        ext = path.suffix.lower()
        if ext in _EXT_MAP:
            return _EXT_MAP[ext]

        # MIME fallback
        mime, _ = mimetypes.guess_type(str(path))
        if mime:
            if mime.startswith("text/"):
                return "text"
            if mime == "application/pdf":
                return "pdf"
            if "spreadsheet" in mime or "excel" in mime:
                return "table"
            if "wordprocessingml" in mime or "msword" in mime:
                return "docx"

        raise UnsupportedFileTypeError(
            f"No extractor registered for '{path.suffix}' (MIME: {mime})."
        )

    async def process_file(self, file_path: str | Path) -> List[IngestChunk]:
        """Route *file_path* to the appropriate extractor and return chunks.

        Args:
            file_path: Path to the file to ingest. Must exist on disk.

        Returns:
            List of :class:`IngestChunk` objects produced by the extractor.
            Returns an empty list if the extractor produces no output.

        Raises:
            FileNotFoundError: If the file does not exist.
            UnsupportedFileTypeError: If the file type is not supported.
            RuntimeError: If the underlying extractor raises an unrecoverable
                error (corrupt file, bad encoding, etc.).
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Ingest target not found: {path}")

        try:
            key = self._detect_extractor_key(path)
        except UnsupportedFileTypeError:
            logger.warning("Unsupported file type: %s", path.suffix)
            raise

        logger.info("Routing '%s' → extractor='%s'", path.name, key)

        try:
            if key == "text":
                return await self._text.parse(path)
            elif key == "pdf":
                return await self._pdf.parse(path)
            elif key == "docx":
                return await self._docx.parse(path)
            elif key == "table":
                return await self._table.parse(path)
        except (FileNotFoundError, UnsupportedFileTypeError):
            raise
        except Exception as exc:
            logger.error(
                "Extractor '%s' failed for '%s': %s",
                key,
                path.name,
                exc,
                exc_info=True,
            )
            raise RuntimeError(
                f"Ingestion failed for '{path.name}': {exc}"
            ) from exc

        # Should be unreachable but satisfies the type-checker.
        return []  # pragma: no cover


ingest_router = IngestRouter()
