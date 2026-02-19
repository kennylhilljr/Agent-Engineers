"""Overage calculation, trial status, and proration logic (AI-247).

Handles:
- Overage calculation for agent-hours beyond tier limits
- Trial period status tracking and expiry
- Proration logic for mid-cycle tier upgrades/downgrades
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from .pricing import (
    OVERAGE_RATE_PER_HOUR,
    PREMIUM_MODEL_SURCHARGE_PER_HOUR,
    TRIAL_DAYS,
    TRIAL_ELIGIBLE_TIERS,
    EXPLORER_HARD_CAP_HOURS,
)
from .tiers import get_tier

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class OverageResult:
    """Result of an overage calculation.

    Attributes:
        included_hours: Hours included in the tier subscription.
        used_hours: Hours actually consumed in the billing period.
        overage_hours: Hours beyond the tier limit.
        overage_charge_usd: Total overage charge in USD.
        premium_hours: Hours using premium models (subject to surcharge).
        premium_surcharge_usd: Surcharge for premium model hours.
        total_charge_usd: Combined overage + premium surcharge.
        is_hard_capped: True if the tier has a hard cap (no overage billing).
    """

    included_hours: Optional[int]
    used_hours: float
    overage_hours: float
    overage_charge_usd: float
    premium_hours: float
    premium_surcharge_usd: float
    total_charge_usd: float
    is_hard_capped: bool


@dataclass
class TrialStatus:
    """Trial period status for a user.

    Attributes:
        is_on_trial: True if currently in a trial period.
        trial_start: Unix timestamp when the trial started (None if never).
        trial_end: Unix timestamp when the trial ends (None if no trial).
        days_remaining: Days remaining in the trial (None if not on trial).
        has_converted: True if the trial converted to paid.
        is_expired: True if the trial period has ended without converting.
    """

    is_on_trial: bool
    trial_start: Optional[float]
    trial_end: Optional[float]
    days_remaining: Optional[int]
    has_converted: bool
    is_expired: bool


@dataclass
class ProrationResult:
    """Result of a proration calculation for tier changes.

    Attributes:
        credit_usd: Credit amount from unused days on the old tier.
        charge_usd: Charge for the remaining days on the new tier.
        net_charge_usd: Net charge (charge - credit); negative means credit.
        days_remaining: Days remaining in the current billing cycle.
        days_in_period: Total days in the billing period.
    """

    credit_usd: float
    charge_usd: float
    net_charge_usd: float
    days_remaining: int
    days_in_period: int


# ---------------------------------------------------------------------------
# Overage calculation
# ---------------------------------------------------------------------------


def calculate_overage(
    tier_id: str,
    used_hours: float,
    premium_hours: float = 0.0,
) -> OverageResult:
    """Calculate overage charges for a billing period.

    For Explorer tier, applies a hard cap (no overage billing — usage is
    blocked when the limit is reached).

    For paid tiers, charges $0.50/agent-hour beyond the included amount.
    Premium model hours (Opus, o1, etc.) incur an additional $1.50/hour
    surcharge on top of overage.

    Args:
        tier_id: The user's current tier identifier.
        used_hours: Total agent-hours consumed in the billing period.
        premium_hours: Subset of used_hours that used premium models.

    Returns:
        OverageResult with full breakdown of charges.
    """
    tier = get_tier(tier_id)
    included = tier.agent_hours_per_month

    # Unlimited tier (Fleet)
    if included is None:
        return OverageResult(
            included_hours=None,
            used_hours=used_hours,
            overage_hours=0.0,
            overage_charge_usd=0.0,
            premium_hours=premium_hours,
            premium_surcharge_usd=0.0,
            total_charge_usd=0.0,
            is_hard_capped=False,
        )

    overage_hours = max(0.0, used_hours - included)

    # Explorer: hard cap, no monetary overage
    if tier_id == "explorer":
        return OverageResult(
            included_hours=included,
            used_hours=used_hours,
            overage_hours=overage_hours,
            overage_charge_usd=0.0,
            premium_hours=premium_hours,
            premium_surcharge_usd=0.0,
            total_charge_usd=0.0,
            is_hard_capped=True,
        )

    overage_charge = overage_hours * OVERAGE_RATE_PER_HOUR
    premium_surcharge = premium_hours * PREMIUM_MODEL_SURCHARGE_PER_HOUR
    total = overage_charge + premium_surcharge

    return OverageResult(
        included_hours=included,
        used_hours=used_hours,
        overage_hours=overage_hours,
        overage_charge_usd=round(overage_charge, 2),
        premium_hours=premium_hours,
        premium_surcharge_usd=round(premium_surcharge, 2),
        total_charge_usd=round(total, 2),
        is_hard_capped=False,
    )


# ---------------------------------------------------------------------------
# Trial status
# ---------------------------------------------------------------------------


def get_trial_status(
    tier_id: str,
    trial_start_ts: Optional[float],
    has_converted: bool = False,
) -> TrialStatus:
    """Determine the current trial status for a user.

    Args:
        tier_id: The user's current tier identifier.
        trial_start_ts: Unix timestamp when the trial began, or None.
        has_converted: True if the user has already converted to paid.

    Returns:
        TrialStatus describing the trial state.
    """
    if tier_id not in TRIAL_ELIGIBLE_TIERS:
        return TrialStatus(
            is_on_trial=False,
            trial_start=None,
            trial_end=None,
            days_remaining=None,
            has_converted=False,
            is_expired=False,
        )

    if trial_start_ts is None:
        return TrialStatus(
            is_on_trial=False,
            trial_start=None,
            trial_end=None,
            days_remaining=None,
            has_converted=False,
            is_expired=False,
        )

    trial_end_ts = trial_start_ts + TRIAL_DAYS * 86400
    now = time.time()

    if has_converted:
        return TrialStatus(
            is_on_trial=False,
            trial_start=trial_start_ts,
            trial_end=trial_end_ts,
            days_remaining=None,
            has_converted=True,
            is_expired=False,
        )

    is_expired = now > trial_end_ts
    is_on_trial = not is_expired

    days_remaining: Optional[int] = None
    if is_on_trial:
        remaining_secs = trial_end_ts - now
        days_remaining = max(0, int(remaining_secs / 86400))

    return TrialStatus(
        is_on_trial=is_on_trial,
        trial_start=trial_start_ts,
        trial_end=trial_end_ts,
        days_remaining=days_remaining,
        has_converted=False,
        is_expired=is_expired,
    )


# ---------------------------------------------------------------------------
# Proration
# ---------------------------------------------------------------------------


def calculate_proration(
    from_tier_id: str,
    to_tier_id: str,
    current_period_start_ts: float,
    current_period_end_ts: float,
    billing_period: str = "monthly",
) -> ProrationResult:
    """Calculate proration for a mid-cycle tier change.

    For upgrades: credits unused days on old plan, charges remaining days
    on new plan. For downgrades: Stripe typically applies the credit at the
    next renewal; this function returns the theoretical proration amounts.

    Args:
        from_tier_id: Current tier identifier.
        to_tier_id: New tier identifier.
        current_period_start_ts: Unix timestamp of billing period start.
        current_period_end_ts: Unix timestamp of billing period end.
        billing_period: 'monthly' or 'annual'.

    Returns:
        ProrationResult with credit/charge breakdown.
    """
    from .pricing import TIER_PRICE_CONFIGS

    now = time.time()
    total_secs = current_period_end_ts - current_period_start_ts
    remaining_secs = max(0.0, current_period_end_ts - now)

    if total_secs <= 0:
        return ProrationResult(
            credit_usd=0.0,
            charge_usd=0.0,
            net_charge_usd=0.0,
            days_remaining=0,
            days_in_period=0,
        )

    days_in_period = int(total_secs / 86400) or 1
    days_remaining = int(remaining_secs / 86400)
    proration_fraction = remaining_secs / total_secs

    from_config = TIER_PRICE_CONFIGS.get(from_tier_id)
    to_config = TIER_PRICE_CONFIGS.get(to_tier_id)

    def monthly_price(config, period: str) -> float:
        if config is None:
            return 0.0
        if period == "annual" and config.annual_usd is not None:
            return config.annual_usd
        return config.monthly_usd

    from_price = monthly_price(from_config, billing_period)
    to_price = monthly_price(to_config, billing_period)

    credit = round(from_price * proration_fraction, 2)
    charge = round(to_price * proration_fraction, 2)
    net = round(charge - credit, 2)

    return ProrationResult(
        credit_usd=credit,
        charge_usd=charge,
        net_charge_usd=net,
        days_remaining=days_remaining,
        days_in_period=days_in_period,
    )
