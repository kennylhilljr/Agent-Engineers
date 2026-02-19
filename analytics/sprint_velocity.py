"""Sprint Velocity Tracker for advanced analytics (AI-249).

Provides sprint cadence metrics for Organisation/Fleet tiers:
- Weekly velocity (tickets completed per sprint)
- Velocity trend line with linear regression
- Blocked tickets and blockers analysis
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List

_RANDOM_SEED = 42


def _org_seed(org_id: str) -> int:
    """Deterministic seed derived from org_id."""
    return _RANDOM_SEED + (hash(org_id) % 500)


def _linear_regression(xs: List[float], ys: List[float]) -> Dict:
    """Compute simple linear regression y = slope * x + intercept.

    Args:
        xs: Independent variable values.
        ys: Dependent variable values.

    Returns:
        Dict with slope, intercept, r_squared.
    """
    n = len(xs)
    if n < 2:
        return {"slope": 0.0, "intercept": float(ys[0]) if ys else 0.0, "r_squared": 0.0}

    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_xx = sum(x * x for x in xs)

    denom = n * sum_xx - sum_x ** 2
    if denom == 0:
        return {"slope": 0.0, "intercept": sum_y / n, "r_squared": 0.0}

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    # R-squared
    y_mean = sum_y / n
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r_squared = 1 - ss_res / max(ss_tot, 1e-10)

    return {
        "slope": round(slope, 4),
        "intercept": round(intercept, 4),
        "r_squared": round(max(0.0, r_squared), 4),
    }


# Blocker categories and their relative frequency
_BLOCKER_CATEGORIES = {
    "waiting_on_review": 0.35,
    "external_dependency": 0.25,
    "scope_unclear": 0.20,
    "failing_tests": 0.12,
    "merge_conflict": 0.08,
}


class SprintVelocityTracker:
    """Tracks sprint velocity and blocked ticket metrics per organisation.

    All data is synthetic with deterministic randomness per org_id.
    """

    def get_weekly_velocity(
        self, org_id: str, weeks: int = 12
    ) -> List[Dict]:
        """Return weekly ticket velocity for the given number of sprints.

        Args:
            org_id: Organisation identifier.
            weeks: Number of weeks of history to return (default 12).

        Returns:
            List of dicts ordered oldest-to-newest:
                [{"week_start": "YYYY-MM-DD",
                  "week_number": int,
                  "tickets_completed": int,
                  "tickets_started": int,
                  "carry_over": int}, ...]
        """
        rng = random.Random(_org_seed(org_id))
        weeks = max(1, int(weeks))
        today = datetime.now(timezone.utc).date()
        # Start on the most recent Monday
        monday = today - timedelta(days=today.weekday())
        base_velocity = rng.randint(15, 45)
        result = []

        for i in range(weeks):
            week_start = monday - timedelta(weeks=weeks - 1 - i)
            # Gradual velocity improvement with noise
            growth = 1 + (i / weeks) * 0.18
            noise = rng.gauss(0, 0.12)
            velocity = max(1, int(base_velocity * growth * (1 + noise)))
            started = velocity + rng.randint(0, 8)
            carry_over = max(0, started - velocity)
            result.append(
                {
                    "week_start": week_start.isoformat(),
                    "week_number": i + 1,
                    "tickets_completed": velocity,
                    "tickets_started": started,
                    "carry_over": carry_over,
                }
            )
        return result

    def get_velocity_trend_line(self, org_id: str) -> Dict:
        """Return a linear regression trend line for sprint velocity.

        Uses the last 12 weeks of velocity data.

        Args:
            org_id: Organisation identifier.

        Returns:
            Dict with keys:
                - slope (float): weekly change in ticket velocity
                - intercept (float): projected velocity at week 0
                - r_squared (float): goodness-of-fit 0-1
                - trend (str): 'improving' | 'declining' | 'stable'
                - weeks_analysed (int)
        """
        weekly_data = self.get_weekly_velocity(org_id, weeks=12)
        xs = [float(entry["week_number"]) for entry in weekly_data]
        ys = [float(entry["tickets_completed"]) for entry in weekly_data]

        regression = _linear_regression(xs, ys)
        slope = regression["slope"]

        if slope > 0.5:
            trend = "improving"
        elif slope < -0.5:
            trend = "declining"
        else:
            trend = "stable"

        return {
            **regression,
            "trend": trend,
            "weeks_analysed": len(weekly_data),
        }

    def get_blocked_tickets_analysis(self, org_id: str) -> Dict:
        """Return analysis of blocked tickets and their root causes.

        Args:
            org_id: Organisation identifier.

        Returns:
            Dict with keys:
                - org_id (str)
                - total_blocked (int)
                - avg_blocked_per_sprint (float)
                - blocked_fraction (float): fraction of all tickets blocked
                - blockers_breakdown (dict): category -> count
                - longest_blocked_days (int): max days a ticket was blocked
                - resolved_this_week (int)
        """
        rng = random.Random(_org_seed(org_id))
        weekly = self.get_weekly_velocity(org_id, weeks=4)
        total_started = sum(w["tickets_started"] for w in weekly)

        # ~12% of tickets experience a block
        blocked_fraction = rng.uniform(0.08, 0.18)
        total_blocked = int(total_started * blocked_fraction)

        breakdown: Dict[str, int] = {}
        remaining = total_blocked
        categories = list(_BLOCKER_CATEGORIES.items())
        for idx, (category, fraction) in enumerate(categories):
            if idx == len(categories) - 1:
                breakdown[category] = remaining
            else:
                count = int(total_blocked * fraction)
                breakdown[category] = count
                remaining -= count

        resolved_this_week = rng.randint(2, min(10, total_blocked))
        longest_blocked = rng.randint(3, 14)

        return {
            "org_id": org_id,
            "total_blocked": total_blocked,
            "avg_blocked_per_sprint": round(total_blocked / 4, 2),
            "blocked_fraction": round(blocked_fraction, 4),
            "blockers_breakdown": breakdown,
            "longest_blocked_days": longest_blocked,
            "resolved_this_week": resolved_this_week,
        }
