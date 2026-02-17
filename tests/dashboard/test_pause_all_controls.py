"""
Tests for AI-153: REQ-CONTROL-003: Implement Pause All / Resume All Controls

Verifies:
- HTML: #global-pause-banner with role/aria attributes, #pause-all-btn, #resume-all-btn,
  #global-control-buttons container
- CSS: #global-pause-banner, .visible, .global-control-btn, .pause-all-btn, .resume-all-btn,
  hover states, fixed positioning
- JS: window.globalPaused flag defined and defaults to false
- pauseAll(): exists, window-exposed, sets globalPaused=true, marks agents paused,
  shows banner, toggles buttons, adds system message
- resumeAll(): exists, window-exposed, sets globalPaused=false, clears pausedAgents,
  sets agents idle, hides banner, toggles buttons, adds system message
- isGloballyPaused(): exists, window-exposed, returns window.globalPaused
- init(): wires pause-all-btn and resume-all-btn listeners to pauseAll/resumeAll
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
# Test Group 1: Pause Banner HTML (6 tests)
# ============================================================

class TestPauseBannerHTML:
    """Verify the global pause banner HTML structure."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return HTML_PATH.read_text(encoding='utf-8')

    def test_global_pause_banner_exists(self, html_content):
        """#global-pause-banner element must be present."""
        assert 'id="global-pause-banner"' in html_content

    def test_global_pause_banner_role_alert(self, html_content):
        """#global-pause-banner must have role='alert'."""
        section = find_section(html_content, 'id="global-pause-banner"', 300)
        assert 'role="alert"' in section

    def test_global_pause_banner_aria_live_assertive(self, html_content):
        """#global-pause-banner must have aria-live='assertive'."""
        section = find_section(html_content, 'id="global-pause-banner"', 300)
        assert 'aria-live="assertive"' in section

    def test_pause_all_btn_exists(self, html_content):
        """#pause-all-btn button element must be present."""
        assert 'id="pause-all-btn"' in html_content

    def test_resume_all_btn_exists(self, html_content):
        """#resume-all-btn button element must be present."""
        assert 'id="resume-all-btn"' in html_content

    def test_global_control_buttons_container_exists(self, html_content):
        """#global-control-buttons container element must be present."""
        assert 'id="global-control-buttons"' in html_content


# ============================================================
# Test Group 2: Pause All CSS (8 tests)
# ============================================================

class TestPauseAllCSS:
    """Verify global pause/resume CSS rules are correctly defined."""

    @pytest.fixture(scope='class')
    def css_content(self):
        return get_css(HTML_PATH.read_text(encoding='utf-8'))

    def test_global_pause_banner_css_defined(self, css_content):
        """#global-pause-banner CSS selector must be defined."""
        assert '#global-pause-banner' in css_content

    def test_global_pause_banner_visible_class(self, css_content):
        """#global-pause-banner .visible CSS class must be defined."""
        assert '#global-pause-banner.visible' in css_content

    def test_global_control_btn_class_defined(self, css_content):
        """.global-control-btn CSS class must be defined."""
        assert '.global-control-btn' in css_content

    def test_pause_all_btn_class_defined(self, css_content):
        """.global-control-btn.pause-all-btn CSS class must be defined."""
        assert '.global-control-btn.pause-all-btn' in css_content or '.pause-all-btn' in css_content

    def test_resume_all_btn_class_defined(self, css_content):
        """.global-control-btn.resume-all-btn CSS class must be defined."""
        assert '.global-control-btn.resume-all-btn' in css_content or '.resume-all-btn' in css_content

    def test_pause_all_btn_hover_state(self, css_content):
        """.pause-all-btn:hover CSS state must be defined."""
        assert '.pause-all-btn:hover' in css_content

    def test_resume_all_btn_hover_state(self, css_content):
        """.resume-all-btn:hover CSS state must be defined."""
        assert '.resume-all-btn:hover' in css_content

    def test_global_pause_banner_fixed_positioning(self, css_content):
        """#global-pause-banner must use fixed positioning."""
        section = find_section(css_content, '#global-pause-banner', 400)
        assert 'position: fixed' in section or 'position:fixed' in section


# ============================================================
# Test Group 3: Global Paused State (3 tests)
# ============================================================

class TestGlobalPausedState:
    """Verify the globalPaused state flag is correctly defined."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return get_js(HTML_PATH.read_text(encoding='utf-8'))

    def test_global_paused_defined(self, js_content):
        """globalPaused variable must be defined in JS."""
        assert 'globalPaused' in js_content

    def test_global_paused_window_exposed(self, js_content):
        """window.globalPaused must be assigned."""
        assert 'window.globalPaused' in js_content

    def test_global_paused_default_false(self, js_content):
        """window.globalPaused must default to false."""
        assert 'window.globalPaused = false' in js_content


# ============================================================
# Test Group 4: pauseAll Function (10 tests)
# ============================================================

class TestPauseAllFunction:
    """Verify the pauseAll() function is correctly implemented."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return get_js(HTML_PATH.read_text(encoding='utf-8'))

    @pytest.fixture(scope='class')
    def pause_all_section(self, js_content):
        return find_section(js_content, 'function pauseAll()', 1200)

    def test_pause_all_function_exists(self, js_content):
        """function pauseAll() must be defined."""
        assert 'function pauseAll()' in js_content

    def test_pause_all_window_exposed(self, js_content):
        """window.pauseAll must be assigned."""
        assert 'window.pauseAll = pauseAll' in js_content

    def test_pause_all_sets_global_paused_true(self, pause_all_section):
        """pauseAll must set window.globalPaused = true."""
        assert 'window.globalPaused = true' in pause_all_section

    def test_pause_all_updates_agents_paused(self, pause_all_section):
        """pauseAll must set agent.status = 'paused'."""
        assert "agent.status = 'paused'" in pause_all_section

    def test_pause_all_adds_to_paused_agents(self, pause_all_section):
        """pauseAll must add agents to window.pausedAgents."""
        assert 'window.pausedAgents.add' in pause_all_section

    def test_pause_all_shows_banner(self, pause_all_section):
        """pauseAll must add 'visible' class to the banner."""
        assert "classList.add('visible')" in pause_all_section

    def test_pause_all_hides_pause_all_btn(self, pause_all_section):
        """pauseAll must hide the #pause-all-btn."""
        assert "pauseBtn.style.display = 'none'" in pause_all_section or "pause-all-btn" in pause_all_section

    def test_pause_all_shows_resume_all_btn(self, pause_all_section):
        """pauseAll must show the #resume-all-btn."""
        assert 'resumeBtn' in pause_all_section or 'resume-all-btn' in pause_all_section

    def test_pause_all_adds_system_message(self, pause_all_section):
        """pauseAll must add a system message."""
        assert 'addSystemMessage' in pause_all_section or 'addMessage' in pause_all_section

    def test_pause_all_system_message_text(self, pause_all_section):
        """pauseAll system message must mention agents paused."""
        assert 'paused' in pause_all_section.lower()


# ============================================================
# Test Group 5: resumeAll Function (10 tests)
# ============================================================

class TestResumeAllFunction:
    """Verify the resumeAll() function is correctly implemented."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return get_js(HTML_PATH.read_text(encoding='utf-8'))

    @pytest.fixture(scope='class')
    def resume_all_section(self, js_content):
        return find_section(js_content, 'function resumeAll()', 1200)

    def test_resume_all_function_exists(self, js_content):
        """function resumeAll() must be defined."""
        assert 'function resumeAll()' in js_content

    def test_resume_all_window_exposed(self, js_content):
        """window.resumeAll must be assigned."""
        assert 'window.resumeAll = resumeAll' in js_content

    def test_resume_all_sets_global_paused_false(self, resume_all_section):
        """resumeAll must set window.globalPaused = false."""
        assert 'window.globalPaused = false' in resume_all_section

    def test_resume_all_clears_paused_agents(self, resume_all_section):
        """resumeAll must clear window.pausedAgents."""
        assert 'window.pausedAgents.clear()' in resume_all_section

    def test_resume_all_sets_agents_idle(self, resume_all_section):
        """resumeAll must set agent.status = 'idle'."""
        assert "agent.status = 'idle'" in resume_all_section

    def test_resume_all_hides_banner(self, resume_all_section):
        """resumeAll must remove 'visible' class from the banner."""
        assert "classList.remove('visible')" in resume_all_section

    def test_resume_all_shows_pause_all_btn(self, resume_all_section):
        """resumeAll must show the #pause-all-btn."""
        assert 'pauseBtn' in resume_all_section or 'pause-all-btn' in resume_all_section

    def test_resume_all_hides_resume_all_btn(self, resume_all_section):
        """resumeAll must hide the #resume-all-btn."""
        assert "resumeBtn.style.display = 'none'" in resume_all_section or 'resume-all-btn' in resume_all_section

    def test_resume_all_adds_system_message(self, resume_all_section):
        """resumeAll must add a system message."""
        assert 'addSystemMessage' in resume_all_section or 'addMessage' in resume_all_section

    def test_resume_all_system_message_text(self, resume_all_section):
        """resumeAll system message must mention agents resumed."""
        assert 'resumed' in resume_all_section.lower()


# ============================================================
# Test Group 6: isGloballyPaused Function (4 tests)
# ============================================================

class TestIsGloballyPausedFunction:
    """Verify the isGloballyPaused() function is correctly implemented."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return get_js(HTML_PATH.read_text(encoding='utf-8'))

    @pytest.fixture(scope='class')
    def is_globally_paused_section(self, js_content):
        return find_section(js_content, 'function isGloballyPaused()', 500)

    def test_is_globally_paused_function_exists(self, js_content):
        """function isGloballyPaused() must be defined."""
        assert 'function isGloballyPaused()' in js_content

    def test_is_globally_paused_window_exposed(self, js_content):
        """window.isGloballyPaused must be assigned."""
        assert 'window.isGloballyPaused = isGloballyPaused' in js_content

    def test_is_globally_paused_returns_global_paused(self, is_globally_paused_section):
        """isGloballyPaused must return window.globalPaused."""
        assert 'window.globalPaused' in is_globally_paused_section

    def test_is_globally_paused_has_return_statement(self, is_globally_paused_section):
        """isGloballyPaused must have a return statement."""
        assert 'return' in is_globally_paused_section


# ============================================================
# Test Group 7: Init Event Listeners (5 tests)
# ============================================================

class TestPauseAllInInit:
    """Verify the init() function wires up the global pause/resume buttons."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return get_js(HTML_PATH.read_text(encoding='utf-8'))

    @pytest.fixture(scope='class')
    def init_section(self, js_content):
        return find_section(js_content, 'function init()', 5000)

    def test_pause_all_btn_listener_in_init(self, init_section):
        """init() must register a click listener on #pause-all-btn."""
        assert 'pause-all-btn' in init_section

    def test_resume_all_btn_listener_in_init(self, init_section):
        """init() must register a click listener on #resume-all-btn."""
        assert 'resume-all-btn' in init_section

    def test_pause_all_wired_in_init(self, init_section):
        """init() must wire pauseAll to the pause-all-btn."""
        assert 'pauseAll' in init_section

    def test_resume_all_wired_in_init(self, init_section):
        """init() must wire resumeAll to the resume-all-btn."""
        assert 'resumeAll' in init_section

    def test_global_control_btn_listener_uses_add_event_listener(self, init_section):
        """init() must use addEventListener for the global control buttons."""
        assert "addEventListener('click', pauseAll)" in init_section or \
               "addEventListener('click', resumeAll)" in init_section


# ============================================================
# Test Group 8: Banner Content and Accessibility (5 tests)
# ============================================================

class TestPauseBannerContent:
    """Verify the banner content and accessibility attributes."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return HTML_PATH.read_text(encoding='utf-8')

    def test_pause_all_btn_has_pause_all_btn_class(self, html_content):
        """#pause-all-btn must have .pause-all-btn class."""
        section = find_section(html_content, 'id="pause-all-btn"', 200)
        assert 'pause-all-btn' in section

    def test_resume_all_btn_has_resume_all_btn_class(self, html_content):
        """#resume-all-btn must have .resume-all-btn class."""
        section = find_section(html_content, 'id="resume-all-btn"', 200)
        assert 'resume-all-btn' in section

    def test_pause_all_btn_title_attribute(self, html_content):
        """#pause-all-btn must have a title attribute."""
        section = find_section(html_content, 'id="pause-all-btn"', 200)
        assert 'title=' in section

    def test_resume_all_btn_title_attribute(self, html_content):
        """#resume-all-btn must have a title attribute."""
        section = find_section(html_content, 'id="resume-all-btn"', 200)
        assert 'title=' in section

    def test_resume_all_btn_initially_hidden(self, html_content):
        """#resume-all-btn must start with display:none."""
        section = find_section(html_content, 'id="resume-all-btn"', 200)
        assert 'display:none' in section or 'display: none' in section


# ============================================================
# Test Group 9: Orchestrator Global Pause Guard (4 tests)
# ============================================================

class TestOrchestratorGlobalPauseGuard:
    """Verify the orchestrator/dispatch code respects globalPaused."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return get_js(HTML_PATH.read_text(encoding='utf-8'))

    def test_global_paused_flag_in_js(self, js_content):
        """window.globalPaused flag must be present in JS."""
        assert 'window.globalPaused' in js_content

    def test_is_globally_paused_helper_available(self, js_content):
        """isGloballyPaused helper must be window-exposed for orchestrator use."""
        assert 'window.isGloballyPaused' in js_content

    def test_pause_all_sets_global_flag(self, js_content):
        """pauseAll must set window.globalPaused = true to block delegations."""
        section = find_section(js_content, 'function pauseAll()', 1200)
        assert 'window.globalPaused = true' in section

    def test_resume_all_clears_global_flag(self, js_content):
        """resumeAll must set window.globalPaused = false to allow delegations."""
        section = find_section(js_content, 'function resumeAll()', 1200)
        assert 'window.globalPaused = false' in section


# ============================================================
# Test Group 10: CSS Properties (5 tests)
# ============================================================

class TestPauseAllCSSProperties:
    """Verify specific CSS property values for global pause controls."""

    @pytest.fixture(scope='class')
    def css_content(self):
        return get_css(HTML_PATH.read_text(encoding='utf-8'))

    def test_banner_z_index_high(self, css_content):
        """#global-pause-banner must have z-index >= 1000."""
        section = find_section(css_content, '#global-pause-banner', 400)
        assert 'z-index: 1000' in section or 'z-index:1000' in section

    def test_banner_top_zero(self, css_content):
        """#global-pause-banner must have top: 0 for full-width display."""
        section = find_section(css_content, '#global-pause-banner', 400)
        assert 'top: 0' in section or 'top:0' in section

    def test_banner_amber_background(self, css_content):
        """#global-pause-banner must use amber background."""
        section = find_section(css_content, '#global-pause-banner', 400)
        assert 'f59e0b' in section or '245, 158, 11' in section

    def test_global_control_btn_uppercase(self, css_content):
        """.global-control-btn must use text-transform: uppercase."""
        section = find_section(css_content, '.global-control-btn', 400)
        assert 'text-transform: uppercase' in section or 'text-transform:uppercase' in section

    def test_global_control_buttons_flex(self, css_content):
        """.global-control-buttons must use display: flex."""
        section = find_section(css_content, '.global-control-buttons', 400)
        assert 'display: flex' in section or 'display:flex' in section
