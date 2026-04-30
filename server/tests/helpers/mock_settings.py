"""
Common mock settings and patching utilities for FastAPI async tests.
"""

import importlib
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

from fastapi import FastAPI


class MockSettings:
    """Shared mock settings that includes all required configuration attributes."""

    llm_provider = "azure"
    azure_openai_endpoint = "https://example.openai.test"
    azure_openai_api_key = "test-key"
    azure_openai_api_version = "2024-12-01-preview"
    openai_api_key = ""
    openai_base_url = ""
    default_model_name = "gpt-4.1-mini"
    explanation_model_name = "gpt-4.1"
    database_url = "postgresql://user:pass@localhost:5432/test"
    db_pool_min_size = 1
    db_pool_max_size = 20
    db_connection_timeout = 30
    db_max_idle = 300
    db_max_lifetime = 3600
    turnstile_secret_key = "test-key"
    allowed_origins = ["*"]
    api_host = "0.0.0.0"
    api_port = 8080
    embedding_model_path = "/tmp/models/all-MiniLM-L12-v2"
    rrf_k_similarity = 6
    rrf_k_chunk = 6
    rrf_k_full_match = 6
    rrf_k_partial_match = 6
    rrf_k_keyword = 10
    rrf_k_filter_value = 6

    def __init__(self, enable_turnstile=False):
        """Initialize with configurable Turnstile setting."""
        self.enable_turnstile = enable_turnstile


def create_common_patches(mock_settings_instance):
    """Create and start common patches for FastAPI async tests."""
    patches = {}

    # Settings patch
    patches["settings"] = patch(
        "src.config.get_settings", return_value=mock_settings_instance
    )

    # Database patches
    patches["db"] = patch.multiple(
        "src.db.connection",
        DatabaseManager=MagicMock(),
        _db_manager=MagicMock(),
        register_database=MagicMock(),
        get_database_pool=MagicMock(),
        get_database_connection=MagicMock(),
        check_database_health=MagicMock(return_value=True),
        reset_database_pool=MagicMock(),
        cleanup_connection_pools=MagicMock(),
    )

    # Migration patch
    patches["migrate"] = patch("src.db.migrate.run_migrations", MagicMock())

    # Server patches
    patches["server"] = patch.multiple(
        "src.server",
        session_cleanup_task=MagicMock(),
    )

    # Session repository patch
    patches["session"] = patch(
        "src.core.session.SessionRepository.cleanup_expired_sessions",
        MagicMock(return_value=0),
    )

    # Start all patches
    for patch_obj in patches.values():
        patch_obj.start()

    return patches


@asynccontextmanager
async def mock_lifespan(app: FastAPI):
    """Mock lifespan context that skips startup/shutdown tasks."""
    yield


def reload_app_modules_with_settings(mock_settings_instance, reload_routers=False):
    """
    Reload server module and optionally router modules with injected mock settings.

    Args:
        mock_settings_instance: The MockSettings instance to inject
        reload_routers: Whether to also reload and inject settings into router modules
    """
    if reload_routers:
        # Reload router modules and inject settings
        import src.routers.document as document_module
        import src.routers.feedback as feedback_module
        import src.routers.search as search_module
        import src.routers.session as session_module

        importlib.reload(session_module)
        session_module.settings = mock_settings_instance
        importlib.reload(search_module)
        importlib.reload(document_module)
        importlib.reload(feedback_module)

    # Reload server module
    import src.server as server_module

    importlib.reload(server_module)
    server_module.settings = mock_settings_instance

    # Override lifespan with mock
    server_module.app.router.lifespan_context = mock_lifespan

    return server_module
