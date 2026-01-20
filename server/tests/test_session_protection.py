import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Add project to path first
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers.mock_settings import (
    MockSettings,
    create_common_patches,
    reload_app_modules_with_settings,
)

# Create mock settings with Turnstile enabled for session protection tests
mock_settings = MockSettings(enable_turnstile=True)

# Start all common patches
patches = create_common_patches(mock_settings)


# ----------------------------
# Async test client fixture
# ----------------------------
@pytest_asyncio.fixture
async def async_client():
    # Reload app modules with mock settings and router injection
    server_module = reload_app_modules_with_settings(mock_settings, reload_routers=True)

    async with AsyncClient(
        transport=ASGITransport(app=server_module.app), base_url="http://localhost"
    ) as ac:
        yield ac


# ----------------------------
# Test cases - Protected endpoints
# ----------------------------
@pytest.mark.asyncio
async def test_search_endpoint_requires_session(async_client: AsyncClient):
    """Test that /search requires X-Session-ID header when Turnstile is enabled."""
    response = await async_client.post("/search", json={"query": "test query"})

    assert response.status_code == 401
    assert "Session ID is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_document_endpoint_requires_session(async_client: AsyncClient):
    """Test that /document requires X-Session-ID header when Turnstile is enabled."""
    response = await async_client.get("/document/10.1000/test")

    assert response.status_code == 401
    assert "Session ID is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_raw_document_endpoint_requires_session(async_client: AsyncClient):
    """Test that /document/raw requires X-Session-ID header when Turnstile is enabled."""
    response = await async_client.get("/document/raw/10.1000/test")

    assert response.status_code == 401
    assert "Session ID is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_feedback_endpoint_requires_session(async_client: AsyncClient):
    """Test that /feedback/submit requires X-Session-ID header when Turnstile is enabled."""
    response = await async_client.post(
        "/feedback/submit",
        json={
            "statistic_id": "test-id",
            "feedback_type": "positive",
            "doi": "10.1000/test",
        },
    )

    assert response.status_code == 401
    assert "Session ID is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_search_structured_endpoint_requires_session(async_client: AsyncClient):
    """Test that /search/structured requires X-Session-ID header when Turnstile is enabled."""
    response = await async_client.post(
        "/search/structured",
        json={
            "modified_query_id": "test-id",
            "structured_data": {
                "intention": "find",
                "keywords": ["test"],
                "filters": {"logic": "AND"},
            },
        },
    )

    assert response.status_code == 401
    assert "Session ID is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_health_endpoint_not_protected(async_client: AsyncClient):
    """Test that /health endpoint is not protected even when Turnstile is enabled."""
    response = await async_client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"


@pytest.mark.asyncio
async def test_root_endpoint_not_protected(async_client: AsyncClient):
    """Test that root endpoint is not protected even when Turnstile is enabled."""
    response = await async_client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Welcome to Pan-Finder API"
