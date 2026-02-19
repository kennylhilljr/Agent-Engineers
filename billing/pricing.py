"""Stripe price IDs and pricing configuration for Agent Dashboard (AI-247).

Centralises all Stripe product/price ID references, overage rates, and
trial configuration for the GA launch pricing tiers.

Environment variables
---------------------
STRIPE_PRICE_EXPLORER             Free plan (no actual Stripe price)
STRIPE_PRICE_BUILDER_MONTHLY      Builder monthly price ID
STRIPE_PRICE_BUILDER_ANNUAL       Builder annual price ID
STRIPE_PRICE_TEAM_MONTHLY         Team monthly price ID
STRIPE_PRICE_TEAM_ANNUAL          Team annual price ID
STRIPE_PRICE_ORG_MONTHLY          Organization monthly price ID
STRIPE_PRICE_ORG_ANNUAL           Organization annual price ID
STRIPE_PRICE_FLEET                Fleet (Enterprise) – custom, negotiate
"""

import os
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Overage & surcharge rates (USD per agent-hour)
# ---------------------------------------------------------------------------

OVERAGE_RATE_PER_HOUR: float = float(
    os.environ.get("BILLING_OVERAGE_RATE", "0.50")
)

PREMIUM_MODEL_SURCHARGE_PER_HOUR: float = float(
    os.environ.get("BILLING_PREMIUM_SURCHARGE", "1.50")
)

# Hard cap agent-hours for Explorer tier (no overage billing on free tier)
EXPLORER_HARD_CAP_HOURS: int = 10


# ---------------------------------------------------------------------------
# Trial configuration
# ---------------------------------------------------------------------------

TRIAL_DAYS: int = int(os.environ.get("BILLING_TRIAL_DAYS", "14"))

# Tiers that support trials
TRIAL_ELIGIBLE_TIERS = frozenset({"builder", "team", "organization"})


# ---------------------------------------------------------------------------
# Stripe price ID configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TierPriceConfig:
    """Stripe price IDs for a billing tier.

    Attributes:
        tier_id: Internal tier identifier.
        monthly_price_id: Stripe Price ID for monthly billing (empty string if N/A).
        annual_price_id: Stripe Price ID for annual billing (empty string if N/A).
        monthly_usd: List price in USD per month.
        annual_usd: List price in USD per month when billed annually.
    """

    tier_id: str
    monthly_price_id: str
    annual_price_id: str
    monthly_usd: float
    annual_usd: Optional[float]


TIER_PRICE_CONFIGS: dict[str, TierPriceConfig] = {
    "explorer": TierPriceConfig(
        tier_id="explorer",
        monthly_price_id="",  # Free – no Stripe price
        annual_price_id="",
        monthly_usd=0.0,
        annual_usd=None,
    ),
    "builder": TierPriceConfig(
        tier_id="builder",
        monthly_price_id=os.environ.get(
            "STRIPE_PRICE_BUILDER_MONTHLY", "price_builder_monthly"
        ),
        annual_price_id=os.environ.get(
            "STRIPE_PRICE_BUILDER_ANNUAL", "price_builder_annual"
        ),
        monthly_usd=49.0,
        annual_usd=39.0,
    ),
    "team": TierPriceConfig(
        tier_id="team",
        monthly_price_id=os.environ.get(
            "STRIPE_PRICE_TEAM_MONTHLY", "price_team_monthly"
        ),
        annual_price_id=os.environ.get(
            "STRIPE_PRICE_TEAM_ANNUAL", "price_team_annual"
        ),
        monthly_usd=199.0,
        annual_usd=149.0,
    ),
    "organization": TierPriceConfig(
        tier_id="organization",
        monthly_price_id=os.environ.get(
            "STRIPE_PRICE_ORG_MONTHLY", "price_org_monthly"
        ),
        annual_price_id=os.environ.get(
            "STRIPE_PRICE_ORG_ANNUAL", "price_org_annual"
        ),
        monthly_usd=799.0,
        annual_usd=599.0,
    ),
    "fleet": TierPriceConfig(
        tier_id="fleet",
        monthly_price_id=os.environ.get("STRIPE_PRICE_FLEET", "price_fleet_custom"),
        annual_price_id="",  # Negotiated per contract
        monthly_usd=0.0,     # Custom pricing
        annual_usd=None,
    ),
}


def get_stripe_price_id(tier_id: str, billing_period: str = "monthly") -> str:
    """Return the Stripe Price ID for a tier and billing period.

    Args:
        tier_id: The tier identifier (e.g., 'builder').
        billing_period: Either 'monthly' or 'annual'.

    Returns:
        The Stripe Price ID string (may be empty for free/custom tiers).

    Raises:
        ValueError: If tier_id or billing_period is invalid.
    """
    config = TIER_PRICE_CONFIGS.get(tier_id.lower())
    if config is None:
        valid = ", ".join(TIER_PRICE_CONFIGS.keys())
        raise ValueError(
            f"Unknown tier '{tier_id}'. Valid tiers: {valid}"
        )

    if billing_period == "monthly":
        return config.monthly_price_id
    elif billing_period == "annual":
        return config.annual_price_id
    else:
        raise ValueError(
            f"Invalid billing_period '{billing_period}'. Must be 'monthly' or 'annual'."
        )


def get_annual_savings_pct(tier_id: str) -> float:
    """Return the percentage savings of annual vs monthly billing.

    Args:
        tier_id: The tier identifier.

    Returns:
        Savings as a percentage (0.0 if no annual pricing).
    """
    config = TIER_PRICE_CONFIGS.get(tier_id.lower())
    if config is None or config.annual_usd is None or config.monthly_usd == 0:
        return 0.0
    return round((1 - config.annual_usd / config.monthly_usd) * 100, 1)
