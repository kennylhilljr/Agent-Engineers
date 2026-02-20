"""Performance optimization utilities for Agent-Engineers.

Provides caching, connection pooling, and async optimization
utilities to improve I/O performance across the system.
"""

import asyncio
import functools
import hashlib
import json
import time
from typing import Any, Callable, Optional, TypeVar
from collections import OrderedDict


F = TypeVar("F", bound=Callable[..., Any])


class LRUCache:
    """Thread-safe LRU cache with TTL support.

    Example:
        >>> cache = LRUCache(maxsize=100, ttl=300)
        >>> cache.set("key", "value")
        >>> cache.get("key")
        'value'
    """

    def __init__(self, maxsize: int = 128, ttl: Optional[float] = None) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, returning None if expired or missing."""
        if key not in self._cache:
            return None
        value, timestamp = self._cache[key]
        if self._ttl is not None and time.monotonic() - timestamp > self._ttl:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        """Set value in cache, evicting oldest if at capacity."""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, time.monotonic())
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def invalidate(self, key: str) -> bool:
        """Remove a key from cache. Returns True if it existed."""
        return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()

    def size(self) -> int:
        """Return number of items currently in cache."""
        return len(self._cache)

    @property
    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        return {"size": self.size(), "maxsize": self._maxsize, "ttl": self._ttl}


def cache_result(ttl: Optional[float] = None, maxsize: int = 128) -> Callable[[F], F]:
    """Decorator to cache function results with optional TTL.

    Args:
        ttl: Cache TTL in seconds (None = no expiry)
        maxsize: Maximum cache size

    Returns:
        Decorated function with caching

    Example:
        >>> @cache_result(ttl=60)
        ... def get_user(user_id: str) -> dict:
        ...     return {"id": user_id}
    """
    def decorator(func: F) -> F:
        cache = LRUCache(maxsize=maxsize, ttl=ttl)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = hashlib.md5(
                json.dumps((args, sorted(kwargs.items())), default=str).encode()
            ).hexdigest()
            cached = cache.get(key)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        wrapper._cache = cache  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


class AsyncConnectionPool:
    """Simple async connection pool for subprocess/HTTP connections.

    Manages a pool of reusable connections to avoid repeated
    connection setup overhead.

    Example:
        >>> pool = AsyncConnectionPool(max_size=5)
        >>> async with pool.acquire() as conn:
        ...     result = await conn.execute("command")
    """

    def __init__(self, max_size: int = 10, timeout: float = 30.0) -> None:
        self._max_size = max_size
        self._timeout = timeout
        self._available: asyncio.Queue[Any] = asyncio.Queue(maxsize=max_size)
        self._size = 0

    async def acquire(self) -> Any:
        """Acquire a connection from the pool."""
        try:
            return await asyncio.wait_for(
                self._available.get(), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Connection pool exhausted after {self._timeout}s")

    async def release(self, connection: Any) -> None:
        """Return a connection to the pool."""
        await self._available.put(connection)

    @property
    def size(self) -> int:
        """Current pool size."""
        return self._size


class TokenCache:
    """Cache for API authentication tokens with expiry.

    Example:
        >>> cache = TokenCache()
        >>> cache.store("openai", "sk-...", expires_in=3600)
        >>> cache.get("openai")
        'sk-...'
    """

    def __init__(self) -> None:
        self._tokens: dict[str, tuple[str, float]] = {}

    def store(self, provider: str, token: str, expires_in: float = 3600.0) -> None:
        """Store a token with its expiry time."""
        self._tokens[provider] = (token, time.monotonic() + expires_in)

    def get(self, provider: str) -> Optional[str]:
        """Get a token if it hasn't expired."""
        if provider not in self._tokens:
            return None
        token, expires_at = self._tokens[provider]
        if time.monotonic() > expires_at:
            del self._tokens[provider]
            return None
        return token

    def invalidate(self, provider: str) -> None:
        """Invalidate a cached token."""
        self._tokens.pop(provider, None)

    def clear(self) -> None:
        """Clear all cached tokens."""
        self._tokens.clear()


# Global instances
_api_cache = LRUCache(maxsize=256, ttl=300)
_token_cache = TokenCache()


def get_api_cache() -> LRUCache:
    """Get the global API response cache."""
    return _api_cache


def get_token_cache() -> TokenCache:
    """Get the global token cache."""
    return _token_cache
