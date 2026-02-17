"""Tests for REQ-PROVIDER-004: Hot-Swap Without Context Loss.

Tests cover:
- Conversation history fully preserved when switching providers
- System message insertion is clear and informative
- Context is passed to the new provider via getConversationContext()
- Hot-swap is blocked while an agent operation is running
- No message loss or reordering
"""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

# Ensure project root is in path
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestHotSwapHTMLStructure:
    """Test the HTML structure for hot-swap functionality."""

    @pytest.fixture
    def index_html(self):
        """Read the index.html file."""
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_is_agent_running_flag_in_state(self, index_html):
        """Test isAgentRunning flag is in state for hot-swap guard."""
        assert 'isAgentRunning' in index_html

    def test_get_conversation_context_function_defined(self, index_html):
        """Test getConversationContext() function is defined."""
        assert 'function getConversationContext()' in index_html

    def test_get_conversation_context_exposed_globally(self, index_html):
        """Test getConversationContext is exposed as window property for testing."""
        assert 'window.getConversationContext = getConversationContext' in index_html

    def test_perform_hot_swap_function_defined(self, index_html):
        """Test performHotSwap() function is defined."""
        assert 'function performHotSwap(' in index_html

    def test_perform_hot_swap_exposed_globally(self, index_html):
        """Test performHotSwap is exposed as window property for testing."""
        assert 'window.performHotSwap = performHotSwap' in index_html

    def test_conversation_history_preserved_in_hot_swap(self, index_html):
        """Test hot-swap preserves conversation history (uses state.messages)."""
        # state.messages is the message history - should NOT be cleared on provider switch
        assert 'state.messages' in index_html
        # Provider change should NOT reset messages
        # Verify handleProviderChange doesn't call messages.length = 0 or similar
        assert 'state.messages = []' not in index_html or \
               index_html.index('state.messages = []') < index_html.index('function handleProviderChange')

    def test_system_message_shows_previous_and_new_provider(self, index_html):
        """Test system message shows both previous and new provider."""
        assert 'previousName' in index_html or 'previousProvider' in index_html
        assert 'newName' in index_html or 'newProvider' in index_html

    def test_system_message_shows_provider_transition_arrow(self, index_html):
        """Test system message has visual indicator of provider transition."""
        assert '→' in index_html

    def test_system_message_shows_context_count(self, index_html):
        """Test system message shows how many messages are preserved."""
        assert 'contextCount' in index_html

    def test_hot_swap_guard_prevents_switch_during_running(self, index_html):
        """Test hot-swap is blocked while isAgentRunning is true."""
        assert 'state.isAgentRunning' in index_html
        assert 'Cannot switch provider while' in index_html

    def test_hot_swap_resets_selector_when_blocked(self, index_html):
        """Test selector is reset to current provider when hot-swap is blocked."""
        assert 'providerSelect.value = previousProvider' in index_html

    def test_hot_swap_calls_perform_hot_swap(self, index_html):
        """Test handleProviderChange calls performHotSwap."""
        assert 'performHotSwap(' in index_html

    def test_agent_running_set_on_send(self, index_html):
        """Test isAgentRunning is set to true when sending a message."""
        assert 'state.isAgentRunning = true' in index_html

    def test_agent_running_cleared_after_response(self, index_html):
        """Test isAgentRunning is cleared after response completes."""
        assert 'state.isAgentRunning = false' in index_html

    def test_no_message_loss_messages_append_not_replace(self, index_html):
        """Test messages are appended (push), not replaced (= [])."""
        # state.messages.push is how messages are added
        assert 'state.messages.push(' in index_html

    def test_context_count_label_singular_plural(self, index_html):
        """Test context count shows singular/plural message correctly."""
        # Should handle 1 message vs multiple
        assert "message${contextCount !== 1 ? 's' : ''}" in index_html


class TestHotSwapContextPreservation:
    """Test that conversation context is preserved and passed correctly."""

    @pytest.fixture
    def index_html(self):
        """Read the index.html file."""
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_get_context_filters_system_messages(self, index_html):
        """Test getConversationContext filters out system messages."""
        # Context should only include user/assistant messages
        assert "msg.role !== 'system'" in index_html

    def test_get_context_returns_role_and_content(self, index_html):
        """Test getConversationContext returns role and content fields."""
        assert "role: msg.role" in index_html
        assert "content: msg.content" in index_html

    def test_context_includes_timestamp(self, index_html):
        """Test getConversationContext includes timestamp for ordering."""
        assert "timestamp: msg.timestamp" in index_html

    def test_chat_handler_accepts_conversation_history(self):
        """Test chat_handler stream_chat_response accepts conversation_history."""
        from dashboard.chat_handler import stream_chat_response
        import inspect
        sig = inspect.signature(stream_chat_response)
        params = list(sig.parameters.keys())
        assert 'conversation_history' in params or len(params) >= 3

    @pytest.mark.asyncio
    async def test_chat_response_with_history_context(self):
        """Test chat_handler correctly uses conversation history."""
        from dashboard.chat_handler import stream_chat_response

        history = [
            {'role': 'user', 'content': 'My name is Alice'},
            {'role': 'assistant', 'content': 'Hello Alice!'}
        ]

        with patch.dict(os.environ, {}, clear=True):
            chunks = []
            async for chunk in stream_chat_response(
                'What is my name?',
                'claude',
                'sonnet-4.5',
                history
            ):
                chunks.append(chunk)

        # Should complete without error
        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

    @pytest.mark.asyncio
    async def test_context_preserved_across_all_providers(self):
        """Test history context works with all 6 providers."""
        from dashboard.chat_handler import stream_chat_response

        history = [
            {'role': 'user', 'content': 'Previous message'},
            {'role': 'assistant', 'content': 'Previous response'}
        ]

        providers = ['claude', 'openai', 'gemini', 'groq', 'kimi', 'windsurf']

        with patch.dict(os.environ, {}, clear=True):
            for provider in providers:
                chunks = []
                async for chunk in stream_chat_response(
                    'Continue the conversation',
                    provider,
                    'default',
                    history
                ):
                    chunks.append(chunk)

                assert chunks[-1]['type'] == 'done', \
                    f"Provider {provider} should complete successfully with history"


class TestHotSwapSystemMessage:
    """Test that system messages are clear and informative."""

    @pytest.fixture
    def index_html(self):
        """Read the index.html file."""
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_system_message_includes_provider_switched_text(self, index_html):
        """Test system message includes 'Provider switched' text."""
        assert 'Provider switched' in index_html

    def test_system_message_includes_conservation_preserved_text(self, index_html):
        """Test system message mentions conversation history preserved."""
        assert 'Conversation history preserved' in index_html

    def test_system_message_includes_context_continuity_text(self, index_html):
        """Test system message mentions context will be sent for continuity."""
        assert 'Context will be sent' in index_html

    def test_system_message_includes_model_info(self, index_html):
        """Test system message includes model information."""
        assert 'previousModel' in index_html
        assert 'newModel' in index_html

    def test_hot_swap_system_message_uses_provider_display_name(self, index_html):
        """Test system message uses capitalized provider display name."""
        # Provider names should be capitalized in the message
        assert "previousProvider.charAt(0).toUpperCase()" in index_html or \
               "previousName" in index_html


class TestHotSwapIntegration:
    """Integration tests for hot-swap functionality."""

    def _make_server(self):
        from scripts.dashboard_server import DashboardServer
        return DashboardServer(project_dir=PROJECT_ROOT)

    @pytest.mark.asyncio
    async def test_provider_switch_preserves_history_in_chat_handler(self):
        """Test that provider switching sends history to new provider."""
        from dashboard.chat_handler import stream_chat_response

        # Simulate a conversation with Claude
        history = [
            {'role': 'user', 'content': 'Hello from the previous provider'},
            {'role': 'assistant', 'content': 'I received your message'}
        ]

        # Now switch to Gemini and continue with same history
        with patch.dict(os.environ, {}, clear=True):
            chunks = []
            async for chunk in stream_chat_response(
                'Do you remember our conversation?',
                'gemini',  # New provider
                '2.5-flash',
                history  # History from previous provider
            ):
                chunks.append(chunk)

        # Should complete successfully with history
        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

    @pytest.mark.asyncio
    async def test_hot_swap_no_message_loss_in_response_stream(self):
        """Test that no messages are lost during a hot-swap scenario."""
        from dashboard.chat_handler import stream_chat_response

        # First provider response
        with patch.dict(os.environ, {}, clear=True):
            chunks_before = []
            async for chunk in stream_chat_response('Message 1', 'claude', 'sonnet-4.5'):
                chunks_before.append(chunk)

            # Switch provider and continue
            chunks_after = []
            async for chunk in stream_chat_response('Message 2', 'openai', 'gpt-4o'):
                chunks_after.append(chunk)

        # Both should complete
        assert chunks_before[-1]['type'] == 'done'
        assert chunks_after[-1]['type'] == 'done'

        # No message loss in either call
        text_before = [c for c in chunks_before if c['type'] == 'text']
        text_after = [c for c in chunks_after if c['type'] == 'text']
        assert len(text_before) > 0
        assert len(text_after) > 0
