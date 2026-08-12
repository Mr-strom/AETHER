"""Unit tests for backend/services/ingest/router.py"""

import asyncio
from pathlib import Path
import pytest

from backend.services.ingest.router import IngestRouter, UnsupportedFileTypeError
from backend.services.ingest.schema import IngestChunk


def _txt(tmp_path: Path, content: str = "Hello evidence router.") -> Path:
    p = tmp_path / "doc.txt"
    p.write_text(content, encoding="utf-8")
    return p


def _md(tmp_path: Path) -> Path:
    p = tmp_path / "notes.md"
    p.write_text("# Heading\nParagraph.", encoding="utf-8")
    return p


def _csv(tmp_path: Path) -> Path:
    p = tmp_path / "data.csv"
    p.write_text("Col1,Col2\nA,B\nC,D", encoding="utf-8")
    return p


def test_router_routes_txt(tmp_path: Path) -> None:
    router = IngestRouter()
    chunks = asyncio.run(router.process_file(_txt(tmp_path)))
    assert len(chunks) >= 1
    assert all(isinstance(c, IngestChunk) for c in chunks)


def test_router_routes_md(tmp_path: Path) -> None:
    router = IngestRouter()
    chunks = asyncio.run(router.process_file(_md(tmp_path)))
    assert len(chunks) >= 1


def test_router_routes_csv(tmp_path: Path) -> None:
    router = IngestRouter()
    chunks = asyncio.run(router.process_file(_csv(tmp_path)))
    assert len(chunks) == 2


def test_router_file_not_found() -> None:
    router = IngestRouter()
    with pytest.raises(FileNotFoundError):
        asyncio.run(router.process_file("/no/such/file.txt"))


def test_router_unsupported_extension(tmp_path: Path) -> None:
    unknown = tmp_path / "file.xyz"
    unknown.write_text("content")
    router = IngestRouter()
    with pytest.raises(UnsupportedFileTypeError):
        asyncio.run(router.process_file(unknown))


def test_router_pdf_extension(tmp_path: Path) -> None:
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not installed")

    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    router = IngestRouter()
    chunks = asyncio.run(router.process_file(pdf_path))
    assert isinstance(chunks, list)


def test_router_docx_extension(tmp_path: Path) -> None:
    try:
        from docx import Document
    except ImportError:
        pytest.skip("python-docx not installed")

    docx_path = tmp_path / "test.docx"
    doc = Document()
    doc.add_paragraph("Router DOCX test.")
    doc.save(str(docx_path))

    router = IngestRouter()
    chunks = asyncio.run(router.process_file(docx_path))
    assert len(chunks) >= 1


def test_router_rst_extension(tmp_path: Path) -> None:
    rst = tmp_path / "doc.rst"
    rst.write_text("Title\n=====\nSome RST content.", encoding="utf-8")
    router = IngestRouter()
    chunks = asyncio.run(router.process_file(rst))
    assert len(chunks) >= 1
