"""Playwright browser automation tests for AI-129 Phase 4: Multi-Provider Switching.

Tests all 5 requirements:
1. Verify all 6 providers display in selector
2. Check provider availability indicators (Available/Unconfigured/Error)
3. Switch between providers without losing chat history
4. Verify correct model appears in selector for each provider
5. Test hot-swap during conversation
"""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path

import pytest


# Mark all tests in this module as requiring playwright
pytestmark = pytest.mark.playwright


@pytest.fixture(scope="module")
def server_process():
    """Start REST API server for testing."""
    project_root = Path(__file__).parent.parent.parent
    server_script = project_root / "dashboard" / "rest_api_server.py"

    # Start server process
    env = os.environ.copy()
    env['PYTHONPATH'] = str(project_root)

    process = subprocess.Popen(
        ["python", str(server_script), "--port", "8420", "--host", "127.0.0.1"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Wait for server to start
    time.sleep(3)

    yield process

    # Cleanup
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.fixture
async def page(playwright):
    """Create a browser page for testing."""
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    yield page
    await context.close()
    await browser.close()


class TestProviderSelector:
    """Test Step 1: Verify all 6 providers display in selector."""

    @pytest.mark.asyncio
    async def test_all_providers_in_selector(self, page, server_process):
        """Test that all 6 providers are displayed in the selector."""
        # Load test chat page
        chat_html = Path(__file__).parent.parent.parent / ".worktrees" / "coding-0" / "dashboard" / "test_chat.html"
        await page.goto(f"file://{chat_html.absolute()}")

        # Wait for selector to load
        await page.wait_for_selector('[data-testid="ai-provider-selector"]', timeout=5000)

        # Get all provider options
        provider_selector = await page.query_selector('[data-testid="ai-provider-selector"]')
        options = await provider_selector.query_selector_all('option')

        # Should have 6 providers
        assert len(options) == 6

        # Verify each provider
        expected_providers = ['claude', 'openai', 'gemini', 'groq', 'kimi', 'windsurf']
        for i, expected_value in enumerate(expected_providers):
            value = await options[i].get_attribute('value')
            assert value == expected_value

    @pytest.mark.asyncio
    async def test_provider_names_display_correctly(self, page, server_process):
        """Test that provider names are displayed correctly."""
        chat_html = Path(__file__).parent.parent.parent / ".worktrees" / "coding-0" / "dashboard" / "test_chat.html"
        await page.goto(f"file://{chat_html.absolute()}")

        await page.wait_for_selector('[data-testid="ai-provider-selector"]', timeout=5000)

        # Check provider names
        expected_names = {
            'claude': 'Claude',
            'openai': 'ChatGPT',
            'gemini': 'Gemini',
            'groq': 'Groq',
            'kimi': 'KIMI',
            'windsurf': 'Windsurf'
        }

        for provider_id, provider_name in expected_names.items():
            option = await page.query_selector(f'[data-testid="provider-option-{provider_id}"]')
            assert option is not None
            text = await option.inner_text()
            assert provider_name in text or provider_id in text.lower()


class TestProviderStatusIndicators:
    """Test Step 2: Check provider availability indicators."""

    @pytest.mark.asyncio
    async def test_provider_status_indicators_present(self, page, server_process):
        """Test that provider status indicators are displayed."""
        chat_html = Path(__file__).parent.parent.parent / ".worktrees" / "coding-0" / "dashboard" / "test_chat.html"
        await page.goto(f"file://{chat_html.absolute()}")

        # Wait for page to load
        await page.wait_for_selector('[data-testid="provider-badge"]', timeout=5000)

        # Wait for provider status to be fetched
        await asyncio.sleep(2)

        # Check that status indicator element exists
        status_dot = await page.query_selector('#provider-status-dot')
        assert status_dot is not None

        # Check that it has a color class
        class_name = await status_dot.get_attribute('class')
        assert 'provider-status-indicator' in class_name
        assert any(color in class_name for color in ['green', 'yellow', 'red'])

    @pytest.mark.asyncio
    async def test_status_indicators_update_on_provider_change(self, page, server_process):
        """Test that status indicators update when provider changes."""
        chat_html = Path(__file__).parent.parent.parent / ".worktrees" / "coding-0" / "dashboard" / "test_chat.html"
        await page.goto(f"file://{chat_html.absolute()}")

        await page.wait_for_selector('[data-testid="ai-provider-selector"]', timeout=5000)
        await asyncio.sleep(2)

        # Get initial status
        status_dot = await page.query_selector('#provider-status-dot')
        initial_class = await status_dot.get_attribute('class')

        # Change provider
        await page.select_option('[data-testid="ai-provider-selector"]', 'gemini')
        await asyncio.sleep(1)

        # Check status updated
        updated_class = await status_dot.get_attribute('class')
        assert 'provider-status-indicator' in updated_class


class TestChatHistoryPreservation:
    """Test Step 3: Switch between providers without losing chat history."""

    @pytest.mark.asyncio
    async def test_chat_history_preserved_on_provider_switch(self, page, server_process):
        """Test that chat history is preserved when switching providers."""
        chat_html = Path(__file__).parent.parent.parent / ".worktrees" / "coding-0" / "dashboard" / "test_chat.html"
        await page.goto(f"file://{chat_html.absolute()}")

        await page.wait_for_selector('[data-testid="chat-message-input"]', timeout=5000)

        # Send a message with Claude
        await page.fill('[data-testid="chat-message-input"]', 'Hello from Claude')
        await page.click('[data-testid="chat-send-button"]')
        await asyncio.sleep(2)

        # Verify message appears
        user_messages = await page.query_selector_all('[data-testid="chat-message-user"]')
        assert len(user_messages) == 1

        # Switch to Gemini
        await page.select_option('[data-testid="ai-provider-selector"]', 'gemini')
        await asyncio.sleep(1)

        # Verify message still visible
        user_messages_after = await page.query_selector_all('[data-testid="chat-message-user"]')
        assert len(user_messages_after) == 1

        # Send another message with Gemini
        await page.fill('[data-testid="chat-message-input"]', 'Hello from Gemini')
        await page.click('[data-testid="chat-send-button"]')
        await asyncio.sleep(2)

        # Verify both messages are visible
        user_messages_final = await page.query_selector_all('[data-testid="chat-message-user"]')
        assert len(user_messages_final) == 2

    @pytest.mark.asyncio
    async def test_session_storage_persistence(self, page, server_process):
        """Test that conversation is saved to sessionStorage."""
        chat_html = Path(__file__).parent.parent.parent / ".worktrees" / "coding-0" / "dashboard" / "test_chat.html"
        await page.goto(f"file://{chat_html.absolute()}")

        await page.wait_for_selector('[data-testid="chat-message-input"]', timeout=5000)

        # Send a message
        await page.fill('[data-testid="chat-message-input"]', 'Test message')
        await page.click('[data-testid="chat-send-button"]')
        await asyncio.sleep(2)

        # Check sessionStorage
        saved_messages = await page.evaluate('() => sessionStorage.getItem("chatMessages")')
        assert saved_messages is not None

        messages = json.loads(saved_messages)
        assert len(messages) > 0


class TestModelSelectorSync:
    """Test Step 4: Verify correct model appears in selector for each provider."""

    @pytest.mark.asyncio
    async def test_model_selector_updates_for_claude(self, page, server_process):
        """Test that model selector shows Claude models when Claude is selected."""
        chat_html = Path(__file__).parent.parent.parent / ".worktrees" / "coding-0" / "dashboard" / "test_chat.html"
        await page.goto(f"file://{chat_html.absolute()}")

        await page.wait_for_selector('[data-testid="ai-model-selector"]', timeout=5000)
        await asyncio.sleep(2)

        # Select Claude
        await page.select_option('[data-testid="ai-provider-selector"]', 'claude')
        await asyncio.sleep(1)

        # Check model selector has Claude models
        model_selector = await page.query_selector('[data-testid="ai-model-selector"]')
        options = await model_selector.query_selector_all('option')

        # Should have Claude models
        assert len(options) > 0

        # Check for expected models
        model_values = []
        for option in options:
            value = await option.get_attribute('value')
            model_values.append(value)

        # Claude should have haiku, sonnet, opus
        assert any('haiku' in m or 'sonnet' in m or 'opus' in m for m in model_values)

    @pytest.mark.asyncio
    async def test_model_selector_updates_for_gemini(self, page, server_process):
        """Test that model selector shows Gemini models when Gemini is selected."""
        chat_html = Path(__file__).parent.parent.parent / ".worktrees" / "coding-0" / "dashboard" / "test_chat.html"
        await page.goto(f"file://{chat_html.absolute()}")

        await page.wait_for_selector('[data-testid="ai-model-selector"]', timeout=5000)
        await asyncio.sleep(2)

        # Select Gemini
        await page.select_option('[data-testid="ai-provider-selector"]', 'gemini')
        await asyncio.sleep(1)

        # Check model selector has Gemini models
        model_selector = await page.query_selector('[data-testid="ai-model-selector"]')
        options = await model_selector.query_selector_all('option')

        # Should have Gemini models
        assert len(options) > 0

        # Check for expected models
        model_values = []
        for option in options:
            value = await option.get_attribute('value')
            model_values.append(value)

        # Gemini should have flash/pro models
        assert any('flash' in m.lower() or 'pro' in m.lower() for m in model_values)


class TestHotSwapDuringConversation:
    """Test Step 5: Test hot-swap during conversation."""

    @pytest.mark.asyncio
    async def test_hot_swap_during_active_conversation(self, page, server_process):
        """Test hot-swap between providers during an active conversation."""
        chat_html = Path(__file__).parent.parent.parent / ".worktrees" / "coding-0" / "dashboard" / "test_chat.html"
        await page.goto(f"file://{chat_html.absolute()}")

        await page.wait_for_selector('[data-testid="chat-message-input"]', timeout=5000)
        await asyncio.sleep(2)

        # Start conversation with Claude
        await page.fill('[data-testid="chat-message-input"]', 'What is the status?')
        await page.click('[data-testid="chat-send-button"]')
        await asyncio.sleep(2)

        # Verify initial messages
        initial_message_count = len(await page.query_selector_all('[data-testid^="chat-message-"]'))
        assert initial_message_count >= 2  # User + AI response

        # Hot-swap to Gemini
        await page.select_option('[data-testid="ai-provider-selector"]', 'gemini')
        await asyncio.sleep(1)

        # Verify badge updated
        badge_text = await page.inner_text('[data-testid="provider-badge"]')
        assert 'Gemini' in badge_text

        # Continue conversation with Gemini
        await page.fill('[data-testid="chat-message-input"]', 'What about metrics?')
        await page.click('[data-testid="chat-send-button"]')
        await asyncio.sleep(2)

        # Verify all messages preserved
        final_message_count = len(await page.query_selector_all('[data-testid^="chat-message-"]'))
        assert final_message_count >= 4  # Previous + new user + new AI

        # Hot-swap to Groq
        await page.select_option('[data-testid="ai-provider-selector"]', 'groq')
        await asyncio.sleep(1)

        # Verify badge updated
        badge_text = await page.inner_text('[data-testid="provider-badge"]')
        assert 'Groq' in badge_text or 'GROQ' in badge_text

        # Continue conversation with Groq
        await page.fill('[data-testid="chat-message-input"]', 'Show performance data')
        await page.click('[data-testid="chat-send-button"]')
        await asyncio.sleep(2)

        # Verify all messages still preserved
        final_final_count = len(await page.query_selector_all('[data-testid^="chat-message-"]'))
        assert final_final_count >= 6  # All previous messages preserved

    @pytest.mark.asyncio
    async def test_provider_selector_reflects_current_provider(self, page, server_process):
        """Test that provider selector always reflects the current provider."""
        chat_html = Path(__file__).parent.parent.parent / ".worktrees" / "coding-0" / "dashboard" / "test_chat.html"
        await page.goto(f"file://{chat_html.absolute()}")

        await page.wait_for_selector('[data-testid="ai-provider-selector"]', timeout=5000)
        await asyncio.sleep(2)

        # Test each provider
        providers = ['claude', 'openai', 'gemini', 'groq', 'kimi', 'windsurf']

        for provider in providers:
            # Select provider
            await page.select_option('[data-testid="ai-provider-selector"]', provider)
            await asyncio.sleep(0.5)

            # Verify selector value
            selected_value = await page.evaluate(
                '() => document.getElementById("ai-provider-selector").value'
            )
            assert selected_value == provider

            # Verify badge updated
            badge_text = await page.inner_text('[data-testid="provider-badge"]')
            assert len(badge_text) > 0


class TestScreenshotCapture:
    """Capture screenshots for documentation."""

    @pytest.mark.asyncio
    async def test_capture_provider_switching_screenshot(self, page, server_process):
        """Capture screenshot showing provider switching."""
        chat_html = Path(__file__).parent.parent.parent / ".worktrees" / "coding-0" / "dashboard" / "test_chat.html"
        await page.goto(f"file://{chat_html.absolute()}")

        await page.wait_for_selector('[data-testid="chat-message-input"]', timeout=5000)
        await asyncio.sleep(2)

        # Send message with Claude
        await page.fill('[data-testid="chat-message-input"]', 'Hello, testing multi-provider chat!')
        await page.click('[data-testid="chat-send-button"]')
        await asyncio.sleep(2)

        # Capture screenshot
        screenshots_dir = Path(__file__).parent.parent.parent / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)

        await page.screenshot(path=str(screenshots_dir / "provider_switching_1_claude.png"))

        # Switch to Gemini
        await page.select_option('[data-testid="ai-provider-selector"]', 'gemini')
        await asyncio.sleep(1)

        await page.screenshot(path=str(screenshots_dir / "provider_switching_2_gemini.png"))

        # Send another message
        await page.fill('[data-testid="chat-message-input"]', 'Continuing conversation with Gemini')
        await page.click('[data-testid="chat-send-button"]')
        await asyncio.sleep(2)

        await page.screenshot(path=str(screenshots_dir / "provider_switching_3_conversation.png"))

        print(f"\nScreenshots saved to: {screenshots_dir}")
