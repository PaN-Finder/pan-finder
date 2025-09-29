import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ----------------------------
# Lifespan override (skip startup/shutdown)
# ----------------------------
@asynccontextmanager
async def mock_lifespan(app: FastAPI):
    yield


# ----------------------------
# Environment setup for Turnstile-enabled tests
# ----------------------------
@pytest.fixture(autouse=True)
def _env_setup_with_turnstile(monkeypatch):
    """Environment configuration with Turnstile enabled."""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.test")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/test")
    monkeypatch.setenv("ENABLE_TURNSTILE", "true")
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "test-turnstile-secret")

    from src import config as config_module

    config_module.get_settings.cache_clear()

    yield

    config_module.get_settings.cache_clear()


# ----------------------------
# Async test client fixture
# ----------------------------
@pytest_asyncio.fixture
async def async_client():
    import src.server as server_module

    importlib.reload(server_module)

    # Disable startup/shutdown events
    server_module.app.router.lifespan_context = mock_lifespan

    with (
        patch("src.server.check_database_health", return_value=True),
        patch("asyncio.create_task", return_value=MagicMock()),
    ):
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
