import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "AI Knowledge Assistant"
    assert data["api_v1"] == "/api/v1"
    assert data["health"] == "/api/v1/health"


@pytest.mark.asyncio
async def test_liveness_probe(async_client: AsyncClient):
    response = await async_client.get("/api/v1/health/liveness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_probe_healthy(async_client: AsyncClient, mock_health_healthy):
    response = await async_client.get("/api/v1/health/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_health_check_healthy(async_client: AsyncClient, mock_health_healthy):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"]["connected"] is True
    assert data["database"]["pgvector_installed"] is True
    assert data["redis"]["connected"] is True


@pytest.mark.asyncio
async def test_health_check_degraded(async_client: AsyncClient, mock_health_unhealthy):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"]["connected"] is False
    assert data["redis"]["connected"] is False


@pytest.mark.asyncio
async def test_api_versioning_endpoints(async_client: AsyncClient):
    # Test v1 chat placeholder
    chat_res = await async_client.get("/api/v1/chat/sessions")
    assert chat_res.status_code == 200
    assert "sessions" in chat_res.json()
