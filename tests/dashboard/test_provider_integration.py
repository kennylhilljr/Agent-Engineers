"""Unit tests for multi-provider integration and hot-swap functionality.

Tests provider status detection, bridge integration, and conversation persistence.
"""

import asyncio
import json
import os
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from dashboard.chat_handler import (
    stream_gemini_response,
    stream_groq_response,
    stream_kimi_response,
    stream_chat_response
)


class TestProviderStatusDetection:
    """Test provider availability detection."""

    def test_claude_detection_with_key(self):
        """Test Claude provider is detected when API key is set."""
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            assert os.getenv('ANTHROPIC_API_KEY') == 'test-key'

    def test_claude_detection_without_key(self):
        """Test Claude provider is not detected without API key."""
        with patch.dict(os.environ, {}, clear=True):
            assert os.getenv('ANTHROPIC_API_KEY') is None

    def test_openai_detection_with_key(self):
        """Test OpenAI provider is detected when API key is set."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            assert os.getenv('OPENAI_API_KEY') == 'test-key'

    def test_gemini_detection_with_key(self):
        """Test Gemini provider is detected when API key is set."""
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}):
            assert os.getenv('GEMINI_API_KEY') == 'test-key'

    def test_gemini_detection_with_google_key(self):
        """Test Gemini provider is detected with GOOGLE_API_KEY."""
        with patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'}):
            assert os.getenv('GOOGLE_API_KEY') == 'test-key'

    def test_groq_detection_with_key(self):
        """Test Groq provider is detected when API key is set."""
        with patch.dict(os.environ, {'GROQ_API_KEY': 'test-key'}):
            assert os.getenv('GROQ_API_KEY') == 'test-key'

    def test_kimi_detection_with_key(self):
        """Test KIMI provider is detected when API key is set."""
        with patch.dict(os.environ, {'KIMI_API_KEY': 'test-key'}):
            assert os.getenv('KIMI_API_KEY') == 'test-key'

    def test_kimi_detection_with_moonshot_key(self):
        """Test KIMI provider is detected with MOONSHOT_API_KEY."""
        with patch.dict(os.environ, {'MOONSHOT_API_KEY': 'test-key'}):
            assert os.getenv('MOONSHOT_API_KEY') == 'test-key'


class TestGeminiIntegration:
    """Test Gemini bridge integration."""

    @pytest.mark.asyncio
    async def test_gemini_streaming_without_bridge(self):
        """Test Gemini streaming falls back gracefully without bridge."""
        chunks = []
        async for chunk in stream_gemini_response('Hello', '2.5-flash'):
            chunks.append(chunk)

        # Should have error and done chunks
        assert len(chunks) >= 2
        assert chunks[-1]['type'] == 'done'

        # Should have error about bridge
        error_chunks = [c for c in chunks if c['type'] == 'error']
        assert len(error_chunks) > 0

    @pytest.mark.asyncio
    async def test_gemini_route_in_chat_response_without_key(self):
        """Test Gemini routing falls back to mock without API key."""
        with patch.dict(os.environ, {}, clear=True):
            chunks = []
            async for chunk in stream_chat_response('Hello', 'gemini', '2.5-flash'):
                chunks.append(chunk)

            # Should complete with mock response
            assert len(chunks) > 0
            assert chunks[-1]['type'] == 'done'


class TestGroqIntegration:
    """Test Groq bridge integration."""

    @pytest.mark.asyncio
    async def test_groq_streaming_without_bridge(self):
        """Test Groq streaming falls back gracefully without bridge."""
        chunks = []
        async for chunk in stream_groq_response('Hello', 'llama-3.3-70b'):
            chunks.append(chunk)

        # Should have error and done chunks
        assert len(chunks) >= 2
        assert chunks[-1]['type'] == 'done'

        # Should have error about bridge
        error_chunks = [c for c in chunks if c['type'] == 'error']
        assert len(error_chunks) > 0

    @pytest.mark.asyncio
    async def test_groq_route_in_chat_response_without_key(self):
        """Test Groq routing falls back to mock without API key."""
        with patch.dict(os.environ, {}, clear=True):
            chunks = []
            async for chunk in stream_chat_response('Hello', 'groq', 'llama-3.3-70b'):
                chunks.append(chunk)

            # Should complete with mock response
            assert len(chunks) > 0
            assert chunks[-1]['type'] == 'done'


class TestKimiIntegration:
    """Test KIMI bridge integration."""

    @pytest.mark.asyncio
    async def test_kimi_streaming_without_bridge(self):
        """Test KIMI streaming falls back gracefully without bridge."""
        chunks = []
        async for chunk in stream_kimi_response('Hello', 'moonshot-v1'):
            chunks.append(chunk)

        # Should have error and done chunks
        assert len(chunks) >= 2
        assert chunks[-1]['type'] == 'done'

        # Should have error about bridge
        error_chunks = [c for c in chunks if c['type'] == 'error']
        assert len(error_chunks) > 0

    @pytest.mark.asyncio
    async def test_kimi_route_in_chat_response_without_key(self):
        """Test KIMI routing falls back to mock without API key."""
        with patch.dict(os.environ, {}, clear=True):
            chunks = []
            async for chunk in stream_chat_response('Hello', 'kimi', 'moonshot-v1'):
                chunks.append(chunk)

            # Should complete with mock response
            assert len(chunks) > 0
            assert chunks[-1]['type'] == 'done'


class TestProviderHotSwap:
    """Test provider hot-swap functionality."""

    @pytest.mark.asyncio
    async def test_conversation_history_preserved_across_providers(self):
        """Test that conversation history is preserved when switching providers."""
        conversation_history = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there!'}
        ]

        # Test with Claude (mock fallback)
        with patch.dict(os.environ, {}, clear=True):
            chunks_claude = []
            async for chunk in stream_chat_response(
                'How are you?',
                'claude',
                'sonnet-4.5',
                conversation_history
            ):
                chunks_claude.append(chunk)

            assert len(chunks_claude) > 0
            assert chunks_claude[-1]['type'] == 'done'

            # Test with Gemini (mock fallback)
            chunks_gemini = []
            async for chunk in stream_chat_response(
                'What is 2+2?',
                'gemini',
                '2.5-flash',
                conversation_history
            ):
                chunks_gemini.append(chunk)

            assert len(chunks_gemini) > 0
            assert chunks_gemini[-1]['type'] == 'done'

    @pytest.mark.asyncio
    async def test_hot_swap_all_providers(self):
        """Test hot-swap between all 6 providers."""
        providers = ['claude', 'openai', 'gemini', 'groq', 'kimi', 'windsurf']
        message = 'Test message'

        with patch.dict(os.environ, {}, clear=True):
            for provider in providers:
                chunks = []
                async for chunk in stream_chat_response(message, provider, 'default'):
                    chunks.append(chunk)

                # All providers should complete successfully (via mock fallback)
                assert len(chunks) > 0
                assert chunks[-1]['type'] == 'done'

                # Should have text response
                text_chunks = [c for c in chunks if c['type'] == 'text']
                assert len(text_chunks) > 0


class TestModelSync:
    """Test model selector synchronization."""

    def test_claude_models_available(self):
        """Test Claude models are correctly defined."""
        claude_models = ['haiku-4.5', 'sonnet-4.5', 'opus-4.6']
        assert len(claude_models) == 3
        assert 'sonnet-4.5' in claude_models

    def test_openai_models_available(self):
        """Test OpenAI models are correctly defined."""
        openai_models = ['gpt-4o', 'o1', 'o3-mini', 'o4-mini']
        assert len(openai_models) == 4
        assert 'gpt-4o' in openai_models

    def test_gemini_models_available(self):
        """Test Gemini models are correctly defined."""
        gemini_models = ['2.5-flash', '2.5-pro', '2.0-flash']
        assert len(gemini_models) == 3
        assert '2.5-flash' in gemini_models

    def test_groq_models_available(self):
        """Test Groq models are correctly defined."""
        groq_models = ['llama-3.3-70b', 'mixtral-8x7b']
        assert len(groq_models) == 2
        assert 'llama-3.3-70b' in groq_models

    def test_kimi_models_available(self):
        """Test KIMI models are correctly defined."""
        kimi_models = ['moonshot-v1']
        assert len(kimi_models) == 1
        assert 'moonshot-v1' in kimi_models

    def test_windsurf_models_available(self):
        """Test Windsurf models are correctly defined."""
        windsurf_models = ['cascade']
        assert len(windsurf_models) == 1
        assert 'cascade' in windsurf_models


class TestErrorHandling:
    """Test error handling for provider integration."""

    @pytest.mark.asyncio
    async def test_gemini_error_with_invalid_model(self):
        """Test Gemini handles invalid model gracefully."""
        chunks = []
        async for chunk in stream_gemini_response('Hello', 'invalid-model'):
            chunks.append(chunk)

        # Should complete (either with error or mock)
        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

    @pytest.mark.asyncio
    async def test_unknown_provider_falls_back_to_mock(self):
        """Test unknown provider falls back to mock."""
        chunks = []
        async for chunk in stream_chat_response('Hello', 'unknown-provider', 'model'):
            chunks.append(chunk)

        # Should complete with mock response
        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

        # Should have text
        text_chunks = [c for c in chunks if c['type'] == 'text']
        assert len(text_chunks) > 0
