"""Tests for AI-163: REQ-CODE-001: Implement Live Code Streaming Display.

Tests cover:
- POST /api/code-stream creates stream and returns stream_id
- POST /api/code-stream broadcasts code_stream via WebSocket
- Language auto-detection works for .py, .js, .ts, .html
- POST with is_final=true marks stream complete
- GET /api/code-streams returns active/recent streams
- GET /api/code-streams/{stream_id} returns full stream content
- Multiple chunks accumulate correctly
- chunk_type (addition/deletion/context) stored correctly
- Missing file_path returns 400
- Invalid JSON returns 400
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

from dashboard.server import DashboardServer, LANGUAGE_MAP, detect_language


# ---------------------------------------------------------------------------
# Test helpers / base class
# ---------------------------------------------------------------------------

class TestCodeStreamBase(AioHTTPTestCase):
    """Base class: creates a fresh DashboardServer for each test method."""

    async def get_application(self):
        self._temp_dir = tempfile.mkdtemp()
        self._ds = DashboardServer(
            project_name="test-code-streaming",
            metrics_dir=Path(self._temp_dir),
        )
        return self._ds.app

    async def _post_chunk(self, payload):
        """Helper: POST a code-stream chunk and return the response."""
        return await self.client.request(
            "POST",
            "/api/code-stream",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )


# ---------------------------------------------------------------------------
# 1. Language auto-detection unit tests
# ---------------------------------------------------------------------------

class TestLanguageDetection(AioHTTPTestCase):
    """Unit tests for detect_language() helper."""

    async def get_application(self):
        ds = DashboardServer(project_name="test-lang", metrics_dir=Path(tempfile.mkdtemp()))
        return ds.app

    @unittest_run_loop
    async def test_detect_python(self):
        """.py files detect as 'python'."""
        assert detect_language("src/app.py") == "python"

    @unittest_run_loop
    async def test_detect_javascript(self):
        """.js files detect as 'javascript'."""
        assert detect_language("src/index.js") == "javascript"

    @unittest_run_loop
    async def test_detect_typescript(self):
        """.ts files detect as 'typescript'."""
        assert detect_language("src/types.ts") == "typescript"

    @unittest_run_loop
    async def test_detect_tsx(self):
        """.tsx files detect as 'typescript'."""
        assert detect_language("components/App.tsx") == "typescript"

    @unittest_run_loop
    async def test_detect_html(self):
        """.html files detect as 'html'."""
        assert detect_language("templates/index.html") == "html"

    @unittest_run_loop
    async def test_detect_json(self):
        """.json files detect as 'json'."""
        assert detect_language("config/settings.json") == "json"

    @unittest_run_loop
    async def test_detect_css(self):
        """.css files detect as 'css'."""
        assert detect_language("styles/main.css") == "css"

    @unittest_run_loop
    async def test_detect_yaml(self):
        """.yaml files detect as 'yaml'."""
        assert detect_language(".github/workflows/ci.yaml") == "yaml"

    @unittest_run_loop
    async def test_detect_yml(self):
        """.yml files detect as 'yaml'."""
        assert detect_language("docker-compose.yml") == "yaml"

    @unittest_run_loop
    async def test_detect_markdown(self):
        """.md files detect as 'markdown'."""
        assert detect_language("README.md") == "markdown"

    @unittest_run_loop
    async def test_detect_bash(self):
        """.sh files detect as 'bash'."""
        assert detect_language("scripts/deploy.sh") == "bash"

    @unittest_run_loop
    async def test_detect_unknown_defaults_to_text(self):
        """Unknown extensions default to 'text'."""
        assert detect_language("binary.xyz") == "text"
        assert detect_language("noextension") == "text"

    @unittest_run_loop
    async def test_detect_case_insensitive(self):
        """Extension detection is case-insensitive."""
        assert detect_language("Module.PY") == "python"
        assert detect_language("Component.TSX") == "typescript"

    @unittest_run_loop
    async def test_language_map_has_required_entries(self):
        """LANGUAGE_MAP contains all required extensions from spec."""
        required = {'.py', '.js', '.ts', '.html', '.css', '.json', '.md',
                    '.sh', '.yaml', '.yml', '.go', '.rs', '.java', '.tsx'}
        for ext in required:
            assert ext in LANGUAGE_MAP, f"Missing extension {ext} in LANGUAGE_MAP"


# ---------------------------------------------------------------------------
# 2. POST /api/code-stream — creates stream and returns stream_id
# ---------------------------------------------------------------------------

class TestPostCodeStream(TestCodeStreamBase):
    """POST /api/code-stream creates a stream and returns stream_id."""

    @unittest_run_loop
    async def test_post_returns_200(self):
        """POST /api/code-stream returns HTTP 200."""
        payload = {
            "agent": "coding",
            "file_path": "src/app.py",
            "chunk": "def foo():\n",
            "chunk_type": "addition",
            "stream_id": str(uuid4()),
        }
        resp = await self._post_chunk(payload)
        assert resp.status == 200

    @unittest_run_loop
    async def test_post_returns_success_and_stream_id(self):
        """POST /api/code-stream returns {success: true, stream_id: ...}."""
        sid = str(uuid4())
        payload = {
            "agent": "coding",
            "file_path": "src/app.py",
            "chunk": "    pass\n",
            "chunk_type": "context",
            "stream_id": sid,
        }
        resp = await self._post_chunk(payload)
        data = await resp.json()
        assert data["success"] is True
        assert data["stream_id"] == sid

    @unittest_run_loop
    async def test_post_generates_stream_id_if_not_provided(self):
        """POST /api/code-stream generates a stream_id when none is provided."""
        payload = {
            "agent": "coding",
            "file_path": "src/utils.py",
            "chunk": "import os\n",
        }
        resp = await self._post_chunk(payload)
        data = await resp.json()
        assert data["success"] is True
        assert "stream_id" in data
        assert len(data["stream_id"]) > 0

    @unittest_run_loop
    async def test_post_missing_file_path_returns_400(self):
        """POST /api/code-stream without file_path returns 400."""
        payload = {
            "agent": "coding",
            "chunk": "def bar():\n",
        }
        resp = await self._post_chunk(payload)
        assert resp.status == 400

    @unittest_run_loop
    async def test_post_invalid_json_returns_400(self):
        """POST /api/code-stream with invalid JSON returns 400."""
        resp = await self.client.request(
            "POST",
            "/api/code-stream",
            data="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    @unittest_run_loop
    async def test_post_auto_detects_language_from_extension(self):
        """POST /api/code-stream auto-detects language from file extension."""
        sid = str(uuid4())
        payload = {
            "agent": "coding",
            "file_path": "src/component.tsx",
            "chunk": "export default function App() {}\n",
            "stream_id": sid,
        }
        resp = await self._post_chunk(payload)
        assert resp.status == 200
        # Verify stream was created with correct language
        stream = self._ds._code_streams.get(sid)
        assert stream is not None
        assert stream["language"] == "typescript"

    @unittest_run_loop
    async def test_post_uses_provided_language_over_auto_detect(self):
        """POST /api/code-stream uses explicitly provided language."""
        sid = str(uuid4())
        payload = {
            "agent": "coding",
            "file_path": "src/app.py",
            "language": "python3",
            "chunk": "print('hello')\n",
            "stream_id": sid,
        }
        resp = await self._post_chunk(payload)
        assert resp.status == 200
        stream = self._ds._code_streams.get(sid)
        assert stream is not None
        assert stream["language"] == "python3"


# ---------------------------------------------------------------------------
# 3. chunk_type stored correctly
# ---------------------------------------------------------------------------

class TestChunkTypeStorage(TestCodeStreamBase):
    """chunk_type (addition/deletion/context) is stored correctly."""

    @unittest_run_loop
    async def test_addition_chunk_type_stored(self):
        """chunk_type='addition' is stored in the stream chunks."""
        sid = str(uuid4())
        await self._post_chunk({
            "agent": "coding",
            "file_path": "src/app.py",
            "chunk": "+ def new_func():\n",
            "chunk_type": "addition",
            "stream_id": sid,
        })
        stream = self._ds._code_streams[sid]
        assert stream["chunks"][0]["chunk_type"] == "addition"

    @unittest_run_loop
    async def test_deletion_chunk_type_stored(self):
        """chunk_type='deletion' is stored in the stream chunks."""
        sid = str(uuid4())
        await self._post_chunk({
            "agent": "coding",
            "file_path": "src/app.py",
            "chunk": "- def old_func():\n",
            "chunk_type": "deletion",
            "stream_id": sid,
        })
        stream = self._ds._code_streams[sid]
        assert stream["chunks"][0]["chunk_type"] == "deletion"

    @unittest_run_loop
    async def test_context_chunk_type_stored(self):
        """chunk_type='context' is stored in the stream chunks."""
        sid = str(uuid4())
        await self._post_chunk({
            "agent": "coding",
            "file_path": "src/app.py",
            "chunk": "  unchanged line\n",
            "chunk_type": "context",
            "stream_id": sid,
        })
        stream = self._ds._code_streams[sid]
        assert stream["chunks"][0]["chunk_type"] == "context"

    @unittest_run_loop
    async def test_invalid_chunk_type_defaults_to_context(self):
        """Invalid chunk_type defaults to 'context'."""
        sid = str(uuid4())
        await self._post_chunk({
            "agent": "coding",
            "file_path": "src/app.py",
            "chunk": "some code\n",
            "chunk_type": "unknown_type",
            "stream_id": sid,
        })
        stream = self._ds._code_streams[sid]
        assert stream["chunks"][0]["chunk_type"] == "context"


# ---------------------------------------------------------------------------
# 4. Multiple chunks accumulate correctly
# ---------------------------------------------------------------------------

class TestChunkAccumulation(TestCodeStreamBase):
    """Multiple chunks accumulate in the correct order."""

    @unittest_run_loop
    async def test_multiple_chunks_accumulate(self):
        """Multiple POST calls for the same stream_id accumulate all chunks."""
        sid = str(uuid4())
        chunks = [
            ("def foo():\n", "addition"),
            ("    return 42\n", "addition"),
            ("# comment\n", "context"),
        ]
        for chunk_text, chunk_type in chunks:
            await self._post_chunk({
                "agent": "coding",
                "file_path": "src/app.py",
                "chunk": chunk_text,
                "chunk_type": chunk_type,
                "stream_id": sid,
            })

        stream = self._ds._code_streams[sid]
        assert len(stream["chunks"]) == 3
        for i, (text, ctype) in enumerate(chunks):
            assert stream["chunks"][i]["chunk"] == text
            assert stream["chunks"][i]["chunk_type"] == ctype

    @unittest_run_loop
    async def test_different_stream_ids_create_separate_streams(self):
        """Different stream_ids create independent stream entries."""
        sid1 = str(uuid4())
        sid2 = str(uuid4())
        await self._post_chunk({
            "agent": "coding", "file_path": "a.py", "chunk": "a\n", "stream_id": sid1,
        })
        await self._post_chunk({
            "agent": "coding", "file_path": "b.py", "chunk": "b\n", "stream_id": sid2,
        })
        assert sid1 in self._ds._code_streams
        assert sid2 in self._ds._code_streams
        assert self._ds._code_streams[sid1]["file_path"] == "a.py"
        assert self._ds._code_streams[sid2]["file_path"] == "b.py"


# ---------------------------------------------------------------------------
# 5. POST with is_final=true marks stream complete
# ---------------------------------------------------------------------------

class TestStreamCompletion(TestCodeStreamBase):
    """POST with is_final=true marks stream as completed."""

    @unittest_run_loop
    async def test_is_final_marks_stream_complete(self):
        """POST with is_final=true sets stream.completed=True."""
        sid = str(uuid4())
        await self._post_chunk({
            "agent": "coding",
            "file_path": "src/app.py",
            "chunk": "def foo(): pass\n",
            "chunk_type": "addition",
            "stream_id": sid,
            "is_final": True,
        })
        stream = self._ds._code_streams[sid]
        assert stream["completed"] is True

    @unittest_run_loop
    async def test_is_final_false_leaves_stream_active(self):
        """POST with is_final=false leaves stream.completed=False."""
        sid = str(uuid4())
        await self._post_chunk({
            "agent": "coding",
            "file_path": "src/app.py",
            "chunk": "import os\n",
            "stream_id": sid,
            "is_final": False,
        })
        stream = self._ds._code_streams[sid]
        assert stream["completed"] is False

    @unittest_run_loop
    async def test_chunks_before_final_plus_final_all_stored(self):
        """Chunks sent before is_final=True all appear in the stream."""
        sid = str(uuid4())
        # Send two chunks then finalise
        for text in ("line1\n", "line2\n"):
            await self._post_chunk({
                "agent": "coding", "file_path": "f.py",
                "chunk": text, "stream_id": sid,
            })
        await self._post_chunk({
            "agent": "coding", "file_path": "f.py",
            "chunk": "line3\n", "stream_id": sid, "is_final": True,
        })
        stream = self._ds._code_streams[sid]
        assert len(stream["chunks"]) == 3
        assert stream["completed"] is True

    @unittest_run_loop
    async def test_completed_stream_has_completed_at_timestamp(self):
        """Stream finalised with is_final=True includes completed_at timestamp."""
        sid = str(uuid4())
        await self._post_chunk({
            "agent": "coding",
            "file_path": "src/app.py",
            "chunk": "",
            "stream_id": sid,
            "is_final": True,
        })
        stream = self._ds._code_streams[sid]
        assert "completed_at" in stream
        assert stream["completed_at"] is not None


# ---------------------------------------------------------------------------
# 6. GET /api/code-streams returns active/recent streams
# ---------------------------------------------------------------------------

class TestGetCodeStreams(TestCodeStreamBase):
    """GET /api/code-streams returns summary list of streams."""

    @unittest_run_loop
    async def test_get_streams_initially_empty(self):
        """GET /api/code-streams returns empty list on a fresh server."""
        resp = await self.client.request("GET", "/api/code-streams")
        assert resp.status == 200
        data = await resp.json()
        assert "streams" in data
        assert "total" in data
        assert data["streams"] == []
        assert data["total"] == 0

    @unittest_run_loop
    async def test_get_streams_returns_all_active(self):
        """GET /api/code-streams returns all created streams."""
        for i in range(3):
            sid = str(uuid4())
            await self._post_chunk({
                "agent": "coding",
                "file_path": f"src/file{i}.py",
                "chunk": f"chunk {i}\n",
                "stream_id": sid,
            })

        resp = await self.client.request("GET", "/api/code-streams")
        data = await resp.json()
        assert data["total"] == 3
        assert len(data["streams"]) == 3

    @unittest_run_loop
    async def test_get_streams_does_not_include_chunks(self):
        """GET /api/code-streams summary does not include full chunks list."""
        sid = str(uuid4())
        await self._post_chunk({
            "agent": "coding", "file_path": "a.py",
            "chunk": "big code here\n", "stream_id": sid,
        })
        resp = await self.client.request("GET", "/api/code-streams")
        data = await resp.json()
        stream_summary = data["streams"][0]
        # Should have chunk_count, not the raw chunks list
        assert "chunk_count" in stream_summary
        assert "chunks" not in stream_summary

    @unittest_run_loop
    async def test_get_streams_includes_correct_fields(self):
        """GET /api/code-streams includes required summary fields."""
        sid = str(uuid4())
        await self._post_chunk({
            "agent": "coding",
            "file_path": "src/main.py",
            "language": "python",
            "chunk": "pass\n",
            "stream_id": sid,
        })
        resp = await self.client.request("GET", "/api/code-streams")
        data = await resp.json()
        s = data["streams"][0]
        required_fields = {"stream_id", "agent", "file_path", "language",
                           "chunk_count", "started_at", "completed"}
        assert required_fields.issubset(set(s.keys()))

    @unittest_run_loop
    async def test_get_streams_content_type_json(self):
        """GET /api/code-streams returns JSON content type."""
        resp = await self.client.request("GET", "/api/code-streams")
        assert "application/json" in resp.headers.get("Content-Type", "")


# ---------------------------------------------------------------------------
# 7. GET /api/code-streams/{stream_id} returns full content
# ---------------------------------------------------------------------------

class TestGetCodeStreamById(TestCodeStreamBase):
    """GET /api/code-streams/{stream_id} returns full stream with chunks."""

    @unittest_run_loop
    async def test_get_by_id_returns_stream(self):
        """GET /api/code-streams/{id} returns the full stream record."""
        sid = str(uuid4())
        await self._post_chunk({
            "agent": "coding",
            "file_path": "src/app.py",
            "chunk": "def greet(): pass\n",
            "chunk_type": "addition",
            "stream_id": sid,
        })
        resp = await self.client.request("GET", f"/api/code-streams/{sid}")
        assert resp.status == 200
        data = await resp.json()
        assert data["stream_id"] == sid
        assert data["file_path"] == "src/app.py"
        assert len(data["chunks"]) == 1
        assert data["chunks"][0]["chunk"] == "def greet(): pass\n"
        assert data["chunks"][0]["chunk_type"] == "addition"

    @unittest_run_loop
    async def test_get_by_id_returns_all_chunks(self):
        """GET /api/code-streams/{id} includes all accumulated chunks."""
        sid = str(uuid4())
        for i in range(5):
            await self._post_chunk({
                "agent": "coding",
                "file_path": "src/app.py",
                "chunk": f"line {i}\n",
                "stream_id": sid,
            })
        resp = await self.client.request("GET", f"/api/code-streams/{sid}")
        data = await resp.json()
        assert len(data["chunks"]) == 5

    @unittest_run_loop
    async def test_get_by_id_not_found_returns_404(self):
        """GET /api/code-streams/{unknown_id} returns 404."""
        resp = await self.client.request(
            "GET", f"/api/code-streams/nonexistent-stream-id-xyz"
        )
        assert resp.status == 404

    @unittest_run_loop
    async def test_get_by_id_includes_completed_flag(self):
        """GET /api/code-streams/{id} includes the completed flag."""
        sid = str(uuid4())
        await self._post_chunk({
            "agent": "coding", "file_path": "f.py",
            "chunk": "x\n", "stream_id": sid, "is_final": True,
        })
        resp = await self.client.request("GET", f"/api/code-streams/{sid}")
        data = await resp.json()
        assert data["completed"] is True


# ---------------------------------------------------------------------------
# 8. WebSocket broadcast on POST
# ---------------------------------------------------------------------------

class TestCodeStreamWebSocketBroadcast(TestCodeStreamBase):
    """POST /api/code-stream broadcasts code_stream event to WebSocket clients."""

    @unittest_run_loop
    async def test_post_broadcasts_code_stream_event(self):
        """POST /api/code-stream sends a code_stream message over WebSocket."""
        sid = str(uuid4())

        async with self.client.ws_connect('/ws') as ws:
            # Discard initial metrics_update message
            msg = await ws.receive_json(timeout=2)
            assert msg['type'] == 'metrics_update'

            payload = {
                "agent": "coding",
                "file_path": "src/server.py",
                "language": "python",
                "chunk": "def handle_request():\n",
                "chunk_type": "addition",
                "stream_id": sid,
                "is_final": False,
            }
            post_resp = await self._post_chunk(payload)
            assert post_resp.status == 200

            ws_msg = await ws.receive_json(timeout=2)
            assert ws_msg['type'] == 'code_stream'
            assert ws_msg['agent'] == 'coding'
            assert ws_msg['file_path'] == 'src/server.py'
            assert ws_msg['language'] == 'python'
            assert ws_msg['chunk'] == 'def handle_request():\n'
            assert ws_msg['chunk_type'] == 'addition'
            assert ws_msg['stream_id'] == sid
            assert ws_msg['is_final'] is False
            assert 'timestamp' in ws_msg

    @unittest_run_loop
    async def test_broadcast_includes_is_final_true(self):
        """WebSocket message for final chunk has is_final=True."""
        sid = str(uuid4())

        async with self.client.ws_connect('/ws') as ws:
            await ws.receive_json(timeout=2)  # discard metrics_update

            await self._post_chunk({
                "agent": "coding_fast",
                "file_path": "main.go",
                "chunk": "}\n",
                "chunk_type": "context",
                "stream_id": sid,
                "is_final": True,
            })

            ws_msg = await ws.receive_json(timeout=2)
            assert ws_msg['type'] == 'code_stream'
            assert ws_msg['is_final'] is True
            assert ws_msg['agent'] == 'coding_fast'
