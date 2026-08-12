"""Main FastAPI application entry point for AETHER."""

from contextlib import asynccontextmanager
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """App lifecycle startup and shutdown handler."""
    setup_logging(settings.LOG_LEVEL)

    # Initialize database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Cleanup resources on shutdown
    await engine.dispose()


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
