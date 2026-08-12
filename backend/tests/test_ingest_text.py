"""Unit tests for backend/services/ingest/text.py"""

import asyncio
from pathlib import Path
import pytest

from backend.services.ingest.text import TextIngester, _read_file, _split_into_chunks
from backend.services.ingest.schema import IngestChunk


# ---------------------------------------------------------------------------
# _read_file
# ---------------------------------------------------------------------------


def test_read_file_utf8(tmp_path: Path) -> None:
    f = tmp_path / "utf8.txt"
    f.write_text("Hello AETHER", encoding="utf-8")
    assert _read_file(f) == "Hello AETHER"


def test_read_file_latin1_fallback(tmp_path: Path) -> None:
    f = tmp_path / "latin1.txt"
    f.write_bytes(b"caf\xe9 evidence")
    content = _read_file(f)
    assert "caf" in content


# ---------------------------------------------------------------------------
# _split_into_chunks
# ---------------------------------------------------------------------------


def test_split_empty_string() -> None:
    chunks = _split_into_chunks("", 2048, 50, "test.txt")
    assert chunks == []


def test_split_whitespace_only() -> None:
    chunks = _split_into_chunks("   \n\t  ", 2048, 50, "test.txt")
    assert chunks == []


def test_split_short_text_single_chunk() -> None:
    text = "Short text that fits in one chunk."
    chunks = _split_into_chunks(text, 2048, 50, "file.txt")
    assert len(chunks) == 1
    assert chunks[0].text == text.strip()
    assert chunks[0].chunk_index == 0
    assert chunks[0].source_path == "file.txt"
    assert chunks[0].modality == "text"


def test_split_long_text_multiple_chunks() -> None:
    text = "A" * 5000
    chunks = _split_into_chunks(text, 2048, 50, "large.txt")
    assert len(chunks) > 1
    for i, c in enumerate(chunks):
        assert c.chunk_index == i


def test_split_overlap() -> None:
    text = "x" * 200
    chunks = _split_into_chunks(text, 100, 20, "overlap.txt")
    if len(chunks) > 1:
        assert len(chunks) >= 2


def test_split_char_count_populated() -> None:
    text = "Hello world"
    chunks = _split_into_chunks(text, 2048, 50, "f.txt")
    assert chunks[0].char_count == len("Hello world")


# ---------------------------------------------------------------------------
# TextIngester
# ---------------------------------------------------------------------------


def test_text_ingester_basic(tmp_path: Path) -> None:
    f = tmp_path / "doc.txt"
    f.write_text("This is a test document for AETHER ingestion.", encoding="utf-8")
    ingester = TextIngester(chunk_size=2048, overlap=50)
    chunks = asyncio.run(ingester.parse(f))
    assert len(chunks) >= 1
    assert all(isinstance(c, IngestChunk) for c in chunks)
    assert chunks[0].modality == "text"


def test_text_ingester_markdown(tmp_path: Path) -> None:
    f = tmp_path / "readme.md"
    f.write_text("# Title\n\nParagraph one.\n\n## Section\nParagraph two.", encoding="utf-8")
    ingester = TextIngester()
    chunks = asyncio.run(ingester.parse(f))
    combined = " ".join(c.text for c in chunks)
    assert "Title" in combined
    assert "Section" in combined


def test_text_ingester_empty_file(tmp_path: Path) -> None:
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    ingester = TextIngester()
    chunks = asyncio.run(ingester.parse(f))
    assert chunks == []


def test_text_ingester_file_not_found() -> None:
    ingester = TextIngester()
    with pytest.raises(FileNotFoundError):
        asyncio.run(ingester.parse("/nonexistent/path/file.txt"))


def test_text_ingester_large_file(tmp_path: Path) -> None:
    content = ("Evidence sentence number {}. " * 300).format(*range(300))
    f = tmp_path / "large.txt"
    f.write_text(content, encoding="utf-8")
    ingester = TextIngester(chunk_size=512, overlap=50)
    chunks = asyncio.run(ingester.parse(f))
    assert len(chunks) > 3
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_text_ingester_chunk_size_respected(tmp_path: Path) -> None:
    f = tmp_path / "bounded.txt"
    f.write_text("X" * 10_000, encoding="utf-8")
    chunk_size = 500
    overlap = 50
    ingester = TextIngester(chunk_size=chunk_size, overlap=overlap)
    chunks = asyncio.run(ingester.parse(f))
    for c in chunks:
        assert c.char_count <= chunk_size + overlap + 5
