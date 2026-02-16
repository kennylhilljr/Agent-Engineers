#!/usr/bin/env python3
"""
Screenshot Capture Script for Provider Status Indicators - AI-73
Captures screenshots showing:
1. Available status (green)
2. Unconfigured status (gray) with tooltip
3. Error status (red)
4. All providers with different statuses
"""

import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

SCREENSHOTS_DIR = Path(__file__).parent / "screenshots" / "ai-73-provider-status"
DASHBOARD_PATH = Path(__file__).parent.parent / "dashboard.html"


async def inject_mock_api(page):
    """Inject mock API responses for provider status."""
    await page.route("**/api/providers/status", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body="""{
            "providers": {
                "claude": {
                    "status": "available",
                    "name": "Claude",
                    "configured": true,
                    "setup_instructions": null
                },
                "chatgpt": {
                    "status": "unconfigured",
                    "name": "ChatGPT",
                    "configured": false,
                    "setup_instructions": "Set OPENAI_API_KEY environment variable with your OpenAI API key"
                },
                "gemini": {
                    "status": "unconfigured",
                    "name": "Gemini",
                    "configured": false,
                    "setup_instructions": "Set GOOGLE_API_KEY environment variable with your Google AI API key"
                },
                "groq": {
                    "status": "available",
                    "name": "Groq",
                    "configured": true,
                    "setup_instructions": null
                },
                "kimi": {
                    "status": "unconfigured",
                    "name": "KIMI",
                    "configured": false,
                    "setup_instructions": "Set KIMI_API_KEY environment variable with your KIMI API key"
                },
                "windsurf": {
                    "status": "error",
                    "name": "Windsurf",
                    "configured": true,
                    "setup_instructions": null
                }
            },
            "timestamp": "2026-02-16T10:00:00Z"
        }"""
    ))


async def capture_screenshots():
    """Capture all required screenshots for AI-73."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    print("🎬 Starting Provider Status Indicator screenshot capture...")
    print(f"📁 Screenshots will be saved to: {SCREENSHOTS_DIR}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        # Inject mock API
        await inject_mock_api(page)

        # Navigate to dashboard
        dashboard_url = f"file://{DASHBOARD_PATH.absolute()}"
        print(f"\n📄 Loading dashboard from: {dashboard_url}")
        await page.goto(dashboard_url)

        # Wait for page to load
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # Manually inject provider status data
        await page.evaluate("""
            () => {
                const chatInterface = window.chatInterface || {};
                chatInterface.providerStatuses = {
                    "claude": {
                        "status": "available",
                        "name": "Claude",
                        "configured": true,
                        "setup_instructions": null
                    },
                    "chatgpt": {
                        "status": "unconfigured",
                        "name": "ChatGPT",
                        "configured": false,
                        "setup_instructions": "Set OPENAI_API_KEY environment variable with your OpenAI API key"
                    },
                    "gemini": {
                        "status": "unconfigured",
                        "name": "Gemini",
                        "configured": false,
                        "setup_instructions": "Set GOOGLE_API_KEY environment variable with your Google AI API key"
                    },
                    "groq": {
                        "status": "available",
                        "name": "Groq",
                        "configured": true,
                        "setup_instructions": null
                    },
                    "kimi": {
                        "status": "unconfigured",
                        "name": "KIMI",
                        "configured": false,
                        "setup_instructions": "Set KIMI_API_KEY environment variable with your KIMI API key"
                    },
                    "windsurf": {
                        "status": "error",
                        "name": "Windsurf",
                        "configured": true,
                        "setup_instructions": null
                    }
                };

                // Update the current status indicator
                if (window.chatInterface && window.chatInterface.updateProviderStatusIndicator) {
                    window.chatInterface.updateProviderStatusIndicator('claude');
                }
            }
        """)

        # Screenshot 1: Available Status (Claude)
        print("\n📸 Capturing: 1-available-status-claude.png")
        chat_container = page.locator('#chat-container')
        await chat_container.screenshot(
            path=SCREENSHOTS_DIR / "1-available-status-claude.png"
        )

        # Screenshot 2: Unconfigured Status (ChatGPT) with tooltip
        print("📸 Capturing: 2-unconfigured-status-chatgpt.png")
        await page.select_option('#ai-provider-selector', 'chatgpt')
        await page.wait_for_timeout(500)
        await chat_container.screenshot(
            path=SCREENSHOTS_DIR / "2-unconfigured-status-chatgpt.png"
        )

        # Screenshot 3: Unconfigured Status with Tooltip Hover
        print("📸 Capturing: 3-unconfigured-tooltip-hover.png")
        status_indicator = page.locator('#provider-status-indicator')
        await status_indicator.hover()
        await page.wait_for_timeout(500)
        await chat_container.screenshot(
            path=SCREENSHOTS_DIR / "3-unconfigured-tooltip-hover.png"
        )

        # Screenshot 4: Error Status (Windsurf)
        print("📸 Capturing: 4-error-status-windsurf.png")
        await page.select_option('#ai-provider-selector', 'windsurf')
        await page.wait_for_timeout(500)
        await chat_container.screenshot(
            path=SCREENSHOTS_DIR / "4-error-status-windsurf.png"
        )

        # Screenshot 5: Error Status with Tooltip Hover
        print("📸 Capturing: 5-error-tooltip-hover.png")
        await status_indicator.hover()
        await page.wait_for_timeout(500)
        await chat_container.screenshot(
            path=SCREENSHOTS_DIR / "5-error-tooltip-hover.png"
        )

        # Screenshot 6: Available Status (Groq)
        print("📸 Capturing: 6-available-status-groq.png")
        await page.select_option('#ai-provider-selector', 'groq')
        await page.wait_for_timeout(500)
        await chat_container.screenshot(
            path=SCREENSHOTS_DIR / "6-available-status-groq.png"
        )

        # Screenshot 7: All Three Statuses Side by Side (composite view)
        print("📸 Capturing: 7-status-comparison.png")
        # Take full page screenshot to show the selector
        await page.screenshot(
            path=SCREENSHOTS_DIR / "7-status-comparison.png",
            full_page=False
        )

        # Screenshot 8: Mobile viewport
        print("📸 Capturing: 8-mobile-responsive-view.png")
        await page.set_viewport_size({"width": 375, "height": 667})
        await page.wait_for_timeout(500)
        await chat_container.screenshot(
            path=SCREENSHOTS_DIR / "8-mobile-responsive-view.png"
        )

        await browser.close()

    print("\n✅ All screenshots captured successfully!")
    print(f"📁 Screenshots saved to: {SCREENSHOTS_DIR}")

    # List captured files
    print("\n📋 Captured files:")
    for screenshot in sorted(SCREENSHOTS_DIR.glob("*.png")):
        size = screenshot.stat().st_size / 1024  # KB
        print(f"   - {screenshot.name} ({size:.1f} KB)")


async def main():
    """Main entry point."""
    try:
        await capture_screenshots()
        return 0
    except Exception as e:
        print(f"\n❌ Error capturing screenshots: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
