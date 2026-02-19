"""Subscription record store for Agent Dashboard (AI-221).

Persists Stripe subscription records to data/subscriptions.json.
Provides CRUD operations and grace period management.
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_SUBSCRIPTIONS_FILE = Path(__file__).parent.parent / "data" / "subscriptions.json"


@dataclass
class SubscriptionRecord:
    """A user's Stripe subscription record.

    Attributes:
        user_id: Internal user identifier.
        stripe_customer_id: Stripe customer ID (cus_...).
        stripe_subscription_id: Stripe subscription ID (sub_...).
        plan: Plan name ('explorer', 'builder', 'team', 'organization', 'fleet').
        status: Stripe subscription status (active, past_due, canceled, trialing, etc.)
            or 'free' for explorer users not in Stripe.
        current_period_end: Unix timestamp when current billing period ends.
        grace_period_end: Unix timestamp when grace period expires (None if not in grace).
        created_at: ISO timestamp when record was created.
        updated_at: ISO timestamp when record was last updated.
    """

    user_id: str
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    plan: str = "explorer"
    status: str = "free"
    current_period_end: Optional[int] = None
    grace_period_end: Optional[int] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def is_active(self) -> bool:
        """Return True if the subscription allows full access.

        A subscription is considered active if:
        - status is 'active' or 'trialing'
        - OR status is 'past_due' but within grace period
        - OR plan is 'explorer' (always active, free tier)
        """
        if self.plan == "explorer":
            return True
        if self.status in ("active", "trialing"):
            return True
        if self.status == "past_due" and self.grace_period_end is not None:
            return int(time.time()) < self.grace_period_end
        return False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_active"] = self.is_active()
        return d


class SubscriptionStore:
    """Persistent store for Stripe subscription records.

    Args:
        data_file: Path to JSON persistence file.
            Defaults to ``data/subscriptions.json`` in project root.
    """

    def __init__(self, data_file: Optional[Path] = None) -> None:
        self._data_file = data_file or DEFAULT_SUBSCRIPTIONS_FILE
        self._records: Dict[str, SubscriptionRecord] = {}  # user_id -> record
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load subscription records from JSON file."""
        try:
            if self._data_file.exists():
                raw = json.loads(self._data_file.read_text(encoding="utf-8"))
                for user_id, data in raw.items():
                    self._records[user_id] = SubscriptionRecord(
                        user_id=user_id,
                        stripe_customer_id=data.get("stripe_customer_id"),
                        stripe_subscription_id=data.get("stripe_subscription_id"),
                        plan=data.get("plan", "explorer"),
                        status=data.get("status", "free"),
                        current_period_end=data.get("current_period_end"),
                        grace_period_end=data.get("grace_period_end"),
                        created_at=data.get(
                            "created_at", datetime.now(timezone.utc).isoformat()
                        ),
                        updated_at=data.get(
                            "updated_at", datetime.now(timezone.utc).isoformat()
                        ),
                    )
                logger.debug(
                    f"SubscriptionStore: loaded {len(self._records)} records"
                )
        except Exception as exc:
            logger.warning(f"SubscriptionStore: could not load file: {exc}")

    def _save(self) -> None:
        """Persist subscription records to JSON file."""
        try:
            payload = {
                user_id: {
                    "stripe_customer_id": rec.stripe_customer_id,
                    "stripe_subscription_id": rec.stripe_subscription_id,
                    "plan": rec.plan,
                    "status": rec.status,
                    "current_period_end": rec.current_period_end,
                    "grace_period_end": rec.grace_period_end,
                    "created_at": rec.created_at,
                    "updated_at": rec.updated_at,
                }
                for user_id, rec in self._records.items()
            }
            self._data_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"SubscriptionStore: could not save file: {exc}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_subscription(self, user_id: str) -> Optional[SubscriptionRecord]:
        """Return the subscription record for a user, or None if not found.

        Args:
            user_id: Internal user identifier.

        Returns:
            SubscriptionRecord or None.
        """
        return self._records.get(user_id)

    def get_subscription_by_customer(
        self, stripe_customer_id: Optional[str]
    ) -> Optional[SubscriptionRecord]:
        """Return the subscription record matching a Stripe customer ID.

        Args:
            stripe_customer_id: Stripe customer ID (cus_...).

        Returns:
            SubscriptionRecord or None.
        """
        if not stripe_customer_id:
            return None
        for rec in self._records.values():
            if rec.stripe_customer_id == stripe_customer_id:
                return rec
        return None

    def upsert_subscription(
        self,
        user_id: str,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        plan: str = "explorer",
        status: str = "active",
        current_period_end: Optional[int] = None,
        grace_period_end: Optional[int] = None,
    ) -> SubscriptionRecord:
        """Create or update a subscription record.

        Args:
            user_id: Internal user identifier.
            stripe_customer_id: Stripe customer ID.
            stripe_subscription_id: Stripe subscription ID.
            plan: Plan name.
            status: Stripe subscription status.
            current_period_end: Unix timestamp for period end.
            grace_period_end: Unix timestamp for grace period end.

        Returns:
            The updated SubscriptionRecord.
        """
        now = datetime.now(timezone.utc).isoformat()

        existing = self._records.get(user_id)
        if existing:
            existing.stripe_customer_id = stripe_customer_id or existing.stripe_customer_id
            existing.stripe_subscription_id = (
                stripe_subscription_id
                if stripe_subscription_id is not None
                else existing.stripe_subscription_id
            )
            existing.plan = plan
            existing.status = status
            if current_period_end is not None:
                existing.current_period_end = current_period_end
            existing.grace_period_end = grace_period_end
            existing.updated_at = now
            record = existing
        else:
            record = SubscriptionRecord(
                user_id=user_id,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                plan=plan,
                status=status,
                current_period_end=current_period_end,
                grace_period_end=grace_period_end,
                created_at=now,
                updated_at=now,
            )
            self._records[user_id] = record

        self._save()
        return record

    def set_grace_period(self, user_id: str, days: int = 3) -> Optional[SubscriptionRecord]:
        """Set a grace period for a user's subscription.

        Args:
            user_id: Internal user identifier.
            days: Number of days for the grace period (default 3).

        Returns:
            Updated SubscriptionRecord, or None if user not found.
        """
        record = self._records.get(user_id)
        if not record:
            logger.warning(f"SubscriptionStore.set_grace_period: no record for user={user_id}")
            return None

        grace_end = int(time.time()) + days * 86400
        record.grace_period_end = grace_end
        record.status = "past_due"
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()
        logger.info(
            f"SubscriptionStore: grace period set for user={user_id} "
            f"expires={grace_end} (in {days} days)"
        )
        return record

    def is_in_grace_period(self, user_id: str) -> bool:
        """Return True if a user is currently in a grace period.

        Args:
            user_id: Internal user identifier.

        Returns:
            True if in grace period, False otherwise.
        """
        record = self._records.get(user_id)
        if not record:
            return False
        if record.grace_period_end is None:
            return False
        return int(time.time()) < record.grace_period_end

    def list_all(self) -> List[SubscriptionRecord]:
        """Return all subscription records."""
        return list(self._records.values())


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_global_subscription_store: Optional[SubscriptionStore] = None


def get_subscription_store() -> SubscriptionStore:
    """Return the global SubscriptionStore singleton (lazy init)."""
    global _global_subscription_store
    if _global_subscription_store is None:
        _global_subscription_store = SubscriptionStore()
    return _global_subscription_store


def reset_subscription_store() -> None:
    """Reset the global SubscriptionStore singleton (useful for testing)."""
    global _global_subscription_store
    _global_subscription_store = None
