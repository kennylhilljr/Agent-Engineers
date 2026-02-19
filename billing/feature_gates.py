"""Feature gate middleware for Agent Dashboard (AI-247).

Enforces tier-specific access controls for:
- Model access (which AI models a user can call)
- Concurrent agent limits
- Feature flag checks
- Decorator for gating endpoints by tier requirement
"""

import functools
import logging
from typing import Any, Callable, List, Optional

from .tiers import TIERS, TierDefinition, get_tier

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TierGateError(Exception):
    """Raised when a user attempts to use a feature not available on their tier."""

    def __init__(
        self,
        message: str,
        required_tier: Optional[str] = None,
        current_tier: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.required_tier = required_tier
        self.current_tier = current_tier


class ModelAccessDeniedError(TierGateError):
    """Raised when a user attempts to use a model not allowed on their tier."""


class ConcurrentAgentLimitError(TierGateError):
    """Raised when a user exceeds their concurrent agent limit."""


class FeatureNotAvailableError(TierGateError):
    """Raised when a user attempts to use a feature not on their tier."""


# ---------------------------------------------------------------------------
# Model access
# ---------------------------------------------------------------------------


def is_model_allowed(model_id: str, tier_id: str) -> bool:
    """Return True if the given model is accessible on the given tier.

    Args:
        model_id: Identifier of the AI model (e.g., 'claude-haiku-3').
        tier_id: The user's current tier identifier.

    Returns:
        True if the model is allowed; False otherwise.
    """
    try:
        tier = get_tier(tier_id)
    except ValueError:
        logger.warning("Unknown tier '%s' in model access check", tier_id)
        return False

    # Fleet tier allows BYO model (any string starting with "byo:")
    if "byo_model" in tier.allowed_models and model_id.startswith("byo:"):
        return True

    return model_id in tier.allowed_models


def check_model_access(model_id: str, tier_id: str) -> None:
    """Raise ModelAccessDeniedError if the model is not allowed on this tier.

    Args:
        model_id: Identifier of the AI model.
        tier_id: The user's current tier identifier.

    Raises:
        ModelAccessDeniedError: If the model is not available on the tier.
    """
    if not is_model_allowed(model_id, tier_id):
        tier = TIERS.get(tier_id)
        tier_name = tier.name if tier else tier_id
        raise ModelAccessDeniedError(
            f"Model '{model_id}' is not available on the {tier_name} tier. "
            f"Upgrade your plan to access this model.",
            current_tier=tier_id,
        )


# ---------------------------------------------------------------------------
# Concurrent agent limits
# ---------------------------------------------------------------------------


def check_concurrent_agent_limit(
    current_active_agents: int,
    tier_id: str,
) -> None:
    """Raise ConcurrentAgentLimitError if the user has hit their agent limit.

    Args:
        current_active_agents: Number of agents currently active for the user.
        tier_id: The user's current tier identifier.

    Raises:
        ConcurrentAgentLimitError: If the limit would be exceeded.
    """
    try:
        tier = get_tier(tier_id)
    except ValueError:
        logger.warning("Unknown tier '%s' in concurrent agent check", tier_id)
        raise ConcurrentAgentLimitError(
            f"Unknown tier '{tier_id}'",
            current_tier=tier_id,
        )

    if tier.concurrent_agents is None:
        # Unlimited (Fleet tier)
        return

    if current_active_agents >= tier.concurrent_agents:
        raise ConcurrentAgentLimitError(
            f"You have reached the maximum of {tier.concurrent_agents} concurrent "
            f"agent(s) on the {tier.name} tier. Upgrade to run more agents in parallel.",
            current_tier=tier_id,
        )


def get_concurrent_agent_limit(tier_id: str) -> Optional[int]:
    """Return the concurrent agent limit for a tier, or None if unlimited.

    Args:
        tier_id: The tier identifier.

    Returns:
        Integer limit or None for unlimited.
    """
    try:
        tier = get_tier(tier_id)
        return tier.concurrent_agents
    except ValueError:
        return 1  # Fail-safe to most restrictive


# ---------------------------------------------------------------------------
# Feature flag checks
# ---------------------------------------------------------------------------


def has_feature(feature: str, tier_id: str) -> bool:
    """Return True if the given feature is available on the tier.

    Args:
        feature: Feature flag identifier (e.g., 'audit_log', 'sso_saml').
        tier_id: The user's current tier identifier.

    Returns:
        True if the feature is available on the tier.
    """
    try:
        tier = get_tier(tier_id)
    except ValueError:
        logger.warning("Unknown tier '%s' in feature check", tier_id)
        return False
    return feature in tier.features


def require_feature(feature: str, tier_id: str) -> None:
    """Raise FeatureNotAvailableError if the feature is not on this tier.

    Args:
        feature: Feature flag identifier.
        tier_id: The user's current tier identifier.

    Raises:
        FeatureNotAvailableError: If the feature is not available.
    """
    if not has_feature(feature, tier_id):
        # Find the minimum tier that has the feature
        required_tier = _min_tier_for_feature(feature)
        tier = TIERS.get(tier_id)
        tier_name = tier.name if tier else tier_id
        msg = f"Feature '{feature}' is not available on the {tier_name} tier."
        if required_tier:
            required = TIERS[required_tier]
            msg += f" Upgrade to {required.name} or higher to access this feature."
        raise FeatureNotAvailableError(
            msg,
            required_tier=required_tier,
            current_tier=tier_id,
        )


def _min_tier_for_feature(feature: str) -> Optional[str]:
    """Return the ID of the lowest tier that includes the given feature."""
    from .tiers import TIER_ORDER
    for tier_id in TIER_ORDER:
        tier = TIERS[tier_id]
        if feature in tier.features:
            return tier_id
    return None


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def require_tier(minimum_tier: str) -> Callable:
    """Decorator factory that gates a function behind a minimum tier requirement.

    Usage::

        @require_tier("team")
        async def export_audit_log(request, user_tier):
            ...

    The decorated function must accept ``user_tier`` as its last positional
    argument or as a keyword argument.

    Args:
        minimum_tier: The minimum tier ID required (e.g., 'team').

    Returns:
        Decorator that enforces the tier gate.

    Raises:
        TierGateError: At call time if the user's tier is below the minimum.
    """
    from .tiers import TIER_ORDER

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract user_tier from kwargs or last positional arg
            user_tier: Optional[str] = kwargs.get("user_tier")
            if user_tier is None and args:
                user_tier = args[-1]

            if user_tier is None:
                raise TierGateError(
                    "No user_tier provided to tier-gated function.",
                )

            try:
                min_idx = TIER_ORDER.index(minimum_tier)
                user_idx = TIER_ORDER.index(user_tier)
            except ValueError as exc:
                raise TierGateError(f"Invalid tier in gate check: {exc}") from exc

            if user_idx < min_idx:
                required = TIERS[minimum_tier]
                current = TIERS.get(user_tier)
                current_name = current.name if current else user_tier
                raise TierGateError(
                    f"This feature requires the {required.name} tier or higher. "
                    f"You are currently on the {current_name} tier.",
                    required_tier=minimum_tier,
                    current_tier=user_tier,
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator
