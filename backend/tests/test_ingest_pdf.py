"""Unit tests for backend/services/ingest/pdf.py"""

import asyncio
from pathlib import Path
from typing import List
import pytest

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

from backend.services.ingest.schema import IngestChunk

pytestmark = pytest.mark.skipif(
    not FITZ_AVAILABLE, reason="PyMuPDF (fitz) not installed"
)


def _make_pdf(path: Path, pages: List[str]) -> None:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((50, 100), text, fontsize=12)
    doc.save(str(path))
    doc.close()


def test_pdf_single_page(tmp_path: Path) -> None:
    from backend.services.ingest.pdf import PDFIngester

    pdf_path = tmp_path / "single.pdf"
    _make_pdf(pdf_path, ["Hello AETHER evidence system."])

    ingester = PDFIngester()
    chunks = asyncio.run(ingester.parse(pdf_path))

    assert len(chunks) >= 1
    assert all(isinstance(c, IngestChunk) for c in chunks)
    assert chunks[0].page_number == 1
    assert chunks[0].modality == "text"
    assert "AETHER" in chunks[0].text or "Hello" in chunks[0].text


def test_pdf_multiple_pages(tmp_path: Path) -> None:
    from backend.services.ingest.pdf import PDFIngester

    pdf_path = tmp_path / "multi.pdf"
    _make_pdf(pdf_path, [f"Page {i} content." for i in range(1, 6)])

    ingester = PDFIngester()
    chunks = asyncio.run(ingester.parse(pdf_path))

    page_numbers = [c.page_number for c in chunks]
    assert 1 in page_numbers
    assert 5 in page_numbers
    assert len(chunks) == 5


def test_pdf_chunk_indices_sequential(tmp_path: Path) -> None:
    from backend.services.ingest.pdf import PDFIngester

    pdf_path = tmp_path / "seq.pdf"
    _make_pdf(pdf_path, ["Content A", "Content B", "Content C"])

    ingester = PDFIngester()
    chunks = asyncio.run(ingester.parse(pdf_path))

    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_pdf_long_page_splits(tmp_path: Path) -> None:
    from backend.services.ingest.pdf import PDFIngester

    pdf_path = tmp_path / "long.pdf"
    long_text = "Evidence word. " * 300
    _make_pdf(pdf_path, [long_text])

    ingester = PDFIngester(chunk_size=512, overlap=50)
    chunks = asyncio.run(ingester.parse(pdf_path))

    assert len(chunks) > 1
    assert all(c.page_number == 1 for c in chunks)


def test_pdf_not_found() -> None:
    from backend.services.ingest.pdf import PDFIngester

    ingester = PDFIngester()
    with pytest.raises(FileNotFoundError):
        asyncio.run(ingester.parse("/no/such/file.pdf"))


def test_pdf_empty_page_skipped(tmp_path: Path) -> None:
    from backend.services.ingest.pdf import PDFIngester

    pdf_path = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    ingester = PDFIngester()
    chunks = asyncio.run(ingester.parse(pdf_path))
    assert chunks == []


def test_pdf_source_path_set(tmp_path: Path) -> None:
    from backend.services.ingest.pdf import PDFIngester

    pdf_path = tmp_path / "sp.pdf"
    _make_pdf(pdf_path, ["Check source path."])

    ingester = PDFIngester()
    chunks = asyncio.run(ingester.parse(pdf_path))

    for c in chunks:
        assert c.source_path == str(pdf_path)
