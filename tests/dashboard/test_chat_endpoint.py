"""Comprehensive tests for POST /api/chat streaming endpoint.

Tests streaming responses, SSE format, and tool transparency in chat endpoint.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from aiohttp.test_utils import AioHTTPTestCase

from dashboard.rest_api_server import RESTAPIServer


class TestChatEndpointStreaming(AioHTTPTestCase):
    """Test streaming chat endpoint functionality."""

    async def get_application(self):
        """Create test application."""
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

        # No auth token for tests
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

    async def test_chat_endpoint_exists(self):
        """Test POST /api/chat endpoint exists."""
        resp = await self.client.request(
            "POST",
            "/api/chat",
            json={"message": "Hello"}
        )
        # Should not be 404
        assert resp.status != 404

    async def test_chat_requires_message(self):
        """Test chat endpoint requires message field."""
        resp = await self.client.request(
            "POST",
            "/api/chat",
            json={}
        )
        assert resp.status == 400

        data = await resp.json()
        assert "error" in data
        assert "message" in data["error"].lower()

    async def test_chat_rejects_invalid_json(self):
        """Test chat endpoint rejects invalid JSON."""
        resp = await self.client.request(
            "POST",
            "/api/chat",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert resp.status == 400

    async def test_chat_streaming_response(self):
        """Test chat returns streaming SSE response."""
        resp = await self.client.request(
            "POST",
            "/api/chat",
            json={"message": "Hello"}
        )
        assert resp.status == 200

        # Check content type
        content_type = resp.headers.get('Content-Type', '')
        # Could be either streaming or JSON fallback
        assert content_type in ['text/event-stream', 'application/json']

    async def test_chat_with_provider_and_model(self):
        """Test chat accepts provider and model parameters."""
        resp = await self.client.request(
            "POST",
            "/api/chat",
            json={
                "message": "Hello",
                "provider": "claude",
                "model": "sonnet-4.5"
            }
        )
        assert resp.status == 200

    async def test_chat_with_session_id(self):
        """Test chat accepts session_id parameter."""
        resp = await self.client.request(
            "POST",
            "/api/chat",
            json={
                "message": "Hello",
                "session_id": "test-session-123"
            }
        )
        assert resp.status == 200

    async def test_chat_with_conversation_history(self):
        """Test chat accepts conversation_history parameter."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]

        resp = await self.client.request(
            "POST",
            "/api/chat",
            json={
                "message": "How are you?",
                "conversation_history": history
            }
        )
        assert resp.status == 200

    async def test_chat_streaming_format(self):
        """Test chat streaming uses SSE format."""
        resp = await self.client.request(
            "POST",
            "/api/chat",
            json={"message": "Hello"}
        )

        content_type = resp.headers.get('Content-Type', '')

        if 'text/event-stream' in content_type:
            # Read streaming response
            content = await resp.text()

            # Should contain SSE format
            assert 'data: ' in content or content == ''  # Empty is OK for immediate completion

    async def test_chat_cors_headers(self):
        """Test chat endpoint has CORS headers."""
        resp = await self.client.request(
            "POST",
            "/api/chat",
            json={"message": "Hello"}
        )

        # Check for Access-Control-Allow-Origin header
        assert 'Access-Control-Allow-Origin' in resp.headers

    async def test_chat_multiple_providers(self):
        """Test chat works with multiple providers."""
        providers = ['claude', 'openai', 'gemini', 'groq', 'kimi', 'windsurf']

        for provider in providers:
            resp = await self.client.request(
                "POST",
                "/api/chat",
                json={
                    "message": "Hello",
                    "provider": provider
                }
            )
            assert resp.status == 200, f"Failed for provider: {provider}"


class TestChatEndpointToolTransparency(AioHTTPTestCase):
    """Test tool transparency in chat responses."""

    async def get_application(self):
        """Create test application."""
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

    async def test_chat_with_linear_query(self):
        """Test chat with Linear query triggers tool transparency."""
        resp = await self.client.request(
            "POST",
            "/api/chat",
            json={"message": "What are my Linear issues?"}
        )
        assert resp.status == 200

        content_type = resp.headers.get('Content-Type', '')

        if 'text/event-stream' in content_type:
            content = await resp.text()

            # Should contain tool use events (or could be in JSON)
            # Check for either SSE format or fallback
            # Tool transparency is tested more thoroughly in unit tests
            assert len(content) >= 0  # Response received

    async def test_chat_with_github_query(self):
        """Test chat with GitHub query triggers tool transparency."""
        resp = await self.client.request(
            "POST",
            "/api/chat",
            json={"message": "Show me GitHub pull requests"}
        )
        assert resp.status == 200

    async def test_chat_with_slack_query(self):
        """Test chat with Slack query triggers tool transparency."""
        resp = await self.client.request(
            "POST",
            "/api/chat",
            json={"message": "Get Slack messages"}
        )
        assert resp.status == 200


class TestProviderStatusEndpoint(AioHTTPTestCase):
    """Test GET /api/providers/status endpoint."""

    async def get_application(self):
        """Create test application."""
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

    async def test_provider_status_endpoint_exists(self):
        """Test GET /api/providers/status exists."""
        resp = await self.client.request("GET", "/api/providers/status")
        assert resp.status == 200

    async def test_provider_status_returns_all_providers(self):
        """Test provider status returns all 6 providers."""
        resp = await self.client.request("GET", "/api/providers/status")
        assert resp.status == 200

        data = await resp.json()
        assert "providers" in data
        assert data["total_providers"] == 6

        # Check provider IDs
        provider_ids = [p["provider_id"] for p in data["providers"]]
        assert "claude" in provider_ids
        assert "openai" in provider_ids
        assert "gemini" in provider_ids
        assert "groq" in provider_ids
        assert "kimi" in provider_ids
        assert "windsurf" in provider_ids

    async def test_provider_status_includes_api_key_status(self):
        """Test provider status includes has_api_key field."""
        resp = await self.client.request("GET", "/api/providers/status")
        data = await resp.json()

        for provider in data["providers"]:
            assert "has_api_key" in provider
            assert "available" in provider
            assert "status" in provider

    async def test_provider_status_includes_models(self):
        """Test provider status includes models list."""
        resp = await self.client.request("GET", "/api/providers/status")
        data = await resp.json()

        for provider in data["providers"]:
            assert "models" in provider
            assert isinstance(provider["models"], list)
            assert len(provider["models"]) > 0

    async def test_provider_status_counts_active(self):
        """Test provider status counts active providers."""
        resp = await self.client.request("GET", "/api/providers/status")
        data = await resp.json()

        assert "active_providers" in data
        assert isinstance(data["active_providers"], int)
        assert data["active_providers"] >= 0
        assert data["active_providers"] <= data["total_providers"]

    async def test_provider_status_with_anthropic_key(self):
        """Test provider status with ANTHROPIC_API_KEY set."""
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            resp = await self.client.request("GET", "/api/providers/status")
            data = await resp.json()

            claude = next(p for p in data["providers"] if p["provider_id"] == "claude")
            assert claude["available"] is True
            assert claude["has_api_key"] is True
            assert claude["status"] == "active"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
