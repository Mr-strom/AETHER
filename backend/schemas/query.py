"""Query and Evaluation schemas using Pydantic v2."""

from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel, Field
from backend.schemas.evidence import EvidenceResponse


class QueryRequest(BaseModel):
    """Payload for user query submission."""

    query: str = Field(..., example="What is the voltage reading for Panel A-001?")
    filters: Optional[dict[str, Any]] = Field(default_factory=dict)
    top_k: int = Field(default=5, ge=1, le=20)
    use_crag_validator: bool = True
    modalities: Optional[list[str]] = Field(default_factory=lambda: ["text", "table"])


class QueryResponse(BaseModel):
    """Payload returned for a query execution."""

    query_id: Optional[int] = None
    query: str
    answer: str
    citations: list[str] = Field(default_factory=list)
    confidence: str = "high"
    confidence_score: float = 1.0
    response_time_ms: float = 0.0
    latency_ms: int = 0
    model_used: str = "Qwen2.5-3B-Instruct-Q4_K_M"
    evidence: list[EvidenceResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvaluationRequest(BaseModel):
    """Payload for triggering RAG system evaluation."""

    sample_size: int = 10


class MetricScore(BaseModel):
    """Single metric result."""

    metric_name: str
    score: float
    details: Optional[dict[str, Any]] = None


class EvaluationResponse(BaseModel):
    """Results from automated or offline RAG evaluation."""

    evaluated_queries_count: int
    overall_score: float
    metrics: list[MetricScore]
