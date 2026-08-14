"""API router for query: POST /api/query and GET /api/query/stream (SSE)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

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

# Simple LRU query cache (max 100 entries)
_query_cache: Dict[str, dict] = {}
_CACHE_MAX = 100


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


def _build_response_dict(
    query_text: str,
    synthesis: Any,
    retrieved_evidence: List[RetrievalResult],
    elapsed_ms: int,
    hop_count: int,
    detected_conflicts: list,
) -> dict:
    """Build the response dict used by both POST and SSE endpoints."""
    evidence_list = []
    for item in retrieved_evidence:
        numeric_id = 0
        try:
            numeric_id = int(item.evidence_id.replace("EID-", ""))
        except ValueError:
            pass
        evidence_list.append({
            "id": numeric_id,
            "source_id": 1,
            "chunk_index": 0,
            "content": item.text,
            "modality": "text",
            "page_number": item.page_number,
            "confidence_score": item.score,
            "metadata_json": {
                "source_name": item.source_name,
                "reason": item.reason,
                "evidence_id": item.evidence_id,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    conf_score = 0.9 if synthesis.confidence == "high" else (0.6 if synthesis.confidence == "medium" else 0.3)

    return {
        "query_id": 1,
        "query": query_text,
        "answer": synthesis.answer_text,
        "citations": synthesis.cited_ids,
        "confidence": synthesis.confidence,
        "confidence_score": conf_score,
        "response_time_ms": float(elapsed_ms),
        "latency_ms": elapsed_ms,
        "model_used": "Qwen2.5-3B-Instruct-Q4_K_M",
        "evidence": evidence_list,
        "conflicts": [str(c) for c in detected_conflicts] if detected_conflicts else [],
        "hops": hop_count,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


async def _run_pipeline(
    query_text: str,
    top_k: int,
    db: AsyncSession,
    status_callback=None,
):
    """Run the full RAG pipeline, optionally yielding status updates via callback.

    Returns the response dict.
    """
    start_time = time.time()

    async def emit(step: str, message: str):
        if status_callback:
            await status_callback(step, message)

    # Step 1: Planning
    await emit("planning", "Analyzing query intent...")
    plan = await query_planner_service.plan_query(query_text)

    # Step 2: Retrieval
    await emit("retrieving", "Searching evidence database (FAISS + BM25)...")
    merged_evidence: Dict[str, RetrievalResult] = {}
    current_queries = [query_text]
    hop_count = 0

    for hop in range(1, CRAG_MAX_HOPS + 1):
        hop_count = hop
        await emit("crag", f"Evaluating evidence quality (Hop {hop}/{CRAG_MAX_HOPS})...")

        new_evidence = []
        for q in current_queries:
            query_vec = embedding_service.embed_query(q)
            distances, indices = faiss_index_service.search(query_vec, k=top_k)
            hop_evidence = await _load_evidence_from_db(
                indices, distances, db, reason_prefix=f"Hop{hop}",
            )
            new_evidence.extend(hop_evidence)

        for ev in new_evidence:
            if ev.evidence_id not in merged_evidence:
                merged_evidence[ev.evidence_id] = ev

        all_evidence = list(merged_evidence.values())
        quality_score, quality_feedback = evidence_quality_score(all_evidence)

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
    await emit("conflicts", "Checking for cross-source conflicts...")
    detected_conflicts = conflict_detector.detect(retrieved_evidence)

    # Step 4: Synthesis
    await emit("synthesizing", "Generating answer with citations...")
    synthesis = await answer_synthesizer_service.synthesize(
        evidence=retrieved_evidence,
        query=query_text,
        unload_after=False,
        conflicts=detected_conflicts if detected_conflicts else None,
    )

    # Step 5: Validation
    await emit("validating", "Verifying citation accuracy...")
    valid_eids = {item.evidence_id for item in retrieved_evidence}
    validate_citations(synthesis.answer_text, valid_eids)

    elapsed_ms = int((time.time() - start_time) * 1000)

    return _build_response_dict(
        query_text, synthesis, retrieved_evidence,
        elapsed_ms, hop_count, detected_conflicts,
    )


# ============================================================
# POST /api/query — standard JSON response
# ============================================================

@router.post("", response_model=QueryResponse)
async def submit_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """Process a text-only evidence RAG query."""
    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty or whitespace-only.",
        )

    query_text = request.query.strip()
    top_k = request.top_k or 5

    # Check cache
    cache_key = f"{query_text}:{top_k}"
    if cache_key in _query_cache:
        logger.info("Cache hit for query: '%s'", query_text)
        cached = _query_cache[cache_key]
        return QueryResponse(**cached)

    try:
        result = await _run_pipeline(query_text, top_k, db)

        # Cache result
        if len(_query_cache) >= _CACHE_MAX:
            oldest = next(iter(_query_cache))
            del _query_cache[oldest]
        _query_cache[cache_key] = result

        return QueryResponse(**result)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Query pipeline failure: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Query engine model failure: {exc}",
        ) from exc


# ============================================================
# GET /api/query/stream — Server-Sent Events
# ============================================================

def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/stream")
async def stream_query(
    q: str = Query(..., description="The query string"),
    top_k: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Stream query processing status via Server-Sent Events.

    Event types:
      - status: {step, message} — fires before each pipeline step
      - complete: full response payload
      - error: {error: string}
    """
    if not q or not q.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty.",
        )

    query_text = q.strip()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            status_queue: asyncio.Queue = asyncio.Queue()

            async def status_callback(step: str, message: str):
                await status_queue.put({"step": step, "message": message})

            # Run pipeline in background task
            pipeline_task = asyncio.create_task(
                _run_pipeline(query_text, top_k, db, status_callback=status_callback)
            )

            # Yield status events as they arrive
            while not pipeline_task.done():
                try:
                    status_update = await asyncio.wait_for(status_queue.get(), timeout=0.1)
                    yield _sse_event("status", status_update)
                except asyncio.TimeoutError:
                    continue

            # Drain remaining status events
            while not status_queue.empty():
                status_update = await status_queue.get()
                yield _sse_event("status", status_update)

            # Get result
            result = pipeline_task.result()
            yield _sse_event("complete", result)

        except Exception as exc:
            logger.error("SSE stream error: %s", exc, exc_info=True)
            yield _sse_event("error", {"error": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
