"""
Tests for AI-151 (Pause Agent Control) + AI-152 (Resume Agent Control)

Verifies:
- CSS: .agent-control-btn, .pause-btn, .resume-btn, hover states, agent-item positioning
- State: pausedAgents defined, window-exposed, is a Set, starts empty
- isAgentPaused() function: exists, window-exposed, correct return values
- pauseAgent() function: exists, window-exposed, adds to pausedAgents, updates status,
  calls renderAgents, inserts system message
- resumeAgent() function: exists, window-exposed, removes from pausedAgents, sets idle,
  re-renders, inserts system message
- addSystemMessage() function: exists, window-exposed, delegates to addMessage
- Agent rendering: pause button for running, resume for paused, none for idle/error,
  data-agent-id attribute, correct CSS classes
- init() event delegation: agent-list listener, pauseAgent/resumeAgent wired up
"""
import pytest
import sys
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

HTML_PATH = PROJECT_ROOT / 'dashboard' / 'index.html'


def find_section(content, start_marker, size=2000):
    """Return a slice of content starting at start_marker."""
    idx = content.find(start_marker)
    if idx == -1:
        return ''
    return content[idx:idx + size]


def get_css(content):
    """Extract CSS between <style> and </style>."""
    start = content.find('<style>')
    end = content.find('</style>')
    return content[start:end] if start >= 0 and end >= 0 else content


def get_js(content):
    """Extract JS between <script> and </script>."""
    start = content.find('<script>')
    end = content.rfind('</script>')
    return content[start:end] if start >= 0 and end >= 0 else content


# ============================================================
# Test Group 1: Pause/Resume CSS (8 tests)
# ============================================================

class TestPauseResumeCSS:
    """Verify pause/resume CSS classes are correctly defined."""

    @pytest.fixture(scope='class')
    def css_content(self):
        return get_css(HTML_PATH.read_text(encoding='utf-8'))

    def test_agent_control_btn_class_defined(self, css_content):
        """.agent-control-btn CSS class must be defined."""
        assert '.agent-control-btn' in css_content

    def test_agent_control_btn_position_absolute(self, css_content):
        """.agent-control-btn must be position:absolute."""
        section = find_section(css_content, '.agent-control-btn', 400)
        assert 'position: absolute' in section or 'position:absolute' in section

    def test_pause_btn_class_defined(self, css_content):
        """.agent-control-btn.pause-btn CSS class must be defined."""
        assert '.agent-control-btn.pause-btn' in css_content

    def test_pause_btn_has_amber_color(self, css_content):
        """.pause-btn must use amber color (#f59e0b)."""
        section = find_section(css_content, '.agent-control-btn.pause-btn', 300)
        assert '#f59e0b' in section or 'f59e0b' in section

    def test_resume_btn_class_defined(self, css_content):
        """.agent-control-btn.resume-btn CSS class must be defined."""
        assert '.agent-control-btn.resume-btn' in css_content

    def test_resume_btn_has_green_color(self, css_content):
        """.resume-btn must use green color (#10b981)."""
        section = find_section(css_content, '.agent-control-btn.resume-btn', 300)
        assert '#10b981' in section or '10b981' in section

    def test_pause_btn_hover_defined(self, css_content):
        """.pause-btn:hover CSS must be defined."""
        assert '.agent-control-btn.pause-btn:hover' in css_content

    def test_resume_btn_hover_defined(self, css_content):
        """.resume-btn:hover CSS must be defined."""
        assert '.agent-control-btn.resume-btn:hover' in css_content

    def test_agent_item_position_relative(self, css_content):
        """agent-item must have position:relative for absolute button placement."""
        # Find the agent-item position:relative rule
        assert 'position: relative' in css_content or 'position:relative' in css_content

    def test_agent_control_btn_has_cursor_pointer(self, css_content):
        """.agent-control-btn must have cursor:pointer."""
        section = find_section(css_content, '.agent-control-btn', 400)
        assert 'cursor: pointer' in section or 'cursor:pointer' in section


# ============================================================
# Test Group 2: pausedAgents State (4 tests)
# ============================================================

class TestPausedAgentsState:
    """Verify pausedAgents state variable is correctly defined and exposed."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return get_js(HTML_PATH.read_text(encoding='utf-8'))

    def test_paused_agents_defined(self, js_content):
        """pausedAgents variable must be defined."""
        assert 'pausedAgents' in js_content

    def test_paused_agents_window_exposed(self, js_content):
        """pausedAgents must be exposed on window for orchestrator access."""
        assert 'window.pausedAgents' in js_content

    def test_paused_agents_is_set(self, js_content):
        """pausedAgents must be initialized as a Set."""
        assert 'window.pausedAgents = new Set()' in js_content

    def test_paused_agents_starts_empty(self, js_content):
        """pausedAgents must start as an empty Set (no pre-populated values)."""
        # The initialization must be `new Set()` with no arguments
        assert 'new Set()' in js_content


# ============================================================
# Test Group 3: isAgentPaused Function (4 tests)
# ============================================================

class TestIsAgentPausedFunction:
    """Verify isAgentPaused() function is correctly implemented."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return get_js(HTML_PATH.read_text(encoding='utf-8'))

    def test_is_agent_paused_function_exists(self, js_content):
        """isAgentPaused function must be defined."""
        assert 'function isAgentPaused' in js_content

    def test_is_agent_paused_window_exposed(self, js_content):
        """isAgentPaused must be exposed on window."""
        assert 'window.isAgentPaused' in js_content

    def test_is_agent_paused_checks_set(self, js_content):
        """isAgentPaused must check the pausedAgents Set using .has()."""
        section = find_section(js_content, 'function isAgentPaused', 200)
        assert '.has(' in section

    def test_is_agent_paused_takes_agent_id_param(self, js_content):
        """isAgentPaused must accept an agentId parameter."""
        assert 'function isAgentPaused(agentId)' in js_content


# ============================================================
# Test Group 4: pauseAgent Function (8 tests)
# ============================================================

class TestPauseAgentFunction:
    """Verify pauseAgent() function is correctly implemented (AI-151)."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return get_js(HTML_PATH.read_text(encoding='utf-8'))

    @pytest.fixture(scope='class')
    def fn_section(self, js_content):
        return find_section(js_content, 'function pauseAgent', 600)

    def test_pause_agent_function_exists(self, js_content):
        """pauseAgent function must be defined."""
        assert 'function pauseAgent' in js_content

    def test_pause_agent_window_exposed(self, js_content):
        """pauseAgent must be exposed on window."""
        assert 'window.pauseAgent' in js_content

    def test_pause_agent_adds_to_paused_set(self, fn_section):
        """pauseAgent must add the agentId to window.pausedAgents."""
        assert 'pausedAgents.add(' in fn_section

    def test_pause_agent_updates_status_to_paused(self, fn_section):
        """pauseAgent must set agent.status to 'paused'."""
        assert "'paused'" in fn_section or '"paused"' in fn_section

    def test_pause_agent_calls_render_agents(self, fn_section):
        """pauseAgent must call renderAgents() to refresh the UI."""
        assert 'renderAgents()' in fn_section

    def test_pause_agent_adds_system_message(self, fn_section):
        """pauseAgent must insert a system message about the pause."""
        assert 'addSystemMessage' in fn_section or 'addMessage' in fn_section

    def test_pause_agent_message_contains_paused_text(self, fn_section):
        """pauseAgent system message must contain 'paused by user'."""
        assert 'paused by user' in fn_section

    def test_pause_agent_takes_agent_id_param(self, js_content):
        """pauseAgent must accept an agentId parameter."""
        assert 'function pauseAgent(agentId)' in js_content


# ============================================================
# Test Group 5: resumeAgent Function (8 tests)
# ============================================================

class TestResumeAgentFunction:
    """Verify resumeAgent() function is correctly implemented (AI-152)."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return get_js(HTML_PATH.read_text(encoding='utf-8'))

    @pytest.fixture(scope='class')
    def fn_section(self, js_content):
        return find_section(js_content, 'function resumeAgent', 600)

    def test_resume_agent_function_exists(self, js_content):
        """resumeAgent function must be defined."""
        assert 'function resumeAgent' in js_content

    def test_resume_agent_window_exposed(self, js_content):
        """resumeAgent must be exposed on window."""
        assert 'window.resumeAgent' in js_content

    def test_resume_agent_removes_from_paused_set(self, fn_section):
        """resumeAgent must remove the agentId from window.pausedAgents."""
        assert 'pausedAgents.delete(' in fn_section

    def test_resume_agent_updates_status_to_idle(self, fn_section):
        """resumeAgent must set agent.status to 'idle'."""
        assert "'idle'" in fn_section or '"idle"' in fn_section

    def test_resume_agent_calls_render_agents(self, fn_section):
        """resumeAgent must call renderAgents() to refresh the UI."""
        assert 'renderAgents()' in fn_section

    def test_resume_agent_adds_system_message(self, fn_section):
        """resumeAgent must insert a system message about the resume."""
        assert 'addSystemMessage' in fn_section or 'addMessage' in fn_section

    def test_resume_agent_message_contains_resumed_text(self, fn_section):
        """resumeAgent system message must contain 'resumed by user'."""
        assert 'resumed by user' in fn_section

    def test_resume_agent_takes_agent_id_param(self, js_content):
        """resumeAgent must accept an agentId parameter."""
        assert 'function resumeAgent(agentId)' in js_content


# ============================================================
# Test Group 6: addSystemMessage Function (5 tests)
# ============================================================

class TestAddSystemMessageFunction:
    """Verify addSystemMessage() helper function is correctly implemented."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return get_js(HTML_PATH.read_text(encoding='utf-8'))

    @pytest.fixture(scope='class')
    def fn_section(self, js_content):
        return find_section(js_content, 'function addSystemMessage', 300)

    def test_add_system_message_function_exists(self, js_content):
        """addSystemMessage function must be defined."""
        assert 'function addSystemMessage' in js_content

    def test_add_system_message_window_exposed(self, js_content):
        """addSystemMessage must be exposed on window."""
        assert 'window.addSystemMessage' in js_content

    def test_add_system_message_takes_text_param(self, js_content):
        """addSystemMessage must accept a text parameter."""
        assert 'function addSystemMessage(text)' in js_content

    def test_add_system_message_calls_add_message(self, fn_section):
        """addSystemMessage must delegate to addMessage()."""
        assert 'addMessage(' in fn_section

    def test_add_system_message_uses_system_role(self, fn_section):
        """addSystemMessage must use 'system' role when calling addMessage."""
        assert "'system'" in fn_section or '"system"' in fn_section


# ============================================================
# Test Group 7: Agent Rendering with Controls (8 tests)
# ============================================================

class TestAgentRenderingWithControls:
    """Verify renderAgents() correctly inserts pause/resume buttons."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return get_js(HTML_PATH.read_text(encoding='utf-8'))

    @pytest.fixture(scope='class')
    def render_section(self, js_content):
        return find_section(js_content, 'window.renderAgents', 5500)

    def test_render_agents_has_control_btn_logic(self, render_section):
        """renderAgents must generate .agent-control-btn HTML."""
        assert 'agent-control-btn' in render_section

    def test_render_agents_pause_btn_for_running(self, render_section):
        """renderAgents must produce pause-btn for running agents."""
        assert 'pause-btn' in render_section

    def test_render_agents_resume_btn_for_paused(self, render_section):
        """renderAgents must produce resume-btn for paused agents."""
        assert 'resume-btn' in render_section

    def test_render_agents_checks_running_status(self, render_section):
        """renderAgents control logic must check for 'running' status."""
        assert "'running'" in render_section or '"running"' in render_section

    def test_render_agents_checks_paused_status(self, render_section):
        """renderAgents control logic must check for 'paused' status."""
        assert "'paused'" in render_section or '"paused"' in render_section

    def test_render_agents_data_agent_id_attribute(self, render_section):
        """Pause/resume buttons must have data-agent-id attribute."""
        assert 'data-agent-id=' in render_section

    def test_render_agents_pause_btn_title(self, render_section):
        """Pause button must have descriptive title attribute."""
        assert 'Pause' in render_section

    def test_render_agents_resume_btn_title(self, render_section):
        """Resume button must have descriptive title attribute."""
        assert 'Resume' in render_section


# ============================================================
# Test Group 8: Pause/Resume Wiring in init() (7 tests)
# ============================================================

class TestPauseResumeInInit:
    """Verify init() wires up pause/resume event delegation correctly."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return get_js(HTML_PATH.read_text(encoding='utf-8'))

    @pytest.fixture(scope='class')
    def init_section(self, js_content):
        return find_section(js_content, 'function init()', 5000)

    def test_init_has_agent_list_control_listener(self, init_section):
        """init() must add a click listener to agent-list for control buttons."""
        assert 'agent-list' in init_section

    def test_init_uses_closest_for_delegation(self, init_section):
        """init() pause/resume listener must use closest() for event delegation."""
        assert '.closest(' in init_section

    def test_init_checks_pause_btn_class(self, init_section):
        """init() must check for pause-btn class to dispatch pauseAgent."""
        assert 'pause-btn' in init_section

    def test_init_checks_resume_btn_class(self, init_section):
        """init() must check for resume-btn class to dispatch resumeAgent."""
        assert 'resume-btn' in init_section

    def test_init_calls_pause_agent(self, init_section):
        """init() event delegation must call pauseAgent()."""
        assert 'pauseAgent(' in init_section

    def test_init_calls_resume_agent(self, init_section):
        """init() event delegation must call resumeAgent()."""
        assert 'resumeAgent(' in init_section

    def test_paused_agents_initialized_before_init(self, js_content):
        """pausedAgents Set must be defined before init() is called."""
        paused_idx = js_content.find('window.pausedAgents = new Set()')
        init_idx = js_content.find('function init()')
        assert paused_idx >= 0, 'window.pausedAgents not found'
        assert init_idx >= 0, 'function init() not found'
        assert paused_idx < init_idx, 'pausedAgents must be defined before init()'


# ============================================================
# Test Group 9: HTML Integration (5 tests)
# ============================================================

class TestHTMLIntegration:
    """Verify the HTML file integrates the pause/resume feature correctly."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return HTML_PATH.read_text(encoding='utf-8')

    def test_pause_resume_section_comment_present(self, html_content):
        """HTML must contain the AI-151/AI-152 section comment."""
        assert 'AI-151' in html_content and 'AI-152' in html_content

    def test_agent_list_id_present(self, html_content):
        """agent-list element must exist for event delegation."""
        assert 'id="agent-list"' in html_content

    def test_window_pause_agent_assignment(self, html_content):
        """window.pauseAgent assignment must be present."""
        assert 'window.pauseAgent = pauseAgent' in html_content

    def test_window_resume_agent_assignment(self, html_content):
        """window.resumeAgent assignment must be present."""
        assert 'window.resumeAgent = resumeAgent' in html_content

    def test_window_is_agent_paused_assignment(self, html_content):
        """window.isAgentPaused assignment must be present."""
        assert 'window.isAgentPaused = isAgentPaused' in html_content

    def test_window_add_system_message_assignment(self, html_content):
        """window.addSystemMessage assignment must be present."""
        assert 'window.addSystemMessage = addSystemMessage' in html_content
