"""
Tests for AI-147: REQ-METRICS-001: Implement Global Metrics Bar

Verifies:
- Header shows all 5 metrics from DashboardState: total_sessions, total_tokens,
  total_cost_usd, total_duration_seconds, session_number
- ProgressRing used for tokens and cost visualization
- HTML elements: global-metrics-bar, total-sessions, total-duration, ring containers
- CSS: global-metrics-ring-wrap, global-metrics-ring, global-metrics-ring-item
- formatDuration() utility function
- updateGlobalMetricsBar() function
- loadGlobalMetrics() function polls /api/metrics
- GLOBAL_METRICS_MAX threshold constants
- renderGlobalMetricRing() function
- init() calls loadGlobalMetrics()
"""
import pytest
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Test Group 1: Header HTML — 5 Metric Elements
# ============================================================

class TestGlobalMetricsBarHTML:
    """Verify the header shows all 5 required metrics."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_global_metrics_bar_id_exists(self, html_content):
        """Header stats must have id=global-metrics-bar."""
        assert 'id="global-metrics-bar"' in html_content

    def test_global_metrics_bar_aria_label(self, html_content):
        """Global metrics bar must have aria-label."""
        assert 'aria-label="Global Dashboard Metrics"' in html_content

    def test_session_number_element_exists(self, html_content):
        """session-number element must exist."""
        assert 'id="session-number"' in html_content

    def test_total_sessions_element_exists(self, html_content):
        """total-sessions element must be in header."""
        assert 'id="total-sessions"' in html_content

    def test_total_tokens_element_exists(self, html_content):
        """total-tokens element must exist."""
        assert 'id="total-tokens"' in html_content

    def test_total_cost_element_exists(self, html_content):
        """total-cost element must exist."""
        assert 'id="total-cost"' in html_content

    def test_total_duration_element_exists(self, html_content):
        """total-duration element must exist for uptime display."""
        assert 'id="total-duration"' in html_content

    def test_tokens_ring_container_exists(self, html_content):
        """tokens-ring-container element must exist for ProgressRing."""
        assert 'id="tokens-ring-container"' in html_content

    def test_cost_ring_container_exists(self, html_content):
        """cost-ring-container element must exist for ProgressRing."""
        assert 'id="cost-ring-container"' in html_content

    def test_total_sessions_label_shown(self, html_content):
        """'Total Sessions' label must be shown."""
        assert 'Total Sessions' in html_content

    def test_uptime_label_shown(self, html_content):
        """'Uptime' label must be shown."""
        assert 'Uptime' in html_content


# ============================================================
# Test Group 2: CSS for Global Metrics Bar
# ============================================================

class TestGlobalMetricsBarCSS:
    """Verify CSS classes for the global metrics bar."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_global_metrics_bar_css(self, html_content):
        """#global-metrics-bar CSS must be defined."""
        assert '#global-metrics-bar' in html_content

    def test_global_metrics_ring_wrap_css(self, html_content):
        """.global-metrics-ring-wrap CSS must be defined."""
        assert '.global-metrics-ring-wrap' in html_content

    def test_global_metrics_ring_css(self, html_content):
        """.global-metrics-ring CSS must be defined."""
        assert '.global-metrics-ring' in html_content

    def test_global_metrics_ring_item_css(self, html_content):
        """.global-metrics-ring-item CSS must be defined."""
        assert '.global-metrics-ring-item' in html_content

    def test_total_sessions_css_defined(self, html_content):
        """#total-sessions CSS style must be defined."""
        assert '#total-sessions' in html_content

    def test_total_duration_css_defined(self, html_content):
        """#total-duration CSS style must be defined."""
        assert '#total-duration' in html_content


# ============================================================
# Test Group 3: formatDuration() Utility Function
# ============================================================

class TestFormatDurationFunction:
    """Verify formatDuration() formats seconds to human-readable string."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_format_duration_function_defined(self, html_content):
        """formatDuration function must be defined."""
        assert 'function formatDuration' in html_content

    def test_format_duration_exposed_on_window(self, html_content):
        """formatDuration must be exposed on window."""
        assert 'window.formatDuration' in html_content

    def test_format_duration_handles_hours(self, html_content):
        """formatDuration must handle hours (>= 3600s)."""
        idx = html_content.index('function formatDuration')
        section = html_content[idx:idx + 500]
        assert '3600' in section

    def test_format_duration_handles_minutes(self, html_content):
        """formatDuration must handle minutes (>= 60s)."""
        idx = html_content.index('function formatDuration')
        section = html_content[idx:idx + 500]
        assert '60' in section

    def test_format_duration_returns_hours_format(self, html_content):
        """formatDuration must use 'h' for hours."""
        idx = html_content.index('function formatDuration')
        section = html_content[idx:idx + 500]
        assert "'h'" in section or '"h"' in section or '`h`' in section or 'h ' in section


# ============================================================
# Test Group 4: GLOBAL_METRICS_MAX Constants
# ============================================================

class TestGlobalMetricsMaxConstants:
    """Verify GLOBAL_METRICS_MAX threshold constants."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_global_metrics_max_defined(self, html_content):
        """GLOBAL_METRICS_MAX must be defined."""
        assert 'GLOBAL_METRICS_MAX' in html_content

    def test_global_metrics_max_exposed_on_window(self, html_content):
        """GLOBAL_METRICS_MAX must be exposed on window."""
        assert 'window.GLOBAL_METRICS_MAX' in html_content

    def test_global_metrics_max_has_tokens(self, html_content):
        """GLOBAL_METRICS_MAX must have tokens threshold."""
        idx = html_content.index('GLOBAL_METRICS_MAX')
        section = html_content[idx:idx + 300]
        assert 'tokens' in section

    def test_global_metrics_max_has_cost(self, html_content):
        """GLOBAL_METRICS_MAX must have cost threshold."""
        idx = html_content.index('GLOBAL_METRICS_MAX')
        section = html_content[idx:idx + 300]
        assert 'cost' in section


# ============================================================
# Test Group 5: renderGlobalMetricRing() Function
# ============================================================

class TestRenderGlobalMetricRing:
    """Verify renderGlobalMetricRing() function."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_render_global_metric_ring_defined(self, html_content):
        """renderGlobalMetricRing function must be defined."""
        assert 'function renderGlobalMetricRing' in html_content

    def test_render_global_metric_ring_exposed_on_window(self, html_content):
        """renderGlobalMetricRing must be exposed on window."""
        assert 'window.renderGlobalMetricRing' in html_content

    def test_render_global_metric_ring_calls_progress_ring(self, html_content):
        """renderGlobalMetricRing must call ProgressRing()."""
        idx = html_content.index('function renderGlobalMetricRing')
        section = html_content[idx:idx + 500]
        assert 'ProgressRing' in section

    def test_render_global_metric_ring_clamps_fraction(self, html_content):
        """renderGlobalMetricRing must clamp fraction to 0-1."""
        idx = html_content.index('function renderGlobalMetricRing')
        section = html_content[idx:idx + 500]
        assert 'Math.min' in section or 'Math.max' in section or 'clamp' in section.lower()


# ============================================================
# Test Group 6: updateGlobalMetricsBar() Function
# ============================================================

class TestUpdateGlobalMetricsBar:
    """Verify updateGlobalMetricsBar() function."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_update_global_metrics_bar_defined(self, html_content):
        """updateGlobalMetricsBar function must be defined."""
        assert 'function updateGlobalMetricsBar' in html_content

    def test_update_global_metrics_bar_exposed_on_window(self, html_content):
        """updateGlobalMetricsBar must be exposed on window."""
        assert 'window.updateGlobalMetricsBar' in html_content

    def test_updates_session_number(self, html_content):
        """updateGlobalMetricsBar must update session-number element."""
        idx = html_content.index('function updateGlobalMetricsBar')
        section = html_content[idx:idx + 2000]
        assert 'session-number' in section

    def test_updates_total_sessions(self, html_content):
        """updateGlobalMetricsBar must update total-sessions element."""
        idx = html_content.index('function updateGlobalMetricsBar')
        section = html_content[idx:idx + 2000]
        assert 'total-sessions' in section

    def test_updates_total_tokens(self, html_content):
        """updateGlobalMetricsBar must update total-tokens element."""
        idx = html_content.index('function updateGlobalMetricsBar')
        section = html_content[idx:idx + 2000]
        assert 'total-tokens' in section

    def test_updates_total_cost(self, html_content):
        """updateGlobalMetricsBar must update total-cost element."""
        idx = html_content.index('function updateGlobalMetricsBar')
        section = html_content[idx:idx + 2000]
        assert 'total-cost' in section

    def test_updates_total_duration(self, html_content):
        """updateGlobalMetricsBar must update total-duration element."""
        idx = html_content.index('function updateGlobalMetricsBar')
        section = html_content[idx:idx + 2000]
        assert 'total-duration' in section

    def test_renders_tokens_progress_ring(self, html_content):
        """updateGlobalMetricsBar must render ProgressRing for tokens."""
        idx = html_content.index('function updateGlobalMetricsBar')
        section = html_content[idx:idx + 2000]
        assert 'tokens-ring-container' in section

    def test_renders_cost_progress_ring(self, html_content):
        """updateGlobalMetricsBar must render ProgressRing for cost."""
        idx = html_content.index('function updateGlobalMetricsBar')
        section = html_content[idx:idx + 2000]
        assert 'cost-ring-container' in section

    def test_uses_format_count_for_tokens(self, html_content):
        """updateGlobalMetricsBar must use formatCount() for tokens."""
        idx = html_content.index('function updateGlobalMetricsBar')
        section = html_content[idx:idx + 2000]
        assert 'formatCount' in section

    def test_uses_format_cost_for_cost(self, html_content):
        """updateGlobalMetricsBar must use formatCost() for cost."""
        idx = html_content.index('function updateGlobalMetricsBar')
        section = html_content[idx:idx + 2000]
        assert 'formatCost' in section

    def test_uses_format_duration_for_uptime(self, html_content):
        """updateGlobalMetricsBar must use formatDuration() for uptime."""
        idx = html_content.index('function updateGlobalMetricsBar')
        section = html_content[idx:idx + 2000]
        assert 'formatDuration' in section


# ============================================================
# Test Group 7: loadGlobalMetrics() Function
# ============================================================

class TestLoadGlobalMetrics:
    """Verify loadGlobalMetrics() function."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_load_global_metrics_defined(self, html_content):
        """loadGlobalMetrics function must be defined."""
        assert 'function loadGlobalMetrics' in html_content

    def test_load_global_metrics_exposed_on_window(self, html_content):
        """loadGlobalMetrics must be exposed on window."""
        assert 'window.loadGlobalMetrics' in html_content

    def test_load_global_metrics_fetches_api_metrics(self, html_content):
        """loadGlobalMetrics must fetch /api/metrics."""
        idx = html_content.index('function loadGlobalMetrics')
        section = html_content[idx:idx + 800]
        assert '/api/metrics' in section

    def test_load_global_metrics_reads_total_sessions(self, html_content):
        """loadGlobalMetrics must read total_sessions from DashboardState."""
        idx = html_content.index('function loadGlobalMetrics')
        section = html_content[idx:idx + 800]
        assert 'total_sessions' in section

    def test_load_global_metrics_reads_total_tokens(self, html_content):
        """loadGlobalMetrics must read total_tokens from DashboardState."""
        idx = html_content.index('function loadGlobalMetrics')
        section = html_content[idx:idx + 800]
        assert 'total_tokens' in section

    def test_load_global_metrics_reads_total_cost(self, html_content):
        """loadGlobalMetrics must read total_cost_usd from DashboardState."""
        idx = html_content.index('function loadGlobalMetrics')
        section = html_content[idx:idx + 800]
        assert 'total_cost_usd' in section

    def test_load_global_metrics_reads_total_duration(self, html_content):
        """loadGlobalMetrics must read total_duration_seconds from DashboardState."""
        idx = html_content.index('function loadGlobalMetrics')
        section = html_content[idx:idx + 800]
        assert 'total_duration_seconds' in section

    def test_load_global_metrics_calls_update_bar(self, html_content):
        """loadGlobalMetrics must call updateGlobalMetricsBar()."""
        idx = html_content.index('function loadGlobalMetrics')
        section = html_content[idx:idx + 800]
        assert 'updateGlobalMetricsBar' in section

    def test_load_global_metrics_handles_errors(self, html_content):
        """loadGlobalMetrics must handle fetch errors gracefully."""
        idx = html_content.index('function loadGlobalMetrics')
        section = html_content[idx:idx + 800]
        assert 'catch' in section

    def test_load_global_metrics_called_in_init(self, html_content):
        """loadGlobalMetrics must be called in init()."""
        idx = html_content.index('function init()')
        section = html_content[idx:idx + 3500]
        assert 'loadGlobalMetrics' in section


# ============================================================
# Test Group 8: Live endpoint test
# ============================================================

class TestGlobalMetricsEndpointLive:
    """Live endpoint tests for /api/metrics (used by global metrics bar)."""

    @pytest.fixture
    def app(self):
        sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
        from dashboard_server import DashboardServer
        server = DashboardServer(project_dir=str(PROJECT_ROOT), project_name='test')
        return server.app

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_200(self, app):
        """/api/metrics must return 200 OK."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/metrics')
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_total_sessions(self, app):
        """/api/metrics must include total_sessions field."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/metrics')
            data = await resp.json()
            assert 'total_sessions' in data

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_total_tokens(self, app):
        """/api/metrics must include total_tokens field."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/metrics')
            data = await resp.json()
            assert 'total_tokens' in data

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_total_cost(self, app):
        """/api/metrics must include total_cost_usd field."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/metrics')
            data = await resp.json()
            assert 'total_cost_usd' in data

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_total_duration(self, app):
        """/api/metrics must include total_duration_seconds field."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/metrics')
            data = await resp.json()
            assert 'total_duration_seconds' in data
