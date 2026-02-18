"""Usage Metering for Dashboard Server (AI-224).

Tracks agent-hour consumption per user per billing period. Supports
in-memory storage with JSON file persistence and optional Redis backend.

Alerts at 80% and 100% of tier quota.

Storage layout (.agent_usage.json):
    {
        "<user_id>": {
            "tier": "explorer",
            "period_start": "2024-01-01T00:00:00",
            "agent_seconds_used": 18000.0,
            "last_updated": "2024-01-15T12:34:56"
        },
        ...
    }

Usage:
    from dashboard.usage_meter import UsageMeter

    meter = UsageMeter()
    meter.record_usage("user_abc", seconds=300)  # 5 minutes
    stats = meter.get_usage("user_abc")
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from dashboard.rate_limiter import TIER_CONFIGS, TierConfig

logger = logging.getLogger(__name__)

# Alert thresholds as fractions of the tier limit
ALERT_THRESHOLD_WARNING = 0.80   # 80% -> warning alert
ALERT_THRESHOLD_CRITICAL = 1.00  # 100% -> critical alert (overage)

# Default persistence file
DEFAULT_USAGE_FILE = ".agent_usage.json"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class UserUsage:
    """Usage record for a single user in the current billing period."""
    user_id: str
    tier: str = "explorer"
    period_start: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    agent_seconds_used: float = 0.0
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # -------------------------------------------------------------------------
    # Derived properties
    # -------------------------------------------------------------------------

    @property
    def agent_hours_used(self) -> float:
        """Agent-hours consumed (agent_seconds_used / 3600)."""
        return self.agent_seconds_used / 3600.0

    @property
    def tier_config(self) -> TierConfig:
        """TierConfig for this user's tier."""
        return TIER_CONFIGS.get(self.tier, TIER_CONFIGS["explorer"])

    @property
    def agent_hours_limit(self) -> float:
        """Monthly agent-hour quota for the user's tier."""
        return self.tier_config.agent_hours_limit

    @property
    def percentage(self) -> float:
        """Percentage of quota used (0-100+)."""
        if self.agent_hours_limit <= 0:
            return 0.0
        return round((self.agent_hours_used / self.agent_hours_limit) * 100, 2)

    @property
    def alert_level(self) -> Optional[str]:
        """Alert level based on usage percentage.

        Returns:
            'critical' when at/above 100%,
            'warning' when at/above 80%,
            None otherwise.
        """
        fraction = self.agent_hours_used / self.agent_hours_limit if self.agent_hours_limit > 0 else 0
        if fraction >= ALERT_THRESHOLD_CRITICAL:
            return "critical"
        if fraction >= ALERT_THRESHOLD_WARNING:
            return "warning"
        return None

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON output."""
        return {
            "user_id": self.user_id,
            "tier": self.tier,
            "period_start": self.period_start,
            "agent_hours_used": round(self.agent_hours_used, 4),
            "agent_hours_limit": self.agent_hours_limit,
            "percentage": self.percentage,
            "alert_level": self.alert_level,
        }

    def to_storage_dict(self) -> dict:
        """Serialise to storage format (keeps agent_seconds_used for precision)."""
        return {
            "tier": self.tier,
            "period_start": self.period_start,
            "agent_seconds_used": self.agent_seconds_used,
            "last_updated": self.last_updated,
        }


# ---------------------------------------------------------------------------
# UsageMeter
# ---------------------------------------------------------------------------

class UsageMeter:
    """Track and persist agent-hour usage per user.

    Args:
        storage_path: Path to the JSON persistence file.
            Defaults to ``.agent_usage.json`` in the current working directory.
        redis_url: Optional Redis URL for distributed storage.
            Falls back to file persistence when Redis is unavailable.
        user_tier_map: Optional mapping of user_id -> tier for testing.
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        redis_url: Optional[str] = None,
        user_tier_map: Optional[Dict[str, str]] = None,
    ) -> None:
        self._storage_path = storage_path or Path.cwd() / DEFAULT_USAGE_FILE
        self._user_tier_map: Dict[str, str] = user_tier_map or {}

        # In-memory store: {user_id: UserUsage}
        self._store: Dict[str, UserUsage] = {}

        # Redis client (optional)
        self._redis = None
        if redis_url:
            self._init_redis(redis_url)

        # Load persisted data
        self._load()

    def _init_redis(self, redis_url: str) -> None:
        """Attempt to initialise a Redis connection (non-fatal on failure)."""
        try:
            import redis  # type: ignore
            client = redis.from_url(redis_url, socket_connect_timeout=1)
            client.ping()
            self._redis = client
            logger.info(f"UsageMeter: connected to Redis at {redis_url}")
        except Exception as exc:  # pragma: no cover
            logger.warning(
                f"UsageMeter: Redis unavailable ({exc}), using file persistence."
            )
            self._redis = None

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load usage data from the JSON file (if it exists)."""
        try:
            if self._storage_path.exists():
                raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
                for user_id, data in raw.items():
                    self._store[user_id] = UserUsage(
                        user_id=user_id,
                        tier=data.get("tier", "explorer"),
                        period_start=data.get(
                            "period_start",
                            datetime.now(timezone.utc).isoformat(),
                        ),
                        agent_seconds_used=float(data.get("agent_seconds_used", 0.0)),
                        last_updated=data.get(
                            "last_updated",
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                logger.debug(f"UsageMeter: loaded {len(self._store)} user records.")
        except Exception as exc:
            logger.warning(f"UsageMeter: could not load usage file: {exc}")

    def _save(self) -> None:
        """Persist usage data to the JSON file."""
        try:
            payload = {
                user_id: record.to_storage_dict()
                for user_id, record in self._store.items()
            }
            self._storage_path.write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning(f"UsageMeter: could not save usage file: {exc}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create(self, user_id: str) -> UserUsage:
        """Return the UserUsage for user_id, creating one if necessary."""
        if user_id not in self._store:
            tier = self._user_tier_map.get(user_id, "explorer")
            self._store[user_id] = UserUsage(user_id=user_id, tier=tier)
        return self._store[user_id]

    def _emit_alert(self, usage: UserUsage) -> None:
        """Log an alert when usage crosses 80% or 100% thresholds."""
        level = usage.alert_level
        if level == "critical":
            logger.warning(
                f"USAGE OVERAGE: user={usage.user_id} tier={usage.tier} "
                f"used={usage.agent_hours_used:.2f}h "
                f"limit={usage.agent_hours_limit:.2f}h "
                f"({usage.percentage:.1f}%)"
            )
        elif level == "warning":
            logger.info(
                f"USAGE WARNING: user={usage.user_id} tier={usage.tier} "
                f"at {usage.percentage:.1f}% of {usage.agent_hours_limit:.2f}h limit"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_usage(self, user_id: str, seconds: float) -> UserUsage:
        """Record agent-time consumption for a user.

        Args:
            user_id: The user identifier.
            seconds: Number of agent-seconds consumed.

        Returns:
            Updated UserUsage record.
        """
        if seconds < 0:
            raise ValueError(f"seconds must be non-negative, got {seconds}")

        usage = self._get_or_create(user_id)
        usage.agent_seconds_used += seconds
        usage.last_updated = datetime.now(timezone.utc).isoformat()

        self._emit_alert(usage)
        self._save()
        return usage

    def get_usage(self, user_id: str) -> UserUsage:
        """Return usage record for user_id.

        Creates a default record if the user has no recorded usage.

        Args:
            user_id: The user identifier.

        Returns:
            UserUsage record.
        """
        return self._get_or_create(user_id)

    def get_usage_percentage(self, user_id: str) -> float:
        """Return the percentage of quota used for user_id (0-100+).

        Args:
            user_id: The user identifier.

        Returns:
            Float percentage.
        """
        return self._get_or_create(user_id).percentage

    def reset_period(self, user_id: str) -> UserUsage:
        """Reset usage for user_id for a new billing period.

        Args:
            user_id: The user identifier.

        Returns:
            Fresh UserUsage record.
        """
        tier = self._user_tier_map.get(user_id, "explorer")
        if user_id in self._store:
            tier = self._store[user_id].tier

        self._store[user_id] = UserUsage(user_id=user_id, tier=tier)
        self._save()
        logger.info(f"UsageMeter: reset billing period for user={user_id}")
        return self._store[user_id]

    def set_user_tier(self, user_id: str, tier: str) -> None:
        """Set the tier for a user.

        Args:
            user_id: The user identifier.
            tier: Tier name ('explorer', 'builder', 'team', 'scale').
        """
        if tier not in TIER_CONFIGS:
            raise ValueError(f"Unknown tier {tier!r}. Valid: {list(TIER_CONFIGS)}")
        self._user_tier_map[user_id] = tier
        usage = self._get_or_create(user_id)
        usage.tier = tier
        self._save()

    def get_all_usage(self) -> List[dict]:
        """Return a list of usage dicts for all tracked users.

        Returns:
            List of usage dicts.
        """
        return [record.to_dict() for record in self._store.values()]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_global_usage_meter: Optional[UsageMeter] = None


def get_usage_meter() -> UsageMeter:
    """Get the global UsageMeter singleton (lazy init).

    Returns:
        UsageMeter instance
    """
    global _global_usage_meter
    if _global_usage_meter is None:
        redis_url = os.getenv("REDIS_URL", "")
        _global_usage_meter = UsageMeter(
            redis_url=redis_url or None,
        )
    return _global_usage_meter


def reset_usage_meter() -> None:
    """Reset the global UsageMeter singleton (useful for testing)."""
    global _global_usage_meter
    _global_usage_meter = None
