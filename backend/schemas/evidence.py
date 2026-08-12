"""Evidence schemas using Pydantic v2."""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class EvidenceResponse(BaseModel):
    """Evidence chunk response payload."""

    id: int
    source_id: int
    chunk_index: int
    content: str
    modality: str
    page_number: Optional[int] = None
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None
    bbox_json: Optional[dict[str, Any]] = None
    embedding_id: Optional[str] = None
    confidence_score: float = 1.0
    metadata_json: Optional[dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EvidenceRelationResponse(BaseModel):
    """Evidence relationship response payload."""

    id: int
    source_evidence_id: int
    target_evidence_id: int
    relation_type: str
    confidence: float
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GraphNode(BaseModel):
    """Node definition for vis-network conflict graph."""

    id: str
    label: str
    group: str
    evidence_id: int


class GraphEdge(BaseModel):
    """Edge definition for vis-network conflict graph."""

    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    label: str
    arrows: str = "to"

    class Config:
        populate_by_name = True


class ConflictGraphResponse(BaseModel):
    """Graph response formatted for frontend vis-network rendering."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
