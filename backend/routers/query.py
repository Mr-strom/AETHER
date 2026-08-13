"""API router for query planning, hybrid retrieval, CRAG loop, conflict detection, and synthesis."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

try:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:
    select = None  # type: ignore
    AsyncSession = Any  # type: ignore

from backend.app.dependencies import get_db
from backend.models.evidence import EvidenceChunk
from backend.models.source import Source
from backend.schemas.evidence import EvidenceResponse
from backend.schemas.query import QueryRequest, QueryResponse
from backend.services.index.embeddings import embedding_service
from backend.services.index.faiss_index import faiss_index_service
from backend.services.retrieve.conflict_detector import conflict_detector
from backend.services.retrieve.planner import query_planner_service
from backend.services.retrieve.retriever import RetrievalResult
from backend.services.retrieve.synthesizer import answer_synthesizer_service
from backend.utils.validators import validate_citations, evidence_quality_score

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])

# CRAG settings
CRAG_QUALITY_THRESHOLD = 0.6
CRAG_MAX_HOPS = 3


async def _load_evidence_from_db(
    db_ids: List[int],
    distances: List[float],
    db: AsyncSession,
    reason_prefix: str = "FAISS",
) -> List[RetrievalResult]:
    """Load evidence chunks from SQLite by their DB primary keys."""
    evidence = []
    for rank, (dist, db_id) in enumerate(zip(distances, db_ids)):
        stmt = (
            select(EvidenceChunk, Source.filename)
            .join(Source, EvidenceChunk.source_id == Source.id)
            .where(EvidenceChunk.id == db_id)
        )
        row = (await db.execute(stmt)).first()
        if row:
            chunk_row, source_filename = row
            evidence.append(RetrievalResult(
                evidence_id=f"EID-{db_id}",
                text=chunk_row.content,
                source_name=source_filename,
                page_number=chunk_row.page_number,
                score=float(dist),
                reason=f"{reason_prefix} rank {rank+1}"
            ))
    return evidence


@router.post("", response_model=QueryResponse)
async def submit_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """Process a text-only evidence RAG query with CRAG loop and conflict detection.

    Flow:
    1. Plan query intent via Granite.
    2. CRAG retrieval loop: FAISS search → quality check → reformulate if weak → max 3 hops.
    3. Conflict detection across evidence from different sources.
    4. Synthesize grounded answer via Qwen (conflict-aware).
    5. Validate citations.
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
        logger.info("Step 1: Planning query...")
        plan = await query_planner_service.plan_query(query_text)
        if request.filters:
            plan.filters.update(request.filters)

        # Step 2: CRAG Retrieval Loop
        logger.info("Step 2: CRAG retrieval (max %d hops)...", CRAG_MAX_HOPS)
        merged_evidence: Dict[str, RetrievalResult] = {}
        current_queries = [query_text]
        hop_count = 0

        for hop in range(1, CRAG_MAX_HOPS + 1):
            hop_count = hop

            new_evidence = []
            for q in current_queries:
                query_vec = embedding_service.embed_query(q)
                distances, indices = faiss_index_service.search(query_vec, k=top_k)
                hop_evidence = await _load_evidence_from_db(
                    indices, distances, db, reason_prefix=f"Hop{hop}",
                )
                new_evidence.extend(hop_evidence)

            # Deduplicate
            for ev in new_evidence:
                if ev.evidence_id not in merged_evidence:
                    merged_evidence[ev.evidence_id] = ev

            all_evidence = list(merged_evidence.values())
            quality_score, quality_feedback = evidence_quality_score(all_evidence)

            logger.info("Hop %d: %d evidence pieces (score: %.2f)", hop, len(all_evidence), quality_score)

            if quality_score >= CRAG_QUALITY_THRESHOLD:
                break

            if hop < CRAG_MAX_HOPS:
                reformulated = await query_planner_service.reformulate_query(query_text, quality_feedback)
                reformulated = [q for q in reformulated if q.lower() != query_text.lower()]
                if not reformulated:
                    reformulated = [query_text]
                current_queries = reformulated

        retrieved_evidence = list(merged_evidence.values())

        # Step 3: Conflict Detection
        logger.info("Step 3: Conflict detection...")
        detected_conflicts = conflict_detector.detect(retrieved_evidence)
        conflict_count = len(detected_conflicts)
        if conflict_count:
            logger.warning("Detected %d conflict(s) in evidence.", conflict_count)

        # Step 4: Answer Synthesis (conflict-aware)
        logger.info("Step 4: Synthesizing answer...")
        synthesis = await answer_synthesizer_service.synthesize(
            evidence=retrieved_evidence,
            query=query_text,
            unload_after=False,
            conflicts=detected_conflicts if detected_conflicts else None,
        )

        # Step 5: Citation Validation
        logger.info("Step 5: Validating citations...")
        valid_eids = {item.evidence_id for item in retrieved_evidence}
        validation = validate_citations(synthesis.answer_text, valid_eids)

        if not validation.valid:
            logger.warning("Citation validation warnings: %s", validation.errors)

        # Convert to response schema
        evidence_schemas: List[EvidenceResponse] = []
        for item in retrieved_evidence:
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
        logger.info("Query complete in %d ms (%d hops, %d conflicts)", elapsed_ms, hop_count, conflict_count)

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
