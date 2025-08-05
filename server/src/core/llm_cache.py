"""
LLM Response Cache Helper

This module provides a cache implementation for storing and managing LLM responses
to avoid redundant API calls and improve performance.
"""

import hashlib
from typing import Optional, Dict
from logging import Logger
from ..setup_logging import get_logger


class LLMResponseCache:
    """
    A cache for storing LLM responses with size management and eviction policies.

    This class provides efficient caching of LLM responses keyed by model name and query,
    with automatic size management to prevent excessive memory usage.
    """

    def __init__(
        self,
        max_size: int = 1000,
        max_query_length: int = 10000,
        logger: Optional[Logger] = None,
    ):
        """
        Initialize the LLM response cache.

        Args:
            max_size: Maximum number of cached responses
            max_query_length: Maximum query length to cache (in characters)
            logger: Optional logger instance for debugging
        """
        self._cache: Dict[str, str] = {}
        self._max_size = max_size
        self._max_query_length = max_query_length
        self._logger = logger or get_logger(self.__class__.__name__)

    def _get_cache_key(self, model: str, query: str) -> str:
        """
        Generate a hash-based cache key from model and query.

        Args:
            model: The model name
            query: The query string

        Returns:
            SHA-256 hash of the model and query combination
        """
        # Combine model and query with a separator
        combined = f"{model}|{query}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def get(self, model: str, query: str) -> Optional[str]:
        """
        Retrieve a cached response for the given model and query.

        Args:
            model: The model name used for the original request
            query: The query string

        Returns:
            Cached response if found, None otherwise
        """
        if len(query) > self._max_query_length:
            return None

        cache_key = self._get_cache_key(model, query)
        cached_response = self._cache.get(cache_key)

        if cached_response is not None:
            self._logger.debug(
                f"Cache hit for model '{model}' and query: {query[:100]}..."
            )

        return cached_response

    def put(self, model: str, query: str, response: str) -> bool:
        """
        Store a response in the cache.

        Args:
            model: The model name used for the request
            query: The query string
            response: The response to cache

        Returns:
            True if the response was cached, False if it was rejected
        """
        # Don't cache queries that are too long
        if len(query) > self._max_query_length:
            self._logger.debug(f"Query too long to cache (length: {len(query)})")
            return False

        # Check if we need to evict old entries
        if len(self._cache) >= self._max_size:
            self._evict_oldest_entries()

        # Cache the response
        cache_key = self._get_cache_key(model, query)
        self._cache[cache_key] = response

        self._logger.debug(
            f"Cached response for model '{model}'. "
            f"Cache size: {len(self._cache)}/{self._max_size}"
        )
        return True

    def _evict_oldest_entries(self) -> None:
        """
        Evict oldest entries when cache is full.
        This removes 20% of the cache entries to make room for new ones.
        """
        if not self._cache:
            return

        # Calculate how many entries to remove (20% of max size, minimum 1)
        entries_to_remove = max(1, self._max_size // 5)

        # Get the keys and remove the first N entries (oldest in insertion order)
        keys_to_remove = list(self._cache.keys())[:entries_to_remove]

        for key in keys_to_remove:
            del self._cache[key]

        self._logger.debug(
            f"Evicted {len(keys_to_remove)} old cache entries. "
            f"Cache size now: {len(self._cache)}"
        )
