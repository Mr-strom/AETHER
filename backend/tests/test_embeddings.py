"""Unit tests for backend/services/index/embeddings.py

These tests use a lightweight mock to avoid downloading the BGE-M3 model
during CI, while still exercising the batching, empty-string, and shape
validation logic.
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_mock_model(dim: int = 1024):
    """Return a SentenceTransformer mock that returns random float32 vectors."""

    model = MagicMock()

    def fake_encode(texts, **kwargs):
        n = len(texts)
        return np.random.rand(n, dim).astype("float32")

    model.encode.side_effect = fake_encode
    return model


# ---------------------------------------------------------------------------
# EmbeddingService tests
# ---------------------------------------------------------------------------


def test_embed_texts_returns_correct_shape() -> None:
    from backend.services.index.embeddings import EmbeddingService

    svc = EmbeddingService()
    mock_model = _make_mock_model(1024)

    with patch.object(svc, "_get_model", return_value=mock_model):
        vecs = svc.embed_texts(["hello", "world", "AETHER"])

    assert len(vecs) == 3
    assert all(len(v) == 1024 for v in vecs)


def test_embed_texts_empty_list() -> None:
    from backend.services.index.embeddings import EmbeddingService

    svc = EmbeddingService()
    result = svc.embed_texts([])
    assert result == []


def test_embed_texts_replaces_empty_string() -> None:
    """Empty strings should be replaced with sentinel, not cause model errors."""
    from backend.services.index.embeddings import EmbeddingService

    svc = EmbeddingService()
    mock_model = _make_mock_model(1024)
    received: list[list[str]] = []

    def capture_encode(texts, **kwargs):
        received.extend(texts)
        return np.random.rand(len(texts), 1024).astype("float32")

    mock_model.encode.side_effect = capture_encode

    with patch.object(svc, "_get_model", return_value=mock_model):
        svc.embed_texts(["", "  ", "real text"])

    # No empty string should reach the model
    assert "" not in received
    assert all(t == " " or t == "real text" for t in received)


def test_embed_texts_batching() -> None:
    """Verify model.encode is called in batches when input exceeds batch_size."""
    from backend.services.index.embeddings import EmbeddingService

    svc = EmbeddingService()
    svc._batch_size = 3  # Override for test
    mock_model = _make_mock_model(1024)
    call_sizes: List[int] = []

    def capture_encode(texts, **kwargs):
        call_sizes.append(len(texts))
        return np.random.rand(len(texts), 1024).astype("float32")

    mock_model.encode.side_effect = capture_encode

    with patch.object(svc, "_get_model", return_value=mock_model):
        svc.embed_texts(["a", "b", "c", "d", "e", "f", "g"])  # 7 texts, batch=3

    # Expect batches of [3, 3, 1]
    assert call_sizes == [3, 3, 1]


def test_embed_texts_wrong_dim_raises() -> None:
    """If the model returns the wrong dimensionality, RuntimeError is raised."""
    from backend.services.index.embeddings import EmbeddingService

    svc = EmbeddingService()
    svc._expected_dim = 1024
    bad_model = _make_mock_model(dim=512)  # Wrong dim

    with patch.object(svc, "_get_model", return_value=bad_model):
        with pytest.raises(RuntimeError, match="Unexpected embedding dim"):
            svc.embed_texts(["test"])


def test_embed_query_single_vector() -> None:
    from backend.services.index.embeddings import EmbeddingService

    svc = EmbeddingService()
    mock_model = _make_mock_model(1024)

    with patch.object(svc, "_get_model", return_value=mock_model):
        vec = svc.embed_query("What is AETHER?")

    assert isinstance(vec, list)
    assert len(vec) == 1024


def test_embed_query_empty_string() -> None:
    from backend.services.index.embeddings import EmbeddingService

    svc = EmbeddingService()
    mock_model = _make_mock_model(1024)

    with patch.object(svc, "_get_model", return_value=mock_model):
        vec = svc.embed_query("")

    assert len(vec) == 1024


def test_is_loaded_initially_false() -> None:
    from backend.services.index.embeddings import EmbeddingService

    svc = EmbeddingService()
    assert svc.is_loaded() is False


def test_is_loaded_after_mock_init() -> None:
    from backend.services.index.embeddings import EmbeddingService

    svc = EmbeddingService()
    svc._model = _make_mock_model()  # Simulate loaded state
    assert svc.is_loaded() is True


def test_embed_output_is_list_of_lists() -> None:
    from backend.services.index.embeddings import EmbeddingService

    svc = EmbeddingService()
    mock_model = _make_mock_model(1024)

    with patch.object(svc, "_get_model", return_value=mock_model):
        result = svc.embed_texts(["test sentence"])

    assert isinstance(result, list)
    assert isinstance(result[0], list)
    assert all(isinstance(v, float) for v in result[0])
