"""Agent Status Dashboard - Metrics collection, gamification, and visualization.

Provides instrumentation for tracking agent performance, XP/level progression,
achievements, and real-time dashboard views (CLI and web).
"""

from dashboard.collector import AgentMetricsCollector
from dashboard.metrics import AgentEvent, AgentProfile, DashboardState, SessionSummary
from dashboard.metrics_store import MetricsStore

__all__ = [
    "AgentMetricsCollector",
    "AgentEvent",
    "AgentProfile",
    "DashboardState",
    "MetricsStore",
    "SessionSummary",
]
