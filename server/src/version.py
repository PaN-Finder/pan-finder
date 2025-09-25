import os
from functools import lru_cache

_DEFAULT_VERSION = "dev"


@lru_cache(maxsize=1)
def get_version() -> str:
    """Return the current server version embedded during build."""
    return os.getenv("SERVER_VERSION", _DEFAULT_VERSION)
