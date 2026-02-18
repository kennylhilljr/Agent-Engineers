"""
Tests for AI-145: REQ-MONITOR-003: Implement Agent Detail View

Verifies:
- Agent detail overlay HTML structure is present
- CSS classes for modal, panel, header, sections, stats, contributions, gamification
- mockAgentProfiles data structure with all AgentProfile fields
- ActivityItem() component function
- openAgentDetail() function exists and is window-exposed
- closeAgentDetail() function exists and is window-exposed
- Close button, overlay click, and Escape key handlers in init()
- Lifetime statistics section (invocations, success_rate, tokens, cost)
- Contributions section (commits, PRs, files, issues, messages, reviews)
- Gamification section (XP, level, streak, achievements)
- Strengths & Weaknesses section
- Model Assignment section
- Recent Event History section using ActivityItem
"""
import pytest
import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Test Group 1: HTML Structure — Agent Detail Overlay
# ============================================================

class TestAgentDetailOverlayHTML:
    """Verify the agent detail overlay HTML structure."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_agent_detail_overlay_exists(self, html_content):
        """agent-detail-overlay element must be present."""
        assert 'id="agent-detail-overlay"' in html_content

    def test_agent_detail_overlay_has_role_dialog(self, html_content):
        """Overlay must have role=dialog for accessibility."""
        assert 'role="dialog"' in html_content

    def test_agent_detail_overlay_has_aria_modal(self, html_content):
        """Overlay must have aria-modal=true."""
        assert 'aria-modal="true"' in html_content

    def test_agent_detail_panel_exists(self, html_content):
        """agent-detail-panel element must be present."""
        assert 'id="agent-detail-panel"' in html_content

    def test_agent_detail_header_exists(self, html_content):
        """agent-detail-header class must be present."""
        assert 'class="agent-detail-header"' in html_content

    def test_agent_detail_heading_exists(self, html_content):
        """agent-detail-heading element must be present."""
        assert 'id="agent-detail-heading"' in html_content

    def test_agent_detail_model_badge_exists(self, html_content):
        """agent-detail-model-badge element must be present."""
        assert 'id="agent-detail-model-badge"' in html_content

    def test_agent_detail_close_button_exists(self, html_content):
        """agent-detail-close button must be present."""
        assert 'id="agent-detail-close"' in html_content

    def test_agent_detail_close_aria_label(self, html_content):
        """Close button must have aria-label."""
        assert 'aria-label="Close agent detail view"' in html_content

    def test_agent_detail_body_exists(self, html_content):
        """agent-detail-body element must be present."""
        assert 'id="agent-detail-body"' in html_content

    def test_agent_detail_overlay_aria_labelledby(self, html_content):
        """Overlay must have aria-labelledby pointing to heading."""
        assert 'aria-labelledby="agent-detail-heading"' in html_content


# ============================================================
# Test Group 2: CSS Classes for Agent Detail View
# ============================================================

class TestAgentDetailCSS:
    """Verify CSS classes for the agent detail panel."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_agent_detail_overlay_css(self, html_content):
        """.agent-detail-overlay CSS class must be defined."""
        assert '.agent-detail-overlay' in html_content

    def test_agent_detail_overlay_open_css(self, html_content):
        """.agent-detail-overlay.open CSS class must be defined."""
        assert '.agent-detail-overlay.open' in html_content

    def test_agent_detail_panel_css(self, html_content):
        """.agent-detail-panel CSS class must be defined."""
        assert '.agent-detail-panel' in html_content

    def test_agent_detail_header_css(self, html_content):
        """.agent-detail-header CSS class must be defined."""
        assert '.agent-detail-header' in html_content

    def test_agent_detail_close_css(self, html_content):
        """.agent-detail-close CSS class must be defined."""
        assert '.agent-detail-close' in html_content

    def test_agent_detail_section_css(self, html_content):
        """.agent-detail-section CSS class must be defined."""
        assert '.agent-detail-section' in html_content

    def test_agent_detail_section_title_css(self, html_content):
        """.agent-detail-section-title CSS class must be defined."""
        assert '.agent-detail-section-title' in html_content

    def test_agent_profile_stats_grid_css(self, html_content):
        """.agent-profile-stats-grid CSS class must be defined."""
        assert '.agent-profile-stats-grid' in html_content

    def test_agent_profile_stat_css(self, html_content):
        """.agent-profile-stat CSS class must be defined."""
        assert '.agent-profile-stat' in html_content

    def test_agent_contributions_grid_css(self, html_content):
        """.agent-contributions-grid CSS class must be defined."""
        assert '.agent-contributions-grid' in html_content

    def test_agent_contribution_item_css(self, html_content):
        """.agent-contribution-item CSS class must be defined."""
        assert '.agent-contribution-item' in html_content

    def test_agent_gamification_row_css(self, html_content):
        """.agent-gamification-row CSS class must be defined."""
        assert '.agent-gamification-row' in html_content

    def test_agent_xp_block_css(self, html_content):
        """.agent-xp-block CSS class must be defined."""
        assert '.agent-xp-block' in html_content

    def test_agent_level_block_css(self, html_content):
        """.agent-level-block CSS class must be defined."""
        assert '.agent-level-block' in html_content

    def test_agent_streak_block_css(self, html_content):
        """.agent-streak-block CSS class must be defined."""
        assert '.agent-streak-block' in html_content

    def test_agent_achievements_css(self, html_content):
        """.agent-achievements CSS class must be defined."""
        assert '.agent-achievements' in html_content

    def test_agent_achievement_badge_css(self, html_content):
        """.agent-achievement-badge CSS class must be defined."""
        assert '.agent-achievement-badge' in html_content

    def test_agent_traits_row_css(self, html_content):
        """.agent-traits-row CSS class must be defined."""
        assert '.agent-traits-row' in html_content

    def test_agent_traits_group_css(self, html_content):
        """.agent-traits-group CSS class must be defined."""
        assert '.agent-traits-group' in html_content

    def test_activity_item_detail_css(self, html_content):
        """.activity-item-detail CSS class (ActivityItem component) must be defined."""
        assert '.activity-item-detail' in html_content

    def test_activity_item_status_icon_css(self, html_content):
        """.activity-item-status-icon CSS class must be defined."""
        assert '.activity-item-status-icon' in html_content

    def test_agent_no_events_css(self, html_content):
        """.agent-no-events CSS class must be defined."""
        assert '.agent-no-events' in html_content

    def test_agent_current_model_row_css(self, html_content):
        """.agent-current-model-row CSS class must be defined."""
        assert '.agent-current-model-row' in html_content


# ============================================================
# Test Group 3: mockAgentProfiles Data Structure
# ============================================================

class TestMockAgentProfiles:
    """Verify mockAgentProfiles contains all 13 agents with AgentProfile fields."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_mock_agent_profiles_defined(self, html_content):
        """mockAgentProfiles must be defined in JS."""
        assert 'mockAgentProfiles' in html_content

    def test_mock_agent_profiles_exposed_on_window(self, html_content):
        """mockAgentProfiles must be exposed on window for testing."""
        assert 'window.mockAgentProfiles' in html_content

    def test_profiles_have_total_invocations(self, html_content):
        """Profiles must include total_invocations field."""
        assert 'total_invocations' in html_content

    def test_profiles_have_success_rate(self, html_content):
        """Profiles must include success_rate field."""
        assert 'success_rate' in html_content

    def test_profiles_have_total_tokens(self, html_content):
        """Profiles must include total_tokens field."""
        # Check within mockAgentProfiles section
        idx = html_content.index('mockAgentProfiles')
        section = html_content[idx:idx + 3000]
        assert 'total_tokens' in section

    def test_profiles_have_total_cost_usd(self, html_content):
        """Profiles must include total_cost_usd field."""
        assert 'total_cost_usd' in html_content

    def test_profiles_have_xp_field(self, html_content):
        """Profiles must include xp field for gamification."""
        idx = html_content.index('mockAgentProfiles')
        section = html_content[idx:idx + 3000]
        assert 'xp:' in section

    def test_profiles_have_level_field(self, html_content):
        """Profiles must include level field."""
        idx = html_content.index('mockAgentProfiles')
        section = html_content[idx:idx + 3000]
        assert 'level:' in section

    def test_profiles_have_current_streak(self, html_content):
        """Profiles must include current_streak field."""
        assert 'current_streak' in html_content

    def test_profiles_have_achievements(self, html_content):
        """Profiles must include achievements list."""
        idx = html_content.index('mockAgentProfiles')
        section = html_content[idx:idx + 3000]
        assert 'achievements' in section

    def test_profiles_have_strengths(self, html_content):
        """Profiles must include strengths list."""
        idx = html_content.index('mockAgentProfiles')
        section = html_content[idx:idx + 3000]
        assert 'strengths' in section

    def test_profiles_have_weaknesses(self, html_content):
        """Profiles must include weaknesses list."""
        idx = html_content.index('mockAgentProfiles')
        section = html_content[idx:idx + 3000]
        assert 'weaknesses' in section

    def test_profiles_have_recent_events(self, html_content):
        """Profiles must include recent_events list."""
        idx = html_content.index('mockAgentProfiles')
        section = html_content[idx:idx + 3000]
        assert 'recent_events' in section

    def test_profiles_have_commits_made(self, html_content):
        """Profiles must include commits_made (contribution counter)."""
        assert 'commits_made' in html_content

    def test_profiles_have_prs_created(self, html_content):
        """Profiles must include prs_created (contribution counter)."""
        assert 'prs_created' in html_content

    def test_profiles_have_issues_created(self, html_content):
        """Profiles must include issues_created (contribution counter)."""
        assert 'issues_created' in html_content

    def test_profiles_have_messages_sent(self, html_content):
        """Profiles must include messages_sent (contribution counter)."""
        assert 'messages_sent' in html_content

    def test_profiles_have_reviews_completed(self, html_content):
        """Profiles must include reviews_completed (contribution counter)."""
        assert 'reviews_completed' in html_content

    def test_all_13_agents_have_profiles(self, html_content):
        """All 13 canonical agents must have profile entries."""
        agent_ids = ['linear', 'coding', 'github', 'slack', 'pr_reviewer', 'ops',
                     'coding_fast', 'pr_reviewer_fast', 'chatgpt', 'gemini', 'groq', 'kimi', 'windsurf']
        idx = html_content.index('mockAgentProfiles')
        section = html_content[idx:idx + 15000]
        for agent_id in agent_ids:
            assert agent_id in section, f"Profile missing for agent: {agent_id}"


# ============================================================
# Test Group 4: ActivityItem Component
# ============================================================

class TestActivityItemComponent:
    """Verify ActivityItem() component function."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_activity_item_function_defined(self, html_content):
        """ActivityItem function must be defined."""
        assert 'function ActivityItem' in html_content

    def test_activity_item_exposed_on_window(self, html_content):
        """ActivityItem must be exposed on window for testing."""
        assert 'window.ActivityItem' in html_content

    def test_activity_item_uses_status_class(self, html_content):
        """ActivityItem must use event.status as CSS class."""
        idx = html_content.index('function ActivityItem')
        section = html_content[idx:idx + 800]
        assert 'statusClass' in section or 'event.status' in section

    def test_activity_item_shows_ticket_key(self, html_content):
        """ActivityItem must display ticket_key."""
        idx = html_content.index('function ActivityItem')
        section = html_content[idx:idx + 800]
        assert 'ticket_key' in section

    def test_activity_item_shows_model(self, html_content):
        """ActivityItem must display model_used."""
        idx = html_content.index('function ActivityItem')
        section = html_content[idx:idx + 800]
        assert 'model_used' in section

    def test_activity_item_shows_tokens(self, html_content):
        """ActivityItem must display total_tokens."""
        idx = html_content.index('function ActivityItem')
        section = html_content[idx:idx + 800]
        assert 'total_tokens' in section

    def test_activity_item_shows_time(self, html_content):
        """ActivityItem must display started_at timestamp."""
        idx = html_content.index('function ActivityItem')
        section = html_content[idx:idx + 800]
        assert 'started_at' in section

    def test_activity_item_uses_activity_item_detail_class(self, html_content):
        """ActivityItem must use .activity-item-detail CSS class."""
        idx = html_content.index('function ActivityItem')
        section = html_content[idx:idx + 1500]
        assert 'activity-item-detail' in section

    def test_activity_item_uses_format_count(self, html_content):
        """ActivityItem must use formatCount() for token display."""
        idx = html_content.index('function ActivityItem')
        section = html_content[idx:idx + 800]
        assert 'formatCount' in section


# ============================================================
# Test Group 5: openAgentDetail() Function
# ============================================================

class TestOpenAgentDetailFunction:
    """Verify openAgentDetail() function implementation."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_open_agent_detail_defined(self, html_content):
        """openAgentDetail function must be defined."""
        assert 'function openAgentDetail' in html_content

    def test_open_agent_detail_exposed_on_window(self, html_content):
        """openAgentDetail must be exposed on window."""
        assert 'window.openAgentDetail' in html_content

    def test_open_agent_detail_shows_lifetime_stats(self, html_content):
        """openAgentDetail must show lifetime statistics section."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert 'Lifetime Statistics' in section or 'lifetime' in section.lower()

    def test_open_agent_detail_shows_contributions(self, html_content):
        """openAgentDetail must show contributions section."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert 'Contributions' in section or 'contribution' in section.lower()

    def test_open_agent_detail_shows_gamification(self, html_content):
        """openAgentDetail must show gamification section."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert 'Gamification' in section or 'gamification' in section.lower()

    def test_open_agent_detail_shows_xp(self, html_content):
        """openAgentDetail must display XP."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert 'xp' in section.lower() or 'XP' in section

    def test_open_agent_detail_shows_level(self, html_content):
        """openAgentDetail must display level."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert 'level' in section.lower()

    def test_open_agent_detail_shows_streak(self, html_content):
        """openAgentDetail must display streak."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert 'streak' in section.lower()

    def test_open_agent_detail_shows_achievements(self, html_content):
        """openAgentDetail must display achievements."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert 'achievement' in section.lower()

    def test_open_agent_detail_shows_strengths(self, html_content):
        """openAgentDetail must display strengths."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert 'Strengths' in section or 'strengths' in section

    def test_open_agent_detail_shows_weaknesses(self, html_content):
        """openAgentDetail must display weaknesses."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert 'Weaknesses' in section or 'weaknesses' in section

    def test_open_agent_detail_shows_model_assignment(self, html_content):
        """openAgentDetail must display model assignment."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert 'Model Assignment' in section or 'current model' in section.lower()

    def test_open_agent_detail_shows_event_history(self, html_content):
        """openAgentDetail must show recent event history."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert 'Event History' in section or 'recent_events' in section

    def test_open_agent_detail_uses_activity_item(self, html_content):
        """openAgentDetail must call ActivityItem() for event rendering."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert 'ActivityItem' in section

    def test_open_agent_detail_slices_20_events(self, html_content):
        """openAgentDetail must limit events to last 20."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert 'slice(0, 20)' in section or 'slice(0,20)' in section

    def test_open_agent_detail_opens_overlay(self, html_content):
        """openAgentDetail must add 'open' class to overlay."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert "classList.add('open')" in section

    def test_open_agent_detail_locks_body_scroll(self, html_content):
        """openAgentDetail must lock body scroll."""
        idx = html_content.index('function openAgentDetail')
        section = html_content[idx:idx + 11000]
        assert "document.body.style.overflow = 'hidden'" in section


# ============================================================
# Test Group 6: closeAgentDetail() Function
# ============================================================

class TestCloseAgentDetailFunction:
    """Verify closeAgentDetail() function implementation."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_close_agent_detail_defined(self, html_content):
        """closeAgentDetail function must be defined."""
        assert 'function closeAgentDetail' in html_content

    def test_close_agent_detail_exposed_on_window(self, html_content):
        """closeAgentDetail must be exposed on window."""
        assert 'window.closeAgentDetail' in html_content

    def test_close_agent_detail_removes_open_class(self, html_content):
        """closeAgentDetail must remove 'open' class from overlay."""
        idx = html_content.index('function closeAgentDetail')
        section = html_content[idx:idx + 500]
        assert "classList.remove('open')" in section

    def test_close_agent_detail_restores_body_scroll(self, html_content):
        """closeAgentDetail must restore body overflow."""
        idx = html_content.index('function closeAgentDetail')
        section = html_content[idx:idx + 500]
        assert "document.body.style.overflow = ''" in section


# ============================================================
# Test Group 7: Event Listeners for Closing
# ============================================================

class TestAgentDetailCloseHandlers:
    """Verify close button, overlay click, and Escape key handlers."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_close_button_listener_registered(self, html_content):
        """Close button must have click event listener registered in init()."""
        idx = html_content.index('function init')
        section = html_content[idx:idx + 2000]
        assert 'agent-detail-close' in section and 'closeAgentDetail' in section

    def test_overlay_click_closes_panel(self, html_content):
        """Clicking overlay background must close the panel."""
        idx = html_content.index('function init')
        section = html_content[idx:idx + 2000]
        assert 'agent-detail-overlay' in section and 'closeAgentDetail' in section

    def test_escape_key_closes_panel(self, html_content):
        """Pressing Escape key must close the panel."""
        idx = html_content.index('function init')
        section = html_content[idx:idx + 2000]
        assert "key === 'Escape'" in section or "key==='Escape'" in section

    def test_handle_agent_click_calls_open_detail(self, html_content):
        """handleAgentClick must call openAgentDetail()."""
        idx = html_content.index('function handleAgentClick')
        section = html_content[idx:idx + 500]
        assert 'openAgentDetail' in section

    def test_handle_agent_click_skips_active_task_clicks(self, html_content):
        """handleAgentClick must not open detail when clicking .agent-active-task."""
        idx = html_content.index('function handleAgentClick')
        section = html_content[idx:idx + 500]
        assert 'agent-active-task' in section


# ============================================================
# Test Group 8: Section Content Verification
# ============================================================

class TestOpenAgentDetailSections:
    """Verify the content of each section in openAgentDetail()."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def _get_open_detail_section(self, html_content, size=11000):
        idx = html_content.index('function openAgentDetail')
        return html_content[idx:idx + size]

    def test_lifetime_stats_shows_total_invocations(self, html_content):
        """Lifetime stats must show total_invocations."""
        section = self._get_open_detail_section(html_content)
        assert 'total_invocations' in section or 'Invocations' in section

    def test_lifetime_stats_shows_success_rate(self, html_content):
        """Lifetime stats must show success_rate."""
        section = self._get_open_detail_section(html_content)
        assert 'success_rate' in section or 'Success Rate' in section

    def test_contributions_shows_commits(self, html_content):
        """Contributions must show commits_made."""
        section = self._get_open_detail_section(html_content)
        assert 'commits_made' in section or 'Commits' in section

    def test_contributions_shows_prs(self, html_content):
        """Contributions must show prs_created."""
        section = self._get_open_detail_section(html_content)
        assert 'prs_created' in section or 'PRs' in section

    def test_contributions_shows_issues(self, html_content):
        """Contributions must show issues_created."""
        section = self._get_open_detail_section(html_content)
        assert 'issues_created' in section or 'Issues' in section

    def test_contributions_shows_messages(self, html_content):
        """Contributions must show messages_sent."""
        section = self._get_open_detail_section(html_content)
        assert 'messages_sent' in section or 'Messages' in section

    def test_contributions_shows_reviews(self, html_content):
        """Contributions must show reviews_completed."""
        section = self._get_open_detail_section(html_content)
        assert 'reviews_completed' in section or 'Reviews' in section

    def test_gamification_uses_xp_value_class(self, html_content):
        """Gamification must use .agent-xp-value CSS class."""
        section = self._get_open_detail_section(html_content)
        assert 'agent-xp-value' in section

    def test_gamification_uses_level_value_class(self, html_content):
        """Gamification must use .agent-level-value CSS class."""
        section = self._get_open_detail_section(html_content)
        assert 'agent-level-value' in section

    def test_gamification_uses_streak_value_class(self, html_content):
        """Gamification must use .agent-streak-value CSS class."""
        section = self._get_open_detail_section(html_content)
        assert 'agent-streak-value' in section

    def test_event_history_uses_slice_20(self, html_content):
        """Event history must slice to max 20 events."""
        section = self._get_open_detail_section(html_content)
        assert 'slice(0, 20)' in section or 'slice(0,20)' in section

    def test_no_events_message_present(self, html_content):
        """Must show 'No recent events' when events list is empty."""
        section = self._get_open_detail_section(html_content)
        assert 'No recent events' in section


# ============================================================
# Test Group 9: Live endpoint test — /api/agents/status still works
# ============================================================

class TestAgentsStatusStillWorksAfterAI145:
    """Verify /api/agents/status endpoint is unaffected by AI-145 changes."""

    @pytest.fixture
    def app(self):
        sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
        from dashboard_server import DashboardServer
        server = DashboardServer(project_dir=str(PROJECT_ROOT), project_name='test')
        return server.app

    @pytest.mark.asyncio
    async def test_agents_status_returns_13_agents(self, app):
        """After AI-145, /api/agents/status must still return 13 agents."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/agents/status')
            data = await resp.json()
            assert len(data['agents']) == 13

    @pytest.mark.asyncio
    async def test_agents_status_has_active_task_field(self, app):
        """After AI-145, each agent must still have active_task field."""
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/agents/status')
            data = await resp.json()
            for agent in data['agents']:
                assert 'active_task' in agent
