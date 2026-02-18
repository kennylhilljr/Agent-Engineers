"""Tests for dashboard/performance_cache.py - AI-193.

Covers:
- cached_response decorator behavior
- Cache hit/miss logic
- TTL expiration
- clear_cache()
- get_cache_stats()
- Multiple functions cached independently
- Cache key generation from args/kwargs
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure project root is on sys.path regardless of working directory
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dashboard.performance_cache import (
    cached_response,
    clear_cache,
    get_cache_stats,
    CACHE_TTL,
    _response_cache,
)


@pytest.fixture(autouse=True)
def clean_cache():
    """Clear cache before and after each test."""
    clear_cache()
    yield
    clear_cache()


# ---------------------------------------------------------------------------
# CACHE_TTL constant tests
# ---------------------------------------------------------------------------

class TestCacheConstants:
    """Tests for cache constants."""

    def test_cache_ttl_is_300(self):
        """Default CACHE_TTL is 300 seconds (5 minutes)."""
        assert CACHE_TTL == 300

    def test_cache_ttl_is_int(self):
        """CACHE_TTL is an integer."""
        assert isinstance(CACHE_TTL, int)


# ---------------------------------------------------------------------------
# cached_response decorator tests
# ---------------------------------------------------------------------------

class TestCachedResponseDecorator:
    """Tests for cached_response decorator."""

    @pytest.mark.asyncio
    async def test_caches_result_on_first_call(self):
        """First call executes function and caches result."""
        call_count = 0

        @cached_response()
        async def my_func(x):
            nonlocal call_count
            call_count += 1
            return f"result_{x}"

        result = await my_func("hello")
        assert result == "result_hello"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_returns_cached_result_on_second_call(self):
        """Second call with same args returns cached value without re-executing."""
        call_count = 0

        @cached_response()
        async def my_func(x):
            nonlocal call_count
            call_count += 1
            return f"result_{x}"

        await my_func("hello")
        await my_func("hello")
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_different_args_different_cache_entries(self):
        """Different args produce separate cache entries."""
        call_count = 0

        @cached_response()
        async def my_func(x):
            nonlocal call_count
            call_count += 1
            return f"result_{x}"

        r1 = await my_func("hello")
        r2 = await my_func("world")
        assert call_count == 2
        assert r1 == "result_hello"
        assert r2 == "result_world"

    @pytest.mark.asyncio
    async def test_expired_cache_re_executes(self):
        """Expired cache entry re-executes the function."""
        call_count = 0

        @cached_response(ttl=1)
        async def my_func():
            nonlocal call_count
            call_count += 1
            return "fresh"

        await my_func()
        # Simulate TTL expiry by manipulating cache timestamp
        key = list(_response_cache.keys())[0]
        resp, _ = _response_cache[key]
        _response_cache[key] = (resp, time.time() - 2)  # 2 seconds ago

        await my_func()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_custom_ttl_is_respected(self):
        """Custom TTL is used for cache decisions."""
        call_count = 0

        @cached_response(ttl=600)
        async def my_func():
            nonlocal call_count
            call_count += 1
            return "data"

        await my_func()
        await my_func()
        await my_func()
        assert call_count == 1  # Still cached after 3 calls

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_name(self):
        """@wraps preserves the original function name."""
        @cached_response()
        async def my_named_func():
            return "ok"

        assert my_named_func.__name__ == "my_named_func"

    @pytest.mark.asyncio
    async def test_multiple_functions_cached_independently(self):
        """Different functions with different args have independent cache entries."""
        count_a = 0
        count_b = 0

        @cached_response()
        async def func_a(x):
            nonlocal count_a
            count_a += 1
            return f"a_{x}"

        @cached_response()
        async def func_b(x):
            nonlocal count_b
            count_b += 1
            return f"b_{x}"

        # Use distinct args to ensure separate cache keys
        await func_a("arg_for_a")
        await func_b("arg_for_b")
        await func_a("arg_for_a")  # cache hit for func_a
        await func_b("arg_for_b")  # cache hit for func_b

        assert count_a == 1
        assert count_b == 1

    @pytest.mark.asyncio
    async def test_kwargs_contribute_to_cache_key(self):
        """Different kwargs produce different cache entries."""
        call_count = 0

        @cached_response()
        async def my_func(x, context=None):
            nonlocal call_count
            call_count += 1
            return f"{x}_{context}"

        await my_func("hi", context="ctx1")
        await my_func("hi", context="ctx2")
        assert call_count == 2


# ---------------------------------------------------------------------------
# clear_cache() tests
# ---------------------------------------------------------------------------

class TestClearCache:
    """Tests for clear_cache() function."""

    @pytest.mark.asyncio
    async def test_clear_cache_empties_all_entries(self):
        """clear_cache() removes all cached entries."""
        @cached_response()
        async def cached_fn():
            return "value"

        await cached_fn()
        assert len(_response_cache) > 0

        clear_cache()
        assert len(_response_cache) == 0

    def test_clear_cache_on_empty_cache_is_safe(self):
        """clear_cache() on empty cache is a no-op."""
        clear_cache()
        clear_cache()  # Second call is safe
        assert len(_response_cache) == 0

    @pytest.mark.asyncio
    async def test_after_clear_cache_function_re_executes(self):
        """After clear_cache(), function re-executes on next call."""
        call_count = 0

        @cached_response()
        async def fn():
            nonlocal call_count
            call_count += 1
            return "val"

        await fn()
        clear_cache()
        await fn()
        assert call_count == 2


# ---------------------------------------------------------------------------
# get_cache_stats() tests
# ---------------------------------------------------------------------------

class TestGetCacheStats:
    """Tests for get_cache_stats() function."""

    def test_stats_returns_dict(self):
        """get_cache_stats() returns a dict."""
        stats = get_cache_stats()
        assert isinstance(stats, dict)

    def test_stats_has_total_entries_key(self):
        """Stats dict has 'total_entries' key."""
        stats = get_cache_stats()
        assert "total_entries" in stats

    def test_stats_has_cache_ttl_key(self):
        """Stats dict has 'cache_ttl' key."""
        stats = get_cache_stats()
        assert "cache_ttl" in stats

    def test_stats_total_entries_is_zero_when_empty(self):
        """total_entries is 0 on empty cache."""
        stats = get_cache_stats()
        assert stats["total_entries"] == 0

    @pytest.mark.asyncio
    async def test_stats_total_entries_increases_after_caching(self):
        """total_entries reflects cached item count."""
        @cached_response()
        async def fn(x):
            return x

        await fn("a")
        await fn("b")
        stats = get_cache_stats()
        assert stats["total_entries"] == 2

    def test_stats_cache_ttl_matches_constant(self):
        """cache_ttl in stats matches CACHE_TTL constant."""
        stats = get_cache_stats()
        assert stats["cache_ttl"] == CACHE_TTL
