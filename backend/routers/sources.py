"""API endpoints for managing sources."""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:
    AsyncSession = Any  # type: ignore
from backend.app.dependencies import get_db
from backend.schemas.source import SourceResponse, SourceListResponse, SourceCreate

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("", response_model=SourceListResponse)
async def list_sources(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> SourceListResponse:
    """List all ingested sources."""
    # Stub response
    return SourceListResponse(total=0, sources=[])


@router.post("/upload", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_source(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    """Upload and ingest a new source document or file."""
    # Stub response
    raise HTTPException(status_code=501, detail="Source upload ingestion not implemented yet")


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    """Get details of a specific source by ID."""
    raise HTTPException(status_code=404, detail=f"Source {source_id} not found")


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a source document and its associated evidence chunks."""
    return None
