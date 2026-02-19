"""Cost Optimizer for advanced analytics (AI-249).

Provides cost analysis and ROI calculations for Organization/Fleet tiers:
- Cost per ticket broken down by model tier (Haiku/Sonnet/Opus)
- Month-over-month cost trends
- Projected overage warnings
- ROI vs manual dev time
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Cost per 1K tokens for each model tier (approximate mid-2025 pricing)
_MODEL_TIER_COSTS: Dict[str, Dict[str, float]] = {
    "haiku": {
        "input_cost_per_1k": 0.00025,
        "output_cost_per_1k": 0.00125,
        "avg_tokens_per_ticket": 4_500,
    },
    "sonnet": {
        "input_cost_per_1k": 0.003,
        "output_cost_per_1k": 0.015,
        "avg_tokens_per_ticket": 6_200,
    },
    "opus": {
        "input_cost_per_1k": 0.015,
        "output_cost_per_1k": 0.075,
        "avg_tokens_per_ticket": 8_000,
    },
}

# Approximate ticket distribution by model tier
_DEFAULT_TIER_DISTRIBUTION = {
    "haiku": 0.55,
    "sonnet": 0.35,
    "opus": 0.10,
}

# Base monthly agent-hours for Organisation tier
_ORG_MONTHLY_AGENT_HOURS = 2_000

# Hourly rate we use as the "cost" proxy: $2.50/agent-hour average
_AGENT_HOUR_RATE = 2.50

# Fraction of monthly hours that generate overages (simulated per org)
_OVERAGE_THRESHOLD_FRACTION = 0.90

_RANDOM_SEED = 42


def _org_seed(org_id: str) -> int:
    """Deterministic seed derived from org_id for reproducible mock data."""
    return _RANDOM_SEED + (hash(org_id) % 500)


class CostOptimizer:
    """Analyses cost efficiency and ROI for an organisation.

    All data is synthetic/mock — no real DB required.
    """

    def get_cost_per_ticket_by_tier(
        self, org_id: str, days: int = 30
    ) -> Dict:
        """Return cost-per-ticket broken down by model tier.

        Args:
            org_id: Organisation identifier.
            days: Rolling window in days (default 30).

        Returns:
            Dict with keys:
                - org_id (str)
                - days (int)
                - by_model_tier (dict): haiku/sonnet/opus -> cost_per_ticket
                - blended_cost_per_ticket (float)
                - total_tickets (int)
                - total_cost_usd (float)
        """
        rng = random.Random(_org_seed(org_id))
        # Simulate ticket counts
        total_tickets = rng.randint(80, 400) * (days // 30 if days >= 30 else 1)
        by_tier: Dict[str, float] = {}
        total_cost = 0.0

        for tier, meta in _MODEL_TIER_COSTS.items():
            fraction = _DEFAULT_TIER_DISTRIBUTION[tier]
            tickets_for_tier = int(total_tickets * fraction)
            tokens = meta["avg_tokens_per_ticket"]
            cost_per_ticket = (
                tokens / 1000 * meta["input_cost_per_1k"] * 0.7
                + tokens / 1000 * meta["output_cost_per_1k"] * 0.3
            )
            cost_per_ticket = round(cost_per_ticket, 4)
            by_tier[tier] = {
                "cost_per_ticket": cost_per_ticket,
                "tickets": tickets_for_tier,
                "total_cost_usd": round(cost_per_ticket * tickets_for_tier, 4),
            }
            total_cost += cost_per_ticket * tickets_for_tier

        blended = total_cost / max(total_tickets, 1)
        return {
            "org_id": org_id,
            "days": days,
            "by_model_tier": by_tier,
            "blended_cost_per_ticket": round(blended, 4),
            "total_tickets": total_tickets,
            "total_cost_usd": round(total_cost, 4),
        }

    def get_monthly_cost_trend(
        self, org_id: str, months: int = 6
    ) -> List[Dict]:
        """Return month-over-month cost trend.

        Args:
            org_id: Organisation identifier.
            months: Number of months of history (default 6).

        Returns:
            List of dicts ordered oldest-to-newest:
                [{"month": "YYYY-MM", "cost_usd": float,
                  "tickets": int, "cost_per_ticket": float}, ...]
        """
        rng = random.Random(_org_seed(org_id))
        months = max(1, int(months))
        now = datetime.now(timezone.utc)
        result = []
        base_cost = rng.uniform(800.0, 2500.0)

        for i in range(months):
            month_offset = months - 1 - i
            # Calculate year/month offset
            month_num = now.month - month_offset
            year = now.year
            while month_num <= 0:
                month_num += 12
                year -= 1
            label = f"{year}-{month_num:02d}"
            # Slightly growing trend with noise
            growth = 1 + (i / months) * 0.12
            noise = rng.gauss(0, 0.08)
            cost = max(100.0, base_cost * growth * (1 + noise))
            tickets = rng.randint(80, 350)
            result.append(
                {
                    "month": label,
                    "cost_usd": round(cost, 2),
                    "tickets": tickets,
                    "cost_per_ticket": round(cost / max(tickets, 1), 4),
                }
            )
        return result

    def calculate_roi(
        self, org_id: str, manual_dev_hourly_rate: float = 150.0
    ) -> Dict:
        """Calculate ROI compared to manual dev time.

        Assumes each agent-completed ticket would have taken a developer
        an average of 2.5 hours to complete manually.

        Args:
            org_id: Organisation identifier.
            manual_dev_hourly_rate: Fully-loaded hourly rate for a developer
                                    in USD (default $150).

        Returns:
            Dict with keys:
                - org_id (str)
                - manual_dev_hourly_rate (float)
                - avg_manual_hours_per_ticket (float)
                - total_tickets_this_month (int)
                - manual_cost_this_month (float)
                - agent_cost_this_month (float)
                - cost_savings_usd (float)
                - roi_multiplier (float): manual_cost / agent_cost
                - payback_days (int): estimated days to break even
        """
        rng = random.Random(_org_seed(org_id))
        tickets = rng.randint(100, 350)
        avg_manual_hours = 2.5
        manual_cost = tickets * avg_manual_hours * manual_dev_hourly_rate

        # Agent cost: blended ~$0.08/ticket
        agent_cost_per_ticket = rng.uniform(0.05, 0.15)
        agent_cost = tickets * agent_cost_per_ticket

        savings = manual_cost - agent_cost
        roi_multiplier = manual_cost / max(agent_cost, 0.01)

        # Platform subscription cost for Organisation tier ($799/month)
        monthly_subscription = 799.0
        payback_days = int((monthly_subscription / max(savings / 30, 0.01)))

        return {
            "org_id": org_id,
            "manual_dev_hourly_rate": manual_dev_hourly_rate,
            "avg_manual_hours_per_ticket": avg_manual_hours,
            "total_tickets_this_month": tickets,
            "manual_cost_this_month": round(manual_cost, 2),
            "agent_cost_this_month": round(agent_cost, 2),
            "cost_savings_usd": round(savings, 2),
            "roi_multiplier": round(roi_multiplier, 2),
            "payback_days": payback_days,
        }

    def check_overage_risk(self, org_id: str) -> Dict:
        """Check if the organisation is at risk of hitting usage overages.

        Args:
            org_id: Organisation identifier.

        Returns:
            Dict with keys:
                - org_id (str)
                - monthly_limit_hours (int)
                - used_hours (float)
                - used_fraction (float 0-1)
                - days_remaining_in_period (int)
                - projected_total_hours (float)
                - at_risk (bool): True if projected total exceeds limit
                - overage_hours (float): projected hours over limit (0 if not at risk)
                - overage_cost_usd (float): projected overage cost
        """
        rng = random.Random(_org_seed(org_id))
        monthly_limit = _ORG_MONTHLY_AGENT_HOURS

        # Simulate current usage position in the billing cycle
        today = datetime.now(timezone.utc)
        day_of_month = today.day
        days_in_month = 30  # simplified
        days_remaining = days_in_month - day_of_month

        used_fraction = (day_of_month / days_in_month) * rng.uniform(0.85, 1.15)
        used_fraction = min(used_fraction, 1.0)
        used_hours = monthly_limit * used_fraction * rng.uniform(0.90, 1.10)
        used_hours = max(0.0, min(used_hours, monthly_limit * 1.5))

        daily_rate = used_hours / max(day_of_month, 1)
        projected_total = used_hours + daily_rate * days_remaining

        at_risk = projected_total > monthly_limit * _OVERAGE_THRESHOLD_FRACTION
        overage_hours = max(0.0, projected_total - monthly_limit)
        overage_cost = overage_hours * _AGENT_HOUR_RATE

        return {
            "org_id": org_id,
            "monthly_limit_hours": monthly_limit,
            "used_hours": round(used_hours, 2),
            "used_fraction": round(used_hours / monthly_limit, 4),
            "days_remaining_in_period": days_remaining,
            "projected_total_hours": round(projected_total, 2),
            "at_risk": at_risk,
            "overage_hours": round(overage_hours, 2),
            "overage_cost_usd": round(overage_cost, 2),
        }
