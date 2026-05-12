import os
from functools import lru_cache
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


DEFAULT_VALUE_VECTOR_KEYS: tuple[str, ...] = (
    "authors",
    "creator",
    "scientificMetadata.author",
    "owner",
    "metadata.authors.name",
    "principalInvestigator",
    "investigator",
    "scientificMetadata.measurement.team",
    "users.fullName",
    "attributes.creators.name",
)


class Settings:
    """Configuration settings loaded from environment variables or .env file."""

    def __init__(self):
        self.allowed_origins = self._parse_cors_origins()

        # LLM provider selection
        # Supported values: "azure", "openai"
        provider = os.getenv("LLM_PROVIDER", "azure").strip().lower()
        if provider not in {"azure", "openai"}:
            raise ValueError("LLM_PROVIDER must be one of: azure, openai")
        self.llm_provider = provider

        # Azure OpenAI configuration (required only when llm_provider == "azure")
        self.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
        self.azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
        self.azure_openai_api_version = os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-12-01-preview"
        )

        # OpenAI configuration (required only when llm_provider == "openai")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "").strip()

        self.default_model_name = os.getenv("DEFAULT_MODEL_NAME", "gpt-4.1-mini")
        self.explanation_model_name = os.getenv("EXPLANATION_MODEL_NAME", "gpt-4.1")

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

        # Cloudflare Turnstile
        self.enable_turnstile = os.getenv("ENABLE_TURNSTILE", "false").lower() == "true"
        if self.enable_turnstile:
            self.turnstile_secret_key = self._get_required_env("TURNSTILE_SECRET_KEY")

        # RRF (Reciprocal Rank Fusion) configuration
        self.rrf_k_document = int(os.getenv("RRF_K_DOCUMENT", "6"))
        self.rrf_k_chunk = int(os.getenv("RRF_K_CHUNK", "6"))
        self.rrf_k_conditions_full = int(os.getenv("RRF_K_CONDITIONS_FULL", "6"))
        self.rrf_k_conditions_partial = int(os.getenv("RRF_K_CONDITIONS_PARTIAL", "6"))
        self.rrf_k_keywords = int(os.getenv("RRF_K_KEYWORDS", "10"))
        self.value_vector_keys = self._parse_csv_env(
            "VALUE_VECTOR_KEYS", DEFAULT_VALUE_VECTOR_KEYS
        )

    def _parse_cors_origins(self) -> list[str]:
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
            raise ValueError("Invalid DATABASE_URL format") from None

        return url

    def _parse_csv_env(
        self, key: str, default: tuple[str, ...] | list[str]
    ) -> tuple[str, ...]:
        """Parse a comma-separated environment variable into a deduplicated tuple."""
        raw_value = os.getenv(key, "").strip()
        values = raw_value.split(",") if raw_value else list(default)

        parsed_values: list[str] = []
        seen_values: set[str] = set()
        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_values:
                continue
            seen_values.add(normalized_value)
            parsed_values.append(normalized_value)

        return tuple(parsed_values)


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
