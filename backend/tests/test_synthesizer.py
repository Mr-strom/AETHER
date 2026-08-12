"""Unit tests for backend/services/retrieve/synthesizer.py"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from backend.services.retrieve.retriever import RetrievalResult
from backend.services.retrieve.synthesizer import AnswerSynthesizerService


def test_synthesizer_no_evidence() -> None:
    synth = AnswerSynthesizerService()
    res = asyncio.run(synth.synthesize(evidence=[], query="What is panel voltage?"))
    assert res.answer_text == "INSUFFICIENT_EVIDENCE"
    assert res.cited_ids == []
    assert res.confidence == "low"


def test_synthesizer_mock_success() -> None:
    synth = AnswerSynthesizerService()
    evidence = [
        RetrievalResult(
            evidence_id="EID-10",
            text="Voltage is 112V on Panel A-001.",
            source_name="notes.txt",
            page_number=1,
            score=0.9,
            reason="test",
        )
    ]

    mock_qwen = MagicMock()
    mock_qwen.create_chat_completion.return_value = {
        "choices": [
            {
                "message": {
                    "content": "The voltage reading for Panel A-001 is 112V [EID-10].\n\nUnknowns: None."
                }
            }
        ]
    }

    with patch("backend.services.retrieve.synthesizer.model_manager.get", return_value=mock_qwen):
        with patch("backend.services.retrieve.synthesizer.model_manager.unload"):
            res = asyncio.run(synth.synthesize(evidence=evidence, query="What is voltage?"))

    assert "112V" in res.answer_text
    assert res.cited_ids == ["EID-10"]
    assert res.confidence == "high"


def test_extract_cited_ids() -> None:
    synth = AnswerSynthesizerService()
    ids = synth._extract_cited_ids("Based on [EID-1] and [EID-42], the panel passed [EID-1].")
    assert ids == ["EID-1", "EID-42"]
