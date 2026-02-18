"""Tests for AI-170: REQ-TECH-005 Metrics Data Source Integration.

Audit and verify that:
- GET /api/metrics returns data from MetricsStore (not hardcoded)
- GET /api/agents returns agents from MetricsStore/ALL_AGENT_NAMES (not hardcoded list)
- GET /api/providers correctly detects Claude when ANTHROPIC_API_KEY is set
- GET /api/providers shows OpenAI unavailable when OPENAI_API_KEY is not set
- GET /api/providers detects Gemini via GOOGLE_API_KEY (not just GEMINI_API_KEY)
- GET /api/providers detects KIMI via MOONSHOT_API_KEY (not just KIMI_API_KEY)
- MetricsStore reads from .agent_metrics.json
- Data updates when .agent_metrics.json changes
"""

import json
import os
import sys
import tempfile
import unittest.mock as mock
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

# Ensure the project root is importable.
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.rest_api_server import RESTAPIServer
from dashboard.metrics_store import MetricsStore, ALL_AGENT_NAMES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_metrics_state(
    project_name: str = "test-project",
    total_tokens: int = 5000,
    total_cost_usd: float = 0.25,
    total_sessions: int = 3,
    sessions: list | None = None,
    events: list | None = None,
    agents: dict | None = None,
) -> dict:
    """Build a minimal valid DashboardState for tests."""
    return {
        "version": 1,
        "project_name": project_name,
        "created_at": "2024-06-01T00:00:00Z",
        "updated_at": "2024-06-01T12:00:00Z",
        "total_sessions": total_sessions,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost_usd,
        "total_duration_seconds": 60.0,
        "agents": agents or {},
        "events": events or [],
        "sessions": sessions or [],
    }


def _write_metrics_file(path: Path, state: dict) -> None:
    """Write a DashboardState dict as .agent_metrics.json to the given path."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _make_server(tmp_path: Path) -> RESTAPIServer:
    """Create a RESTAPIServer backed by tmp_path as its metrics dir."""
    return RESTAPIServer(
        project_name="test-project",
        metrics_dir=tmp_path,
        port=0,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_metrics_dir(tmp_path):
    """Return a temporary directory for metrics files."""
    return tmp_path


@pytest.fixture
async def client(tmp_metrics_dir):
    """Create a TestClient backed by a fresh RESTAPIServer."""
    server = _make_server(tmp_metrics_dir)
    async with TestClient(TestServer(server.app)) as c:
        yield c, tmp_metrics_dir


# ---------------------------------------------------------------------------
# Tests: MetricsStore reads from .agent_metrics.json
# ---------------------------------------------------------------------------

def test_metrics_store_reads_from_json_file(tmp_metrics_dir):
    """MetricsStore.load() reads data from .agent_metrics.json on disk."""
    state = _make_metrics_state(total_tokens=99999, total_sessions=7)
    _write_metrics_file(tmp_metrics_dir / ".agent_metrics.json", state)

    store = MetricsStore(project_name="test-project", metrics_dir=tmp_metrics_dir)
    loaded = store.load()

    assert loaded["total_tokens"] == 99999
    assert loaded["total_sessions"] == 7
    assert loaded["project_name"] == "test-project"


def test_metrics_store_returns_empty_state_when_no_file(tmp_metrics_dir):
    """MetricsStore.load() returns a fresh empty state when no file exists."""
    store = MetricsStore(project_name="my-project", metrics_dir=tmp_metrics_dir)
    loaded = store.load()

    # Empty state has zero counters
    assert loaded["total_sessions"] == 0
    assert loaded["total_tokens"] == 0
    assert loaded["total_cost_usd"] == 0.0
    assert loaded["project_name"] == "my-project"


def test_metrics_store_data_updates_when_file_changes(tmp_metrics_dir):
    """MetricsStore.load() reflects updates to .agent_metrics.json on subsequent calls."""
    metrics_path = tmp_metrics_dir / ".agent_metrics.json"

    # First write
    state_v1 = _make_metrics_state(total_tokens=1000)
    _write_metrics_file(metrics_path, state_v1)

    store = MetricsStore(project_name="test-project", metrics_dir=tmp_metrics_dir)
    loaded_v1 = store.load()
    assert loaded_v1["total_tokens"] == 1000

    # Update the file with new data
    state_v2 = _make_metrics_state(total_tokens=2500, total_sessions=10)
    _write_metrics_file(metrics_path, state_v2)

    loaded_v2 = store.load()
    assert loaded_v2["total_tokens"] == 2500
    assert loaded_v2["total_sessions"] == 10


def test_metrics_store_ensures_all_canonical_agents_present(tmp_metrics_dir):
    """MetricsStore.load() ensures all canonical agent names appear in the loaded state."""
    # Write a file with only one agent
    state = _make_metrics_state(
        agents={"coding": {"agent_name": "coding", "total_invocations": 3}}
    )
    _write_metrics_file(tmp_metrics_dir / ".agent_metrics.json", state)

    store = MetricsStore(project_name="test-project", metrics_dir=tmp_metrics_dir)
    loaded = store.load()

    # All canonical agents should be present after load
    for name in ALL_AGENT_NAMES:
        assert name in loaded["agents"], f"Missing canonical agent: {name}"


def test_metrics_store_save_and_reload(tmp_metrics_dir):
    """MetricsStore.save() persists state that can be reloaded correctly."""
    store = MetricsStore(project_name="test-project", metrics_dir=tmp_metrics_dir)

    state = store.load()  # fresh empty state
    state["total_tokens"] = 42000
    state["total_sessions"] = 5
    store.save(state)

    # Create a new store instance pointing to the same directory
    store2 = MetricsStore(project_name="test-project", metrics_dir=tmp_metrics_dir)
    reloaded = store2.load()

    assert reloaded["total_tokens"] == 42000
    assert reloaded["total_sessions"] == 5


# ---------------------------------------------------------------------------
# Tests: GET /api/metrics returns data from MetricsStore (not hardcoded)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_metrics_returns_metrics_store_data(client):
    """GET /api/metrics returns data sourced from .agent_metrics.json via MetricsStore."""
    c, tmp_dir = client

    # Write a specific state to disk
    state = _make_metrics_state(total_tokens=77777, total_cost_usd=3.14)
    _write_metrics_file(tmp_dir / ".agent_metrics.json", state)

    resp = await c.get("/api/metrics")
    assert resp.status == 200
    data = await resp.json()

    # Response must reflect what was written to disk
    assert data["total_tokens"] == 77777
    assert data["total_cost_usd"] == pytest.approx(3.14, rel=1e-3)
    assert data["project_name"] == "test-project"


@pytest.mark.asyncio
async def test_get_metrics_not_hardcoded(client):
    """GET /api/metrics reflects disk state, not a hardcoded constant."""
    c, tmp_dir = client

    # Write state with distinctive token count
    state = _make_metrics_state(total_tokens=123456)
    _write_metrics_file(tmp_dir / ".agent_metrics.json", state)

    resp = await c.get("/api/metrics")
    assert resp.status == 200
    data = await resp.json()

    # If the value were hardcoded, it would not match our written value
    assert data["total_tokens"] == 123456


@pytest.mark.asyncio
async def test_get_metrics_updates_when_file_changes(client):
    """GET /api/metrics reflects updated .agent_metrics.json on subsequent requests."""
    c, tmp_dir = client
    metrics_path = tmp_dir / ".agent_metrics.json"

    # First state
    _write_metrics_file(metrics_path, _make_metrics_state(total_tokens=100))
    resp1 = await c.get("/api/metrics")
    data1 = await resp1.json()
    assert data1["total_tokens"] == 100

    # Update the file
    _write_metrics_file(metrics_path, _make_metrics_state(total_tokens=999))
    resp2 = await c.get("/api/metrics")
    data2 = await resp2.json()
    assert data2["total_tokens"] == 999


@pytest.mark.asyncio
async def test_get_metrics_has_required_fields(client):
    """GET /api/metrics response includes all DashboardState required fields."""
    c, tmp_dir = client

    resp = await c.get("/api/metrics")
    assert resp.status == 200
    data = await resp.json()

    required_fields = [
        "version", "project_name", "created_at", "updated_at",
        "total_sessions", "total_tokens", "total_cost_usd",
        "total_duration_seconds", "agents", "events", "sessions",
    ]
    for field in required_fields:
        assert field in data, f"Missing required field in /api/metrics response: {field}"


# ---------------------------------------------------------------------------
# Tests: GET /api/agents returns agents from definitions (not hardcoded list)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_agents_returns_all_canonical_agents(client):
    """GET /api/agents includes all canonical agents defined in ALL_AGENT_NAMES."""
    c, _ = client

    resp = await c.get("/api/agents")
    assert resp.status == 200
    data = await resp.json()

    returned_names = {a["agent_name"] for a in data["agents"] if "agent_name" in a}
    for name in ALL_AGENT_NAMES:
        assert name in returned_names, f"Canonical agent '{name}' missing from /api/agents"


@pytest.mark.asyncio
async def test_get_agents_count_matches_canonical_list(client):
    """GET /api/agents returns the same number of agents as ALL_AGENT_NAMES."""
    c, _ = client

    resp = await c.get("/api/agents")
    assert resp.status == 200
    data = await resp.json()

    # The response should have at least as many agents as the canonical list
    assert data["total_agents"] >= len(ALL_AGENT_NAMES)


@pytest.mark.asyncio
async def test_get_agents_data_comes_from_metrics_store(client):
    """GET /api/agents reflects data from .agent_metrics.json, not hardcoded."""
    c, tmp_dir = client

    # Write a file with a specific invocation count for an agent
    state = _make_metrics_state(
        agents={
            "coding": {
                "agent_name": "coding",
                "total_invocations": 42,
                "successful_invocations": 40,
                "failed_invocations": 2,
                "total_tokens": 5000,
                "total_cost_usd": 0.5,
                "total_duration_seconds": 100.0,
                "commits_made": 0,
                "prs_created": 0,
                "prs_merged": 0,
                "files_created": 0,
                "files_modified": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "tests_written": 0,
                "issues_created": 0,
                "issues_completed": 0,
                "messages_sent": 0,
                "reviews_completed": 0,
                "success_rate": 0.95,
                "avg_duration_seconds": 2.5,
                "avg_tokens_per_call": 119.0,
                "cost_per_success_usd": 0.0125,
                "xp": 200,
                "level": 3,
                "current_streak": 5,
                "best_streak": 10,
                "achievements": [],
                "strengths": [],
                "weaknesses": [],
                "recent_events": [],
                "last_error": "",
                "last_active": "2024-06-01T10:00:00Z",
            }
        }
    )
    _write_metrics_file(tmp_dir / ".agent_metrics.json", state)

    resp = await c.get("/api/agents")
    assert resp.status == 200
    data = await resp.json()

    # Find the coding agent in the response
    coding = next((a for a in data["agents"] if a.get("agent_name") == "coding"), None)
    assert coding is not None, "coding agent should be in /api/agents response"
    assert coding["total_invocations"] == 42


# ---------------------------------------------------------------------------
# Tests: GET /api/providers provider detection via env vars
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_providers_claude_available_when_anthropic_key_set(client):
    """Claude provider is available when ANTHROPIC_API_KEY is set."""
    c, _ = client

    with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-anthropic-key"}, clear=False):
        resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    claude = next((p for p in data["providers"] if p["provider_id"] == "claude"), None)
    assert claude is not None, "Claude provider must be in /api/providers response"
    assert claude["available"] is True, "Claude must be available when ANTHROPIC_API_KEY is set"


@pytest.mark.asyncio
async def test_get_providers_claude_unavailable_when_no_anthropic_key(client):
    """Claude provider is unavailable when ANTHROPIC_API_KEY is not set."""
    c, _ = client

    env_without_key = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    with mock.patch.dict(os.environ, env_without_key, clear=True):
        resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    claude = next((p for p in data["providers"] if p["provider_id"] == "claude"), None)
    assert claude is not None, "Claude provider must always be listed"
    assert claude["available"] is False, "Claude must be unavailable when ANTHROPIC_API_KEY is not set"


@pytest.mark.asyncio
async def test_get_providers_openai_available_when_key_set(client):
    """OpenAI/ChatGPT provider is available when OPENAI_API_KEY is set."""
    c, _ = client

    with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"}, clear=False):
        resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    openai = next((p for p in data["providers"] if p["provider_id"] == "openai"), None)
    assert openai is not None
    assert openai["available"] is True


@pytest.mark.asyncio
async def test_get_providers_openai_unavailable_without_key(client):
    """OpenAI provider shows unavailable when OPENAI_API_KEY is not set."""
    c, _ = client

    env_without_key = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    with mock.patch.dict(os.environ, env_without_key, clear=True):
        resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    openai = next((p for p in data["providers"] if p["provider_id"] == "openai"), None)
    assert openai is not None
    assert openai["available"] is False, "OpenAI should be unavailable without OPENAI_API_KEY"


@pytest.mark.asyncio
async def test_get_providers_gemini_detected_via_google_api_key(client):
    """Gemini provider is available when GOOGLE_API_KEY is set (not just GEMINI_API_KEY)."""
    c, _ = client

    # Only set GOOGLE_API_KEY (not GEMINI_API_KEY)
    env_with_google_key = {
        k: v for k, v in os.environ.items()
        if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    }
    env_with_google_key["GOOGLE_API_KEY"] = "test-google-key"
    with mock.patch.dict(os.environ, env_with_google_key, clear=True):
        resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    gemini = next((p for p in data["providers"] if p["provider_id"] == "gemini"), None)
    assert gemini is not None
    assert gemini["available"] is True, "Gemini must be available when GOOGLE_API_KEY is set"


@pytest.mark.asyncio
async def test_get_providers_gemini_detected_via_gemini_api_key(client):
    """Gemini provider is available when GEMINI_API_KEY is set."""
    c, _ = client

    env_with_gemini_key = {
        k: v for k, v in os.environ.items()
        if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    }
    env_with_gemini_key["GEMINI_API_KEY"] = "test-gemini-key"
    with mock.patch.dict(os.environ, env_with_gemini_key, clear=True):
        resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    gemini = next((p for p in data["providers"] if p["provider_id"] == "gemini"), None)
    assert gemini is not None
    assert gemini["available"] is True, "Gemini must be available when GEMINI_API_KEY is set"


@pytest.mark.asyncio
async def test_get_providers_gemini_unavailable_without_any_key(client):
    """Gemini provider is unavailable when neither GEMINI_API_KEY nor GOOGLE_API_KEY is set."""
    c, _ = client

    env_without_gemini = {
        k: v for k, v in os.environ.items()
        if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    }
    with mock.patch.dict(os.environ, env_without_gemini, clear=True):
        resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    gemini = next((p for p in data["providers"] if p["provider_id"] == "gemini"), None)
    assert gemini is not None
    assert gemini["available"] is False, "Gemini must be unavailable without any API key"


@pytest.mark.asyncio
async def test_get_providers_groq_detected_via_groq_api_key(client):
    """Groq provider is available when GROQ_API_KEY is set."""
    c, _ = client

    env_with_groq = {k: v for k, v in os.environ.items() if k != "GROQ_API_KEY"}
    env_with_groq["GROQ_API_KEY"] = "test-groq-key"
    with mock.patch.dict(os.environ, env_with_groq, clear=True):
        resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    groq = next((p for p in data["providers"] if p["provider_id"] == "groq"), None)
    assert groq is not None
    assert groq["available"] is True, "Groq must be available when GROQ_API_KEY is set"


@pytest.mark.asyncio
async def test_get_providers_groq_unavailable_without_key(client):
    """Groq provider is unavailable when GROQ_API_KEY is not set."""
    c, _ = client

    env_without_groq = {k: v for k, v in os.environ.items() if k != "GROQ_API_KEY"}
    with mock.patch.dict(os.environ, env_without_groq, clear=True):
        resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    groq = next((p for p in data["providers"] if p["provider_id"] == "groq"), None)
    assert groq is not None
    assert groq["available"] is False, "Groq must be unavailable without GROQ_API_KEY"


@pytest.mark.asyncio
async def test_get_providers_kimi_detected_via_moonshot_api_key(client):
    """KIMI provider is available when MOONSHOT_API_KEY is set (not just KIMI_API_KEY)."""
    c, _ = client

    # Only set MOONSHOT_API_KEY (not KIMI_API_KEY)
    env_with_moonshot = {
        k: v for k, v in os.environ.items()
        if k not in ("KIMI_API_KEY", "MOONSHOT_API_KEY")
    }
    env_with_moonshot["MOONSHOT_API_KEY"] = "test-moonshot-key"
    with mock.patch.dict(os.environ, env_with_moonshot, clear=True):
        resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    kimi = next((p for p in data["providers"] if p["provider_id"] == "kimi"), None)
    assert kimi is not None
    assert kimi["available"] is True, "KIMI must be available when MOONSHOT_API_KEY is set"


@pytest.mark.asyncio
async def test_get_providers_kimi_detected_via_kimi_api_key(client):
    """KIMI provider is available when KIMI_API_KEY is set."""
    c, _ = client

    env_with_kimi = {
        k: v for k, v in os.environ.items()
        if k not in ("KIMI_API_KEY", "MOONSHOT_API_KEY")
    }
    env_with_kimi["KIMI_API_KEY"] = "test-kimi-key"
    with mock.patch.dict(os.environ, env_with_kimi, clear=True):
        resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    kimi = next((p for p in data["providers"] if p["provider_id"] == "kimi"), None)
    assert kimi is not None
    assert kimi["available"] is True, "KIMI must be available when KIMI_API_KEY is set"


@pytest.mark.asyncio
async def test_get_providers_kimi_unavailable_without_any_key(client):
    """KIMI provider is unavailable when neither KIMI_API_KEY nor MOONSHOT_API_KEY is set."""
    c, _ = client

    env_without_kimi = {
        k: v for k, v in os.environ.items()
        if k not in ("KIMI_API_KEY", "MOONSHOT_API_KEY")
    }
    with mock.patch.dict(os.environ, env_without_kimi, clear=True):
        resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    kimi = next((p for p in data["providers"] if p["provider_id"] == "kimi"), None)
    assert kimi is not None
    assert kimi["available"] is False, "KIMI must be unavailable without any API key"


@pytest.mark.asyncio
async def test_get_providers_returns_all_six_providers(client):
    """GET /api/providers returns entries for all 6 expected AI providers."""
    c, _ = client

    resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    provider_ids = {p["provider_id"] for p in data["providers"]}
    expected_ids = {"claude", "openai", "gemini", "groq", "kimi", "windsurf"}
    assert expected_ids.issubset(provider_ids), (
        f"Missing providers: {expected_ids - provider_ids}"
    )


@pytest.mark.asyncio
async def test_get_providers_availability_is_not_hardcoded(client):
    """Provider availability responds dynamically to env var changes, not hardcoded values."""
    c, _ = client

    # Without any keys
    env_no_keys = {
        k: v for k, v in os.environ.items()
        if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
                     "GEMINI_API_KEY", "GROQ_API_KEY", "KIMI_API_KEY", "MOONSHOT_API_KEY",
                     "WINDSURF_API_KEY")
    }
    with mock.patch.dict(os.environ, env_no_keys, clear=True):
        resp = await c.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()

    # All providers should show unavailable without keys
    for provider in data["providers"]:
        assert provider["available"] is False, (
            f"Provider '{provider['provider_id']}' should be unavailable without API key, "
            f"but got available={provider['available']}"
        )


# ---------------------------------------------------------------------------
# Tests: ALL_AGENT_NAMES consistency with agents/definitions.py
# ---------------------------------------------------------------------------

def test_all_agent_names_contains_expected_agents():
    """ALL_AGENT_NAMES in metrics_store includes the core agent names."""
    # These are the canonical agent names that must be present
    expected_core_agents = [
        "linear", "coding", "coding_fast", "github",
        "pr_reviewer", "pr_reviewer_fast", "ops", "slack",
        "chatgpt", "gemini", "groq", "kimi", "windsurf",
    ]
    for name in expected_core_agents:
        assert name in ALL_AGENT_NAMES, f"Expected agent '{name}' missing from ALL_AGENT_NAMES"


def test_all_agent_names_is_not_empty():
    """ALL_AGENT_NAMES is a non-empty list of strings."""
    assert isinstance(ALL_AGENT_NAMES, list)
    assert len(ALL_AGENT_NAMES) > 0
    for name in ALL_AGENT_NAMES:
        assert isinstance(name, str)
        assert len(name) > 0
