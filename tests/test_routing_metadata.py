"""Tests for agents/routing_metadata.py and the routing REST endpoint (AI-255).

Covers:
- RoutingDecision dataclass: creation, defaults, to_dict, from_dict
- log_routing_decision: persistence to in-memory log
- get_routing_history: retrieval by session_id, empty case, malformed record skipping
- get_routing_history_raw: returns plain dicts
- clear_routing_log: single session and full clear
- REST endpoint GET /api/sessions/{session_id}/routing:
  - 200 with routing decisions when session known via routing log
  - 200 with routing decisions when session known via metrics events
  - 404 when session completely unknown
  - Empty decision list when session exists but has no routing decisions
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import types
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Stub heavy optional dependencies so the module loads in CI without a full
# agent SDK or arcade installation.
# ---------------------------------------------------------------------------


def _stub_optional_deps():
    """Install minimal stubs for claude_agent_sdk and arcade_config."""
    if "claude_agent_sdk" not in sys.modules:
        sdk_mod = types.ModuleType("claude_agent_sdk")
        for cls_name in ("AssistantMessage", "ClaudeSDKClient", "TextBlock", "ToolUseBlock"):
            setattr(sdk_mod, cls_name, type(cls_name, (), {}))
        sys.modules["claude_agent_sdk"] = sdk_mod

    if "arcade_config" not in sys.modules:
        arcade_mod = types.ModuleType("arcade_config")
        for fn in ("get_coding_tools", "get_github_tools", "get_linear_tools", "get_slack_tools"):
            setattr(arcade_mod, fn, lambda: [])
        sys.modules["arcade_config"] = arcade_mod


_stub_optional_deps()

# ---------------------------------------------------------------------------
# Import agents.routing_metadata via file path to avoid running agents/__init__.py
# which has Python 3.10+ dependencies.
# ---------------------------------------------------------------------------

_METADATA_PATH = PROJECT_ROOT / "agents" / "routing_metadata.py"

# Ensure the "agents" package namespace exists without running __init__.py
if "agents" not in sys.modules:
    _agents_pkg = types.ModuleType("agents")
    _agents_pkg.__path__ = [str(PROJECT_ROOT / "agents")]  # type: ignore[attr-defined]
    _agents_pkg.__package__ = "agents"
    sys.modules["agents"] = _agents_pkg

_spec = importlib.util.spec_from_file_location("agents.routing_metadata", _METADATA_PATH)
_routing_metadata_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["agents.routing_metadata"] = _routing_metadata_module
_spec.loader.exec_module(_routing_metadata_module)  # type: ignore[union-attr]

from agents.routing_metadata import (  # noqa: E402
    RoutingDecision,
    clear_routing_log,
    get_routing_history,
    get_routing_history_raw,
    log_routing_decision,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(autouse=True)
def clear_log_before_each_test():
    """Reset the global routing log before every test."""
    clear_routing_log()
    yield
    clear_routing_log()


# ===========================================================================
# RoutingDecision dataclass tests
# ===========================================================================


class TestRoutingDecisionDataclass:
    """Tests for the RoutingDecision dataclass."""

    def test_required_fields(self):
        decision = RoutingDecision(
            session_id="s-001",
            agent_selected="coding",
            routing_reason="complexity keywords found",
        )
        assert decision.session_id == "s-001"
        assert decision.agent_selected == "coding"
        assert decision.routing_reason == "complexity keywords found"

    def test_default_alternatives_is_empty_list(self):
        decision = RoutingDecision(
            session_id="s-001",
            agent_selected="coding",
            routing_reason="reason",
        )
        assert decision.alternatives_considered == []

    def test_default_complexity_score_is_zero(self):
        decision = RoutingDecision(
            session_id="s-001",
            agent_selected="coding",
            routing_reason="reason",
        )
        assert decision.complexity_score == 0

    def test_default_model_tier_is_sonnet(self):
        decision = RoutingDecision(
            session_id="s-001",
            agent_selected="coding",
            routing_reason="reason",
        )
        assert decision.model_tier == "sonnet"

    def test_default_timestamp_is_set(self):
        decision = RoutingDecision(
            session_id="s-001",
            agent_selected="coding",
            routing_reason="reason",
        )
        assert decision.timestamp  # non-empty string
        assert "T" in decision.timestamp  # ISO 8601 format

    def test_default_task_description_is_empty(self):
        decision = RoutingDecision(
            session_id="s-001",
            agent_selected="coding",
            routing_reason="reason",
        )
        assert decision.task_description == ""

    def test_explicit_all_fields(self):
        decision = RoutingDecision(
            session_id="s-002",
            agent_selected="pr_reviewer",
            routing_reason="lines changed > 200",
            alternatives_considered=["pr_reviewer_fast"],
            complexity_score=6,
            model_tier="opus",
            timestamp="2026-01-01T00:00:00+00:00",
            task_description="Review PR #42",
        )
        assert decision.alternatives_considered == ["pr_reviewer_fast"]
        assert decision.complexity_score == 6
        assert decision.model_tier == "opus"
        assert decision.timestamp == "2026-01-01T00:00:00+00:00"
        assert decision.task_description == "Review PR #42"

    def test_to_dict_returns_all_fields(self):
        decision = RoutingDecision(
            session_id="s-003",
            agent_selected="coding_fast",
            routing_reason="file count <= 3",
            alternatives_considered=["coding"],
            complexity_score=2,
            model_tier="haiku",
            timestamp="2026-01-01T00:00:00+00:00",
            task_description="update README",
        )
        d = decision.to_dict()
        assert d["session_id"] == "s-003"
        assert d["agent_selected"] == "coding_fast"
        assert d["routing_reason"] == "file count <= 3"
        assert d["alternatives_considered"] == ["coding"]
        assert d["complexity_score"] == 2
        assert d["model_tier"] == "haiku"
        assert d["timestamp"] == "2026-01-01T00:00:00+00:00"
        assert d["task_description"] == "update README"

    def test_from_dict_round_trips(self):
        original = RoutingDecision(
            session_id="s-004",
            agent_selected="gemini",
            routing_reason="large context",
            alternatives_considered=["kimi", "chatgpt"],
            complexity_score=5,
            model_tier="sonnet",
            timestamp="2026-02-01T12:00:00+00:00",
            task_description="analyse 200k context",
        )
        restored = RoutingDecision.from_dict(original.to_dict())
        assert restored.session_id == original.session_id
        assert restored.agent_selected == original.agent_selected
        assert restored.routing_reason == original.routing_reason
        assert restored.alternatives_considered == original.alternatives_considered
        assert restored.complexity_score == original.complexity_score
        assert restored.model_tier == original.model_tier

    def test_from_dict_ignores_unknown_keys(self):
        data = {
            "session_id": "s-005",
            "agent_selected": "groq",
            "routing_reason": "speed required",
            "unknown_future_field": "value",
        }
        decision = RoutingDecision.from_dict(data)
        assert decision.session_id == "s-005"
        assert decision.agent_selected == "groq"

    def test_alternatives_lists_are_independent(self):
        """Mutable default should not be shared between instances."""
        d1 = RoutingDecision(session_id="s1", agent_selected="a", routing_reason="r")
        d2 = RoutingDecision(session_id="s2", agent_selected="b", routing_reason="r")
        d1.alternatives_considered.append("x")
        assert d2.alternatives_considered == []


# ===========================================================================
# log_routing_decision tests
# ===========================================================================


class TestLogRoutingDecision:
    """Tests for log_routing_decision()."""

    def test_logs_decision_for_new_session(self):
        decision = RoutingDecision(
            session_id="s-log-001",
            agent_selected="coding",
            routing_reason="test",
        )
        log_routing_decision("s-log-001", decision)
        history = get_routing_history("s-log-001")
        assert len(history) == 1
        assert history[0].agent_selected == "coding"

    def test_multiple_decisions_same_session(self):
        for agent in ["coding_fast", "pr_reviewer_fast", "coding"]:
            log_routing_decision(
                "s-multi",
                RoutingDecision(
                    session_id="s-multi",
                    agent_selected=agent,
                    routing_reason="test",
                ),
            )
        history = get_routing_history("s-multi")
        assert len(history) == 3
        assert [d.agent_selected for d in history] == ["coding_fast", "pr_reviewer_fast", "coding"]

    def test_sessions_are_isolated(self):
        log_routing_decision(
            "s-a",
            RoutingDecision(session_id="s-a", agent_selected="coding", routing_reason="r"),
        )
        log_routing_decision(
            "s-b",
            RoutingDecision(session_id="s-b", agent_selected="gemini", routing_reason="r"),
        )
        assert len(get_routing_history("s-a")) == 1
        assert len(get_routing_history("s-b")) == 1
        assert get_routing_history("s-a")[0].agent_selected == "coding"
        assert get_routing_history("s-b")[0].agent_selected == "gemini"

    def test_session_id_mismatch_reconciles(self):
        """When argument session_id differs from decision.session_id, argument wins."""
        decision = RoutingDecision(
            session_id="decision-id",
            agent_selected="coding",
            routing_reason="test",
        )
        log_routing_decision("argument-id", decision)
        # Should be logged under "argument-id"
        assert len(get_routing_history("argument-id")) == 1
        assert len(get_routing_history("decision-id")) == 0

    def test_decision_persisted_as_dict(self):
        decision = RoutingDecision(
            session_id="s-dict",
            agent_selected="kimi",
            routing_reason="2M context",
            complexity_score=8,
            model_tier="sonnet",
        )
        log_routing_decision("s-dict", decision)
        raw = get_routing_history_raw("s-dict")
        assert isinstance(raw[0], dict)
        assert raw[0]["agent_selected"] == "kimi"
        assert raw[0]["complexity_score"] == 8


# ===========================================================================
# get_routing_history tests
# ===========================================================================


class TestGetRoutingHistory:
    """Tests for get_routing_history()."""

    def test_empty_for_unknown_session(self):
        result = get_routing_history("nonexistent-session")
        assert result == []

    def test_returns_routing_decision_instances(self):
        log_routing_decision(
            "s-inst",
            RoutingDecision(session_id="s-inst", agent_selected="groq", routing_reason="fast"),
        )
        history = get_routing_history("s-inst")
        assert all(isinstance(d, RoutingDecision) for d in history)

    def test_preserves_complexity_score(self):
        log_routing_decision(
            "s-score",
            RoutingDecision(
                session_id="s-score",
                agent_selected="coding",
                routing_reason="keywords",
                complexity_score=9,
            ),
        )
        history = get_routing_history("s-score")
        assert history[0].complexity_score == 9

    def test_preserves_alternatives(self):
        log_routing_decision(
            "s-alts",
            RoutingDecision(
                session_id="s-alts",
                agent_selected="coding",
                routing_reason="keywords",
                alternatives_considered=["coding_fast"],
            ),
        )
        history = get_routing_history("s-alts")
        assert history[0].alternatives_considered == ["coding_fast"]


# ===========================================================================
# get_routing_history_raw tests
# ===========================================================================


class TestGetRoutingHistoryRaw:
    """Tests for get_routing_history_raw()."""

    def test_returns_plain_dicts(self):
        log_routing_decision(
            "s-raw",
            RoutingDecision(session_id="s-raw", agent_selected="chatgpt", routing_reason="r"),
        )
        raw = get_routing_history_raw("s-raw")
        assert isinstance(raw, list)
        assert isinstance(raw[0], dict)

    def test_returns_copy_not_reference(self):
        """Mutating the returned list should not affect the internal store."""
        log_routing_decision(
            "s-copy",
            RoutingDecision(session_id="s-copy", agent_selected="coding", routing_reason="r"),
        )
        raw = get_routing_history_raw("s-copy")
        raw.append({"injected": True})
        assert len(get_routing_history_raw("s-copy")) == 1

    def test_empty_for_unknown_session(self):
        assert get_routing_history_raw("not-a-session") == []


# ===========================================================================
# clear_routing_log tests
# ===========================================================================


class TestClearRoutingLog:
    """Tests for clear_routing_log()."""

    def test_clear_specific_session(self):
        log_routing_decision(
            "s-clear-1",
            RoutingDecision(session_id="s-clear-1", agent_selected="a", routing_reason="r"),
        )
        log_routing_decision(
            "s-clear-2",
            RoutingDecision(session_id="s-clear-2", agent_selected="b", routing_reason="r"),
        )
        clear_routing_log("s-clear-1")
        assert get_routing_history("s-clear-1") == []
        assert len(get_routing_history("s-clear-2")) == 1

    def test_clear_all(self):
        for sid in ["s-all-1", "s-all-2", "s-all-3"]:
            log_routing_decision(
                sid,
                RoutingDecision(session_id=sid, agent_selected="coding", routing_reason="r"),
            )
        clear_routing_log()
        for sid in ["s-all-1", "s-all-2", "s-all-3"]:
            assert get_routing_history(sid) == []

    def test_clear_nonexistent_session_is_noop(self):
        """clear_routing_log on an unknown session_id should not raise."""
        clear_routing_log("not-there")  # Should not raise


# ===========================================================================
# REST API endpoint tests
# ===========================================================================


class TestGetSessionRoutingEndpoint:
    """Tests for GET /api/sessions/{session_id}/routing.

    Uses aiohttp's TestClient pattern to test the handler without a running
    server.  The MetricsStore is mocked to return controlled data.
    """

    @pytest.fixture
    def make_server(self, tmp_path):
        """Create a RESTAPIServer bound to a temp directory."""
        # Stub dependencies needed by rest_api_server at import time
        _stub_optional_deps()

        # Stub dashboard.auth.* to avoid heavy imports
        for mod_path in [
            "dashboard.auth",
            "dashboard.auth.user_store",
            "dashboard.auth.session_manager",
            "dashboard.auth.oauth_handler",
        ]:
            if mod_path not in sys.modules:
                m = types.ModuleType(mod_path)
                if mod_path == "dashboard.auth.oauth_handler":
                    m.OAuthNotConfiguredError = Exception  # type: ignore[attr-defined]
                sys.modules[mod_path] = m

        # Stub sso modules
        for mod_path in [
            "sso.saml_handler",
            "sso.oidc_handler",
            "sso.organization_store",
            "sso.jit_provisioner",
            "sso.scim_handler",
        ]:
            if mod_path not in sys.modules:
                sys.modules[mod_path] = types.ModuleType(mod_path)

        from dashboard.rest_api_server import RESTAPIServer
        server = RESTAPIServer(
            project_name="test-routing",
            metrics_dir=tmp_path,
            host="127.0.0.1",
            port=9999,
        )
        return server

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_session(self, make_server):
        """Sessions not in the metrics store or routing log return 404."""
        from aiohttp.test_utils import TestClient, TestServer

        server = make_server
        # Mock the MetricsStore.load to return empty state
        server.store.load = MagicMock(return_value={"events": [], "sessions": []})

        # Ensure routing log is empty for this session
        clear_routing_log("unknown-session-xyz")

        async with TestClient(TestServer(server.app)) as client:
            resp = await client.get("/api/sessions/unknown-session-xyz/routing")
            assert resp.status == 404
            data = await resp.json()
            assert data["session_id"] == "unknown-session-xyz"

    @pytest.mark.asyncio
    async def test_returns_200_with_routing_decisions_from_log(self, make_server):
        """Returns 200 with routing decisions when found in the routing log."""
        from aiohttp.test_utils import TestClient, TestServer

        server = make_server
        session_id = "s-rest-001"

        # Pre-populate routing log
        log_routing_decision(
            session_id,
            RoutingDecision(
                session_id=session_id,
                agent_selected="coding",
                routing_reason="complexity keywords",
                complexity_score=7,
                model_tier="sonnet",
            ),
        )

        # Metrics store returns empty (session only known via routing log)
        server.store.load = MagicMock(return_value={"events": [], "sessions": []})

        async with TestClient(TestServer(server.app)) as client:
            resp = await client.get(f"/api/sessions/{session_id}/routing")
            assert resp.status == 200
            data = await resp.json()
            assert data["session_id"] == session_id
            assert data["total_decisions"] == 1
            assert data["routing_decisions"][0]["agent_selected"] == "coding"
            assert data["routing_decisions"][0]["complexity_score"] == 7
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_returns_200_when_session_in_events_only(self, make_server):
        """Returns 200 even when session has no routing decisions but exists in events."""
        from aiohttp.test_utils import TestClient, TestServer

        server = make_server
        session_id = "s-events-only"

        # Session exists in events but has no routing decisions
        server.store.load = MagicMock(return_value={
            "events": [{"session_id": session_id, "agent_name": "coding"}],
            "sessions": [],
        })

        async with TestClient(TestServer(server.app)) as client:
            resp = await client.get(f"/api/sessions/{session_id}/routing")
            assert resp.status == 200
            data = await resp.json()
            assert data["session_id"] == session_id
            assert data["total_decisions"] == 0
            assert data["routing_decisions"] == []

    @pytest.mark.asyncio
    async def test_returns_multiple_decisions(self, make_server):
        """All routing decisions for a session are returned."""
        from aiohttp.test_utils import TestClient, TestServer

        server = make_server
        session_id = "s-multi-rest"

        agents = ["coding_fast", "pr_reviewer_fast", "gemini"]
        for agent in agents:
            log_routing_decision(
                session_id,
                RoutingDecision(
                    session_id=session_id,
                    agent_selected=agent,
                    routing_reason="test",
                ),
            )

        server.store.load = MagicMock(return_value={"events": [], "sessions": []})

        async with TestClient(TestServer(server.app)) as client:
            resp = await client.get(f"/api/sessions/{session_id}/routing")
            assert resp.status == 200
            data = await resp.json()
            assert data["total_decisions"] == 3
            returned_agents = [d["agent_selected"] for d in data["routing_decisions"]]
            assert returned_agents == agents

    @pytest.mark.asyncio
    async def test_response_structure(self, make_server):
        """Response always contains required fields."""
        from aiohttp.test_utils import TestClient, TestServer

        server = make_server
        session_id = "s-structure"

        log_routing_decision(
            session_id,
            RoutingDecision(
                session_id=session_id,
                agent_selected="kimi",
                routing_reason="2M context needed",
                alternatives_considered=["gemini"],
                complexity_score=5,
                model_tier="sonnet",
                task_description="analyse full codebase",
            ),
        )
        server.store.load = MagicMock(return_value={"events": [], "sessions": []})

        async with TestClient(TestServer(server.app)) as client:
            resp = await client.get(f"/api/sessions/{session_id}/routing")
            assert resp.status == 200
            data = await resp.json()
            # Top-level structure
            assert "session_id" in data
            assert "routing_decisions" in data
            assert "total_decisions" in data
            assert "timestamp" in data
            # Decision record structure
            decision = data["routing_decisions"][0]
            assert "agent_selected" in decision
            assert "routing_reason" in decision
            assert "alternatives_considered" in decision
            assert "complexity_score" in decision
            assert "model_tier" in decision
            assert "timestamp" in decision
