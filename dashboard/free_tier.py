"""Free Tier / Explorer Plan Management for Agent Dashboard (AI-220).

Implements the FreeTierManager class responsible for:
- Tracking agent-hours per user with monthly reset logic
- Enforcing model restrictions (Explorer: Haiku only)
- Enforcing concurrency limits (Explorer: 1 concurrent agent)
- Enforcing agent-hour limits (Explorer: 10h/month)
- Recording session start/end events
- Persisting usage to data/usage_data.json

Plans:
    EXPLORER  (free)   - 10 agent-hours/month, Haiku only, 1 concurrent agent
    BUILDER   ($49)    - 50 agent-hours/month, all models, 5 concurrent agents
    TEAM      ($199)   - 200 agent-hours/month, all models, 20 concurrent agents
    ORGANIZATION ($799) - unlimited agent-hours, all models, unlimited concurrency
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plan definitions
# ---------------------------------------------------------------------------

@dataclass
class PlanConfig:
    """Configuration for a billing plan."""
    name: str
    display_name: str
    price_monthly: float
    agent_hours_limit: float          # monthly agent-hour quota (float('inf') for unlimited)
    max_concurrent_agents: int        # max concurrent agents (0 = unlimited)
    allowed_models: List[str]         # list of allowed model identifiers
    allowed_integrations: List[str]   # list of allowed integrations


PLAN_CONFIGS: Dict[str, PlanConfig] = {
    "explorer": PlanConfig(
        name="explorer",
        display_name="Explorer (Free)",
        price_monthly=0.0,
        agent_hours_limit=10.0,
        max_concurrent_agents=1,
        allowed_models=["claude-haiku-3-5", "claude-haiku-3", "haiku"],
        allowed_integrations=["github"],
    ),
    "builder": PlanConfig(
        name="builder",
        display_name="Builder",
        price_monthly=49.0,
        agent_hours_limit=50.0,
        max_concurrent_agents=5,
        allowed_models=[
            "claude-haiku-3-5", "claude-haiku-3", "haiku",
            "claude-sonnet-4-5", "claude-sonnet-3-5", "sonnet",
            "claude-opus-4-6", "claude-opus-4", "opus",
        ],
        allowed_integrations=["github", "slack", "jira", "linear"],
    ),
    "team": PlanConfig(
        name="team",
        display_name="Team",
        price_monthly=199.0,
        agent_hours_limit=200.0,
        max_concurrent_agents=20,
        allowed_models=[
            "claude-haiku-3-5", "claude-haiku-3", "haiku",
            "claude-sonnet-4-5", "claude-sonnet-3-5", "sonnet",
            "claude-opus-4-6", "claude-opus-4", "opus",
        ],
        allowed_integrations=["github", "slack", "jira", "linear", "pagerduty", "datadog"],
    ),
    "organization": PlanConfig(
        name="organization",
        display_name="Organization",
        price_monthly=799.0,
        agent_hours_limit=float("inf"),
        max_concurrent_agents=0,  # 0 = unlimited
        allowed_models=[
            "claude-haiku-3-5", "claude-haiku-3", "haiku",
            "claude-sonnet-4-5", "claude-sonnet-3-5", "sonnet",
            "claude-opus-4-6", "claude-opus-4", "opus",
        ],
        allowed_integrations=["*"],  # all integrations
    ),
}

# Default data file path
DEFAULT_USAGE_DATA_FILE = Path(__file__).parent.parent / "data" / "usage_data.json"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ActiveSession:
    """Represents an in-progress agent session."""
    session_id: str
    user_id: str
    started_at: float  # unix timestamp
    model: Optional[str] = None

    def elapsed_seconds(self) -> float:
        """Return elapsed time in seconds since session started."""
        return time.time() - self.started_at

    def elapsed_hours(self) -> float:
        """Return elapsed time in hours since session started."""
        return self.elapsed_seconds() / 3600.0

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "started_at": self.started_at,
            "elapsed_hours": round(self.elapsed_hours(), 4),
            "model": self.model,
        }


@dataclass
class UserBillingRecord:
    """Billing and usage record for a single user."""
    user_id: str
    plan: str = "explorer"
    hours_used: float = 0.0
    period_start: str = field(
        default_factory=lambda: _first_of_month_iso()
    )
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def plan_config(self) -> PlanConfig:
        return PLAN_CONFIGS.get(self.plan, PLAN_CONFIGS["explorer"])

    @property
    def hours_limit(self) -> float:
        return self.plan_config.agent_hours_limit

    @property
    def percent_used(self) -> float:
        if self.hours_limit <= 0 or self.hours_limit == float("inf"):
            return 0.0
        return round((self.hours_used / self.hours_limit) * 100.0, 2)

    @property
    def reset_date(self) -> str:
        """ISO date string for next reset (1st of next month)."""
        try:
            period = datetime.fromisoformat(self.period_start.replace("Z", "+00:00"))
            # Calculate the 1st of the next month
            if period.month == 12:
                next_month = period.replace(year=period.year + 1, month=1, day=1)
            else:
                next_month = period.replace(month=period.month + 1, day=1)
            return next_month.date().isoformat()
        except Exception:
            return ""

    def to_dict(self) -> dict:
        limit = self.hours_limit
        return {
            "user_id": self.user_id,
            "plan": self.plan,
            "plan_display": self.plan_config.display_name,
            "hours_used": round(self.hours_used, 4),
            "hours_limit": limit if limit != float("inf") else None,
            "percent_used": self.percent_used,
            "period_start": self.period_start,
            "reset_date": self.reset_date,
            "show_upgrade_cta": self.percent_used >= 80.0,
            "allowed_models": self.plan_config.allowed_models,
            "max_concurrent_agents": self.plan_config.max_concurrent_agents,
        }

    def to_storage_dict(self) -> dict:
        return {
            "plan": self.plan,
            "hours_used": self.hours_used,
            "period_start": self.period_start,
            "last_updated": self.last_updated,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_of_month_iso() -> str:
    """Return ISO string for the first of the current month (UTC)."""
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def _needs_monthly_reset(period_start_iso: str) -> bool:
    """Return True if period_start is in a previous month (UTC)."""
    try:
        period = datetime.fromisoformat(period_start_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (period.year, period.month) != (now.year, now.month)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# FreeTierManager
# ---------------------------------------------------------------------------

class FreeTierManager:
    """Manages free tier limits and usage tracking for Agent Dashboard (AI-220).

    Args:
        data_file: Path to the JSON persistence file.
            Defaults to ``data/usage_data.json`` in the project root.
        default_plan: Default plan assigned to new users. Defaults to 'explorer'.
    """

    def __init__(
        self,
        data_file: Optional[Path] = None,
        default_plan: str = "explorer",
    ) -> None:
        self._data_file = data_file or DEFAULT_USAGE_DATA_FILE
        self._default_plan = default_plan

        # In-memory stores
        self._billing: Dict[str, UserBillingRecord] = {}
        self._active_sessions: Dict[str, ActiveSession] = {}  # session_id -> ActiveSession
        self._completed_sessions: List[dict] = []  # history

        # Ensure data directory exists
        self._data_file.parent.mkdir(parents=True, exist_ok=True)

        # Load persisted data
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load billing records from JSON file."""
        try:
            if self._data_file.exists():
                raw = json.loads(self._data_file.read_text(encoding="utf-8"))
                billing_data = raw.get("billing", {})
                for user_id, data in billing_data.items():
                    self._billing[user_id] = UserBillingRecord(
                        user_id=user_id,
                        plan=data.get("plan", self._default_plan),
                        hours_used=float(data.get("hours_used", 0.0)),
                        period_start=data.get("period_start", _first_of_month_iso()),
                        last_updated=data.get(
                            "last_updated", datetime.now(timezone.utc).isoformat()
                        ),
                    )
                self._completed_sessions = raw.get("completed_sessions", [])
                logger.debug(
                    f"FreeTierManager: loaded {len(self._billing)} user records."
                )
        except Exception as exc:
            logger.warning(f"FreeTierManager: could not load data file: {exc}")

    def _save(self) -> None:
        """Persist billing records to JSON file."""
        try:
            payload = {
                "billing": {
                    user_id: record.to_storage_dict()
                    for user_id, record in self._billing.items()
                },
                "completed_sessions": self._completed_sessions[-200:],  # keep last 200
            }
            self._data_file.write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning(f"FreeTierManager: could not save data file: {exc}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_billing(self, user_id: str) -> UserBillingRecord:
        """Return billing record for user_id, creating one if necessary."""
        if user_id not in self._billing:
            self._billing[user_id] = UserBillingRecord(
                user_id=user_id, plan=self._default_plan
            )

        record = self._billing[user_id]

        # Check if monthly reset is needed
        if _needs_monthly_reset(record.period_start):
            logger.info(
                f"FreeTierManager: monthly reset triggered for user={user_id}"
            )
            record.hours_used = 0.0
            record.period_start = _first_of_month_iso()
            record.last_updated = datetime.now(timezone.utc).isoformat()
            self._save()

        return record

    def _get_user_active_count(self, user_id: str) -> int:
        """Return count of active sessions for user_id."""
        return sum(
            1 for s in self._active_sessions.values() if s.user_id == user_id
        )

    # ------------------------------------------------------------------
    # Public API: usage queries
    # ------------------------------------------------------------------

    def get_usage(self, user_id: str) -> dict:
        """Return current usage stats for user_id.

        Returns:
            dict with keys: hours_used, hours_limit, percent_used, plan,
            plan_display, reset_date, period_start, show_upgrade_cta,
            allowed_models, max_concurrent_agents
        """
        record = self._get_or_create_billing(user_id)
        return record.to_dict()

    def get_plan(self, user_id: str) -> dict:
        """Return the current plan info for user_id.

        Returns:
            dict with plan info including features and pricing
        """
        record = self._get_or_create_billing(user_id)
        cfg = record.plan_config
        return {
            "plan": record.plan,
            "display_name": cfg.display_name,
            "price_monthly": cfg.price_monthly,
            "agent_hours_limit": cfg.agent_hours_limit if cfg.agent_hours_limit != float("inf") else None,
            "max_concurrent_agents": cfg.max_concurrent_agents,
            "allowed_models": cfg.allowed_models,
            "allowed_integrations": cfg.allowed_integrations,
        }

    # ------------------------------------------------------------------
    # Public API: limit checks
    # ------------------------------------------------------------------

    def check_agent_hour_limit(self, user_id: str) -> bool:
        """Check if user has remaining agent-hours this month.

        Returns:
            True if the user can start a new session, False if limit exceeded.
        """
        record = self._get_or_create_billing(user_id)
        limit = record.hours_limit
        if limit == float("inf"):
            return True
        return record.hours_used < limit

    def check_model_allowed(self, user_id: str, model: str) -> bool:
        """Check if the given model is allowed for user_id's plan.

        Args:
            user_id: The user identifier.
            model: Model identifier (e.g. 'claude-sonnet-4-5', 'sonnet', 'haiku').

        Returns:
            True if the model is allowed, False otherwise.
        """
        record = self._get_or_create_billing(user_id)
        allowed = record.plan_config.allowed_models
        # Check exact match or partial/alias match
        model_lower = model.lower()
        for allowed_model in allowed:
            if model_lower == allowed_model.lower():
                return True
            # Also match by short alias (e.g. "haiku" matches "claude-haiku-3-5")
            if model_lower in allowed_model.lower():
                return True
        return False

    def check_concurrency_limit(self, user_id: str, current_active: Optional[int] = None) -> bool:
        """Check if user can start another concurrent agent session.

        Args:
            user_id: The user identifier.
            current_active: Optional override for current active session count.
                If None, uses internal tracking.

        Returns:
            True if the user can start another agent, False if at concurrency limit.
        """
        record = self._get_or_create_billing(user_id)
        max_concurrent = record.plan_config.max_concurrent_agents
        if max_concurrent == 0:  # unlimited
            return True

        active_count = (
            current_active
            if current_active is not None
            else self._get_user_active_count(user_id)
        )
        return active_count < max_concurrent

    # ------------------------------------------------------------------
    # Public API: session tracking
    # ------------------------------------------------------------------

    def record_session_start(
        self, user_id: str, session_id: str, model: Optional[str] = None
    ) -> dict:
        """Record the start of an agent session.

        Args:
            user_id: The user identifier.
            session_id: Unique session identifier.
            model: Model being used (optional).

        Returns:
            dict with session info and current usage stats.
        """
        if session_id in self._active_sessions:
            logger.warning(
                f"FreeTierManager: session {session_id} already active for user {user_id}"
            )
            return {
                "session_id": session_id,
                "already_active": True,
                "usage": self.get_usage(user_id),
            }

        session = ActiveSession(
            session_id=session_id,
            user_id=user_id,
            started_at=time.time(),
            model=model,
        )
        self._active_sessions[session_id] = session
        logger.info(
            f"FreeTierManager: session started session_id={session_id} user={user_id}"
        )
        return {
            "session_id": session_id,
            "started_at": session.started_at,
            "usage": self.get_usage(user_id),
        }

    def record_session_end(self, user_id: str, session_id: str) -> dict:
        """Record the end of an agent session and update hours used.

        Args:
            user_id: The user identifier.
            session_id: Unique session identifier.

        Returns:
            dict with session info including hours consumed.
        """
        session = self._active_sessions.pop(session_id, None)
        if session is None:
            logger.warning(
                f"FreeTierManager: session {session_id} not found for user {user_id}"
            )
            return {
                "session_id": session_id,
                "error": "session not found",
                "usage": self.get_usage(user_id),
            }

        elapsed_hours = session.elapsed_hours()
        record = self._get_or_create_billing(user_id)
        record.hours_used += elapsed_hours
        record.last_updated = datetime.now(timezone.utc).isoformat()

        # Store completed session record
        completed = {
            "session_id": session_id,
            "user_id": user_id,
            "started_at": session.started_at,
            "ended_at": time.time(),
            "hours_consumed": round(elapsed_hours, 4),
            "model": session.model,
        }
        self._completed_sessions.append(completed)

        self._save()
        logger.info(
            f"FreeTierManager: session ended session_id={session_id} user={user_id} "
            f"hours={elapsed_hours:.4f}"
        )
        return {
            "session_id": session_id,
            "hours_consumed": round(elapsed_hours, 4),
            "usage": self.get_usage(user_id),
        }

    def get_active_sessions(self, user_id: str) -> List[dict]:
        """Return list of active sessions for user_id.

        Args:
            user_id: The user identifier.

        Returns:
            List of session dicts.
        """
        return [
            s.to_dict()
            for s in self._active_sessions.values()
            if s.user_id == user_id
        ]

    # ------------------------------------------------------------------
    # Public API: plan management
    # ------------------------------------------------------------------

    def set_user_plan(self, user_id: str, plan: str) -> dict:
        """Set the billing plan for a user.

        Args:
            user_id: The user identifier.
            plan: Plan name ('explorer', 'builder', 'team', 'organization').

        Returns:
            Updated plan info dict.
        """
        if plan not in PLAN_CONFIGS:
            raise ValueError(
                f"Unknown plan {plan!r}. Valid: {list(PLAN_CONFIGS)}"
            )
        record = self._get_or_create_billing(user_id)
        record.plan = plan
        record.last_updated = datetime.now(timezone.utc).isoformat()
        self._save()
        return self.get_plan(user_id)

    def reset_usage(self, user_id: str) -> dict:
        """Reset usage for user_id (e.g. for monthly reset or testing).

        Args:
            user_id: The user identifier.

        Returns:
            Updated usage dict.
        """
        record = self._get_or_create_billing(user_id)
        record.hours_used = 0.0
        record.period_start = _first_of_month_iso()
        record.last_updated = datetime.now(timezone.utc).isoformat()
        self._save()
        return self.get_usage(user_id)

    def get_upgrade_info(self) -> dict:
        """Return upgrade tier comparison info for the upgrade modal.

        Returns:
            dict with plan tiers and their features.
        """
        tiers = []
        for plan_name, cfg in PLAN_CONFIGS.items():
            tiers.append({
                "plan": plan_name,
                "display_name": cfg.display_name,
                "price_monthly": cfg.price_monthly,
                "agent_hours_limit": cfg.agent_hours_limit if cfg.agent_hours_limit != float("inf") else None,
                "max_concurrent_agents": cfg.max_concurrent_agents if cfg.max_concurrent_agents > 0 else None,
                "allowed_models": cfg.allowed_models,
                "allowed_integrations": cfg.allowed_integrations,
                "features": _get_plan_features(plan_name),
            })
        return {
            "tiers": tiers,
            "upgrade_url": "https://agentdashboard.ai/upgrade",
        }

    def add_hours_for_testing(self, user_id: str, hours: float) -> dict:
        """Add hours to a user's usage (for testing/admin purposes).

        Args:
            user_id: The user identifier.
            hours: Number of hours to add.

        Returns:
            Updated usage dict.
        """
        record = self._get_or_create_billing(user_id)
        record.hours_used += hours
        record.last_updated = datetime.now(timezone.utc).isoformat()
        self._save()
        return self.get_usage(user_id)


def _get_plan_features(plan_name: str) -> List[str]:
    """Return human-readable feature list for a plan."""
    features_map = {
        "explorer": [
            "10 agent-hours/month",
            "Claude Haiku only",
            "1 concurrent agent",
            "GitHub integration",
            "Community support",
        ],
        "builder": [
            "50 agent-hours/month",
            "Claude Haiku, Sonnet & Opus",
            "5 concurrent agents",
            "GitHub, Slack, Jira & Linear",
            "Email support",
        ],
        "team": [
            "200 agent-hours/month",
            "All Claude models",
            "20 concurrent agents",
            "All integrations",
            "Priority support",
        ],
        "organization": [
            "Unlimited agent-hours",
            "All Claude models",
            "Unlimited concurrent agents",
            "All integrations + custom",
            "Dedicated support",
            "SSO & SAML",
            "Audit logs",
        ],
    }
    return features_map.get(plan_name, [])


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_global_free_tier_manager: Optional[FreeTierManager] = None


def get_free_tier_manager() -> FreeTierManager:
    """Get the global FreeTierManager singleton (lazy init).

    Returns:
        FreeTierManager instance
    """
    global _global_free_tier_manager
    if _global_free_tier_manager is None:
        _global_free_tier_manager = FreeTierManager()
    return _global_free_tier_manager


def reset_free_tier_manager() -> None:
    """Reset the global FreeTierManager singleton (useful for testing)."""
    global _global_free_tier_manager
    _global_free_tier_manager = None
