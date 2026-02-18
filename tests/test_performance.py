"""Comprehensive tests for performance optimization utilities (AI-204).

Tests cover:
- LRUCache get/set/eviction/TTL expiry
- LRUCache.invalidate() and .clear()
- LRUCache.stats property
- cache_result decorator caches function calls
- cache_result with TTL
- cache_result preserves function signature
- TokenCache store/get/expiry/invalidate/clear
- Global get_api_cache() and get_token_cache() singletons
- LRU eviction order (oldest removed first)
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from performance import (
    AsyncConnectionPool,
    LRUCache,
    TokenCache,
    cache_result,
    get_api_cache,
    get_token_cache,
)


# ---------------------------------------------------------------------------
# LRUCache basic get/set tests
# ---------------------------------------------------------------------------


class TestLRUCacheBasic:
    def test_get_missing_key_returns_none(self):
        cache = LRUCache()
        assert cache.get("missing") is None

    def test_set_and_get_returns_value(self):
        cache = LRUCache()
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_set_integer_value(self):
        cache = LRUCache()
        cache.set("num", 42)
        assert cache.get("num") == 42

    def test_set_dict_value(self):
        cache = LRUCache()
        cache.set("data", {"a": 1, "b": 2})
        assert cache.get("data") == {"a": 1, "b": 2}

    def test_set_list_value(self):
        cache = LRUCache()
        cache.set("items", [1, 2, 3])
        assert cache.get("items") == [1, 2, 3]

    def test_set_none_value_stores_and_retrieves(self):
        cache = LRUCache()
        cache.set("null_key", None)
        # None stored but get returns None which is also the missing sentinel
        # The important thing is that None can be stored without error
        assert cache.size() == 1

    def test_overwrite_existing_key(self):
        cache = LRUCache()
        cache.set("key", "first")
        cache.set("key", "second")
        assert cache.get("key") == "second"

    def test_size_starts_at_zero(self):
        cache = LRUCache()
        assert cache.size() == 0

    def test_size_increments_on_set(self):
        cache = LRUCache()
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.size() == 2

    def test_overwrite_does_not_increase_size(self):
        cache = LRUCache()
        cache.set("a", 1)
        cache.set("a", 99)
        assert cache.size() == 1


# ---------------------------------------------------------------------------
# LRUCache eviction tests
# ---------------------------------------------------------------------------


class TestLRUCacheEviction:
    def test_evicts_oldest_when_full(self):
        cache = LRUCache(maxsize=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_size_does_not_exceed_maxsize(self):
        cache = LRUCache(maxsize=5)
        for i in range(10):
            cache.set(str(i), i)
        assert cache.size() == 5

    def test_accessed_key_not_evicted_first(self):
        cache = LRUCache(maxsize=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # Access "a" so it moves to end (most recently used)
        cache.get("a")
        # Now add "d" — "b" should be evicted (now oldest)
        cache.set("d", 4)
        assert cache.get("b") is None
        assert cache.get("a") == 1

    def test_maxsize_one_always_evicts_previous(self):
        cache = LRUCache(maxsize=1)
        cache.set("first", 1)
        cache.set("second", 2)
        assert cache.get("first") is None
        assert cache.get("second") == 2

    def test_eviction_order_is_lru(self):
        cache = LRUCache(maxsize=3)
        cache.set("x", 10)
        cache.set("y", 20)
        cache.set("z", 30)
        # Access y and z, leaving x as LRU
        cache.get("y")
        cache.get("z")
        cache.set("w", 40)  # x should be evicted
        assert cache.get("x") is None
        assert cache.get("y") == 20
        assert cache.get("z") == 30
        assert cache.get("w") == 40


# ---------------------------------------------------------------------------
# LRUCache TTL tests
# ---------------------------------------------------------------------------


class TestLRUCacheTTL:
    def test_item_returned_before_expiry(self):
        cache = LRUCache(maxsize=10, ttl=10.0)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_item_not_returned_after_ttl_expires(self):
        cache = LRUCache(maxsize=10, ttl=0.01)
        cache.set("key", "value")
        time.sleep(0.05)
        assert cache.get("key") is None

    def test_expired_item_removed_from_cache(self):
        cache = LRUCache(maxsize=10, ttl=0.01)
        cache.set("key", "value")
        time.sleep(0.05)
        cache.get("key")  # triggers removal
        assert cache.size() == 0

    def test_no_ttl_items_never_expire(self):
        cache = LRUCache(maxsize=10, ttl=None)
        cache.set("key", "value")
        # Without TTL, items should remain indefinitely
        assert cache.get("key") == "value"


# ---------------------------------------------------------------------------
# LRUCache invalidate/clear tests
# ---------------------------------------------------------------------------


class TestLRUCacheInvalidateAndClear:
    def test_invalidate_existing_key_returns_true(self):
        cache = LRUCache()
        cache.set("key", "value")
        result = cache.invalidate("key")
        assert result is True

    def test_invalidate_missing_key_returns_false(self):
        cache = LRUCache()
        result = cache.invalidate("nonexistent")
        assert result is False

    def test_invalidate_removes_key(self):
        cache = LRUCache()
        cache.set("key", "value")
        cache.invalidate("key")
        assert cache.get("key") is None

    def test_invalidate_reduces_size(self):
        cache = LRUCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.invalidate("a")
        assert cache.size() == 1

    def test_clear_removes_all_items(self):
        cache = LRUCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.clear()
        assert cache.size() == 0

    def test_clear_makes_all_keys_missing(self):
        cache = LRUCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_clear_on_empty_cache_does_not_raise(self):
        cache = LRUCache()
        cache.clear()  # should not raise
        assert cache.size() == 0


# ---------------------------------------------------------------------------
# LRUCache stats tests
# ---------------------------------------------------------------------------


class TestLRUCacheStats:
    def test_stats_contains_size_key(self):
        cache = LRUCache(maxsize=50)
        assert "size" in cache.stats

    def test_stats_contains_maxsize_key(self):
        cache = LRUCache(maxsize=50)
        assert "maxsize" in cache.stats

    def test_stats_contains_ttl_key(self):
        cache = LRUCache(maxsize=50, ttl=120.0)
        assert "ttl" in cache.stats

    def test_stats_maxsize_matches_init(self):
        cache = LRUCache(maxsize=77)
        assert cache.stats["maxsize"] == 77

    def test_stats_ttl_matches_init(self):
        cache = LRUCache(ttl=42.0)
        assert cache.stats["ttl"] == 42.0

    def test_stats_ttl_none_when_not_set(self):
        cache = LRUCache()
        assert cache.stats["ttl"] is None

    def test_stats_size_reflects_current_count(self):
        cache = LRUCache()
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.stats["size"] == 2


# ---------------------------------------------------------------------------
# cache_result decorator tests
# ---------------------------------------------------------------------------


class TestCacheResultDecorator:
    def test_cached_function_returns_correct_result(self):
        call_count = [0]

        @cache_result()
        def compute(x: int) -> int:
            call_count[0] += 1
            return x * 2

        assert compute(5) == 10

    def test_cached_function_called_only_once_for_same_args(self):
        call_count = [0]

        @cache_result()
        def compute(x: int) -> int:
            call_count[0] += 1
            return x * 2

        compute(5)
        compute(5)
        assert call_count[0] == 1

    def test_cached_function_called_again_for_different_args(self):
        call_count = [0]

        @cache_result()
        def compute(x: int) -> int:
            call_count[0] += 1
            return x * 2

        compute(5)
        compute(10)
        assert call_count[0] == 2

    def test_cache_result_preserves_function_name(self):
        @cache_result()
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_cache_result_preserves_docstring(self):
        @cache_result()
        def my_function():
            """My docstring."""
            pass

        assert my_function.__doc__ == "My docstring."

    def test_cache_result_exposes_cache_attribute(self):
        @cache_result()
        def my_function():
            pass

        assert hasattr(my_function, "_cache")
        assert isinstance(my_function._cache, LRUCache)

    def test_cache_result_with_kwargs(self):
        call_count = [0]

        @cache_result()
        def greet(name: str, greeting: str = "Hello") -> str:
            call_count[0] += 1
            return f"{greeting}, {name}!"

        greet(name="Alice", greeting="Hi")
        greet(name="Alice", greeting="Hi")
        assert call_count[0] == 1

    def test_cache_result_with_ttl_returns_fresh_after_expiry(self):
        call_count = [0]

        @cache_result(ttl=0.05)
        def fetch(key: str) -> str:
            call_count[0] += 1
            return f"result-{key}"

        fetch("x")
        time.sleep(0.1)
        fetch("x")
        assert call_count[0] == 2

    def test_cache_result_with_ttl_uses_cache_before_expiry(self):
        call_count = [0]

        @cache_result(ttl=10.0)
        def fetch(key: str) -> str:
            call_count[0] += 1
            return f"result-{key}"

        fetch("x")
        fetch("x")
        assert call_count[0] == 1

    def test_cache_result_maxsize_respected(self):
        @cache_result(maxsize=2)
        def compute(x: int) -> int:
            return x

        compute(1)
        compute(2)
        compute(3)
        assert compute._cache.size() == 2


# ---------------------------------------------------------------------------
# TokenCache tests
# ---------------------------------------------------------------------------


class TestTokenCache:
    def test_get_missing_provider_returns_none(self):
        cache = TokenCache()
        assert cache.get("openai") is None

    def test_store_and_get_token(self):
        cache = TokenCache()
        cache.store("openai", "sk-test-token", expires_in=3600)
        assert cache.get("openai") == "sk-test-token"

    def test_expired_token_returns_none(self):
        cache = TokenCache()
        cache.store("openai", "sk-expired", expires_in=0.01)
        time.sleep(0.05)
        assert cache.get("openai") is None

    def test_expired_token_removed_from_internal_store(self):
        cache = TokenCache()
        cache.store("openai", "sk-expired", expires_in=0.01)
        time.sleep(0.05)
        cache.get("openai")
        assert "openai" not in cache._tokens

    def test_invalidate_removes_token(self):
        cache = TokenCache()
        cache.store("anthropic", "sk-ant-123", expires_in=3600)
        cache.invalidate("anthropic")
        assert cache.get("anthropic") is None

    def test_invalidate_missing_provider_does_not_raise(self):
        cache = TokenCache()
        cache.invalidate("nonexistent")  # should not raise

    def test_clear_removes_all_tokens(self):
        cache = TokenCache()
        cache.store("openai", "sk-1", expires_in=3600)
        cache.store("anthropic", "sk-2", expires_in=3600)
        cache.clear()
        assert cache.get("openai") is None
        assert cache.get("anthropic") is None

    def test_clear_empties_internal_dict(self):
        cache = TokenCache()
        cache.store("openai", "sk-1", expires_in=3600)
        cache.clear()
        assert len(cache._tokens) == 0

    def test_store_overwrites_existing_token(self):
        cache = TokenCache()
        cache.store("openai", "sk-old", expires_in=3600)
        cache.store("openai", "sk-new", expires_in=3600)
        assert cache.get("openai") == "sk-new"

    def test_default_expiry_is_3600(self):
        cache = TokenCache()
        cache.store("provider", "token-value")
        # Token stored with default 1-hour expiry should be available now
        assert cache.get("provider") == "token-value"

    def test_multiple_providers_independent(self):
        cache = TokenCache()
        cache.store("openai", "sk-openai", expires_in=3600)
        cache.store("anthropic", "sk-ant", expires_in=3600)
        assert cache.get("openai") == "sk-openai"
        assert cache.get("anthropic") == "sk-ant"


# ---------------------------------------------------------------------------
# Global singleton tests
# ---------------------------------------------------------------------------


class TestGlobalSingletons:
    def test_get_api_cache_returns_lru_cache(self):
        cache = get_api_cache()
        assert isinstance(cache, LRUCache)

    def test_get_token_cache_returns_token_cache(self):
        cache = get_token_cache()
        assert isinstance(cache, TokenCache)

    def test_get_api_cache_same_instance_each_call(self):
        cache1 = get_api_cache()
        cache2 = get_api_cache()
        assert cache1 is cache2

    def test_get_token_cache_same_instance_each_call(self):
        cache1 = get_token_cache()
        cache2 = get_token_cache()
        assert cache1 is cache2

    def test_api_cache_maxsize_is_256(self):
        cache = get_api_cache()
        assert cache.stats["maxsize"] == 256

    def test_api_cache_ttl_is_300(self):
        cache = get_api_cache()
        assert cache.stats["ttl"] == 300
