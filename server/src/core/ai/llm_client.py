"""
LLM Client with Caching Support

This module provides a unified interface for Large Language Model interactions
with built-in caching, retry logic, and support for multiple providers.
"""

import json
import hashlib
import time
import asyncio
from typing import Optional, Dict, List, Any, AsyncGenerator, Union, Callable
from dataclasses import dataclass
from openai import AzureOpenAI
from logging import Logger

from .cache_interface import CacheInterface, create_cache
from ...utils import get_logger
from ...config import get_settings

settings = get_settings()


@dataclass
class LLMMessage:
    """Represents a single message in a conversation."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMCompletionRequest:
    """Request configuration for LLM completion."""

    messages: List[LLMMessage]
    model: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: float = 0.3
    stream: bool = False
    response_format: Optional[Dict[str, str]] = None
    cache_metadata: Optional[Dict[str, Any]] = None  # For storing additional metadata


@dataclass
class LLMCompletionResponse:
    """Response from LLM completion."""

    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    cached: bool = False
    response_time_ms: int = 0


class LLMClient:
    """
    Unified LLM client with caching and retry logic.

    Features:
    - Automatic caching of responses (memory, file, or hybrid)
    - Retry logic with exponential backoff
    - Streaming and non-streaming completions
    - Cache key generation and management
    - Comprehensive logging
    """

    def __init__(
        self,
        provider: str = "azure_openai",
        cache: Optional[CacheInterface] = None,
        cache_config: Optional[Dict[str, Any]] = None,
        default_model: Optional[str] = None,
        logger: Optional[Logger] = None,
        **provider_kwargs,
    ):
        """
        Initialize LLM client.

        Args:
            provider: LLM provider ("azure_openai", "openai", etc.)
            cache: Cache instance (creates default if None)
            cache_config: Configuration for cache creation
            default_model: Default model to use
            logger: Optional logger instance
            **provider_kwargs: Provider-specific configuration
        """
        self._provider = provider
        self._logger = logger or get_logger(self.__class__.__name__)
        self._default_model = default_model or self._get_default_model()

        # Initialize cache
        if cache is not None:
            self._cache = cache
        else:
            cache_config = cache_config or {}
            self._cache = create_cache(**cache_config)

        # Initialize provider client
        self._client = self._create_client(**provider_kwargs)

    def _get_default_model(self) -> str:
        """Get default model based on provider and settings."""
        if self._provider == "azure_openai":
            return settings.azure_openai_model_name
        return "gpt-3.5-turbo"  # Fallback

    def _create_client(self, **kwargs) -> Any:
        """Create provider-specific client."""
        if self._provider == "azure_openai":
            return AzureOpenAI(
                api_key=kwargs.get("api_key") or settings.azure_openai_api_key,
                azure_endpoint=kwargs.get("azure_endpoint")
                or settings.azure_openai_endpoint,
                api_version=kwargs.get("api_version")
                or settings.azure_openai_api_version,
            )
        else:
            raise ValueError(f"Unsupported provider: {self._provider}")

    def _generate_cache_key(self, request: LLMCompletionRequest) -> str:
        """Generate a unique cache key for the request."""
        # Create a hash of the key components
        key_data = {
            "model": request.model or self._default_model,
            "messages": [
                {"role": msg.role, "content": msg.content} for msg in request.messages
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "response_format": request.response_format,
        }

        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode("utf-8")).hexdigest()

    async def complete(self, request: LLMCompletionRequest) -> LLMCompletionResponse:
        """
        Perform non-streaming LLM completion with caching.

        Args:
            request: Completion request configuration

        Returns:
            LLMCompletionResponse
        """
        if request.stream:
            raise ValueError("Use complete_stream() for streaming requests")

        start_time = time.time()

        model = request.model or self._default_model
        cache_key = self._generate_cache_key(request)

        # Check cache
        cached_response = self._cache.get(cache_key)
        if cached_response is not None:
            self._logger.debug(f"Cache hit for model '{model}'")

            try:
                cached_data = json.loads(cached_response)
                response_time = int((time.time() - start_time) * 1000)
                return LLMCompletionResponse(
                    content=cached_data["content"],
                    model=cached_data["model"],
                    usage=cached_data.get("usage"),
                    cached=True,
                    response_time_ms=response_time,
                )
            except json.JSONDecodeError:
                self._logger.warning("Invalid cached response format, ignoring cache")

        # Cache miss - call provider
        self._logger.debug(f"Cache miss for model '{model}', calling provider")

        try:
            return await self._non_stream_completion(request, cache_key, start_time)
        except Exception as e:
            self._logger.error(f"LLM completion failed: {e}")
            raise

    async def complete_stream(
        self, request: LLMCompletionRequest
    ) -> AsyncGenerator[str, None]:
        """
        Perform streaming LLM completion with caching.

        Args:
            request: Completion request configuration

        Yields:
            Streaming content chunks
        """
        start_time = time.time()
        cache_key = self._generate_cache_key(request)

        # Check cache first
        cached_response = self._cache.get(cache_key)
        if cached_response is not None:
            self._logger.debug("Cache hit for streaming request")

            try:
                cached_data = json.loads(cached_response)
                content = cached_data["content"]

                # Stream the cached content in chunks (simulate streaming)
                chunk_size = 50  # characters per chunk
                for i in range(0, len(content), chunk_size):
                    chunk = content[i : i + chunk_size]
                    yield chunk
                    # Small delay to simulate streaming behavior
                    await asyncio.sleep(0.01)
                return

            except json.JSONDecodeError:
                self._logger.warning(
                    "Invalid cached response format for streaming, ignoring cache"
                )

        # Cache miss - call provider for streaming
        self._logger.debug("Cache miss for streaming request, calling provider")

        try:
            async for chunk in self._stream_completion(request, cache_key, start_time):
                yield chunk
        except Exception as e:
            self._logger.error(f"LLM streaming completion failed: {e}")
            raise

    async def _non_stream_completion(
        self, request: LLMCompletionRequest, cache_key: str, start_time: float
    ) -> LLMCompletionResponse:
        """Handle non-streaming completion."""
        model = request.model or self._default_model

        # Prepare messages for provider
        messages = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]

        # Call provider with retry logic
        response = await self._call_with_retry(
            lambda: self._client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                response_format=request.response_format or None,
                stream=False,
            )
        )

        if not response or not response.choices:
            raise RuntimeError("Empty response from LLM provider")

        content = response.choices[0].message.content or ""
        usage = None
        if response.usage:
            usage = {
                "completion_tokens": response.usage.completion_tokens,
                "prompt_tokens": response.usage.prompt_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        # Cache the response
        response_data = {
            "content": content,
            "model": model,
            "usage": usage,
            "created_at": time.time(),
        }

        self._cache.put(cache_key, json.dumps(response_data), request.cache_metadata)

        response_time = int((time.time() - start_time) * 1000)
        return LLMCompletionResponse(
            content=content,
            model=model,
            usage=usage,
            cached=False,
            response_time_ms=response_time,
        )

    async def _stream_completion(
        self, request: LLMCompletionRequest, cache_key: str, start_time: float
    ) -> AsyncGenerator[str, None]:
        """Handle streaming completion."""
        model = request.model or self._default_model
        messages = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]

        # Call provider for streaming
        stream = await self._call_with_retry(
            lambda: self._client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                response_format=request.response_format or None,
                stream=True,
            )
        )

        if not stream:
            raise RuntimeError("Failed to create streaming response")

        # Collect content for caching while streaming
        collected_content = ""

        try:
            for chunk in stream:
                if hasattr(chunk, "choices") and len(chunk.choices) > 0:
                    content = getattr(chunk.choices[0].delta, "content", "")
                    if content:
                        collected_content += content
                        yield content
                else:
                    self._logger.warning(f"Unexpected chunk format: {chunk}")

        except Exception as e:
            self._logger.error(f"Streaming error: {e}")
            if not collected_content:
                raise

        # Cache the complete response
        if collected_content:
            response_data = {
                "content": collected_content,
                "model": model,
                "usage": None,  # Usage not available in streaming
                "created_at": time.time(),
            }

            self._cache.put(
                cache_key, json.dumps(response_data), request.cache_metadata
            )

    async def _call_with_retry(
        self, func: Callable, max_attempts: int = 3, base_backoff: float = 1.0
    ) -> Any:
        """Call function with exponential backoff retry."""
        last_exception = None

        for attempt in range(max_attempts):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    backoff = base_backoff * (2**attempt)
                    self._logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                        f"Retrying in {backoff}s..."
                    )
                    time.sleep(backoff)
                else:
                    self._logger.error(f"All {max_attempts} attempts failed")

        if last_exception is not None:
            raise last_exception
        else:
            raise RuntimeError("Retry logic failed without exception")

    def create_request(
        self, messages: Union[List[LLMMessage], List[Dict[str, str]]], **kwargs
    ) -> LLMCompletionRequest:
        """
        Convenience method to create completion request.

        Args:
            messages: List of messages (LLMMessage objects or dicts)
            **kwargs: Additional request parameters

        Returns:
            LLMCompletionRequest object
        """
        # Convert dict messages to LLMMessage objects if needed
        converted_messages: List[LLMMessage] = []

        for msg in messages:
            if isinstance(msg, LLMMessage):
                converted_messages.append(msg)
            elif isinstance(msg, dict):
                converted_messages.append(
                    LLMMessage(role=msg["role"], content=msg["content"])
                )
            else:
                raise ValueError(f"Invalid message type: {type(msg)}")

        return LLMCompletionRequest(messages=converted_messages, **kwargs)

    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._logger.info("LLM cache cleared")


# Convenience factory functions
def create_llm_client(
    provider: str = "azure_openai", cache_type: str = "hybrid", **kwargs
) -> LLMClient:
    """
    Factory function to create LLM client with common configurations.

    Args:
        provider: LLM provider
        cache_type: Cache type ("memory", "file", "hybrid")
        **kwargs: Additional arguments

    Returns:
        Configured LLMClient instance
    """
    cache_config = kwargs.pop("cache_config", {})
    cache_config["cache_type"] = cache_type

    cache = create_cache(**cache_config)

    return LLMClient(provider=provider, cache=cache, **kwargs)


def create_azure_openai_client(**kwargs) -> LLMClient:
    """Create Azure OpenAI client with default configuration."""
    return create_llm_client(
        provider="azure_openai",
        default_model=settings.azure_openai_model_name,
        **kwargs,
    )
