"""Unit tests for backend/services/retrieve/retriever.py"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from backend.services.retrieve.planner import QueryPlan
from backend.services.retrieve.retriever import HybridRetrieverService, RetrievalResult


def test_retrieval_result_schema() -> None:
    res = RetrievalResult(
        evidence_id="EID-1",
        text="Sample text",
        source_name="notes.txt",
        page_number=1,
        score=0.95,
        reason="FAISS similarity",
    )
    assert res.evidence_id == "EID-1"
    assert res.score == 0.95


def test_hybrid_retriever_empty_candidates() -> None:
    retriever = HybridRetrieverService()
    plan = QueryPlan(primary_modality="text", sub_queries=["test"], filters={}, requires_calculation=False)

    with patch("backend.services.retrieve.retriever.embedding_service.embed_query", return_value=[0.1] * 1024):
        with patch("backend.services.retrieve.retriever.faiss_index_service.search", return_value=([], [])):
            with patch("backend.services.retrieve.retriever.bm25_index_service.search", return_value=[]):
                results = asyncio.run(retriever.retrieve(plan, db_session=None, k=5))

    assert results == []


def test_hybrid_retriever_with_candidates() -> None:
    retriever = HybridRetrieverService()
    plan = QueryPlan(primary_modality="text", sub_queries=["voltage"], filters={}, requires_calculation=False)

    with patch("backend.services.retrieve.retriever.embedding_service.embed_query", return_value=[0.1] * 1024):
        with patch("backend.services.retrieve.retriever.faiss_index_service.search", return_value=([0.9, 0.8], [10, 20])):
            with patch("backend.services.retrieve.retriever.reranker_service.rerank", return_value=[0.95, 0.85]):
                results = asyncio.run(retriever.retrieve(plan, db_session=None, k=5))

    assert len(results) == 2
    assert results[0].evidence_id in {"EID-10", "EID-20"}
    assert results[0].score == 0.95
