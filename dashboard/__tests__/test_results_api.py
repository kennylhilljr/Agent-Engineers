"""Tests for AI-165: REQ-CODE-003: Implement Test Results Display.

Tests cover:
- POST /api/test-results returns 201
- Pass rate computed correctly
- GET /api/test-results returns list
- GET /api/test-results/{ticket} returns ticket-specific results
- WebSocket receives test_results event
- Circular buffer caps at 200
- Failed test with error_output stored correctly
- Screenshot path stored correctly
- Duration stored correctly
"""

import json
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.server import DashboardServer, TEST_RESULTS_MAX


# ---------------------------------------------------------------------------
# Test helpers / base class
# ---------------------------------------------------------------------------

class TestResultsBase(AioHTTPTestCase):
    """Base class: creates a fresh DashboardServer for each test method."""

    async def get_application(self):
        self._temp_dir = tempfile.mkdtemp()
        self._ds = DashboardServer(
            project_name="test-test-results",
            metrics_dir=Path(self._temp_dir),
        )
        return self._ds.app

    async def _post_test_results(self, payload):
        """Helper: POST test results and return the response."""
        return await self.client.request(
            "POST",
            "/api/test-results",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def _make_test_item(self, name="test_example", status="passed",
                        duration_ms=45, error_output="", screenshot_path=""):
        """Helper: build a test item dict."""
        return {
            "name": name,
            "status": status,
            "duration_ms": duration_ms,
            "error_output": error_output,
            "screenshot_path": screenshot_path,
        }

    def _make_payload(self, agent="coding", ticket="AI-42",
                      command="python -m pytest dashboard/__tests__/ -v",
                      status="passed", total=42, passed=40, failed=2,
                      errors=0, duration_ms=3200, tests=None, full_output=""):
        """Helper: build a full POST payload."""
        if tests is None:
            tests = [self._make_test_item()]
        return {
            "agent": agent,
            "ticket": ticket,
            "command": command,
            "status": status,
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "duration_ms": duration_ms,
            "tests": tests,
            "full_output": full_output,
        }


# ---------------------------------------------------------------------------
# 1. POST /api/test-results returns 201
# ---------------------------------------------------------------------------

class TestPostTestResults(TestResultsBase):
    """POST /api/test-results creates a record and returns HTTP 201."""

    @unittest_run_loop
    async def test_post_returns_201(self):
        """POST /api/test-results returns HTTP 201."""
        resp = await self._post_test_results(self._make_payload())
        assert resp.status == 201

    @unittest_run_loop
    async def test_post_returns_required_fields(self):
        """POST /api/test-results returns all required fields."""
        payload = self._make_payload(
            agent="coding",
            ticket="AI-165",
            command="python -m pytest dashboard/__tests__/ -v",
            status="passed",
            total=42,
            passed=40,
            failed=2,
        )
        resp = await self._post_test_results(payload)
        assert resp.status == 201
        data = await resp.json()

        assert data["agent"] == "coding"
        assert data["ticket"] == "AI-165"
        assert data["command"] == "python -m pytest dashboard/__tests__/ -v"
        assert data["status"] == "passed"
        assert data["total"] == 42
        assert data["passed"] == 40
        assert data["failed"] == 2
        assert "pass_rate" in data
        assert "timestamp" in data
        assert "tests" in data

    @unittest_run_loop
    async def test_post_missing_command_returns_400(self):
        """POST /api/test-results without command field returns 400."""
        payload = self._make_payload()
        del payload["command"]
        resp = await self._post_test_results(payload)
        assert resp.status == 400

    @unittest_run_loop
    async def test_post_invalid_json_returns_400(self):
        """POST /api/test-results with invalid JSON returns 400."""
        resp = await self.client.request(
            "POST",
            "/api/test-results",
            data="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    @unittest_run_loop
    async def test_post_status_passed(self):
        """POST /api/test-results with status=passed stores correctly."""
        resp = await self._post_test_results(self._make_payload(status="passed"))
        data = await resp.json()
        assert data["status"] == "passed"

    @unittest_run_loop
    async def test_post_status_failed(self):
        """POST /api/test-results with status=failed stores correctly."""
        resp = await self._post_test_results(self._make_payload(status="failed"))
        data = await resp.json()
        assert data["status"] == "failed"

    @unittest_run_loop
    async def test_post_status_error(self):
        """POST /api/test-results with status=error stores correctly."""
        resp = await self._post_test_results(self._make_payload(status="error"))
        data = await resp.json()
        assert data["status"] == "error"

    @unittest_run_loop
    async def test_post_invalid_status_normalised_to_error(self):
        """POST /api/test-results with invalid status normalises to error."""
        resp = await self._post_test_results(self._make_payload(status="unknown"))
        data = await resp.json()
        assert data["status"] == "error"

    @unittest_run_loop
    async def test_post_auto_sets_timestamp(self):
        """POST /api/test-results auto-sets a timestamp."""
        resp = await self._post_test_results(self._make_payload())
        data = await resp.json()
        assert "timestamp" in data
        assert len(data["timestamp"]) > 0


# ---------------------------------------------------------------------------
# 2. Pass rate computed correctly
# ---------------------------------------------------------------------------

class TestPassRateComputation(TestResultsBase):
    """Pass rate is computed correctly from passed/total."""

    @unittest_run_loop
    async def test_pass_rate_100_percent(self):
        """Pass rate is 100.0 when all tests pass."""
        resp = await self._post_test_results(
            self._make_payload(total=10, passed=10, failed=0)
        )
        data = await resp.json()
        assert data["pass_rate"] == 100.0

    @unittest_run_loop
    async def test_pass_rate_0_percent(self):
        """Pass rate is 0.0 when no tests pass."""
        resp = await self._post_test_results(
            self._make_payload(total=10, passed=0, failed=10)
        )
        data = await resp.json()
        assert data["pass_rate"] == 0.0

    @unittest_run_loop
    async def test_pass_rate_partial(self):
        """Pass rate is computed correctly for partial pass."""
        # 40 passed out of 42 = 95.2%
        resp = await self._post_test_results(
            self._make_payload(total=42, passed=40, failed=2)
        )
        data = await resp.json()
        assert data["pass_rate"] == pytest.approx(95.2, abs=0.2)

    @unittest_run_loop
    async def test_pass_rate_zero_total(self):
        """Pass rate is 0.0 when total is 0 (no division by zero)."""
        resp = await self._post_test_results(
            self._make_payload(total=0, passed=0, failed=0)
        )
        data = await resp.json()
        assert data["pass_rate"] == 0.0

    @unittest_run_loop
    async def test_pass_rate_stored_in_buffer(self):
        """Pass rate is persisted in the internal buffer."""
        await self._post_test_results(
            self._make_payload(total=5, passed=4, failed=1)
        )
        record = self._ds._test_results[-1]
        assert record["pass_rate"] == pytest.approx(80.0, abs=0.2)


# ---------------------------------------------------------------------------
# 3. GET /api/test-results returns list
# ---------------------------------------------------------------------------

class TestGetTestResults(TestResultsBase):
    """GET /api/test-results returns the recent results list."""

    @unittest_run_loop
    async def test_get_initially_empty(self):
        """GET /api/test-results returns empty list on a fresh server."""
        resp = await self.client.request("GET", "/api/test-results")
        assert resp.status == 200
        data = await resp.json()
        assert "results" in data
        assert "total" in data
        assert data["results"] == []
        assert data["total"] == 0

    @unittest_run_loop
    async def test_get_returns_stored_results(self):
        """GET /api/test-results returns previously submitted results."""
        for i in range(3):
            await self._post_test_results(
                self._make_payload(command=f"pytest test_{i}.py -v")
            )
        resp = await self.client.request("GET", "/api/test-results")
        data = await resp.json()
        assert data["total"] == 3
        assert len(data["results"]) == 3

    @unittest_run_loop
    async def test_get_returns_newest_first(self):
        """GET /api/test-results returns newest results first."""
        commands = [f"pytest test_{i}.py" for i in range(3)]
        for cmd in commands:
            await self._post_test_results(self._make_payload(command=cmd))
        resp = await self.client.request("GET", "/api/test-results")
        data = await resp.json()
        # The last posted command should be first in the response
        assert data["results"][0]["command"] == commands[-1]

    @unittest_run_loop
    async def test_get_returns_at_most_50(self):
        """GET /api/test-results returns at most 50 results."""
        for i in range(60):
            await self._post_test_results(
                self._make_payload(command=f"pytest test_{i}.py")
            )
        resp = await self.client.request("GET", "/api/test-results")
        data = await resp.json()
        assert data["total"] <= 50
        assert len(data["results"]) <= 50

    @unittest_run_loop
    async def test_get_content_type_json(self):
        """GET /api/test-results returns JSON content type."""
        resp = await self.client.request("GET", "/api/test-results")
        assert "application/json" in resp.headers.get("Content-Type", "")


# ---------------------------------------------------------------------------
# 4. GET /api/test-results/{ticket} returns ticket-specific results
# ---------------------------------------------------------------------------

class TestGetTestResultsByTicket(TestResultsBase):
    """GET /api/test-results/{ticket} returns results for a specific ticket."""

    @unittest_run_loop
    async def test_get_by_ticket_returns_matching_results(self):
        """GET /api/test-results/{ticket} returns results for that ticket."""
        ticket = "AI-165"
        await self._post_test_results(self._make_payload(ticket=ticket))
        await self._post_test_results(self._make_payload(ticket="AI-999"))

        resp = await self.client.request("GET", f"/api/test-results/{ticket}")
        assert resp.status == 200
        data = await resp.json()
        assert data["total"] == 1
        assert data["results"][0]["ticket"] == ticket

    @unittest_run_loop
    async def test_get_by_ticket_returns_all_runs_for_ticket(self):
        """GET /api/test-results/{ticket} returns all runs for that ticket."""
        ticket = "AI-42"
        for i in range(3):
            await self._post_test_results(
                self._make_payload(ticket=ticket, command=f"pytest run_{i}.py")
            )
        resp = await self.client.request("GET", f"/api/test-results/{ticket}")
        data = await resp.json()
        assert data["total"] == 3

    @unittest_run_loop
    async def test_get_by_ticket_returns_empty_for_unknown_ticket(self):
        """GET /api/test-results/{unknown} returns empty list (not 404)."""
        resp = await self.client.request("GET", "/api/test-results/AI-99999")
        assert resp.status == 200
        data = await resp.json()
        assert data["total"] == 0
        assert data["results"] == []

    @unittest_run_loop
    async def test_get_by_ticket_returns_newest_first(self):
        """GET /api/test-results/{ticket} returns newest runs first."""
        ticket = "AI-42"
        commands = [f"pytest run_{i}.py" for i in range(3)]
        for cmd in commands:
            await self._post_test_results(
                self._make_payload(ticket=ticket, command=cmd)
            )
        resp = await self.client.request("GET", f"/api/test-results/{ticket}")
        data = await resp.json()
        assert data["results"][0]["command"] == commands[-1]


# ---------------------------------------------------------------------------
# 5. WebSocket receives test_results event
# ---------------------------------------------------------------------------

class TestTestResultsWebSocket(TestResultsBase):
    """POST /api/test-results broadcasts test_results event to WebSocket clients."""

    @unittest_run_loop
    async def test_post_broadcasts_test_results_event(self):
        """POST /api/test-results sends a test_results message over WebSocket."""
        async with self.client.ws_connect('/ws') as ws:
            # Discard initial metrics_update message
            msg = await ws.receive_json(timeout=2)
            assert msg['type'] == 'metrics_update'

            payload = self._make_payload(
                agent="coding",
                ticket="AI-165",
                command="python -m pytest dashboard/__tests__/ -v",
                status="passed",
                total=42,
                passed=40,
                failed=2,
            )
            post_resp = await self._post_test_results(payload)
            assert post_resp.status == 201

            ws_msg = await ws.receive_json(timeout=2)
            assert ws_msg['type'] == 'test_results'
            assert ws_msg['agent'] == 'coding'
            assert ws_msg['ticket'] == 'AI-165'
            assert ws_msg['command'] == 'python -m pytest dashboard/__tests__/ -v'
            assert ws_msg['status'] == 'passed'
            assert ws_msg['total'] == 42
            assert ws_msg['passed'] == 40
            assert ws_msg['failed'] == 2
            assert 'pass_rate' in ws_msg
            assert 'timestamp' in ws_msg

    @unittest_run_loop
    async def test_broadcast_includes_test_list(self):
        """WebSocket message includes the tests list."""
        async with self.client.ws_connect('/ws') as ws:
            await ws.receive_json(timeout=2)  # discard metrics_update

            tests = [
                self._make_test_item("test_one", "passed"),
                self._make_test_item("test_two", "failed", error_output="AssertionError"),
            ]
            payload = self._make_payload(tests=tests, total=2, passed=1, failed=1)
            await self._post_test_results(payload)

            ws_msg = await ws.receive_json(timeout=2)
            assert ws_msg['type'] == 'test_results'
            assert isinstance(ws_msg['tests'], list)
            assert len(ws_msg['tests']) == 2


# ---------------------------------------------------------------------------
# 6. Circular buffer caps at 200
# ---------------------------------------------------------------------------

class TestCircularBuffer(TestResultsBase):
    """_test_results circular buffer is capped at TEST_RESULTS_MAX (200)."""

    @unittest_run_loop
    async def test_buffer_caps_at_200(self):
        """Submitting more than 200 results keeps only the last 200."""
        for i in range(210):
            await self._post_test_results(
                self._make_payload(command=f"pytest test_{i}.py")
            )
        assert len(self._ds._test_results) <= TEST_RESULTS_MAX
        assert len(self._ds._test_results) == TEST_RESULTS_MAX

    @unittest_run_loop
    async def test_buffer_retains_most_recent_on_overflow(self):
        """After overflow, the buffer contains the most recently added records."""
        commands = [f"pytest test_{i}.py" for i in range(210)]
        for cmd in commands:
            await self._post_test_results(self._make_payload(command=cmd))
        stored_commands = [r["command"] for r in self._ds._test_results]
        expected_commands = commands[-TEST_RESULTS_MAX:]
        assert stored_commands == expected_commands

    @unittest_run_loop
    async def test_test_results_max_constant_is_200(self):
        """TEST_RESULTS_MAX constant equals 200."""
        assert TEST_RESULTS_MAX == 200


# ---------------------------------------------------------------------------
# 7. Failed test with error_output stored correctly
# ---------------------------------------------------------------------------

class TestErrorOutputStorage(TestResultsBase):
    """error_output for failed tests is stored correctly."""

    @unittest_run_loop
    async def test_failed_test_error_output_stored(self):
        """Failed test error_output is preserved in the record."""
        error_text = "AssertionError: assert 1 == 2\nTraceback (most recent call last):\n  File 'test.py', line 5"
        tests = [self._make_test_item("test_foo", "failed", error_output=error_text)]
        payload = self._make_payload(tests=tests, status="failed", total=1, passed=0, failed=1)
        await self._post_test_results(payload)
        record = self._ds._test_results[-1]
        assert record["tests"][0]["error_output"] == error_text

    @unittest_run_loop
    async def test_error_output_accessible_via_get(self):
        """error_output is returned by GET /api/test-results."""
        error_text = "SomeError: something went wrong"
        tests = [self._make_test_item("test_bar", "failed", error_output=error_text)]
        payload = self._make_payload(tests=tests, status="failed", total=1, passed=0, failed=1)
        await self._post_test_results(payload)
        resp = await self.client.request("GET", "/api/test-results")
        data = await resp.json()
        assert data["results"][0]["tests"][0]["error_output"] == error_text

    @unittest_run_loop
    async def test_passed_test_empty_error_output(self):
        """Passed test has empty error_output."""
        tests = [self._make_test_item("test_pass", "passed")]
        payload = self._make_payload(tests=tests)
        await self._post_test_results(payload)
        record = self._ds._test_results[-1]
        assert record["tests"][0]["error_output"] == ""

    @unittest_run_loop
    async def test_multiple_failed_tests_error_output(self):
        """Multiple failed tests each preserve their own error_output."""
        error1 = "Error in test_alpha"
        error2 = "Error in test_beta"
        tests = [
            self._make_test_item("test_alpha", "failed", error_output=error1),
            self._make_test_item("test_beta", "failed", error_output=error2),
        ]
        payload = self._make_payload(tests=tests, status="failed", total=2, passed=0, failed=2)
        await self._post_test_results(payload)
        record = self._ds._test_results[-1]
        assert record["tests"][0]["error_output"] == error1
        assert record["tests"][1]["error_output"] == error2

    @unittest_run_loop
    async def test_error_output_broadcast_via_websocket(self):
        """error_output is included in the WebSocket broadcast."""
        error_text = "Test failure output"

        async with self.client.ws_connect('/ws') as ws:
            await ws.receive_json(timeout=2)  # discard metrics_update

            tests = [self._make_test_item("test_ws", "failed", error_output=error_text)]
            payload = self._make_payload(tests=tests, status="failed", total=1, passed=0, failed=1)
            await self._post_test_results(payload)

            ws_msg = await ws.receive_json(timeout=2)
            assert ws_msg['type'] == 'test_results'
            assert ws_msg['tests'][0]['error_output'] == error_text


# ---------------------------------------------------------------------------
# 8. Screenshot path stored correctly
# ---------------------------------------------------------------------------

class TestScreenshotPathStorage(TestResultsBase):
    """screenshot_path is stored and returned correctly."""

    @unittest_run_loop
    async def test_screenshot_path_stored(self):
        """screenshot_path is preserved in the test record."""
        screenshot = "/tmp/playwright_screenshots/test_login.png"
        tests = [self._make_test_item("test_login", "failed", screenshot_path=screenshot)]
        payload = self._make_payload(tests=tests, status="failed", total=1, passed=0, failed=1)
        await self._post_test_results(payload)
        record = self._ds._test_results[-1]
        assert record["tests"][0]["screenshot_path"] == screenshot

    @unittest_run_loop
    async def test_screenshot_path_accessible_via_get(self):
        """screenshot_path is returned by GET /api/test-results."""
        screenshot = "/screenshots/test_dashboard.png"
        tests = [self._make_test_item("test_dashboard", "failed", screenshot_path=screenshot)]
        payload = self._make_payload(tests=tests, status="failed", total=1, passed=0, failed=1)
        await self._post_test_results(payload)
        resp = await self.client.request("GET", "/api/test-results")
        data = await resp.json()
        assert data["results"][0]["tests"][0]["screenshot_path"] == screenshot

    @unittest_run_loop
    async def test_screenshot_path_empty_when_not_provided(self):
        """screenshot_path defaults to empty string when not provided."""
        tests = [{"name": "test_no_screenshot", "status": "passed", "duration_ms": 10}]
        payload = self._make_payload(tests=tests)
        await self._post_test_results(payload)
        record = self._ds._test_results[-1]
        assert record["tests"][0]["screenshot_path"] == ""

    @unittest_run_loop
    async def test_screenshot_path_broadcast_via_websocket(self):
        """screenshot_path is included in the WebSocket broadcast."""
        screenshot = "/screenshots/ws_test.png"

        async with self.client.ws_connect('/ws') as ws:
            await ws.receive_json(timeout=2)  # discard metrics_update

            tests = [self._make_test_item("test_ws_shot", "failed", screenshot_path=screenshot)]
            payload = self._make_payload(tests=tests, status="failed", total=1, passed=0, failed=1)
            await self._post_test_results(payload)

            ws_msg = await ws.receive_json(timeout=2)
            assert ws_msg['type'] == 'test_results'
            assert ws_msg['tests'][0]['screenshot_path'] == screenshot


# ---------------------------------------------------------------------------
# 9. Duration stored correctly
# ---------------------------------------------------------------------------

class TestDurationStorage(TestResultsBase):
    """duration_ms for both overall run and individual tests is stored correctly."""

    @unittest_run_loop
    async def test_overall_duration_ms_stored(self):
        """Overall duration_ms is stored in the record."""
        payload = self._make_payload(duration_ms=3200)
        await self._post_test_results(payload)
        record = self._ds._test_results[-1]
        assert record["duration_ms"] == 3200

    @unittest_run_loop
    async def test_per_test_duration_ms_stored(self):
        """Per-test duration_ms is stored correctly."""
        tests = [self._make_test_item("test_fast", "passed", duration_ms=45)]
        payload = self._make_payload(tests=tests)
        await self._post_test_results(payload)
        record = self._ds._test_results[-1]
        assert record["tests"][0]["duration_ms"] == 45

    @unittest_run_loop
    async def test_duration_accessible_via_get(self):
        """duration_ms is returned by GET /api/test-results."""
        payload = self._make_payload(duration_ms=5000)
        await self._post_test_results(payload)
        resp = await self.client.request("GET", "/api/test-results")
        data = await resp.json()
        assert data["results"][0]["duration_ms"] == 5000

    @unittest_run_loop
    async def test_duration_broadcast_via_websocket(self):
        """duration_ms is included in the WebSocket broadcast."""
        async with self.client.ws_connect('/ws') as ws:
            await ws.receive_json(timeout=2)  # discard metrics_update

            payload = self._make_payload(duration_ms=1234)
            await self._post_test_results(payload)

            ws_msg = await ws.receive_json(timeout=2)
            assert ws_msg['type'] == 'test_results'
            assert ws_msg['duration_ms'] == 1234

    @unittest_run_loop
    async def test_none_duration_allowed(self):
        """duration_ms can be omitted (stored as None)."""
        payload = self._make_payload()
        del payload["duration_ms"]
        resp = await self._post_test_results(payload)
        assert resp.status == 201
        data = await resp.json()
        assert data["duration_ms"] is None

    @unittest_run_loop
    async def test_multiple_test_durations_stored(self):
        """Multiple tests each preserve their own duration_ms."""
        tests = [
            self._make_test_item("test_a", "passed", duration_ms=10),
            self._make_test_item("test_b", "passed", duration_ms=200),
            self._make_test_item("test_c", "failed", duration_ms=55),
        ]
        payload = self._make_payload(tests=tests, total=3, passed=2, failed=1)
        await self._post_test_results(payload)
        record = self._ds._test_results[-1]
        assert record["tests"][0]["duration_ms"] == 10
        assert record["tests"][1]["duration_ms"] == 200
        assert record["tests"][2]["duration_ms"] == 55


# ---------------------------------------------------------------------------
# 10. Full output stored correctly
# ---------------------------------------------------------------------------

class TestFullOutputStorage(TestResultsBase):
    """full_output field is stored and returned correctly."""

    @unittest_run_loop
    async def test_full_output_stored(self):
        """full_output is preserved in the record."""
        output = "===== test session starts =====\ncollected 42 items\n...\n42 passed in 3.2s"
        payload = self._make_payload(full_output=output)
        await self._post_test_results(payload)
        record = self._ds._test_results[-1]
        assert record["full_output"] == output

    @unittest_run_loop
    async def test_full_output_empty_when_not_provided(self):
        """full_output defaults to empty string when not provided."""
        payload = self._make_payload()
        del payload["full_output"]
        resp = await self._post_test_results(payload)
        data = await resp.json()
        assert data["full_output"] == ""

    @unittest_run_loop
    async def test_full_output_accessible_via_get(self):
        """full_output is returned by GET /api/test-results."""
        output = "PASSED - all good"
        payload = self._make_payload(full_output=output)
        await self._post_test_results(payload)
        resp = await self.client.request("GET", "/api/test-results")
        data = await resp.json()
        assert data["results"][0]["full_output"] == output
