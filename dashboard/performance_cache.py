"""Performance optimization utilities for provider bridges."""
import asyncio
import time
from functools import wraps
from typing import Any, Dict, Optional, Callable

_response_cache: Dict[str, tuple] = {}  # key -> (response, timestamp)
CACHE_TTL = 300  # 5 minutes


def cached_response(ttl: int = CACHE_TTL):
    """Decorator to cache provider responses."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = str(args) + str(sorted(kwargs.items()))
            if cache_key in _response_cache:
                resp, ts = _response_cache[cache_key]
                if time.time() - ts < ttl:
                    return resp
            result = await func(*args, **kwargs)
            _response_cache[cache_key] = (result, time.time())
            return result
        return wrapper
    return decorator


def clear_cache():
    """Clear all cached responses."""
    _response_cache.clear()


def get_cache_stats() -> Dict[str, Any]:
    """Return cache statistics."""
    return {
        "total_entries": len(_response_cache),
        "cache_ttl": CACHE_TTL,
    }
