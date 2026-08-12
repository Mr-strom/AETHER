"""pandas / openpyxl-based tabular data ingestion extractor.

Supported formats: ``.csv``, ``.xlsx``, ``.xls``.

Each *row* of a CSV is emitted as a single chunk in the format::

    Column1: val1 | Column2: val2 | …

For XLSX/XLS files each **sheet** is processed independently and every
row within it is treated as one evidence unit.  An empty sheet produces no
chunks.

Empty cells are represented as ``(empty)``.  Very wide rows (more than
``MAX_ROW_COLS`` columns) are truncated and a warning is logged.

Example
-------
>>> import asyncio
>>> chunks = asyncio.run(TableIngester().parse("data.csv"))
>>> print(chunks[0].text)
Name: Alice | Age: 30 | Role: Engineer
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore

from backend.services.ingest.schema import IngestChunk

logger = logging.getLogger(__name__)

# Maximum columns rendered per row to avoid excessively wide evidence strings.
MAX_ROW_COLS = 50


def _row_to_text(row: "pd.Series", columns: list[str]) -> str:  # type: ignore[type-arg]
    """Convert one DataFrame row to a pipe-delimited evidence string.

    Args:
        row: A pandas Series (one DataFrame row).
        columns: Column names to render (already truncated to MAX_ROW_COLS).

    Returns:
        String of the form ``"Col1: val1 | Col2: val2 | …"``.
    """
    parts = []
    for col in columns:
        val = row[col]
        cell = "(empty)" if pd.isna(val) else str(val).strip()
        parts.append(f"{col}: {cell}")
    return " | ".join(parts)


def _chunks_from_dataframe(
    df: "pd.DataFrame",
    source_path: str,
    start_index: int = 0,
    sheet_name: str | None = None,
) -> List[IngestChunk]:
    """Convert a DataFrame to a list of row-level chunks.

    Args:
        df: The DataFrame to process.
        source_path: Origin file path.
        start_index: Global chunk index offset.
        sheet_name: If from an XLSX sheet, the sheet name (stored in ``extra``).

    Returns:
        List of :class:`IngestChunk` objects, one per non-empty row.
    """
    if df.empty:
        logger.warning("Empty dataframe from '%s' (sheet=%s)", source_path, sheet_name)
        return []

    # Coerce column names to str
    df.columns = [str(c) for c in df.columns]

    all_cols = list(df.columns)
    if len(all_cols) > MAX_ROW_COLS:
        logger.warning(
            "Table '%s' has %d columns; truncating to %d.",
            source_path,
            len(all_cols),
            MAX_ROW_COLS,
        )
        all_cols = all_cols[:MAX_ROW_COLS]

    chunks: List[IngestChunk] = []
    for i, (_, row) in enumerate(df.iterrows()):
        text = _row_to_text(row, all_cols)
        if not text.strip() or text == " | ".join(f"{c}: (empty)" for c in all_cols):
            continue  # Skip fully-empty rows
        extra: dict = {"row_index": i}
        if sheet_name is not None:
            extra["sheet"] = sheet_name
        chunks.append(
            IngestChunk(
                source_path=source_path,
                chunk_index=start_index + len(chunks),
                text=text,
                modality="text",
                extra=extra,
            )
        )
    return chunks


class TableIngester:
    """pandas-backed CSV / XLSX tabular data extractor."""

    async def parse(self, file_path: str | Path) -> List[IngestChunk]:
        """Extract row-level evidence chunks from a CSV or Excel file.

        Args:
            file_path: Path to the ``.csv``, ``.xlsx``, or ``.xls`` file.

        Returns:
            Ordered list of :class:`IngestChunk` objects; one per data row.

        Raises:
            FileNotFoundError: If *file_path* does not exist.
            ValueError: If the file format is not supported.
            RuntimeError: If pandas/openpyxl cannot read the file.
        """
        if pd is None:
            raise RuntimeError("pandas is required: pip install pandas openpyxl")

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Table file not found: {path}")

        suffix = path.suffix.lower()
        logger.info("Ingesting table file: %s (%s)", path, suffix)

        try:
            if suffix == ".csv":
                return await self._parse_csv(path)
            elif suffix in {".xlsx", ".xls"}:
                return await self._parse_excel(path)
            else:
                raise ValueError(
                    f"Unsupported table format '{suffix}'. "
                    "Expected .csv, .xlsx, or .xls."
                )
        except (ValueError, FileNotFoundError):
            raise
        except Exception as exc:
            logger.error("Failed to parse table '%s': %s", path, exc)
            raise RuntimeError(f"Cannot read table '{path}': {exc}") from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _parse_csv(self, path: Path) -> List[IngestChunk]:
        """Read a CSV file and emit one chunk per row."""
        # Try UTF-8, fall back to Latin-1 to handle varied exports.
        try:
            df = pd.read_csv(path, dtype=str, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(path, dtype=str, encoding="latin-1")
        chunks = _chunks_from_dataframe(df, str(path))
        logger.info("CSV '%s': %d row-chunks", path.name, len(chunks))
        return chunks

    async def _parse_excel(self, path: Path) -> List[IngestChunk]:
        """Read an XLSX/XLS workbook and emit one chunk per row per sheet."""
        sheets: dict[str, "pd.DataFrame"] = pd.read_excel(
            path, sheet_name=None, dtype=str
        )
        all_chunks: List[IngestChunk] = []
        global_index = 0
        for sheet_name, df in sheets.items():
            sheet_chunks = _chunks_from_dataframe(
                df, str(path), start_index=global_index, sheet_name=sheet_name
            )
            all_chunks.extend(sheet_chunks)
            global_index += len(sheet_chunks)
            logger.info(
                "XLSX '%s' sheet '%s': %d row-chunks",
                path.name,
                sheet_name,
                len(sheet_chunks),
            )
        return all_chunks


table_ingester = TableIngester()
