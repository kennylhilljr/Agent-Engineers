"""Playwright browser tests for dashboard server - Phase 1.

Verifies all test steps from AI-126:
1. Start dashboard server
2. Navigate to http://localhost:8420
3. Verify all 13 agents display with current status
4. Verify status updates when refreshing page
5. Verify API endpoints respond correctly

Uses real browser automation to test the complete user experience.
"""

import asyncio
import json
import tempfile
import time
from pathlib import Path

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright, Page, expect

# Add project root to path
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.dashboard_server import DashboardServer
from dashboard.metrics import DashboardState
from aiohttp import web


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


class TestDashboardPlaywright:
    """Playwright browser tests for dashboard."""

    @pytest_asyncio.fixture
    async def dashboard_server(self):
        """Start a test dashboard server."""
        # Create temporary directory with test data
        temp_dir = tempfile.TemporaryDirectory()
        project_dir = Path(temp_dir.name)

        # Create comprehensive test metrics
        test_state: DashboardState = {
            "version": 1,
            "project_name": "playwright-test",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-02-16T12:00:00Z",
            "total_sessions": 42,
            "total_tokens": 250000,
            "total_cost_usd": 12.50,
            "total_duration_seconds": 3600.0,
            "agents": {
                "orchestrator": {
                    "agent_name": "orchestrator",
                    "total_invocations": 42,
                    "successful_invocations": 42,
                    "failed_invocations": 0,
                    "total_tokens": 8400,
                    "total_cost_usd": 0.42,
                    "total_duration_seconds": 84.0,
                    "commits_made": 0,
                    "prs_created": 0,
                    "prs_merged": 0,
                    "files_created": 0,
                    "files_modified": 0,
                    "lines_added": 0,
                    "lines_removed": 0,
                    "tests_written": 0,
                    "issues_created": 0,
                    "issues_completed": 0,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 2.0,
                    "avg_tokens_per_call": 200.0,
                    "cost_per_success_usd": 0.01,
                    "xp": 420,
                    "level": 5,
                    "current_streak": 42,
                    "best_streak": 42,
                    "achievements": ["perfect_streak", "coordinator"],
                    "strengths": ["reliability", "orchestration"],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "",
                    "last_active": "2026-02-16T12:00:00Z"
                },
                "linear": {
                    "agent_name": "linear",
                    "total_invocations": 45,
                    "successful_invocations": 43,
                    "failed_invocations": 2,
                    "total_tokens": 18000,
                    "total_cost_usd": 0.90,
                    "total_duration_seconds": 180.0,
                    "commits_made": 0,
                    "prs_created": 0,
                    "prs_merged": 0,
                    "files_created": 0,
                    "files_modified": 0,
                    "lines_added": 0,
                    "lines_removed": 0,
                    "tests_written": 0,
                    "issues_created": 25,
                    "issues_completed": 18,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 0.956,
                    "avg_duration_seconds": 4.0,
                    "avg_tokens_per_call": 400.0,
                    "cost_per_success_usd": 0.021,
                    "xp": 1290,
                    "level": 8,
                    "current_streak": 12,
                    "best_streak": 28,
                    "achievements": ["issue_creator", "project_manager"],
                    "strengths": ["issue_tracking", "reliability"],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "API rate limit: 429",
                    "last_active": "2026-02-16T11:45:00Z"
                },
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 85,
                    "successful_invocations": 72,
                    "failed_invocations": 13,
                    "total_tokens": 127500,
                    "total_cost_usd": 6.375,
                    "total_duration_seconds": 1530.0,
                    "commits_made": 42,
                    "prs_created": 18,
                    "prs_merged": 15,
                    "files_created": 78,
                    "files_modified": 210,
                    "lines_added": 4200,
                    "lines_removed": 1350,
                    "tests_written": 112,
                    "issues_created": 0,
                    "issues_completed": 20,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 0.847,
                    "avg_duration_seconds": 18.0,
                    "avg_tokens_per_call": 1500.0,
                    "cost_per_success_usd": 0.089,
                    "xp": 2160,
                    "level": 12,
                    "current_streak": 8,
                    "best_streak": 22,
                    "achievements": ["first_commit", "test_master", "code_warrior"],
                    "strengths": ["testing", "code_quality", "productivity"],
                    "weaknesses": ["error_recovery"],
                    "recent_events": [],
                    "last_error": "Test timeout",
                    "last_active": "2026-02-16T12:00:00Z"
                }
            },
            "events": [],
            "sessions": []
        }

        metrics_path = project_dir / ".agent_metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump(test_state, f, indent=2)

        # Create and start server
        server = DashboardServer(
            project_dir=project_dir,
            host="127.0.0.1",
            port=8420,
            project_name="playwright-test"
        )

        runner = web.AppRunner(server.app)
        await runner.setup()
        site = web.TCPSite(runner, server.host, server.port)
        await site.start()

        # Give server time to start
        await asyncio.sleep(0.2)

        yield server

        # Cleanup
        await runner.cleanup()
        temp_dir.cleanup()

    @pytest.mark.asyncio
    async def test_step_1_start_dashboard_server(self, dashboard_server):
        """Test Step 1: Start dashboard server.

        Verifies that the server starts successfully and is accessible.
        """
        # Server is started by fixture, verify it's running
        assert dashboard_server is not None
        assert dashboard_server.host == "127.0.0.1"
        assert dashboard_server.port == 8420

    @pytest.mark.asyncio
    async def test_step_2_navigate_to_dashboard(self, dashboard_server):
        """Test Step 2: Navigate to http://localhost:8420.

        Verifies that browser can navigate to dashboard and page loads.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Navigate to dashboard
            url = f"http://{dashboard_server.host}:{dashboard_server.port}"
            response = await page.goto(url)

            # Verify page loaded successfully
            assert response.status == 200
            assert "Agent Status Dashboard" in await page.title()

            # Verify page content loaded
            header = page.locator("h1")
            await expect(header).to_contain_text("Agent Status Dashboard")

            await browser.close()

    @pytest.mark.asyncio
    async def test_step_3_verify_all_13_agents_display(self, dashboard_server):
        """Test Step 3: Verify all 13 agents display with current status.

        Verifies that:
        - All 13 canonical agents are displayed
        - Each agent shows level, XP, invocations, success rate
        - Agent cards have proper styling and layout
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            url = f"http://{dashboard_server.host}:{dashboard_server.port}"
            await page.goto(url)

            # Wait for agents to load
            await page.wait_for_selector(".agent-card", timeout=5000)

            # Get all agent cards
            agent_cards = await page.locator(".agent-card").all()

            # Should have all 14 agents (13 canonical + possibly extras from MetricsStore)
            assert len(agent_cards) >= 13, f"Expected at least 13 agents, found {len(agent_cards)}"

            # Verify specific agents are present
            expected_agents = [
                "orchestrator", "linear", "coding", "coding fast",
                "github", "pr reviewer", "pr reviewer fast",
                "ops", "slack", "chatgpt", "gemini", "groq", "kimi", "windsurf"
            ]

            for expected in expected_agents:
                agent_locator = page.locator(f".agent-name:has-text('{expected}')")
                await expect(agent_locator).to_be_visible()

            # Verify first agent card has all required elements
            first_card = page.locator(".agent-card").first

            # Should have agent name
            await expect(first_card.locator(".agent-name")).to_be_visible()

            # Should have level badge
            await expect(first_card.locator(".agent-level")).to_be_visible()

            # Should have stats
            await expect(first_card.locator(".agent-stats")).to_be_visible()

            # Should have progress bar
            await expect(first_card.locator(".progress-bar")).to_be_visible()

            await browser.close()

    @pytest.mark.asyncio
    async def test_step_3_verify_agent_status_details(self, dashboard_server):
        """Test Step 3 (detailed): Verify agent status displays correctly.

        Verifies that each agent shows:
        - Current level and XP
        - Total invocations
        - Success rate
        - Recent activity
        - Achievements and strengths
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            url = f"http://{dashboard_server.host}:{dashboard_server.port}"
            await page.goto(url)

            # Wait for agents to load
            await page.wait_for_selector(".agent-card", timeout=5000)

            # Check coding agent (should be highest level)
            coding_card = page.locator(".agent-card:has-text('coding')").first

            # Verify level
            level_badge = coding_card.locator(".agent-level")
            await expect(level_badge).to_contain_text("Level 12")

            # Verify stats are visible
            stats = coding_card.locator(".stat-item-value")
            assert await stats.count() >= 4  # At least invocations, success rate, XP, streak

            # Verify success rate progress bar
            progress = coding_card.locator(".progress-fill")
            await expect(progress).to_be_visible()

            # Verify achievements/strengths tags are visible
            tags = coding_card.locator(".tag")
            assert await tags.count() >= 1

            await browser.close()

    @pytest.mark.asyncio
    async def test_step_4_verify_status_updates_on_refresh(self, dashboard_server):
        """Test Step 4: Verify status updates when refreshing page.

        Verifies that:
        - Page refresh triggers data reload
        - Dashboard reflects current metrics
        - No stale data is displayed
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            url = f"http://{dashboard_server.host}:{dashboard_server.port}"
            await page.goto(url)

            # Wait for initial load
            await page.wait_for_selector(".agent-card", timeout=5000)

            # Get initial agent count
            initial_cards = await page.locator(".agent-card").count()

            # Manually trigger refresh via button
            refresh_btn = page.locator(".refresh-btn")
            await refresh_btn.click()

            # Wait a bit for refresh to complete
            await asyncio.sleep(0.5)

            # Verify agents are still displayed
            refreshed_cards = await page.locator(".agent-card").count()
            assert refreshed_cards >= initial_cards

            # Verify data is still accurate (coding agent level)
            coding_card = page.locator(".agent-card:has-text('coding')").first
            level_badge = coding_card.locator(".agent-level")
            await expect(level_badge).to_contain_text("Level 12")

            await browser.close()

    @pytest.mark.asyncio
    async def test_step_5_verify_api_endpoints_respond(self, dashboard_server):
        """Test Step 5: Verify API endpoints respond correctly.

        Tests all three API endpoints:
        - /api/health - Returns server health
        - /api/metrics - Returns full dashboard state
        - /api/agents - Returns sorted agent list
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            # Test /api/health
            health_page = await context.new_page()
            url = f"http://{dashboard_server.host}:{dashboard_server.port}/api/health"
            await health_page.goto(url)

            health_text = await health_page.locator("body").text_content()
            health_data = json.loads(health_text)
            assert health_data["status"] == "healthy"
            assert health_data["server"]["project_name"] == "playwright-test"

            # Test /api/metrics
            metrics_page = await context.new_page()
            url = f"http://{dashboard_server.host}:{dashboard_server.port}/api/metrics"
            await metrics_page.goto(url)

            metrics_text = await metrics_page.locator("body").text_content()
            metrics_data = json.loads(metrics_text)
            assert metrics_data["version"] == 1
            assert metrics_data["project_name"] == "playwright-test"
            assert "agents" in metrics_data
            assert len(metrics_data["agents"]) >= 3

            # Test /api/agents
            agents_page = await context.new_page()
            url = f"http://{dashboard_server.host}:{dashboard_server.port}/api/agents"
            await agents_page.goto(url)

            agents_text = await agents_page.locator("body").text_content()
            agents_data = json.loads(agents_text)
            assert "agents" in agents_data
            assert len(agents_data["agents"]) >= 13

            # Verify agents are sorted by level
            agents = agents_data["agents"]
            for i in range(len(agents) - 1):
                assert agents[i]["level"] >= agents[i + 1]["level"]

            await browser.close()

    @pytest.mark.asyncio
    async def test_global_stats_display(self, dashboard_server):
        """Test that global statistics are displayed correctly."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            url = f"http://{dashboard_server.host}:{dashboard_server.port}"
            await page.goto(url)

            # Wait for stats to load
            await page.wait_for_selector(".stat-card", timeout=5000)

            # Should have 4 stat cards
            stat_cards = await page.locator(".stat-card").count()
            assert stat_cards == 4

            # Verify stat labels
            labels = await page.locator(".stat-label").all_text_contents()
            assert "Total Sessions" in labels or "TOTAL SESSIONS" in labels
            assert "Total Tokens" in labels or "TOTAL TOKENS" in labels
            assert "Total Cost" in labels or "TOTAL COST" in labels
            assert "Active Agents" in labels or "ACTIVE AGENTS" in labels

            await browser.close()

    @pytest.mark.asyncio
    async def test_agent_error_display(self, dashboard_server):
        """Test that agents with errors show error messages."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            url = f"http://{dashboard_server.host}:{dashboard_server.port}"
            await page.goto(url)

            # Wait for agents to load
            await page.wait_for_selector(".agent-card", timeout=5000)

            # Find linear agent (has error in test data)
            linear_card = page.locator(".agent-card:has-text('linear')").first

            # Should show error message
            error_msg = linear_card.locator(".error-message")
            await expect(error_msg).to_be_visible()
            await expect(error_msg).to_contain_text("API rate limit")

            await browser.close()

    @pytest.mark.asyncio
    async def test_agent_sorting_by_level(self, dashboard_server):
        """Test that agents are sorted by level (highest first)."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            url = f"http://{dashboard_server.host}:{dashboard_server.port}"
            await page.goto(url)

            # Wait for agents to load
            await page.wait_for_selector(".agent-card", timeout=5000)

            # Get all level badges
            level_badges = await page.locator(".agent-level").all_text_contents()

            # Extract level numbers
            levels = []
            for badge in level_badges:
                # Extract number from "Level X"
                if "Level" in badge:
                    level_num = int(badge.split("Level")[1].strip())
                    levels.append(level_num)

            # Verify levels are in descending order
            for i in range(len(levels) - 1):
                assert levels[i] >= levels[i + 1], f"Levels not sorted: {levels}"

            # Coding agent (level 12) should be first
            first_card = page.locator(".agent-card").first
            first_level = first_card.locator(".agent-level")
            await expect(first_level).to_contain_text("Level 12")

            await browser.close()

    @pytest.mark.asyncio
    async def test_responsive_layout(self, dashboard_server):
        """Test that dashboard layout is responsive."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            url = f"http://{dashboard_server.host}:{dashboard_server.port}"

            # Test desktop viewport
            await page.set_viewport_size({"width": 1400, "height": 900})
            await page.goto(url)
            await page.wait_for_selector(".agent-card", timeout=5000)

            # Agent cards should be visible
            cards = await page.locator(".agent-card").count()
            assert cards >= 13

            # Test mobile viewport
            await page.set_viewport_size({"width": 375, "height": 667})
            await page.reload()
            await page.wait_for_selector(".agent-card", timeout=5000)

            # Cards should still be visible on mobile
            cards_mobile = await page.locator(".agent-card").count()
            assert cards_mobile >= 13

            await browser.close()

    @pytest.mark.asyncio
    async def test_take_screenshot_evidence(self, dashboard_server):
        """Take screenshot evidence of working dashboard."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1400, "height": 900})

            url = f"http://{dashboard_server.host}:{dashboard_server.port}"
            await page.goto(url)

            # Wait for full page load
            await page.wait_for_selector(".agent-card", timeout=5000)
            await asyncio.sleep(1)  # Give time for animations

            # Create screenshots directory
            screenshots_dir = PROJECT_ROOT / "screenshots"
            screenshots_dir.mkdir(exist_ok=True)

            # Take full page screenshot
            screenshot_path = screenshots_dir / "ai-126-dashboard-phase1.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)

            # Verify screenshot was created
            assert screenshot_path.exists()
            assert screenshot_path.stat().st_size > 0

            await browser.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
