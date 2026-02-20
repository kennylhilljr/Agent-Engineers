"""Billing tier definitions for Agent Dashboard (AI-247).

Defines all 5 pricing tiers for GA launch:
- Explorer (Free)
- Builder
- Team
- Organization
- Fleet (Enterprise)
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TierDefinition:
    """Complete definition of a pricing tier.

    Attributes:
        tier_id: Unique identifier for the tier (e.g., 'explorer', 'builder').
        name: Display name for the tier.
        monthly_price_usd: Monthly price in USD (0 for free/custom tiers).
        annual_price_usd: Annual price in USD per month (None for free/custom).
        agent_hours_per_month: Agent-hours included per billing cycle.
        concurrent_agents: Max number of concurrent agents allowed.
        allowed_models: List of model identifiers allowed for this tier.
        features: List of feature flags available on this tier.
        overage_rate_per_hour: USD charged per agent-hour over the limit.
        premium_model_surcharge: Additional USD per agent-hour for premium models.
        trial_days: Number of trial days (0 if no trial).
        is_custom_pricing: True for enterprise tiers with custom pricing.
        min_monthly_price: Minimum monthly commitment for custom tiers.
    """

    tier_id: str
    name: str
    monthly_price_usd: float
    annual_price_usd: Optional[float]
    agent_hours_per_month: Optional[int]  # None = unlimited
    concurrent_agents: Optional[int]      # None = unlimited
    allowed_models: List[str]
    features: List[str]
    overage_rate_per_hour: float = 0.50
    premium_model_surcharge: float = 1.50
    trial_days: int = 0
    is_custom_pricing: bool = False
    min_monthly_price: Optional[float] = None


# ---------------------------------------------------------------------------
# Model identifiers
# ---------------------------------------------------------------------------

HAIKU_MODELS = [
    "claude-haiku-3",
    "claude-haiku-3-5",
]

SONNET_MODELS = [
    "claude-sonnet-3-5",
    "claude-sonnet-4",
    "claude-sonnet-4-5",
]

PREMIUM_MODELS = [
    "claude-opus-3",
    "claude-opus-4",
    "claude-opus-4-6",
    "gpt-4o",
    "o1",
    "o1-mini",
    "o3",
]

EXTENDED_MODELS = [
    "gemini-1-5-pro",
    "gemini-2-0-flash",
    "gemini-2-0-pro",
    "mistral-large",
    "llama-3-70b",
    "deepseek-r1",
]

ALL_CLAUDE_MODELS = HAIKU_MODELS + SONNET_MODELS + PREMIUM_MODELS[:3]

ALL_STANDARD_MODELS = ALL_CLAUDE_MODELS + ["gpt-4o", "gemini-1-5-pro", "gemini-2-0-flash"]

ALL_MODELS = HAIKU_MODELS + SONNET_MODELS + PREMIUM_MODELS + EXTENDED_MODELS


# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------

EXPLORER_TIER = TierDefinition(
    tier_id="explorer",
    name="Explorer",
    monthly_price_usd=0.0,
    annual_price_usd=None,
    agent_hours_per_month=10,
    concurrent_agents=1,
    allowed_models=HAIKU_MODELS,
    features=[
        "basic_dashboard",
        "single_agent",
        "community_support",
    ],
    overage_rate_per_hour=0.0,   # No overage on free tier – hard cap
    premium_model_surcharge=0.0,
    trial_days=0,
    is_custom_pricing=False,
)

BUILDER_TIER = TierDefinition(
    tier_id="builder",
    name="Builder",
    monthly_price_usd=49.0,
    annual_price_usd=39.0,
    agent_hours_per_month=100,
    concurrent_agents=3,
    allowed_models=HAIKU_MODELS + SONNET_MODELS,
    features=[
        "basic_dashboard",
        "multi_agent",
        "usage_analytics",
        "email_support",
        "webhooks",
    ],
    overage_rate_per_hour=0.50,
    premium_model_surcharge=1.50,
    trial_days=14,
    is_custom_pricing=False,
)

TEAM_TIER = TierDefinition(
    tier_id="team",
    name="Team",
    monthly_price_usd=199.0,
    annual_price_usd=149.0,
    agent_hours_per_month=500,
    concurrent_agents=10,
    allowed_models=ALL_CLAUDE_MODELS + ["gpt-4o", "gemini-1-5-pro", "gemini-2-0-flash"],
    features=[
        "basic_dashboard",
        "advanced_dashboard",
        "multi_agent",
        "usage_analytics",
        "team_management",
        "rbac",
        "audit_log",
        "email_support",
        "priority_support",
        "webhooks",
        "slack_integration",
        "linear_integration",
        "github_integration",
    ],
    overage_rate_per_hour=0.50,
    premium_model_surcharge=1.50,
    trial_days=14,
    is_custom_pricing=False,
)

ORGANIZATION_TIER = TierDefinition(
    tier_id="organization",
    name="Organization",
    monthly_price_usd=799.0,
    annual_price_usd=599.0,
    agent_hours_per_month=2000,
    concurrent_agents=25,
    allowed_models=ALL_STANDARD_MODELS,
    features=[
        "basic_dashboard",
        "advanced_dashboard",
        "multi_agent",
        "usage_analytics",
        "team_management",
        "rbac",
        "audit_log",
        "sso_saml",
        "sso_oidc",
        "email_support",
        "priority_support",
        "dedicated_support",
        "webhooks",
        "slack_integration",
        "linear_integration",
        "github_integration",
        "custom_integrations",
        "sla_99_9",
    ],
    overage_rate_per_hour=0.50,
    premium_model_surcharge=1.50,
    trial_days=14,
    is_custom_pricing=False,
)

FLEET_TIER = TierDefinition(
    tier_id="fleet",
    name="Fleet",
    monthly_price_usd=0.0,    # Custom pricing
    annual_price_usd=None,
    agent_hours_per_month=None,   # Unlimited
    concurrent_agents=None,       # Unlimited
    allowed_models=ALL_MODELS + ["byo_model"],
    features=[
        "basic_dashboard",
        "advanced_dashboard",
        "multi_agent",
        "usage_analytics",
        "team_management",
        "rbac",
        "audit_log",
        "sso_saml",
        "sso_oidc",
        "scim",
        "email_support",
        "priority_support",
        "dedicated_support",
        "customer_success_manager",
        "webhooks",
        "slack_integration",
        "linear_integration",
        "github_integration",
        "custom_integrations",
        "byo_model",
        "on_premise_option",
        "custom_sla",
        "sla_99_9",
        "sla_99_99",
        "volume_discounts",
    ],
    overage_rate_per_hour=0.0,    # Negotiated per contract
    premium_model_surcharge=0.0,  # Negotiated per contract
    trial_days=0,
    is_custom_pricing=True,
    min_monthly_price=5000.0,
)


# ---------------------------------------------------------------------------
# Tier registry
# ---------------------------------------------------------------------------

TIERS: dict[str, TierDefinition] = {
    "explorer": EXPLORER_TIER,
    "builder": BUILDER_TIER,
    "team": TEAM_TIER,
    "organization": ORGANIZATION_TIER,
    "fleet": FLEET_TIER,
}

# Ordered tier progression (for upgrade/downgrade logic)
TIER_ORDER = ["explorer", "builder", "team", "organization", "fleet"]


def get_tier(tier_id: str) -> TierDefinition:
    """Return a TierDefinition by ID.

    Args:
        tier_id: The tier identifier (case-insensitive).

    Returns:
        TierDefinition for the requested tier.

    Raises:
        ValueError: If the tier_id is not recognised.
    """
    tier = TIERS.get(tier_id.lower())
    if tier is None:
        valid = ", ".join(TIERS.keys())
        raise ValueError(f"Unknown tier '{tier_id}'. Valid tiers: {valid}")
    return tier


def is_upgrade(from_tier: str, to_tier: str) -> bool:
    """Return True if moving from_tier to to_tier is an upgrade."""
    try:
        return TIER_ORDER.index(to_tier) > TIER_ORDER.index(from_tier)
    except ValueError:
        return False


def is_downgrade(from_tier: str, to_tier: str) -> bool:
    """Return True if moving from_tier to to_tier is a downgrade."""
    try:
        return TIER_ORDER.index(to_tier) < TIER_ORDER.index(from_tier)
    except ValueError:
        return False
