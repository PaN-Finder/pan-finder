import os
from functools import lru_cache
from typing import List
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Configuration settings loaded from environment variables or .env file."""

    def __init__(self):
        self.allowed_origins = self._parse_cors_origins()
        self.azure_openai_endpoint = self._get_required_env("AZURE_OPENAI_ENDPOINT")
        self.azure_openai_api_key = self._get_required_env("AZURE_OPENAI_API_KEY")
        self.azure_openai_api_version = os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-12-01-preview"
        )
        self.azure_openai_model_name = os.getenv(
            "AZURE_OPENAI_MODEL_NAME", "gpt-4.1-mini"
        )
        self.embedding_model_path = os.getenv(
            "EMBEDDING_MODEL_PATH", "/code/models/all-MiniLM-L12-v2"
        )
        self.database_url = self._get_database_url()
        self.api_host = os.getenv("API_HOST", "0.0.0.0")
        self.api_port = int(os.getenv("API_PORT", "8080"))

        # Database connection settings
        self.db_pool_min_size = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
        self.db_pool_max_size = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
        self.db_connection_timeout = int(os.getenv("DB_CONNECTION_TIMEOUT", "30"))
        self.db_max_idle = int(os.getenv("DB_MAX_IDLE", "300"))  # 5 minutes
        self.db_max_lifetime = int(os.getenv("DB_MAX_LIFETIME", "3600"))  # 1 hour

    def _parse_cors_origins(self) -> List[str]:
        """Parse CORS origins from environment variable."""
        origins_str = os.getenv("ALLOWED_ORIGINS", "*")
        if origins_str == "*":
            return ["*"]
        return [origin.strip() for origin in origins_str.split(",") if origin.strip()]

    def _get_required_env(self, key: str) -> str:
        """Get required environment variable with validation."""
        value = os.getenv(key, "").strip()
        if not value:
            raise ValueError(f"{key} environment variable is required")
        return value

    def _get_database_url(self) -> str:
        """Get database URL with validation."""
        url = os.getenv("DATABASE_URL", "")
        if not url:
            raise ValueError("DATABASE_URL environment variable is required")

        # Basic URL validation
        try:
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValueError("Invalid DATABASE_URL format")
        except Exception:
            raise ValueError("Invalid DATABASE_URL format")

        return url


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
