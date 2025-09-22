"""
Cache Interface and Implementations

This module provides a unified interface for caching LLM responses with multiple backend options:
- Memory cache (in-memory storage with size limits)
- File cache (persistent disk storage)
- Hybrid cache (memory + file fallback)
"""

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, Union
from logging import Logger
from ...utils import get_logger


class CacheInterface(ABC):
    """Abstract interface for LLM response caching."""

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """Retrieve a cached response."""
        pass

    @abstractmethod
    def put(
        self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store a response in cache."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached entries."""
        pass

    @abstractmethod
    def size(self) -> int:
        """Get the number of cached entries."""
        pass


class MemoryCache(CacheInterface):
    """In-memory cache with LRU eviction and size limits."""

    def __init__(
        self,
        max_entries: int = 1000,
        max_memory_mb: int = 100,
        logger: Optional[Logger] = None,
    ):
        """
        Initialize memory cache.

        Args:
            max_entries: Maximum number of cache entries
            max_memory_mb: Maximum memory usage in MB
            logger: Optional logger instance
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_order: Dict[str, float] = {}  # key -> timestamp
        self._max_entries = max_entries
        self._max_memory_bytes = max_memory_mb * 1024 * 1024
        self._current_memory_bytes = 0
        self._logger = logger or get_logger(self.__class__.__name__)

    def get(self, key: str) -> Optional[str]:
        """Retrieve cached response and update access time."""
        if key in self._cache:
            self._access_order[key] = time.time()
            self._logger.debug(f"Memory cache hit for key: {key[:20]}...")
            return self._cache[key]["response"]
        return None

    def put(
        self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store response in memory cache with LRU eviction."""
        entry_size = len(key.encode("utf-8")) + len(value.encode("utf-8"))
        if metadata:
            entry_size += len(json.dumps(metadata).encode("utf-8"))

        # Check if single entry would exceed memory limit
        if entry_size > self._max_memory_bytes:
            self._logger.warning(
                f"Entry too large for memory cache: {entry_size} bytes"
            )
            return False

        # Evict entries if needed
        while (
            len(self._cache) >= self._max_entries
            or self._current_memory_bytes + entry_size > self._max_memory_bytes
        ):
            if not self._evict_lru():
                break

        # Store the entry
        self._cache[key] = {
            "response": value,
            "metadata": metadata or {},
            "size": entry_size,
            "created_at": time.time(),
        }
        self._access_order[key] = time.time()
        self._current_memory_bytes += entry_size

        self._logger.debug(
            f"Stored in memory cache. Size: {len(self._cache)}/{self._max_entries}, "
            f"Memory: {self._current_memory_bytes / 1024 / 1024:.1f}MB"
        )
        return True

    def _evict_lru(self) -> bool:
        """Evict least recently used entry."""
        if not self._access_order:
            return False

        # Find LRU key
        lru_key = min(self._access_order.keys(), key=lambda k: self._access_order[k])

        # Remove entry
        if lru_key in self._cache:
            entry_size = self._cache[lru_key]["size"]
            del self._cache[lru_key]
            del self._access_order[lru_key]
            self._current_memory_bytes -= entry_size
            self._logger.debug(f"Evicted LRU entry: {lru_key[:20]}...")
            return True
        return False

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._access_order.clear()
        self._current_memory_bytes = 0
        self._logger.info("Memory cache cleared")

    def size(self) -> int:
        """Get number of cached entries."""
        return len(self._cache)


class FileCache(CacheInterface):
    """File-based persistent cache with single JSON file storage."""

    def __init__(
        self,
        cache_file: Union[str, Path] = "./llm_cache.json",
        logger: Optional[Logger] = None,
    ):
        """
        Initialize file cache.

        Args:
            cache_file: Path to the cache file
            logger: Optional logger instance
        """
        self._cache_file = Path(cache_file)
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._logger = logger or get_logger(self.__class__.__name__)

        # In-memory cache for performance
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from disk."""
        try:
            if self._cache_file.exists():
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._cache = data.get("entries", {})

                    self._logger.debug(
                        f"Loaded {len(self._cache)} entries from cache file"
                    )
            else:
                self._cache = {}
                self._logger.debug(
                    "No existing cache file found, starting with empty cache"
                )
        except Exception as e:
            self._logger.warning(f"Failed to load cache from {self._cache_file}: {e}")
            self._cache = {}

    def _save_cache(self) -> None:
        """Save cache to disk."""
        try:
            data = {"version": "1.0", "entries": self._cache}

            # Write to temporary file first, then rename for atomic operation
            temp_file = self._cache_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            temp_file.replace(self._cache_file)
            self._logger.debug(f"Saved {len(self._cache)} entries to cache file")
        except Exception as e:
            self._logger.error(f"Failed to save cache to {self._cache_file}: {e}")

    def get(self, key: str) -> Optional[str]:
        """Retrieve cached response from file."""
        entry = self._cache.get(key)
        if entry is None:
            return None

        self._logger.debug(f"File cache hit for key: {key[:20]}...")
        return entry.get("response")

    def put(
        self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store response in file cache."""
        try:
            # Store the entry
            self._cache[key] = {
                "response": value,
                "metadata": metadata or {},
            }

            # Save to disk
            self._save_cache()
            self._logger.debug(f"Stored entry in file cache: {key[:20]}...")
            return True

        except Exception as e:
            self._logger.error(f"Failed to store entry in cache: {e}")
            return False

    def clear(self) -> None:
        """Clear all cached entries."""
        try:
            self._cache.clear()
            if self._cache_file.exists():
                self._cache_file.unlink()
            self._logger.info("File cache cleared")
        except Exception as e:
            self._logger.error(f"Failed to clear file cache: {e}")

    def size(self) -> int:
        """Get number of cached entries."""
        return len(self._cache)


class HybridCache(CacheInterface):
    """Hybrid cache that uses memory cache with file cache fallback."""

    def __init__(
        self,
        memory_cache: Optional[MemoryCache] = None,
        file_cache: Optional[FileCache] = None,
        logger: Optional[Logger] = None,
    ):
        """
        Initialize hybrid cache.

        Args:
            memory_cache: Memory cache instance (creates default if None)
            file_cache: File cache instance (creates default if None)
            logger: Optional logger instance
        """
        self._memory = memory_cache or MemoryCache()
        self._file = file_cache or FileCache()
        self._logger = logger or get_logger(self.__class__.__name__)

    def get(self, key: str) -> Optional[str]:
        """Try memory cache first, then file cache."""
        # Try memory first
        result = self._memory.get(key)
        if result is not None:
            return result

        # Try file cache
        result = self._file.get(key)
        if result is not None:
            # Promote to memory cache
            self._memory.put(key, result)
            self._logger.debug(f"Promoted file cache hit to memory: {key[:20]}...")

        return result

    def put(
        self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store in both memory and file cache."""
        memory_success = self._memory.put(key, value, metadata)
        file_success = self._file.put(key, value, metadata)

        # Consider successful if at least one cache succeeded
        return memory_success or file_success

    def clear(self) -> None:
        """Clear both caches."""
        self._memory.clear()
        self._file.clear()
        self._logger.info("Hybrid cache cleared")

    def size(self) -> int:
        """Get combined size (memory + unique file entries)."""
        return self._memory.size() + self._file.size()


def create_cache(
    cache_type: str = "hybrid",
    cache_file: Optional[str] = None,
    max_memory_mb: int = 100,
    **kwargs,
) -> CacheInterface:
    """
    Factory function to create cache instances.

    Args:
        cache_type: Type of cache ("memory", "file", "hybrid")
        cache_file: Path to cache file for file cache
        max_memory_mb: Memory limit for memory cache
        **kwargs: Additional arguments passed to cache constructors

    Returns:
        Cache instance
    """
    logger = get_logger("CacheFactory")

    if cache_type == "memory":
        return MemoryCache(max_memory_mb=max_memory_mb, **kwargs)
    elif cache_type == "file":
        return FileCache(
            cache_file=cache_file or "./llm_cache.json",
            **kwargs,
        )
    elif cache_type == "hybrid":
        memory = MemoryCache(max_memory_mb=max_memory_mb, **kwargs)
        file_cache = FileCache(
            cache_file=cache_file or "./llm_cache.json",
            **kwargs,
        )
        return HybridCache(memory, file_cache, logger=logger)
    else:
        raise ValueError(f"Unknown cache type: {cache_type}")
