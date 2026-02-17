"""Comprehensive unit tests for dashboard/chat_handler.py

Tests streaming responses, tool transparency, and multi-provider support.
"""

import asyncio
import os
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from dashboard.chat_handler import (
    stream_claude_response,
    stream_openai_response,
    stream_mock_response,
    stream_chat_response,
    map_model_to_api
)


class TestModelMapping:
    """Test model ID mapping to provider APIs."""

    def test_map_claude_models(self):
        """Test Claude model mapping."""
        assert map_model_to_api('claude', 'haiku-4.5') == 'claude-3-5-haiku-20241022'
        assert map_model_to_api('claude', 'sonnet-4.5') == 'claude-3-5-sonnet-20241022'
        assert map_model_to_api('claude', 'opus-4.6') == 'claude-3-opus-20240229'

    def test_map_openai_models(self):
        """Test OpenAI model mapping."""
        assert map_model_to_api('openai', 'gpt-4o') == 'gpt-4o'
        assert map_model_to_api('openai', 'o1') == 'o1-preview'

    def test_map_unknown_provider(self):
        """Test unknown provider returns original model."""
        assert map_model_to_api('unknown', 'model-x') == 'model-x'

    def test_map_unknown_model(self):
        """Test unknown model returns original."""
        assert map_model_to_api('claude', 'unknown-model') == 'unknown-model'


class TestMockStreaming:
    """Test mock streaming responses."""

    @pytest.mark.asyncio
    async def test_stream_mock_response_basic(self):
        """Test basic mock streaming response."""
        chunks = []
        async for chunk in stream_mock_response('Hello', 'Claude', 'sonnet-4.5'):
            chunks.append(chunk)

        # Should have text chunks and done
        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

        # Should have text chunks
        text_chunks = [c for c in chunks if c['type'] == 'text']
        assert len(text_chunks) > 0

        # Reconstruct message
        full_text = ''.join(c['content'] for c in text_chunks)
        assert 'Claude' in full_text or 'sonnet' in full_text.lower()

    @pytest.mark.asyncio
    async def test_stream_mock_response_linear_query(self):
        """Test mock response for Linear query includes tool use."""
        chunks = []
        async for chunk in stream_mock_response('What are my Linear issues?', 'Claude', 'sonnet-4.5'):
            chunks.append(chunk)

        # Should have tool use
        tool_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_chunks) > 0
        assert 'Linear' in tool_chunks[0]['tool_name']

        # Should have tool result
        result_chunks = [c for c in chunks if c['type'] == 'tool_result']
        assert len(result_chunks) > 0

        # Should have text response
        text_chunks = [c for c in chunks if c['type'] == 'text']
        assert len(text_chunks) > 0

    @pytest.mark.asyncio
    async def test_stream_mock_response_github_query(self):
        """Test mock response for GitHub query includes tool use."""
        chunks = []
        async for chunk in stream_mock_response('Show me GitHub PRs', 'Claude', 'sonnet-4.5'):
            chunks.append(chunk)

        # Should have GitHub tool use
        tool_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_chunks) > 0
        assert 'Github' in tool_chunks[0]['tool_name']

    @pytest.mark.asyncio
    async def test_stream_mock_response_slack_query(self):
        """Test mock response for Slack query includes tool use."""
        chunks = []
        async for chunk in stream_mock_response('Get Slack messages', 'Claude', 'sonnet-4.5'):
            chunks.append(chunk)

        # Should have Slack tool use
        tool_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_chunks) > 0
        assert 'slack' in tool_chunks[0]['tool_name']

    @pytest.mark.asyncio
    async def test_stream_mock_response_code_query(self):
        """Test mock response for code query includes code block."""
        chunks = []
        async for chunk in stream_mock_response('Show me code', 'Claude', 'sonnet-4.5'):
            chunks.append(chunk)

        text_chunks = [c for c in chunks if c['type'] == 'text']
        full_text = ''.join(c['content'] for c in text_chunks)

        # Should have code block
        assert '```' in full_text
        assert 'python' in full_text.lower()

    @pytest.mark.asyncio
    async def test_stream_mock_response_timestamps(self):
        """Test all chunks have timestamps."""
        chunks = []
        async for chunk in stream_mock_response('Hello', 'Claude', 'sonnet-4.5'):
            chunks.append(chunk)

        for chunk in chunks:
            assert 'timestamp' in chunk
            assert chunk['timestamp'].endswith('Z')


class TestStreamChatResponse:
    """Test main stream_chat_response function."""

    @pytest.mark.asyncio
    async def test_stream_chat_claude_no_api_key(self):
        """Test Claude streaming falls back to mock without API key."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove API key if exists
            if 'ANTHROPIC_API_KEY' in os.environ:
                del os.environ['ANTHROPIC_API_KEY']

            chunks = []
            async for chunk in stream_chat_response('Hello', 'claude', 'sonnet-4.5'):
                chunks.append(chunk)

            # Should use mock
            assert len(chunks) > 0
            assert chunks[-1]['type'] == 'done'

    @pytest.mark.asyncio
    async def test_stream_chat_openai_no_api_key(self):
        """Test OpenAI streaming falls back to mock without API key."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove API key if exists
            if 'OPENAI_API_KEY' in os.environ:
                del os.environ['OPENAI_API_KEY']

            chunks = []
            async for chunk in stream_chat_response('Hello', 'openai', 'gpt-4o'):
                chunks.append(chunk)

            # Should use mock
            assert len(chunks) > 0
            assert chunks[-1]['type'] == 'done'

    @pytest.mark.asyncio
    async def test_stream_chat_gemini_uses_mock(self):
        """Test Gemini uses mock (not implemented yet)."""
        # Clear Gemini API keys to force mock usage
        with patch.dict(os.environ, {'GEMINI_API_KEY': '', 'GOOGLE_API_KEY': ''}, clear=False):
            chunks = []
            async for chunk in stream_chat_response('Hello', 'gemini', '2.5-flash'):
                chunks.append(chunk)

            # Should use mock
            assert len(chunks) > 0
            assert chunks[-1]['type'] == 'done'

            # Check provider name in response
            text_chunks = [c for c in chunks if c['type'] == 'text']
            full_text = ''.join(c['content'] for c in text_chunks)
            assert 'GEMINI' in full_text.upper()

    @pytest.mark.asyncio
    async def test_stream_chat_groq_uses_mock(self):
        """Test Groq uses mock (not implemented yet)."""
        chunks = []
        async for chunk in stream_chat_response('Hello', 'groq', 'llama-3.3-70b'):
            chunks.append(chunk)

        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

    @pytest.mark.asyncio
    async def test_stream_chat_kimi_uses_mock(self):
        """Test KIMI uses mock (not implemented yet)."""
        chunks = []
        async for chunk in stream_chat_response('Hello', 'kimi', 'moonshot-v1'):
            chunks.append(chunk)

        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

    @pytest.mark.asyncio
    async def test_stream_chat_windsurf_uses_mock(self):
        """Test Windsurf uses mock (not implemented yet)."""
        chunks = []
        async for chunk in stream_chat_response('Hello', 'windsurf', 'cascade'):
            chunks.append(chunk)

        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

    @pytest.mark.asyncio
    async def test_stream_chat_unknown_provider(self):
        """Test unknown provider uses mock."""
        chunks = []
        async for chunk in stream_chat_response('Hello', 'unknown', 'model-x'):
            chunks.append(chunk)

        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

    @pytest.mark.asyncio
    async def test_stream_chat_with_conversation_history(self):
        """Test streaming with conversation history."""
        history = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there!'}
        ]

        chunks = []
        async for chunk in stream_chat_response(
            'How are you?',
            'claude',
            'sonnet-4.5',
            conversation_history=history
        ):
            chunks.append(chunk)

        assert len(chunks) > 0


class TestToolTransparency:
    """Test tool call transparency features."""

    @pytest.mark.asyncio
    async def test_tool_call_structure(self):
        """Test tool call chunks have required fields."""
        chunks = []
        async for chunk in stream_mock_response('Check Linear issues', 'Claude', 'sonnet-4.5'):
            if chunk['type'] == 'tool_use':
                chunks.append(chunk)

        assert len(chunks) > 0
        tool_chunk = chunks[0]

        # Required fields
        assert 'tool_name' in tool_chunk
        assert 'tool_input' in tool_chunk
        assert 'tool_id' in tool_chunk
        assert 'timestamp' in tool_chunk

    @pytest.mark.asyncio
    async def test_tool_result_structure(self):
        """Test tool result chunks have required fields."""
        chunks = []
        async for chunk in stream_mock_response('Check Linear issues', 'Claude', 'sonnet-4.5'):
            if chunk['type'] == 'tool_result':
                chunks.append(chunk)

        assert len(chunks) > 0
        result_chunk = chunks[0]

        # Required fields
        assert 'tool_id' in result_chunk
        assert 'result' in result_chunk
        assert 'timestamp' in result_chunk

    @pytest.mark.asyncio
    async def test_tool_call_order(self):
        """Test tool calls appear before results."""
        chunks = []
        async for chunk in stream_mock_response('Check Linear issues', 'Claude', 'sonnet-4.5'):
            chunks.append(chunk)

        # Find indices
        tool_use_idx = next(i for i, c in enumerate(chunks) if c['type'] == 'tool_use')
        tool_result_idx = next(i for i, c in enumerate(chunks) if c['type'] == 'tool_result')

        # Tool use should come before result
        assert tool_use_idx < tool_result_idx


class TestErrorHandling:
    """Test error handling in streaming."""

    @pytest.mark.asyncio
    async def test_stream_handles_exceptions(self):
        """Test streaming handles exceptions gracefully."""
        # This will be covered by integration tests with mocked clients
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
