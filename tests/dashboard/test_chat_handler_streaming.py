"""Unit tests for dashboard/chat_handler.py streaming functionality

Tests the new stream_chat_response function with provider bridge integration.
"""

import asyncio
import os
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from dashboard.chat_handler import (
    ChatRouter,
    stream_chat_response,
    get_chat_history,
    clear_chat_history,
)


class TestStreamChatResponse:
    """Test stream_chat_response function."""

    @pytest.mark.asyncio
    async def test_stream_chat_no_provider_bridge(self):
        """Test streaming when provider bridge is unavailable."""
        with patch('dashboard.chat_handler._get_provider_bridge_registry', return_value=None):
            chunks = []
            async for chunk in stream_chat_response('Hello', 'claude', 'sonnet-4.5'):
                chunks.append(chunk)

            # Should return fallback message
            assert len(chunks) >= 2
            assert chunks[0]['type'] == 'token'
            assert 'Configure an API key' in chunks[0]['content']
            assert chunks[-1]['type'] == 'done'

    @pytest.mark.asyncio
    async def test_stream_chat_unknown_provider(self):
        """Test streaming with unknown provider."""
        # Mock registry that raises KeyError for unknown provider
        mock_registry = MagicMock()
        mock_registry.get.side_effect = KeyError('unknown')

        with patch('dashboard.chat_handler._get_provider_bridge_registry', return_value=mock_registry):
            chunks = []
            async for chunk in stream_chat_response('Hello', 'unknown', 'model-x'):
                chunks.append(chunk)

            # Should return error
            assert len(chunks) >= 1
            assert chunks[0]['type'] == 'error'
            assert 'Unknown provider' in chunks[0]['content']

    @pytest.mark.asyncio
    async def test_stream_chat_no_api_key(self):
        """Test streaming when API key is not configured."""
        # Mock bridge that is not available
        mock_bridge = MagicMock()
        mock_bridge.is_available.return_value = False

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_bridge

        with patch('dashboard.chat_handler._get_provider_bridge_registry', return_value=mock_registry):
            chunks = []
            async for chunk in stream_chat_response('Hello', 'claude', 'sonnet-4.5'):
                chunks.append(chunk)

            # Should return fallback message
            assert len(chunks) >= 2
            assert chunks[0]['type'] == 'token'
            assert 'Configure an API key' in chunks[0]['content']
            assert chunks[-1]['type'] == 'done'

    @pytest.mark.asyncio
    async def test_stream_chat_successful_response(self):
        """Test streaming with successful provider response."""
        # Mock bridge with successful response
        mock_bridge = MagicMock()
        mock_bridge.is_available.return_value = True
        mock_bridge.send_message_async = AsyncMock(return_value="This is a test response from Claude.")

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_bridge

        with patch('dashboard.chat_handler._get_provider_bridge_registry', return_value=mock_registry):
            chunks = []
            async for chunk in stream_chat_response('Hello', 'claude', 'sonnet-4.5'):
                chunks.append(chunk)

            # Should have token chunks and done
            assert len(chunks) > 1
            token_chunks = [c for c in chunks if c['type'] == 'token']
            assert len(token_chunks) > 0

            # Last chunk should be done
            assert chunks[-1]['type'] == 'done'
            assert chunks[-1]['content'] == "This is a test response from Claude."

            # Verify send_message_async was called
            mock_bridge.send_message_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_chat_with_conversation_history(self):
        """Test streaming with conversation history."""
        # Mock bridge
        mock_bridge = MagicMock()
        mock_bridge.is_available.return_value = True
        mock_bridge.send_message_async = AsyncMock(return_value="Response with context")

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_bridge

        history = [
            {'sender': 'user', 'text': 'Hello'},
            {'sender': 'ai', 'text': 'Hi there!'}
        ]

        with patch('dashboard.chat_handler._get_provider_bridge_registry', return_value=mock_registry):
            chunks = []
            async for chunk in stream_chat_response(
                'How are you?',
                'claude',
                'sonnet-4.5',
                conversation_history=history
            ):
                chunks.append(chunk)

            # Verify context was passed
            call_args = mock_bridge.send_message_async.call_args
            assert call_args is not None
            assert 'context' in call_args.kwargs
            context = call_args.kwargs['context']
            assert 'user: Hello' in context
            assert 'ai: Hi there!' in context

    @pytest.mark.asyncio
    async def test_stream_chat_provider_error(self):
        """Test streaming when provider raises an error."""
        # Mock bridge that raises an error
        mock_bridge = MagicMock()
        mock_bridge.is_available.return_value = True
        mock_bridge.send_message_async = AsyncMock(side_effect=Exception("API Error"))

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_bridge

        with patch('dashboard.chat_handler._get_provider_bridge_registry', return_value=mock_registry):
            chunks = []
            async for chunk in stream_chat_response('Hello', 'claude', 'sonnet-4.5'):
                chunks.append(chunk)

            # Should return error chunk
            assert len(chunks) >= 1
            assert chunks[-1]['type'] == 'error'
            assert 'Error communicating' in chunks[-1]['content']

    @pytest.mark.asyncio
    async def test_stream_chat_all_chunks_have_metadata(self):
        """Test all chunks have required metadata."""
        mock_bridge = MagicMock()
        mock_bridge.is_available.return_value = True
        mock_bridge.send_message_async = AsyncMock(return_value="Test response")

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_bridge

        with patch('dashboard.chat_handler._get_provider_bridge_registry', return_value=mock_registry):
            chunks = []
            async for chunk in stream_chat_response('Hello', 'claude', 'sonnet-4.5'):
                chunks.append(chunk)

            # All chunks should have required fields
            for chunk in chunks:
                assert 'type' in chunk
                assert 'content' in chunk
                assert 'timestamp' in chunk
                assert 'provider' in chunk
                assert 'model' in chunk
                assert chunk['timestamp'].endswith('Z')
                assert chunk['provider'] == 'claude'
                assert chunk['model'] == 'sonnet-4.5'


class TestChatRouter:
    """Test ChatRouter class."""

    def test_chat_router_init(self):
        """Test ChatRouter initialization."""
        router = ChatRouter()
        assert router is not None
        assert router.websockets is not None
        assert router.executor is not None

    @pytest.mark.asyncio
    async def test_chat_router_handle_message(self):
        """Test ChatRouter.handle_message with conversation intent."""
        router = ChatRouter()

        # Mock provider bridge
        mock_bridge = MagicMock()
        mock_bridge.is_available.return_value = True
        mock_bridge.send_message_async = AsyncMock(return_value="Hello! I'm Claude.")

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_bridge

        with patch('dashboard.chat_handler._get_provider_bridge_registry', return_value=mock_registry):
            result = await router.handle_message("Hello", provider="claude")

            assert result is not None
            assert 'message_id' in result
            assert 'response' in result
            assert result['response'] == "Hello! I'm Claude."
            assert result['provider'] == 'claude'

    @pytest.mark.asyncio
    async def test_chat_router_parse_intent(self):
        """Test ChatRouter.parse method."""
        router = ChatRouter()

        # Test conversation intent
        intent = router.parse("Hello, how are you?")
        assert intent.intent_type in ['conversation', 'agent_action', 'query']

    def test_get_routing_decision_conversation(self):
        """Test routing decision for conversation intent."""
        router = ChatRouter()

        from dashboard.intent_parser import ParsedIntent
        intent = ParsedIntent(
            intent_type='conversation',
            agent=None,
            action=None,
            params={},
            original_message='Hello'
        )

        decision = router.get_routing_decision(intent)
        assert decision['handler'] == 'ai_provider'
        assert decision['intent_type'] == 'conversation'


class TestChatHistory:
    """Test chat history management."""

    def test_get_chat_history(self):
        """Test getting chat history."""
        clear_chat_history()
        history = get_chat_history()
        assert isinstance(history, list)

    def test_clear_chat_history(self):
        """Test clearing chat history."""
        clear_chat_history()
        history = get_chat_history()
        assert len(history) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
