"""Analytics Exporter for advanced analytics (AI-249).

Generates JSON-serialisable monthly digest reports and writes them to disk.
PDF export is implemented as JSON export (no PDF library dependency).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from analytics.efficiency import AgentEfficiencyAnalyzer
from analytics.cost_optimizer import CostOptimizer
from analytics.model_performance import ModelPerformanceComparator
from analytics.sprint_velocity import SprintVelocityTracker


class AnalyticsExporter:
    """Assembles and exports full monthly analytics reports.

    The report is a JSON-serialisable dict containing all four analytics
    sections (efficiency, costs, model performance, sprint velocity).
    """

    def __init__(self) -> None:
        self._efficiency = AgentEfficiencyAnalyzer()
        self._costs = CostOptimizer()
        self._models = ModelPerformanceComparator()
        self._velocity = SprintVelocityTracker()

    def export_monthly_report(
        self, org_id: str, month: Optional[str] = None
    ) -> Dict:
        """Build a complete monthly analytics report for an organisation.

        Args:
            org_id: Organisation identifier.
            month: Target month in 'YYYY-MM' format.  If None, defaults to
                   the current UTC month.

        Returns:
            JSON-serialisable dict with keys:
                - org_id (str)
                - month (str): 'YYYY-MM'
                - generated_at (str): ISO-8601 timestamp
                - sections (dict):
                    - efficiency: agent efficiency summary
                    - costs: cost optimisation summary
                    - model_performance: provider comparison
                    - sprint_velocity: velocity metrics
        """
        if month is None:
            now = datetime.now(timezone.utc)
            month = f"{now.year}-{now.month:02d}"

        generated_at = datetime.now(timezone.utc).isoformat()

        efficiency_data = {
            "agent_rankings": self._efficiency.rank_agents_by_efficiency(),
            "success_rate_trends": {
                agent: self._efficiency.get_success_rate_trend(agent, days=30)
                for agent in ["coding", "pr_reviewer", "linear", "github"]
            },
            "idle_vs_active": {
                agent: self._efficiency.get_idle_vs_active_ratio(agent)
                for agent in ["coding", "pr_reviewer", "linear", "github"]
            },
        }

        costs_data = {
            "cost_per_ticket_by_tier": self._costs.get_cost_per_ticket_by_tier(
                org_id, days=30
            ),
            "monthly_trend": self._costs.get_monthly_cost_trend(org_id, months=6),
            "roi": self._costs.calculate_roi(org_id),
            "overage_risk": self._costs.check_overage_risk(org_id),
        }

        model_data = {
            "quality_scores": self._models.get_quality_scores_by_provider(),
            "task_affinity": self._models.get_task_affinity_matrix(),
            "cross_validation_agreement_rate": (
                self._models.get_crossvalidation_agreement_rate()
            ),
        }

        velocity_data = {
            "weekly_velocity": self._velocity.get_weekly_velocity(
                org_id, weeks=4
            ),
            "trend_line": self._velocity.get_velocity_trend_line(org_id),
            "blocked_analysis": self._velocity.get_blocked_tickets_analysis(
                org_id
            ),
        }

        return {
            "org_id": org_id,
            "month": month,
            "generated_at": generated_at,
            "sections": {
                "efficiency": efficiency_data,
                "costs": costs_data,
                "model_performance": model_data,
                "sprint_velocity": velocity_data,
            },
        }

    def export_to_json(self, data: Dict, filepath: str) -> str:
        """Write a report dict to a JSON file on disk.

        Args:
            data: JSON-serialisable dict (e.g. the output of
                  export_monthly_report).
            filepath: Destination file path.  Parent directories are
                      created if they do not exist.

        Returns:
            Absolute path to the written file as a string.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        return str(path.resolve())
