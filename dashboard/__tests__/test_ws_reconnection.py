"""Tests for AI-184: WebSocket Reconnection with Exponential Backoff (REQ-REL-002).

Verifies that dashboard.html contains the WS_RECONNECT object with:
- Exponential backoff delay calculation (1s, 2s, 4s, 8s)
- Max delay of 30000ms (30 seconds)
- reset() method that resets attempts to 0
- schedule() method that logs and sets timer
- onclose triggers reconnect for unclean close
- onopen resets reconnect state and calls fetchMetrics
- connectWebSocket function exists
"""

from pathlib import Path
import re

# Path to dashboard.html
DASHBOARD_HTML = Path(__file__).parent.parent / "dashboard.html"


def read_html() -> str:
    """Read dashboard.html content."""
    return DASHBOARD_HTML.read_text(encoding="utf-8")


# ─────────────────────────────────────────────
# Test Group 1: WS_RECONNECT object presence
# ─────────────────────────────────────────────

def test_html_contains_ws_reconnect_object():
    """Dashboard HTML must declare the WS_RECONNECT object."""
    html = read_html()
    assert "WS_RECONNECT" in html, "WS_RECONNECT object not found in dashboard.html"


def test_ws_reconnect_has_attempts_field():
    """WS_RECONNECT must have an 'attempts' field."""
    html = read_html()
    assert re.search(r"attempts\s*:", html), "WS_RECONNECT.attempts field not found"


def test_ws_reconnect_has_max_delay_field():
    """WS_RECONNECT must have maxDelay field set to 30000."""
    html = read_html()
    assert re.search(r"maxDelay\s*:\s*30000", html), "WS_RECONNECT.maxDelay: 30000 not found"


def test_ws_reconnect_has_base_delay_field():
    """WS_RECONNECT must have baseDelay field set to 1000."""
    html = read_html()
    assert re.search(r"baseDelay\s*:\s*1000", html), "WS_RECONNECT.baseDelay: 1000 not found"


def test_ws_reconnect_has_timer_field():
    """WS_RECONNECT must have a timer field."""
    html = read_html()
    assert re.search(r"timer\s*:", html), "WS_RECONNECT.timer field not found"


# ─────────────────────────────────────────────
# Test Group 2: getDelay() exponential backoff
# ─────────────────────────────────────────────

def test_ws_reconnect_has_get_delay_method():
    """WS_RECONNECT must have a getDelay() method."""
    html = read_html()
    assert re.search(r"getDelay\s*\(\s*\)", html), "WS_RECONNECT.getDelay() method not found"


def test_get_delay_uses_exponential_formula():
    """getDelay() must use exponential backoff formula (baseDelay * 2^attempts)."""
    html = read_html()
    # Should contain Math.pow(2, this.attempts) or equivalent
    assert re.search(r"Math\.pow\s*\(\s*2\s*,\s*this\.attempts\s*\)", html), \
        "getDelay() does not use Math.pow(2, this.attempts) exponential backoff"


def test_get_delay_caps_at_max_delay():
    """getDelay() must cap the result at maxDelay using Math.min."""
    html = read_html()
    # Should use Math.min(..., this.maxDelay)
    assert re.search(r"Math\.min\s*\(.*this\.maxDelay\s*\)", html, re.DOTALL), \
        "getDelay() does not cap at maxDelay with Math.min"


def test_max_delay_is_30000_ms():
    """Maximum reconnect delay must be 30000ms (30 seconds)."""
    html = read_html()
    assert re.search(r"maxDelay\s*:\s*30000", html), "maxDelay is not 30000ms"


def test_base_delay_is_1000_ms():
    """Base reconnect delay (initial delay) must be 1000ms (1 second)."""
    html = read_html()
    assert re.search(r"baseDelay\s*:\s*1000", html), "baseDelay is not 1000ms"


# ─────────────────────────────────────────────
# Test Group 3: reset() method
# ─────────────────────────────────────────────

def test_ws_reconnect_has_reset_method():
    """WS_RECONNECT must have a reset() method."""
    html = read_html()
    assert re.search(r"reset\s*\(\s*\)\s*\{", html), "WS_RECONNECT.reset() method not found"


def test_reset_sets_attempts_to_zero():
    """reset() must set this.attempts = 0."""
    html = read_html()
    assert re.search(r"this\.attempts\s*=\s*0", html), "reset() does not set this.attempts = 0"


def test_reset_clears_timer():
    """reset() must clear any pending timer with clearTimeout."""
    html = read_html()
    assert "clearTimeout" in html, "reset() does not use clearTimeout"
    assert re.search(r"this\.timer\s*=\s*null", html), "reset() does not set this.timer = null"


# ─────────────────────────────────────────────
# Test Group 4: schedule() method
# ─────────────────────────────────────────────

def test_ws_reconnect_has_schedule_method():
    """WS_RECONNECT must have a schedule() method."""
    html = read_html()
    assert re.search(r"schedule\s*\(connectFn\)", html), "WS_RECONNECT.schedule(connectFn) not found"


def test_schedule_increments_attempts():
    """schedule() must increment this.attempts."""
    html = read_html()
    assert re.search(r"this\.attempts\+\+", html), "schedule() does not increment this.attempts"


def test_schedule_uses_set_timeout():
    """schedule() must use setTimeout to delay reconnection."""
    html = read_html()
    assert re.search(r"this\.timer\s*=\s*setTimeout\(connectFn", html), \
        "schedule() does not use setTimeout(connectFn, ...)"


# ─────────────────────────────────────────────
# Test Group 5: connectWebSocket integration
# ─────────────────────────────────────────────

def test_connect_web_socket_function_exists():
    """connectWebSocket() function must exist in the HTML."""
    html = read_html()
    assert re.search(r"function\s+connectWebSocket\s*\(\s*\)", html), \
        "connectWebSocket() function not found"


def test_on_open_calls_ws_reconnect_reset():
    """onopen handler must call WS_RECONNECT.reset()."""
    html = read_html()
    assert "WS_RECONNECT.reset()" in html, "onopen handler does not call WS_RECONNECT.reset()"


def test_on_open_calls_fetch_metrics():
    """onopen handler must call fetchMetrics() to resync state on reconnect."""
    html = read_html()
    # fetchMetrics() should be called inside the onopen handler
    assert "fetchMetrics()" in html, "onopen handler does not call fetchMetrics()"


def test_on_close_triggers_ws_reconnect_for_unclean_close():
    """onclose handler must trigger WS_RECONNECT.schedule() for unclean close."""
    html = read_html()
    assert re.search(r"event\.wasClean", html), \
        "onclose handler does not check event.wasClean"
    assert re.search(r"WS_RECONNECT\.schedule\s*\(connectWebSocket\)", html), \
        "onclose handler does not call WS_RECONNECT.schedule(connectWebSocket)"


def test_on_error_closes_websocket():
    """onerror handler must close the websocket to trigger onclose reconnect logic."""
    html = read_html()
    # The onerror should close the websocket
    assert re.search(r"websocket\.onerror", html), "websocket.onerror handler not found"
    # Must have some form of .close() call in the handler area
    assert re.search(r"\.close\(\)", html), "onerror does not trigger close()"
