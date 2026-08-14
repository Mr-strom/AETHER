"""Chat message model for persistent conversation history."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text, Float, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.database import Base


class ChatMessage(Base):
    """Represents a single message in a conversation (user or aether)."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" or "aether"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    evidence_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
