#!/usr/bin/env python3
"""
Screenshot capture script for AI-109: Chat-to-Agent Bridge.
Captures visual evidence of chat routing working in the dashboard.
"""

import json
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright not available.")


def capture_screenshots():
    """Capture screenshots showing Chat-to-Agent Bridge functionality."""

    if not PLAYWRIGHT_AVAILABLE:
        print("Cannot capture screenshots - Playwright not installed")
        return None

    screenshots_dir = Path(__file__).parent / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    screenshot_path = str(screenshots_dir / "ai109_chat_bridge.png")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # Navigate to the dashboard
        print("Loading dashboard at http://127.0.0.1:8420...")
        page.goto("http://127.0.0.1:8420")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        # Find the chat input and send button
        chat_input = page.locator("#chat-input")
        send_btn = page.locator("#chat-send-btn")

        # Scroll to chat section
        chat_container = page.locator("#chat-container")
        chat_container.scroll_into_view_if_needed()
        time.sleep(0.5)

        # Type the test message
        msg = "What is AI-109 status?"
        print(f"Typing: '{msg}'")
        chat_input.fill(msg)
        time.sleep(0.3)

        # Take screenshot before sending
        page.screenshot(path=str(screenshots_dir / "ai109_before_send.png"), full_page=False)
        print("Saved: ai109_before_send.png")

        # Send the message
        send_btn.click()
        time.sleep(1.5)

        # Take screenshot after sending
        page.screenshot(path=screenshot_path, full_page=False)
        print(f"Saved: {screenshot_path}")

        browser.close()
        return screenshot_path


if __name__ == "__main__":
    path = capture_screenshots()
    if path:
        print(f"Screenshot saved: {path}")
        sys.exit(0)
    else:
        sys.exit(1)
