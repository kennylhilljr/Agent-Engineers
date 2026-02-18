"""Integration tests for AI-166: REQ-TECH-001 Backend Async Server.

Audits and verifies the aiohttp-based DashboardServer against all acceptance
criteria defined in REQ-TECH-001:

    - Server starts and serves requests
    - All endpoints respond correctly
    - WebSocket connections work
    - Concurrent handling is robust
    - Graceful error handling
    - Minimal dependencies (aiohttp only)

Test categories
---------------
1.  GET /  returns 200 with HTML content
2.  All major REST endpoints return correct status codes
3.  WebSocket connection can be established and receives an initial message
4.  Concurrent requests are handled correctly (10 simultaneous GET /health)
5.  Error middleware returns structured JSON (not stack traces)
6.  Server starts on a custom port
7.  Health check returns expected fields
8.  CORS headers are present on responses
9.  OPTIONS preflight returns 204
10. WebSocket ping/pong
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

import pytest
from aiohttp import ClientSession, WSMsgType
from aiohttp import web

# Ensure the project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.server import DashboardServer

# -------------------------------------------------------------------------
# Port allocation: use a high port to avoid collision with other test suites
# -------------------------------------------------------------------------
_TEST_PORT = 18166


# -------------------------------------------------------------------------
# Shared server fixture
# -------------------------------------------------------------------------

@pytest.fixture
async def server():
    """Start a DashboardServer on _TEST_PORT, yield it, then tear down."""
    with tempfile.TemporaryDirectory() as tmpdir:
        srv = DashboardServer(
            project_name="test-ai166",
            metrics_dir=Path(tmpdir),
            port=_TEST_PORT,
            host="127.0.0.1",
        )
        runner = web.AppRunner(srv.app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", _TEST_PORT)
        await site.start()
        await asyncio.sleep(0.1)  # brief settle

        yield srv

        await runner.cleanup()


@pytest.fixture
def base_url():
    return f"http://127.0.0.1:{_TEST_PORT}"


@pytest.fixture
def ws_url():
    return f"http://127.0.0.1:{_TEST_PORT}/ws"


# =========================================================================
# 1. GET / returns 200 with HTML content
# =========================================================================

@pytest.mark.asyncio
async def test_root_returns_200(server, base_url):
    """GET / returns HTTP 200."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/") as resp:
            assert resp.status == 200


@pytest.mark.asyncio
async def test_root_returns_html_content_type(server, base_url):
    """GET / returns Content-Type text/html."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/") as resp:
            assert "text/html" in resp.content_type


@pytest.mark.asyncio
async def test_root_body_contains_html_tag(server, base_url):
    """GET / response body is a non-empty HTML document."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/") as resp:
            text = await resp.text()
            assert len(text) > 0
            # Must look like an HTML document
            assert "<html" in text.lower() or "<!doctype" in text.lower()


# =========================================================================
# 2. Health check endpoint
# =========================================================================

@pytest.mark.asyncio
async def test_health_returns_200(server, base_url):
    """GET /health returns HTTP 200."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/health") as resp:
            assert resp.status == 200


@pytest.mark.asyncio
async def test_health_returns_expected_fields(server, base_url):
    """GET /health returns all required fields: status, timestamp, project,
    metrics_file_exists, event_count, session_count, agent_count."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/health") as resp:
            data = await resp.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert "project" in data
    assert "metrics_file_exists" in data
    assert "event_count" in data
    assert "session_count" in data
    assert "agent_count" in data


@pytest.mark.asyncio
async def test_health_status_is_ok(server, base_url):
    """GET /health returns status='ok'."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/health") as resp:
            data = await resp.json()
    assert data["status"] == "ok"


# =========================================================================
# 3. All major REST endpoints return correct status codes
# =========================================================================

@pytest.mark.asyncio
async def test_get_metrics_returns_200(server, base_url):
    """GET /api/metrics returns HTTP 200."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/metrics") as resp:
            assert resp.status == 200


@pytest.mark.asyncio
async def test_get_metrics_returns_json(server, base_url):
    """GET /api/metrics returns valid JSON."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/metrics") as resp:
            data = await resp.json()
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_get_agent_unknown_returns_404(server, base_url):
    """GET /api/agents/{unknown} returns HTTP 404."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/agents/no_such_agent_xyz") as resp:
            assert resp.status == 404


@pytest.mark.asyncio
async def test_get_requirement_returns_200(server, base_url):
    """GET /api/requirements/{ticket_key} returns HTTP 200 for a valid key."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/requirements/AI-166") as resp:
            assert resp.status == 200


@pytest.mark.asyncio
async def test_get_requirement_invalid_key_returns_400(server, base_url):
    """GET /api/requirements/{invalid} returns HTTP 400 for an invalid key."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/requirements/invalid-key!!") as resp:
            assert resp.status == 400


@pytest.mark.asyncio
async def test_put_requirement_stores_and_returns_success(server, base_url):
    """PUT /api/requirements/{ticket_key} stores a requirement and returns success."""
    payload = {"requirement": "The server must handle 100 concurrent connections."}
    async with ClientSession() as session:
        async with session.put(
            f"{base_url}/api/requirements/AI-166",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
    assert data["success"] is True
    assert data["ticket_key"] == "AI-166"


@pytest.mark.asyncio
async def test_post_reasoning_returns_success(server, base_url):
    """POST /api/reasoning broadcasts a reasoning event and returns success."""
    payload = {"content": "Analysing dependencies…", "ticket": "AI-166"}
    async with ClientSession() as session:
        async with session.post(
            f"{base_url}/api/reasoning",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_post_agent_thinking_returns_success(server, base_url):
    """POST /api/agent-thinking stores an event and returns success."""
    payload = {
        "agent": "coding",
        "category": "files",
        "content": "Reading server.py…",
        "ticket": "AI-166",
    }
    async with ClientSession() as session:
        async with session.post(
            f"{base_url}/api/agent-thinking",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_get_reasoning_blocks_returns_200(server, base_url):
    """GET /api/reasoning/blocks returns HTTP 200 and expected structure."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/reasoning/blocks") as resp:
            assert resp.status == 200
            data = await resp.json()
    assert "blocks" in data
    assert "total" in data
    assert isinstance(data["blocks"], list)


@pytest.mark.asyncio
async def test_reasoning_blocks_reflect_thinking_posts(server, base_url):
    """GET /api/reasoning/blocks reflects previously POSTed agent-thinking events."""
    payload = {
        "agent": "coding",
        "category": "tests",
        "content": "Running test suite…",
        "ticket": "AI-166",
    }
    async with ClientSession() as session:
        await session.post(
            f"{base_url}/api/agent-thinking",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        async with session.get(f"{base_url}/api/reasoning/blocks") as resp:
            data = await resp.json()
    assert data["total"] >= 1
    contents = [b["content"] for b in data["blocks"]]
    assert "Running test suite…" in contents


@pytest.mark.asyncio
async def test_post_decision_returns_201(server, base_url):
    """POST /api/decisions returns HTTP 201 with a new decision record."""
    payload = {
        "type": "agent_selection",
        "ticket": "AI-166",
        "decision": "Use coding (sonnet) agent",
        "reason": "Server-side integration requires file access",
    }
    async with ClientSession() as session:
        async with session.post(
            f"{base_url}/api/decisions",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        ) as resp:
            assert resp.status == 201
            data = await resp.json()
    assert "id" in data
    assert data["decision"] == "Use coding (sonnet) agent"
    assert data["type"] == "agent_selection"


@pytest.mark.asyncio
async def test_get_decisions_returns_200(server, base_url):
    """GET /api/decisions returns HTTP 200 with decisions list."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/decisions") as resp:
            assert resp.status == 200
            data = await resp.json()
    assert "decisions" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_decisions_summary_returns_200(server, base_url):
    """GET /api/decisions/summary returns HTTP 200 with summary fields."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/decisions/summary") as resp:
            assert resp.status == 200
            data = await resp.json()
    assert "total" in data
    assert "by_type" in data
    assert "by_outcome" in data
    assert "recent_session_count" in data


@pytest.mark.asyncio
async def test_get_decisions_export_json(server, base_url):
    """GET /api/decisions/export returns HTTP 200 with a JSON array."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/decisions/export") as resp:
            assert resp.status == 200
            data = await resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_decisions_export_csv(server, base_url):
    """GET /api/decisions/export?format=csv returns a CSV download."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/decisions/export?format=csv") as resp:
            assert resp.status == 200
            assert "text/csv" in resp.content_type


@pytest.mark.asyncio
async def test_get_decision_by_unknown_id_returns_404(server, base_url):
    """GET /api/decisions/{unknown_id} returns HTTP 404."""
    async with ClientSession() as session:
        async with session.get(
            f"{base_url}/api/decisions/00000000-0000-0000-0000-000000000000"
        ) as resp:
            assert resp.status == 404


@pytest.mark.asyncio
async def test_get_decision_by_id_returns_record(server, base_url):
    """GET /api/decisions/{id} returns the decision that was just POSTed."""
    payload = {
        "type": "complexity",
        "ticket": "AI-166",
        "decision": "Large diff: use careful review",
        "reason": "Over 500 lines changed",
    }
    async with ClientSession() as session:
        # POST a decision first
        async with session.post(
            f"{base_url}/api/decisions",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        ) as post_resp:
            created = await post_resp.json()

        decision_id = created["id"]

        # Fetch by ID
        async with session.get(f"{base_url}/api/decisions/{decision_id}") as resp:
            assert resp.status == 200
            fetched = await resp.json()

    assert fetched["id"] == decision_id
    assert fetched["decision"] == "Large diff: use careful review"


@pytest.mark.asyncio
async def test_post_code_stream_returns_success(server, base_url):
    """POST /api/code-stream returns HTTP 200 with success and stream_id."""
    payload = {
        "agent": "coding",
        "file_path": "dashboard/server.py",
        "chunk": "def run(self):",
        "chunk_type": "addition",
        "is_final": False,
    }
    async with ClientSession() as session:
        async with session.post(
            f"{base_url}/api/code-stream",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
    assert data["success"] is True
    assert "stream_id" in data


@pytest.mark.asyncio
async def test_get_code_streams_returns_200(server, base_url):
    """GET /api/code-streams returns HTTP 200 with streams list."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/code-streams") as resp:
            assert resp.status == 200
            data = await resp.json()
    assert "streams" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_code_stream_by_id_returns_record(server, base_url):
    """GET /api/code-streams/{id} returns the stream that was just posted."""
    payload = {
        "agent": "coding",
        "file_path": "dashboard/server.py",
        "chunk": "    pass",
        "chunk_type": "context",
        "is_final": True,
    }
    async with ClientSession() as session:
        async with session.post(
            f"{base_url}/api/code-stream",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        ) as post_resp:
            created = await post_resp.json()

        stream_id = created["stream_id"]

        async with session.get(f"{base_url}/api/code-streams/{stream_id}") as resp:
            assert resp.status == 200
            data = await resp.json()

    assert data["stream_id"] == stream_id
    assert data["file_path"] == "dashboard/server.py"
    assert data["completed"] is True


@pytest.mark.asyncio
async def test_get_code_stream_unknown_id_returns_404(server, base_url):
    """GET /api/code-streams/{unknown} returns HTTP 404."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/code-streams/nonexistent-id") as resp:
            assert resp.status == 404


@pytest.mark.asyncio
async def test_post_file_changes_returns_201(server, base_url):
    """POST /api/file-changes returns HTTP 201 with the stored record."""
    payload = {
        "agent": "coding",
        "ticket": "AI-166",
        "files": [
            {
                "path": "dashboard/server.py",
                "status": "modified",
                "lines_added": 47,
                "lines_removed": 3,
            }
        ],
    }
    async with ClientSession() as session:
        async with session.post(
            f"{base_url}/api/file-changes",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        ) as resp:
            assert resp.status == 201
            data = await resp.json()
    assert data["agent"] == "coding"
    assert data["total_added"] == 47
    assert data["total_removed"] == 3
    assert "session_id" in data


@pytest.mark.asyncio
async def test_get_file_changes_returns_200(server, base_url):
    """GET /api/file-changes returns HTTP 200 with summaries list."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/file-changes") as resp:
            assert resp.status == 200
            data = await resp.json()
    assert "summaries" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_file_changes_by_session_returns_record(server, base_url):
    """GET /api/file-changes/{session_id} returns the record that was just POSTed."""
    payload = {
        "agent": "coding",
        "ticket": "AI-166",
        "files": [{"path": "init.sh", "status": "created", "lines_added": 20, "lines_removed": 0}],
    }
    async with ClientSession() as session:
        async with session.post(
            f"{base_url}/api/file-changes",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        ) as post_resp:
            created = await post_resp.json()

        session_id = created["session_id"]

        async with session.get(f"{base_url}/api/file-changes/{session_id}") as resp:
            assert resp.status == 200
            data = await resp.json()

    assert data["session_id"] == session_id
    assert data["files"][0]["path"] == "init.sh"


@pytest.mark.asyncio
async def test_get_file_changes_unknown_session_returns_404(server, base_url):
    """GET /api/file-changes/{unknown} returns HTTP 404."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/file-changes/no-such-session") as resp:
            assert resp.status == 404


@pytest.mark.asyncio
async def test_post_test_results_returns_201(server, base_url):
    """POST /api/test-results returns HTTP 201 with the stored record."""
    payload = {
        "agent": "coding",
        "ticket": "AI-166",
        "command": "python -m pytest dashboard/__tests__/test_server_integration.py -v",
        "status": "passed",
        "total": 30,
        "passed": 30,
        "failed": 0,
        "errors": 0,
        "duration_ms": 4200,
        "tests": [{"name": "test_root_returns_200", "status": "passed", "duration_ms": 55}],
    }
    async with ClientSession() as session:
        async with session.post(
            f"{base_url}/api/test-results",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        ) as resp:
            assert resp.status == 201
            data = await resp.json()
    assert data["status"] == "passed"
    assert data["pass_rate"] == 100.0
    assert data["total"] == 30


@pytest.mark.asyncio
async def test_get_test_results_returns_200(server, base_url):
    """GET /api/test-results returns HTTP 200 with results list."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/test-results") as resp:
            assert resp.status == 200
            data = await resp.json()
    assert "results" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_test_results_by_ticket_returns_200(server, base_url):
    """GET /api/test-results/{ticket} returns HTTP 200."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/test-results/AI-166") as resp:
            assert resp.status == 200
            data = await resp.json()
    assert "results" in data


# =========================================================================
# 4. WebSocket connection established and receives initial message
# =========================================================================

@pytest.mark.asyncio
async def test_websocket_connection_established(server, ws_url):
    """WebSocket at /ws can be connected."""
    async with ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
            assert not ws.closed


@pytest.mark.asyncio
async def test_websocket_receives_initial_metrics(server, ws_url):
    """WebSocket at /ws immediately sends a metrics_update message on connect."""
    async with ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
            msg = await ws.receive(timeout=3)
            assert msg.type == WSMsgType.TEXT
            data = json.loads(msg.data)
    assert data.get("type") == "metrics_update"
    assert "data" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_websocket_ping_pong(server, ws_url):
    """WebSocket responds 'pong' when sent 'ping'."""
    async with ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
            # Consume the initial metrics message
            await ws.receive(timeout=3)
            await ws.send_str("ping")
            msg = await ws.receive(timeout=3)
    assert msg.type == WSMsgType.TEXT
    assert msg.data == "pong"


@pytest.mark.asyncio
async def test_websocket_receives_reasoning_broadcast(server, base_url, ws_url):
    """WebSocket clients receive events broadcast by POST /api/reasoning."""
    async with ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
            # Consume initial metrics update
            await ws.receive(timeout=3)

            # Trigger broadcast
            await session.post(
                f"{base_url}/api/reasoning",
                data=json.dumps({"content": "ws-reasoning-test", "ticket": "AI-166"}),
                headers={"Content-Type": "application/json"},
            )

            # Should receive the reasoning event
            msg = await ws.receive(timeout=3)
            data = json.loads(msg.data)

    assert data.get("type") == "reasoning"
    assert data.get("content") == "ws-reasoning-test"


@pytest.mark.asyncio
async def test_websocket_multiple_clients(server, ws_url):
    """Multiple WebSocket clients can connect simultaneously."""
    async with ClientSession() as session:
        async with session.ws_connect(ws_url) as ws1:
            async with session.ws_connect(ws_url) as ws2:
                assert not ws1.closed
                assert not ws2.closed
                assert len(server.websockets) == 2


# =========================================================================
# 5. Concurrent requests handled correctly (10 simultaneous GET /health)
# =========================================================================

@pytest.mark.asyncio
async def test_concurrent_requests(server, base_url):
    """10 simultaneous GET /health requests all return 200."""
    async def get_health(session):
        async with session.get(f"{base_url}/health") as resp:
            return resp.status

    async with ClientSession() as session:
        results = await asyncio.gather(
            *[get_health(session) for _ in range(10)]
        )

    assert all(status == 200 for status in results), (
        f"Not all requests succeeded: {results}"
    )


@pytest.mark.asyncio
async def test_concurrent_mixed_endpoints(server, base_url):
    """10 mixed-endpoint concurrent requests all return expected status codes."""
    endpoints = [
        ("/health", 200),
        ("/api/metrics", 200),
        ("/api/decisions", 200),
        ("/api/code-streams", 200),
        ("/api/file-changes", 200),
        ("/api/test-results", 200),
        ("/api/reasoning/blocks", 200),
        ("/api/decisions/summary", 200),
        ("/health", 200),
        ("/api/metrics", 200),
    ]

    async def fetch(session, path, expected):
        async with session.get(f"{base_url}{path}") as resp:
            return resp.status, expected

    async with ClientSession() as session:
        pairs = await asyncio.gather(
            *[fetch(session, path, expected) for path, expected in endpoints]
        )

    for actual, expected in pairs:
        assert actual == expected, f"Expected {expected}, got {actual}"


# =========================================================================
# 6. Error middleware returns structured JSON (not stack traces)
# =========================================================================

@pytest.mark.asyncio
async def test_error_middleware_on_unknown_route(server, base_url):
    """An unknown route returns HTTP 404 (not a stack trace in 500)."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/api/does-not-exist") as resp:
            # aiohttp returns 404 for unknown routes; must not be 500
            assert resp.status == 404


@pytest.mark.asyncio
async def test_error_middleware_on_bad_json_post(server, base_url):
    """POST /api/decisions with invalid JSON returns HTTP 400 JSON error."""
    async with ClientSession() as session:
        async with session.post(
            f"{base_url}/api/decisions",
            data="this is not JSON!!!",
            headers={"Content-Type": "application/json"},
        ) as resp:
            assert resp.status == 400
            data = await resp.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_error_middleware_on_missing_required_field(server, base_url):
    """POST /api/decisions with missing 'decision' field returns HTTP 400 JSON."""
    async with ClientSession() as session:
        async with session.post(
            f"{base_url}/api/decisions",
            data=json.dumps({"type": "other"}),
            headers={"Content-Type": "application/json"},
        ) as resp:
            assert resp.status == 400
            data = await resp.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_error_middleware_structured_json_on_server_error(server, base_url):
    """Unhandled exceptions propagate as structured JSON (status 500).

    We force a server error by monkeypatching the metrics store to raise.
    """
    original_load = server.store.load

    def _explode():
        raise RuntimeError("Simulated internal error for AI-166 integration test")

    server.store.load = _explode
    try:
        async with ClientSession() as session:
            async with session.get(f"{base_url}/api/metrics") as resp:
                # The error_middleware should return 500 JSON
                assert resp.status == 500
                data = await resp.json()
        assert "error" in data or "message" in data
    finally:
        server.store.load = original_load


# =========================================================================
# 7. Server starts on custom port
# =========================================================================

@pytest.mark.asyncio
async def test_server_on_custom_port():
    """DashboardServer can start on an arbitrary custom port (18167)."""
    custom_port = 18167
    with tempfile.TemporaryDirectory() as tmpdir:
        srv = DashboardServer(
            project_name="test-custom-port",
            metrics_dir=Path(tmpdir),
            port=custom_port,
            host="127.0.0.1",
        )
        runner = web.AppRunner(srv.app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", custom_port)
        await site.start()
        await asyncio.sleep(0.1)

        try:
            async with ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{custom_port}/health") as resp:
                    assert resp.status == 200
        finally:
            await runner.cleanup()


# =========================================================================
# 8. CORS headers present on responses
# =========================================================================

@pytest.mark.asyncio
async def test_cors_header_present_on_health(server, base_url):
    """GET /health includes Access-Control-Allow-Origin header."""
    async with ClientSession() as session:
        async with session.get(
            f"{base_url}/health",
            headers={"Origin": "http://localhost:3000"},
        ) as resp:
            assert resp.status == 200
            assert "Access-Control-Allow-Origin" in resp.headers


@pytest.mark.asyncio
async def test_cors_methods_header(server, base_url):
    """Responses include Access-Control-Allow-Methods."""
    async with ClientSession() as session:
        async with session.get(f"{base_url}/health") as resp:
            assert "Access-Control-Allow-Methods" in resp.headers


# =========================================================================
# 9. OPTIONS preflight returns 204
# =========================================================================

@pytest.mark.asyncio
async def test_options_preflight_metrics(server, base_url):
    """OPTIONS /api/metrics returns HTTP 204 for CORS preflight."""
    async with ClientSession() as session:
        async with session.options(f"{base_url}/api/metrics") as resp:
            assert resp.status == 204


@pytest.mark.asyncio
async def test_options_preflight_decisions(server, base_url):
    """OPTIONS /api/decisions returns HTTP 204 for CORS preflight."""
    async with ClientSession() as session:
        async with session.options(f"{base_url}/api/decisions") as resp:
            assert resp.status == 204


# =========================================================================
# 10. WebSocket broadcast loop publishes periodic metrics_update messages
# =========================================================================

@pytest.mark.asyncio
async def test_websocket_broadcast_loop_running(server):
    """The periodic broadcast task is created and not yet cancelled."""
    assert server.broadcast_task is not None
    assert not server.broadcast_task.done()


# =========================================================================
# 11. aiohttp is used (not FastAPI / Flask / etc.)
# =========================================================================

def test_server_uses_aiohttp():
    """DashboardServer.app is an aiohttp web.Application (not a WSGI app)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        srv = DashboardServer(
            project_name="test-aiohttp-check",
            metrics_dir=Path(tmpdir),
        )
    assert isinstance(srv.app, web.Application)


# =========================================================================
# 12. Graceful shutdown: cleanup method closes websockets and cancels task
# =========================================================================

@pytest.mark.asyncio
async def test_graceful_cleanup_cancels_broadcast_task(server, ws_url):
    """On cleanup, the broadcast task is cancelled and WebSocket pool is cleared."""
    async with ClientSession() as session:
        async with session.ws_connect(ws_url) as _ws:
            # Consume initial message to ensure WS is live
            await _ws.receive(timeout=3)
            assert len(server.websockets) == 1

        # After the context manager exits, aiohttp marks ws as closed;
        # server will clean it up on next broadcast or cleanup.

    # Trigger cleanup manually to verify cancellation
    await server._cleanup_websockets(server.app)
    assert server.broadcast_task.cancelled() or server.broadcast_task.done()
    assert len(server.websockets) == 0
