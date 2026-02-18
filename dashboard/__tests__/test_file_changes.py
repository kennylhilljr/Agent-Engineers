"""Tests for AI-164: REQ-CODE-002: Implement File Change Summary.

Tests cover:
- POST /api/file-changes returns 201 with summary
- Files with all 3 statuses stored correctly
- Line counts stored correctly
- GET /api/file-changes returns list
- GET /api/file-changes/{session_id} returns specific summary
- WebSocket receives file_changes event
- Circular buffer caps at 100
- POST without files returns 400
- Diff content stored correctly when provided
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

from dashboard.server import DashboardServer, FILE_CHANGES_MAX


# ---------------------------------------------------------------------------
# Test helpers / base class
# ---------------------------------------------------------------------------

class TestFileChangesBase(AioHTTPTestCase):
    """Base class: creates a fresh DashboardServer for each test method."""

    async def get_application(self):
        self._temp_dir = tempfile.mkdtemp()
        self._ds = DashboardServer(
            project_name="test-file-changes",
            metrics_dir=Path(self._temp_dir),
        )
        return self._ds.app

    async def _post_file_changes(self, payload):
        """Helper: POST a file change summary and return the response."""
        return await self.client.request(
            "POST",
            "/api/file-changes",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def _make_file_entry(self, path="src/app.py", status="modified",
                         lines_added=10, lines_removed=2, diff=None):
        """Helper: build a file entry dict."""
        entry = {
            "path": path,
            "status": status,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
        }
        if diff is not None:
            entry["diff"] = diff
        return entry

    def _make_payload(self, files=None, agent="coding", ticket="AI-42",
                      session_id=None, total_added=None, total_removed=None):
        """Helper: build a full POST payload."""
        if files is None:
            files = [self._make_file_entry()]
        payload = {
            "agent": agent,
            "ticket": ticket,
            "files": files,
        }
        if session_id is not None:
            payload["session_id"] = session_id
        if total_added is not None:
            payload["total_added"] = total_added
        if total_removed is not None:
            payload["total_removed"] = total_removed
        return payload


# ---------------------------------------------------------------------------
# 1. POST /api/file-changes returns 201 with summary
# ---------------------------------------------------------------------------

class TestPostFileChanges(TestFileChangesBase):
    """POST /api/file-changes creates a record and returns HTTP 201."""

    @unittest_run_loop
    async def test_post_returns_201(self):
        """POST /api/file-changes returns HTTP 201."""
        resp = await self._post_file_changes(self._make_payload())
        assert resp.status == 201

    @unittest_run_loop
    async def test_post_returns_summary_with_required_fields(self):
        """POST /api/file-changes returns all required fields in the response."""
        sid = str(uuid4())
        payload = self._make_payload(
            session_id=sid,
            files=[self._make_file_entry(path="dashboard/server.py", status="modified",
                                         lines_added=47, lines_removed=3)],
            total_added=47,
            total_removed=3,
        )
        resp = await self._post_file_changes(payload)
        assert resp.status == 201
        data = await resp.json()

        assert data["session_id"] == sid
        assert data["agent"] == "coding"
        assert data["ticket"] == "AI-42"
        assert "files" in data
        assert "total_added" in data
        assert "total_removed" in data
        assert "timestamp" in data

    @unittest_run_loop
    async def test_post_auto_generates_session_id(self):
        """POST /api/file-changes auto-generates session_id when not provided."""
        payload = self._make_payload()
        # Do not provide session_id
        resp = await self._post_file_changes(payload)
        data = await resp.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    @unittest_run_loop
    async def test_post_auto_sets_timestamp(self):
        """POST /api/file-changes auto-sets timestamp when not provided."""
        payload = self._make_payload()
        resp = await self._post_file_changes(payload)
        data = await resp.json()
        assert "timestamp" in data
        assert len(data["timestamp"]) > 0

    @unittest_run_loop
    async def test_post_uses_provided_session_id(self):
        """POST /api/file-changes uses provided session_id."""
        sid = str(uuid4())
        resp = await self._post_file_changes(self._make_payload(session_id=sid))
        data = await resp.json()
        assert data["session_id"] == sid


# ---------------------------------------------------------------------------
# 2. Files with all 3 statuses stored correctly
# ---------------------------------------------------------------------------

class TestFileStatusStorage(TestFileChangesBase):
    """Files with created/modified/deleted status are stored correctly."""

    @unittest_run_loop
    async def test_created_status_stored(self):
        """File with status='created' is stored correctly."""
        sid = str(uuid4())
        payload = self._make_payload(
            session_id=sid,
            files=[self._make_file_entry(path="new.py", status="created",
                                         lines_added=50, lines_removed=0)],
        )
        await self._post_file_changes(payload)
        record = self._ds._file_changes[-1]
        assert record["files"][0]["status"] == "created"
        assert record["files"][0]["path"] == "new.py"

    @unittest_run_loop
    async def test_modified_status_stored(self):
        """File with status='modified' is stored correctly."""
        sid = str(uuid4())
        payload = self._make_payload(
            session_id=sid,
            files=[self._make_file_entry(path="existing.py", status="modified",
                                         lines_added=10, lines_removed=3)],
        )
        await self._post_file_changes(payload)
        record = self._ds._file_changes[-1]
        assert record["files"][0]["status"] == "modified"

    @unittest_run_loop
    async def test_deleted_status_stored(self):
        """File with status='deleted' is stored correctly."""
        sid = str(uuid4())
        payload = self._make_payload(
            session_id=sid,
            files=[self._make_file_entry(path="old.py", status="deleted",
                                         lines_added=0, lines_removed=100)],
        )
        await self._post_file_changes(payload)
        record = self._ds._file_changes[-1]
        assert record["files"][0]["status"] == "deleted"

    @unittest_run_loop
    async def test_all_three_statuses_in_one_request(self):
        """All 3 statuses can be submitted in a single request."""
        sid = str(uuid4())
        payload = self._make_payload(
            session_id=sid,
            files=[
                self._make_file_entry("a.py", "created", 20, 0),
                self._make_file_entry("b.py", "modified", 5, 2),
                self._make_file_entry("c.py", "deleted", 0, 30),
            ],
        )
        resp = await self._post_file_changes(payload)
        assert resp.status == 201
        data = await resp.json()
        statuses = [f["status"] for f in data["files"]]
        assert "created" in statuses
        assert "modified" in statuses
        assert "deleted" in statuses

    @unittest_run_loop
    async def test_invalid_status_normalised_to_modified(self):
        """Invalid file status is normalised to 'modified'."""
        sid = str(uuid4())
        files = [{
            "path": "x.py",
            "status": "unknown_status",
            "lines_added": 5,
            "lines_removed": 2,
        }]
        payload = self._make_payload(session_id=sid, files=files)
        resp = await self._post_file_changes(payload)
        data = await resp.json()
        assert data["files"][0]["status"] == "modified"


# ---------------------------------------------------------------------------
# 3. Line counts stored correctly
# ---------------------------------------------------------------------------

class TestLineCounts(TestFileChangesBase):
    """Line counts (added/removed) are stored accurately."""

    @unittest_run_loop
    async def test_per_file_line_counts_stored(self):
        """Per-file line counts are stored in the record."""
        sid = str(uuid4())
        payload = self._make_payload(
            session_id=sid,
            files=[self._make_file_entry(lines_added=47, lines_removed=3)],
        )
        await self._post_file_changes(payload)
        record = self._ds._file_changes[-1]
        assert record["files"][0]["lines_added"] == 47
        assert record["files"][0]["lines_removed"] == 3

    @unittest_run_loop
    async def test_explicit_totals_stored(self):
        """Explicitly provided total_added/total_removed are stored."""
        sid = str(uuid4())
        payload = self._make_payload(
            session_id=sid,
            files=[self._make_file_entry(lines_added=10, lines_removed=2)],
            total_added=10,
            total_removed=2,
        )
        resp = await self._post_file_changes(payload)
        data = await resp.json()
        assert data["total_added"] == 10
        assert data["total_removed"] == 2

    @unittest_run_loop
    async def test_totals_computed_from_files_when_absent(self):
        """total_added/total_removed are computed from files when not provided."""
        sid = str(uuid4())
        payload = self._make_payload(
            session_id=sid,
            files=[
                self._make_file_entry(lines_added=20, lines_removed=5),
                self._make_file_entry(lines_added=15, lines_removed=8),
            ],
        )
        resp = await self._post_file_changes(payload)
        data = await resp.json()
        assert data["total_added"] == 35
        assert data["total_removed"] == 13

    @unittest_run_loop
    async def test_zero_line_counts_valid(self):
        """Files with zero line counts are valid (e.g. deleted with 0 added)."""
        sid = str(uuid4())
        payload = self._make_payload(
            session_id=sid,
            files=[self._make_file_entry(status="created", lines_added=0, lines_removed=0)],
        )
        resp = await self._post_file_changes(payload)
        assert resp.status == 201


# ---------------------------------------------------------------------------
# 4. GET /api/file-changes returns list
# ---------------------------------------------------------------------------

class TestGetFileChanges(TestFileChangesBase):
    """GET /api/file-changes returns the recent summaries list."""

    @unittest_run_loop
    async def test_get_initially_empty(self):
        """GET /api/file-changes returns empty list on a fresh server."""
        resp = await self.client.request("GET", "/api/file-changes")
        assert resp.status == 200
        data = await resp.json()
        assert "summaries" in data
        assert "total" in data
        assert data["summaries"] == []
        assert data["total"] == 0

    @unittest_run_loop
    async def test_get_returns_stored_summaries(self):
        """GET /api/file-changes returns previously submitted summaries."""
        for i in range(3):
            await self._post_file_changes(
                self._make_payload(
                    session_id=str(uuid4()),
                    files=[self._make_file_entry(path=f"file{i}.py")],
                )
            )
        resp = await self.client.request("GET", "/api/file-changes")
        data = await resp.json()
        assert data["total"] == 3
        assert len(data["summaries"]) == 3

    @unittest_run_loop
    async def test_get_returns_newest_first(self):
        """GET /api/file-changes returns newest summaries first."""
        sids = [str(uuid4()) for _ in range(3)]
        for sid in sids:
            await self._post_file_changes(
                self._make_payload(session_id=sid,
                                   files=[self._make_file_entry()])
            )
        resp = await self.client.request("GET", "/api/file-changes")
        data = await resp.json()
        # Last submitted should be first in response
        assert data["summaries"][0]["session_id"] == sids[-1]

    @unittest_run_loop
    async def test_get_returns_at_most_50(self):
        """GET /api/file-changes returns at most 50 summaries."""
        for _ in range(60):
            await self._post_file_changes(
                self._make_payload(session_id=str(uuid4()),
                                   files=[self._make_file_entry()])
            )
        resp = await self.client.request("GET", "/api/file-changes")
        data = await resp.json()
        assert data["total"] <= 50
        assert len(data["summaries"]) <= 50

    @unittest_run_loop
    async def test_get_content_type_json(self):
        """GET /api/file-changes returns JSON content type."""
        resp = await self.client.request("GET", "/api/file-changes")
        assert "application/json" in resp.headers.get("Content-Type", "")


# ---------------------------------------------------------------------------
# 5. GET /api/file-changes/{session_id} returns specific summary
# ---------------------------------------------------------------------------

class TestGetFileChangesBySession(TestFileChangesBase):
    """GET /api/file-changes/{session_id} returns a specific summary."""

    @unittest_run_loop
    async def test_get_by_session_id_returns_correct_record(self):
        """GET /api/file-changes/{id} returns the summary for that session."""
        sid = str(uuid4())
        payload = self._make_payload(
            session_id=sid,
            files=[self._make_file_entry(path="target.py", status="created",
                                         lines_added=25, lines_removed=0)],
        )
        await self._post_file_changes(payload)

        resp = await self.client.request("GET", f"/api/file-changes/{sid}")
        assert resp.status == 200
        data = await resp.json()
        assert data["session_id"] == sid
        assert data["files"][0]["path"] == "target.py"

    @unittest_run_loop
    async def test_get_by_session_id_not_found_returns_404(self):
        """GET /api/file-changes/{unknown} returns 404."""
        resp = await self.client.request(
            "GET", "/api/file-changes/nonexistent-session-id-xyz"
        )
        assert resp.status == 404

    @unittest_run_loop
    async def test_get_by_session_id_includes_all_files(self):
        """GET /api/file-changes/{id} includes all files in the summary."""
        sid = str(uuid4())
        payload = self._make_payload(
            session_id=sid,
            files=[
                self._make_file_entry("a.py", "created", 10, 0),
                self._make_file_entry("b.py", "modified", 5, 2),
                self._make_file_entry("c.py", "deleted", 0, 8),
            ],
        )
        await self._post_file_changes(payload)
        resp = await self.client.request("GET", f"/api/file-changes/{sid}")
        data = await resp.json()
        assert len(data["files"]) == 3

    @unittest_run_loop
    async def test_get_by_session_id_includes_line_counts(self):
        """GET /api/file-changes/{id} includes total_added and total_removed."""
        sid = str(uuid4())
        payload = self._make_payload(
            session_id=sid,
            files=[self._make_file_entry(lines_added=42, lines_removed=7)],
            total_added=42,
            total_removed=7,
        )
        await self._post_file_changes(payload)
        resp = await self.client.request("GET", f"/api/file-changes/{sid}")
        data = await resp.json()
        assert data["total_added"] == 42
        assert data["total_removed"] == 7


# ---------------------------------------------------------------------------
# 6. WebSocket receives file_changes event
# ---------------------------------------------------------------------------

class TestFileChangesWebSocket(TestFileChangesBase):
    """POST /api/file-changes broadcasts file_changes event to WebSocket clients."""

    @unittest_run_loop
    async def test_post_broadcasts_file_changes_event(self):
        """POST /api/file-changes sends a file_changes message over WebSocket."""
        sid = str(uuid4())

        async with self.client.ws_connect('/ws') as ws:
            # Discard initial metrics_update message
            msg = await ws.receive_json(timeout=2)
            assert msg['type'] == 'metrics_update'

            payload = self._make_payload(
                session_id=sid,
                agent="coding",
                ticket="AI-164",
                files=[
                    self._make_file_entry("server.py", "modified", 47, 3),
                ],
                total_added=47,
                total_removed=3,
            )
            post_resp = await self._post_file_changes(payload)
            assert post_resp.status == 201

            ws_msg = await ws.receive_json(timeout=2)
            assert ws_msg['type'] == 'file_changes'
            assert ws_msg['agent'] == 'coding'
            assert ws_msg['ticket'] == 'AI-164'
            assert ws_msg['session_id'] == sid
            assert isinstance(ws_msg['files'], list)
            assert ws_msg['total_added'] == 47
            assert ws_msg['total_removed'] == 3
            assert 'timestamp' in ws_msg

    @unittest_run_loop
    async def test_broadcast_includes_all_statuses(self):
        """WebSocket message includes files with all 3 statuses."""
        sid = str(uuid4())

        async with self.client.ws_connect('/ws') as ws:
            await ws.receive_json(timeout=2)  # discard metrics_update

            payload = self._make_payload(
                session_id=sid,
                files=[
                    self._make_file_entry("new.py", "created", 10, 0),
                    self._make_file_entry("mod.py", "modified", 5, 2),
                    self._make_file_entry("del.py", "deleted", 0, 8),
                ],
            )
            await self._post_file_changes(payload)

            ws_msg = await ws.receive_json(timeout=2)
            assert ws_msg['type'] == 'file_changes'
            statuses = [f['status'] for f in ws_msg['files']]
            assert 'created' in statuses
            assert 'modified' in statuses
            assert 'deleted' in statuses


# ---------------------------------------------------------------------------
# 7. Circular buffer caps at 100
# ---------------------------------------------------------------------------

class TestCircularBuffer(TestFileChangesBase):
    """_file_changes circular buffer is capped at FILE_CHANGES_MAX (100)."""

    @unittest_run_loop
    async def test_buffer_caps_at_100(self):
        """Submitting more than 100 summaries keeps only the last 100."""
        for i in range(110):
            await self._post_file_changes(
                self._make_payload(
                    session_id=str(uuid4()),
                    files=[self._make_file_entry(path=f"file{i}.py")],
                )
            )
        assert len(self._ds._file_changes) <= FILE_CHANGES_MAX
        assert len(self._ds._file_changes) == FILE_CHANGES_MAX

    @unittest_run_loop
    async def test_buffer_retains_most_recent_on_overflow(self):
        """After overflow, the buffer contains the most recently added records."""
        sids = [str(uuid4()) for _ in range(110)]
        for sid in sids:
            await self._post_file_changes(
                self._make_payload(session_id=sid,
                                   files=[self._make_file_entry()])
            )
        stored_sids = [r["session_id"] for r in self._ds._file_changes]
        # The last 100 submitted should be retained
        expected_sids = sids[-FILE_CHANGES_MAX:]
        assert stored_sids == expected_sids

    @unittest_run_loop
    async def test_file_changes_max_constant_is_100(self):
        """FILE_CHANGES_MAX constant equals 100."""
        assert FILE_CHANGES_MAX == 100


# ---------------------------------------------------------------------------
# 8. POST without files returns 400
# ---------------------------------------------------------------------------

class TestPostValidation(TestFileChangesBase):
    """POST /api/file-changes with missing or invalid fields returns 400."""

    @unittest_run_loop
    async def test_post_missing_files_returns_400(self):
        """POST /api/file-changes without files field returns 400."""
        payload = {"agent": "coding", "ticket": "AI-42"}
        resp = await self._post_file_changes(payload)
        assert resp.status == 400

    @unittest_run_loop
    async def test_post_empty_files_list_returns_400(self):
        """POST /api/file-changes with empty files list returns 400."""
        payload = {"agent": "coding", "files": []}
        resp = await self._post_file_changes(payload)
        assert resp.status == 400

    @unittest_run_loop
    async def test_post_invalid_json_returns_400(self):
        """POST /api/file-changes with invalid JSON returns 400."""
        resp = await self.client.request(
            "POST",
            "/api/file-changes",
            data="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    @unittest_run_loop
    async def test_post_files_not_a_list_returns_400(self):
        """POST /api/file-changes where files is not a list returns 400."""
        payload = {"agent": "coding", "files": "not-a-list"}
        resp = await self._post_file_changes(payload)
        assert resp.status == 400


# ---------------------------------------------------------------------------
# 9. Diff content stored correctly when provided
# ---------------------------------------------------------------------------

class TestDiffStorage(TestFileChangesBase):
    """Diff content is stored correctly when provided."""

    @unittest_run_loop
    async def test_diff_stored_when_provided(self):
        """Diff string is stored verbatim in the file record."""
        sid = str(uuid4())
        diff_text = "--- a/server.py\n+++ b/server.py\n@@ -1,3 +1,4 @@\n-old\n+new\n context"
        payload = self._make_payload(
            session_id=sid,
            files=[self._make_file_entry(diff=diff_text)],
        )
        await self._post_file_changes(payload)
        record = self._ds._file_changes[-1]
        assert record["files"][0]["diff"] == diff_text

    @unittest_run_loop
    async def test_diff_accessible_via_get_by_session(self):
        """Diff is returned by GET /api/file-changes/{session_id}."""
        sid = str(uuid4())
        diff_text = "+added line\n-removed line\n context"
        payload = self._make_payload(
            session_id=sid,
            files=[self._make_file_entry(diff=diff_text)],
        )
        await self._post_file_changes(payload)
        resp = await self.client.request("GET", f"/api/file-changes/{sid}")
        data = await resp.json()
        assert data["files"][0]["diff"] == diff_text

    @unittest_run_loop
    async def test_diff_empty_string_when_not_provided(self):
        """Diff defaults to empty string when not included in file entry."""
        sid = str(uuid4())
        # Do not include 'diff' key in the file entry
        files = [{
            "path": "no_diff.py",
            "status": "modified",
            "lines_added": 5,
            "lines_removed": 2,
        }]
        payload = self._make_payload(session_id=sid, files=files)
        await self._post_file_changes(payload)
        record = self._ds._file_changes[-1]
        assert record["files"][0]["diff"] == ""

    @unittest_run_loop
    async def test_diff_preserved_for_all_three_file_statuses(self):
        """Diff content is stored for created, modified, and deleted files."""
        sid = str(uuid4())
        diff_created = "+new content"
        diff_modified = "-old\n+new"
        diff_deleted = "-all gone"
        payload = self._make_payload(
            session_id=sid,
            files=[
                self._make_file_entry("c.py", "created", 10, 0, diff=diff_created),
                self._make_file_entry("m.py", "modified", 5, 2, diff=diff_modified),
                self._make_file_entry("d.py", "deleted", 0, 8, diff=diff_deleted),
            ],
        )
        await self._post_file_changes(payload)
        record = self._ds._file_changes[-1]
        assert record["files"][0]["diff"] == diff_created
        assert record["files"][1]["diff"] == diff_modified
        assert record["files"][2]["diff"] == diff_deleted

    @unittest_run_loop
    async def test_diff_broadcast_via_websocket(self):
        """Diff content is included in the WebSocket broadcast."""
        sid = str(uuid4())
        diff_text = "+new line\n-old line"

        async with self.client.ws_connect('/ws') as ws:
            await ws.receive_json(timeout=2)  # discard metrics_update

            payload = self._make_payload(
                session_id=sid,
                files=[self._make_file_entry(diff=diff_text)],
            )
            await self._post_file_changes(payload)

            ws_msg = await ws.receive_json(timeout=2)
            assert ws_msg['type'] == 'file_changes'
            assert ws_msg['files'][0]['diff'] == diff_text
