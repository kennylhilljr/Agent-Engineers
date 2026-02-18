"""API Rate Limiting Middleware for Dashboard Server (AI-224).

Implements a sliding window rate limiter with Redis backend (optional) and
in-memory fallback. Supports per-user (authenticated) and per-IP
(unauthenticated) rate limiting.

Tier Configurations:
    Explorer: Chat 10/min, Agent 5/min, Webhook N/A, WebSocket 1 conn
    Builder:  Chat 60/min, Agent 30/min, Webhook 10/min, WebSocket 3 conn
    Team:     Chat 300/min, Agent 150/min, Webhook 60/min, WebSocket 10 conn
    Scale:    Chat 1000/min, Agent 500/min, Webhook 200/min, WebSocket 25 conn

Usage:
    from dashboard.rate_limiter import RateLimiter, rate_limit_middleware

    limiter = RateLimiter()
    app = web.Application(middlewares=[limiter.middleware, auth_middleware, cors_middleware])
"""

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from aiohttp import web
from aiohttp.web import Request, Response, middleware

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier configuration
# ---------------------------------------------------------------------------

@dataclass
class TierConfig:
    """Rate limit configuration for a single tier."""
    name: str
    chat_per_min: int          # Chat API requests per minute
    agent_per_min: int         # Agent API requests per minute
    webhook_per_min: int       # Webhook requests per minute (0 = N/A)
    websocket_conns: int       # Maximum concurrent WebSocket connections
    agent_hours_limit: float   # Monthly agent-hour quota


# Tier definitions in order of escalating permissions
TIER_CONFIGS: Dict[str, TierConfig] = {
    "explorer": TierConfig(
        name="explorer",
        chat_per_min=10,
        agent_per_min=5,
        webhook_per_min=0,
        websocket_conns=1,
        agent_hours_limit=10.0,
    ),
    "builder": TierConfig(
        name="builder",
        chat_per_min=60,
        agent_per_min=30,
        webhook_per_min=10,
        websocket_conns=3,
        agent_hours_limit=50.0,
    ),
    "team": TierConfig(
        name="team",
        chat_per_min=300,
        agent_per_min=150,
        webhook_per_min=60,
        websocket_conns=10,
        agent_hours_limit=200.0,
    ),
    "scale": TierConfig(
        name="scale",
        chat_per_min=1000,
        agent_per_min=500,
        webhook_per_min=200,
        websocket_conns=25,
        agent_hours_limit=1000.0,
    ),
}

# Endpoint-type to tier config attribute mapping
ENDPOINT_TYPE_MAP = {
    "chat": "chat_per_min",
    "agent": "agent_per_min",
    "webhook": "webhook_per_min",
}


def classify_endpoint(path: str, method: str) -> str:
    """Classify a request path into an endpoint type.

    Args:
        path: The request URL path.
        method: The HTTP method.

    Returns:
        One of 'chat', 'agent', 'webhook', 'websocket', or 'other'.
    """
    if path == "/ws":
        return "websocket"
    if path.startswith("/api/chat"):
        return "chat"
    if path.startswith("/api/agents") or path.startswith("/api/agent"):
        return "agent"
    if path.startswith("/api/webhook"):
        return "webhook"
    return "other"


def get_identifier(request: Request) -> Tuple[str, bool]:
    """Extract the rate-limit identifier from a request.

    Returns the user token (authenticated) or IP address (unauthenticated).

    Args:
        request: The incoming aiohttp request.

    Returns:
        Tuple of (identifier, is_authenticated).
    """
    # Check for API key in X-API-Key header
    api_key = request.headers.get("X-API-Key", "").strip()
    if api_key:
        return f"key:{api_key}", True

    # Check for Bearer token in Authorization header
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        if token:
            return f"token:{token}", True

    # Fallback to IP address
    # Check X-Forwarded-For first for proxy-forwarded requests
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    else:
        ip = request.remote or "unknown"
    return f"ip:{ip}", False


# ---------------------------------------------------------------------------
# Sliding Window Counter (in-memory)
# ---------------------------------------------------------------------------

@dataclass
class SlidingWindowCounter:
    """Thread-safe sliding window request counter.

    Uses a list of timestamps to track requests within a rolling window.
    """
    window_seconds: int = 60
    timestamps: List[float] = field(default_factory=list)

    def add(self, now: Optional[float] = None) -> None:
        """Record a new request at the current time."""
        if now is None:
            now = time.time()
        self.timestamps.append(now)
        self._prune(now)

    def count(self, now: Optional[float] = None) -> int:
        """Count requests within the current window."""
        if now is None:
            now = time.time()
        self._prune(now)
        return len(self.timestamps)

    def _prune(self, now: float) -> None:
        """Remove timestamps older than the window."""
        cutoff = now - self.window_seconds
        self.timestamps = [t for t in self.timestamps if t > cutoff]

    def oldest_timestamp(self) -> Optional[float]:
        """Return the oldest timestamp in the window, or None if empty."""
        if self.timestamps:
            return self.timestamps[0]
        return None


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Rate limiter using sliding window algorithm.

    Supports optional Redis backend for distributed deployments; falls back
    gracefully to an in-memory dict when Redis is unavailable.

    Args:
        default_tier: Default tier name for unrecognised users.
        redis_url: Optional Redis URL (e.g. 'redis://localhost:6379').
            When not provided or when connection fails, falls back to memory.
        user_tier_map: Optional mapping of identifier -> tier name for testing.
    """

    def __init__(
        self,
        default_tier: str = "explorer",
        redis_url: Optional[str] = None,
        user_tier_map: Optional[Dict[str, str]] = None,
    ) -> None:
        self.default_tier = default_tier
        self._user_tier_map: Dict[str, str] = user_tier_map or {}

        # In-memory counters: {identifier: {endpoint_type: SlidingWindowCounter}}
        self._counters: Dict[str, Dict[str, SlidingWindowCounter]] = defaultdict(
            lambda: defaultdict(SlidingWindowCounter)
        )

        # Redis client (optional)
        self._redis = None
        if redis_url:
            self._init_redis(redis_url)

    def _init_redis(self, redis_url: str) -> None:
        """Attempt to initialise a Redis connection (non-fatal on failure)."""
        try:
            import redis  # type: ignore
            client = redis.from_url(redis_url, socket_connect_timeout=1)
            client.ping()
            self._redis = client
            logger.info(f"RateLimiter: connected to Redis at {redis_url}")
        except Exception as exc:  # pragma: no cover
            logger.warning(
                f"RateLimiter: Redis unavailable ({exc}), using in-memory fallback."
            )
            self._redis = None

    # ------------------------------------------------------------------
    # Tier resolution
    # ------------------------------------------------------------------

    def get_tier(self, identifier: str) -> TierConfig:
        """Return the TierConfig for a given identifier.

        Args:
            identifier: Rate-limit key (user token or IP).

        Returns:
            TierConfig for the resolved tier.
        """
        tier_name = self._user_tier_map.get(identifier, self.default_tier)
        return TIER_CONFIGS.get(tier_name, TIER_CONFIGS[self.default_tier])

    def set_user_tier(self, identifier: str, tier: str) -> None:
        """Assign a specific tier to an identifier (e.g. during auth).

        Args:
            identifier: Rate-limit key.
            tier: Tier name ('explorer', 'builder', 'team', 'scale').
        """
        if tier not in TIER_CONFIGS:
            raise ValueError(f"Unknown tier {tier!r}. Valid tiers: {list(TIER_CONFIGS)}")
        self._user_tier_map[identifier] = tier

    # ------------------------------------------------------------------
    # Core rate limiting
    # ------------------------------------------------------------------

    def _get_limit(self, tier: TierConfig, endpoint_type: str) -> int:
        """Return the per-minute request limit for endpoint_type in tier.

        Returns 0 for N/A limits (e.g. explorer webhooks).
        """
        attr = ENDPOINT_TYPE_MAP.get(endpoint_type)
        if attr is None:
            return 0  # 'other' and 'websocket' are not request-rate limited here
        return getattr(tier, attr, 0)

    def check_rate_limit(
        self,
        identifier: str,
        endpoint_type: str,
        now: Optional[float] = None,
    ) -> Tuple[bool, int, int, float]:
        """Check whether a request is within rate limits.

        Uses Redis when available, otherwise in-memory sliding window.

        Args:
            identifier: Rate-limit key (user token or IP).
            endpoint_type: One of 'chat', 'agent', 'webhook', 'other'.
            now: Override current time (useful in tests).

        Returns:
            Tuple of:
                - allowed (bool): True if request should proceed.
                - limit (int): Configured max requests per window.
                - remaining (int): Remaining requests in current window.
                - reset_at (float): Unix timestamp when window resets.
        """
        if now is None:
            now = time.time()

        tier = self.get_tier(identifier)
        limit = self._get_limit(tier, endpoint_type)

        if limit == 0:
            # Endpoint not available on this tier (e.g. explorer webhooks)
            return False, 0, 0, now + 60

        if self._redis is not None:
            return self._check_redis(identifier, endpoint_type, limit, now)
        return self._check_memory(identifier, endpoint_type, limit, now)

    def _check_memory(
        self,
        identifier: str,
        endpoint_type: str,
        limit: int,
        now: float,
    ) -> Tuple[bool, int, int, float]:
        """Sliding window check against in-memory counter."""
        counter = self._counters[identifier][endpoint_type]
        current_count = counter.count(now)

        allowed = current_count < limit
        if allowed:
            counter.add(now)
            current_count += 1

        remaining = max(0, limit - current_count)

        # Reset time = oldest timestamp + 60s (or now+60 if window is empty)
        oldest = counter.oldest_timestamp()
        reset_at = (oldest + 60) if oldest else (now + 60)

        return allowed, limit, remaining, reset_at

    def _check_redis(
        self,
        identifier: str,
        endpoint_type: str,
        limit: int,
        now: float,
    ) -> Tuple[bool, int, int, float]:  # pragma: no cover
        """Sliding window check against Redis sorted set."""
        try:
            key = f"rl:{identifier}:{endpoint_type}"
            window_start = now - 60

            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, "-inf", window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, 120)
            results = pipe.execute()
            count = results[2]

            if count > limit:
                # Undo the add we just made
                self._redis.zremrangebyscore(key, now, now)
                count -= 1
                allowed = False
            else:
                allowed = True

            remaining = max(0, limit - count)
            oldest_scores = self._redis.zrange(key, 0, 0, withscores=True)
            reset_at = (oldest_scores[0][1] + 60) if oldest_scores else (now + 60)
            return allowed, limit, remaining, reset_at
        except Exception as exc:
            logger.warning(f"Redis rate limit check failed: {exc}. Falling back to memory.")
            return self._check_memory(identifier, endpoint_type, limit, now)

    def get_headers(
        self,
        identifier: str,
        endpoint_type: str,
        now: Optional[float] = None,
    ) -> Dict[str, str]:
        """Return rate limit headers for a given identifier and endpoint type.

        Does NOT consume a request slot (read-only).

        Args:
            identifier: Rate-limit key.
            endpoint_type: Endpoint type string.
            now: Override current time (useful in tests).

        Returns:
            Dict with X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset.
        """
        if now is None:
            now = time.time()

        tier = self.get_tier(identifier)
        limit = self._get_limit(tier, endpoint_type)

        if limit == 0:
            return {
                "X-RateLimit-Limit": "0",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + 60)),
            }

        counter = self._counters[identifier][endpoint_type]
        current_count = counter.count(now)
        remaining = max(0, limit - current_count)
        oldest = counter.oldest_timestamp()
        reset_at = int((oldest + 60) if oldest else (now + 60))

        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_at),
        }

    # ------------------------------------------------------------------
    # aiohttp middleware
    # ------------------------------------------------------------------

    @middleware
    async def middleware(self, request: Request, handler):
        """aiohttp middleware that enforces rate limits.

        - Passes OPTIONS preflight requests through without rate limiting.
        - Passes /health through without rate limiting.
        - Returns HTTP 429 with Retry-After and X-RateLimit-* headers when
          the limit is exceeded.
        - Adds X-RateLimit-* headers to all non-429 API responses.

        Returns:
            The upstream handler response or a 429 JSON response.
        """
        # Skip rate limiting for health checks and preflight requests
        if request.path == "/health" or request.method == "OPTIONS":
            return await handler(request)

        endpoint_type = classify_endpoint(request.path, request.method)

        # 'other' endpoints are not rate-limited
        if endpoint_type == "other":
            return await handler(request)

        identifier, _is_auth = get_identifier(request)
        now = time.time()

        allowed, limit, remaining, reset_at = self.check_rate_limit(
            identifier, endpoint_type, now
        )

        if not allowed:
            retry_after = max(1, int(reset_at - now))
            return web.json_response(
                {
                    "error": "Rate limit exceeded",
                    "message": (
                        f"Too many requests. Limit: {limit} per minute. "
                        f"Retry after {retry_after} seconds."
                    ),
                    "retry_after": retry_after,
                },
                status=429,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_at)),
                },
            )

        response = await handler(request)

        # Attach rate limit headers to response
        rl_headers = self.get_headers(identifier, endpoint_type, now)
        for key, value in rl_headers.items():
            response.headers[key] = value

        return response


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global RateLimiter singleton (lazy init).

    Returns:
        RateLimiter instance
    """
    global _global_rate_limiter
    if _global_rate_limiter is None:
        import os
        redis_url = os.getenv("REDIS_URL", "")
        _global_rate_limiter = RateLimiter(
            default_tier=os.getenv("DEFAULT_TIER", "explorer"),
            redis_url=redis_url or None,
        )
    return _global_rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global RateLimiter singleton (useful for testing)."""
    global _global_rate_limiter
    _global_rate_limiter = None
