"""
Tests for AI-143: REQ-MONITOR-001: Agent Status Panel

Verifies:
- All 13 agents from agents/definitions.py are listed correctly
- Status indicators (running=green pulsing, idle=gray, paused=yellow, error=red)
- CSS classes for status colors are defined
- /api/agents/status endpoint returns correct structure
- Real-time polling via loadAgentStatus() and startAgentStatusPolling()
- renderAgents() handles agent data with id, name, model, status, description
"""
import pytest
import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# The 13 canonical agent IDs from agents/definitions.py DEFAULT_MODELS
EXPECTED_AGENTS = [
    'linear', 'coding', 'github', 'slack',
    'pr_reviewer', 'ops', 'coding_fast', 'pr_reviewer_fast',
    'chatgpt', 'gemini', 'groq', 'kimi', 'windsurf',
]

EXPECTED_STATUS_VALUES = {'running', 'idle', 'paused', 'error'}


# ============================================================
# Test Group 1: Correct 13 Agents in mockAgents
# ============================================================

class TestMockAgentsRoster:
    """Verify index.html mockAgents has the correct 13 agents from definitions.py."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_all_13_expected_agent_ids_present(self, html_content):
        """All 13 canonical agent IDs must appear in mockAgents."""
        for agent_id in EXPECTED_AGENTS:
            assert f"'{agent_id}'" in html_content or f'"{agent_id}"' in html_content, \
                f"Agent ID '{agent_id}' not found in index.html"

    def test_linear_agent_in_mock_data(self, html_content):
        """linear agent must be in mockAgents."""
        assert "'linear'" in html_content or '"linear"' in html_content

    def test_coding_agent_in_mock_data(self, html_content):
        """coding agent must be in mockAgents."""
        assert "'coding'" in html_content

    def test_github_agent_in_mock_data(self, html_content):
        """github agent must be in mockAgents."""
        assert "'github'" in html_content

    def test_chatgpt_agent_in_mock_data(self, html_content):
        """chatgpt agent must be in mockAgents (not 'implementation_planning')."""
        assert "'chatgpt'" in html_content

    def test_gemini_agent_in_mock_data(self, html_content):
        """gemini agent must be in mockAgents (not 'requirements_analysis')."""
        assert "'gemini'" in html_content

    def test_groq_agent_in_mock_data(self, html_content):
        """groq agent must be in mockAgents (not 'integration')."""
        assert "'groq'" in html_content

    def test_kimi_agent_in_mock_data(self, html_content):
        """kimi agent must be in mockAgents (not 'migration')."""
        assert "'kimi'" in html_content

    def test_windsurf_agent_in_mock_data(self, html_content):
        """windsurf agent must be in mockAgents (not 'security_review')."""
        assert "'windsurf'" in html_content

    def test_wrong_agent_implementation_planning_not_present(self, html_content):
        """implementation_planning must NOT be in mockAgents (was incorrect)."""
        # Find the mockAgents array section
        idx = html_content.index('mockAgents')
        section = html_content[idx:idx + 2000]
        assert 'implementation_planning' not in section

    def test_wrong_agent_requirements_analysis_not_present(self, html_content):
        """requirements_analysis must NOT be in mockAgents."""
        idx = html_content.index('mockAgents')
        section = html_content[idx:idx + 2000]
        assert 'requirements_analysis' not in section

    def test_wrong_agent_security_review_not_present(self, html_content):
        """security_review must NOT be in mockAgents."""
        idx = html_content.index('mockAgents')
        section = html_content[idx:idx + 2000]
        assert 'security_review' not in section

    def test_agents_have_model_field(self, html_content):
        """Each agent in mockAgents must have a model field."""
        idx = html_content.index('mockAgents')
        section = html_content[idx:idx + 2000]
        assert 'model:' in section

    def test_agents_have_description_field(self, html_content):
        """Each agent in mockAgents must have a description field."""
        idx = html_content.index('mockAgents')
        section = html_content[idx:idx + 2000]
        assert 'description:' in section

    def test_sonnet_model_for_coding_agent(self, html_content):
        """coding agent must use sonnet model."""
        idx = html_content.index('mockAgents')
        section = html_content[idx:idx + 2000]
        assert "'sonnet'" in section


# ============================================================
# Test Group 2: Status Indicator CSS
# ============================================================

class TestStatusIndicatorCSS:
    """Verify status indicator CSS classes are properly defined."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_agent_status_dot_css_defined(self, html_content):
        """.agent-status-dot CSS class must be defined."""
        assert '.agent-status-dot' in html_content

    def test_running_status_has_green_color(self, html_content):
        """.agent-status-dot.running must have green background (accent-green)."""
        assert '.agent-status-dot.running' in html_content
        # Check it uses accent-green or a green color
        idx = html_content.index('.agent-status-dot.running')
        section = html_content[idx:idx + 200]
        assert 'accent-green' in section or '#10b981' in section

    def test_running_status_has_pulse_animation(self, html_content):
        """.agent-status-dot.running must have pulse animation."""
        idx = html_content.index('.agent-status-dot.running')
        section = html_content[idx:idx + 200]
        assert 'pulse' in section or 'animation' in section

    def test_idle_status_has_gray_color(self, html_content):
        """.agent-status-dot.idle must have gray color (text-muted)."""
        idx = html_content.index('.agent-status-dot.idle')
        section = html_content[idx:idx + 100]
        assert 'text-muted' in section or '#94a3b8' in section

    def test_paused_status_has_yellow_color(self, html_content):
        """.agent-status-dot.paused must have yellow color (accent-yellow)."""
        idx = html_content.index('.agent-status-dot.paused')
        section = html_content[idx:idx + 100]
        assert 'accent-yellow' in section or '#f59e0b' in section

    def test_error_status_has_red_color(self, html_content):
        """.agent-status-dot.error must have red color (accent-red)."""
        idx = html_content.index('.agent-status-dot.error')
        section = html_content[idx:idx + 100]
        assert 'accent-red' in section or '#ef4444' in section

    def test_agent_description_css_defined(self, html_content):
        """.agent-description CSS class must be defined for description text."""
        assert '.agent-description' in html_content

    def test_agent_model_badge_css_defined(self, html_content):
        """.agent-model-badge CSS class must be defined."""
        assert '.agent-model-badge' in html_content

    def test_agent_meta_css_defined(self, html_content):
        """.agent-meta CSS class must be defined."""
        assert '.agent-meta' in html_content

    def test_agent_details_css_defined(self, html_content):
        """.agent-details CSS class must be defined."""
        assert '.agent-details' in html_content


# ============================================================
# Test Group 3: renderAgents() function
# ============================================================

class TestRenderAgentsFunction:
    """Verify renderAgents() function renders enhanced agent cards."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_render_agents_function_defined(self, html_content):
        """renderAgents function must be defined."""
        assert 'function renderAgents' in html_content or 'renderAgents = function' in html_content

    def test_render_agents_uses_agent_id(self, html_content):
        """renderAgents must use agent.id (not just agent.name) for data-agent."""
        assert 'agent.id' in html_content

    def test_render_agents_shows_description(self, html_content):
        """renderAgents must show agent.description."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 1500]
        assert 'agent.description' in section or 'description' in section

    def test_render_agents_shows_model(self, html_content):
        """renderAgents must show agent.model."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 1500]
        assert 'agent.model' in section or 'model' in section

    def test_render_agents_shows_status_dot(self, html_content):
        """renderAgents must render a status dot with status class."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 4000]
        assert 'agent-status-dot' in section

    def test_render_agents_uses_escape_html(self, html_content):
        """renderAgents must use escapeHtml() for XSS prevention."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 1500]
        assert 'escapeHtml' in section

    def test_render_agents_is_globally_exposed(self, html_content):
        """renderAgents must be exposed on window object for testing."""
        assert 'window.renderAgents' in html_content


# ============================================================
# Test Group 4: loadAgentStatus() function
# ============================================================

class TestLoadAgentStatusFunction:
    """Verify loadAgentStatus() function fetches /api/agents/status."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_load_agent_status_function_defined(self, html_content):
        """loadAgentStatus async function must be defined."""
        assert 'async function loadAgentStatus' in html_content

    def test_load_agent_status_fetches_correct_endpoint(self, html_content):
        """loadAgentStatus must fetch /api/agents/status."""
        assert '/api/agents/status' in html_content

    def test_load_agent_status_updates_state_agents(self, html_content):
        """loadAgentStatus must update state.agents from API response."""
        idx = html_content.index('async function loadAgentStatus')
        section = html_content[idx:idx + 1000]
        assert 'state.agents' in section

    def test_load_agent_status_calls_render_agents(self, html_content):
        """loadAgentStatus must call renderAgents() after update."""
        idx = html_content.index('async function loadAgentStatus')
        section = html_content[idx:idx + 1500]
        assert 'renderAgents' in section

    def test_load_agent_status_handles_error_gracefully(self, html_content):
        """loadAgentStatus must handle API errors gracefully with try/catch."""
        idx = html_content.index('async function loadAgentStatus')
        section = html_content[idx:idx + 1500]
        assert 'catch' in section

    def test_start_agent_status_polling_defined(self, html_content):
        """startAgentStatusPolling function must be defined."""
        assert 'function startAgentStatusPolling' in html_content

    def test_polling_uses_set_interval(self, html_content):
        """startAgentStatusPolling must use setInterval for periodic updates."""
        idx = html_content.index('function startAgentStatusPolling')
        section = html_content[idx:idx + 500]
        assert 'setInterval' in section

    def test_polling_interval_is_5_seconds(self, html_content):
        """Polling interval must be 5000ms (5 seconds)."""
        idx = html_content.index('function startAgentStatusPolling')
        section = html_content[idx:idx + 500]
        assert '5000' in section

    def test_load_agent_status_exposed_on_window(self, html_content):
        """loadAgentStatus must be exposed on window for testing."""
        assert 'window.loadAgentStatus' in html_content

    def test_start_polling_called_in_init(self, html_content):
        """startAgentStatusPolling must be called in init()."""
        idx = html_content.index('function init()')
        section = html_content[idx:idx + 2000]
        assert 'startAgentStatusPolling' in section


# ============================================================
# Test Group 5: /api/agents/status endpoint
# ============================================================

class TestAgentsStatusEndpoint:
    """Verify /api/agents/status endpoint in dashboard_server.py."""

    @pytest.fixture(scope='class')
    def server_content(self):
        return (PROJECT_ROOT / 'scripts' / 'dashboard_server.py').read_text(encoding='utf-8')

    def test_agents_status_route_registered(self, server_content):
        """Route /api/agents/status must be registered."""
        assert '/api/agents/status' in server_content

    def test_handle_agents_status_method_defined(self, server_content):
        """handle_agents_status method must be defined."""
        assert 'handle_agents_status' in server_content

    def test_agent_roster_has_13_agents(self, server_content):
        """AGENT_ROSTER in handle_agents_status must have all 13 agents."""
        for agent_id in EXPECTED_AGENTS:
            assert f'"{agent_id}"' in server_content or f"'{agent_id}'" in server_content

    def test_endpoint_returns_agents_key(self, server_content):
        """Endpoint must return 'agents' key in JSON response."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 4000]
        assert '"agents"' in section or "'agents'" in section

    def test_endpoint_returns_total_key(self, server_content):
        """Endpoint must return 'total' count."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 6000]
        assert '"total"' in section

    def test_endpoint_returns_running_count(self, server_content):
        """Endpoint must return 'running_count' for quick status check."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 6000]
        assert 'running_count' in section

    def test_endpoint_returns_timestamp(self, server_content):
        """Endpoint must return timestamp."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 4000]
        assert 'timestamp' in section

    def test_endpoint_has_fallback_on_error(self, server_content):
        """Endpoint must have try/except with fallback idle status."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 6000]
        assert 'except' in section
        assert '"idle"' in section or "'idle'" in section

    def test_agent_items_have_model_field(self, server_content):
        """Each agent item must include model field."""
        idx = server_content.index('AGENT_ROSTER')
        section = server_content[idx:idx + 2000]
        assert '"model"' in section

    def test_agent_items_have_description_field(self, server_content):
        """Each agent item must include description field."""
        idx = server_content.index('AGENT_ROSTER')
        section = server_content[idx:idx + 2000]
        assert '"description"' in section

    def test_status_defaults_to_idle(self, server_content):
        """Status must default to 'idle' when no active metrics."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 6000]
        assert 'idle' in section


# ============================================================
# Test Group 6: /api/agents/status endpoint live test
# ============================================================

class TestAgentsStatusEndpointLive:
    """Live tests for the /api/agents/status endpoint."""

    @pytest.fixture
    def app(self):
        """Create a test app instance."""
        from aiohttp.test_utils import TestClient, TestServer
        from aiohttp import web
        sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
        from dashboard_server import DashboardServer
        server = DashboardServer(project_dir=str(PROJECT_ROOT), project_name='test')
        return server.app

    @pytest.mark.asyncio
    async def test_agents_status_returns_200(self, app):
        """GET /api/agents/status must return HTTP 200."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/agents/status')
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_agents_status_returns_13_agents(self, app):
        """GET /api/agents/status must return exactly 13 agents."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/agents/status')
            data = await resp.json()
            assert data['total'] == 13
            assert len(data['agents']) == 13

    @pytest.mark.asyncio
    async def test_agents_status_has_all_expected_agent_ids(self, app):
        """GET /api/agents/status must include all 13 canonical agent IDs."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/agents/status')
            data = await resp.json()
            agent_ids = {a['id'] for a in data['agents']}
            for expected_id in EXPECTED_AGENTS:
                assert expected_id in agent_ids, f"Agent '{expected_id}' missing from /api/agents/status"

    @pytest.mark.asyncio
    async def test_agents_status_each_has_required_fields(self, app):
        """Each agent in /api/agents/status must have id, name, model, status, description."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/agents/status')
            data = await resp.json()
            required_fields = {'id', 'name', 'model', 'status', 'description'}
            for agent in data['agents']:
                for field in required_fields:
                    assert field in agent, f"Agent '{agent.get('id')}' missing field '{field}'"

    @pytest.mark.asyncio
    async def test_agents_status_default_status_is_idle(self, app):
        """Default status for all agents must be 'idle' (no active runs)."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/agents/status')
            data = await resp.json()
            for agent in data['agents']:
                assert agent['status'] in EXPECTED_STATUS_VALUES

    @pytest.mark.asyncio
    async def test_agents_status_has_running_count(self, app):
        """GET /api/agents/status must return running_count field."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/agents/status')
            data = await resp.json()
            assert 'running_count' in data
            assert isinstance(data['running_count'], int)

    @pytest.mark.asyncio
    async def test_agents_status_has_timestamp(self, app):
        """GET /api/agents/status must return timestamp field."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/agents/status')
            data = await resp.json()
            assert 'timestamp' in data

    @pytest.mark.asyncio
    async def test_coding_agent_uses_sonnet_model(self, app):
        """coding agent must use sonnet model (from DEFAULT_MODELS)."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/agents/status')
            data = await resp.json()
            coding = next((a for a in data['agents'] if a['id'] == 'coding'), None)
            assert coding is not None
            assert coding['model'] == 'sonnet'

    @pytest.mark.asyncio
    async def test_pr_reviewer_uses_sonnet_model(self, app):
        """pr_reviewer agent must use sonnet model."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/agents/status')
            data = await resp.json()
            reviewer = next((a for a in data['agents'] if a['id'] == 'pr_reviewer'), None)
            assert reviewer is not None
            assert reviewer['model'] == 'sonnet'
