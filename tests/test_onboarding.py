"""Tests for AI-226: Onboarding API endpoints.

Tests /api/onboarding/status and /api/onboarding/complete endpoints.
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.server import DashboardServer


class TestOnboardingEndpoints(AioHTTPTestCase):
    """Test suite for onboarding API endpoints (AI-226)."""

    async def get_application(self):
        """Create test application instance."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)

        self.server = DashboardServer(
            project_name="test-project",
            metrics_dir=self.project_dir,
            host="127.0.0.1",
            port=8499,
        )
        return self.server.app

    async def tearDown(self):
        """Clean up test resources."""
        await super().tearDown()
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # /api/onboarding/status — no env vars set
    # ------------------------------------------------------------------

    async def test_onboarding_status_no_env_vars(self):
        """All integrations report as not connected when no env vars are set."""
        with patch.dict("os.environ", {}, clear=False):
            # Ensure none of our vars are present
            import os
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("LINEAR_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)

            resp = await self.client.get("/api/onboarding/status")
        assert resp.status == 200
        data = await resp.json()
        assert data["github_connected"] is False
        assert data["linear_connected"] is False
        assert data["api_key_set"] is False
        assert data["setup_complete"] is False

    async def test_onboarding_status_github_only(self):
        """Only github_connected is True when only GITHUB_TOKEN is set."""
        env = {"GITHUB_TOKEN": "ghp_testtoken123"}
        with patch.dict("os.environ", env, clear=False):
            import os
            os.environ.pop("LINEAR_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)

            resp = await self.client.get("/api/onboarding/status")
        assert resp.status == 200
        data = await resp.json()
        assert data["github_connected"] is True
        assert data["linear_connected"] is False
        assert data["api_key_set"] is False
        assert data["setup_complete"] is False

    async def test_onboarding_status_linear_only(self):
        """Only linear_connected is True when only LINEAR_API_KEY is set."""
        env = {"LINEAR_API_KEY": "lin_api_testkey"}
        with patch.dict("os.environ", env, clear=False):
            import os
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)

            resp = await self.client.get("/api/onboarding/status")
        assert resp.status == 200
        data = await resp.json()
        assert data["github_connected"] is False
        assert data["linear_connected"] is True
        assert data["api_key_set"] is False
        assert data["setup_complete"] is False

    async def test_onboarding_status_anthropic_only(self):
        """Only api_key_set is True when only ANTHROPIC_API_KEY is set."""
        env = {"ANTHROPIC_API_KEY": "sk-ant-test123"}
        with patch.dict("os.environ", env, clear=False):
            import os
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("LINEAR_API_KEY", None)

            resp = await self.client.get("/api/onboarding/status")
        assert resp.status == 200
        data = await resp.json()
        assert data["github_connected"] is False
        assert data["linear_connected"] is False
        assert data["api_key_set"] is True
        assert data["setup_complete"] is False

    async def test_onboarding_status_all_env_vars_set(self):
        """setup_complete is True only when all three env vars are present."""
        env = {
            "GITHUB_TOKEN": "ghp_all",
            "LINEAR_API_KEY": "lin_api_all",
            "ANTHROPIC_API_KEY": "sk-ant-all",
        }
        with patch.dict("os.environ", env, clear=False):
            resp = await self.client.get("/api/onboarding/status")
        assert resp.status == 200
        data = await resp.json()
        assert data["github_connected"] is True
        assert data["linear_connected"] is True
        assert data["api_key_set"] is True
        assert data["setup_complete"] is True

    async def test_onboarding_status_empty_string_vars(self):
        """Empty string env vars are treated as not connected."""
        env = {
            "GITHUB_TOKEN": "",
            "LINEAR_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
        }
        with patch.dict("os.environ", env, clear=False):
            resp = await self.client.get("/api/onboarding/status")
        assert resp.status == 200
        data = await resp.json()
        assert data["github_connected"] is False
        assert data["linear_connected"] is False
        assert data["api_key_set"] is False
        assert data["setup_complete"] is False

    async def test_onboarding_status_whitespace_only_vars(self):
        """Whitespace-only env vars are treated as not connected."""
        env = {
            "GITHUB_TOKEN": "   ",
            "LINEAR_API_KEY": "\t",
            "ANTHROPIC_API_KEY": " ",
        }
        with patch.dict("os.environ", env, clear=False):
            resp = await self.client.get("/api/onboarding/status")
        assert resp.status == 200
        data = await resp.json()
        assert data["github_connected"] is False
        assert data["linear_connected"] is False
        assert data["api_key_set"] is False
        assert data["setup_complete"] is False

    async def test_onboarding_status_response_shape(self):
        """Response contains exactly the expected keys."""
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("LINEAR_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)

            resp = await self.client.get("/api/onboarding/status")
        data = await resp.json()
        expected_keys = {"github_connected", "linear_connected", "api_key_set", "setup_complete"}
        assert set(data.keys()) == expected_keys

    async def test_onboarding_status_content_type(self):
        """Response content type is application/json."""
        resp = await self.client.get("/api/onboarding/status")
        assert "application/json" in resp.content_type

    async def test_onboarding_status_github_and_anthropic(self):
        """setup_complete is False when only GitHub and Anthropic keys are set."""
        env = {
            "GITHUB_TOKEN": "ghp_partial",
            "ANTHROPIC_API_KEY": "sk-ant-partial",
        }
        with patch.dict("os.environ", env, clear=False):
            import os
            os.environ.pop("LINEAR_API_KEY", None)

            resp = await self.client.get("/api/onboarding/status")
        assert resp.status == 200
        data = await resp.json()
        assert data["github_connected"] is True
        assert data["linear_connected"] is False
        assert data["api_key_set"] is True
        assert data["setup_complete"] is False

    # ------------------------------------------------------------------
    # /api/onboarding/complete
    # ------------------------------------------------------------------

    async def test_onboarding_complete_returns_200(self):
        """/api/onboarding/complete returns HTTP 200."""
        resp = await self.client.get("/api/onboarding/complete")
        assert resp.status == 200

    async def test_onboarding_complete_response_shape(self):
        """/api/onboarding/complete response has status and message fields."""
        resp = await self.client.get("/api/onboarding/complete")
        data = await resp.json()
        assert "status" in data
        assert "message" in data

    async def test_onboarding_complete_status_ok(self):
        """/api/onboarding/complete returns status=ok."""
        resp = await self.client.get("/api/onboarding/complete")
        data = await resp.json()
        assert data["status"] == "ok"

    async def test_onboarding_complete_content_type(self):
        """/api/onboarding/complete response content type is application/json."""
        resp = await self.client.get("/api/onboarding/complete")
        assert "application/json" in resp.content_type

    async def test_onboarding_complete_message_not_empty(self):
        """/api/onboarding/complete message field is a non-empty string."""
        resp = await self.client.get("/api/onboarding/complete")
        data = await resp.json()
        assert isinstance(data["message"], str)
        assert len(data["message"]) > 0

    async def test_onboarding_status_http_get_only(self):
        """OPTIONS preflight for /api/onboarding/status returns 204."""
        resp = await self.client.options("/api/onboarding/status")
        assert resp.status == 204

    async def test_onboarding_complete_http_options(self):
        """OPTIONS preflight for /api/onboarding/complete returns 204."""
        resp = await self.client.options("/api/onboarding/complete")
        assert resp.status == 204

    async def test_onboarding_status_linear_and_anthropic(self):
        """setup_complete is False when only Linear and Anthropic keys are set."""
        env = {
            "LINEAR_API_KEY": "lin_api_partial",
            "ANTHROPIC_API_KEY": "sk-ant-partial",
        }
        with patch.dict("os.environ", env, clear=False):
            import os
            os.environ.pop("GITHUB_TOKEN", None)

            resp = await self.client.get("/api/onboarding/status")
        assert resp.status == 200
        data = await resp.json()
        assert data["github_connected"] is False
        assert data["linear_connected"] is True
        assert data["api_key_set"] is True
        assert data["setup_complete"] is False

    async def test_onboarding_status_booleans_not_strings(self):
        """Status values are JSON booleans, not strings."""
        with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_tok"}, clear=False):
            import os
            os.environ.pop("LINEAR_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)

            resp = await self.client.get("/api/onboarding/status")
        data = await resp.json()
        # In Python JSON decode, booleans should be True/False, not "true"/"false"
        assert isinstance(data["github_connected"], bool)
        assert isinstance(data["linear_connected"], bool)
        assert isinstance(data["api_key_set"], bool)
        assert isinstance(data["setup_complete"], bool)
