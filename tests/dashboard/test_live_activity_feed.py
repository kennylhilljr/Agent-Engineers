"""
Tests for AI-150: REQ-FEED-001: Implement Live Activity Feed

Verifies:
- HTML structure: live indicator, count badge, filter controls, aria-live
- CSS: activity-feed-header, activity-feed-count, activity-filter-btn, status-icon styles
- JavaScript state: activityFilter default, liveActivityBuffer, MAX_ACTIVITY_ITEMS
- getStatusIcon() function: correct icons for all status types
- filterActivities() function: filters by all/success/error/running
- setActivityFilter() function: updates state, button active class, calls renderActivities
- addLiveActivityEvent() function: prepends, caps at MAX, calls renderActivities
- updateActivityCount() function: updates count badge text
- renderActivities() enhanced: applies filter, latest-first, updateActivityCount call
- init() wires up filter button event delegation
"""
import pytest
import sys
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def find_section(content, start_marker, size=3000):
    """Find a section of content starting at start_marker with given size."""
    idx = content.find(start_marker)
    if idx == -1:
        return ''
    return content[idx:idx + size]


# ============================================================
# Test Group 1: Activity Feed HTML Structure (8+ tests)
# ============================================================

class TestActivityFeedHTML:
    """Verify the live activity feed HTML structure is correctly defined."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_activity_feed_section_exists(self, html_content):
        """activity-feed-section element must exist."""
        assert 'id="activity-feed-section"' in html_content

    def test_activity_live_indicator_exists(self, html_content):
        """Live indicator element must exist."""
        assert 'id="activity-live-indicator"' in html_content

    def test_activity_count_badge_exists(self, html_content):
        """Count badge element must exist."""
        assert 'id="activity-count-badge"' in html_content

    def test_activity_filter_controls_id_exists(self, html_content):
        """activity-filter-controls element must exist."""
        assert 'id="activity-filter-controls"' in html_content

    def test_filter_button_all_exists(self, html_content):
        """All filter button must exist with data-filter='all'."""
        assert 'data-filter="all"' in html_content

    def test_filter_button_success_exists(self, html_content):
        """Success filter button must exist with data-filter='success'."""
        assert 'data-filter="success"' in html_content

    def test_filter_button_error_exists(self, html_content):
        """Error filter button must exist with data-filter='error'."""
        assert 'data-filter="error"' in html_content

    def test_filter_button_running_exists(self, html_content):
        """Running filter button must exist with data-filter='running'."""
        assert 'data-filter="running"' in html_content

    def test_activity_feed_has_aria_live(self, html_content):
        """activity-feed element must have aria-live for screen readers."""
        # Find the activity-feed div
        idx = html_content.find('id="activity-feed"')
        assert idx >= 0, "activity-feed element not found"
        # Check the surrounding element for aria-live
        section = html_content[max(0, idx - 200):idx + 200]
        assert 'aria-live="polite"' in section

    def test_activity_feed_header_class_exists(self, html_content):
        """activity-feed-header class must be present in HTML."""
        assert 'activity-feed-header' in html_content

    def test_activity_feed_live_indicator_class(self, html_content):
        """Live indicator must use activity-feed-live-indicator CSS class."""
        assert 'activity-feed-live-indicator' in html_content

    def test_activity_feed_count_class(self, html_content):
        """Count badge must use activity-feed-count CSS class."""
        assert 'activity-feed-count' in html_content


# ============================================================
# Test Group 2: Activity Feed CSS Styles (8+ tests)
# ============================================================

class TestActivityFeedCSS:
    """Verify the live activity feed CSS styles are defined."""

    @pytest.fixture(scope='class')
    def css_content(self):
        content = (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')
        # Extract just the CSS between <style> and </style>
        start = content.find('<style>')
        end = content.find('</style>')
        return content[start:end] if start >= 0 and end >= 0 else content

    def test_activity_feed_header_css(self, css_content):
        """.activity-feed-header CSS class must be defined."""
        assert '.activity-feed-header' in css_content

    def test_activity_feed_count_css(self, css_content):
        """.activity-feed-count CSS class must be defined."""
        assert '.activity-feed-count' in css_content

    def test_activity_filter_btn_css(self, css_content):
        """.activity-filter-btn CSS class must be defined."""
        assert '.activity-filter-btn' in css_content

    def test_activity_filter_btn_active_css(self, css_content):
        """.activity-filter-btn.active CSS class must be defined for active state."""
        assert '.activity-filter-btn.active' in css_content

    def test_activity_feed_live_indicator_css(self, css_content):
        """.activity-feed-live-indicator CSS class must be defined."""
        assert '.activity-feed-live-indicator' in css_content

    def test_live_indicator_pulse_animation(self, css_content):
        """Live indicator must use keyframe animation for pulsing effect."""
        assert 'live-pulse' in css_content or 'animation' in find_section(css_content, '.activity-feed-live-indicator')

    def test_status_icon_success_css(self, css_content):
        """.status-icon.success CSS must be defined."""
        assert '.status-icon.success' in css_content

    def test_status_icon_error_css(self, css_content):
        """.status-icon.error CSS must be defined."""
        assert '.status-icon.error' in css_content

    def test_status_icon_running_css(self, css_content):
        """.status-icon.running CSS must be defined."""
        assert '.status-icon.running' in css_content

    def test_status_icon_pending_css(self, css_content):
        """.status-icon.pending CSS must be defined."""
        assert '.status-icon.pending' in css_content

    def test_activity_filter_btn_hover_css(self, css_content):
        """.activity-filter-btn:hover CSS must be defined."""
        assert '.activity-filter-btn:hover' in css_content

    def test_activity_feed_filters_css(self, css_content):
        """.activity-feed-filters CSS must be defined."""
        assert '.activity-feed-filters' in css_content


# ============================================================
# Test Group 3: Activity Filter State Variables (5+ tests)
# ============================================================

class TestActivityFilterState:
    """Verify the activity feed state variables are defined and exposed."""

    @pytest.fixture(scope='class')
    def js_content(self):
        content = (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')
        # Extract JS from <script> sections
        start = content.find('<script>')
        end = content.rfind('</script>')
        return content[start:end] if start >= 0 and end >= 0 else content

    def test_activity_filter_defined(self, js_content):
        """window.activityFilter must be defined."""
        assert "window.activityFilter" in js_content

    def test_activity_filter_default_all(self, js_content):
        """activityFilter must default to 'all'."""
        assert "window.activityFilter = 'all'" in js_content

    def test_live_activity_buffer_defined(self, js_content):
        """window.liveActivityBuffer must be defined."""
        assert "window.liveActivityBuffer" in js_content

    def test_live_activity_buffer_is_array(self, js_content):
        """liveActivityBuffer must be initialized as an empty array."""
        assert "window.liveActivityBuffer = []" in js_content

    def test_max_activity_items_defined(self, js_content):
        """window.MAX_ACTIVITY_ITEMS must be defined."""
        assert "window.MAX_ACTIVITY_ITEMS" in js_content

    def test_max_activity_items_value(self, js_content):
        """MAX_ACTIVITY_ITEMS must be set to 100."""
        assert "window.MAX_ACTIVITY_ITEMS = 100" in js_content


# ============================================================
# Test Group 4: getStatusIcon Function (7+ tests)
# ============================================================

class TestGetStatusIconFunction:
    """Verify getStatusIcon() returns correct HTML icon spans."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_get_status_icon_function_exists(self, js_content):
        """getStatusIcon function must be defined."""
        assert 'function getStatusIcon' in js_content

    def test_get_status_icon_window_exposed(self, js_content):
        """getStatusIcon must be exposed on window for testing."""
        assert 'window.getStatusIcon' in js_content

    def test_get_status_icon_success_checkmark(self, js_content):
        """getStatusIcon must return ✓ for success status."""
        fn_section = find_section(js_content, 'function getStatusIcon')
        assert '✓' in fn_section

    def test_get_status_icon_success_class(self, js_content):
        """getStatusIcon must return element with 'success' CSS class."""
        fn_section = find_section(js_content, 'function getStatusIcon')
        assert 'success' in fn_section

    def test_get_status_icon_error_x(self, js_content):
        """getStatusIcon must return ✗ for error status."""
        fn_section = find_section(js_content, 'function getStatusIcon')
        assert '✗' in fn_section

    def test_get_status_icon_error_class(self, js_content):
        """getStatusIcon must return element with 'error' CSS class."""
        fn_section = find_section(js_content, 'function getStatusIcon')
        assert 'error' in fn_section

    def test_get_status_icon_running_spinner(self, js_content):
        """getStatusIcon must return ⟳ for running status."""
        fn_section = find_section(js_content, 'function getStatusIcon')
        assert '⟳' in fn_section

    def test_get_status_icon_running_class(self, js_content):
        """getStatusIcon must return element with 'running' CSS class."""
        fn_section = find_section(js_content, 'function getStatusIcon')
        assert 'running' in fn_section

    def test_get_status_icon_pending_circle(self, js_content):
        """getStatusIcon must return ○ for unknown/pending status."""
        fn_section = find_section(js_content, 'function getStatusIcon')
        assert '○' in fn_section

    def test_get_status_icon_handles_done(self, js_content):
        """getStatusIcon must handle 'done' status as success."""
        fn_section = find_section(js_content, 'function getStatusIcon')
        assert "'done'" in fn_section or '"done"' in fn_section

    def test_get_status_icon_handles_completed(self, js_content):
        """getStatusIcon must handle 'completed' status as success."""
        fn_section = find_section(js_content, 'function getStatusIcon')
        assert "'completed'" in fn_section or '"completed"' in fn_section

    def test_get_status_icon_handles_failed(self, js_content):
        """getStatusIcon must handle 'failed' status as error."""
        fn_section = find_section(js_content, 'function getStatusIcon')
        assert "'failed'" in fn_section or '"failed"' in fn_section

    def test_get_status_icon_status_icon_class(self, js_content):
        """getStatusIcon must use 'status-icon' as base CSS class."""
        fn_section = find_section(js_content, 'function getStatusIcon')
        assert 'status-icon' in fn_section


# ============================================================
# Test Group 5: filterActivities Function (7+ tests)
# ============================================================

class TestFilterActivitiesFunction:
    """Verify filterActivities() correctly filters activities by status."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_filter_activities_function_exists(self, js_content):
        """filterActivities function must be defined."""
        assert 'function filterActivities' in js_content

    def test_filter_activities_window_exposed(self, js_content):
        """filterActivities must be exposed on window for testing."""
        assert 'window.filterActivities' in js_content

    def test_filter_activities_handles_all(self, js_content):
        """filterActivities must return all items for 'all' filter."""
        fn_section = find_section(js_content, 'function filterActivities', 1500)
        assert "'all'" in fn_section or '"all"' in fn_section

    def test_filter_activities_success_filters_done(self, js_content):
        """filterActivities success filter must include 'done' status."""
        fn_section = find_section(js_content, 'function filterActivities', 1500)
        assert "'done'" in fn_section or '"done"' in fn_section

    def test_filter_activities_success_filters_completed(self, js_content):
        """filterActivities success filter must include 'completed' status."""
        fn_section = find_section(js_content, 'function filterActivities', 1500)
        assert "'completed'" in fn_section or '"completed"' in fn_section

    def test_filter_activities_error_filters_failed(self, js_content):
        """filterActivities error filter must include 'failed' status."""
        fn_section = find_section(js_content, 'function filterActivities', 1500)
        assert "'failed'" in fn_section or '"failed"' in fn_section

    def test_filter_activities_running_filters_in_progress(self, js_content):
        """filterActivities running filter must include 'in_progress' status."""
        fn_section = find_section(js_content, 'function filterActivities', 1500)
        assert "'in_progress'" in fn_section or '"in_progress"' in fn_section

    def test_filter_activities_running_filters_active(self, js_content):
        """filterActivities running filter must include 'active' status."""
        fn_section = find_section(js_content, 'function filterActivities', 1500)
        assert "'active'" in fn_section or '"active"' in fn_section

    def test_filter_activities_takes_two_params(self, js_content):
        """filterActivities must accept activities array and filter string."""
        assert 'function filterActivities(activities, filter)' in js_content


# ============================================================
# Test Group 6: setActivityFilter Function (6+ tests)
# ============================================================

class TestSetActivityFilterFunction:
    """Verify setActivityFilter() correctly updates state and UI."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_set_activity_filter_function_exists(self, js_content):
        """setActivityFilter function must be defined."""
        assert 'function setActivityFilter' in js_content

    def test_set_activity_filter_window_exposed(self, js_content):
        """setActivityFilter must be exposed on window for testing."""
        assert 'window.setActivityFilter' in js_content

    def test_set_activity_filter_updates_window_filter(self, js_content):
        """setActivityFilter must update window.activityFilter."""
        fn_section = find_section(js_content, 'function setActivityFilter', 800)
        assert 'window.activityFilter = filter' in fn_section

    def test_set_activity_filter_updates_button_active_class(self, js_content):
        """setActivityFilter must toggle active class on filter buttons."""
        fn_section = find_section(js_content, 'function setActivityFilter', 800)
        assert 'active' in fn_section

    def test_set_activity_filter_calls_render_activities(self, js_content):
        """setActivityFilter must call renderActivities() to refresh display."""
        fn_section = find_section(js_content, 'function setActivityFilter', 800)
        assert 'renderActivities()' in fn_section

    def test_set_activity_filter_uses_filter_controls(self, js_content):
        """setActivityFilter must query activity-filter-controls element."""
        fn_section = find_section(js_content, 'function setActivityFilter', 800)
        assert 'activity-filter-controls' in fn_section


# ============================================================
# Test Group 7: addLiveActivityEvent Function (6+ tests)
# ============================================================

class TestAddLiveActivityEventFunction:
    """Verify addLiveActivityEvent() correctly manages live events."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_add_live_activity_event_function_exists(self, js_content):
        """addLiveActivityEvent function must be defined."""
        assert 'function addLiveActivityEvent' in js_content

    def test_add_live_activity_event_window_exposed(self, js_content):
        """addLiveActivityEvent must be exposed on window for testing."""
        assert 'window.addLiveActivityEvent' in js_content

    def test_add_live_activity_event_prepends_to_front(self, js_content):
        """addLiveActivityEvent must prepend new event to front of activities."""
        fn_section = find_section(js_content, 'function addLiveActivityEvent', 600)
        assert 'unshift' in fn_section

    def test_add_live_activity_event_caps_at_max(self, js_content):
        """addLiveActivityEvent must cap list at MAX_ACTIVITY_ITEMS."""
        fn_section = find_section(js_content, 'function addLiveActivityEvent', 600)
        assert 'MAX_ACTIVITY_ITEMS' in fn_section

    def test_add_live_activity_event_calls_render(self, js_content):
        """addLiveActivityEvent must call renderActivities() to refresh display."""
        fn_section = find_section(js_content, 'function addLiveActivityEvent', 600)
        assert 'renderActivities()' in fn_section

    def test_add_live_activity_event_calls_update_count(self, js_content):
        """addLiveActivityEvent must call updateActivityCount() after adding."""
        fn_section = find_section(js_content, 'function addLiveActivityEvent', 600)
        assert 'updateActivityCount()' in fn_section


# ============================================================
# Test Group 8: updateActivityCount Function (4 tests)
# ============================================================

class TestUpdateActivityCountFunction:
    """Verify updateActivityCount() correctly updates the count badge."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_update_activity_count_function_exists(self, js_content):
        """updateActivityCount function must be defined."""
        assert 'function updateActivityCount' in js_content

    def test_update_activity_count_window_exposed(self, js_content):
        """updateActivityCount must be exposed on window for testing."""
        assert 'window.updateActivityCount' in js_content

    def test_update_activity_count_targets_badge(self, js_content):
        """updateActivityCount must target the activity-count-badge element."""
        fn_section = find_section(js_content, 'function updateActivityCount', 500)
        assert 'activity-count-badge' in fn_section

    def test_update_activity_count_sets_text(self, js_content):
        """updateActivityCount must set textContent of the badge."""
        fn_section = find_section(js_content, 'function updateActivityCount', 500)
        assert 'textContent' in fn_section


# ============================================================
# Test Group 9: renderActivities Enhanced (6+ tests)
# ============================================================

class TestRenderActivitiesEnhanced:
    """Verify renderActivities() has been enhanced with new capabilities."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_render_activities_function_exists(self, js_content):
        """renderActivities function must exist."""
        assert 'function renderActivities' in js_content

    def test_render_activities_applies_filter(self, js_content):
        """renderActivities must call filterActivities to apply current filter."""
        fn_section = find_section(js_content, 'function renderActivities', 2500)
        assert 'filterActivities' in fn_section

    def test_render_activities_uses_activity_filter(self, js_content):
        """renderActivities must use window.activityFilter when filtering."""
        fn_section = find_section(js_content, 'function renderActivities', 2500)
        assert 'activityFilter' in fn_section

    def test_render_activities_calls_update_count(self, js_content):
        """renderActivities must call updateActivityCount() after rendering."""
        fn_section = find_section(js_content, 'function renderActivities', 2500)
        assert 'updateActivityCount()' in fn_section

    def test_render_activities_latest_first_sorting(self, js_content):
        """renderActivities must sort activities in latest-first order."""
        fn_section = find_section(js_content, 'function renderActivities', 2500)
        assert 'sort(' in fn_section

    def test_render_activities_uses_get_status_icon(self, js_content):
        """renderActivities must use getStatusIcon for status display."""
        fn_section = find_section(js_content, 'function renderActivities', 2500)
        assert 'getStatusIcon' in fn_section

    def test_render_activities_shows_ticket_key(self, js_content):
        """renderActivities must display ticket_key field."""
        fn_section = find_section(js_content, 'function renderActivities', 2500)
        assert 'ticket_key' in fn_section or 'activity-ticket' in fn_section

    def test_render_activities_shows_duration(self, js_content):
        """renderActivities must display duration field."""
        fn_section = find_section(js_content, 'function renderActivities', 2500)
        assert 'duration' in fn_section


# ============================================================
# Test Group 10: Init Wiring and WebSocket (5+ tests)
# ============================================================

class TestActivityFeedInInit:
    """Verify init() correctly sets up the activity feed event listeners."""

    @pytest.fixture(scope='class')
    def js_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_filter_button_listener_in_init(self, js_content):
        """init() must add click listener to activity-filter-controls."""
        init_section = find_section(js_content, 'function init()', 5000)
        assert 'activity-filter-controls' in init_section

    def test_filter_button_listener_calls_set_filter(self, js_content):
        """init() filter button listener must call setActivityFilter."""
        init_section = find_section(js_content, 'function init()', 5000)
        assert 'setActivityFilter' in init_section

    def test_add_live_activity_event_window_accessible(self, js_content):
        """addLiveActivityEvent must be accessible via window for external calls."""
        assert 'window.addLiveActivityEvent = addLiveActivityEvent' in js_content

    def test_websocket_integration_present(self, js_content):
        """WebSocket connection setup must be present in init."""
        init_section = find_section(js_content, 'function init()', 6000)
        assert 'WebSocket' in init_section

    def test_websocket_handles_agent_event(self, js_content):
        """WebSocket handler must process 'agent_event' message type."""
        assert "agent_event" in js_content

    def test_websocket_handles_activity_type(self, js_content):
        """WebSocket handler must process 'activity' message type."""
        assert "'activity'" in js_content or '"activity"' in js_content

    def test_websocket_calls_add_live_activity(self, js_content):
        """WebSocket handler must call addLiveActivityEvent on receiving events."""
        ws_section = find_section(js_content, 'setupActivityWebSocket', 1500)
        assert 'addLiveActivityEvent' in ws_section
