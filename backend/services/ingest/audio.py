"""whisper.cpp ASR audio ingestion pipeline stub."""

from pathlib import Path
from typing import Any


class AudioIngester:
    """Transcribes audio files into timestamped text evidence chunks using whisper.cpp."""

    async def parse(self, file_path: str | Path) -> list[dict[str, Any]]:
        """Parse audio file into transcript evidence chunks."""
        # Stub implementation
        return []


audio_ingester = AudioIngester()
