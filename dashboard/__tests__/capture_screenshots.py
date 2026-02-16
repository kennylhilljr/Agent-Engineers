#!/usr/bin/env python3
"""
Screenshot capture script for AI-71: Provider Switcher
Captures visual evidence of all test steps
"""

import os
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️  Playwright not available. Install with: pip install playwright && playwright install")

def capture_screenshots():
    """Capture screenshots showing provider switcher functionality"""

    if not PLAYWRIGHT_AVAILABLE:
        print("❌ Cannot capture screenshots - Playwright not installed")
        return False

    # Setup paths
    script_dir = Path(__file__).parent
    test_html = script_dir.parent / "test_chat.html"
    screenshots_dir = script_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    print("🔷 AI-71 Provider Switcher - Screenshot Capture")
    print("=" * 60)
    print(f"📄 Test file: {test_html}")
    print(f"📁 Screenshots dir: {screenshots_dir}")
    print()

    if not test_html.exists():
        print(f"❌ Test file not found: {test_html}")
        return False

    with sync_playwright() as p:
        # Launch browser
        print("🌐 Launching browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # Load test page
        file_url = f"file://{test_html.absolute()}"
        print(f"📂 Loading: {file_url}")
        page.goto(file_url)
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        # Test Step 1-2: Provider dropdown with all 6 providers
        print("\n📸 Test Step 1-2: Capturing provider dropdown...")
        page.screenshot(path=str(screenshots_dir / "01_provider_dropdown_default.png"))
        print("   ✓ Saved: 01_provider_dropdown_default.png")

        # Click selector to show options
        provider_selector = page.locator("#ai-provider-selector")
        provider_selector.click()
        time.sleep(0.5)
        page.screenshot(path=str(screenshots_dir / "02_provider_dropdown_expanded.png"))
        print("   ✓ Saved: 02_provider_dropdown_expanded.png")

        # Test Step 3-4: Verify Claude is default
        print("\n📸 Test Step 4: Capturing default Claude selection...")
        badge = page.locator("#provider-badge")
        badge_text = badge.text_content()
        assert badge_text == "Claude", f"Expected 'Claude', got '{badge_text}'"
        page.screenshot(path=str(screenshots_dir / "03_default_claude.png"))
        print(f"   ✓ Default provider: {badge_text}")
        print("   ✓ Saved: 03_default_claude.png")

        # Test Step 5: Switch to ChatGPT
        print("\n📸 Test Step 5: Switching to ChatGPT...")
        provider_selector.select_option("chatgpt")
        time.sleep(0.3)
        badge_text = badge.text_content()
        assert badge_text == "ChatGPT", f"Expected 'ChatGPT', got '{badge_text}'"
        page.screenshot(path=str(screenshots_dir / "04_chatgpt_selected.png"))
        print(f"   ✓ Provider switched to: {badge_text}")
        print("   ✓ Saved: 04_chatgpt_selected.png")

        # Test Step 6: Switch to Gemini
        print("\n📸 Test Step 6: Switching to Gemini...")
        provider_selector.select_option("gemini")
        time.sleep(0.3)
        badge_text = badge.text_content()
        assert badge_text == "Gemini", f"Expected 'Gemini', got '{badge_text}'"
        page.screenshot(path=str(screenshots_dir / "05_gemini_selected.png"))
        print(f"   ✓ Provider switched to: {badge_text}")
        print("   ✓ Saved: 05_gemini_selected.png")

        # Test Step 7: Test all providers
        print("\n📸 Test Step 7: Testing all providers...")
        providers = [
            ("groq", "Groq"),
            ("kimi", "KIMI"),
            ("windsurf", "Windsurf"),
            ("claude", "Claude")
        ]

        for i, (provider_value, provider_name) in enumerate(providers, start=6):
            provider_selector.select_option(provider_value)
            time.sleep(0.3)
            badge_text = badge.text_content()
            assert badge_text == provider_name, f"Expected '{provider_name}', got '{badge_text}'"
            page.screenshot(path=str(screenshots_dir / f"{i:02d}_{provider_value}_selected.png"))
            print(f"   ✓ Provider: {provider_name} - Saved: {i:02d}_{provider_value}_selected.png")

        # Test Step 8: Send message with each provider
        print("\n📸 Test Step 8-9: Sending messages with different providers...")

        # ChatGPT message
        provider_selector.select_option("chatgpt")
        time.sleep(0.3)
        input_field = page.locator("#chat-input")
        send_btn = page.locator("#chat-send-btn")

        input_field.fill("Hello from ChatGPT!")
        send_btn.click()
        time.sleep(1)  # Wait for response
        page.screenshot(path=str(screenshots_dir / "10_message_chatgpt.png"))
        print("   ✓ ChatGPT message sent - Saved: 10_message_chatgpt.png")

        # Gemini message
        provider_selector.select_option("gemini")
        time.sleep(0.3)
        input_field.fill("Hello from Gemini!")
        send_btn.click()
        time.sleep(1)
        page.screenshot(path=str(screenshots_dir / "11_message_gemini.png"))
        print("   ✓ Gemini message sent - Saved: 11_message_gemini.png")

        # Groq message
        provider_selector.select_option("groq")
        time.sleep(0.3)
        input_field.fill("What's my status?")
        send_btn.click()
        time.sleep(1)
        page.screenshot(path=str(screenshots_dir / "12_message_groq.png"))
        print("   ✓ Groq message sent - Saved: 12_message_groq.png")

        # Verify messages show provider attribution
        print("\n📸 Verifying message attribution...")
        ai_messages = page.locator(".chat-message.ai").all()
        messages = [msg.text_content() for msg in ai_messages]

        has_chatgpt = any("[ChatGPT]" in msg for msg in messages)
        has_gemini = any("[Gemini]" in msg for msg in messages)
        has_groq = any("[Groq]" in msg for msg in messages)

        if has_chatgpt and has_gemini and has_groq:
            print("   ✓ All messages properly attributed to providers")
        else:
            print("   ⚠️  Some message attributions missing")
            print(f"   ChatGPT: {has_chatgpt}, Gemini: {has_gemini}, Groq: {has_groq}")

        # Final screenshot showing conversation with multiple providers
        page.screenshot(path=str(screenshots_dir / "13_conversation_multiple_providers.png"))
        print("   ✓ Saved: 13_conversation_multiple_providers.png")

        # Close browser
        browser.close()
        print("\n" + "=" * 60)
        print("✅ Screenshot capture complete!")
        print(f"📁 Screenshots saved to: {screenshots_dir}")
        print(f"📊 Total screenshots: {len(list(screenshots_dir.glob('*.png')))}")

        return True

if __name__ == "__main__":
    try:
        success = capture_screenshots()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
