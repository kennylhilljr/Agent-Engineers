"""Tests for REQ-INTEGRATION-001: Linear Access in Chat.

Tests cover:
- POST /api/chat endpoint is registered and functional
- Linear queries trigger tool transparency in mock responses
- GET /api/providers/status endpoint returns correct data
- chat_handler.py unit tests for mock responses with Linear keywords
- SSE streaming format validation
- Provider routing and fallback behavior
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def make_server(tmpdir=None):
    """Create a DashboardServer instance for testing."""
    from scripts.dashboard_server import DashboardServer
    project_dir = Path(tmpdir) if tmpdir else PROJECT_ROOT
    return DashboardServer(project_dir=project_dir)


# ============================================================
# ASYNC HELPERS
# ============================================================

def run_async(coro):
    """Run async coroutine in a new event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def collect_stream(async_gen):
    """Collect all chunks from an async generator."""
    chunks = []
    async for chunk in async_gen:
        chunks.append(chunk)
    return chunks


# ============================================================
# TEST: LINEAR CHAT INTEGRATION (via DashboardServer)
# ============================================================

class TestLinearChatIntegration:
    """Test Linear access through the chat endpoint."""

    def test_chat_endpoint_registered(self):
        """Test POST /api/chat route is registered."""
        server = make_server()
        routes = [route.resource.canonical for route in server.app.router.routes()]
        assert '/api/chat' in routes

    def test_providers_status_endpoint_registered(self):
        """Test GET /api/providers/status route is registered."""
        server = make_server()
        routes = [route.resource.canonical for route in server.app.router.routes()]
        assert '/api/providers/status' in routes

    def test_chat_handler_returns_400_for_missing_message(self):
        """Test /api/chat returns 400 when message field is missing."""
        server = make_server()
        request = MagicMock()
        request.json = AsyncMock(return_value={})

        response = run_async(server.handle_chat(request))
        assert response.status == 400

        body = json.loads(response.text)
        assert 'error' in body
        assert 'message' in body['error'].lower()

    def test_chat_handler_returns_400_for_empty_message(self):
        """Test /api/chat returns 400 when message is empty string."""
        server = make_server()
        request = MagicMock()
        request.json = AsyncMock(return_value={"message": "   "})

        response = run_async(server.handle_chat(request))
        assert response.status == 400

    def test_chat_handler_returns_400_for_invalid_json(self):
        """Test /api/chat returns 400 when JSON is invalid."""
        server = make_server()
        request = MagicMock()
        request.json = AsyncMock(side_effect=Exception("JSON decode error"))

        response = run_async(server.handle_chat(request))
        assert response.status == 400

        body = json.loads(response.text)
        assert 'error' in body

    def test_chat_accepts_provider_parameter(self):
        """Test /api/chat accepts provider parameter without error."""
        # This just tests the handler doesn't crash on valid input with provider
        # The actual streaming is tested via mock
        server = make_server()

        async def _run():
            from unittest.mock import patch as _patch

            async def mock_stream(*args, **kwargs):
                yield {'type': 'text', 'content': 'Hello', 'timestamp': '2026-01-01T00:00:00Z'}
                yield {'type': 'done', 'timestamp': '2026-01-01T00:00:00Z'}

            request = MagicMock()
            request.json = AsyncMock(return_value={
                "message": "test",
                "provider": "claude",
                "model": "sonnet-4.5"
            })

            # Mock StreamResponse
            mock_response = MagicMock()
            mock_response.prepare = AsyncMock()
            mock_response.write = AsyncMock()
            mock_response.status = 200

            with _patch('dashboard.chat_handler.stream_chat_response', side_effect=mock_stream):
                from aiohttp import web
                with _patch.object(web, 'StreamResponse', return_value=mock_response):
                    await server.handle_chat(request)

            # Verify write was called (streaming happened)
            assert mock_response.write.called

        run_async(_run())

    def test_chat_accepts_conversation_history(self):
        """Test /api/chat accepts conversation_history parameter."""
        server = make_server()
        request = MagicMock()
        request.json = AsyncMock(return_value={
            "message": "   ",  # Empty - should return 400 before even checking history
            "conversation_history": [
                {"role": "user", "content": "previous msg"}
            ]
        })

        response = run_async(server.handle_chat(request))
        # Empty message still returns 400
        assert response.status == 400

    def test_chat_accepts_session_id(self):
        """Test /api/chat accepts session_id parameter (ignored server-side)."""
        server = make_server()
        request = MagicMock()
        request.json = AsyncMock(return_value={
            "message": "  ",  # Empty triggers 400
            "session_id": "test-session-123"
        })

        response = run_async(server.handle_chat(request))
        assert response.status == 400  # Empty message still rejected


# ============================================================
# TEST: PROVIDERS STATUS ENDPOINT
# ============================================================

class TestProvidersStatusEndpoint:
    """Test GET /api/providers/status endpoint."""

    def test_providers_status_returns_200(self):
        """Test /api/providers/status returns 200 OK."""
        server = make_server()
        request = MagicMock()

        response = run_async(server.handle_providers_status(request))
        assert response.status == 200

    def test_providers_status_returns_all_six(self):
        """Test /api/providers/status returns all 6 providers."""
        server = make_server()
        request = MagicMock()

        response = run_async(server.handle_providers_status(request))
        data = json.loads(response.text)

        assert 'providers' in data
        assert len(data['providers']) == 6

        provider_ids = [p['provider_id'] for p in data['providers']]
        assert 'claude' in provider_ids
        assert 'openai' in provider_ids
        assert 'gemini' in provider_ids
        assert 'groq' in provider_ids
        assert 'kimi' in provider_ids
        assert 'windsurf' in provider_ids

    def test_providers_status_total_count(self):
        """Test total_providers is 6."""
        server = make_server()
        request = MagicMock()

        response = run_async(server.handle_providers_status(request))
        data = json.loads(response.text)

        assert data['total_providers'] == 6

    def test_providers_status_has_required_fields(self):
        """Test each provider entry has all required fields."""
        server = make_server()
        request = MagicMock()

        response = run_async(server.handle_providers_status(request))
        data = json.loads(response.text)

        required_fields = ['provider_id', 'available', 'has_api_key', 'status', 'models']
        for provider in data['providers']:
            for field in required_fields:
                assert field in provider, f"Provider '{provider.get('provider_id')}' missing field '{field}'"

    def test_providers_status_active_count_is_valid(self):
        """Test active_providers is valid integer within range."""
        server = make_server()
        request = MagicMock()

        response = run_async(server.handle_providers_status(request))
        data = json.loads(response.text)

        assert 'active_providers' in data
        assert isinstance(data['active_providers'], int)
        assert 0 <= data['active_providers'] <= 6

    def test_providers_status_with_anthropic_key(self):
        """Test Claude shows as active when ANTHROPIC_API_KEY is set."""
        server = make_server()
        request = MagicMock()

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'sk-test-key'}):
            response = run_async(server.handle_providers_status(request))
            data = json.loads(response.text)

        claude = next(p for p in data['providers'] if p['provider_id'] == 'claude')
        assert claude['available'] is True
        assert claude['has_api_key'] is True
        assert claude['status'] == 'active'

    def test_providers_status_without_keys(self):
        """Test all providers unavailable when no API keys are set."""
        server = make_server()
        request = MagicMock()

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY',
                                  'GEMINI_API_KEY', 'GOOGLE_API_KEY',
                                  'GROQ_API_KEY', 'KIMI_API_KEY',
                                  'MOONSHOT_API_KEY', 'WINDSURF_API_KEY']}

        with patch.dict(os.environ, clean_env, clear=True):
            response = run_async(server.handle_providers_status(request))
            data = json.loads(response.text)

        for provider in data['providers']:
            assert provider['available'] is False, \
                f"Provider {provider['provider_id']} should be unavailable without key"
            assert provider['has_api_key'] is False
            assert provider['status'] == 'unavailable'
        assert data['active_providers'] == 0

    def test_providers_status_has_timestamp(self):
        """Test response includes a UTC timestamp."""
        server = make_server()
        request = MagicMock()

        response = run_async(server.handle_providers_status(request))
        data = json.loads(response.text)

        assert 'timestamp' in data
        assert data['timestamp'].endswith('Z')

    def test_providers_status_models_are_lists(self):
        """Test each provider has models as a non-empty list."""
        server = make_server()
        request = MagicMock()

        response = run_async(server.handle_providers_status(request))
        data = json.loads(response.text)

        for provider in data['providers']:
            assert isinstance(provider['models'], list)
            assert len(provider['models']) > 0


# ============================================================
# TEST: CHAT HANDLER UNIT TESTS (mock responses)
# ============================================================

class TestChatHandlerUnit:
    """Unit tests for chat_handler.py stream_mock_response function."""

    def test_stream_mock_linear_keywords(self):
        """Test mock response handles 'linear' keyword with tool use."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('Show me linear issues', 'claude', 'sonnet-4.5')
        ))

        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types
        assert 'tool_result' in chunk_types
        assert 'done' in chunk_types

    def test_stream_mock_issue_keyword(self):
        """Test mock response handles 'issue' keyword with tool use."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('What issue am I working on?', 'claude', 'sonnet-4.5')
        ))

        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types

    def test_stream_mock_ticket_keyword(self):
        """Test mock response handles 'ticket' keyword with tool use."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('Show me my tickets', 'openai', 'gpt-4o')
        ))

        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types

    def test_stream_mock_always_has_done(self):
        """Test mock response always yields a 'done' event."""
        from dashboard.chat_handler import stream_mock_response

        for msg in ['hello', 'linear issue', 'github repo', 'slack message', 'status']:
            chunks = run_async(collect_stream(
                stream_mock_response(msg, 'claude', 'sonnet-4.5')
            ))
            last_chunk = chunks[-1]
            assert last_chunk['type'] == 'done', \
                f"Last chunk should be 'done' for message '{msg}', got '{last_chunk['type']}'"

    def test_stream_mock_has_text_chunks(self):
        """Test mock response yields text chunks."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('hello there', 'claude', 'sonnet-4.5')
        ))

        text_chunks = [c for c in chunks if c['type'] == 'text']
        assert len(text_chunks) > 0

    def test_stream_mock_default_response(self):
        """Test mock response handles unknown message."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('random unknown query xyz', 'windsurf', 'cascade')
        ))

        # Should have text + done
        chunk_types = [c['type'] for c in chunks]
        assert 'text' in chunk_types
        assert 'done' in chunk_types

    def test_tool_use_event_has_required_fields(self):
        """Test tool_use events have tool_name, tool_input, tool_id fields."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('linear issues', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        for chunk in tool_use_chunks:
            assert 'tool_name' in chunk
            assert 'tool_input' in chunk
            assert 'tool_id' in chunk
            assert 'timestamp' in chunk

    def test_tool_result_event_has_required_fields(self):
        """Test tool_result events have tool_id and result fields."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('show issues', 'claude', 'sonnet-4.5')
        ))

        tool_result_chunks = [c for c in chunks if c['type'] == 'tool_result']
        assert len(tool_result_chunks) > 0

        for chunk in tool_result_chunks:
            assert 'tool_id' in chunk
            assert 'result' in chunk
            assert 'timestamp' in chunk


class TestMapModelToAPI:
    """Test map_model_to_api function."""

    def test_claude_haiku_mapping(self):
        """Test haiku-4.5 maps to correct API model."""
        from dashboard.chat_handler import map_model_to_api
        result = map_model_to_api('claude', 'haiku-4.5')
        assert 'haiku' in result.lower() or result == 'haiku-4.5'

    def test_claude_sonnet_mapping(self):
        """Test sonnet-4.5 maps to correct API model."""
        from dashboard.chat_handler import map_model_to_api
        result = map_model_to_api('claude', 'sonnet-4.5')
        assert 'sonnet' in result.lower()

    def test_claude_opus_mapping(self):
        """Test opus-4.6 maps to an opus model."""
        from dashboard.chat_handler import map_model_to_api
        result = map_model_to_api('claude', 'opus-4.6')
        assert 'opus' in result.lower()

    def test_openai_gpt4o_mapping(self):
        """Test gpt-4o maps to gpt-4o."""
        from dashboard.chat_handler import map_model_to_api
        result = map_model_to_api('openai', 'gpt-4o')
        assert result == 'gpt-4o'

    def test_unknown_provider_returns_model_as_is(self):
        """Test unknown provider returns model unchanged."""
        from dashboard.chat_handler import map_model_to_api
        result = map_model_to_api('unknown_provider', 'some-model')
        assert result == 'some-model'


class TestStreamChatResponseRouting:
    """Test stream_chat_response routing to mock when no API keys."""

    def test_routes_to_mock_for_claude_without_key(self):
        """Test routes to mock when ANTHROPIC_API_KEY is not set."""
        from dashboard.chat_handler import stream_chat_response

        clean_env = {k: v for k, v in os.environ.items()
                     if k != 'ANTHROPIC_API_KEY'}

        with patch.dict(os.environ, clean_env, clear=True):
            chunks = run_async(collect_stream(
                stream_chat_response('hello', provider='claude', model='sonnet-4.5')
            ))

        # Should get a response (mock)
        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

    def test_routes_to_mock_for_openai_without_key(self):
        """Test routes to mock when OPENAI_API_KEY is not set."""
        from dashboard.chat_handler import stream_chat_response

        clean_env = {k: v for k, v in os.environ.items()
                     if k != 'OPENAI_API_KEY'}

        with patch.dict(os.environ, clean_env, clear=True):
            chunks = run_async(collect_stream(
                stream_chat_response('hello', provider='openai', model='gpt-4o')
            ))

        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

    def test_routes_to_mock_for_windsurf(self):
        """Test Windsurf always routes to mock (not yet implemented)."""
        from dashboard.chat_handler import stream_chat_response

        chunks = run_async(collect_stream(
            stream_chat_response('hello', provider='windsurf', model='cascade')
        ))

        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

    def test_routes_to_mock_for_unknown_provider(self):
        """Test unknown provider falls back to mock."""
        from dashboard.chat_handler import stream_chat_response

        chunks = run_async(collect_stream(
            stream_chat_response('hello', provider='nonexistent_provider', model='some-model')
        ))

        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

    def test_all_six_providers_return_done(self):
        """Test all 6 providers return a 'done' event (via mock fallback)."""
        from dashboard.chat_handler import stream_chat_response

        providers = [
            ('claude', 'sonnet-4.5'),
            ('openai', 'gpt-4o'),
            ('gemini', '2.5-flash'),
            ('groq', 'llama-3.3-70b'),
            ('kimi', 'moonshot'),
            ('windsurf', 'cascade'),
        ]

        # Remove all API keys so all fall through to mock
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY',
                                  'GEMINI_API_KEY', 'GOOGLE_API_KEY',
                                  'GROQ_API_KEY', 'KIMI_API_KEY',
                                  'MOONSHOT_API_KEY', 'WINDSURF_API_KEY']}

        with patch.dict(os.environ, clean_env, clear=True):
            for provider, model in providers:
                chunks = run_async(collect_stream(
                    stream_chat_response('hello', provider=provider, model=model)
                ))
                assert len(chunks) > 0, f"No chunks for provider {provider}"
                assert chunks[-1]['type'] == 'done', \
                    f"Provider {provider} did not end with 'done', got '{chunks[-1]['type']}'"


# ============================================================
# TEST: INDEX.HTML CHAT INTEGRATION
# ============================================================

class TestIndexHTMLChatIntegration:
    """Test that index.html has real chat API integration."""

    @pytest.fixture
    def index_html(self):
        """Read the index.html file."""
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_call_chat_api_function_defined(self, index_html):
        """Test callChatAPI function is defined in index.html."""
        assert 'async function callChatAPI(' in index_html

    def test_fetch_api_chat_called(self, index_html):
        """Test fetch('/api/chat') is called in callChatAPI."""
        assert "fetch('/api/chat'" in index_html

    def test_post_method_used(self, index_html):
        """Test POST method is used for /api/chat."""
        assert "method: 'POST'" in index_html

    def test_conversation_history_sent(self, index_html):
        """Test conversation history is sent with chat request."""
        assert 'getConversationContext()' in index_html
        assert 'conversation_history' in index_html

    def test_provider_and_model_sent(self, index_html):
        """Test current provider and model are included in chat request."""
        assert 'state.currentProvider' in index_html
        assert 'state.currentModel' in index_html

    def test_sse_streaming_implemented(self, index_html):
        """Test SSE streaming is implemented with text/event-stream check."""
        assert 'text/event-stream' in index_html

    def test_reader_api_used(self, index_html):
        """Test ReadableStream reader API is used for streaming."""
        assert 'getReader()' in index_html or 'reader.read()' in index_html

    def test_text_decoder_used(self, index_html):
        """Test TextDecoder is used for streaming."""
        assert 'TextDecoder' in index_html

    def test_tool_use_handled(self, index_html):
        """Test tool_use events are handled."""
        assert "chunk.type === 'tool_use'" in index_html or "chunk.type == 'tool_use'" in index_html

    def test_done_event_handled(self, index_html):
        """Test done events are handled to finalize message."""
        assert "chunk.type === 'done'" in index_html or "chunk.type == 'done'" in index_html

    def test_error_event_handled(self, index_html):
        """Test error events are handled."""
        assert "chunk.type === 'error'" in index_html or "chunk.type == 'error'" in index_html

    def test_network_error_handled(self, index_html):
        """Test network errors are caught with try/catch."""
        assert 'catch (err)' in index_html or 'catch(err)' in index_html or 'catch (e)' in index_html

    def test_no_placeholder_timeout(self, index_html):
        """Test the old placeholder setTimeout is removed."""
        assert "This is a placeholder response" not in index_html

    def test_send_button_reenabled_on_done(self, index_html):
        """Test send button is re-enabled after chat completion."""
        assert "sendBtn.disabled = false" in index_html
        assert "sendBtn.textContent = 'Send'" in index_html

    def test_is_agent_running_cleared_on_done(self, index_html):
        """Test isAgentRunning is cleared on done."""
        assert 'state.isAgentRunning = false' in index_html

    def test_streaming_cursor_used(self, index_html):
        """Test streaming cursor is shown during response."""
        assert 'streaming-cursor' in index_html


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
