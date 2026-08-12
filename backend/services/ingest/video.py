"""ffmpeg-python keyframe extraction & video ingestion pipeline stub."""

from pathlib import Path
from typing import Any


class VideoIngester:
    """Extracts keyframes and audio tracks from video files for multimodal evidence indexing."""

    async def parse(self, file_path: str | Path) -> list[dict[str, Any]]:
        """Parse video file into keyframe and transcript evidence chunks."""
        # Stub implementation
        return []


video_ingester = VideoIngester()
