"""pytesseract OCR & visual evidence ingestion pipeline stub."""

from pathlib import Path
from typing import Any


class ImageIngester:
    """Extracts text via OCR and layout features from standalone images."""

    async def parse(self, file_path: str | Path) -> list[dict[str, Any]]:
        """Parse image file into visual OCR evidence chunks."""
        # Stub implementation
        return []


image_ingester = ImageIngester()
