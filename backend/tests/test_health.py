"""Test system health check endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_endpoint(async_client: AsyncClient):
    """Verify /api/health returns 200 OK and valid health payload."""
    response = await async_client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"
    assert isinstance(data["models_loaded"], list)
    assert data["models_loaded"] == []
    assert data["ram_usage_mb"] == 0.0
