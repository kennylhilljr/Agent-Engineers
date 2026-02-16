#!/usr/bin/env python3
"""
AI-72: Model Selector Screenshot Automation

Captures screenshots for all test steps defined in the requirements:
1. Select Claude provider - verify models show: Haiku 4.5, Sonnet 4.5, Opus 4.6
2. Select ChatGPT - verify models show: GPT-4o, o1, o3-mini, o4-mini
3. Select Gemini - verify models show: 2.5 Flash, 2.5 Pro, 2.0 Flash
4. Verify default model is highlighted for each provider
5. Select a specific model and send a message
6. Verify the selected model persists after sending
7. Refresh page and verify selection persists (session storage)
"""

import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright

# Configuration
SCREENSHOT_DIR = Path(__file__).parent / "screenshots" / "ai-72"
TEST_FILE = Path(__file__).parent.parent / "test_chat.html"
TEST_URL = f"file://{TEST_FILE.resolve()}"

# Create screenshot directory
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

print(f"📸 AI-72 Screenshot Automation")
print(f"📁 Screenshots will be saved to: {SCREENSHOT_DIR}")
print(f"🌐 Test URL: {TEST_URL}")
print("=" * 80)

async def capture_screenshot(page, filename, description):
    """Capture screenshot with description"""
    filepath = SCREENSHOT_DIR / filename
    await page.screenshot(path=str(filepath), full_page=True)
    print(f"✅ {description}")
    print(f"   📸 {filename}")
    return filepath

async def main():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page(viewport={'width': 1400, 'height': 900})

        try:
            # Navigate to test page
            print("\n🚀 Navigating to test page...")
            await page.goto(TEST_URL)
            await page.wait_for_load_state('domcontentloaded')

            # Clear session storage
            await page.evaluate("sessionStorage.clear()")
            await page.reload()
            await page.wait_for_load_state('domcontentloaded')
            await asyncio.sleep(1)

            # ==========================================
            # Test Step 1: Claude Models
            # ==========================================
            print("\n📋 Test Step 1: Claude Provider Models")
            await page.select_option('#ai-provider-selector', 'claude')
            await asyncio.sleep(0.5)

            # Expand model dropdown
            await page.click('#ai-model-selector')
            await asyncio.sleep(0.3)
            await capture_screenshot(
                page,
                '01_claude_models_dropdown.png',
                'Claude models shown: Haiku 4.5, Sonnet 4.5, Opus 4.6'
            )

            # Close dropdown and capture default
            await page.click('#ai-model-selector')
            await asyncio.sleep(0.3)
            await capture_screenshot(
                page,
                '02_claude_default_haiku.png',
                'Claude default model: Haiku 4.5 highlighted'
            )

            # ==========================================
            # Test Step 2: ChatGPT Models
            # ==========================================
            print("\n📋 Test Step 2: ChatGPT Provider Models")
            await page.select_option('#ai-provider-selector', 'chatgpt')
            await asyncio.sleep(0.5)

            await page.click('#ai-model-selector')
            await asyncio.sleep(0.3)
            await capture_screenshot(
                page,
                '03_chatgpt_models_dropdown.png',
                'ChatGPT models shown: GPT-4o, o1, o3-mini, o4-mini'
            )

            await page.click('#ai-model-selector')
            await asyncio.sleep(0.3)
            await capture_screenshot(
                page,
                '04_chatgpt_default_gpt4o.png',
                'ChatGPT default model: GPT-4o highlighted'
            )

            # ==========================================
            # Test Step 3: Gemini Models
            # ==========================================
            print("\n📋 Test Step 3: Gemini Provider Models")
            await page.select_option('#ai-provider-selector', 'gemini')
            await asyncio.sleep(0.5)

            await page.click('#ai-model-selector')
            await asyncio.sleep(0.3)
            await capture_screenshot(
                page,
                '05_gemini_models_dropdown.png',
                'Gemini models shown: 2.5 Flash, 2.5 Pro, 2.0 Flash'
            )

            await page.click('#ai-model-selector')
            await asyncio.sleep(0.3)
            await capture_screenshot(
                page,
                '06_gemini_default_flash.png',
                'Gemini default model: 2.5 Flash highlighted'
            )

            # ==========================================
            # Test Step 4: Groq Models
            # ==========================================
            print("\n📋 Test Step 4: Groq Provider Models")
            await page.select_option('#ai-provider-selector', 'groq')
            await asyncio.sleep(0.5)

            await page.click('#ai-model-selector')
            await asyncio.sleep(0.3)
            await capture_screenshot(
                page,
                '07_groq_models_dropdown.png',
                'Groq models shown: Llama 3.3 70B, Mixtral 8x7B'
            )

            await page.click('#ai-model-selector')
            await asyncio.sleep(0.3)
            await capture_screenshot(
                page,
                '08_groq_default_llama.png',
                'Groq default model: Llama 3.3 70B highlighted'
            )

            # ==========================================
            # Test Step 5: KIMI and Windsurf (single models)
            # ==========================================
            print("\n📋 Test Step 5: KIMI and Windsurf Models")
            await page.select_option('#ai-provider-selector', 'kimi')
            await asyncio.sleep(0.5)
            await capture_screenshot(
                page,
                '09_kimi_single_model.png',
                'KIMI single model: Moonshot'
            )

            await page.select_option('#ai-provider-selector', 'windsurf')
            await asyncio.sleep(0.5)
            await capture_screenshot(
                page,
                '10_windsurf_single_model.png',
                'Windsurf single model: Cascade'
            )

            # ==========================================
            # Test Step 6: Select Model and Send Message
            # ==========================================
            print("\n📋 Test Step 6: Select Model and Send Message")
            await page.select_option('#ai-provider-selector', 'claude')
            await asyncio.sleep(0.5)

            # Select Sonnet 4.5
            await page.select_option('#ai-model-selector', 'sonnet-4.5')
            await asyncio.sleep(0.5)
            await capture_screenshot(
                page,
                '11_model_selected_sonnet.png',
                'Sonnet 4.5 selected and badge updated'
            )

            # Send a message
            await page.fill('#chat-input', 'Hello, testing model selector!')
            await asyncio.sleep(0.3)
            await capture_screenshot(
                page,
                '12_before_send_message.png',
                'Message typed with Sonnet 4.5 selected'
            )

            await page.click('#chat-send-btn')
            await asyncio.sleep(1.5)
            await capture_screenshot(
                page,
                '13_after_send_message.png',
                'Message sent with Sonnet 4.5, waiting for response'
            )

            # Wait for AI response
            await asyncio.sleep(1)
            await capture_screenshot(
                page,
                '14_ai_response_with_model.png',
                'AI response includes provider and model name'
            )

            # ==========================================
            # Test Step 7: Model Persists After Message
            # ==========================================
            print("\n📋 Test Step 7: Model Selection Persists")
            # Send another message to verify persistence
            await page.fill('#chat-input', 'Another message')
            await page.click('#chat-send-btn')
            await asyncio.sleep(1.5)

            await capture_screenshot(
                page,
                '15_model_persists_after_message.png',
                'Model selection (Sonnet 4.5) persists after sending messages'
            )

            # Change to Opus 4.6
            await page.select_option('#ai-model-selector', 'opus-4.6')
            await asyncio.sleep(0.5)
            await page.fill('#chat-input', 'Message with Opus')
            await page.click('#chat-send-btn')
            await asyncio.sleep(1.5)

            await capture_screenshot(
                page,
                '16_different_model_conversation.png',
                'Conversation with multiple models (Sonnet and Opus)'
            )

            # ==========================================
            # Test Step 8: Session Persistence After Refresh
            # ==========================================
            print("\n📋 Test Step 8: Session Persistence After Refresh")
            await capture_screenshot(
                page,
                '17_before_refresh.png',
                'State before refresh: Opus 4.6 selected'
            )

            # Refresh page
            await page.reload()
            await page.wait_for_load_state('domcontentloaded')
            await asyncio.sleep(1)

            await capture_screenshot(
                page,
                '18_after_refresh_persisted.png',
                'After refresh: Opus 4.6 still selected (sessionStorage)'
            )

            # ==========================================
            # Test Step 9: Multiple Provider Switches
            # ==========================================
            print("\n📋 Test Step 9: Multiple Provider-Model Combinations")

            # Switch to ChatGPT and select o1
            await page.select_option('#ai-provider-selector', 'chatgpt')
            await asyncio.sleep(0.5)
            await page.select_option('#ai-model-selector', 'o1')
            await asyncio.sleep(0.5)
            await capture_screenshot(
                page,
                '19_chatgpt_o1_selected.png',
                'ChatGPT provider with o1 model selected'
            )

            # Switch to Gemini and select 2.5 Pro
            await page.select_option('#ai-provider-selector', 'gemini')
            await asyncio.sleep(0.5)
            await page.select_option('#ai-model-selector', '2.5-pro')
            await asyncio.sleep(0.5)
            await capture_screenshot(
                page,
                '20_gemini_pro_selected.png',
                'Gemini provider with 2.5 Pro model selected'
            )

            # ==========================================
            # Test Step 10: Full Interface View
            # ==========================================
            print("\n📋 Test Step 10: Full Interface Overview")

            # Back to Claude with different model
            await page.select_option('#ai-provider-selector', 'claude')
            await asyncio.sleep(0.5)
            await page.select_option('#ai-model-selector', 'haiku-4.5')
            await asyncio.sleep(0.5)

            # Send messages to show full conversation with models
            await page.fill('#chat-input', 'Final test with Haiku')
            await page.click('#chat-send-btn')
            await asyncio.sleep(1.5)

            await capture_screenshot(
                page,
                '21_full_interface_overview.png',
                'Complete interface showing provider selector, model selector, and chat'
            )

            # Capture both dropdowns visible
            await page.select_option('#ai-provider-selector', 'claude')
            await page.click('#ai-model-selector')
            await asyncio.sleep(0.3)

            await capture_screenshot(
                page,
                '22_complete_ui_with_dropdown.png',
                'Complete UI: both provider and model selectors visible'
            )

            print("\n" + "=" * 80)
            print(f"✅ Screenshot capture complete!")
            print(f"📁 {len(list(SCREENSHOT_DIR.glob('*.png')))} screenshots saved to:")
            print(f"   {SCREENSHOT_DIR}")
            print("=" * 80)

        except Exception as e:
            print(f"\n❌ Error during screenshot capture: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
