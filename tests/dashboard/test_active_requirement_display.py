"""
Tests for AI-144: REQ-MONITOR-002: Active Requirement Display

Verifies:
- When agent status is 'running', an active task section shows:
  - Linear ticket key and title
  - Full requirement description (expandable via details/summary)
  - Elapsed time timer (live)
  - Token count (formatted with K for thousands)
  - Estimated cost (formatted with $ prefix)
- formatCount(), formatCost(), formatElapsed() utility functions
- updateActiveTaskTimers() updates timer elements
- /api/agents/status includes active_task field when running
"""
import pytest
import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Test Group 1: CSS for Active Task Section
# ============================================================

class TestActiveTaskCSS:
    """Verify CSS classes for the active requirement display."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_agent_active_task_css_defined(self, html_content):
        """.agent-active-task CSS class must be defined."""
        assert '.agent-active-task' in html_content

    def test_agent_active_task_header_css_defined(self, html_content):
        """.agent-active-task-header CSS class must be defined."""
        assert '.agent-active-task-header' in html_content

    def test_agent_task_ticket_css_defined(self, html_content):
        """.agent-task-ticket CSS class for ticket key display."""
        assert '.agent-task-ticket' in html_content

    def test_agent_task_title_css_defined(self, html_content):
        """.agent-task-title CSS class for ticket title display."""
        assert '.agent-task-title' in html_content

    def test_agent_task_timer_css_defined(self, html_content):
        """.agent-task-timer CSS class for elapsed time display."""
        assert '.agent-task-timer' in html_content

    def test_agent_active_task_body_css_defined(self, html_content):
        """.agent-active-task-body CSS class for expandable content."""
        assert '.agent-active-task-body' in html_content

    def test_agent_task_description_css_defined(self, html_content):
        """.agent-task-description CSS class for description text."""
        assert '.agent-task-description' in html_content

    def test_agent_task_stats_css_defined(self, html_content):
        """.agent-task-stats CSS class for token/cost stats container."""
        assert '.agent-task-stats' in html_content

    def test_agent_task_stat_css_defined(self, html_content):
        """.agent-task-stat CSS class for individual stat."""
        assert '.agent-task-stat' in html_content

    def test_agent_task_stat_label_css_defined(self, html_content):
        """.agent-task-stat-label CSS class."""
        assert '.agent-task-stat-label' in html_content

    def test_agent_task_stat_value_css_defined(self, html_content):
        """.agent-task-stat-value CSS class."""
        assert '.agent-task-stat-value' in html_content


# ============================================================
# Test Group 2: renderAgents() active task section
# ============================================================

class TestRenderAgentsActiveTask:
    """Verify renderAgents() shows active task section for running agents."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_render_agents_checks_running_status(self, html_content):
        """renderAgents must check if status === 'running' for active task."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 3000]
        assert "status === 'running'" in section

    def test_render_agents_checks_active_task(self, html_content):
        """renderAgents must check agent.active_task."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 3000]
        assert 'agent.active_task' in section

    def test_render_agents_shows_ticket_key(self, html_content):
        """renderAgents must display ticket_key from active_task."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 3000]
        assert 'ticket_key' in section

    def test_render_agents_shows_ticket_title(self, html_content):
        """renderAgents must display title from active_task."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 3000]
        assert 'task.title' in section

    def test_render_agents_shows_task_description(self, html_content):
        """renderAgents must display description from active_task."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 3000]
        assert 'task.description' in section or 'taskDesc' in section

    def test_render_agents_uses_details_for_expandable(self, html_content):
        """renderAgents must use <details> element for expandable task info."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 3000]
        assert '<details class="agent-active-task"' in section

    def test_render_agents_shows_tokens(self, html_content):
        """renderAgents must display token count from active_task."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 3000]
        assert 'tokens' in section.lower()

    def test_render_agents_shows_cost(self, html_content):
        """renderAgents must display cost from active_task."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 3000]
        assert 'cost' in section.lower()

    def test_render_agents_uses_format_count(self, html_content):
        """renderAgents must use formatCount() for token display."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 3000]
        assert 'formatCount' in section

    def test_render_agents_uses_format_cost(self, html_content):
        """renderAgents must use formatCost() for cost display."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 3000]
        assert 'formatCost' in section

    def test_render_agents_timer_has_data_started(self, html_content):
        """Timer element must have data-started attribute for elapsed calculation."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 3000]
        assert 'data-started' in section

    def test_render_agents_timer_has_id(self, html_content):
        """Timer element must have unique id for DOM access."""
        idx = html_content.index('window.renderAgents')
        section = html_content[idx:idx + 3000]
        assert 'agent-task-timer' in section and 'id=' in section


# ============================================================
# Test Group 3: formatCount() utility function
# ============================================================

class TestFormatCountFunction:
    """Verify formatCount() correctly formats numbers with K suffix."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_format_count_function_defined(self, html_content):
        """formatCount function must be defined."""
        assert 'function formatCount' in html_content

    def test_format_count_uses_k_suffix(self, html_content):
        """formatCount must use 'K' suffix for thousands."""
        idx = html_content.index('function formatCount')
        section = html_content[idx:idx + 200]
        assert "'K'" in section or '"K"' in section

    def test_format_count_threshold_1000(self, html_content):
        """formatCount must apply K suffix at 1000."""
        idx = html_content.index('function formatCount')
        section = html_content[idx:idx + 200]
        assert '1000' in section

    def test_format_count_exposed_on_window(self, html_content):
        """formatCount must be exposed on window for testing."""
        assert 'window.formatCount' in html_content


# ============================================================
# Test Group 4: formatCost() utility function
# ============================================================

class TestFormatCostFunction:
    """Verify formatCost() correctly formats dollar amounts."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_format_cost_function_defined(self, html_content):
        """formatCost function must be defined."""
        assert 'function formatCost' in html_content

    def test_format_cost_uses_dollar_prefix(self, html_content):
        """formatCost must use '$' prefix."""
        idx = html_content.index('function formatCost')
        section = html_content[idx:idx + 200]
        assert "'$'" in section or '"$"' in section

    def test_format_cost_exposed_on_window(self, html_content):
        """formatCost must be exposed on window for testing."""
        assert 'window.formatCost' in html_content


# ============================================================
# Test Group 5: formatElapsed() utility function
# ============================================================

class TestFormatElapsedFunction:
    """Verify formatElapsed() formats elapsed seconds as M:SS."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_format_elapsed_function_defined(self, html_content):
        """formatElapsed function must be defined."""
        assert 'function formatElapsed' in html_content

    def test_format_elapsed_uses_padStart(self, html_content):
        """formatElapsed must use padStart for MM:SS formatting."""
        idx = html_content.index('function formatElapsed')
        section = html_content[idx:idx + 300]
        assert 'padStart' in section

    def test_format_elapsed_exposed_on_window(self, html_content):
        """formatElapsed must be exposed on window for testing."""
        assert 'window.formatElapsed' in html_content


# ============================================================
# Test Group 6: updateActiveTaskTimers() function
# ============================================================

class TestUpdateActiveTaskTimers:
    """Verify updateActiveTaskTimers() updates timer elements."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_update_active_task_timers_defined(self, html_content):
        """updateActiveTaskTimers function must be defined."""
        assert 'function updateActiveTaskTimers' in html_content

    def test_update_timers_queries_all_timers(self, html_content):
        """updateActiveTaskTimers must query all .agent-task-timer elements."""
        idx = html_content.index('function updateActiveTaskTimers')
        section = html_content[idx:idx + 500]
        assert 'agent-task-timer' in section

    def test_update_timers_reads_data_started(self, html_content):
        """updateActiveTaskTimers must read data-started attribute."""
        idx = html_content.index('function updateActiveTaskTimers')
        section = html_content[idx:idx + 500]
        assert 'data-started' in section

    def test_update_timers_uses_format_elapsed(self, html_content):
        """updateActiveTaskTimers must call formatElapsed()."""
        idx = html_content.index('function updateActiveTaskTimers')
        section = html_content[idx:idx + 800]
        assert 'formatElapsed' in section

    def test_timer_interval_is_1_second(self, html_content):
        """Timer must update every 1000ms (1 second)."""
        assert 'updateActiveTaskTimers, 1000' in html_content or 'updateActiveTaskTimers,1000' in html_content

    def test_timer_interval_stored_on_window(self, html_content):
        """Timer interval ID must be stored on window for cleanup."""
        assert 'window.activeTaskTimerIntervalId' in html_content

    def test_update_timers_exposed_on_window(self, html_content):
        """updateActiveTaskTimers must be exposed on window."""
        assert 'window.updateActiveTaskTimers' in html_content


# ============================================================
# Test Group 7: /api/agents/status includes active_task field
# ============================================================

class TestAgentsStatusActiveTask:
    """Verify /api/agents/status endpoint includes active_task field."""

    @pytest.fixture(scope='class')
    def server_content(self):
        return (PROJECT_ROOT / 'scripts' / 'dashboard_server.py').read_text(encoding='utf-8')

    def test_active_task_field_in_response(self, server_content):
        """handle_agents_status must include active_task in agent dict."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 6000]
        assert 'active_task' in section

    def test_active_task_built_for_running_agents(self, server_content):
        """active_task must be built when status is running."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 6000]
        assert 'status == "running"' in section and 'active_task' in section

    def test_active_task_has_ticket_key(self, server_content):
        """active_task must include ticket_key field."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 6000]
        assert 'ticket_key' in section

    def test_active_task_has_title(self, server_content):
        """active_task must include title field."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 6000]
        assert '"title"' in section

    def test_active_task_has_tokens(self, server_content):
        """active_task must include tokens field."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 6000]
        assert 'tokens' in section

    def test_active_task_has_cost(self, server_content):
        """active_task must include cost field."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 6000]
        assert 'cost' in section

    def test_active_task_has_started_at(self, server_content):
        """active_task must include started_at timestamp."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 6000]
        assert 'started_at' in section

    def test_active_task_null_for_idle_agents(self, server_content):
        """active_task must be None/null for idle agents."""
        idx = server_content.index('async def handle_agents_status')
        section = server_content[idx:idx + 6000]
        assert 'active_task": None' in section or '"active_task": null' in section or 'active_task = None' in section

    def test_fallback_includes_active_task_none(self, server_content):
        """Fallback error response must include active_task: None."""
        # Find the except block
        idx = server_content.rindex('active_task')  # Last occurrence is in fallback
        section = server_content[idx:idx + 100]
        assert 'None' in section


# ============================================================
# Test Group 8: Live endpoint test for active_task field
# ============================================================

class TestAgentsStatusActiveTaskLive:
    """Live endpoint tests for active_task field."""

    @pytest.fixture
    def app(self):
        sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
        from dashboard_server import DashboardServer
        server = DashboardServer(project_dir=str(PROJECT_ROOT), project_name='test')
        return server.app

    @pytest.mark.asyncio
    async def test_agents_status_active_task_field_present(self, app):
        """Each agent must have active_task field (None if idle)."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/agents/status')
            data = await resp.json()
            for agent in data['agents']:
                assert 'active_task' in agent, f"Agent {agent['id']} missing active_task field"

    @pytest.mark.asyncio
    async def test_agents_status_active_task_is_none_for_idle(self, app):
        """All agents (idle by default) must have active_task=None."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/agents/status')
            data = await resp.json()
            idle_agents = [a for a in data['agents'] if a['status'] == 'idle']
            for agent in idle_agents:
                assert agent['active_task'] is None, \
                    f"Idle agent {agent['id']} should have active_task=None"
