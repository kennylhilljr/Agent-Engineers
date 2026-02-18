"""Tests for telemetry/event_collector.py (AI-227).

Coverage:
- TelemetryEvent creation and serialisation
- PII stripping
- Opt-out via TELEMETRY_DISABLED env var
- Opt-out via flag file
- EventCollector: collect, flush, batch write
- Async lifecycle (start/stop)
- Module-level singleton (get_collector / reset_collector)
- Analytics endpoint response shape
- Opt-out POST endpoint
- Event count metrics
- Multiple event types
- Storage JSONL format
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from telemetry.event_collector import (
    TelemetryEvent,
    EventCollector,
    get_collector,
    reset_collector,
    strip_pii,
    is_telemetry_disabled,
    write_opt_out_flag,
    remove_opt_out_flag,
    OPT_OUT_FLAG_PATH,
    VALID_EVENT_TYPES,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(autouse=True)
def clean_env_and_flag(tmp_path, monkeypatch):
    """Ensure every test starts with a clean environment and no opt-out flag."""
    monkeypatch.delenv("TELEMETRY_DISABLED", raising=False)
    monkeypatch.delenv("TELEMETRY_ENDPOINT", raising=False)
    # Patch the module-level OPT_OUT_FLAG_PATH to use tmp dir so tests never
    # touch the real filesystem.
    flag = tmp_path / ".telemetry_optout"
    monkeypatch.setattr("telemetry.event_collector.OPT_OUT_FLAG_PATH", flag)
    reset_collector()
    yield
    reset_collector()


@pytest.fixture
def storage_path(tmp_path) -> Path:
    return tmp_path / ".telemetry_events.jsonl"


@pytest.fixture
def collector(storage_path) -> EventCollector:
    c = EventCollector(storage_path=storage_path, batch_interval=9999)
    reset_collector(c)
    return c


# ===========================================================================
# 1. TelemetryEvent data class
# ===========================================================================


def test_telemetry_event_has_expected_fields():
    """TelemetryEvent must carry event_type, properties, timestamp, session_id, event_id."""
    ev = TelemetryEvent(event_type="session_started", properties={"key": "val"})
    assert ev.event_type == "session_started"
    assert ev.properties == {"key": "val"}
    assert ev.timestamp  # non-empty string
    assert ev.session_id
    assert ev.event_id


def test_telemetry_event_to_dict_is_serialisable():
    """to_dict() must return a JSON-serialisable dict."""
    ev = TelemetryEvent(event_type="chat_message_sent", properties={"provider": "claude"})
    d = ev.to_dict()
    serialised = json.dumps(d)  # must not raise
    loaded = json.loads(serialised)
    assert loaded["event_type"] == "chat_message_sent"
    assert loaded["properties"]["provider"] == "claude"


def test_telemetry_event_unique_event_ids():
    """Two TelemetryEvent instances must have different event_ids."""
    a = TelemetryEvent(event_type="session_started")
    b = TelemetryEvent(event_type="session_started")
    assert a.event_id != b.event_id


def test_telemetry_event_timestamp_is_iso():
    """Timestamp must be parseable as ISO-8601."""
    from datetime import datetime
    ev = TelemetryEvent(event_type="dashboard_tab_viewed")
    # Should not raise
    datetime.fromisoformat(ev.timestamp)


# ===========================================================================
# 2. PII stripping
# ===========================================================================


def test_strip_pii_removes_email():
    props = {"email": "user@example.com", "provider": "claude"}
    result = strip_pii(props)
    assert "email" not in result
    assert result["provider"] == "claude"


def test_strip_pii_case_insensitive():
    props = {"Email": "test@example.com", "NAME": "Alice", "provider": "openai"}
    result = strip_pii(props)
    assert "Email" not in result
    assert "NAME" not in result
    assert "provider" in result


def test_strip_pii_removes_all_pii_fields():
    pii = {
        "email": "x", "name": "y", "phone": "z",
        "address": "a", "ip": "1.2.3.4", "token": "abc",
        "password": "secret",
    }
    result = strip_pii({**pii, "safe_field": "keep"})
    for key in pii:
        assert key not in result
    assert result["safe_field"] == "keep"


def test_strip_pii_preserves_non_pii():
    props = {"provider": "claude", "intent_type": "query", "duration_ms": 123}
    result = strip_pii(props)
    assert result == props


def test_collect_strips_pii_automatically(collector):
    """collect() must strip email before the event is queued."""
    collector.collect("chat_message_sent", {"email": "spy@example.com", "provider": "claude"})
    # Drain the queue
    ev = collector._queue.get_nowait()
    assert "email" not in ev.properties
    assert ev.properties.get("provider") == "claude"


# ===========================================================================
# 3. Opt-out via TELEMETRY_DISABLED env var
# ===========================================================================


def test_is_telemetry_disabled_false_by_default(monkeypatch):
    monkeypatch.delenv("TELEMETRY_DISABLED", raising=False)
    assert is_telemetry_disabled() is False


def test_is_telemetry_disabled_true_when_env_set(monkeypatch):
    monkeypatch.setenv("TELEMETRY_DISABLED", "true")
    assert is_telemetry_disabled() is True


def test_is_telemetry_disabled_handles_1(monkeypatch):
    monkeypatch.setenv("TELEMETRY_DISABLED", "1")
    assert is_telemetry_disabled() is True


def test_collect_is_noop_when_disabled(monkeypatch, collector):
    """collect() must not queue events when TELEMETRY_DISABLED=true."""
    monkeypatch.setenv("TELEMETRY_DISABLED", "true")
    collector.collect("session_started", {"provider": "claude"})
    assert collector._queue.empty()


# ===========================================================================
# 4. Opt-out via flag file
# ===========================================================================


def test_write_opt_out_flag_creates_file(tmp_path, monkeypatch):
    flag = tmp_path / ".telemetry_optout"
    monkeypatch.setattr("telemetry.event_collector.OPT_OUT_FLAG_PATH", flag)
    assert not flag.exists()
    write_opt_out_flag()
    assert flag.exists()


def test_remove_opt_out_flag_deletes_file(tmp_path, monkeypatch):
    flag = tmp_path / ".telemetry_optout"
    flag.touch()
    monkeypatch.setattr("telemetry.event_collector.OPT_OUT_FLAG_PATH", flag)
    remove_opt_out_flag()
    assert not flag.exists()


def test_collect_noop_when_flag_file_exists(tmp_path, monkeypatch, collector):
    flag = tmp_path / ".telemetry_optout"
    flag.touch()
    monkeypatch.setattr("telemetry.event_collector.OPT_OUT_FLAG_PATH", flag)
    collector.collect("session_started")
    assert collector._queue.empty()


# ===========================================================================
# 5. Async collection and batch write
# ===========================================================================


@pytest.mark.asyncio
async def test_collect_and_flush_writes_jsonl(collector, storage_path):
    """Flushing a queued event must append a valid JSON line to the JSONL file."""
    collector.collect("session_started", {"project": "test"})
    await collector._flush_pending()

    assert storage_path.exists()
    lines = [l for l in storage_path.read_text().splitlines() if l.strip()]
    assert len(lines) == 1

    ev = json.loads(lines[0])
    assert ev["event_type"] == "session_started"
    assert ev["properties"]["project"] == "test"


@pytest.mark.asyncio
async def test_multiple_events_all_written(collector, storage_path):
    """Multiple events must all be written to the JSONL file."""
    for etype in ["session_started", "chat_message_sent", "agent_paused"]:
        collector.collect(etype, {"source": "test"})

    await collector._flush_pending()

    lines = [l for l in storage_path.read_text().splitlines() if l.strip()]
    assert len(lines) == 3
    types = {json.loads(l)["event_type"] for l in lines}
    assert types == {"session_started", "chat_message_sent", "agent_paused"}


@pytest.mark.asyncio
async def test_flush_is_idempotent_when_empty(collector, storage_path):
    """Flushing an empty queue must not create the file."""
    await collector._flush_pending()
    assert not storage_path.exists()


@pytest.mark.asyncio
async def test_events_written_counter_increments(collector, storage_path):
    collector.collect("session_started")
    collector.collect("chat_message_sent")
    await collector._flush_pending()
    assert collector._events_written == 2


@pytest.mark.asyncio
async def test_start_stop_lifecycle(collector):
    """Collector must start and stop cleanly."""
    await collector.start()
    assert collector._running is True
    assert collector._flush_task is not None

    await collector.stop()
    assert collector._running is False


@pytest.mark.asyncio
async def test_start_is_idempotent(collector):
    """Calling start() twice must not create a second flush task."""
    await collector.start()
    task1 = collector._flush_task
    await collector.start()
    task2 = collector._flush_task
    assert task1 is task2
    await collector.stop()


@pytest.mark.asyncio
async def test_stop_flushes_remaining_events(collector, storage_path):
    """stop() must flush any queued events before terminating."""
    collector.collect("session_ended", {"project": "test"})
    await collector.start()
    await collector.stop()

    lines = [l for l in storage_path.read_text().splitlines() if l.strip()]
    assert len(lines) >= 1
    types = {json.loads(l)["event_type"] for l in lines}
    assert "session_ended" in types


# ===========================================================================
# 6. Module-level singleton
# ===========================================================================


def test_get_collector_returns_same_instance(storage_path):
    reset_collector()
    a = get_collector(storage_path=storage_path)
    b = get_collector(storage_path=storage_path)
    assert a is b


def test_reset_collector_clears_singleton(storage_path):
    reset_collector()
    a = get_collector(storage_path=storage_path)
    reset_collector()
    b = get_collector(storage_path=storage_path)
    assert a is not b


def test_reset_collector_with_instance(collector):
    new_c = EventCollector()
    reset_collector(new_c)
    assert get_collector() is new_c


# ===========================================================================
# 7. Analytics endpoint
# ===========================================================================


@pytest.mark.asyncio
async def test_analytics_endpoint_response_shape(tmp_path):
    """GET /api/admin/analytics must return correct shape even with no events."""
    from aiohttp.test_utils import TestClient, TestServer
    from dashboard.server import DashboardServer

    server = DashboardServer(
        project_name="test-analytics",
        metrics_dir=tmp_path,
        port=9100,
    )

    async with TestClient(TestServer(server.app)) as client:
        resp = await client.get("/api/admin/analytics")
        assert resp.status == 200
        data = await resp.json()

        assert "total_events" in data
        assert "events_last_24h" in data
        assert "events_last_7d" in data
        assert "counts_by_type" in data
        assert "daily_totals" in data
        assert "telemetry_disabled" in data
        assert isinstance(data["total_events"], int)
        assert isinstance(data["counts_by_type"], dict)
        assert isinstance(data["daily_totals"], list)


@pytest.mark.asyncio
async def test_analytics_endpoint_counts_events(tmp_path):
    """Analytics endpoint must return correct event counts from JSONL file."""
    from aiohttp.test_utils import TestClient, TestServer
    from dashboard.server import DashboardServer
    from telemetry.event_collector import EventCollector, reset_collector

    storage = tmp_path / ".telemetry_events.jsonl"
    collector = EventCollector(storage_path=storage, batch_interval=9999)
    reset_collector(collector)

    # Write 3 events
    collector.collect("session_started")
    collector.collect("chat_message_sent", {"provider": "claude"})
    collector.collect("agent_paused")
    await collector._flush_pending()

    server = DashboardServer(
        project_name="test-analytics-count",
        metrics_dir=tmp_path,
        port=9101,
    )

    async with TestClient(TestServer(server.app)) as client:
        resp = await client.get("/api/admin/analytics")
        assert resp.status == 200
        data = await resp.json()
        assert data["total_events"] == 3
        assert data["counts_by_type"]["session_started"] == 1
        assert data["counts_by_type"]["chat_message_sent"] == 1
        assert data["counts_by_type"]["agent_paused"] == 1

    reset_collector()


@pytest.mark.asyncio
async def test_optout_endpoint_returns_disabled(tmp_path):
    """POST /api/telemetry/optout must return telemetry_disabled=true."""
    from aiohttp.test_utils import TestClient, TestServer
    from dashboard.server import DashboardServer

    server = DashboardServer(
        project_name="test-optout",
        metrics_dir=tmp_path,
        port=9102,
    )

    async with TestClient(TestServer(server.app)) as client:
        resp = await client.post("/api/telemetry/optout")
        assert resp.status == 200
        data = await resp.json()
        assert data["telemetry_disabled"] is True
        assert data["status"] == "ok"

    # Cleanup opt-out flag
    remove_opt_out_flag()
