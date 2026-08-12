"""System schemas using Pydantic v2."""

from typing import Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: str = Field(default="ok", example="ok")
    version: str = Field(default="1.0.0", example="1.0.0")
    models_loaded: list[str] = Field(default_factory=list)
    ram_usage_mb: float = Field(default=0.0, example=0.0)


class ModelInfo(BaseModel):
    """Information about a loaded or available LLM/VLM model."""

    name: str
    filename: str
    size_mb: float
    is_loaded: bool = False
    context_window: int = 4096


class SystemStatusResponse(BaseModel):
    """Detailed system status response."""

    status: str = "ok"
    version: str = "1.0.0"
    models_loaded: list[ModelInfo] = Field(default_factory=list)
    ram_budget_mb: float = 14336.0
    ram_usage_mb: float = 0.0
    gpu_layers: int = 999
    gpu_available: bool = False
    active_sources_count: int = 0
    total_evidence_chunks: int = 0
