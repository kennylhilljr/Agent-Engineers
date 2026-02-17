"""
Comprehensive authentication tests for AI-112: Bearer Token Validation

Tests all 8 required test steps:
1. Run without DASHBOARD_AUTH_TOKEN - API endpoints accessible without token
2. Verify API endpoints are accessible without token
3. Set DASHBOARD_AUTH_TOKEN=secret123 - API endpoints reject requests without token
4. Verify API endpoints reject requests without token
5. Verify API endpoints reject requests with wrong token
6. Verify WebSocket rejects connection without token
7. Verify WebSocket accepts connection with valid token
8. Test with Authorization: Bearer header format

Test Coverage:
- REST API authentication (with and without token)
- WebSocket authentication (with and without token)
- Constant-time comparison (security requirement)
- Error messages and HTTP 401 responses
- Health endpoint bypass
- Multiple authentication methods for WebSocket
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from aiohttp import WSMsgType
from aiohttp.test_utils import AioHTTPTestCase

from dashboard.rest_api_server import RESTAPIServer, constant_time_compare
from dashboard.websocket_server import WebSocketServer, validate_websocket_auth
from aiohttp import web


# ============================================================================
# Test 1-2: Open Mode (No Authentication Token)
# ============================================================================

class TestOpenMode(AioHTTPTestCase):
    """Test Step 1-2: Verify API endpoints are accessible without token when DASHBOARD_AUTH_TOKEN is not set."""

    async def get_application(self):
        """Create test application without authentication."""
        self.temp_dir = tempfile.mkdtemp()
        self.metrics_file = Path(self.temp_dir) / ".agent_metrics.json"

        # Create minimal metrics
        minimal_metrics = {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": []
        }
        self.metrics_file.write_text(json.dumps(minimal_metrics))

        # Ensure DASHBOARD_AUTH_TOKEN is NOT set (open mode)
        with patch.dict(os.environ, {}, clear=False):
            if 'DASHBOARD_AUTH_TOKEN' in os.environ:
                del os.environ['DASHBOARD_AUTH_TOKEN']

            self.server = RESTAPIServer(
                project_name="test-project",
                metrics_dir=Path(self.temp_dir),
                port=8420,
                host="127.0.0.1"
            )

        return self.server.app

    async def tearDown(self):
        """Cleanup after tests."""
        await super().tearDown()
        import shutil
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_open_mode_health_endpoint(self):
        """Test Step 1: Health endpoint is accessible without token."""
        resp = await self.client.request("GET", "/api/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"

    async def test_open_mode_metrics_endpoint(self):
        """Test Step 2: Metrics endpoint is accessible without token."""
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200
        data = await resp.json()
        assert "project_name" in data

    async def test_open_mode_agents_endpoint(self):
        """Test Step 2: Agents endpoint is accessible without token."""
        resp = await self.client.request("GET", "/api/agents")
        assert resp.status == 200
        data = await resp.json()
        assert "agents" in data

    async def test_open_mode_sessions_endpoint(self):
        """Test Step 2: Sessions endpoint is accessible without token."""
        resp = await self.client.request("GET", "/api/sessions")
        assert resp.status == 200
        data = await resp.json()
        assert "sessions" in data

    async def test_open_mode_post_chat(self):
        """Test Step 2: POST /api/chat is accessible without token."""
        payload = {"message": "Hello"}
        resp = await self.client.request("POST", "/api/chat", json=payload)
        # Should get 200 (streaming) or 200 (fallback), not 401
        assert resp.status == 200


# ============================================================================
# Test 3-5: Authenticated Mode (Token Required)
# ============================================================================

class TestAuthenticatedMode(AioHTTPTestCase):
    """Test Step 3-5: Verify API endpoints reject requests without token or with wrong token."""

    async def get_application(self):
        """Create test application with authentication enabled."""
        self.temp_dir = tempfile.mkdtemp()
        self.metrics_file = Path(self.temp_dir) / ".agent_metrics.json"

        # Create minimal metrics
        minimal_metrics = {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": []
        }
        self.metrics_file.write_text(json.dumps(minimal_metrics))

        # Set DASHBOARD_AUTH_TOKEN to enable authentication
        self.auth_token = "secret123"
        os.environ['DASHBOARD_AUTH_TOKEN'] = self.auth_token

        self.server = RESTAPIServer(
            project_name="test-project",
            metrics_dir=Path(self.temp_dir),
            port=8420,
            host="127.0.0.1"
        )

        return self.server.app

    async def tearDown(self):
        """Cleanup after tests."""
        await super().tearDown()
        import shutil
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        if 'DASHBOARD_AUTH_TOKEN' in os.environ:
            del os.environ['DASHBOARD_AUTH_TOKEN']

    # Test Step 3-4: Reject requests without token
    async def test_reject_without_token_metrics(self):
        """Test Step 4: GET /api/metrics rejects request without token (401)."""
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 401
        data = await resp.json()
        assert "error" in data
        assert data["error"] == "Unauthorized"

    async def test_reject_without_token_agents(self):
        """Test Step 4: GET /api/agents rejects request without token (401)."""
        resp = await self.client.request("GET", "/api/agents")
        assert resp.status == 401
        data = await resp.json()
        assert "error" in data

    async def test_reject_without_token_sessions(self):
        """Test Step 4: GET /api/sessions rejects request without token (401)."""
        resp = await self.client.request("GET", "/api/sessions")
        assert resp.status == 401
        data = await resp.json()
        assert "error" in data

    async def test_reject_without_token_post_chat(self):
        """Test Step 4: POST /api/chat rejects request without token (401)."""
        payload = {"message": "Hello"}
        resp = await self.client.request("POST", "/api/chat", json=payload)
        assert resp.status == 401
        data = await resp.json()
        assert "error" in data

    # Test Step 5: Reject requests with wrong token
    async def test_reject_wrong_token_metrics(self):
        """Test Step 5: GET /api/metrics rejects request with wrong token (401)."""
        headers = {"Authorization": "Bearer wrong-token-12345"}
        resp = await self.client.request("GET", "/api/metrics", headers=headers)
        assert resp.status == 401
        data = await resp.json()
        assert "error" in data
        assert data["error"] == "Unauthorized"

    async def test_reject_wrong_token_agents(self):
        """Test Step 5: GET /api/agents rejects request with wrong token (401)."""
        headers = {"Authorization": "Bearer invalid"}
        resp = await self.client.request("GET", "/api/agents", headers=headers)
        assert resp.status == 401
        data = await resp.json()
        assert "error" in data

    async def test_reject_malformed_header(self):
        """Test Step 5: Reject malformed Authorization header (no Bearer prefix)."""
        headers = {"Authorization": "secret123"}  # Missing "Bearer " prefix
        resp = await self.client.request("GET", "/api/metrics", headers=headers)
        assert resp.status == 401
        data = await resp.json()
        assert "error" in data
        assert "Bearer" in data["message"]

    # Test Step 8: Accept requests with valid Bearer token
    async def test_accept_valid_token_metrics(self):
        """Test Step 8: GET /api/metrics accepts request with valid Bearer token."""
        headers = {"Authorization": "Bearer secret123"}
        resp = await self.client.request("GET", "/api/metrics", headers=headers)
        assert resp.status == 200
        data = await resp.json()
        assert "project_name" in data

    async def test_accept_valid_token_agents(self):
        """Test Step 8: GET /api/agents accepts request with valid Bearer token."""
        headers = {"Authorization": "Bearer secret123"}
        resp = await self.client.request("GET", "/api/agents", headers=headers)
        assert resp.status == 200
        data = await resp.json()
        assert "agents" in data

    async def test_accept_valid_token_sessions(self):
        """Test Step 8: GET /api/sessions accepts request with valid Bearer token."""
        headers = {"Authorization": "Bearer secret123"}
        resp = await self.client.request("GET", "/api/sessions", headers=headers)
        assert resp.status == 200
        data = await resp.json()
        assert "sessions" in data

    async def test_accept_valid_token_post_chat(self):
        """Test Step 8: POST /api/chat accepts request with valid Bearer token."""
        headers = {"Authorization": "Bearer secret123"}
        payload = {"message": "Hello"}
        resp = await self.client.request("POST", "/api/chat", json=payload, headers=headers)
        assert resp.status == 200

    # Health endpoint should always bypass auth
    async def test_health_bypasses_auth(self):
        """Test: Health endpoint always accessible (no auth required)."""
        resp = await self.client.request("GET", "/api/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"


# ============================================================================
# Test 6-7: WebSocket Authentication
# ============================================================================

class TestWebSocketAuthentication(AioHTTPTestCase):
    """Test Step 6-7: WebSocket authentication with and without token."""

    async def get_application(self):
        """Create test application with WebSocket server and authentication."""
        self.auth_token = "secret123"
        os.environ['DASHBOARD_AUTH_TOKEN'] = self.auth_token

        self.ws_server = WebSocketServer(host='127.0.0.1', port=0)
        self.ws_server.app = web.Application()
        self.ws_server.app.router.add_get('/ws', self.ws_server.websocket_handler)
        self.ws_server.app.router.add_get('/health', self.ws_server.health_handler)
        return self.ws_server.app

    async def tearDown(self):
        """Cleanup after tests."""
        await self.ws_server._close_all_connections()
        if 'DASHBOARD_AUTH_TOKEN' in os.environ:
            del os.environ['DASHBOARD_AUTH_TOKEN']
        await super().tearDown()

    # Test Step 6: Reject WebSocket connection without token
    async def test_websocket_reject_without_token(self):
        """Test Step 6: WebSocket rejects connection without token."""
        async with self.client.ws_connect('/ws') as ws:
            # Should receive error message
            msg = await ws.receive()
            assert msg.type == WSMsgType.TEXT

            data = json.loads(msg.data)
            assert data['type'] == 'error'
            assert data['error'] == 'Unauthorized'

            # Connection should be closed
            msg = await ws.receive()
            assert msg.type == WSMsgType.CLOSE

    async def test_websocket_reject_wrong_token_header(self):
        """Test Step 6: WebSocket rejects connection with wrong token in header."""
        headers = {"Authorization": "Bearer wrong-token"}
        async with self.client.ws_connect('/ws', headers=headers) as ws:
            # Should receive error message
            msg = await ws.receive()
            assert msg.type == WSMsgType.TEXT

            data = json.loads(msg.data)
            assert data['type'] == 'error'
            assert data['error'] == 'Unauthorized'

    async def test_websocket_reject_wrong_token_query(self):
        """Test Step 6: WebSocket rejects connection with wrong token in query param."""
        async with self.client.ws_connect('/ws?token=wrong-token') as ws:
            # Should receive error message
            msg = await ws.receive()
            data = json.loads(msg.data)
            assert data['type'] == 'error'

    # Test Step 7: Accept WebSocket connection with valid token
    async def test_websocket_accept_valid_token_header(self):
        """Test Step 7: WebSocket accepts connection with valid token in Authorization header."""
        headers = {"Authorization": "Bearer secret123"}
        async with self.client.ws_connect('/ws', headers=headers) as ws:
            # Should receive welcome message (not error)
            msg = await ws.receive()
            assert msg.type == WSMsgType.TEXT

            data = json.loads(msg.data)
            assert data['type'] == 'connection'
            assert data['status'] == 'connected'

            # Connection should remain open
            await ws.send_str('ping')
            msg = await ws.receive()
            assert msg.data == 'pong'

    async def test_websocket_accept_valid_token_query(self):
        """Test Step 7: WebSocket accepts connection with valid token in query parameter."""
        async with self.client.ws_connect('/ws?token=secret123') as ws:
            # Should receive welcome message
            msg = await ws.receive()
            data = json.loads(msg.data)
            assert data['type'] == 'connection'
            assert data['status'] == 'connected'

    async def test_websocket_accept_valid_token_protocol(self):
        """Test Step 7: WebSocket accepts connection with valid token in Sec-WebSocket-Protocol."""
        headers = {"Sec-WebSocket-Protocol": "bearer-secret123"}
        async with self.client.ws_connect('/ws', headers=headers) as ws:
            # Should receive welcome message
            msg = await ws.receive()
            data = json.loads(msg.data)
            assert data['type'] == 'connection'
            assert data['status'] == 'connected'


# ============================================================================
# Test: WebSocket Open Mode (No Authentication)
# ============================================================================

class TestWebSocketOpenMode(AioHTTPTestCase):
    """Test: WebSocket accepts connections without token when DASHBOARD_AUTH_TOKEN is not set."""

    async def get_application(self):
        """Create test application without authentication."""
        # Ensure DASHBOARD_AUTH_TOKEN is NOT set
        if 'DASHBOARD_AUTH_TOKEN' in os.environ:
            del os.environ['DASHBOARD_AUTH_TOKEN']

        self.ws_server = WebSocketServer(host='127.0.0.1', port=0)
        self.ws_server.app = web.Application()
        self.ws_server.app.router.add_get('/ws', self.ws_server.websocket_handler)
        return self.ws_server.app

    async def tearDown(self):
        """Cleanup after tests."""
        await self.ws_server._close_all_connections()
        await super().tearDown()

    async def test_websocket_open_mode_no_token(self):
        """Test: WebSocket accepts connection without token in open mode."""
        async with self.client.ws_connect('/ws') as ws:
            # Should receive welcome message (not error)
            msg = await ws.receive()
            assert msg.type == WSMsgType.TEXT

            data = json.loads(msg.data)
            assert data['type'] == 'connection'
            assert data['status'] == 'connected'


# ============================================================================
# Security Tests: Constant-Time Comparison
# ============================================================================

class TestConstantTimeComparison:
    """Test constant-time comparison function for security."""

    def test_equal_strings(self):
        """Test constant-time comparison returns True for equal strings."""
        assert constant_time_compare("secret123", "secret123") is True

    def test_unequal_strings_same_length(self):
        """Test constant-time comparison returns False for different strings of same length."""
        assert constant_time_compare("secret123", "secret124") is False

    def test_unequal_strings_different_length(self):
        """Test constant-time comparison returns False for strings of different length."""
        assert constant_time_compare("secret", "secret123") is False
        assert constant_time_compare("secret123", "secret") is False

    def test_empty_strings(self):
        """Test constant-time comparison with empty strings."""
        assert constant_time_compare("", "") is True
        assert constant_time_compare("secret", "") is False

    def test_unicode_strings(self):
        """Test constant-time comparison with unicode strings."""
        assert constant_time_compare("pässwörd", "pässwörd") is True
        assert constant_time_compare("pässwörd", "password") is False

    def test_special_characters(self):
        """Test constant-time comparison with special characters."""
        token = "sec!@#$%^&*()_+-=[]{}|;:',.<>?/~`ret123"
        assert constant_time_compare(token, token) is True
        assert constant_time_compare(token, "different") is False


# ============================================================================
# Integration Tests: End-to-End Authentication
# ============================================================================

class TestAuthenticationIntegration(AioHTTPTestCase):
    """Integration tests for complete authentication flow."""

    async def get_application(self):
        """Create test application with authentication."""
        self.temp_dir = tempfile.mkdtemp()
        self.metrics_file = Path(self.temp_dir) / ".agent_metrics.json"

        minimal_metrics = {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": []
        }
        self.metrics_file.write_text(json.dumps(minimal_metrics))

        self.auth_token = "integration-test-token-12345"
        os.environ['DASHBOARD_AUTH_TOKEN'] = self.auth_token

        self.server = RESTAPIServer(
            project_name="test-project",
            metrics_dir=Path(self.temp_dir),
            port=8420,
            host="127.0.0.1"
        )

        return self.server.app

    async def tearDown(self):
        """Cleanup after tests."""
        await super().tearDown()
        import shutil
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        if 'DASHBOARD_AUTH_TOKEN' in os.environ:
            del os.environ['DASHBOARD_AUTH_TOKEN']

    async def test_multiple_endpoints_with_valid_token(self):
        """Test multiple endpoints work with valid token."""
        headers = {"Authorization": "Bearer integration-test-token-12345"}

        # Test multiple endpoints
        endpoints = [
            "/api/metrics",
            "/api/agents",
            "/api/sessions",
            "/api/providers"
        ]

        for endpoint in endpoints:
            resp = await self.client.request("GET", endpoint, headers=headers)
            assert resp.status == 200, f"Endpoint {endpoint} failed with valid token"

    async def test_multiple_endpoints_without_token(self):
        """Test multiple endpoints fail without token."""
        endpoints = [
            "/api/metrics",
            "/api/agents",
            "/api/sessions",
            "/api/providers"
        ]

        for endpoint in endpoints:
            resp = await self.client.request("GET", endpoint)
            assert resp.status == 401, f"Endpoint {endpoint} should reject without token"

    async def test_error_message_format(self):
        """Test error messages have proper format."""
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 401

        data = await resp.json()
        assert "error" in data
        assert "message" in data
        assert data["error"] == "Unauthorized"
        assert "Bearer" in data["message"]


# Run with: python -m pytest tests/dashboard/test_authentication.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
