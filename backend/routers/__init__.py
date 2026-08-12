"""FastAPI routers package for AETHER."""

from backend.routers.sources import router as sources_router
from backend.routers.query import router as query_router
from backend.routers.evidence import router as evidence_router
from backend.routers.system import router as system_router
from backend.routers.evaluate import router as evaluate_router

__all__ = [
    "sources_router",
    "query_router",
    "evidence_router",
    "system_router",
    "evaluate_router",
]
