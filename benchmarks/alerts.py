"""Benchmark regression alerting for Agent Dashboard (AI-248).

BenchmarkAlerter checks whether latency metrics have regressed beyond
acceptable thresholds and emits structured log alerts.
"""

from __future__ import annotations

import logging
from typing import Optional

from structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

# Regression fires when current p95 exceeds rolling average p95 by more than 20%
LATENCY_REGRESSION_THRESHOLD = 0.20


class BenchmarkAlerter:
    """Checks benchmark metrics for regressions and issues alerts.

    Alerts are emitted via structured logging so they are captured by any
    log aggregator (e.g. CloudWatch, Datadog, Splunk) watching structured output.

    Args:
        threshold: Fractional increase beyond which a latency regression is
            declared (default 0.20, i.e. 20%).
    """

    def __init__(self, threshold: float = LATENCY_REGRESSION_THRESHOLD) -> None:
        self.threshold = threshold

    def check_latency_regression(
        self,
        current_p95: float,
        historical_p95: float,
    ) -> bool:
        """Determine whether p95 latency has regressed.

        A regression is detected when::

            (current_p95 - historical_p95) / historical_p95 > threshold

        Args:
            current_p95: p95 latency from the most recent benchmark run (seconds).
            historical_p95: Rolling p95 latency baseline (seconds).

        Returns:
            True if a regression is detected, False otherwise.
        """
        if historical_p95 <= 0:
            # Cannot determine regression without a valid baseline
            return False

        ratio = (current_p95 - historical_p95) / historical_p95
        return ratio > self.threshold

    def send_alert(self, message: str, extra: Optional[dict] = None) -> None:
        """Emit a structured alert log message.

        The alert is logged at WARNING level so it is surfaced by default log
        configurations. Additional key-value context can be attached via ``extra``.

        Args:
            message: Human-readable alert description.
            extra: Optional dict of extra structured fields to attach to the log.
        """
        log_extra = {"alert_type": "benchmark_regression"}
        if extra:
            log_extra.update(extra)

        logger.warning(
            "BENCHMARK ALERT: %s",
            message,
            extra={"extra": log_extra},
        )

    def check_and_alert(
        self,
        current_p95: float,
        historical_p95: float,
        agent_type: str = "unknown",
    ) -> bool:
        """Convenience method: check for regression and fire an alert if detected.

        Args:
            current_p95: p95 latency from the most recent benchmark run (seconds).
            historical_p95: Rolling p95 latency baseline (seconds).
            agent_type: Agent type label for the alert message.

        Returns:
            True if a regression was detected (and an alert was sent).
        """
        if self.check_latency_regression(current_p95, historical_p95):
            pct_increase = (
                ((current_p95 - historical_p95) / historical_p95) * 100
                if historical_p95 > 0
                else 0.0
            )
            self.send_alert(
                f"p95 latency regression for agent '{agent_type}': "
                f"{current_p95:.3f}s vs baseline {historical_p95:.3f}s "
                f"(+{pct_increase:.1f}%)",
                extra={
                    "agent_type": agent_type,
                    "current_p95": current_p95,
                    "historical_p95": historical_p95,
                    "pct_increase": pct_increase,
                },
            )
            return True
        return False
