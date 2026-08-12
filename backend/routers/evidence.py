"""API endpoints for evidence chunks and conflict graph exploration."""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:
    AsyncSession = Any  # type: ignore
from backend.app.dependencies import get_db
from backend.schemas.evidence import EvidenceResponse, ConflictGraphResponse

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    evidence_id: int,
    db: AsyncSession = Depends(get_db),
) -> EvidenceResponse:
    """Retrieve details for a single evidence chunk."""
    raise HTTPException(status_code=404, detail=f"Evidence {evidence_id} not found")


@router.get("/graph/conflicts", response_model=ConflictGraphResponse)
async def get_conflict_graph(
    db: AsyncSession = Depends(get_db),
) -> ConflictGraphResponse:
    """Retrieve graph visualization network data for evidence relationships and conflicts."""
    # Stub response
    return ConflictGraphResponse(nodes=[], edges=[])
