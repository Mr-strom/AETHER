"""Evidence relation database model."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.database import Base


class EvidenceRelation(Base):
    """Represents a directional relationship or conflict between two evidence chunks."""

    __tablename__ = "evidence_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    source_evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evidence_chunks.id", ondelete="CASCADE"), nullable=False
    )
    target_evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evidence_chunks.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)  # supports, contradicts, elaborates, temporally_follows
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    source_evidence: Mapped["EvidenceChunk"] = relationship(
        "EvidenceChunk", foreign_keys=[source_evidence_id]
    )
    target_evidence: Mapped["EvidenceChunk"] = relationship(
        "EvidenceChunk", foreign_keys=[target_evidence_id]
    )
