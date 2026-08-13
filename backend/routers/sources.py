"""API endpoints for managing sources."""

import hashlib
import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

try:
    from sqlalchemy import select, func, delete
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:
    select = None  # type: ignore
    func = None  # type: ignore
    AsyncSession = Any  # type: ignore

from backend.app.dependencies import get_db
from backend.models.evidence import EvidenceChunk
from backend.models.source import Source
from backend.schemas.source import SourceResponse, SourceListResponse, SourceCreate
from backend.services.index.embeddings import embedding_service
from backend.services.index.faiss_index import faiss_index_service
from backend.services.index.bm25_index import bm25_index_service
from backend.services.ingest.router import IngestRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("", response_model=SourceListResponse)
async def list_sources(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> SourceListResponse:
    """List all ingested sources with pagination."""
    # Count total
    count_stmt = select(func.count(Source.id))
    total = (await db.execute(count_stmt)).scalar() or 0

    # Fetch page
    stmt = select(Source).offset(skip).limit(limit).order_by(Source.id)
    rows = (await db.execute(stmt)).scalars().all()

    sources = [
        SourceResponse(
            id=s.id,
            filename=s.filename,
            file_type=s.file_type,
            file_path=s.file_path,
            file_hash=s.file_hash,
            size_bytes=s.size_bytes,
            status=s.status,
            metadata_json=s.metadata_json,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in rows
    ]

    return SourceListResponse(total=total, sources=sources)


@router.post("/upload", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_source(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    """Upload and ingest a new source document."""
    # Save uploaded file to temp location
    upload_dir = Path("./uploads")
    upload_dir.mkdir(exist_ok=True)
    file_path = upload_dir / file.filename

    content = await file.read()
    file_path.write_bytes(content)

    try:
        # Compute hash
        file_hash = hashlib.md5(content).hexdigest()

        # Check for duplicate
        existing = (await db.execute(
            select(Source).where(Source.file_hash == file_hash)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"File already ingested as source ID {existing.id}",
            )

        # Determine file type
        mime, _ = mimetypes.guess_type(str(file_path))
        file_type = mime or f"application/{file_path.suffix.lstrip('.')}"

        # Ingest chunks
        ingest_router = IngestRouter()
        chunks = await ingest_router.process_file(file_path)

        # Create Source record
        source = Source(
            filename=file.filename,
            file_type=file_type,
            file_path=str(file_path.absolute()),
            file_hash=file_hash,
            size_bytes=len(content),
            status="indexed",
        )
        db.add(source)
        await db.flush()

        # Create EvidenceChunk records
        chunk_ids = []
        for chunk in chunks:
            ec = EvidenceChunk(
                source_id=source.id,
                chunk_index=chunk.chunk_index,
                content=chunk.text,
                modality=chunk.modality,
                page_number=chunk.page_number,
            )
            db.add(ec)
            await db.flush()
            chunk_ids.append(ec.id)

        # Index into FAISS + BM25
        if chunks and chunk_ids:
            texts = [c.text for c in chunks]
            vectors = embedding_service.embed_texts(texts)
            faiss_index_service.add_vectors(vectors, chunk_ids)
            faiss_index_service.save()

            bm25_items = [(cid, c.text) for cid, c in zip(chunk_ids, chunks)]
            # Rebuild BM25 with all existing data
            all_chunks_stmt = select(EvidenceChunk.id, EvidenceChunk.content)
            all_rows = (await db.execute(all_chunks_stmt)).all()
            all_bm25 = [(row[0], row[1]) for row in all_rows]
            bm25_index_service.build_index(all_bm25)
            bm25_index_service.save()

        await db.commit()

        logger.info("Source '%s' ingested: %d chunks", file.filename, len(chunks))

        return SourceResponse(
            id=source.id,
            filename=source.filename,
            file_type=source.file_type,
            file_path=source.file_path,
            file_hash=source.file_hash,
            size_bytes=source.size_bytes,
            status=source.status,
            metadata_json=source.metadata_json,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Source upload failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {exc}",
        ) from exc


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    """Get details of a specific source by ID."""
    stmt = select(Source).where(Source.id == source_id)
    source = (await db.execute(stmt)).scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")

    return SourceResponse(
        id=source.id,
        filename=source.filename,
        file_type=source.file_type,
        file_path=source.file_path,
        file_hash=source.file_hash,
        size_bytes=source.size_bytes,
        status=source.status,
        metadata_json=source.metadata_json,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a source document and its associated evidence chunks.

    Also rebuilds FAISS and BM25 indices after removal.
    """
    source = (await db.execute(
        select(Source).where(Source.id == source_id)
    )).scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")

    # Delete source (cascade deletes evidence_chunks)
    await db.delete(source)
    await db.flush()

    # Rebuild indices from remaining data
    all_chunks_stmt = (
        select(EvidenceChunk.id, EvidenceChunk.content)
        .order_by(EvidenceChunk.id)
    )
    remaining = (await db.execute(all_chunks_stmt)).all()

    if remaining:
        chunk_ids = [row[0] for row in remaining]
        texts = [row[1] for row in remaining]

        # Rebuild FAISS
        vectors = embedding_service.embed_texts(texts)
        faiss_index_service.rebuild(vectors, chunk_ids)
        faiss_index_service.save()

        # Rebuild BM25
        bm25_items = [(cid, text) for cid, text in zip(chunk_ids, texts)]
        bm25_index_service.build_index(bm25_items)
        bm25_index_service.save()
    else:
        # No data left — clear indices
        faiss_index_service.clear()
        bm25_index_service.build_index([])

    await db.commit()
    logger.info("Source %d deleted. Indices rebuilt with %d remaining chunks.", source_id, len(remaining))
