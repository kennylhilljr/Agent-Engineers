"""Performance Metrics Collection for Agent Dashboard.

This module provides comprehensive performance metrics collection including:
- Request/response timing
- Database query performance
- Cache hit rates
- Memory and CPU usage
- Custom business metrics
- Prometheus-compatible metrics export

Usage:
    from dashboard.performance_metrics import (
        metrics_collector,
        track_time,
        record_metric,
        increment_counter
    )

    # Track function execution time
    @track_time("user_login")
    def login_user(username):
        # ... login logic
        pass

    # Record custom metric
    record_metric("api_response_time", 150, {"endpoint": "/api/metrics"})

    # Increment counter
    increment_counter("user_login_success")

    # Get metrics for export
    metrics = metrics_collector.get_metrics()
"""

import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

from dashboard.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class MetricData:
    """Individual metric data point."""

    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: str = "gauge"  # gauge, counter, histogram, summary


@dataclass
class HistogramData:
    """Histogram metric data for tracking distributions."""

    count: int = 0
    sum: float = 0.0
    min: float = float("inf")
    max: float = float("-inf")
    buckets: Dict[float, int] = field(default_factory=dict)

    def observe(self, value: float):
        """Record an observation."""
        self.count += 1
        self.sum += value
        self.min = min(self.min, value)
        self.max = max(self.max, value)

        # Update buckets (predefined percentile buckets)
        for threshold in [0.001, 0.01, 0.1, 0.5, 1, 5, 10, 30, 60]:
            if value <= threshold:
                self.buckets[threshold] = self.buckets.get(threshold, 0) + 1

    @property
    def mean(self) -> float:
        """Calculate mean value."""
        return self.sum / self.count if self.count > 0 else 0.0

    def percentile(self, p: float) -> float:
        """Estimate percentile from buckets.

        Args:
            p: Percentile (0-100)

        Returns:
            Estimated percentile value
        """
        if self.count == 0:
            return 0.0

        target_count = (p / 100) * self.count
        cumulative = 0

        for threshold in sorted(self.buckets.keys()):
            cumulative += self.buckets[threshold]
            if cumulative >= target_count:
                return threshold

        return self.max


class MetricsCollector:
    """Centralized metrics collector with thread-safe operations.

    Collects and stores various types of metrics:
    - Counters: Monotonically increasing values
    - Gauges: Point-in-time values
    - Histograms: Distribution of values
    - Summaries: Aggregated statistics
    """

    def __init__(self):
        """Initialize metrics collector."""
        self._lock = Lock()
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, HistogramData] = defaultdict(HistogramData)
        self._labels: Dict[str, Dict[str, str]] = {}
        self._metric_metadata: Dict[str, Dict[str, str]] = {}

        # Track collector start time
        self._start_time = time.time()

    def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric.

        Counters are monotonically increasing values.

        Args:
            name: Metric name
            value: Value to increment by (default: 1.0)
            labels: Optional labels for the metric
        """
        with self._lock:
            metric_key = self._make_key(name, labels)
            self._counters[metric_key] += value

            if labels:
                self._labels[metric_key] = labels

            logger.debug(
                "Counter incremented",
                extra={
                    "metric_name": name,
                    "value": value,
                    "labels": labels,
                    "new_total": self._counters[metric_key]
                }
            )

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge metric.

        Gauges are point-in-time values that can go up or down.

        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels for the metric
        """
        with self._lock:
            metric_key = self._make_key(name, labels)
            self._gauges[metric_key] = value

            if labels:
                self._labels[metric_key] = labels

            logger.debug(
                "Gauge set",
                extra={
                    "metric_name": name,
                    "value": value,
                    "labels": labels
                }
            )

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Observe a value in a histogram metric.

        Histograms track distributions of values.

        Args:
            name: Metric name
            value: Observed value
            labels: Optional labels for the metric
        """
        with self._lock:
            metric_key = self._make_key(name, labels)
            self._histograms[metric_key].observe(value)

            if labels:
                self._labels[metric_key] = labels

            logger.debug(
                "Histogram observation recorded",
                extra={
                    "metric_name": name,
                    "value": value,
                    "labels": labels
                }
            )

    def register_metric(
        self,
        name: str,
        metric_type: str,
        description: str,
        unit: Optional[str] = None
    ) -> None:
        """Register metadata for a metric.

        Args:
            name: Metric name
            metric_type: Type (counter, gauge, histogram)
            description: Human-readable description
            unit: Unit of measurement (e.g., "seconds", "bytes")
        """
        with self._lock:
            self._metric_metadata[name] = {
                "type": metric_type,
                "description": description,
                "unit": unit or ""
            }

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value.

        Args:
            name: Metric name
            labels: Optional labels

        Returns:
            Current counter value
        """
        with self._lock:
            metric_key = self._make_key(name, labels)
            return self._counters.get(metric_key, 0.0)

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get current gauge value.

        Args:
            name: Metric name
            labels: Optional labels

        Returns:
            Current gauge value or None
        """
        with self._lock:
            metric_key = self._make_key(name, labels)
            return self._gauges.get(metric_key)

    def get_histogram(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[HistogramData]:
        """Get histogram data.

        Args:
            name: Metric name
            labels: Optional labels

        Returns:
            HistogramData or None
        """
        with self._lock:
            metric_key = self._make_key(name, labels)
            return self._histograms.get(metric_key)

    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary.

        Returns:
            Dictionary containing all metrics
        """
        with self._lock:
            metrics = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "uptime_seconds": time.time() - self._start_time,
                "counters": {},
                "gauges": {},
                "histograms": {}
            }

            # Export counters
            for key, value in self._counters.items():
                name, labels = self._parse_key(key)
                if name not in metrics["counters"]:
                    metrics["counters"][name] = []
                metrics["counters"][name].append({
                    "value": value,
                    "labels": labels
                })

            # Export gauges
            for key, value in self._gauges.items():
                name, labels = self._parse_key(key)
                if name not in metrics["gauges"]:
                    metrics["gauges"][name] = []
                metrics["gauges"][name].append({
                    "value": value,
                    "labels": labels
                })

            # Export histograms
            for key, hist_data in self._histograms.items():
                name, labels = self._parse_key(key)
                if name not in metrics["histograms"]:
                    metrics["histograms"][name] = []
                metrics["histograms"][name].append({
                    "count": hist_data.count,
                    "sum": hist_data.sum,
                    "mean": hist_data.mean,
                    "min": hist_data.min if hist_data.count > 0 else 0,
                    "max": hist_data.max if hist_data.count > 0 else 0,
                    "p50": hist_data.percentile(50),
                    "p95": hist_data.percentile(95),
                    "p99": hist_data.percentile(99),
                    "labels": labels
                })

            return metrics

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metrics string
        """
        with self._lock:
            lines = []

            # Export counters
            for key, value in self._counters.items():
                name, labels = self._parse_key(key)
                prom_name = self._prometheus_name(name)
                label_str = self._prometheus_labels(labels)

                # Add metadata if available
                if name in self._metric_metadata:
                    meta = self._metric_metadata[name]
                    lines.append(f"# HELP {prom_name} {meta['description']}")
                    lines.append(f"# TYPE {prom_name} counter")

                lines.append(f"{prom_name}{label_str} {value}")

            # Export gauges
            for key, value in self._gauges.items():
                name, labels = self._parse_key(key)
                prom_name = self._prometheus_name(name)
                label_str = self._prometheus_labels(labels)

                # Add metadata if available
                if name in self._metric_metadata:
                    meta = self._metric_metadata[name]
                    lines.append(f"# HELP {prom_name} {meta['description']}")
                    lines.append(f"# TYPE {prom_name} gauge")

                lines.append(f"{prom_name}{label_str} {value}")

            # Export histograms
            for key, hist_data in self._histograms.items():
                name, labels = self._parse_key(key)
                prom_name = self._prometheus_name(name)

                # Add metadata if available
                if name in self._metric_metadata:
                    meta = self._metric_metadata[name]
                    lines.append(f"# HELP {prom_name} {meta['description']}")
                    lines.append(f"# TYPE {prom_name} histogram")

                # Export histogram buckets
                for threshold, count in sorted(hist_data.buckets.items()):
                    bucket_labels = {**labels, "le": str(threshold)}
                    label_str = self._prometheus_labels(bucket_labels)
                    lines.append(f"{prom_name}_bucket{label_str} {count}")

                # Add +Inf bucket
                inf_labels = {**labels, "le": "+Inf"}
                label_str = self._prometheus_labels(inf_labels)
                lines.append(f"{prom_name}_bucket{label_str} {hist_data.count}")

                # Add sum and count
                label_str = self._prometheus_labels(labels)
                lines.append(f"{prom_name}_sum{label_str} {hist_data.sum}")
                lines.append(f"{prom_name}_count{label_str} {hist_data.count}")

            return "\n".join(lines) + "\n"

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._labels.clear()
            self._start_time = time.time()

            logger.info("Metrics collector reset")

    @staticmethod
    def _make_key(name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create a unique key for a metric with labels.

        Args:
            name: Metric name
            labels: Optional labels

        Returns:
            Unique metric key
        """
        if not labels:
            return name

        # Sort labels for consistent keys
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    @staticmethod
    def _parse_key(key: str) -> tuple[str, Dict[str, str]]:
        """Parse a metric key into name and labels.

        Args:
            key: Metric key

        Returns:
            Tuple of (name, labels)
        """
        if "{" not in key:
            return key, {}

        name, label_str = key.split("{", 1)
        label_str = label_str.rstrip("}")

        labels = {}
        if label_str:
            for pair in label_str.split(","):
                k, v = pair.split("=", 1)
                labels[k] = v

        return name, labels

    @staticmethod
    def _prometheus_name(name: str) -> str:
        """Convert metric name to Prometheus format.

        Args:
            name: Metric name

        Returns:
            Prometheus-formatted name
        """
        # Replace invalid characters with underscores
        return name.replace(".", "_").replace("-", "_")

    @staticmethod
    def _prometheus_labels(labels: Dict[str, str]) -> str:
        """Format labels for Prometheus output.

        Args:
            labels: Label dictionary

        Returns:
            Prometheus-formatted label string
        """
        if not labels:
            return ""

        label_pairs = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(label_pairs) + "}"


# Global metrics collector instance
metrics_collector = MetricsCollector()


# Decorator for tracking function execution time
def track_time(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to track function execution time.

    Args:
        metric_name: Name of the metric
        labels: Optional labels for the metric

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                metrics_collector.observe_histogram(
                    metric_name,
                    duration,
                    labels
                )
                logger.debug(
                    f"Function {func.__name__} executed",
                    extra={
                        "function": func.__name__,
                        "duration_seconds": duration,
                        "metric_name": metric_name
                    }
                )
        return wrapper
    return decorator


# Context manager for tracking execution time
@contextmanager
def timed_operation(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Context manager for tracking operation execution time.

    Args:
        metric_name: Name of the metric
        labels: Optional labels for the metric

    Yields:
        None
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metrics_collector.observe_histogram(metric_name, duration, labels)


# Convenience functions
def increment_counter(name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
    """Increment a counter metric."""
    metrics_collector.increment_counter(name, value, labels)


def set_gauge(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Set a gauge metric."""
    metrics_collector.set_gauge(name, value, labels)


def record_metric(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Record a histogram observation."""
    metrics_collector.observe_histogram(name, value, labels)


def register_metric(name: str, metric_type: str, description: str, unit: Optional[str] = None) -> None:
    """Register metric metadata."""
    metrics_collector.register_metric(name, metric_type, description, unit)
