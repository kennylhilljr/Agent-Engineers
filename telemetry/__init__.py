"""Telemetry & Usage Analytics (AI-227).

Provides async event collection with batched writes, privacy-first schema
(no PII), opt-out support, and JSONL-based local storage.

Usage
-----
    from telemetry import get_collector

    collector = get_collector()
    await collector.collect("chat_message_sent", {"provider": "claude"})
"""

from telemetry.event_collector import (
    EventCollector,
    TelemetryEvent,
    get_collector,
    reset_collector,
)

__all__ = [
    "EventCollector",
    "TelemetryEvent",
    "get_collector",
    "reset_collector",
]
