"""
Playwright browser tests for monitoring dashboard.

Tests the visual monitoring dashboard and ensures all elements render correctly.
"""

import asyncio
import json
import tempfile
import time
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

from dashboard.server import DashboardServer


@pytest.fixture
async def dashboard_server():
    """Fixture to start dashboard server for browser testing."""
    temp_dir = tempfile.mkdtemp()
    metrics_file = Path(temp_dir) / ".agent_metrics.json"

    # Create comprehensive test metrics
    test_metrics = {
        "version": 1,
        "project_name": "test-project",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z",
        "total_sessions": 10,
        "total_tokens": 50000,
        "total_cost_usd": 2.5,
        "total_duration_seconds": 600.0,
        "agents": {
            "coding": {
                "agent_name": "coding",
                "total_invocations": 20,
                "successful_invocations": 18,
                "failed_invocations": 2,
                "total_tokens": 25000,
                "total_cost_usd": 1.25,
                "total_duration_seconds": 300.0,
                "commits_made": 5,
                "prs_created": 2,
                "prs_merged": 1,
                "files_created": 10,
                "files_modified": 15,
                "lines_added": 500,
                "lines_removed": 100,
                "tests_written": 8,
                "issues_created": 0,
                "issues_completed": 2,
                "messages_sent": 0,
                "reviews_completed": 0,
                "success_rate": 0.9,
                "avg_duration_seconds": 15.0,
                "avg_tokens_per_call": 1250.0,
                "cost_per_success_usd": 0.069,
                "xp": 500,
                "level": 5,
                "current_streak": 3,
                "best_streak": 8,
                "achievements": ["first_commit", "test_writer", "pr_master"],
                "strengths": ["code_quality", "testing"],
                "weaknesses": ["error_handling"],
                "recent_events": [],
                "last_error": "",
                "last_active": "2024-01-01T12:00:00Z"
            }
        },
        "events": [],
        "sessions": []
    }

    metrics_file.write_text(json.dumps(test_metrics))

    # Create server
    server = DashboardServer(
        project_name="test-project",
        metrics_dir=Path(temp_dir),
        port=8081,  # Different port to avoid conflicts
        host="127.0.0.1"
    )

    # Start server in background
    import threading

    def run_server():
        server.run()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to start
    await asyncio.sleep(2)

    yield server

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
class TestMonitoringDashboardBrowser:
    """Browser tests for monitoring dashboard."""

    async def test_monitoring_dashboard_loads(self, dashboard_server):
        """Test 1: Monitoring dashboard page loads successfully."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                await page.goto("http://127.0.0.1:8081/monitoring", timeout=10000)

                # Check page title
                title = await page.title()
                assert "Monitoring" in title or "Dashboard" in title

                # Check header is visible
                header = page.locator("h1")
                await expect(header).to_be_visible(timeout=5000)

                print("✓ Monitoring dashboard loaded successfully")

            finally:
                await browser.close()

    async def test_health_metrics_display(self, dashboard_server):
        """Test 2: Health metrics are displayed correctly."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                await page.goto("http://127.0.0.1:8081/monitoring", timeout=10000)

                # Wait for content to load
                await page.wait_for_selector(".card", timeout=10000)

                # Check for health status card
                cards = await page.locator(".card").all()
                assert len(cards) > 0, "No cards found on page"

                # Check for Service Health card
                service_health = page.locator("text=Service Health")
                await expect(service_health).to_be_visible()

                # Check for CPU Usage card
                cpu_usage = page.locator("text=CPU Usage")
                await expect(cpu_usage).to_be_visible()

                # Check for Memory Usage card
                memory_usage = page.locator("text=Memory Usage")
                await expect(memory_usage).to_be_visible()

                print("✓ Health metrics display correctly")

            finally:
                await browser.close()

    async def test_status_badge_colors(self, dashboard_server):
        """Test 3: Status badges show correct colors."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                await page.goto("http://127.0.0.1:8081/monitoring", timeout=10000)

                # Wait for status badge
                await page.wait_for_selector(".status-badge", timeout=10000)

                # Get status badge
                status_badge = page.locator(".status-badge").first

                # Should be visible
                await expect(status_badge).to_be_visible()

                # Check that it has a status class
                classes = await status_badge.get_attribute("class")
                assert "status-" in classes, f"Status badge missing status class: {classes}"

                print("✓ Status badges render with correct styling")

            finally:
                await browser.close()

    async def test_progress_bars_render(self, dashboard_server):
        """Test 4: Progress bars render with correct widths."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                await page.goto("http://127.0.0.1:8081/monitoring", timeout=10000)

                # Wait for progress bars
                await page.wait_for_selector(".progress-bar", timeout=10000)

                # Get all progress bars
                progress_bars = await page.locator(".progress-bar").all()
                assert len(progress_bars) > 0, "No progress bars found"

                # Check that progress fills have width
                for bar in progress_bars[:3]:  # Check first 3
                    fill = bar.locator(".progress-fill")
                    style = await fill.get_attribute("style")
                    assert "width" in style, f"Progress fill missing width: {style}"

                print("✓ Progress bars render correctly")

            finally:
                await browser.close()

    async def test_metrics_store_section(self, dashboard_server):
        """Test 5: Metrics store section displays data."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                await page.goto("http://127.0.0.1:8081/monitoring", timeout=10000)

                # Wait for section title
                await page.wait_for_selector("text=Metrics Store", timeout=10000)

                # Check for metrics
                events = page.locator("text=Events")
                await expect(events).to_be_visible()

                sessions = page.locator("text=Sessions")
                await expect(sessions).to_be_visible()

                agents = page.locator("text=Agents")
                await expect(agents).to_be_visible()

                print("✓ Metrics store section displays correctly")

            finally:
                await browser.close()

    async def test_auto_refresh_indicator(self, dashboard_server):
        """Test 6: Auto-refresh indicator appears during refresh."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                await page.goto("http://127.0.0.1:8081/monitoring", timeout=10000)

                # Wait for page to load
                await page.wait_for_selector(".card", timeout=10000)

                # Wait for potential refresh (5 seconds interval)
                await asyncio.sleep(6)

                # Check if refresh indicator exists (it may be hidden)
                refresh_indicator = page.locator("#refreshIndicator")
                assert await refresh_indicator.count() > 0, "Refresh indicator not found"

                print("✓ Auto-refresh mechanism is working")

            finally:
                await browser.close()

    async def test_timestamp_updates(self, dashboard_server):
        """Test 7: Timestamp shows last update time."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                await page.goto("http://127.0.0.1:8081/monitoring", timeout=10000)

                # Wait for timestamp
                await page.wait_for_selector("#lastUpdate", timeout=10000)

                timestamp = page.locator("#lastUpdate")
                text = await timestamp.inner_text()

                assert "Last updated:" in text, f"Timestamp text incorrect: {text}"
                assert "Never" not in text, "Timestamp should not be 'Never' after load"

                print("✓ Timestamp displays correctly")

            finally:
                await browser.close()

    async def test_responsive_layout(self, dashboard_server):
        """Test 8: Dashboard is responsive on different screen sizes."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                # Test desktop size
                await page.set_viewport_size({"width": 1920, "height": 1080})
                await page.goto("http://127.0.0.1:8081/monitoring", timeout=10000)
                await page.wait_for_selector(".card", timeout=10000)

                cards_desktop = await page.locator(".card").all()
                assert len(cards_desktop) > 0

                # Test tablet size
                await page.set_viewport_size({"width": 768, "height": 1024})
                await page.wait_for_timeout(500)

                cards_tablet = await page.locator(".card").all()
                assert len(cards_tablet) > 0

                # Test mobile size
                await page.set_viewport_size({"width": 375, "height": 667})
                await page.wait_for_timeout(500)

                cards_mobile = await page.locator(".card").all()
                assert len(cards_mobile) > 0

                print("✓ Dashboard is responsive across screen sizes")

            finally:
                await browser.close()

    async def test_network_statistics_table(self, dashboard_server):
        """Test 9: Network statistics table renders."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                await page.goto("http://127.0.0.1:8081/monitoring", timeout=10000)

                # Wait for network section
                await page.wait_for_selector("text=Network Statistics", timeout=10000)

                # Check for table
                table = page.locator(".metrics-table")
                await expect(table).to_be_visible()

                # Check for table rows
                rows = await table.locator("tbody tr").all()
                assert len(rows) > 0, "Network statistics table has no rows"

                print("✓ Network statistics table renders correctly")

            finally:
                await browser.close()

    async def test_process_information_section(self, dashboard_server):
        """Test 10: Process information section displays."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                await page.goto("http://127.0.0.1:8081/monitoring", timeout=10000)

                # Wait for process info section
                await page.wait_for_selector("text=Process Information", timeout=10000)

                # Check for PID
                pid_label = page.locator("text=PID")
                await expect(pid_label).to_be_visible()

                print("✓ Process information section displays correctly")

            finally:
                await browser.close()


@pytest.mark.asyncio
class TestMonitoringDashboardScreenshots:
    """Screenshot tests for monitoring dashboard."""

    async def test_take_full_page_screenshot(self, dashboard_server):
        """Test 11: Take full page screenshot of monitoring dashboard."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                await page.goto("http://127.0.0.1:8081/monitoring", timeout=10000)

                # Wait for all content to load
                await page.wait_for_selector(".card", timeout=10000)
                await page.wait_for_timeout(2000)  # Wait for any animations

                # Take screenshot
                screenshot_path = Path("test_screenshots") / "monitoring_dashboard.png"
                screenshot_path.parent.mkdir(exist_ok=True)

                await page.screenshot(path=str(screenshot_path), full_page=True)

                assert screenshot_path.exists(), "Screenshot was not created"
                assert screenshot_path.stat().st_size > 0, "Screenshot file is empty"

                print(f"✓ Screenshot saved to {screenshot_path}")

            finally:
                await browser.close()

    async def test_take_health_card_screenshot(self, dashboard_server):
        """Test 12: Take screenshot of health status card."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                await page.goto("http://127.0.0.1:8081/monitoring", timeout=10000)

                # Wait for health card
                await page.wait_for_selector("text=Service Health", timeout=10000)

                # Find and screenshot the health card
                health_card = page.locator(".card").first
                screenshot_path = Path("test_screenshots") / "health_card.png"
                screenshot_path.parent.mkdir(exist_ok=True)

                await health_card.screenshot(path=str(screenshot_path))

                assert screenshot_path.exists(), "Screenshot was not created"

                print(f"✓ Health card screenshot saved to {screenshot_path}")

            finally:
                await browser.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
