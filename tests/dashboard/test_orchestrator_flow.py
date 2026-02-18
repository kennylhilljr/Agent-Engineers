"""
Tests for AI-146: REQ-MONITOR-004: Implement Orchestrator Flow Visualization

Verifies:
- HTML section for orchestrator flow is present
- CSS for flow visualization (orchestrator-flow, flow-root-node, flow-tree, flow-node, etc.)
- CSS for ProgressRing (progress-ring-svg, progress-ring-fill, etc.)
- mockOrchestratorFlow data structure with ticket + nodes
- ProgressRing() component function
- FlowNode() component function
- renderOrchestratorFlow() function
- loadOrchestratorFlow() function
- /api/orchestrator/flow endpoint in dashboard_server.py
- init() calls renderOrchestratorFlow() and loadOrchestratorFlow()
"""
import pytest
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Test Group 1: HTML Structure
# ============================================================

class TestOrchestratorFlowHTML:
    """Verify orchestrator flow section HTML structure."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_orchestrator_flow_section_exists(self, html_content):
        """orchestrator-flow-section element must be present."""
        assert 'id="orchestrator-flow-section"' in html_content

    def test_orchestrator_flow_container_exists(self, html_content):
        """orchestrator-flow container div must be present."""
        assert 'id="orchestrator-flow"' in html_content

    def test_orchestrator_flow_section_has_title(self, html_content):
        """Section must have 'Orchestrator Flow' heading."""
        assert 'Orchestrator Flow' in html_content

    def test_orchestrator_flow_panel_section_class(self, html_content):
        """Orchestrator flow must use panel-section class."""
        assert 'id="orchestrator-flow-section"' in html_content
        # Check the section uses panel-section class
        idx = html_content.index('id="orchestrator-flow-section"')
        nearby = html_content[max(0, idx - 50):idx + 100]
        assert 'panel-section' in nearby


# ============================================================
# Test Group 2: CSS Classes for Flow Visualization
# ============================================================

class TestOrchestratorFlowCSS:
    """Verify CSS classes for the orchestrator flow visualization."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_orchestrator_flow_css(self, html_content):
        """.orchestrator-flow CSS must be defined."""
        assert '.orchestrator-flow' in html_content

    def test_flow_root_node_css(self, html_content):
        """.flow-root-node CSS must be defined."""
        assert '.flow-root-node' in html_content

    def test_flow_tree_css(self, html_content):
        """.flow-tree CSS must be defined."""
        assert '.flow-tree' in html_content

    def test_flow_node_css(self, html_content):
        """.flow-node CSS must be defined."""
        assert '.flow-node' in html_content

    def test_flow_node_active_css(self, html_content):
        """.flow-node.active CSS must be defined."""
        assert '.flow-node.active' in html_content

    def test_flow_node_done_css(self, html_content):
        """.flow-node.done CSS must be defined."""
        assert '.flow-node.done' in html_content

    def test_flow_node_pending_css(self, html_content):
        """.flow-node.pending CSS must be defined."""
        assert '.flow-node.pending' in html_content

    def test_flow_connector_css(self, html_content):
        """.flow-connector CSS must be defined."""
        assert '.flow-connector' in html_content

    def test_flow_node_agent_css(self, html_content):
        """.flow-node-agent CSS must be defined."""
        assert '.flow-node-agent' in html_content

    def test_flow_node_task_css(self, html_content):
        """.flow-node-task CSS must be defined."""
        assert '.flow-node-task' in html_content

    def test_flow_node_timing_css(self, html_content):
        """.flow-node-timing CSS must be defined."""
        assert '.flow-node-timing' in html_content

    def test_flow_node_status_label_css(self, html_content):
        """.flow-node-status-label CSS must be defined."""
        assert '.flow-node-status-label' in html_content

    def test_flow_empty_css(self, html_content):
        """.flow-empty CSS must be defined."""
        assert '.flow-empty' in html_content


# ============================================================
# Test Group 3: ProgressRing CSS
# ============================================================

class TestProgressRingCSS:
    """Verify CSS for ProgressRing SVG component."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_progress_ring_wrapper_css(self, html_content):
        """.progress-ring-wrapper CSS must be defined."""
        assert '.progress-ring-wrapper' in html_content

    def test_progress_ring_svg_css(self, html_content):
        """.progress-ring-svg CSS must be defined."""
        assert '.progress-ring-svg' in html_content

    def test_progress_ring_track_css(self, html_content):
        """.progress-ring-track CSS must be defined."""
        assert '.progress-ring-track' in html_content

    def test_progress_ring_fill_css(self, html_content):
        """.progress-ring-fill CSS must be defined."""
        assert '.progress-ring-fill' in html_content

    def test_progress_ring_fill_done_css(self, html_content):
        """.progress-ring-fill.done CSS must be defined."""
        assert '.progress-ring-fill.done' in html_content

    def test_progress_ring_fill_active_css(self, html_content):
        """.progress-ring-fill.active CSS must be defined."""
        assert '.progress-ring-fill.active' in html_content

    def test_progress_ring_fill_pending_css(self, html_content):
        """.progress-ring-fill.pending CSS must be defined."""
        assert '.progress-ring-fill.pending' in html_content

    def test_progress_ring_text_css(self, html_content):
        """.progress-ring-text CSS must be defined."""
        assert '.progress-ring-text' in html_content

    def test_ring_pulse_animation_defined(self, html_content):
        """ring-pulse animation must be defined for active nodes."""
        assert 'ring-pulse' in html_content


# ============================================================
# Test Group 4: mockOrchestratorFlow Data
# ============================================================

class TestMockOrchestratorFlow:
    """Verify mockOrchestratorFlow data structure."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_mock_orchestrator_flow_defined(self, html_content):
        """mockOrchestratorFlow must be defined."""
        assert 'mockOrchestratorFlow' in html_content

    def test_mock_orchestrator_flow_exposed_on_window(self, html_content):
        """mockOrchestratorFlow must be exposed on window."""
        assert 'window.mockOrchestratorFlow' in html_content

    def test_mock_flow_has_ticket_field(self, html_content):
        """mockOrchestratorFlow must have ticket field."""
        idx = html_content.index('mockOrchestratorFlow')
        section = html_content[idx:idx + 1000]
        assert 'ticket' in section

    def test_mock_flow_has_nodes_array(self, html_content):
        """mockOrchestratorFlow must have nodes array."""
        idx = html_content.index('mockOrchestratorFlow')
        section = html_content[idx:idx + 1000]
        assert 'nodes' in section

    def test_mock_flow_nodes_have_agent_field(self, html_content):
        """Flow nodes must have agent field."""
        idx = html_content.index('mockOrchestratorFlow')
        section = html_content[idx:idx + 1000]
        assert 'agent' in section

    def test_mock_flow_nodes_have_task_field(self, html_content):
        """Flow nodes must have task field."""
        idx = html_content.index('mockOrchestratorFlow')
        section = html_content[idx:idx + 1000]
        assert 'task' in section

    def test_mock_flow_nodes_have_status_field(self, html_content):
        """Flow nodes must have status field."""
        idx = html_content.index('mockOrchestratorFlow')
        section = html_content[idx:idx + 1000]
        assert 'status' in section

    def test_mock_flow_nodes_have_elapsed_s_field(self, html_content):
        """Flow nodes must have elapsed_s field."""
        idx = html_content.index('mockOrchestratorFlow')
        section = html_content[idx:idx + 1000]
        assert 'elapsed_s' in section

    def test_mock_flow_has_done_status(self, html_content):
        """Flow must include nodes with 'done' status."""
        idx = html_content.index('mockOrchestratorFlow')
        section = html_content[idx:idx + 1000]
        assert "'done'" in section or '"done"' in section

    def test_mock_flow_has_active_status(self, html_content):
        """Flow must include nodes with 'active' status."""
        idx = html_content.index('mockOrchestratorFlow')
        section = html_content[idx:idx + 1000]
        assert "'active'" in section or '"active"' in section


# ============================================================
# Test Group 5: ProgressRing Component Function
# ============================================================

class TestProgressRingFunction:
    """Verify ProgressRing() component function."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_progress_ring_function_defined(self, html_content):
        """ProgressRing function must be defined."""
        assert 'function ProgressRing' in html_content

    def test_progress_ring_exposed_on_window(self, html_content):
        """ProgressRing must be exposed on window."""
        assert 'window.ProgressRing' in html_content

    def test_progress_ring_returns_svg(self, html_content):
        """ProgressRing must return SVG element."""
        idx = html_content.index('function ProgressRing')
        section = html_content[idx:idx + 800]
        assert '<svg' in section or 'svg' in section

    def test_progress_ring_uses_stroke_dasharray(self, html_content):
        """ProgressRing must use stroke-dasharray for progress fill."""
        idx = html_content.index('function ProgressRing')
        section = html_content[idx:idx + 800]
        assert 'stroke-dasharray' in section

    def test_progress_ring_uses_stroke_dashoffset(self, html_content):
        """ProgressRing must use stroke-dashoffset for progress position."""
        idx = html_content.index('function ProgressRing')
        section = html_content[idx:idx + 800]
        assert 'stroke-dashoffset' in section

    def test_progress_ring_handles_done_status(self, html_content):
        """ProgressRing must handle 'done' status."""
        idx = html_content.index('function ProgressRing')
        section = html_content[idx:idx + 800]
        assert 'done' in section

    def test_progress_ring_handles_active_status(self, html_content):
        """ProgressRing must handle 'active' status."""
        idx = html_content.index('function ProgressRing')
        section = html_content[idx:idx + 800]
        assert 'active' in section

    def test_progress_ring_handles_pending_status(self, html_content):
        """ProgressRing must handle 'pending' status."""
        idx = html_content.index('function ProgressRing')
        section = html_content[idx:idx + 800]
        assert 'pending' in section


# ============================================================
# Test Group 6: FlowNode Component Function
# ============================================================

class TestFlowNodeFunction:
    """Verify FlowNode() component function."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_flow_node_function_defined(self, html_content):
        """FlowNode function must be defined."""
        assert 'function FlowNode' in html_content

    def test_flow_node_exposed_on_window(self, html_content):
        """FlowNode must be exposed on window."""
        assert 'window.FlowNode' in html_content

    def test_flow_node_uses_flow_node_css_class(self, html_content):
        """FlowNode must use .flow-node CSS class."""
        idx = html_content.index('function FlowNode')
        section = html_content[idx:idx + 1000]
        assert 'flow-node' in section

    def test_flow_node_uses_progress_ring(self, html_content):
        """FlowNode must call ProgressRing() for status indicator."""
        idx = html_content.index('function FlowNode')
        section = html_content[idx:idx + 1800]
        assert 'ProgressRing' in section

    def test_flow_node_shows_agent_name(self, html_content):
        """FlowNode must display agent name."""
        idx = html_content.index('function FlowNode')
        section = html_content[idx:idx + 1800]
        assert 'flow-node-agent' in section

    def test_flow_node_shows_task_description(self, html_content):
        """FlowNode must display task description."""
        idx = html_content.index('function FlowNode')
        section = html_content[idx:idx + 1800]
        assert 'flow-node-task' in section

    def test_flow_node_shows_timing(self, html_content):
        """FlowNode must display timing (elapsed time or status label)."""
        idx = html_content.index('function FlowNode')
        section = html_content[idx:idx + 1800]
        assert 'flow-node-timing' in section or 'flow-node-status-label' in section

    def test_flow_node_uses_last_connector(self, html_content):
        """FlowNode must use └─► for last node."""
        idx = html_content.index('function FlowNode')
        section = html_content[idx:idx + 1800]
        assert '└─►' in section or 'isLast' in section

    def test_flow_node_uses_branch_connector(self, html_content):
        """FlowNode must use ├─► for non-last nodes."""
        idx = html_content.index('function FlowNode')
        section = html_content[idx:idx + 1800]
        assert '├─►' in section

    def test_flow_node_uses_data_flow_agent(self, html_content):
        """FlowNode must include data-flow-agent attribute."""
        idx = html_content.index('function FlowNode')
        section = html_content[idx:idx + 1800]
        assert 'data-flow-agent' in section

    def test_flow_node_uses_data_flow_status(self, html_content):
        """FlowNode must include data-flow-status attribute."""
        idx = html_content.index('function FlowNode')
        section = html_content[idx:idx + 1800]
        assert 'data-flow-status' in section


# ============================================================
# Test Group 7: renderOrchestratorFlow() Function
# ============================================================

class TestRenderOrchestratorFlow:
    """Verify renderOrchestratorFlow() function."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_render_orchestrator_flow_defined(self, html_content):
        """renderOrchestratorFlow function must be defined."""
        assert 'function renderOrchestratorFlow' in html_content

    def test_render_orchestrator_flow_exposed_on_window(self, html_content):
        """renderOrchestratorFlow must be exposed on window."""
        assert 'window.renderOrchestratorFlow' in html_content

    def test_render_flow_uses_orchestrator_flow_container(self, html_content):
        """renderOrchestratorFlow must target #orchestrator-flow element."""
        idx = html_content.index('function renderOrchestratorFlow')
        section = html_content[idx:idx + 2000]
        assert 'orchestrator-flow' in section

    def test_render_flow_shows_root_node(self, html_content):
        """renderOrchestratorFlow must show root Orchestrator node."""
        idx = html_content.index('function renderOrchestratorFlow')
        section = html_content[idx:idx + 2000]
        assert 'Orchestrator' in section or 'flow-root-node' in section

    def test_render_flow_uses_flow_node_component(self, html_content):
        """renderOrchestratorFlow must call FlowNode() component."""
        idx = html_content.index('function renderOrchestratorFlow')
        section = html_content[idx:idx + 2000]
        assert 'FlowNode' in section

    def test_render_flow_uses_flow_tree(self, html_content):
        """renderOrchestratorFlow must use flow-tree wrapper."""
        idx = html_content.index('function renderOrchestratorFlow')
        section = html_content[idx:idx + 2000]
        assert 'flow-tree' in section

    def test_render_flow_shows_empty_state(self, html_content):
        """renderOrchestratorFlow must show empty state when no nodes."""
        idx = html_content.index('function renderOrchestratorFlow')
        section = html_content[idx:idx + 2000]
        assert 'No active pipeline' in section or 'flow-empty' in section

    def test_render_flow_marks_last_node(self, html_content):
        """renderOrchestratorFlow must pass isLast=true for last node."""
        idx = html_content.index('function renderOrchestratorFlow')
        section = html_content[idx:idx + 2000]
        assert 'nodes.length - 1' in section or 'isLast' in section

    def test_render_flow_uses_mock_or_current(self, html_content):
        """renderOrchestratorFlow must use currentOrchestratorFlow or mockOrchestratorFlow."""
        idx = html_content.index('function renderOrchestratorFlow')
        section = html_content[idx:idx + 2000]
        assert 'currentOrchestratorFlow' in section or 'mockOrchestratorFlow' in section


# ============================================================
# Test Group 8: loadOrchestratorFlow() Function
# ============================================================

class TestLoadOrchestratorFlow:
    """Verify loadOrchestratorFlow() function."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_load_orchestrator_flow_defined(self, html_content):
        """loadOrchestratorFlow function must be defined."""
        assert 'function loadOrchestratorFlow' in html_content

    def test_load_orchestrator_flow_exposed_on_window(self, html_content):
        """loadOrchestratorFlow must be exposed on window."""
        assert 'window.loadOrchestratorFlow' in html_content

    def test_load_flow_fetches_api_endpoint(self, html_content):
        """loadOrchestratorFlow must fetch /api/orchestrator/flow."""
        idx = html_content.index('function loadOrchestratorFlow')
        section = html_content[idx:idx + 500]
        assert '/api/orchestrator/flow' in section

    def test_load_flow_calls_render_on_success(self, html_content):
        """loadOrchestratorFlow must call renderOrchestratorFlow() on success."""
        idx = html_content.index('function loadOrchestratorFlow')
        section = html_content[idx:idx + 500]
        assert 'renderOrchestratorFlow' in section

    def test_load_flow_handles_error_gracefully(self, html_content):
        """loadOrchestratorFlow must handle fetch errors gracefully."""
        idx = html_content.index('function loadOrchestratorFlow')
        section = html_content[idx:idx + 500]
        assert 'catch' in section

    def test_load_flow_called_in_init(self, html_content):
        """loadOrchestratorFlow must be called in init()."""
        idx = html_content.index('function init()')
        section = html_content[idx:idx + 3000]
        assert 'loadOrchestratorFlow' in section


# ============================================================
# Test Group 9: renderOrchestratorFlow called in init()
# ============================================================

class TestInitCallsRenderFlow:
    """Verify init() calls renderOrchestratorFlow()."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_render_flow_called_in_init(self, html_content):
        """init() must call renderOrchestratorFlow()."""
        idx = html_content.index('function init()')
        section = html_content[idx:idx + 3000]
        assert 'renderOrchestratorFlow' in section


# ============================================================
# Test Group 10: /api/orchestrator/flow Endpoint
# ============================================================

class TestOrchestratorFlowEndpoint:
    """Verify /api/orchestrator/flow endpoint in dashboard_server.py."""

    @pytest.fixture(scope='class')
    def server_content(self):
        return (PROJECT_ROOT / 'scripts' / 'dashboard_server.py').read_text(encoding='utf-8')

    def test_orchestrator_flow_route_registered(self, server_content):
        """/api/orchestrator/flow route must be registered."""
        assert '/api/orchestrator/flow' in server_content

    def test_handle_orchestrator_flow_method_exists(self, server_content):
        """handle_orchestrator_flow method must be defined."""
        assert 'async def handle_orchestrator_flow' in server_content

    def test_endpoint_returns_ticket_field(self, server_content):
        """Endpoint must include 'ticket' field in response."""
        idx = server_content.index('async def handle_orchestrator_flow')
        section = server_content[idx:idx + 2000]
        assert 'ticket' in section

    def test_endpoint_returns_nodes_field(self, server_content):
        """Endpoint must include 'nodes' field in response."""
        idx = server_content.index('async def handle_orchestrator_flow')
        section = server_content[idx:idx + 2000]
        assert 'nodes' in section

    def test_endpoint_returns_timestamp_field(self, server_content):
        """Endpoint must include 'timestamp' field."""
        idx = server_content.index('async def handle_orchestrator_flow')
        section = server_content[idx:idx + 2000]
        assert 'timestamp' in section

    def test_endpoint_has_fallback_nodes(self, server_content):
        """Endpoint must have fallback mock nodes when no real data."""
        idx = server_content.index('async def handle_orchestrator_flow')
        section = server_content[idx:idx + 2000]
        assert 'pending' in section or 'done' in section

    def test_endpoint_handles_exceptions(self, server_content):
        """Endpoint must have try/except error handling."""
        idx = server_content.index('async def handle_orchestrator_flow')
        section = server_content[idx:idx + 2000]
        assert 'except' in section


# ============================================================
# Test Group 11: Live endpoint test
# ============================================================

class TestOrchestratorFlowEndpointLive:
    """Live endpoint tests for /api/orchestrator/flow."""

    @pytest.fixture
    def app(self):
        sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
        from dashboard_server import DashboardServer
        server = DashboardServer(project_dir=str(PROJECT_ROOT), project_name='test')
        return server.app

    @pytest.mark.asyncio
    async def test_endpoint_returns_200(self, app):
        """/api/orchestrator/flow must return 200 OK."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/orchestrator/flow')
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_endpoint_returns_valid_json(self, app):
        """/api/orchestrator/flow must return valid JSON."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/orchestrator/flow')
            data = await resp.json()
            assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_endpoint_has_nodes_array(self, app):
        """Response must include 'nodes' array."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/orchestrator/flow')
            data = await resp.json()
            assert 'nodes' in data
            assert isinstance(data['nodes'], list)

    @pytest.mark.asyncio
    async def test_endpoint_has_ticket_field(self, app):
        """Response must include 'ticket' field."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/orchestrator/flow')
            data = await resp.json()
            assert 'ticket' in data

    @pytest.mark.asyncio
    async def test_endpoint_nodes_have_required_fields(self, app):
        """Each node in response must have agent, task, status fields."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/orchestrator/flow')
            data = await resp.json()
            for node in data['nodes']:
                assert 'agent' in node, f"Node missing 'agent' field: {node}"
                assert 'task' in node, f"Node missing 'task' field: {node}"
                assert 'status' in node, f"Node missing 'status' field: {node}"
