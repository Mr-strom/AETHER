"""Source schemas using Pydantic v2."""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class SourceBase(BaseModel):
    """Base fields for Source."""

    filename: str
    file_type: str
    file_path: str
    file_hash: str
    size_bytes: int = 0
    status: str = "pending"
    metadata_json: Optional[dict[str, Any]] = None


class SourceCreate(BaseModel):
    """Payload for creating a source manually or via file upload."""

    filename: str
    file_type: str
    file_path: str
    file_hash: str
    size_bytes: int = 0
    metadata_json: Optional[dict[str, Any]] = None


class SourceResponse(SourceBase):
    """Source response payload."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SourceListResponse(BaseModel):
    """List of sources response payload."""

    total: int
    sources: list[SourceResponse]
