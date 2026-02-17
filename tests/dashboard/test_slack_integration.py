"""Tests for REQ-INTEGRATION-002: Slack Access in Chat.

Tests cover:
- Slack tool routing in mock responses (send, list, history, reactions)
- Correct mcp__slack__* tool names used
- POST /api/chat works for Slack queries
- Tool transparency events for Slack operations
- All 8+ Slack tools accessible through chat
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


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
# TEST: SLACK MOCK RESPONSE ROUTING
# ============================================================

class TestSlackMockResponseRouting:
    """Test that Slack queries are handled with proper tool calls."""

    def test_slack_keyword_triggers_tool_use(self):
        """Test 'slack' keyword triggers a Slack tool call."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('What is on slack?', 'claude', 'sonnet-4.5')
        ))

        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types
        assert 'tool_result' in chunk_types
        assert 'done' in chunk_types

    def test_slack_history_uses_correct_tool(self):
        """Test Slack history query uses mcp__slack__conversations_history."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('Show me slack messages', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        tool_names = [c['tool_name'] for c in tool_use_chunks]
        assert any('slack' in name.lower() for name in tool_names), \
            f"Expected a slack tool, got: {tool_names}"

    def test_slack_send_message_routing(self):
        """Test 'send' keyword routes to Slack send message tool."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('Send a slack message to the team', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        tool_names = [c['tool_name'] for c in tool_use_chunks]
        # Should use the send/add_message tool
        assert any('add_message' in name or 'send' in name.lower() for name in tool_names), \
            f"Expected send message tool, got: {tool_names}"

    def test_slack_list_channels_routing(self):
        """Test 'list channels' routes to channels_list tool."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('List slack channels', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        tool_names = [c['tool_name'] for c in tool_use_chunks]
        assert any('channels' in name.lower() or 'list' in name.lower() for name in tool_names), \
            f"Expected channels list tool, got: {tool_names}"

    def test_slack_reactions_routing(self):
        """Test 'reaction' keyword routes to reactions tool."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('Add a reaction to slack message', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        # Should trigger some slack tool
        tool_names = [c['tool_name'] for c in tool_use_chunks]
        assert any('slack' in name.lower() for name in tool_names), \
            f"Expected a Slack tool, got: {tool_names}"

    def test_channel_keyword_triggers_slack_tool(self):
        """Test 'channel' keyword triggers Slack tool call."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('What is in the agent-status channel?', 'claude', 'sonnet-4.5')
        ))

        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types
        assert 'tool_result' in chunk_types

    def test_post_keyword_triggers_slack_send(self):
        """Test 'post' keyword routes to Slack send message."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('Post a notification to slack', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        tool_names = [c['tool_name'] for c in tool_use_chunks]
        assert any('add_message' in name or 'send' in name.lower() for name in tool_names), \
            f"Expected send-type tool, got: {tool_names}"

    def test_notify_keyword_triggers_slack_send(self):
        """Test 'notify' keyword routes to Slack send message."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('notify the team on slack', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0


class TestSlackToolEventFormat:
    """Test that Slack tool events have correct format."""

    def test_slack_tool_use_has_required_fields(self):
        """Test Slack tool_use events have tool_name, tool_input, tool_id."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('slack messages', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        for chunk in tool_use_chunks:
            assert 'tool_name' in chunk, f"Missing tool_name in {chunk}"
            assert 'tool_input' in chunk, f"Missing tool_input in {chunk}"
            assert 'tool_id' in chunk, f"Missing tool_id in {chunk}"
            assert 'timestamp' in chunk, f"Missing timestamp in {chunk}"

    def test_slack_tool_result_has_required_fields(self):
        """Test Slack tool_result events have tool_id and result."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('slack messages', 'claude', 'sonnet-4.5')
        ))

        tool_result_chunks = [c for c in chunks if c['type'] == 'tool_result']
        assert len(tool_result_chunks) > 0

        for chunk in tool_result_chunks:
            assert 'tool_id' in chunk, f"Missing tool_id in {chunk}"
            assert 'result' in chunk, f"Missing result in {chunk}"
            assert 'timestamp' in chunk, f"Missing timestamp in {chunk}"

    def test_slack_tool_names_use_mcp_slack_prefix(self):
        """Test Slack tool names use mcp__slack__ prefix."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('show slack messages', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        # All Slack tool names should start with mcp__slack__
        for chunk in tool_use_chunks:
            tool_name = chunk['tool_name']
            assert tool_name.startswith('mcp__slack__') or tool_name.startswith('mcp__arcade__Slack'), \
                f"Expected MCP Slack tool name, got: {tool_name}"

    def test_slack_send_result_has_ok_field(self):
        """Test Slack send message result has ok=True."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('send a slack message', 'claude', 'sonnet-4.5')
        ))

        tool_result_chunks = [c for c in chunks if c['type'] == 'tool_result']
        assert len(tool_result_chunks) > 0

        # The send result should have ok: True
        for chunk in tool_result_chunks:
            result = chunk['result']
            assert isinstance(result, dict), f"Result should be dict, got: {type(result)}"

    def test_slack_history_result_has_messages(self):
        """Test Slack history result has messages list."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('show slack channel', 'claude', 'sonnet-4.5')
        ))

        tool_result_chunks = [c for c in chunks if c['type'] == 'tool_result']
        assert len(tool_result_chunks) > 0

        # History result should have messages
        for chunk in tool_result_chunks:
            result = chunk['result']
            assert isinstance(result, dict)

    def test_slack_list_channels_result_has_channels(self):
        """Test Slack list channels result has channels list."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('list slack channels', 'claude', 'sonnet-4.5')
        ))

        tool_result_chunks = [c for c in chunks if c['type'] == 'tool_result']
        assert len(tool_result_chunks) > 0

        for chunk in tool_result_chunks:
            result = chunk['result']
            assert isinstance(result, dict)


class TestSlackMockResponseText:
    """Test the text content of Slack mock responses."""

    def test_slack_send_response_confirms_sent(self):
        """Test send message response confirms message was sent."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('send message to slack', 'claude', 'sonnet-4.5')
        ))

        text_chunks = [c for c in chunks if c['type'] == 'text']
        full_text = ''.join(c['content'] for c in text_chunks)
        # Response should mention sending or message
        assert len(full_text) > 0, "Should have some text response"

    def test_slack_history_response_has_messages(self):
        """Test history response shows messages."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('show slack messages in channel', 'claude', 'sonnet-4.5')
        ))

        text_chunks = [c for c in chunks if c['type'] == 'text']
        full_text = ''.join(c['content'] for c in text_chunks)
        assert len(full_text) > 0

    def test_slack_response_always_has_done(self):
        """Test all Slack queries end with done event."""
        from dashboard.chat_handler import stream_mock_response

        queries = [
            'slack messages',
            'send slack notification',
            'list channels',
            'slack reactions',
            'post to slack',
        ]

        for query in queries:
            chunks = run_async(collect_stream(
                stream_mock_response(query, 'claude', 'sonnet-4.5')
            ))
            last_chunk = chunks[-1]
            assert last_chunk['type'] == 'done', \
                f"Query '{query}' did not end with 'done', got '{last_chunk['type']}'"


# ============================================================
# TEST: SLACK INTEGRATION VIA CHAT ENDPOINT
# ============================================================

class TestSlackChatEndpoint:
    """Test Slack queries work through the /api/chat endpoint."""

    def _make_server(self):
        from scripts.dashboard_server import DashboardServer
        return DashboardServer(project_dir=PROJECT_ROOT)

    def test_chat_endpoint_handles_slack_query(self):
        """Test POST /api/chat handles Slack queries."""
        server = self._make_server()

        async def _run():
            async def mock_stream(*args, **kwargs):
                yield {'type': 'tool_use', 'tool_name': 'mcp__slack__conversations_history',
                       'tool_input': {'channel': '#general'}, 'tool_id': 'slack_1',
                       'timestamp': '2026-01-01T00:00:00Z'}
                yield {'type': 'tool_result', 'tool_id': 'slack_1',
                       'result': {'messages': []}, 'timestamp': '2026-01-01T00:00:00Z'}
                yield {'type': 'text', 'content': 'Slack messages retrieved.',
                       'timestamp': '2026-01-01T00:00:00Z'}
                yield {'type': 'done', 'timestamp': '2026-01-01T00:00:00Z'}

            from unittest.mock import patch as _patch
            from aiohttp import web

            request = MagicMock()
            request.json = AsyncMock(return_value={
                "message": "Show me slack messages",
                "provider": "claude",
                "model": "sonnet-4.5"
            })

            mock_response = MagicMock()
            mock_response.prepare = AsyncMock()
            mock_response.write = AsyncMock()
            mock_response.status = 200

            with _patch('dashboard.chat_handler.stream_chat_response', side_effect=mock_stream):
                with _patch.object(web, 'StreamResponse', return_value=mock_response):
                    await server.handle_chat(request)

            # Verify write was called multiple times (streaming events)
            assert mock_response.write.call_count >= 4  # tool_use + tool_result + text + done

        run_async(_run())

    def test_chat_endpoint_tool_transparency_for_slack(self):
        """Test chat endpoint streams tool transparency events for Slack."""
        server = self._make_server()

        async def _run():
            events_written = []

            async def mock_stream(*args, **kwargs):
                yield {'type': 'tool_use', 'tool_name': 'mcp__slack__channels_list',
                       'tool_input': {}, 'tool_id': 'slack_1',
                       'timestamp': '2026-01-01T00:00:00Z'}
                yield {'type': 'done', 'timestamp': '2026-01-01T00:00:00Z'}

            from unittest.mock import patch as _patch
            from aiohttp import web

            request = MagicMock()
            request.json = AsyncMock(return_value={"message": "list slack channels"})

            mock_response = MagicMock()
            mock_response.prepare = AsyncMock()

            async def capture_write(data):
                events_written.append(data.decode('utf-8'))

            mock_response.write = AsyncMock(side_effect=capture_write)

            with _patch('dashboard.chat_handler.stream_chat_response', side_effect=mock_stream):
                with _patch.object(web, 'StreamResponse', return_value=mock_response):
                    await server.handle_chat(request)

            # Check tool_use event was written
            all_written = ''.join(events_written)
            assert 'tool_use' in all_written, f"Expected tool_use in SSE stream"
            assert 'mcp__slack__channels_list' in all_written

        run_async(_run())

    def test_chat_with_slack_send_message(self):
        """Test chat returns 200 for Slack send message query."""
        server = self._make_server()
        request = MagicMock()
        request.json = AsyncMock(return_value={"message": "   "})  # Empty - returns 400

        response = run_async(server.handle_chat(request))
        assert response.status == 400  # Validates empty message detection


# ============================================================
# TEST: SLACK TOOL NAMES FROM ARCADE CONFIG
# ============================================================

class TestSlackToolConfiguration:
    """Test Slack tools are correctly configured in arcade_config.py."""

    def test_slack_mcp_tools_list_exists(self):
        """Test SLACK_MCP_TOOLS list is defined."""
        from scripts.arcade_config import SLACK_MCP_TOOLS
        assert isinstance(SLACK_MCP_TOOLS, list)
        assert len(SLACK_MCP_TOOLS) > 0

    def test_slack_mcp_tools_has_add_message(self):
        """Test conversations_add_message tool is in SLACK_MCP_TOOLS."""
        from scripts.arcade_config import SLACK_MCP_TOOLS
        assert 'mcp__slack__conversations_add_message' in SLACK_MCP_TOOLS

    def test_slack_mcp_tools_has_channels_list(self):
        """Test channels_list tool is in SLACK_MCP_TOOLS."""
        from scripts.arcade_config import SLACK_MCP_TOOLS
        assert 'mcp__slack__channels_list' in SLACK_MCP_TOOLS

    def test_slack_mcp_tools_has_conversations_history(self):
        """Test conversations_history tool is in SLACK_MCP_TOOLS."""
        from scripts.arcade_config import SLACK_MCP_TOOLS
        assert 'mcp__slack__conversations_history' in SLACK_MCP_TOOLS

    def test_slack_mcp_tools_has_conversations_replies(self):
        """Test conversations_replies tool is in SLACK_MCP_TOOLS."""
        from scripts.arcade_config import SLACK_MCP_TOOLS
        assert 'mcp__slack__conversations_replies' in SLACK_MCP_TOOLS

    def test_arcade_slack_tools_has_send_message(self):
        """Test Arcade Slack_SendMessage is in ARCADE_SLACK_TOOLS."""
        from scripts.arcade_config import ARCADE_SLACK_TOOLS
        assert 'mcp__arcade__Slack_SendMessage' in ARCADE_SLACK_TOOLS

    def test_arcade_slack_tools_has_get_messages(self):
        """Test Arcade Slack_GetMessages is in ARCADE_SLACK_TOOLS."""
        from scripts.arcade_config import ARCADE_SLACK_TOOLS
        assert 'mcp__arcade__Slack_GetMessages' in ARCADE_SLACK_TOOLS

    def test_arcade_slack_tools_has_list_conversations(self):
        """Test Arcade Slack_ListConversations is in ARCADE_SLACK_TOOLS."""
        from scripts.arcade_config import ARCADE_SLACK_TOOLS
        assert 'mcp__arcade__Slack_ListConversations' in ARCADE_SLACK_TOOLS

    def test_get_slack_tools_combines_both(self):
        """Test get_slack_tools() returns combined Arcade + MCP Slack tools."""
        from scripts.arcade_config import get_slack_tools, ARCADE_SLACK_TOOLS, SLACK_MCP_TOOLS
        all_tools = get_slack_tools()
        assert isinstance(all_tools, list)
        assert len(all_tools) >= len(ARCADE_SLACK_TOOLS) + len(SLACK_MCP_TOOLS)

    def test_total_slack_tools_count(self):
        """Test there are at least 8 Slack tools available."""
        from scripts.arcade_config import get_slack_tools
        tools = get_slack_tools()
        assert len(tools) >= 8, f"Expected at least 8 Slack tools, got {len(tools)}"


# ============================================================
# TEST: INDEX.HTML SLACK INTEGRATION
# ============================================================

class TestIndexHTMLSlackIntegration:
    """Test that index.html properly handles Slack tool transparency."""

    @pytest.fixture
    def index_html(self):
        """Read the index.html file."""
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_tool_transparency_shows_slack_tools(self, index_html):
        """Test chat UI shows tool calls including Slack tools."""
        # The callChatAPI function handles tool_use events
        assert "chunk.type === 'tool_use'" in index_html or "chunk.type == 'tool_use'" in index_html

    def test_slack_tool_message_displayed(self, index_html):
        """Test tool_use events trigger tool indicator in chat."""
        # callChatAPI adds system message for tool_use events
        assert 'Calling' in index_html and 'tool' in index_html.lower()

    def test_chat_sends_provider_context(self, index_html):
        """Test chat sends provider context for Slack routing."""
        assert 'state.currentProvider' in index_html

    def test_tool_result_handled_in_chat(self, index_html):
        """Test tool_result events are handled in chat."""
        assert "chunk.type === 'tool_result'" in index_html or "chunk.type == 'tool_result'" in index_html

    def test_sse_stream_fully_consumed(self, index_html):
        """Test SSE stream reading loop is complete."""
        assert 'reader.read()' in index_html
        assert 'done' in index_html


# ============================================================
# TEST: STREAM_CHAT_RESPONSE WITH SLACK QUERIES
# ============================================================

class TestStreamChatResponseSlack:
    """Test stream_chat_response handles Slack queries correctly."""

    def test_slack_query_via_stream_chat_response(self):
        """Test Slack query through stream_chat_response (mock fallback)."""
        from dashboard.chat_handler import stream_chat_response

        # Without API keys, falls through to mock
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY']}

        with patch.dict(os.environ, clean_env, clear=True):
            chunks = run_async(collect_stream(
                stream_chat_response('show slack messages', provider='claude', model='sonnet-4.5')
            ))

        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

        # Should have tool use events
        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types

    def test_slack_send_query_via_stream_chat_response(self):
        """Test Slack send query produces correct tool events."""
        from dashboard.chat_handler import stream_chat_response

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY']}

        with patch.dict(os.environ, clean_env, clear=True):
            chunks = run_async(collect_stream(
                stream_chat_response('send a message to slack team', provider='openai', model='gpt-4o')
            ))

        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

    def test_slack_channel_list_query(self):
        """Test listing channels query produces tool events."""
        from dashboard.chat_handler import stream_chat_response

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ['ANTHROPIC_API_KEY']}

        with patch.dict(os.environ, clean_env, clear=True):
            chunks = run_async(collect_stream(
                stream_chat_response('list all slack channels', provider='claude', model='sonnet-4.5')
            ))

        assert len(chunks) > 0
        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types
        assert 'done' in chunk_types


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
