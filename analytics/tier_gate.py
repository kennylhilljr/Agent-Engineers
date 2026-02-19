"""Tier gate for advanced analytics feature (AI-249).

Controls access to the analytics dashboard based on subscription tier.
Only Organization, Fleet, and Enterprise tier customers may access
advanced analytics.
"""

from __future__ import annotations

from typing import List


# Tiers that have access to advanced analytics
ANALYTICS_TIERS: List[str] = ["organization", "fleet", "enterprise"]


class TierGate:
    """Gate that controls access to advanced analytics based on billing tier.

    Usage
    -----
        gate = TierGate()
        if gate.is_analytics_enabled(user_tier):
            # serve analytics data
        else:
            # return 403
    """

    #: Tiers that are allowed to use the analytics feature.
    ANALYTICS_TIERS: List[str] = ANALYTICS_TIERS

    def is_analytics_enabled(self, tier: str) -> bool:
        """Return True if the given tier has access to advanced analytics.

        Args:
            tier: Billing tier identifier (case-insensitive), e.g.
                  'explorer', 'builder', 'team', 'organization', 'fleet'.

        Returns:
            True when ``tier`` is one of the analytics-enabled tiers,
            False otherwise.
        """
        if not tier:
            return False
        return tier.lower() in self.ANALYTICS_TIERS
