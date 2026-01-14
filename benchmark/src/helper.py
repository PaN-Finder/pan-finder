import sys

from paths import benchmark_dir, root_dir
from sentence_transformers import SentenceTransformer

# Make server code importable without modifying server files
server_dir = root_dir() / "server"
sys.path.insert(0, str(server_dir))

# ruff: noqa: E402
from src.config import get_settings
from src.core.ai.llm_client import LLMClient

settings = get_settings()

CACHE_FILE_PATH = benchmark_dir() / "cache" / "llm_cache.json"


def load_system_prompt(model: str, version: str) -> str:
    filepath = benchmark_dir() / "prompts" / model / version
    return filepath.read_text()


def get_sentence_transformer(model: str = "all-MiniLM-L12-v2") -> SentenceTransformer:
    model_path = root_dir() / "models" / model
    return SentenceTransformer(str(model_path), device="cpu")


def get_llm_client(model: str) -> LLMClient:
    """Get or create the LLM client with file caching."""

    # Ensure cache directory exists
    CACHE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    llm_client = LLMClient(
        provider=settings.llm_provider,
        cache_config={
            "cache_type": "file",
            "cache_file": str(CACHE_FILE_PATH),
        },
        default_model=model,
    )
    return llm_client
