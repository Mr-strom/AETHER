"""API endpoints for conversation history management."""

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

try:
    from sqlalchemy import select, func, update
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import selectinload
except ImportError:
    select = None  # type: ignore
    AsyncSession = Any  # type: ignore

from backend.app.dependencies import get_db
from backend.models.conversation import Conversation
from backend.models.message import ChatMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ---------- Schemas ----------

class MessageSchema(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    citations_json: Optional[list] = None
    confidence: Optional[str] = None
    latency_ms: Optional[int] = None
    evidence_json: Optional[list] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationSchema(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = 0

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    total: int
    conversations: List[ConversationSchema]


class CreateMessageRequest(BaseModel):
    role: str
    content: str
    citations_json: Optional[list] = None
    confidence: Optional[str] = None
    latency_ms: Optional[int] = None
    evidence_json: Optional[list] = None


# ---------- Endpoints ----------

@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all conversations, most recent first."""
    total = (await db.execute(select(func.count(Conversation.id)))).scalar() or 0

    stmt = (
        select(Conversation)
        .order_by(Conversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()

    conversations = []
    for c in rows:
        msg_count = (await db.execute(
            select(func.count(ChatMessage.id)).where(ChatMessage.conversation_id == c.id)
        )).scalar() or 0
        conversations.append(ConversationSchema(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=msg_count,
        ))

    return ConversationListResponse(total=total, conversations=conversations)


@router.post("", response_model=ConversationSchema, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    db: AsyncSession = Depends(get_db),
):
    """Create a new empty conversation."""
    conv = Conversation(title="New Chat")
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationSchema(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0,
    )


@router.get("/{conversation_id}/messages", response_model=List[MessageSchema])
async def get_messages(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all messages in a conversation."""
    conv = (await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at)
    )
    messages = (await db.execute(stmt)).scalars().all()
    return [MessageSchema.model_validate(m) for m in messages]


@router.post("/{conversation_id}/messages", response_model=MessageSchema, status_code=status.HTTP_201_CREATED)
async def add_message(
    conversation_id: int,
    request: CreateMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add a message to a conversation."""
    conv = (await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg = ChatMessage(
        conversation_id=conversation_id,
        role=request.role,
        content=request.content,
        citations_json=request.citations_json,
        confidence=request.confidence,
        latency_ms=request.latency_ms,
        evidence_json=request.evidence_json,
    )
    db.add(msg)

    # Update conversation title from first user message
    msg_count = (await db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.conversation_id == conversation_id)
    )).scalar() or 0

    if msg_count == 0 and request.role == "user":
        title = request.content[:50] + ("..." if len(request.content) > 50 else "")
        conv.title = title

    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)

    return MessageSchema.model_validate(msg)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    conv = (await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conv)
    await db.commit()
    logger.info("Deleted conversation %d", conversation_id)
