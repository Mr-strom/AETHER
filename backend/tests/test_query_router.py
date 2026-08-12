"""Unit tests for backend/routers/query.py"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.routers.query import submit_query
from backend.schemas.query import QueryRequest
from backend.services.retrieve.planner import QueryPlan
from backend.services.retrieve.retriever import RetrievalResult
from backend.services.retrieve.synthesizer import SynthesisResult


def test_submit_query_empty_bad_request() -> None:
    req = QueryRequest(query="")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(submit_query(req, db=None))
    assert exc_info.value.status_code == 400


def test_submit_query_success_flow() -> None:
    req = QueryRequest(query="What is Panel A-001 voltage?", top_k=3)

    mock_plan = QueryPlan(primary_modality="text", sub_queries=["What is Panel A-001 voltage?"], filters={}, requires_calculation=False)
    mock_evidence = [
        RetrievalResult(
            evidence_id="EID-1",
            text="Voltage is 112V on Panel A-001.",
            source_name="notes.txt",
            page_number=1,
            score=0.9,
            reason="FAISS similarity",
        )
    ]
    mock_synthesis = SynthesisResult(
        answer_text="The voltage is 112V [EID-1].",
        cited_ids=["EID-1"],
        confidence="high",
    )

    with patch("backend.routers.query.query_planner_service.plan_query", return_value=mock_plan):
        with patch("backend.routers.query.hybrid_retriever_service.retrieve", return_value=mock_evidence):
            with patch("backend.routers.query.answer_synthesizer_service.synthesize", return_value=mock_synthesis):
                res = asyncio.run(submit_query(req, db=None))

    assert res.query == "What is Panel A-001 voltage?"
    assert "112V" in res.answer
    assert res.citations == ["EID-1"]
    assert res.confidence == "high"
    assert len(res.evidence) == 1
    assert res.evidence[0].content == "Voltage is 112V on Panel A-001."
    assert res.latency_ms >= 0


def test_submit_query_pipeline_failure_503() -> None:
    req = QueryRequest(query="Error test")

    with patch("backend.routers.query.query_planner_service.plan_query", side_effect=RuntimeError("Model crash")):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(submit_query(req, db=None))

    assert exc_info.value.status_code == 503
