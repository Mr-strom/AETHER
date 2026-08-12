"""Async pytest fixtures for AETHER backend testing."""

import asyncio
from typing import AsyncGenerator
import pytest


@pytest.fixture
async def async_client() -> AsyncGenerator:
    """Async HTTP client fixture configured for testing FastAPI app."""
    try:
        from httpx import AsyncClient, ASGITransport
        from backend.app.main import app
    except ImportError as e:
        pytest.skip(f"Dependencies not installed for async_client: {e}")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
