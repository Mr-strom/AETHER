"""API endpoints for managing sources with file upload and cleanup."""

import hashlib
import logging
import mimetypes
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse

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

UPLOADS_DIR = Path("./uploads")
DEMO_BUNDLE_DIR = Path("./demo_bundle")


def _source_to_response(s: Any) -> SourceResponse:
    """Convert a Source ORM object to a SourceResponse schema."""
    return SourceResponse(
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


@router.get("", response_model=SourceListResponse)
async def list_sources(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> SourceListResponse:
    """List all ingested sources with pagination."""
    count_stmt = select(func.count(Source.id))
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = select(Source).offset(skip).limit(limit).order_by(Source.id)
    rows = (await db.execute(stmt)).scalars().all()

    return SourceListResponse(
        total=total,
        sources=[_source_to_response(s) for s in rows],
    )


async def _ingest_file_to_db(
    file_path: Path,
    file_bytes: bytes,
    db: AsyncSession,
    origin: str = "upload",
) -> dict:
    """Shared ingestion logic: ingest file → DB + FAISS + BM25.

    Returns dict with {source_id, filename, chunks_count, status}.
    """
    file_hash = hashlib.md5(file_bytes).hexdigest()

    # Check duplicate
    existing = (await db.execute(
        select(Source).where(Source.file_hash == file_hash)
    )).scalar_one_or_none()
    if existing:
        return {
            "source_id": existing.id,
            "filename": existing.filename,
            "chunks_count": 0,
            "status": "duplicate",
        }

    # Determine file type
    mime, _ = mimetypes.guess_type(str(file_path))
    file_type = mime or f"application/{file_path.suffix.lstrip('.')}"

    # Ingest chunks
    ingest_router = IngestRouter()
    chunks = await ingest_router.process_file(file_path)

    # --- Contextual Retrieval: enrich chunks before embedding ---
    try:
        from backend.services.ingest.contextualizer import Contextualizer
        raw_texts = [c.text for c in chunks if c.text]
        if raw_texts:
            contextualizer = Contextualizer()
            ctx_texts = contextualizer.contextualize_document(raw_texts)
            idx = 0
            for chunk in chunks:
                if chunk.text:
                    chunk.index_text = ctx_texts[idx]
                    idx += 1
                else:
                    chunk.index_text = chunk.text
    except Exception as exc:
        logger.warning("Contextualizer failed, using raw text: %s", exc)
        for chunk in chunks:
            chunk.index_text = chunk.text

    # Create Source record
    source = Source(
        filename=file_path.name,
        file_type=file_type,
        file_path=str(file_path.absolute()),
        file_hash=file_hash,
        size_bytes=len(file_bytes),
        status="indexed",
        metadata_json={"origin": origin},
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
            index_text=chunk.index_text,
            modality=chunk.modality,
            page_number=chunk.page_number,
        )
        db.add(ec)
        await db.flush()
        chunk_ids.append(ec.id)

    # Index into FAISS + BM25 (use index_text for better retrieval)
    if chunks and chunk_ids:
        texts = [c.index_text or c.text for c in chunks]
        vectors = embedding_service.embed_texts(texts)
        faiss_index_service.add_vectors(vectors, chunk_ids)
        faiss_index_service.save()

        # Rebuild BM25 from all data (prefer index_text)
        all_chunks_stmt = select(EvidenceChunk.id, EvidenceChunk.index_text, EvidenceChunk.content)
        all_rows = (await db.execute(all_chunks_stmt)).all()
        all_bm25 = [(row[0], row[1] or row[2]) for row in all_rows]
        bm25_index_service.build_index(all_bm25)
        bm25_index_service.save()

    return {
        "source_id": source.id,
        "filename": file_path.name,
        "chunks_count": len(chunks),
        "status": "indexed",
    }


@router.post("/upload-file", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload and ingest a file via multipart/form-data.

    Accepts PDF, DOCX, TXT, CSV, MD files.
    Returns {source_id, filename, chunks_count, status}.
    """
    UPLOADS_DIR.mkdir(exist_ok=True)
    file_path = UPLOADS_DIR / file.filename

    content = await file.read()
    file_path.write_bytes(content)

    try:
        result = await _ingest_file_to_db(file_path, content, db, origin="upload")
        await db.commit()
        logger.info("Upload '%s': %s", file.filename, result["status"])
        return JSONResponse(content=result, status_code=201)

    except Exception as exc:
        await db.rollback()
        logger.error("Upload failed for '%s': %s", file.filename, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {exc}",
        ) from exc


@router.post("/clear-uploads")
async def clear_uploads(
    db: AsyncSession = Depends(get_db),
):
    """Clear all uploaded files and rebuild indices from demo_bundle only.

    - Deletes all files in ./uploads/
    - Removes their chunks from SQLite
    - Rebuilds FAISS + BM25 from remaining (demo_bundle) data
    """
    cleared_count = 0

    # Find sources with origin=upload
    stmt = select(Source).where(Source.metadata_json["origin"].as_string() == "upload")
    upload_sources = (await db.execute(stmt)).scalars().all()

    if not upload_sources:
        # Fallback: check file_path for ./uploads/ prefix
        stmt2 = select(Source)
        all_sources = (await db.execute(stmt2)).scalars().all()
        upload_sources = [
            s for s in all_sources
            if "uploads" in (s.file_path or "").replace("\\", "/")
        ]

    for source in upload_sources:
        await db.delete(source)
        cleared_count += 1

    await db.flush()

    # Clear the uploads directory on disk
    if UPLOADS_DIR.exists():
        shutil.rmtree(UPLOADS_DIR, ignore_errors=True)
        UPLOADS_DIR.mkdir(exist_ok=True)

    # Rebuild indices from remaining data (prefer index_text)
    remaining_stmt = (
        select(EvidenceChunk.id, EvidenceChunk.index_text, EvidenceChunk.content)
        .order_by(EvidenceChunk.id)
    )
    remaining = (await db.execute(remaining_stmt)).all()

    if remaining:
        chunk_ids = [row[0] for row in remaining]
        texts = [row[1] or row[2] for row in remaining]
        vectors = embedding_service.embed_texts(texts)
        faiss_index_service.rebuild(vectors, chunk_ids)
        faiss_index_service.save()
        bm25_index_service.build_index(list(zip(chunk_ids, texts)))
        bm25_index_service.save()
    else:
        faiss_index_service.clear()
        bm25_index_service.build_index([])

    await db.commit()

    remaining_count = (await db.execute(select(func.count(Source.id)))).scalar() or 0
    logger.info("Cleared %d uploads. %d sources remain.", cleared_count, remaining_count)

    return {
        "cleared_count": cleared_count,
        "remaining_sources": remaining_count,
    }


# Keep existing upload endpoint for backward compat
@router.post("/upload", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_source(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    """Upload and ingest a new source document (legacy endpoint)."""
    UPLOADS_DIR.mkdir(exist_ok=True)
    file_path = UPLOADS_DIR / file.filename

    content = await file.read()
    file_path.write_bytes(content)

    try:
        file_hash = hashlib.md5(content).hexdigest()

        existing = (await db.execute(
            select(Source).where(Source.file_hash == file_hash)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"File already ingested as source ID {existing.id}",
            )

        mime, _ = mimetypes.guess_type(str(file_path))
        file_type = mime or f"application/{file_path.suffix.lstrip('.')}"

        ingest_router = IngestRouter()
        chunks = await ingest_router.process_file(file_path)

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

        chunk_ids = []
        for chunk in chunks:
            ec = EvidenceChunk(
                source_id=source.id,
                chunk_index=chunk.chunk_index,
                content=chunk.text,
                index_text=getattr(chunk, 'index_text', None) or chunk.text,
                modality=chunk.modality,
                page_number=chunk.page_number,
            )
            db.add(ec)
            await db.flush()
            chunk_ids.append(ec.id)

        if chunks and chunk_ids:
            texts = [getattr(c, 'index_text', None) or c.text for c in chunks]
            vectors = embedding_service.embed_texts(texts)
            faiss_index_service.add_vectors(vectors, chunk_ids)
            faiss_index_service.save()

            all_chunks_stmt = select(EvidenceChunk.id, EvidenceChunk.index_text, EvidenceChunk.content)
            all_rows = (await db.execute(all_chunks_stmt)).all()
            all_bm25 = [(row[0], row[1] or row[2]) for row in all_rows]
            bm25_index_service.build_index(all_bm25)
            bm25_index_service.save()

        await db.commit()
        logger.info("Source '%s' ingested: %d chunks", file.filename, len(chunks))
        return _source_to_response(source)

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
    return _source_to_response(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a source and rebuild indices."""
    source = (await db.execute(
        select(Source).where(Source.id == source_id)
    )).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")

    await db.delete(source)
    await db.flush()

    remaining = (await db.execute(
        select(EvidenceChunk.id, EvidenceChunk.index_text, EvidenceChunk.content).order_by(EvidenceChunk.id)
    )).all()

    if remaining:
        chunk_ids = [row[0] for row in remaining]
        texts = [row[1] or row[2] for row in remaining]
        vectors = embedding_service.embed_texts(texts)
        faiss_index_service.rebuild(vectors, chunk_ids)
        faiss_index_service.save()
        bm25_index_service.build_index(list(zip(chunk_ids, texts)))
        bm25_index_service.save()
    else:
        faiss_index_service.clear()
        bm25_index_service.build_index([])

    await db.commit()
    logger.info("Source %d deleted. %d chunks remaining.", source_id, len(remaining))
