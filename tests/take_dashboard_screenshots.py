#!/usr/bin/env python3
"""Standalone script to take screenshots of the dashboard for AI-126.

This script:
1. Starts the dashboard server
2. Opens it in a browser via Playwright
3. Takes screenshots for evidence
4. Shuts down cleanly
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.dashboard_server import DashboardServer
from playwright.async_api import async_playwright
from aiohttp import web


async def main():
    """Main function to start server and take screenshots."""
    project_dir = PROJECT_ROOT
    screenshots_dir = PROJECT_ROOT / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    # Create server
    server = DashboardServer(
        project_dir=project_dir,
        host="127.0.0.1",
        port=8420,
        project_name="agent-dashboard"
    )

    # Start server
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, server.host, server.port)
    await site.start()

    print(f"Dashboard server started at http://{server.host}:{server.port}")

    # Give server time to start
    await asyncio.sleep(0.5)

    try:
        # Launch browser and take screenshots
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1400, "height": 900})

            url = f"http://{server.host}:{server.port}"
            print(f"Navigating to {url}...")
            await page.goto(url, wait_until="networkidle")

            # Wait for agents to load
            await page.wait_for_selector(".agent-card", timeout=10000)
            print("Dashboard loaded successfully!")

            # Give animations time to complete
            await asyncio.sleep(2)

            # Take full page screenshot
            screenshot_path = screenshots_dir / "ai-126-dashboard-phase1-full.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"Screenshot saved: {screenshot_path}")

            # Take viewport screenshot
            screenshot_path2 = screenshots_dir / "ai-126-dashboard-phase1-viewport.png"
            await page.screenshot(path=str(screenshot_path2), full_page=False)
            print(f"Screenshot saved: {screenshot_path2}")

            # Verify all agents are displayed
            agent_cards = await page.locator(".agent-card").count()
            print(f"Found {agent_cards} agent cards on dashboard")

            # Get global stats
            stat_cards = await page.locator(".stat-card").count()
            print(f"Found {stat_cards} stat cards")

            await browser.close()

    finally:
        # Cleanup
        print("Shutting down server...")
        await runner.cleanup()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
