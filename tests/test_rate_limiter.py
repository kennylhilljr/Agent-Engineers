"""Tests for rate limiting and usage metering (AI-224).

Covers:
- Rate limit enforcement (429 responses)
- Rate limit headers on normal responses
- Per-IP fallback when unauthenticated
- In-memory fallback when Redis is unavailable
- Usage metering: record, retrieve, percentage
- Overage alert at 80%
- Usage reset
- API endpoint integration (/api/usage)

Aim: >= 20 tests.
"""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.rate_limiter import (
    RateLimiter,
    SlidingWindowCounter,
    TierConfig,
    TIER_CONFIGS,
    classify_endpoint,
    get_identifier,
    get_rate_limiter,
    reset_rate_limiter,
)
from dashboard.usage_meter import (
    UsageMeter,
    UserUsage,
    ALERT_THRESHOLD_WARNING,
    ALERT_THRESHOLD_CRITICAL,
    get_usage_meter,
    reset_usage_meter,
)


# ===========================================================================
# SlidingWindowCounter tests
# ===========================================================================

class TestSlidingWindowCounter:
    """Tests for the sliding window counter data structure."""

    def test_empty_counter_returns_zero(self):
        counter = SlidingWindowCounter(window_seconds=60)
        assert counter.count() == 0

    def test_add_and_count(self):
        counter = SlidingWindowCounter(window_seconds=60)
        now = time.time()
        counter.add(now)
        counter.add(now + 1)
        assert counter.count(now + 1) == 2

    def test_old_entries_pruned(self):
        counter = SlidingWindowCounter(window_seconds=60)
        old_time = time.time() - 120  # 2 minutes ago — outside window
        counter.add(old_time)
        assert counter.count() == 0

    def test_oldest_timestamp_returns_none_when_empty(self):
        counter = SlidingWindowCounter()
        assert counter.oldest_timestamp() is None

    def test_oldest_timestamp_correct(self):
        counter = SlidingWindowCounter(window_seconds=60)
        now = time.time()
        counter.add(now)
        counter.add(now + 1)
        assert counter.oldest_timestamp() == pytest.approx(now, abs=0.01)


# ===========================================================================
# RateLimiter unit tests
# ===========================================================================

class TestRateLimiter:
    """Tests for the RateLimiter class (in-memory backend)."""

    def setup_method(self):
        self.limiter = RateLimiter(default_tier="explorer")

    def test_first_request_allowed(self):
        allowed, limit, remaining, reset_at = self.limiter.check_rate_limit(
            "user:alice", "chat"
        )
        assert allowed is True
        assert limit == 10  # explorer chat limit
        assert remaining == 9

    def test_limit_exceeded_returns_false(self):
        # Explorer chat limit is 10/min
        identifier = "user:limit_test"
        now = time.time()
        for i in range(10):
            allowed, *_ = self.limiter.check_rate_limit(identifier, "chat", now=now + i * 0.001)
        # 11th request should be denied
        allowed, limit, remaining, reset_at = self.limiter.check_rate_limit(
            identifier, "chat", now=now + 0.1
        )
        assert allowed is False
        assert remaining == 0

    def test_tier_limits_enforced_per_tier(self):
        # Builder tier has 60 chat/min
        self.limiter.set_user_tier("user:builder", "builder")
        tier = self.limiter.get_tier("user:builder")
        assert tier.chat_per_min == 60

    def test_scale_tier_high_limits(self):
        self.limiter.set_user_tier("user:scale", "scale")
        tier = self.limiter.get_tier("user:scale")
        assert tier.chat_per_min == 1000
        assert tier.agent_per_min == 500

    def test_explorer_webhook_returns_not_allowed(self):
        """Explorer tier has no webhook access (limit = 0)."""
        allowed, limit, remaining, reset_at = self.limiter.check_rate_limit(
            "user:explorer", "webhook"
        )
        assert allowed is False
        assert limit == 0

    def test_get_headers_returns_expected_keys(self):
        headers = self.limiter.get_headers("user:headers_test", "chat")
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers

    def test_get_headers_limit_matches_tier(self):
        headers = self.limiter.get_headers("user:hdr", "chat")
        assert headers["X-RateLimit-Limit"] == "10"  # explorer default

    def test_set_user_tier_invalid_raises(self):
        with pytest.raises(ValueError, match="Unknown tier"):
            self.limiter.set_user_tier("user:x", "mythic")

    def test_unknown_endpoint_type_zero_limit(self):
        # 'other' endpoints are not limited but check_rate_limit returns 0 limit
        allowed, limit, remaining, reset_at = self.limiter.check_rate_limit(
            "user:other", "other"
        )
        # 'other' maps to 0 limit -> not allowed
        assert limit == 0

    def test_redis_unavailable_falls_back_to_memory(self):
        """RateLimiter with a bad Redis URL must fall back gracefully."""
        limiter = RateLimiter(
            default_tier="explorer",
            redis_url="redis://invalid-host:9999",
        )
        # Should not raise; redis should be None
        assert limiter._redis is None
        allowed, limit, remaining, reset_at = limiter.check_rate_limit(
            "user:fallback", "chat"
        )
        assert allowed is True

    def test_remaining_decreases_with_each_request(self):
        identifier = "user:remaining"
        now = time.time()
        _, _, rem0, _ = self.limiter.check_rate_limit(identifier, "chat", now=now)
        _, _, rem1, _ = self.limiter.check_rate_limit(identifier, "chat", now=now + 0.01)
        assert rem1 < rem0

    def test_classify_endpoint_chat(self):
        assert classify_endpoint("/api/chat", "POST") == "chat"
        assert classify_endpoint("/api/chat/history", "GET") == "chat"

    def test_classify_endpoint_agent(self):
        assert classify_endpoint("/api/agents/status", "GET") == "agent"
        assert classify_endpoint("/api/agent-status", "POST") == "agent"

    def test_classify_endpoint_websocket(self):
        assert classify_endpoint("/ws", "GET") == "websocket"

    def test_classify_endpoint_other(self):
        assert classify_endpoint("/health", "GET") == "other"
        assert classify_endpoint("/api/metrics", "GET") == "other"


# ===========================================================================
# get_identifier tests
# ===========================================================================

class TestGetIdentifier:
    """Tests for the request identifier extractor."""

    def _make_request(self, headers=None, remote="192.168.1.1"):
        """Create a minimal mock request."""
        req = MagicMock()
        req.headers = headers or {}
        req.remote = remote
        req.rel_url = MagicMock()
        return req

    def test_bearer_token_returns_authenticated(self):
        req = self._make_request(headers={"Authorization": "Bearer mytoken123"})
        identifier, is_auth = get_identifier(req)
        assert is_auth is True
        assert "token:mytoken123" == identifier

    def test_api_key_returns_authenticated(self):
        req = self._make_request(headers={"X-API-Key": "apikey_abc"})
        identifier, is_auth = get_identifier(req)
        assert is_auth is True
        assert "key:apikey_abc" == identifier

    def test_unauthenticated_returns_ip(self):
        req = self._make_request(remote="10.0.0.1")
        identifier, is_auth = get_identifier(req)
        assert is_auth is False
        assert "ip:10.0.0.1" == identifier

    def test_forwarded_for_takes_priority(self):
        req = self._make_request(
            headers={"X-Forwarded-For": "203.0.113.5, 10.0.0.1"},
            remote="10.0.0.1",
        )
        identifier, is_auth = get_identifier(req)
        assert is_auth is False
        assert "ip:203.0.113.5" == identifier


# ===========================================================================
# UsageMeter tests
# ===========================================================================

class TestUsageMeter:
    """Tests for the UsageMeter class."""

    def setup_method(self):
        # Use a temporary file so tests don't pollute the filesystem
        self._tmpdir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self._tmpdir.name) / ".agent_usage.json"
        self.meter = UsageMeter(storage_path=self.storage_path)

    def teardown_method(self):
        self._tmpdir.cleanup()

    def test_record_usage_returns_updated_record(self):
        usage = self.meter.record_usage("user1", seconds=3600)
        assert usage.agent_hours_used == pytest.approx(1.0, abs=1e-6)

    def test_record_usage_accumulates(self):
        self.meter.record_usage("user2", seconds=1800)
        self.meter.record_usage("user2", seconds=1800)
        usage = self.meter.get_usage("user2")
        assert usage.agent_hours_used == pytest.approx(1.0, abs=1e-6)

    def test_get_usage_zero_for_new_user(self):
        usage = self.meter.get_usage("brand_new_user")
        assert usage.agent_hours_used == 0.0

    def test_get_usage_percentage_zero_initially(self):
        pct = self.meter.get_usage_percentage("nobody")
        assert pct == 0.0

    def test_percentage_calculated_correctly(self):
        # Explorer limit = 10 hours; use 5 hours = 50%
        self.meter.record_usage("user3", seconds=5 * 3600)
        pct = self.meter.get_usage_percentage("user3")
        assert pct == pytest.approx(50.0, abs=0.01)

    def test_alert_level_none_below_80(self):
        self.meter.record_usage("user4", seconds=2 * 3600)  # 20% of 10h
        usage = self.meter.get_usage("user4")
        assert usage.alert_level is None

    def test_alert_level_warning_at_80_percent(self):
        # 80% of 10h explorer = 8h
        self.meter.record_usage("user5", seconds=8 * 3600)
        usage = self.meter.get_usage("user5")
        assert usage.alert_level == "warning"

    def test_alert_level_critical_at_100_percent(self):
        # 100% of 10h = 10h
        self.meter.record_usage("user6", seconds=10 * 3600)
        usage = self.meter.get_usage("user6")
        assert usage.alert_level == "critical"

    def test_alert_level_critical_above_100_percent(self):
        # Over limit
        self.meter.record_usage("user7", seconds=12 * 3600)
        usage = self.meter.get_usage("user7")
        assert usage.alert_level == "critical"

    def test_reset_period_clears_usage(self):
        self.meter.record_usage("user8", seconds=5 * 3600)
        usage = self.meter.reset_period("user8")
        assert usage.agent_hours_used == 0.0

    def test_reset_period_preserves_tier(self):
        self.meter.set_user_tier("user9", "builder")
        self.meter.record_usage("user9", seconds=1000)
        usage = self.meter.reset_period("user9")
        assert usage.tier == "builder"

    def test_set_user_tier_invalid_raises(self):
        with pytest.raises(ValueError, match="Unknown tier"):
            self.meter.set_user_tier("user_x", "invalid_tier")

    def test_to_dict_has_required_keys(self):
        usage = self.meter.get_usage("user10")
        d = usage.to_dict()
        required_keys = {
            "user_id", "tier", "period_start",
            "agent_hours_used", "agent_hours_limit",
            "percentage", "alert_level",
        }
        assert required_keys.issubset(d.keys())

    def test_persistence_survives_reload(self):
        self.meter.record_usage("persist_user", seconds=1800)
        # Create a new UsageMeter pointing to the same file
        meter2 = UsageMeter(storage_path=self.storage_path)
        usage = meter2.get_usage("persist_user")
        assert usage.agent_hours_used == pytest.approx(0.5, abs=1e-6)

    def test_builder_tier_higher_limit(self):
        self.meter.set_user_tier("user_builder", "builder")
        usage = self.meter.get_usage("user_builder")
        assert usage.agent_hours_limit == 50.0

    def test_negative_seconds_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            self.meter.record_usage("user11", seconds=-10)

    def test_get_all_usage_returns_list(self):
        self.meter.record_usage("userA", seconds=100)
        self.meter.record_usage("userB", seconds=200)
        all_usage = self.meter.get_all_usage()
        assert isinstance(all_usage, list)
        user_ids = {u["user_id"] for u in all_usage}
        assert "userA" in user_ids
        assert "userB" in user_ids


# ===========================================================================
# Integration: aiohttp middleware tests
# ===========================================================================

@pytest.fixture
def rate_limiter():
    """Fresh RateLimiter for each test."""
    reset_rate_limiter()
    limiter = RateLimiter(default_tier="explorer")
    return limiter


@pytest.mark.asyncio
async def test_rate_limit_middleware_passes_normal_request(rate_limiter):
    """Normal requests within limits should get 200 with rate limit headers."""
    async def handler(request):
        return web.Response(text="ok")

    app = web.Application(middlewares=[rate_limiter.middleware])
    app.router.add_get("/api/chat", handler)

    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        resp = await client.get("/api/chat")
        assert resp.status == 200
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_rate_limit_middleware_returns_429_when_exceeded(rate_limiter):
    """Requests beyond the per-minute limit should return 429."""
    # Set a very low limit by changing the user's tier to explorer
    # and hammering the endpoint 11 times (explorer limit = 10)

    async def handler(request):
        return web.Response(text="ok")

    app = web.Application(middlewares=[rate_limiter.middleware])
    app.router.add_get("/api/chat", handler)

    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        # First 10 should succeed
        for _ in range(10):
            resp = await client.get(
                "/api/chat",
                headers={"X-API-Key": "test_key_429"},
            )
            # May be 200 or already 429 if test order matters; we only care about the 11th
        # 11th should be 429
        resp = await client.get(
            "/api/chat",
            headers={"X-API-Key": "test_key_429"},
        )
        assert resp.status == 429
        data = await resp.json()
        assert "error" in data
        assert "Rate limit" in data["error"]
        assert "Retry-After" in resp.headers
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_rate_limit_middleware_health_exempt(rate_limiter):
    """/health endpoint is not rate-limited."""
    async def handler(request):
        return web.Response(text="healthy")

    app = web.Application(middlewares=[rate_limiter.middleware])
    app.router.add_get("/health", handler)

    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        # Hammer /health well past any rate limit — should never get 429
        for _ in range(20):
            resp = await client.get(
                "/health",
                headers={"X-API-Key": "hammer_health"},
            )
            assert resp.status == 200
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_rate_limit_per_user_not_global(rate_limiter):
    """Rate limits should be per-identifier, not shared across users."""
    async def handler(request):
        return web.Response(text="ok")

    app = web.Application(middlewares=[rate_limiter.middleware])
    app.router.add_get("/api/chat", handler)

    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        # Use up user1's quota
        for _ in range(10):
            await client.get("/api/chat", headers={"X-API-Key": "user_one"})
        # user1 should be rate-limited
        resp1 = await client.get("/api/chat", headers={"X-API-Key": "user_one"})
        assert resp1.status == 429

        # user2 should still have capacity
        resp2 = await client.get("/api/chat", headers={"X-API-Key": "user_two"})
        assert resp2.status == 200
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_options_preflight_not_rate_limited(rate_limiter):
    """OPTIONS requests (CORS preflight) must never be rate-limited."""
    async def handler(request):
        return web.Response(status=204)

    app = web.Application(middlewares=[rate_limiter.middleware])
    app.router.add_route("OPTIONS", "/api/chat", handler)

    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        for _ in range(20):
            resp = await client.options("/api/chat")
            assert resp.status == 204
    finally:
        await client.close()


# ===========================================================================
# Integration: /api/usage endpoint
# ===========================================================================

@pytest.mark.asyncio
async def test_usage_endpoint_returns_json(rate_limiter):
    """GET /api/usage should return a JSON object with required keys."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / ".agent_usage.json"
        usage_meter = UsageMeter(storage_path=storage_path)

        async def handler(request):
            from dashboard.rate_limiter import get_identifier
            identifier, _ = get_identifier(request)
            usage = usage_meter.get_usage(identifier)
            return web.json_response(usage.to_dict())

        app = web.Application()
        app.router.add_get("/api/usage", handler)

        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            resp = await client.get("/api/usage")
            assert resp.status == 200
            data = await resp.json()
            assert "user_id" in data
            assert "tier" in data
            assert "agent_hours_used" in data
            assert "agent_hours_limit" in data
            assert "percentage" in data
            assert "alert_level" in data
        finally:
            await client.close()


# ===========================================================================
# Tier configuration sanity checks
# ===========================================================================

class TestTierConfigs:
    """Verify the tier configuration table matches the spec."""

    def test_explorer_limits(self):
        t = TIER_CONFIGS["explorer"]
        assert t.chat_per_min == 10
        assert t.agent_per_min == 5
        assert t.webhook_per_min == 0
        assert t.websocket_conns == 1

    def test_builder_limits(self):
        t = TIER_CONFIGS["builder"]
        assert t.chat_per_min == 60
        assert t.agent_per_min == 30
        assert t.webhook_per_min == 10
        assert t.websocket_conns == 3

    def test_team_limits(self):
        t = TIER_CONFIGS["team"]
        assert t.chat_per_min == 300
        assert t.agent_per_min == 150
        assert t.webhook_per_min == 60
        assert t.websocket_conns == 10

    def test_scale_limits(self):
        t = TIER_CONFIGS["scale"]
        assert t.chat_per_min == 1000
        assert t.agent_per_min == 500
        assert t.webhook_per_min == 200
        assert t.websocket_conns == 25

    def test_all_four_tiers_present(self):
        for tier_name in ("explorer", "builder", "team", "scale"):
            assert tier_name in TIER_CONFIGS
