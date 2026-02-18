"""
Tests for AI-178: REQ-UI-001 - Panel Collapsibility.

Validates that dashboard/dashboard.html meets the acceptance criteria:
- Collapsible on narrow viewports (< 768px) OR via a toggle button
- Icons are clear and clickable when collapsed
- Panel expands/collapses smoothly (CSS transition)
- Main panel uses available space when left panel is collapsed
- No content is cut off
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


class TestPanelCollapsibilityHTML:
    """Tests verifying the HTML structure for panel collapsibility."""

    def test_left_panel_element_exists(self, dashboard_content):
        """The left panel element must exist in the HTML."""
        assert 'id="left-panel"' in dashboard_content or \
               "left-panel" in dashboard_content, \
               "left-panel element not found in dashboard.html"

    def test_left_panel_aside_or_div(self, dashboard_content):
        """The left panel should be an aside or div with left-panel class/id."""
        assert re.search(
            r'<(aside|div)[^>]+(?:class|id)=["\'][^"\']*left-panel[^"\']*["\']',
            dashboard_content
        ), "No aside/div with left-panel class or id found"

    def test_collapse_toggle_button_exists(self, dashboard_content):
        """A toggle button for collapsing the left panel must exist."""
        assert 'left-panel-toggle' in dashboard_content or \
               'toggleLeftPanel' in dashboard_content, \
               "No collapse toggle button or toggleLeftPanel function found"

    def test_toggle_button_has_id(self, dashboard_content):
        """The collapse toggle button should have an ID."""
        assert 'id="left-panel-toggle"' in dashboard_content, \
               "left-panel-toggle button id not found"

    def test_toggle_button_onclick(self, dashboard_content):
        """The collapse toggle button must call toggleLeftPanel() on click."""
        assert 'onclick="toggleLeftPanel()"' in dashboard_content, \
               "toggleLeftPanel() onclick not found on toggle button"

    def test_collapse_icon_bar_exists(self, dashboard_content):
        """A collapse icon bar should exist for the collapsed state."""
        assert 'collapse-icon' in dashboard_content, \
               "collapse-icon element not found"

    def test_panel_content_class_exists(self, dashboard_content):
        """The panel should have a panel-content class for the nav items."""
        assert 'class="panel-content"' in dashboard_content or \
               'panel-content' in dashboard_content, \
               "panel-content class not found"

    def test_nav_items_in_panel(self, dashboard_content):
        """Navigation items should exist inside the left panel."""
        assert 'panel-nav-item' in dashboard_content, \
               "panel-nav-item class not found in left panel"

    def test_main_content_element_exists(self, dashboard_content):
        """A main content area element must exist."""
        assert 'id="main-content"' in dashboard_content or \
               'class="main-content"' in dashboard_content, \
               "main-content element not found"

    def test_app_layout_exists(self, dashboard_content):
        """The app-layout wrapper must exist to enable the flex layout."""
        assert 'class="app-layout"' in dashboard_content, \
               "app-layout class not found"

    def test_aria_label_on_sidebar(self, dashboard_content):
        """The left panel must have an aria-label for accessibility."""
        assert 'aria-label="Navigation sidebar"' in dashboard_content or \
               'aria-label' in dashboard_content, \
               "No aria-label found on sidebar"


class TestPanelCollapsibilityCSS:
    """Tests verifying the CSS for panel collapsibility and transitions."""

    def test_left_panel_css_class_exists(self, dashboard_content):
        """CSS must define .left-panel class."""
        assert re.search(r'\.left-panel\s*\{', dashboard_content), \
               ".left-panel CSS class not found"

    def test_collapsed_css_class_exists(self, dashboard_content):
        """CSS must define .left-panel.collapsed class."""
        assert re.search(
            r'\.left-panel\.collapsed\s*\{', dashboard_content
        ), ".left-panel.collapsed CSS class not found"

    def test_transition_defined_on_left_panel(self, dashboard_content):
        """The left panel must have a CSS transition for smooth animation."""
        assert re.search(
            r'\.left-panel\s*\{[^}]*transition[^}]*\}',
            dashboard_content,
            re.DOTALL
        ), "No CSS transition found in .left-panel rule"

    def test_transition_includes_width(self, dashboard_content):
        """The CSS transition must include width property."""
        # Find the .left-panel block and check for width transition
        match = re.search(
            r'\.left-panel\s*\{([^}]+)\}',
            dashboard_content,
            re.DOTALL
        )
        assert match, ".left-panel CSS block not found"
        block = match.group(1)
        assert 'width' in block and 'transition' in block, \
               "width transition not found in .left-panel block"

    def test_collapsed_width_48px(self, dashboard_content):
        """Collapsed panel must be 48px wide."""
        match = re.search(
            r'\.left-panel\.collapsed\s*\{([^}]+)\}',
            dashboard_content,
            re.DOTALL
        )
        assert match, ".left-panel.collapsed CSS block not found"
        block = match.group(1)
        assert '48px' in block, \
               "48px width not found in .left-panel.collapsed block"

    def test_panel_content_hidden_when_collapsed(self, dashboard_content):
        """Panel content must be hidden when panel is collapsed."""
        assert re.search(
            r'\.left-panel\.collapsed\s+\.panel-content\s*\{[^}]*display\s*:\s*none[^}]*\}',
            dashboard_content,
            re.DOTALL
        ), ".left-panel.collapsed .panel-content { display: none } not found"

    def test_collapse_icon_visible_when_collapsed(self, dashboard_content):
        """collapse-icon must be visible (flex) when panel is collapsed."""
        assert re.search(
            r'\.left-panel\.collapsed\s+\.collapse-icon\s*\{[^}]*display\s*:\s*flex[^}]*\}',
            dashboard_content,
            re.DOTALL
        ), ".left-panel.collapsed .collapse-icon { display: flex } not found"

    def test_responsive_media_query_768px(self, dashboard_content):
        """Media query for max-width: 768px must exist for auto-collapse."""
        assert re.search(
            r'@media\s*\(\s*max-width\s*:\s*768px\s*\)',
            dashboard_content
        ), "@media (max-width: 768px) not found"

    def test_main_content_flex_1(self, dashboard_content):
        """Main content area must have flex: 1 to use available space."""
        match = re.search(
            r'\.main-content\s*\{([^}]+)\}',
            dashboard_content,
            re.DOTALL
        )
        assert match, ".main-content CSS block not found"
        block = match.group(1)
        assert 'flex' in block, \
               "flex property not found in .main-content CSS block"


class TestPanelCollapsibilityJS:
    """Tests verifying the JavaScript for panel collapsibility."""

    def test_toggle_function_defined(self, dashboard_content):
        """toggleLeftPanel function must be defined."""
        assert 'function toggleLeftPanel()' in dashboard_content, \
               "toggleLeftPanel function not defined"

    def test_localstorage_set_on_toggle(self, dashboard_content):
        """localStorage.setItem must be called in toggleLeftPanel."""
        assert re.search(
            r'localStorage\.setItem\(["\']leftPanelCollapsed["\']',
            dashboard_content
        ), "localStorage.setItem('leftPanelCollapsed', ...) not found"

    def test_localstorage_restore_on_load(self, dashboard_content):
        """localStorage.getItem must be used to restore panel state."""
        assert re.search(
            r'localStorage\.getItem\(["\']leftPanelCollapsed["\']',
            dashboard_content
        ), "localStorage.getItem('leftPanelCollapsed') not found"

    def test_panel_collapsed_class_toggled(self, dashboard_content):
        """classList.toggle('collapsed') must be used in toggleLeftPanel."""
        # Allow for toggle or add of 'collapsed' class
        assert re.search(
            r'classList\.(?:toggle|add)\(["\']collapsed["\']',
            dashboard_content
        ), "classList.toggle/add('collapsed') not found"
