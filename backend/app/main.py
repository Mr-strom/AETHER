"""Main FastAPI application entry point for AETHER."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.logging import setup_logging
from backend.models.database import engine, Base
from backend.schemas.system import HealthResponse
from backend.routers import (
    sources_router,
    query_router,
    evidence_router,
    system_router,
    evaluate_router,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """App lifecycle startup and shutdown handler."""
    setup_logging(settings.LOG_LEVEL)

    # Initialize database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Load persisted indices (if they exist)
    _load_indices_on_startup()

    # Generate manifest if missing
    _ensure_manifest()

    yield

    # Cleanup resources on shutdown
    await engine.dispose()


def _load_indices_on_startup() -> None:
    """Attempt to load FAISS and BM25 indices from disk on startup."""
    # Load FAISS
    try:
        from backend.services.index.faiss_index import faiss_index_service
        faiss_index_service.load()
        logger.info(
            "FAISS index loaded: %d vectors.",
            faiss_index_service._index.ntotal if faiss_index_service._index else 0,
        )
    except FileNotFoundError:
        logger.warning("FAISS index not found on disk. Will be empty until data is ingested.")
    except Exception as exc:
        logger.warning("Failed to load FAISS index: %s", exc)

    # Load BM25
    try:
        from backend.services.index.bm25_index import bm25_index_service
        bm25_index_service.load()
        logger.info(
            "BM25 index loaded: %d documents.",
            len(bm25_index_service.corpus_ids),
        )
    except FileNotFoundError:
        logger.warning("BM25 index not found on disk. Will be empty until data is ingested.")
    except Exception as exc:
        logger.warning("Failed to load BM25 index: %s", exc)


def _ensure_manifest() -> None:
    """Generate model manifest if it doesn't exist."""
    manifest_path = Path("./manifest.json")
    if manifest_path.exists():
        logger.info("Manifest found at %s", manifest_path)
        return

    try:
        from backend.services.attestation import generate_manifest
        generate_manifest()
        logger.info("Manifest generated at %s", manifest_path)
    except Exception as exc:
        logger.warning("Could not generate manifest: %s", exc)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="AETHER - Offline Multimodal Evidence RAG System Backend",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register APIRouters
app.include_router(sources_router)
app.include_router(query_router)
app.include_router(evidence_router)
app.include_router(system_router)
app.include_router(evaluate_router)


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    """Return backend health status, loaded models, and memory usage."""
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        models_loaded=[],
        ram_usage_mb=0.0,
    )

