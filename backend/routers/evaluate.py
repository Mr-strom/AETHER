"""API endpoints for evaluating evidence RAG retrieval & synthesis."""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:
    AsyncSession = Any  # type: ignore
from backend.app.dependencies import get_db
from backend.schemas.query import EvaluationRequest, EvaluationResponse

router = APIRouter(prefix="/api/evaluate", tags=["evaluate"])


@router.post("", response_model=EvaluationResponse)
async def run_evaluation(
    request: EvaluationRequest,
    db: AsyncSession = Depends(get_db),
) -> EvaluationResponse:
    """Trigger an offline precision/recall/hallucination evaluation benchmark."""
    # Stub response
    return EvaluationResponse(
        evaluated_queries_count=0,
        overall_score=0.0,
        metrics=[],
    )
