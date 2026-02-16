#!/usr/bin/env python3
"""
Screenshot capture script for File Change Summary feature
Takes screenshots of different test scenarios for AI-100
"""

import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

async def take_screenshots():
    """Capture screenshots of file change summary in different states"""

    test_file = Path(__file__).parent.parent / "test_file_changes.html"
    screenshots_dir = Path(__file__).parent.parent.parent / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1400, 'height': 1000})

        # Navigate to test file
        await page.goto(f"file://{test_file.absolute()}")

        # Wait for page to load
        await page.wait_for_selector('.container', timeout=5000)

        # Scenario 1: With file changes (default)
        print("📸 Taking screenshot 1: File changes displayed...")
        await page.screenshot(
            path=str(screenshots_dir / "ai100_file_changes_with_data.png"),
            full_page=True
        )

        # Scenario 2: Expand a diff view
        print("📸 Taking screenshot 2: Expanded diff view...")
        await page.click('.file-change-header')
        await page.wait_for_timeout(500)
        await page.screenshot(
            path=str(screenshots_dir / "ai100_file_changes_expanded_diff.png"),
            full_page=True
        )

        # Scenario 3: Empty state
        print("📸 Taking screenshot 3: Empty state...")
        await page.click('button:has-text("2. Empty State")')
        await page.wait_for_timeout(500)
        await page.screenshot(
            path=str(screenshots_dir / "ai100_file_changes_empty_state.png"),
            full_page=True
        )

        # Scenario 4: Multiple file types
        print("📸 Taking screenshot 4: Multiple file types...")
        await page.click('button:has-text("3. Multiple File Types")')
        await page.wait_for_timeout(500)
        await page.screenshot(
            path=str(screenshots_dir / "ai100_file_changes_multiple_types.png"),
            full_page=True
        )

        # Scenario 5: All change types (created/modified/deleted)
        print("📸 Taking screenshot 5: All change types...")
        await page.click('button:has-text("5. All Change Types")')
        await page.wait_for_timeout(500)
        await page.screenshot(
            path=str(screenshots_dir / "ai100_file_changes_all_types.png"),
            full_page=True
        )

        await browser.close()

    print(f"\n✅ Screenshots saved to: {screenshots_dir}")
    print("   - ai100_file_changes_with_data.png")
    print("   - ai100_file_changes_expanded_diff.png")
    print("   - ai100_file_changes_empty_state.png")
    print("   - ai100_file_changes_multiple_types.png")
    print("   - ai100_file_changes_all_types.png")

if __name__ == "__main__":
    try:
        asyncio.run(take_screenshots())
    except Exception as e:
        print(f"❌ Error taking screenshots: {e}", file=sys.stderr)
        sys.exit(1)
