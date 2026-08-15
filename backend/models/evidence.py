"""Evidence chunk database model."""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.database import Base

if TYPE_CHECKING:
    from backend.models.source import Source


class EvidenceChunk(Base):
    """Represents an extracted unit of evidence (text, page snippet, transcript chunk, table, crop)."""

    __tablename__ = "evidence_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    modality: Mapped[str] = mapped_column(String(50), nullable=False)  # text, image, audio, video, table
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timestamp_start: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp_end: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    embedding_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    index_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Contextualized text for embedding + BM25
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    source: Mapped["Source"] = relationship("Source", back_populates="evidence_chunks")
