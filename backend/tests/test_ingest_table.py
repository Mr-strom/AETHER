"""Unit tests for backend/services/ingest/table.py"""

import asyncio
import csv
from pathlib import Path
import pytest

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from backend.services.ingest.schema import IngestChunk

pytestmark = pytest.mark.skipif(
    not PANDAS_AVAILABLE, reason="pandas not installed"
)


def _write_csv(path: Path, rows: list[list[str]], header: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def test_csv_basic(tmp_path: Path) -> None:
    from backend.services.ingest.table import TableIngester

    path = tmp_path / "data.csv"
    _write_csv(path, [["Alice", "30"], ["Bob", "25"]], ["Name", "Age"])

    ingester = TableIngester()
    chunks = asyncio.run(ingester.parse(path))

    assert len(chunks) == 2
    assert all(isinstance(c, IngestChunk) for c in chunks)
    assert "Name: Alice" in chunks[0].text
    assert "Age: 30" in chunks[0].text
    assert "Name: Bob" in chunks[1].text


def test_csv_pipe_delimiter(tmp_path: Path) -> None:
    from backend.services.ingest.table import TableIngester

    path = tmp_path / "columns.csv"
    _write_csv(
        path,
        [["Evidence A", "High", "2024"]],
        ["Title", "Priority", "Year"],
    )

    ingester = TableIngester()
    chunks = asyncio.run(ingester.parse(path))

    assert len(chunks) == 1
    text = chunks[0].text
    assert "Title: Evidence A" in text
    assert "Priority: High" in text
    assert "Year: 2024" in text
    assert "|" in text


def test_csv_empty_rows_skipped(tmp_path: Path) -> None:
    from backend.services.ingest.table import TableIngester

    path = tmp_path / "sparse.csv"
    _write_csv(path, [["Alice", "30"], ["", ""], ["Bob", "25"]], ["Name", "Age"])

    ingester = TableIngester()
    chunks = asyncio.run(ingester.parse(path))

    texts = [c.text for c in chunks]
    assert not any("(empty)" in t and "Name: (empty)" in t for t in texts)


def test_csv_not_found() -> None:
    from backend.services.ingest.table import TableIngester

    ingester = TableIngester()
    with pytest.raises(FileNotFoundError):
        asyncio.run(ingester.parse("/no/such/file.csv"))


def test_csv_chunk_indices_sequential(tmp_path: Path) -> None:
    from backend.services.ingest.table import TableIngester

    path = tmp_path / "seq.csv"
    _write_csv(path, [[str(i), str(i * 2)] for i in range(10)], ["A", "B"])

    ingester = TableIngester()
    chunks = asyncio.run(ingester.parse(path))

    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_csv_source_path_set(tmp_path: Path) -> None:
    from backend.services.ingest.table import TableIngester

    path = tmp_path / "sp.csv"
    _write_csv(path, [["x", "y"]], ["Col1", "Col2"])

    ingester = TableIngester()
    chunks = asyncio.run(ingester.parse(path))

    for c in chunks:
        assert c.source_path == str(path)


def test_csv_extra_metadata(tmp_path: Path) -> None:
    from backend.services.ingest.table import TableIngester

    path = tmp_path / "meta.csv"
    _write_csv(path, [["val"]], ["Header"])

    ingester = TableIngester()
    chunks = asyncio.run(ingester.parse(path))

    assert "row_index" in chunks[0].extra


def _write_xlsx(path: Path, sheets: dict[str, list[list[str]]]) -> None:
    try:
        import openpyxl
    except ImportError:
        pytest.skip("openpyxl not installed")

    wb = openpyxl.Workbook()
    first = True
    for sheet_name, rows in sheets.items():
        if first:
            ws = wb.active
            ws.title = sheet_name
            first = False
        else:
            ws = wb.create_sheet(sheet_name)
        for row in rows:
            ws.append(row)
    wb.save(str(path))


def test_xlsx_single_sheet(tmp_path: Path) -> None:
    from backend.services.ingest.table import TableIngester

    path = tmp_path / "single.xlsx"
    _write_xlsx(path, {"Sheet1": [["Name", "Score"], ["Alice", "95"], ["Bob", "80"]]})

    ingester = TableIngester()
    chunks = asyncio.run(ingester.parse(path))

    assert len(chunks) == 2
    assert "Name: Alice" in chunks[0].text


def test_xlsx_multiple_sheets(tmp_path: Path) -> None:
    from backend.services.ingest.table import TableIngester

    path = tmp_path / "multi.xlsx"
    _write_xlsx(
        path,
        {
            "Sheet1": [["A", "B"], ["1", "2"]],
            "Sheet2": [["X", "Y"], ["a", "b"]],
        },
    )

    ingester = TableIngester()
    chunks = asyncio.run(ingester.parse(path))

    sheet_names = [c.extra.get("sheet") for c in chunks]
    assert "Sheet1" in sheet_names
    assert "Sheet2" in sheet_names


def test_unsupported_extension(tmp_path: Path) -> None:
    from backend.services.ingest.table import TableIngester

    path = tmp_path / "file.ods"
    path.write_text("irrelevant")

    ingester = TableIngester()
    with pytest.raises(ValueError, match="Unsupported table format"):
        asyncio.run(ingester.parse(path))
