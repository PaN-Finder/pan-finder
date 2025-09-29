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
# Auto environment setup
# ----------------------------
@pytest.fixture(autouse=True)
def _env_setup(monkeypatch):
    """Provide minimal environment configuration required by settings."""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.test")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/test")
    monkeypatch.setenv("ENABLE_TURNSTILE", "false")

    from src import config as config_module

    config_module.get_settings.cache_clear()

    yield

    config_module.get_settings.cache_clear()


# ----------------------------
# Async test client fixture
# ----------------------------
@pytest_asyncio.fixture(scope="session")
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
# Test cases
# ----------------------------
@pytest.mark.asyncio
async def test_health_endpoint_success(async_client: AsyncClient):
    response = await async_client.get("/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "healthy"
    assert payload["database"] == "healthy"
    assert "version" in payload


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")

    assert response.status_code == 200
    payload = response.json()

    assert payload["message"] == "Welcome to Pan-Finder API"
    assert "version" in payload
