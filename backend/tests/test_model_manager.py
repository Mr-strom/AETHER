"""Unit tests for backend/services/model_manager.py"""

import gc
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.services.model_manager import SmartModelManager, MockLlamaHandle


def test_mock_llama_handle_granite() -> None:
    handle = MockLlamaHandle("granite")
    res = handle.create_chat_completion([{"role": "user", "content": "test query"}])
    assert "choices" in res
    assert "primary_modality" in res["choices"][0]["message"]["content"]


def test_mock_llama_handle_qwen() -> None:
    handle = MockLlamaHandle("qwen")
    res = handle.create_chat_completion([{"role": "user", "content": "test query"}])
    assert "choices" in res
    assert "INSUFFICIENT_EVIDENCE" in res["choices"][0]["message"]["content"] or "Citations:" in res["choices"][0]["message"]["content"]


def test_model_manager_fallback(tmp_path: Path) -> None:
    mgr = SmartModelManager(models_dir=tmp_path)
    handle = mgr.get("granite")
    assert handle is not None
    assert "granite" in mgr.get_loaded_models()


def test_model_manager_unload(tmp_path: Path) -> None:
    mgr = SmartModelManager(models_dir=tmp_path)
    mgr.load("granite")
    assert "granite" in mgr.get_loaded_models()

    unloaded = mgr.unload("granite")
    assert unloaded is True
    assert "granite" not in mgr.get_loaded_models()


def test_model_manager_unload_not_loaded() -> None:
    mgr = SmartModelManager()
    assert mgr.unload("non_existent_model") is False


def test_model_manager_swapping(tmp_path: Path) -> None:
    mgr = SmartModelManager(models_dir=tmp_path)
    # Load qwen (non-resident)
    mgr.load("qwen")
    assert "qwen" in mgr.get_loaded_models()

    # Load granite (resident)
    mgr.load("granite")
    assert "granite" in mgr.get_loaded_models()
