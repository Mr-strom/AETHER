"""API router for query planning, hybrid retrieval, synthesis, and citation validation."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException, status
try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:
    AsyncSession = Any  # type: ignore

from backend.app.dependencies import get_db
from backend.schemas.evidence import EvidenceResponse
from backend.schemas.query import QueryRequest, QueryResponse
from backend.services.retrieve.planner import query_planner_service
from backend.services.retrieve.retriever import hybrid_retriever_service
from backend.services.retrieve.synthesizer import answer_synthesizer_service
from backend.utils.validators import validate_citations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def submit_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """Process a text-only evidence RAG query.

    Flow:
    1. Validate query input (400 if empty).
    2. Plan query intent via Granite 4 Tiny H.
    3. Retrieve hybrid evidence via BGE-M3, FAISS, BM25 fallback, & BGE-Reranker.
    4. Synthesize grounded answer via Qwen2.5-3B.
    5. Post-process & validate citations.
    6. Return QueryResponse payload.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty or whitespace-only.",
        )

    start_time = time.time()
    query_text = request.query.strip()
    top_k = request.top_k or 5

    logger.info("Received query request: '%s' (top_k=%d)", query_text, top_k)

    try:
        # Step 1: Query Planning
        logger.info("Step 1/4: Planning query...")
        plan = await query_planner_service.plan_query(query_text)
        if request.filters:
            plan.filters.update(request.filters)

        # Step 2: Hybrid Retrieval
        logger.info("Step 2/4: Retrieving evidence...")
        retrieved_evidence = await hybrid_retriever_service.retrieve(
            plan=plan,
            db_session=db,
            k=top_k,
        )

        # Step 3: Answer Synthesis
        logger.info("Step 3/4: Synthesizing answer...")
        synthesis = await answer_synthesizer_service.synthesize(
            evidence=retrieved_evidence,
            query=query_text,
        )

        # Step 4: Citation Validation
        logger.info("Step 4/4: Validating citations...")
        valid_eids = {item.evidence_id for item in retrieved_evidence}
        validation = validate_citations(synthesis.answer_text, valid_eids)

        if not validation.valid:
            logger.warning("Citation validation warnings: %s", validation.errors)

        # Convert RetrievalResult items to EvidenceResponse schemas
        evidence_schemas: List[EvidenceResponse] = []
        for item in retrieved_evidence:
            # Parse numeric ID from EID-xxx string if possible
            numeric_id = 0
            try:
                numeric_id = int(item.evidence_id.replace("EID-", ""))
            except ValueError:
                numeric_id = 0

            evidence_schemas.append(
                EvidenceResponse(
                    id=numeric_id,
                    source_id=1,
                    chunk_index=0,
                    content=item.text,
                    modality="text",
                    page_number=item.page_number,
                    confidence_score=item.score,
                    metadata_json={
                        "source_name": item.source_name,
                        "reason": item.reason,
                        "evidence_id": item.evidence_id,
                    },
                    created_at=datetime.now(timezone.utc),
                )
            )

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info("Query processing complete in %d ms", elapsed_ms)

        # Map confidence string to numeric score for backward compatibility
        conf_score = 0.9 if synthesis.confidence == "high" else (0.6 if synthesis.confidence == "medium" else 0.3)

        return QueryResponse(
            query_id=1,
            query=query_text,
            answer=synthesis.answer_text,
            citations=synthesis.cited_ids,
            confidence=synthesis.confidence,
            confidence_score=conf_score,
            response_time_ms=float(elapsed_ms),
            latency_ms=elapsed_ms,
            model_used="Qwen2.5-3B-Instruct-Q4_K_M",
            evidence=evidence_schemas,
            created_at=datetime.now(timezone.utc),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Query pipeline failure: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Query engine model failure: {exc}",
        ) from exc
