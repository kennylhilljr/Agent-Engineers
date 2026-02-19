"""Automated Performance Benchmark Suite for Agent Dashboard (AI-248).

Measures agent quality, speed, and cost metrics on every PR merge.
Results are displayed in the dashboard and used for data-driven model routing.
"""

from benchmarks.runner import BenchmarkRunner, BenchmarkResult, SpeedMetrics, QualityMetrics, CostMetrics
from benchmarks.storage import BenchmarkStorage
from benchmarks.alerts import BenchmarkAlerter
from benchmarks.github_reporter import GitHubReporter

__all__ = [
    "BenchmarkRunner",
    "BenchmarkResult",
    "SpeedMetrics",
    "QualityMetrics",
    "CostMetrics",
    "BenchmarkStorage",
    "BenchmarkAlerter",
    "GitHubReporter",
]
