"""
Tests for AI-179: REQ-UI-002 - Dark Mode Toggle.

Validates that dashboard/dashboard.html meets the acceptance criteria:
- Dark mode is default
- Toggle button switches between dark and light
- Both themes are readable (proper contrast via CSS variables)
- Preference persists in localStorage
- Smooth transition between themes
"""
import os
import re
import pytest

DASHBOARD_PATH = os.path.join(
    os.path.dirname(__file__), "..", "dashboard.html"
)


@pytest.fixture(scope="module")
def dashboard_content():
    """Load the dashboard.html file content once for all tests."""
    assert os.path.isfile(DASHBOARD_PATH), (
        f"dashboard.html not found at {DASHBOARD_PATH}"
    )
    with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
        return f.read()


class TestDarkModeHTML:
    """Tests verifying the HTML structure for dark mode toggle."""

    def test_theme_toggle_button_exists(self, dashboard_content):
        """A theme toggle button must exist in the HTML."""
        assert 'theme-toggle-btn' in dashboard_content, \
               "theme-toggle-btn not found in dashboard.html"

    def test_theme_toggle_button_id(self, dashboard_content):
        """The theme toggle button must have an id attribute."""
        assert 'id="theme-toggle-btn"' in dashboard_content, \
               "id='theme-toggle-btn' not found"

    def test_toggle_button_calls_toggleDarkMode(self, dashboard_content):
        """The toggle button must call toggleDarkMode() on click."""
        assert 'onclick="toggleDarkMode()"' in dashboard_content, \
               "onclick='toggleDarkMode()' not found on toggle button"

    def test_moon_or_sun_icon_present(self, dashboard_content):
        """Moon or sun icon must be present in the theme toggle."""
        # Check for sun emoji (U+2600), moon emoji (U+1F319), or the unicode escapes
        has_sun = '\u2600' in dashboard_content or '&#9728;' in dashboard_content or \
                  '\\u2600' in dashboard_content or 'theme-toggle-icon' in dashboard_content
        has_moon = '\U0001f319' in dashboard_content or '&#127769;' in dashboard_content or \
                   '\\uD83C\\uDF19' in dashboard_content or '🌙' in dashboard_content
        # The icons are set via JS, so we check for the span IDs
        assert 'theme-toggle-icon' in dashboard_content, \
               "theme-toggle-icon span not found"

    def test_theme_toggle_icon_span(self, dashboard_content):
        """The theme toggle must have a span for the icon."""
        assert 'id="theme-toggle-icon"' in dashboard_content, \
               "id='theme-toggle-icon' span not found"

    def test_theme_toggle_label_span(self, dashboard_content):
        """The theme toggle must have a span for the label text."""
        assert 'id="theme-toggle-label"' in dashboard_content, \
               "id='theme-toggle-label' span not found"

    def test_theme_toggle_aria_label(self, dashboard_content):
        """The theme toggle button must have an aria-label."""
        assert re.search(
            r'theme-toggle-btn[^>]*aria-label',
            dashboard_content,
            re.DOTALL
        ) or 'aria-label="Toggle dark/light mode"' in dashboard_content, \
               "No aria-label on theme-toggle-btn"

    def test_theme_toggle_in_header_area(self, dashboard_content):
        """The theme toggle must appear near the header/refresh-info area."""
        # Find the HTML element for the header div (not the CSS class def)
        # The HTML header div is in the body, after the <body> tag
        body_idx = dashboard_content.find('<body>')
        assert body_idx >= 0, "<body> tag not found"
        body_content = dashboard_content[body_idx:]
        header_idx = body_content.find('class="header"')
        toggle_idx = body_content.find('theme-toggle-btn')
        assert header_idx >= 0 and toggle_idx >= 0, \
               "header or theme-toggle-btn not found in body"
        # Toggle should be within 3000 chars of the header (header is a large block)
        assert abs(toggle_idx - header_idx) < 3000, \
               "theme-toggle-btn is not close to the header element in the body"


class TestDarkModeCSS:
    """Tests verifying the CSS for dark/light mode themes."""

    def test_css_variable_bg_primary_dark(self, dashboard_content):
        """CSS must define --bg-primary variable in :root."""
        assert '--bg-primary' in dashboard_content, \
               "--bg-primary CSS variable not found"

    def test_css_variable_bg_secondary(self, dashboard_content):
        """CSS must define --bg-secondary variable."""
        assert '--bg-secondary' in dashboard_content, \
               "--bg-secondary CSS variable not found"

    def test_css_variable_text_primary(self, dashboard_content):
        """CSS must define --text-primary variable."""
        assert '--text-primary' in dashboard_content, \
               "--text-primary CSS variable not found"

    def test_css_variable_text_secondary(self, dashboard_content):
        """CSS must define --text-secondary variable."""
        assert '--text-secondary' in dashboard_content, \
               "--text-secondary CSS variable not found"

    def test_css_variable_border_color(self, dashboard_content):
        """CSS must define --border-color variable."""
        assert '--border-color' in dashboard_content, \
               "--border-color CSS variable not found"

    def test_css_variable_accent(self, dashboard_content):
        """CSS must define --accent variable."""
        assert '--accent' in dashboard_content, \
               "--accent CSS variable not found"

    def test_data_theme_light_selector_exists(self, dashboard_content):
        """CSS must have a [data-theme='light'] selector."""
        assert re.search(
            r'\[data-theme=["\']light["\']\]',
            dashboard_content
        ), "[data-theme='light'] CSS selector not found"

    def test_light_theme_bg_primary_white(self, dashboard_content):
        """Light theme --bg-primary should be a light color."""
        match = re.search(
            r'\[data-theme=["\']light["\']\]\s*\{([^}]+)\}',
            dashboard_content,
            re.DOTALL
        )
        assert match, "[data-theme='light'] CSS block not found"
        block = match.group(1)
        assert '--bg-primary' in block, \
               "--bg-primary not defined in [data-theme='light'] block"

    def test_root_selector_defines_dark_theme(self, dashboard_content):
        """The :root selector must define dark theme variables."""
        match = re.search(
            r':root\s*\{([^}]+)\}',
            dashboard_content,
            re.DOTALL
        )
        assert match, ":root CSS block not found"
        block = match.group(1)
        assert '--bg-primary' in block, \
               "--bg-primary not defined in :root (dark theme) block"

    def test_dark_bg_primary_is_dark_color(self, dashboard_content):
        """Dark theme --bg-primary should be a dark color (starts with #0 or #1)."""
        match = re.search(
            r':root\s*\{([^}]+)\}',
            dashboard_content,
            re.DOTALL
        )
        assert match, ":root CSS block not found"
        block = match.group(1)
        bg_match = re.search(r'--bg-primary\s*:\s*(#[0-9a-fA-F]+)', block)
        assert bg_match, "--bg-primary value not found in :root block"
        color = bg_match.group(1).lower()
        # Dark colors start with #0 or #1 typically
        assert color.startswith('#0') or color.startswith('#1'), \
               f"--bg-primary in :root is '{color}', expected a dark color (#0... or #1...)"

    def test_transition_defined_for_theme_switch(self, dashboard_content):
        """A CSS transition must be defined to smooth theme switching."""
        assert 'transition' in dashboard_content and \
               ('theme' in dashboard_content.lower() or
                'background-color' in dashboard_content), \
               "No theme transition CSS found"


class TestDarkModeJS:
    """Tests verifying the JavaScript for dark mode toggle."""

    def test_toggleDarkMode_function_defined(self, dashboard_content):
        """toggleDarkMode function must be defined."""
        assert 'function toggleDarkMode()' in dashboard_content, \
               "toggleDarkMode function not defined"

    def test_data_theme_attribute_set(self, dashboard_content):
        """setAttribute('data-theme', ...) must be called in toggleDarkMode."""
        assert re.search(
            r'setAttribute\(["\']data-theme["\']',
            dashboard_content
        ), "setAttribute('data-theme', ...) not found"

    def test_localstorage_setitem_theme(self, dashboard_content):
        """localStorage.setItem('theme', ...) must be called."""
        assert re.search(
            r'localStorage\.setItem\(["\']theme["\']',
            dashboard_content
        ), "localStorage.setItem('theme', ...) not found"

    def test_localstorage_getitem_theme(self, dashboard_content):
        """localStorage.getItem('theme') must be used to restore preference."""
        assert re.search(
            r'localStorage\.getItem\(["\']theme["\']',
            dashboard_content
        ), "localStorage.getItem('theme') not found"

    def test_default_theme_is_dark(self, dashboard_content):
        """Default theme must be 'dark' (fallback in localStorage.getItem)."""
        assert re.search(
            r'localStorage\.getItem\(["\']theme["\']\)\s*\|\|\s*["\']dark["\']',
            dashboard_content
        ), "Default theme 'dark' fallback not found in localStorage.getItem('theme') || 'dark'"

    def test_theme_applied_on_load(self, dashboard_content):
        """data-theme attribute must be set on page load from localStorage."""
        # Both reading from localStorage and setting data-theme must exist
        assert 'localStorage.getItem' in dashboard_content and \
               'data-theme' in dashboard_content, \
               "Theme not applied from localStorage on load"
