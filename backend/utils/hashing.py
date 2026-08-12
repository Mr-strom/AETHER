"""File and content hashing utility stub."""

import hashlib
from pathlib import Path


def compute_file_hash(file_path: str | Path) -> str:
    """Compute SHA-256 hash of a file for deduplication."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_string_hash(text: str) -> str:
    """Compute SHA-256 hash of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
