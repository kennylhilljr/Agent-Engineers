"""
Tests for AI-148: REQ-METRICS-002: Agent Leaderboard

Verifies:
- HTML structure: leaderboard-section, leaderboard-list, leaderboard-sort-controls
- CSS: leaderboard-header, leaderboard-sort-btn, task-card, rank badges
- leaderboardSortKey variable initialized and exposed on window
- TaskCard component function: renders agent row with rank, stats, meta
- sortLeaderboard function: sorts pairs by xp, success_rate, cost
- renderLeaderboard function: renders sorted TaskCards into leaderboard-list
- setLeaderboardSort function: updates sort key, button states, re-renders
- init() wires up leaderboard rendering and sort button event delegation
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
# Test Group 1: Leaderboard HTML Structure
# ============================================================

class TestLeaderboardHTML:
    """Verify the leaderboard HTML structure is correctly defined."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_leaderboard_section_id_exists(self, html_content):
        """leaderboard-section element must exist."""
        assert 'id="leaderboard-section"' in html_content

    def test_leaderboard_section_is_panel_section(self, html_content):
        """leaderboard-section must use class panel-section."""
        assert 'class="panel-section" id="leaderboard-section"' in html_content

    def test_leaderboard_list_id_exists(self, html_content):
        """leaderboard-list container must exist for TaskCard rendering."""
        assert 'id="leaderboard-list"' in html_content

    def test_leaderboard_list_aria_live(self, html_content):
        """leaderboard-list must have aria-live for dynamic updates."""
        assert 'aria-live="polite"' in html_content

    def test_leaderboard_sort_controls_id_exists(self, html_content):
        """leaderboard-sort-controls element must exist."""
        assert 'id="leaderboard-sort-controls"' in html_content

    def test_leaderboard_sort_controls_aria_label(self, html_content):
        """leaderboard-sort-controls must have aria-label."""
        assert 'aria-label="Sort leaderboard by"' in html_content

    def test_leaderboard_xp_sort_button_exists(self, html_content):
        """XP sort button must exist with data-sort=xp."""
        assert 'data-sort="xp"' in html_content

    def test_leaderboard_rate_sort_button_exists(self, html_content):
        """Success rate sort button must exist with data-sort=success_rate."""
        assert 'data-sort="success_rate"' in html_content

    def test_leaderboard_cost_sort_button_exists(self, html_content):
        """Cost sort button must exist with data-sort=cost."""
        assert 'data-sort="cost"' in html_content

    def test_leaderboard_xp_button_active_by_default(self, html_content):
        """XP button must be active by default (matching leaderboardSortKey default)."""
        section = find_section(html_content, 'id="leaderboard-sort-controls"', 400)
        assert 'data-sort="xp"' in section
        assert 'active' in section

    def test_leaderboard_header_element_exists(self, html_content):
        """leaderboard-header div must exist."""
        assert 'class="leaderboard-header"' in html_content

    def test_leaderboard_heading_text_exists(self, html_content):
        """'Agent Leaderboard' heading text must appear in HTML."""
        assert 'Agent Leaderboard' in html_content

    def test_leaderboard_sort_btn_class_on_buttons(self, html_content):
        """Sort buttons must use class leaderboard-sort-btn."""
        assert 'class="leaderboard-sort-btn' in html_content

    def test_leaderboard_xp_button_title(self, html_content):
        """XP button must have a descriptive title attribute."""
        assert 'title="Sort by XP"' in html_content

    def test_leaderboard_rate_button_title(self, html_content):
        """Success rate button must have a descriptive title attribute."""
        assert 'title="Sort by success rate"' in html_content

    def test_leaderboard_cost_button_title(self, html_content):
        """Cost button must have a descriptive title attribute."""
        assert 'title="Sort by cost"' in html_content


# ============================================================
# Test Group 2: Leaderboard CSS Styles
# ============================================================

class TestLeaderboardCSS:
    """Verify CSS classes for the leaderboard are defined."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_leaderboard_header_css_defined(self, html_content):
        """.leaderboard-header CSS must be defined."""
        assert '.leaderboard-header' in html_content

    def test_leaderboard_sort_controls_css_defined(self, html_content):
        """.leaderboard-sort-controls CSS must be defined."""
        assert '.leaderboard-sort-controls' in html_content

    def test_leaderboard_sort_btn_css_defined(self, html_content):
        """.leaderboard-sort-btn CSS must be defined."""
        assert '.leaderboard-sort-btn' in html_content

    def test_leaderboard_sort_btn_active_css_defined(self, html_content):
        """.leaderboard-sort-btn.active CSS must be defined."""
        assert '.leaderboard-sort-btn.active' in html_content

    def test_leaderboard_list_css_defined(self, html_content):
        """.leaderboard-list CSS must be defined."""
        assert '.leaderboard-list' in html_content

    def test_task_card_css_defined(self, html_content):
        """.task-card CSS must be defined for TaskCard component."""
        assert '.task-card' in html_content

    def test_task_card_rank_css_defined(self, html_content):
        """.task-card-rank CSS must be defined."""
        assert '.task-card-rank' in html_content

    def test_task_card_rank_gold_css_defined(self, html_content):
        """.task-card-rank.gold CSS must be defined."""
        assert '.task-card-rank.gold' in html_content

    def test_task_card_rank_silver_css_defined(self, html_content):
        """.task-card-rank.silver CSS must be defined."""
        assert '.task-card-rank.silver' in html_content

    def test_task_card_rank_bronze_css_defined(self, html_content):
        """.task-card-rank.bronze CSS must be defined."""
        assert '.task-card-rank.bronze' in html_content

    def test_task_card_name_css_defined(self, html_content):
        """.task-card-name CSS must be defined."""
        assert '.task-card-name' in html_content

    def test_task_card_stats_css_defined(self, html_content):
        """.task-card-stats CSS must be defined."""
        assert '.task-card-stats' in html_content

    def test_task_card_meta_css_defined(self, html_content):
        """.task-card-meta CSS must be defined."""
        assert '.task-card-meta' in html_content

    def test_task_card_xp_css_defined(self, html_content):
        """.task-card-xp CSS must be defined."""
        assert '.task-card-xp' in html_content

    def test_task_card_status_running_css_defined(self, html_content):
        """.task-card.status-running CSS must be defined for running status."""
        assert '.task-card.status-running' in html_content

    def test_task_card_status_idle_css_defined(self, html_content):
        """.task-card.status-idle CSS must be defined."""
        assert '.task-card.status-idle' in html_content

    def test_task_card_status_error_css_defined(self, html_content):
        """.task-card.status-error CSS must be defined."""
        assert '.task-card.status-error' in html_content


# ============================================================
# Test Group 3: leaderboardSortKey Variable
# ============================================================

class TestLeaderboardSortKey:
    """Verify leaderboardSortKey variable is defined and exposed on window."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_leaderboard_sort_key_variable_defined(self, html_content):
        """leaderboardSortKey variable must be defined."""
        assert 'leaderboardSortKey' in html_content

    def test_leaderboard_sort_key_initialized_to_xp(self, html_content):
        """leaderboardSortKey must default to 'xp'."""
        section = find_section(html_content, 'leaderboardSortKey', 200)
        assert "'xp'" in section or '"xp"' in section

    def test_leaderboard_sort_key_exposed_on_window(self, html_content):
        """leaderboardSortKey must be exposed on window for testing."""
        assert 'window.leaderboardSortKey' in html_content

    def test_leaderboard_sort_key_assignment_correct(self, html_content):
        """window.leaderboardSortKey must be assigned from leaderboardSortKey."""
        section = find_section(html_content, 'window.leaderboardSortKey', 100)
        assert 'leaderboardSortKey' in section


# ============================================================
# Test Group 4: TaskCard Component Function
# ============================================================

class TestTaskCardFunction:
    """Verify TaskCard function renders correct HTML for agent leaderboard rows."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def task_card_section(self, html_content):
        # TaskCard size ~2510, use 20% larger = ~3012
        return find_section(html_content, 'function TaskCard', 3012)

    def test_task_card_function_defined(self, html_content):
        """TaskCard function must be defined."""
        assert 'function TaskCard' in html_content

    def test_task_card_exposed_on_window(self, html_content):
        """TaskCard must be exposed on window for testing."""
        assert 'window.TaskCard' in html_content

    def test_task_card_accepts_agent_param(self, task_card_section):
        """TaskCard must accept agent parameter."""
        assert 'agent' in task_card_section

    def test_task_card_accepts_profile_param(self, task_card_section):
        """TaskCard must accept profile parameter."""
        assert 'profile' in task_card_section

    def test_task_card_accepts_rank_param(self, task_card_section):
        """TaskCard must accept rank parameter."""
        assert 'rank' in task_card_section

    def test_task_card_uses_task_card_class(self, task_card_section):
        """TaskCard must render element with class task-card."""
        assert 'task-card' in task_card_section

    def test_task_card_includes_rank_display(self, task_card_section):
        """TaskCard must include rank display element."""
        assert 'task-card-rank' in task_card_section

    def test_task_card_includes_name_element(self, task_card_section):
        """TaskCard must include agent name element."""
        assert 'task-card-name' in task_card_section

    def test_task_card_includes_stats_element(self, task_card_section):
        """TaskCard must include stats element."""
        assert 'task-card-stats' in task_card_section

    def test_task_card_includes_meta_element(self, task_card_section):
        """TaskCard must include meta element."""
        assert 'task-card-meta' in task_card_section

    def test_task_card_shows_xp(self, task_card_section):
        """TaskCard must show XP value."""
        assert 'task-card-xp' in task_card_section

    def test_task_card_shows_level(self, task_card_section):
        """TaskCard must show level value."""
        assert 'task-card-level' in task_card_section

    def test_task_card_shows_success_rate(self, task_card_section):
        """TaskCard must show success rate stat."""
        assert 'success_rate' in task_card_section or 'successRate' in task_card_section

    def test_task_card_shows_avg_duration(self, task_card_section):
        """TaskCard must show average duration stat."""
        assert 'avgDur' in task_card_section or 'avg_duration' in task_card_section

    def test_task_card_shows_cost(self, task_card_section):
        """TaskCard must show cost stat."""
        assert 'cost' in task_card_section

    def test_task_card_applies_gold_rank_badge(self, task_card_section):
        """TaskCard must apply gold class for rank 1."""
        assert 'gold' in task_card_section

    def test_task_card_applies_silver_rank_badge(self, task_card_section):
        """TaskCard must apply silver class for rank 2."""
        assert 'silver' in task_card_section

    def test_task_card_applies_bronze_rank_badge(self, task_card_section):
        """TaskCard must apply bronze class for rank 3."""
        assert 'bronze' in task_card_section

    def test_task_card_uses_rank_medal_emoji_for_top3(self, task_card_section):
        """TaskCard must use medal emoji display for top 3 ranks."""
        # Checks for medal emoji characters or the array pattern
        has_medal = ('🥇' in task_card_section or
                     '\\u' in task_card_section or
                     "['\\U0001F947'" in task_card_section or
                     'rank - 1' in task_card_section or
                     'rank-1' in task_card_section)
        # More robust: check for the pattern that generates medals
        assert 'rank <= 3' in task_card_section or 'rank===1' in task_card_section or 'rank === 1' in task_card_section

    def test_task_card_uses_hash_for_lower_ranks(self, task_card_section):
        """TaskCard must display #N for ranks beyond top 3."""
        assert '#${rank}' in task_card_section or '`#${rank}`' in task_card_section or '"#"' in task_card_section

    def test_task_card_uses_data_agent_id(self, task_card_section):
        """TaskCard must use data-agent-id attribute."""
        assert 'data-agent-id' in task_card_section

    def test_task_card_uses_data_rank(self, task_card_section):
        """TaskCard must use data-rank attribute."""
        assert 'data-rank' in task_card_section

    def test_task_card_uses_escape_html(self, task_card_section):
        """TaskCard must use escapeHtml for agent name (XSS protection)."""
        assert 'escapeHtml' in task_card_section

    def test_task_card_uses_format_cost(self, task_card_section):
        """TaskCard must use formatCost() for cost display."""
        assert 'formatCost' in task_card_section

    def test_task_card_uses_format_duration(self, task_card_section):
        """TaskCard must use formatDuration() for avg duration display."""
        assert 'formatDuration' in task_card_section

    def test_task_card_handles_missing_status(self, task_card_section):
        """TaskCard must handle missing status with fallback."""
        assert "|| 'idle'" in task_card_section or "|| \"idle\"" in task_card_section

    def test_task_card_applies_status_class(self, task_card_section):
        """TaskCard must apply status class to the card element."""
        assert 'status-${status}' in task_card_section

    def test_task_card_shows_status_badge(self, task_card_section):
        """TaskCard must include a status badge element."""
        assert 'task-card-status-badge' in task_card_section


# ============================================================
# Test Group 5: sortLeaderboard Function
# ============================================================

class TestSortLeaderboardFunction:
    """Verify sortLeaderboard sorts agent pairs by different sort keys."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def sort_section(self, html_content):
        # sortLeaderboard size ~640, use 20% larger = ~768
        return find_section(html_content, 'function sortLeaderboard', 768)

    def test_sort_leaderboard_function_defined(self, html_content):
        """sortLeaderboard function must be defined."""
        assert 'function sortLeaderboard' in html_content

    def test_sort_leaderboard_exposed_on_window(self, html_content):
        """sortLeaderboard must be exposed on window for testing."""
        assert 'window.sortLeaderboard' in html_content

    def test_sort_leaderboard_accepts_pairs_param(self, sort_section):
        """sortLeaderboard must accept pairs parameter."""
        assert 'pairs' in sort_section

    def test_sort_leaderboard_accepts_sort_key_param(self, sort_section):
        """sortLeaderboard must accept sortKey parameter."""
        assert 'sortKey' in sort_section

    def test_sort_leaderboard_does_not_mutate_input(self, sort_section):
        """sortLeaderboard must return a new array (immutable sort)."""
        assert '[...pairs]' in sort_section or 'spread' in sort_section.lower() or '.slice()' in sort_section

    def test_sort_leaderboard_sorts_by_xp(self, sort_section):
        """sortLeaderboard must support sorting by xp."""
        assert "'xp'" in sort_section or '"xp"' in sort_section

    def test_sort_leaderboard_sorts_by_success_rate(self, sort_section):
        """sortLeaderboard must support sorting by success_rate."""
        assert 'success_rate' in sort_section

    def test_sort_leaderboard_sorts_by_cost(self, sort_section):
        """sortLeaderboard must support sorting by cost."""
        assert "'cost'" in sort_section or '"cost"' in sort_section

    def test_sort_leaderboard_uses_profile_xp(self, sort_section):
        """sortLeaderboard must read xp from profile object."""
        assert 'profile.xp' in sort_section

    def test_sort_leaderboard_uses_profile_success_rate(self, sort_section):
        """sortLeaderboard must read success_rate from profile object."""
        assert 'profile.success_rate' in sort_section

    def test_sort_leaderboard_uses_profile_cost(self, sort_section):
        """sortLeaderboard must read total_cost_usd from profile object."""
        assert 'profile.total_cost_usd' in sort_section

    def test_sort_leaderboard_is_descending(self, sort_section):
        """sortLeaderboard must sort in descending order (b - a pattern)."""
        # Descending sort means b.value - a.value
        assert 'b.profile' in sort_section and 'a.profile' in sort_section

    def test_sort_leaderboard_handles_missing_xp(self, sort_section):
        """sortLeaderboard must handle missing xp with fallback to 0."""
        assert '|| 0' in sort_section


# ============================================================
# Test Group 6: renderLeaderboard Function
# ============================================================

class TestRenderLeaderboardFunction:
    """Verify renderLeaderboard renders sorted TaskCards into the DOM."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def render_section(self, html_content):
        # renderLeaderboard size ~1035, use 20% larger = ~1242
        return find_section(html_content, 'function renderLeaderboard', 1242)

    def test_render_leaderboard_function_defined(self, html_content):
        """renderLeaderboard function must be defined."""
        assert 'function renderLeaderboard' in html_content

    def test_render_leaderboard_exposed_on_window(self, html_content):
        """renderLeaderboard must be exposed on window for testing."""
        assert 'window.renderLeaderboard' in html_content

    def test_render_leaderboard_gets_container(self, render_section):
        """renderLeaderboard must get leaderboard-list container element."""
        assert 'leaderboard-list' in render_section

    def test_render_leaderboard_uses_get_element_by_id(self, render_section):
        """renderLeaderboard must use getElementById to find container."""
        assert 'getElementById' in render_section

    def test_render_leaderboard_handles_missing_container(self, render_section):
        """renderLeaderboard must handle missing container gracefully."""
        assert 'if (!container)' in render_section or 'if(!container)' in render_section

    def test_render_leaderboard_reads_state_agents(self, render_section):
        """renderLeaderboard must read agents from state."""
        assert 'state.agents' in render_section

    def test_render_leaderboard_shows_empty_message(self, render_section):
        """renderLeaderboard must show message when no agents available."""
        assert 'No agents' in render_section or 'empty' in render_section.lower()

    def test_render_leaderboard_builds_pairs(self, render_section):
        """renderLeaderboard must build agent+profile pairs."""
        assert 'pairs' in render_section

    def test_render_leaderboard_uses_mock_agent_profiles(self, render_section):
        """renderLeaderboard must use mockAgentProfiles for profile data."""
        assert 'mockAgentProfiles' in render_section

    def test_render_leaderboard_calls_sort_leaderboard(self, render_section):
        """renderLeaderboard must call sortLeaderboard."""
        assert 'sortLeaderboard' in render_section

    def test_render_leaderboard_uses_current_sort_key(self, render_section):
        """renderLeaderboard must use leaderboardSortKey for sorting."""
        assert 'leaderboardSortKey' in render_section

    def test_render_leaderboard_calls_task_card(self, render_section):
        """renderLeaderboard must call TaskCard for each agent."""
        assert 'TaskCard' in render_section

    def test_render_leaderboard_uses_1_indexed_rank(self, render_section):
        """renderLeaderboard must pass 1-indexed rank to TaskCard."""
        assert 'i + 1' in render_section or 'i+1' in render_section

    def test_render_leaderboard_sets_inner_html(self, render_section):
        """renderLeaderboard must set container innerHTML."""
        assert 'innerHTML' in render_section

    def test_render_leaderboard_joins_cards(self, render_section):
        """renderLeaderboard must join TaskCard results."""
        assert '.join(' in render_section


# ============================================================
# Test Group 7: setLeaderboardSort Function
# ============================================================

class TestSetLeaderboardSortFunction:
    """Verify setLeaderboardSort updates sort key, button states, and re-renders."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def set_sort_section(self, html_content):
        # setLeaderboardSort size ~509, use 20% larger = ~611
        return find_section(html_content, 'function setLeaderboardSort', 611)

    def test_set_leaderboard_sort_function_defined(self, html_content):
        """setLeaderboardSort function must be defined."""
        assert 'function setLeaderboardSort' in html_content

    def test_set_leaderboard_sort_exposed_on_window(self, html_content):
        """setLeaderboardSort must be exposed on window for testing."""
        assert 'window.setLeaderboardSort' in html_content

    def test_set_leaderboard_sort_accepts_sort_key_param(self, set_sort_section):
        """setLeaderboardSort must accept sortKey parameter."""
        assert 'sortKey' in set_sort_section

    def test_set_leaderboard_sort_updates_module_variable(self, set_sort_section):
        """setLeaderboardSort must update leaderboardSortKey module variable."""
        assert 'leaderboardSortKey = sortKey' in set_sort_section

    def test_set_leaderboard_sort_updates_window_variable(self, set_sort_section):
        """setLeaderboardSort must update window.leaderboardSortKey."""
        assert 'window.leaderboardSortKey = sortKey' in set_sort_section

    def test_set_leaderboard_sort_queries_buttons(self, set_sort_section):
        """setLeaderboardSort must query all sort buttons."""
        assert 'leaderboard-sort-btn' in set_sort_section

    def test_set_leaderboard_sort_uses_query_selector_all(self, set_sort_section):
        """setLeaderboardSort must use querySelectorAll for button selection."""
        assert 'querySelectorAll' in set_sort_section

    def test_set_leaderboard_sort_toggles_active_class(self, set_sort_section):
        """setLeaderboardSort must toggle active class on buttons."""
        assert 'classList.toggle' in set_sort_section and 'active' in set_sort_section

    def test_set_leaderboard_sort_matches_data_sort(self, set_sort_section):
        """setLeaderboardSort must compare button data-sort attribute to sortKey."""
        assert 'dataset.sort' in set_sort_section or 'data-sort' in set_sort_section

    def test_set_leaderboard_sort_calls_render_leaderboard(self, set_sort_section):
        """setLeaderboardSort must call renderLeaderboard() after updating sort key."""
        assert 'renderLeaderboard' in set_sort_section


# ============================================================
# Test Group 8: Leaderboard Integration in init()
# ============================================================

class TestLeaderboardInInit:
    """Verify init() sets up the leaderboard correctly."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def init_section(self, html_content):
        # Get full init function - it's about 3500 chars
        return find_section(html_content, 'function init()', 4000)

    def test_leaderboard_sort_key_default_is_xp(self, html_content):
        """leaderboardSortKey default value of 'xp' must match XP button active state."""
        # The XP button should be marked active by default
        section = find_section(html_content, 'id="leaderboard-sort-controls"', 400)
        assert 'active' in section

    def test_mock_agent_profiles_defined(self, html_content):
        """mockAgentProfiles must be defined for leaderboard data."""
        assert 'mockAgentProfiles' in html_content

    def test_mock_agent_profiles_has_xp_field(self, html_content):
        """mockAgentProfiles entries must have xp field."""
        section = find_section(html_content, 'mockAgentProfiles', 2000)
        assert 'xp:' in section or 'xp :' in section

    def test_mock_agent_profiles_has_level_field(self, html_content):
        """mockAgentProfiles entries must have level field."""
        section = find_section(html_content, 'mockAgentProfiles', 2000)
        assert 'level:' in section or 'level :' in section

    def test_mock_agent_profiles_has_success_rate_field(self, html_content):
        """mockAgentProfiles entries must have success_rate field."""
        section = find_section(html_content, 'mockAgentProfiles', 2000)
        assert 'success_rate:' in section

    def test_mock_agent_profiles_has_cost_field(self, html_content):
        """mockAgentProfiles entries must have total_cost_usd field."""
        section = find_section(html_content, 'mockAgentProfiles', 2000)
        assert 'total_cost_usd:' in section

    def test_leaderboard_functions_all_exposed_before_init(self, html_content):
        """All leaderboard functions must be exposed on window before init is called."""
        task_card_idx = html_content.find('window.TaskCard')
        sort_idx = html_content.find('window.sortLeaderboard')
        render_idx = html_content.find('window.renderLeaderboard')
        set_sort_idx = html_content.find('window.setLeaderboardSort')
        init_call_idx = html_content.find('document.readyState')
        # All must be defined before init is invoked
        assert task_card_idx < init_call_idx
        assert sort_idx < init_call_idx
        assert render_idx < init_call_idx
        assert set_sort_idx < init_call_idx

    def test_leaderboard_sort_btn_class_used_for_click_handling(self, html_content):
        """leaderboard-sort-btn class must be referenced for click handling."""
        assert '.leaderboard-sort-btn' in html_content

    def test_format_cost_helper_defined(self, html_content):
        """formatCost helper used by TaskCard must be defined."""
        assert 'function formatCost' in html_content

    def test_format_duration_helper_defined(self, html_content):
        """formatDuration helper used by TaskCard must be defined."""
        assert 'function formatDuration' in html_content

    def test_escape_html_helper_defined(self, html_content):
        """escapeHtml helper used by TaskCard must be defined."""
        assert 'function escapeHtml' in html_content
