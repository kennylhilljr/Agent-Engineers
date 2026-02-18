"""
Tests for AI-154: REQ-CONTROL-004: Implement View Current Requirements

Verifies:
- HTML structure: requirements-overlay, requirements-modal, modal header/body
- Accessibility: role=dialog, aria-modal, aria-labelledby, aria-label on close btn
- CSS: .requirements-overlay, .requirements-overlay.open, .requirements-modal,
       .requirements-modal-header, .requirements-source-label, .requirements-source-text,
       .requirements-toggle-btn, .requirements-close-btn
- mockRequirements data: defined, window-exposed, has ticket entries with sources
- openRequirementsView function: defined, window-exposed, shows overlay
- closeRequirementsView function: defined, window-exposed, removes open class
- renderRequirementsContent function: defined, window-exposed, builds HTML
- init() wires up close-btn listener and overlay backdrop listener
- handleAgentClick routes .agent-active-task clicks to openRequirementsView
"""
import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def find_section(content, start_marker, size=2000):
    """Find a section of content starting at start_marker with given size."""
    idx = content.find(start_marker)
    if idx == -1:
        return ''
    return content[idx:idx + size]


# ============================================================
# Test Group 1: Requirements Overlay HTML Structure
# ============================================================

class TestRequirementsOverlayHTML:
    """Verify the requirements overlay HTML elements are present."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_requirements_overlay_id_exists(self, html_content):
        """requirements-overlay element must exist with correct id."""
        assert 'id="requirements-overlay"' in html_content

    def test_requirements_modal_id_exists(self, html_content):
        """requirements-modal element must exist with correct id."""
        assert 'id="requirements-modal"' in html_content

    def test_requirements_heading_id_exists(self, html_content):
        """requirements-heading id must exist for aria-labelledby reference."""
        assert 'id="requirements-heading"' in html_content

    def test_requirements_modal_title_exists(self, html_content):
        """requirements-modal-title class must exist with heading text."""
        assert 'requirements-modal-title' in html_content

    def test_requirements_close_btn_id_exists(self, html_content):
        """requirements-close-btn element must exist."""
        assert 'id="requirements-close-btn"' in html_content

    def test_requirements_modal_body_id_exists(self, html_content):
        """requirements-modal-body element must exist for dynamic content."""
        assert 'id="requirements-modal-body"' in html_content

    def test_requirements_overlay_role_dialog(self, html_content):
        """requirements-overlay must have role=dialog for accessibility."""
        overlay_section = find_section(html_content, 'id="requirements-overlay"', 400)
        assert 'role="dialog"' in overlay_section

    def test_requirements_overlay_aria_modal(self, html_content):
        """requirements-overlay must have aria-modal=true."""
        overlay_section = find_section(html_content, 'id="requirements-overlay"', 400)
        assert 'aria-modal="true"' in overlay_section

    def test_requirements_overlay_aria_labelledby(self, html_content):
        """requirements-overlay must have aria-labelledby pointing to heading."""
        overlay_section = find_section(html_content, 'id="requirements-overlay"', 400)
        assert 'aria-labelledby="requirements-heading"' in overlay_section

    def test_requirements_close_btn_aria_label(self, html_content):
        """Close button must have aria-label for screen readers."""
        assert 'aria-label="Close requirements view"' in html_content


# ============================================================
# Test Group 2: Requirements CSS Classes
# ============================================================

class TestRequirementsCSS:
    """Verify the requirements-related CSS classes are defined."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_requirements_overlay_css_class(self, html_content):
        """.requirements-overlay CSS class must be defined."""
        assert '.requirements-overlay {' in html_content or '.requirements-overlay{' in html_content

    def test_requirements_overlay_open_css_class(self, html_content):
        """.requirements-overlay.open must show the element (display: flex)."""
        assert '.requirements-overlay.open' in html_content

    def test_requirements_modal_css_class(self, html_content):
        """.requirements-modal CSS class must be defined."""
        assert '.requirements-modal {' in html_content or '.requirements-modal{' in html_content

    def test_requirements_modal_header_css_class(self, html_content):
        """.requirements-modal-header CSS class must be defined."""
        assert '.requirements-modal-header' in html_content

    def test_requirements_source_label_css_class(self, html_content):
        """.requirements-source-label CSS class must be defined."""
        assert '.requirements-source-label' in html_content

    def test_requirements_source_text_css_class(self, html_content):
        """.requirements-source-text CSS class must be defined."""
        assert '.requirements-source-text' in html_content

    def test_requirements_toggle_btn_css_class(self, html_content):
        """.requirements-toggle-btn CSS class must be defined."""
        assert '.requirements-toggle-btn' in html_content

    def test_requirements_close_btn_css_class(self, html_content):
        """.requirements-close-btn CSS class must be defined."""
        assert '.requirements-close-btn' in html_content

    def test_requirements_panel_css_class(self, html_content):
        """.requirements-panel CSS class must be defined."""
        assert '.requirements-panel' in html_content

    def test_requirements_panel_open_css_class(self, html_content):
        """.requirements-panel.open must be defined."""
        assert '.requirements-panel.open' in html_content

    def test_req_panel_ticket_title_css_class(self, html_content):
        """.req-panel-ticket-title CSS class must be defined."""
        assert '.req-panel-ticket-title' in html_content

    def test_requirements_source_css_class(self, html_content):
        """.requirements-source CSS class must be defined."""
        assert '.requirements-source' in html_content


# ============================================================
# Test Group 3: Mock Requirements Data
# ============================================================

class TestMockRequirements:
    """Verify mockRequirements data is defined and window-exposed."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_mock_requirements_const_defined(self, html_content):
        """mockRequirements const must be declared in JS."""
        assert 'const mockRequirements' in html_content or 'var mockRequirements' in html_content

    def test_mock_requirements_window_exposed(self, html_content):
        """mockRequirements must be exposed on window for testing."""
        assert 'window.mockRequirements' in html_content

    def test_mock_requirements_is_object(self, html_content):
        """mockRequirements must be initialized as an object literal."""
        mock_section = find_section(html_content, 'mockRequirements =', 200)
        assert '{' in mock_section

    def test_mock_requirements_has_ticket_entries(self, html_content):
        """mockRequirements must contain at least one ticket key entry."""
        assert "'AI-" in html_content or '"AI-' in html_content

    def test_mock_requirements_entries_have_sources_array(self, html_content):
        """mockRequirements entries must have sources arrays."""
        assert 'sources:' in html_content or "sources =" in html_content

    def test_mock_requirements_sources_have_label_field(self, html_content):
        """Sources must have a label field."""
        sources_section = find_section(html_content, 'sources:', 500)
        assert 'label:' in sources_section

    def test_mock_requirements_sources_have_text_field(self, html_content):
        """Sources must have a text field."""
        sources_section = find_section(html_content, 'sources:', 500)
        assert 'text:' in sources_section

    def test_mock_requirements_has_linear_issue_source(self, html_content):
        """Requirements sources must include a Linear Issue source."""
        assert 'Linear Issue' in html_content

    def test_mock_requirements_has_app_spec_source(self, html_content):
        """Requirements sources must include an App Spec source."""
        assert 'App Spec' in html_content

    def test_mock_requirements_has_orchestrator_source(self, html_content):
        """Requirements sources must include an Orchestrator Context source."""
        assert 'Orchestrator Context' in html_content


# ============================================================
# Test Group 4: openRequirementsView Function
# ============================================================

class TestOpenRequirementsViewFunction:
    """Verify openRequirementsView function is defined and correctly structured."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def fn_section(self, html_content):
        return find_section(html_content, 'function openRequirementsView', 1500)

    def test_open_requirements_view_function_exists(self, html_content):
        """openRequirementsView function must be defined."""
        assert 'function openRequirementsView' in html_content

    def test_open_requirements_view_window_exposed(self, html_content):
        """openRequirementsView must be exposed on window."""
        assert 'window.openRequirementsView' in html_content

    def test_open_requirements_view_takes_agent_id_param(self, fn_section):
        """openRequirementsView must accept an agentId parameter."""
        assert 'agentId' in fn_section

    def test_open_requirements_view_finds_agent_in_state(self, fn_section):
        """openRequirementsView must look up agent from state.agents."""
        assert 'state.agents' in fn_section

    def test_open_requirements_view_uses_mock_requirements(self, fn_section):
        """openRequirementsView must look up from mockRequirements."""
        assert 'mockRequirements' in fn_section

    def test_open_requirements_view_calls_render_content(self, fn_section):
        """openRequirementsView must call renderRequirementsContent."""
        assert 'renderRequirementsContent' in fn_section

    def test_open_requirements_view_adds_open_class(self, fn_section):
        """openRequirementsView must add 'open' class to the overlay."""
        assert "classList.add('open')" in fn_section or 'classList.add("open")' in fn_section

    def test_open_requirements_view_targets_overlay_element(self, fn_section):
        """openRequirementsView must target requirements-overlay element."""
        assert 'requirements-overlay' in fn_section

    def test_open_requirements_view_sets_modal_body(self, fn_section):
        """openRequirementsView must set innerHTML of requirements-modal-body."""
        assert 'requirements-modal-body' in fn_section


# ============================================================
# Test Group 5: closeRequirementsView Function
# ============================================================

class TestCloseRequirementsViewFunction:
    """Verify closeRequirementsView function is defined and correctly structured."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def fn_section(self, html_content):
        return find_section(html_content, 'function closeRequirementsView', 400)

    def test_close_requirements_view_function_exists(self, html_content):
        """closeRequirementsView function must be defined."""
        assert 'function closeRequirementsView' in html_content

    def test_close_requirements_view_window_exposed(self, html_content):
        """closeRequirementsView must be exposed on window."""
        assert 'window.closeRequirementsView' in html_content

    def test_close_requirements_view_removes_open_class(self, fn_section):
        """closeRequirementsView must remove 'open' class from overlay."""
        assert "classList.remove('open')" in fn_section or 'classList.remove("open")' in fn_section

    def test_close_requirements_view_targets_overlay_element(self, fn_section):
        """closeRequirementsView must target requirements-overlay element."""
        assert 'requirements-overlay' in fn_section


# ============================================================
# Test Group 6: renderRequirementsContent Function
# ============================================================

class TestRenderRequirementsContentFunction:
    """Verify renderRequirementsContent function is correctly structured."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def fn_section(self, html_content):
        return find_section(html_content, 'function renderRequirementsContent', 1000)

    def test_render_requirements_content_function_exists(self, html_content):
        """renderRequirementsContent function must be defined."""
        assert 'function renderRequirementsContent' in html_content

    def test_render_requirements_content_window_exposed(self, html_content):
        """renderRequirementsContent must be exposed on window."""
        assert 'window.renderRequirementsContent' in html_content

    def test_render_requirements_content_takes_ticket_param(self, fn_section):
        """renderRequirementsContent must accept a ticket parameter."""
        assert 'ticket' in fn_section

    def test_render_requirements_content_takes_sources_param(self, fn_section):
        """renderRequirementsContent must accept a sources parameter."""
        assert 'sources' in fn_section

    def test_render_requirements_content_includes_ticket_title_class(self, fn_section):
        """renderRequirementsContent must produce req-panel-ticket-title element."""
        assert 'req-panel-ticket-title' in fn_section

    def test_render_requirements_content_includes_source_label_class(self, fn_section):
        """renderRequirementsContent must produce requirements-source-label elements."""
        assert 'requirements-source-label' in fn_section

    def test_render_requirements_content_includes_source_text_class(self, fn_section):
        """renderRequirementsContent must produce requirements-source-text elements."""
        assert 'requirements-source-text' in fn_section

    def test_render_requirements_content_returns_html(self, fn_section):
        """renderRequirementsContent must return an HTML string."""
        assert 'return' in fn_section

    def test_render_requirements_content_handles_array(self, fn_section):
        """renderRequirementsContent must handle sources as an array."""
        assert 'Array.isArray' in fn_section or '.map(' in fn_section


# ============================================================
# Test Group 7: Requirements Listeners in Init
# ============================================================

class TestRequirementsInInit:
    """Verify requirements-related listeners are wired up in init()."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def init_section(self, html_content):
        return find_section(html_content, 'function init()', 8000)

    def test_requirements_close_btn_listener_in_init(self, init_section):
        """requirements-close-btn must have a click listener in init()."""
        assert 'requirements-close-btn' in init_section

    def test_requirements_close_btn_calls_close_view(self, init_section):
        """requirements-close-btn listener must call closeRequirementsView."""
        assert 'closeRequirementsView' in init_section

    def test_requirements_overlay_backdrop_listener_in_init(self, init_section):
        """requirements-overlay must have a backdrop click listener in init()."""
        assert 'requirements-overlay' in init_section

    def test_requirements_overlay_backdrop_listener_calls_close(self, init_section):
        """Backdrop click handler must call closeRequirementsView."""
        # Both the close btn and backdrop click use closeRequirementsView
        assert init_section.count('closeRequirementsView') >= 2

    def test_requirements_listeners_not_missing_from_init(self, html_content):
        """Both requirements listeners must appear after function init() starts."""
        init_idx = html_content.find('function init()')
        close_btn_idx = html_content.find("'requirements-close-btn'", init_idx)
        overlay_idx = html_content.find("'requirements-overlay'", init_idx)
        assert close_btn_idx > init_idx, "requirements-close-btn listener must be in init"
        assert overlay_idx > init_idx, "requirements-overlay listener must be in init"


# ============================================================
# Test Group 8: Agent Click Opens Requirements
# ============================================================

class TestAgentClickOpensRequirements:
    """Verify handleAgentClick routes .agent-active-task clicks to requirements view."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def handle_click_section(self, html_content):
        return find_section(html_content, 'function handleAgentClick', 1000)

    def test_handle_agent_click_function_exists(self, html_content):
        """handleAgentClick function must be defined."""
        assert 'function handleAgentClick' in html_content

    def test_handle_agent_click_checks_agent_active_task(self, handle_click_section):
        """handleAgentClick must check for .agent-active-task element."""
        assert 'agent-active-task' in handle_click_section

    def test_handle_agent_click_calls_open_requirements_view(self, handle_click_section):
        """handleAgentClick must call openRequirementsView when active task is clicked."""
        assert 'openRequirementsView' in handle_click_section

    def test_handle_agent_click_passes_agent_id(self, handle_click_section):
        """handleAgentClick must pass the agent dataset id to openRequirementsView."""
        assert 'dataset.agent' in handle_click_section or 'agentItem.dataset' in handle_click_section
