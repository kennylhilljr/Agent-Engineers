"""Agent Efficiency Analyzer for advanced analytics (AI-249).

Provides synthetic but realistic efficiency metrics for agent types:
- Success rate trends over rolling windows
- Average time-to-completion per ticket type
- Idle vs active time ratios
- Agent efficiency rankings
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# Seed for reproducible synthetic data per test calls
_RANDOM_SEED = 42

# Known agent types and baseline metrics
_AGENT_BASELINES: Dict[str, Dict] = {
    "coding": {
        "success_rate": 0.87,
        "avg_completion_minutes": 18.5,
        "idle_ratio": 0.25,
    },
    "pr_reviewer": {
        "success_rate": 0.93,
        "avg_completion_minutes": 8.2,
        "idle_ratio": 0.40,
    },
    "linear": {
        "success_rate": 0.95,
        "avg_completion_minutes": 4.1,
        "idle_ratio": 0.55,
    },
    "github": {
        "success_rate": 0.90,
        "avg_completion_minutes": 6.3,
        "idle_ratio": 0.50,
    },
    "ops": {
        "success_rate": 0.91,
        "avg_completion_minutes": 5.5,
        "idle_ratio": 0.60,
    },
    "product_manager": {
        "success_rate": 0.82,
        "avg_completion_minutes": 22.0,
        "idle_ratio": 0.30,
    },
    "designer": {
        "success_rate": 0.79,
        "avg_completion_minutes": 30.0,
        "idle_ratio": 0.20,
    },
    "slack": {
        "success_rate": 0.97,
        "avg_completion_minutes": 2.0,
        "idle_ratio": 0.70,
    },
}

_DEFAULT_BASELINE = {
    "success_rate": 0.85,
    "avg_completion_minutes": 15.0,
    "idle_ratio": 0.40,
}

# Ticket types and relative completion time multipliers
_TICKET_TYPE_MULTIPLIERS: Dict[str, float] = {
    "feature": 1.4,
    "bug": 0.9,
    "chore": 0.6,
    "review": 0.7,
    "deploy": 0.5,
    "design": 1.8,
    "research": 2.2,
}


class AgentEfficiencyAnalyzer:
    """Analyzes agent performance efficiency metrics.

    All data is synthetic but shaped to be realistic for the product.
    In production this would query a telemetry store; here it returns
    computed mock data.
    """

    def get_success_rate_trend(
        self, agent_type: str, days: int = 30
    ) -> List[Dict]:
        """Return daily success rate trend over the given rolling window.

        Args:
            agent_type: Agent type identifier (e.g. 'coding', 'pr_reviewer').
            days: Number of days of history to return (7, 30, or 90).

        Returns:
            List of dicts ordered oldest-to-newest:
                [{"date": "YYYY-MM-DD", "rate": float, "total": int}, ...]
        """
        days = max(1, int(days))
        baseline = _AGENT_BASELINES.get(agent_type, _DEFAULT_BASELINE)
        base_rate = baseline["success_rate"]

        rng = random.Random(_RANDOM_SEED + hash(agent_type) % 100)
        today = datetime.now(timezone.utc).date()
        result = []
        for i in range(days):
            day = today - timedelta(days=days - 1 - i)
            # Small sinusoidal variation around the baseline
            noise = rng.gauss(0, 0.04)
            trend_boost = (i / days) * 0.03  # slight upward trend
            rate = max(0.0, min(1.0, base_rate + noise + trend_boost))
            total = rng.randint(5, 40)
            result.append(
                {
                    "date": day.isoformat(),
                    "rate": round(rate, 4),
                    "total": total,
                    "succeeded": round(total * rate),
                }
            )
        return result

    def get_avg_completion_time(
        self, agent_type: str, ticket_type: Optional[str] = None
    ) -> float:
        """Return average time-to-completion in minutes.

        Args:
            agent_type: Agent type identifier.
            ticket_type: Optional ticket type to filter by (e.g. 'bug',
                         'feature'). If None, returns the overall average.

        Returns:
            Average completion time in minutes (float).
        """
        baseline = _AGENT_BASELINES.get(agent_type, _DEFAULT_BASELINE)
        avg = baseline["avg_completion_minutes"]
        if ticket_type:
            multiplier = _TICKET_TYPE_MULTIPLIERS.get(ticket_type, 1.0)
            avg = avg * multiplier
        # Add a small deterministic noise
        rng = random.Random(_RANDOM_SEED + hash(agent_type) % 100)
        noise = rng.gauss(0, 0.5)
        return round(max(0.5, avg + noise), 2)

    def get_idle_vs_active_ratio(self, agent_type: str) -> Dict:
        """Return idle vs active time breakdown for an agent type.

        Args:
            agent_type: Agent type identifier.

        Returns:
            Dict with keys:
                - idle_ratio (float 0-1): proportion of time idle
                - active_ratio (float 0-1): proportion of time active
                - idle_hours_per_day (float): estimated idle hours per day
                - active_hours_per_day (float): estimated active hours per day
        """
        baseline = _AGENT_BASELINES.get(agent_type, _DEFAULT_BASELINE)
        idle = baseline["idle_ratio"]
        active = 1.0 - idle
        hours_per_day = 8.0  # standard working day
        return {
            "agent_type": agent_type,
            "idle_ratio": round(idle, 4),
            "active_ratio": round(active, 4),
            "idle_hours_per_day": round(idle * hours_per_day, 2),
            "active_hours_per_day": round(active * hours_per_day, 2),
        }

    def rank_agents_by_efficiency(self) -> List[Dict]:
        """Return all known agent types ranked by efficiency score.

        Efficiency score is a composite of:
        - Success rate (weighted 50%)
        - Inverse of relative completion time (weighted 30%)
        - Active ratio / not idle (weighted 20%)

        Returns:
            List of dicts ordered best-to-worst:
                [{"rank": int, "agent_type": str, "efficiency_score": float,
                  "success_rate": float, "avg_completion_minutes": float,
                  "active_ratio": float}, ...]
        """
        scores = []
        # Normalise completion times across agents for scoring
        all_times = [b["avg_completion_minutes"] for b in _AGENT_BASELINES.values()]
        max_time = max(all_times)
        min_time = min(all_times)
        time_range = max(max_time - min_time, 1.0)

        for agent_type, baseline in _AGENT_BASELINES.items():
            success_rate = baseline["success_rate"]
            completion = baseline["avg_completion_minutes"]
            idle = baseline["idle_ratio"]
            active = 1.0 - idle

            # Normalised speed score: shorter = higher score
            speed_score = 1.0 - (completion - min_time) / time_range

            efficiency = (
                0.50 * success_rate
                + 0.30 * speed_score
                + 0.20 * active
            )
            scores.append(
                {
                    "agent_type": agent_type,
                    "efficiency_score": round(efficiency, 4),
                    "success_rate": success_rate,
                    "avg_completion_minutes": completion,
                    "active_ratio": round(active, 4),
                }
            )

        scores.sort(key=lambda x: x["efficiency_score"], reverse=True)
        for i, entry in enumerate(scores):
            entry["rank"] = i + 1
        return scores
