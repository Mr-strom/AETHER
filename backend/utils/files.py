"""File manipulation and path resolution utility stub."""

import os
from pathlib import Path


def ensure_directory(directory_path: str | Path) -> Path:
    """Ensure directory exists and return Path object."""
    path = Path(directory_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_extension(filename: str) -> str:
    """Get lowercase file extension without leading dot."""
    return Path(filename).suffix.lstrip(".").lower()
