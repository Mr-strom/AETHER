"""Visual embedding service stub for images and PDF page renders."""

from pathlib import Path


class VisualEmbeddingService:
    """Generates visual embeddings for page crops and keyframes."""

    def embed_image(self, image_path: str | Path) -> list[float]:
        """Compute visual embedding vector for image."""
        # Stub implementation
        return [0.0] * 512


visual_embedding_service = VisualEmbeddingService()
