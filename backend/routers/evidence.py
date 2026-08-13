"""API endpoints for evidence chunks and conflict graph exploration."""

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

try:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:
    select = None  # type: ignore
    AsyncSession = Any  # type: ignore

from backend.app.dependencies import get_db
from backend.models.evidence import EvidenceChunk
from backend.models.source import Source
from backend.schemas.evidence import EvidenceResponse, ConflictGraphResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    evidence_id: int,
    db: AsyncSession = Depends(get_db),
) -> EvidenceResponse:
    """Retrieve details for a single evidence chunk."""
    stmt = (
        select(EvidenceChunk)
        .where(EvidenceChunk.id == evidence_id)
    )
    chunk = (await db.execute(stmt)).scalar_one_or_none()

    if not chunk:
        raise HTTPException(status_code=404, detail=f"Evidence {evidence_id} not found")

    return EvidenceResponse(
        id=chunk.id,
        source_id=chunk.source_id,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        modality=chunk.modality,
        page_number=chunk.page_number,
        timestamp_start=chunk.timestamp_start,
        timestamp_end=chunk.timestamp_end,
        bbox_json=chunk.bbox_json,
        embedding_id=chunk.embedding_id,
        confidence_score=chunk.confidence_score,
        metadata_json=chunk.metadata_json,
        created_at=chunk.created_at,
    )


@router.get("", response_model=List[EvidenceResponse])
async def list_evidence(
    source_id: Optional[int] = Query(default=None, description="Filter by source ID"),
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> List[EvidenceResponse]:
    """List evidence chunks, optionally filtered by source_id."""
    stmt = select(EvidenceChunk).offset(skip).limit(limit).order_by(EvidenceChunk.id)

    if source_id is not None:
        stmt = stmt.where(EvidenceChunk.source_id == source_id)

    rows = (await db.execute(stmt)).scalars().all()

    return [
        EvidenceResponse(
            id=chunk.id,
            source_id=chunk.source_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            modality=chunk.modality,
            page_number=chunk.page_number,
            timestamp_start=chunk.timestamp_start,
            timestamp_end=chunk.timestamp_end,
            bbox_json=chunk.bbox_json,
            embedding_id=chunk.embedding_id,
            confidence_score=chunk.confidence_score,
            metadata_json=chunk.metadata_json,
            created_at=chunk.created_at,
        )
        for chunk in rows
    ]


@router.get("/graph/conflicts", response_model=ConflictGraphResponse)
async def get_conflict_graph(
    db: AsyncSession = Depends(get_db),
) -> ConflictGraphResponse:
    """Retrieve graph visualization network data for evidence relationships and conflicts."""
    # Stub response — conflict graph requires full evidence loaded
    return ConflictGraphResponse(nodes=[], edges=[])
