"""FastAPI dependency injection utilities."""

from typing import AsyncGenerator, Any
from backend.app.config import Settings, settings

try:
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.models.database import get_async_session
except ImportError:
    AsyncSession = Any  # type: ignore
    get_async_session = None  # type: ignore


def get_settings() -> Settings:
    """Dependency to inject application settings."""
    return settings


async def get_db() -> AsyncGenerator:
    """Dependency to inject asynchronous database session."""
    if get_async_session is None:
        yield None
        return
    async for session in get_async_session():
        yield session
