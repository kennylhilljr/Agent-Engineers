"""Analytics package for Agent Dashboard (AI-249).

Provides advanced analytics for Organization and Fleet tier customers:
- Agent Efficiency Analysis
- Cost Optimization
- Model Performance Comparison
- Sprint Velocity Tracking
- Report Export
- Tier Gating

Usage
-----
    from analytics import TierGate, AgentEfficiencyAnalyzer, CostOptimizer
    from analytics import ModelPerformanceComparator, SprintVelocityTracker
    from analytics import AnalyticsExporter
"""

from analytics.tier_gate import TierGate
from analytics.efficiency import AgentEfficiencyAnalyzer
from analytics.cost_optimizer import CostOptimizer
from analytics.model_performance import ModelPerformanceComparator
from analytics.sprint_velocity import SprintVelocityTracker
from analytics.exporter import AnalyticsExporter

__all__ = [
    "TierGate",
    "AgentEfficiencyAnalyzer",
    "CostOptimizer",
    "ModelPerformanceComparator",
    "SprintVelocityTracker",
    "AnalyticsExporter",
]
