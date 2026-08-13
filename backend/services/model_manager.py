"""Smart Model Manager service for offline GGUF/llama.cpp model loading, unloading, and RAM management.

Manages resident (always loaded, e.g. Granite 4 Tiny H) and non-resident
(swapped on demand, e.g. Qwen2.5-3B) models within the configured RAM budget.
"""

from __future__ import annotations

import gc
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Set

from backend.app.config import settings

logger = logging.getLogger(__name__)

# Model configurations: alias -> metadata
MODEL_SPECS: Dict[str, Dict[str, Any]] = {
    "granite": {
        "filename": settings.GRANITE_MODEL_FILENAME,
        "n_ctx": 2048,
        "n_threads": 16,
        "n_gpu_layers": 0,
        "size_mb": 1500,
        "is_resident": True,
    },
    "qwen": {
        "filename": settings.QWEN_MODEL_FILENAME,
        "n_ctx": 8192,
        "n_threads": 16,
        "n_gpu_layers": 999,
        "size_mb": 2500,
        "is_resident": False,
    },
}


class MockLlamaHandle:
    """Fallback mock handle for test environments when GGUF model files are absent."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def create_chat_completion(self, messages: list[dict[str, str]], **kwargs) -> dict[str, Any]:
        """Simulate llama_cpp create_chat_completion output."""
        user_content = messages[-1]["content"] if messages else ""
        
        if self.model_name == "granite":
            # Mock planner response
            response_json = (
                '{"primary_modality": "text", '
                f'"sub_queries": ["{user_content}"], '
                '"filters": {}, '
                '"requires_calculation": false}'
            )
        else:
            # Mock synthesizer response
            response_json = (
                f"Based on the evidence, the answer for '{user_content}' is confirmed. "
                "Citations: [EID-1].\n\nUnknowns: None."
            )

        return {
            "choices": [
                {
                    "message": {
                        "content": response_json
                    }
                }
            ]
        }


class SmartModelManager:
    """Manages offline GGUF model loading, unloading, and RAM budget enforcement.

    Parameters
    ----------
    ram_budget_mb:
        Maximum RAM budget allocated for models.
    models_dir:
        Directory containing .gguf model files.
    """

    def __init__(
        self,
        ram_budget_mb: int = settings.RAM_BUDGET_MB,
        models_dir: Path = settings.MODELS_DIR,
    ) -> None:
        self.ram_budget_mb = ram_budget_mb
        self.models_dir = Path(models_dir)
        self.loaded_models: Dict[str, Any] = {}
        self.resident_models: Set[str] = {"granite", "bge_m3", "bge_reranker"}
        self._lock = threading.Lock()

    def get(self, model_name: str) -> Any:
        """Get loaded model handle, loading it first if not present.

        Args:
            model_name: Model alias ("granite" or "qwen").

        Returns:
            Llama handle (or MockLlamaHandle if model file is missing).
        """
        with self._lock:
            if model_name in self.loaded_models:
                return self.loaded_models[model_name]
            return self._load_unlocked(model_name)

    def load(self, model_name: str) -> Any:
        """Explicitly load a model into memory.

        Args:
            model_name: Model alias ("granite" or "qwen").

        Returns:
            Llama handle.
        """
        with self._lock:
            return self._load_unlocked(model_name)

    def unload(self, model_name: str) -> bool:
        """Unload a model from memory to free RAM.

        Args:
            model_name: Model alias to unload.

        Returns:
            True if model was unloaded, False if it was not loaded.
        """
        with self._lock:
            if model_name not in self.loaded_models:
                return False

            logger.info("Unloading model '%s' from RAM...", model_name)
            del self.loaded_models[model_name]
            gc.collect()
            logger.info("Model '%s' unloaded successfully.", model_name)
            return True

    def get_loaded_models(self) -> list[str]:
        """Return names of currently loaded models."""
        with self._lock:
            return list(self.loaded_models.keys())

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _load_unlocked(self, model_name: str) -> Any:
        """Internal load logic executed under self._lock."""
        if model_name in self.loaded_models:
            return self.loaded_models[model_name]

        spec = MODEL_SPECS.get(model_name)
        filename = spec["filename"] if spec else f"{model_name}.gguf"
        model_path = self.models_dir / filename

        # Unload non-resident models if loading another non-resident model
        if spec and not spec.get("is_resident", False):
            for loaded_name in list(self.loaded_models.keys()):
                loaded_spec = MODEL_SPECS.get(loaded_name)
                if loaded_spec and not loaded_spec.get("is_resident", False):
                    if loaded_name not in self.resident_models:  # <-- ADD THIS CHECK
                        logger.info(
                            "Swapping out non-resident model '%s' to load '%s'...",
                            loaded_name,
                            model_name,
                        )
                        del self.loaded_models[loaded_name]
                        gc.collect()

        logger.info("Loading model '%s' from '%s'...", model_name, model_path)

        if model_path.exists():
            try:
                from llama_cpp import Llama

                n_ctx = spec["n_ctx"] if spec else 4096
                n_threads = spec["n_threads"] if spec else 16
                n_gpu_layers = spec.get("n_gpu_layers", 0) if spec else 0

                handle = Llama(
                    model_path=str(model_path),
                    n_ctx=n_ctx,
                    n_threads=n_threads,
                    n_batch=512,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
                self.loaded_models[model_name] = handle
                logger.info("Model '%s' loaded into memory successfully.", model_name)
                return handle
            except Exception as exc:
                logger.error("Failed to load Llama model '%s': %s", model_name, exc)
                raise RuntimeError(f"Failed to load model '{model_name}': {exc}") from exc
        else:
            logger.warning(
                "Model file '%s' not found at '%s'. Using MockLlamaHandle for fallback.",
                model_name,
                model_path,
            )
            mock_handle = MockLlamaHandle(model_name)
            self.loaded_models[model_name] = mock_handle
            return mock_handle
    def keep_loaded(self, model_name: str) -> None:
        """Mark a model as resident (do not auto-unload). Use for batch tests."""
        self.resident_models.add(model_name)
        logger.info("Model '%s' marked as resident for batch operation.", model_name)

    def release_batch(self, model_name: str) -> None:
        """Remove a model from resident set and unload it. Call after batch tests."""
        self.resident_models.discard(model_name)
        self.unload(model_name)
        logger.info("Model '%s' released after batch operation.", model_name)


# Singleton instance
model_manager = SmartModelManager()
