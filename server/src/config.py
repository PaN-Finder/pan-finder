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
        self.embedding_model_path = os.getenv(
            "EMBEDDING_MODEL_PATH", "/code/models/all-MiniLM-L12-v2"
        )
        self.database_url = self._get_database_url()

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
