"""
Tests for AI-142: REQ-INTEGRATION-004: Tool Transparency & Call Visualization

Verifies that the chat interface shows collapsible tool call blocks with:
- Tool name display (short name with mcp__ prefix stripped)
- Collapsible parameter details for tool_use events
- Collapsible response details for tool_result events
- Success/failure icons
- CSS classes for styling
- chat_handler.py tool_result events include content field
"""
import pytest
import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Test Group 1: CSS Classes in index.html
# ============================================================

class TestToolCallCSS:
    """Verify CSS classes for tool call visualization are defined in index.html."""

    @pytest.fixture(scope='class')
    def html_content(self):
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_tool_call_block_css_defined(self, html_content):
        """CSS class .tool-call-block must be defined."""
        assert '.tool-call-block' in html_content

    def test_tool_use_block_css_defined(self, html_content):
        """CSS class .tool-use-block must be defined for tool call styling."""
        assert '.tool-use-block' in html_content

    def test_tool_result_block_css_defined(self, html_content):
        """CSS class .tool-result-block must be defined for tool result styling."""
        assert '.tool-result-block' in html_content

    def test_tool_call_block_inner_css_defined(self, html_content):
        """CSS class .tool-call-block-inner must be defined."""
        assert '.tool-call-block-inner' in html_content

    def test_tool_call_header_css_defined(self, html_content):
        """CSS class .tool-call-header must be defined for the clickable summary."""
        assert '.tool-call-header' in html_content

    def test_tool_call_body_css_defined(self, html_content):
        """CSS class .tool-call-body must be defined."""
        assert '.tool-call-body' in html_content

    def test_tool_full_name_css_defined(self, html_content):
        """CSS class .tool-full-name must be defined."""
        assert '.tool-full-name' in html_content

    def test_tool_call_details_css_defined(self, html_content):
        """CSS class .tool-call-details must be defined for collapsible details."""
        assert '.tool-call-details' in html_content

    def test_tool_params_css_defined(self, html_content):
        """CSS class .tool-params must be defined for parameter display."""
        assert '.tool-params' in html_content

    def test_tool_icon_css_defined(self, html_content):
        """CSS class .tool-icon must be defined."""
        assert '.tool-icon' in html_content

    def test_tool_label_css_defined(self, html_content):
        """CSS class .tool-label must be defined."""
        assert '.tool-label' in html_content

    def test_tool_name_css_defined(self, html_content):
        """CSS class .tool-name must be defined."""
        assert '.tool-name' in html_content

    def test_tool_use_block_has_background(self, html_content):
        """Tool use block must have a background color."""
        # Check for indigo-ish background for tool use
        assert 'tool-use-block' in html_content
        # The CSS block must come before </style>
        style_end = html_content.index('</style>')
        css_section = html_content[:style_end]
        assert '.tool-use-block' in css_section

    def test_tool_result_block_has_background(self, html_content):
        """Tool result block must have a background color."""
        style_end = html_content.index('</style>')
        css_section = html_content[:style_end]
        assert '.tool-result-block' in css_section

    def test_tool_params_has_max_height(self, html_content):
        """Tool params must have max-height to prevent overflow."""
        assert 'max-height' in html_content


# ============================================================
# Test Group 2: addToolMessage() JavaScript function
# ============================================================

class TestAddToolMessageFunction:
    """Verify addToolMessage() function implementation in index.html."""

    @pytest.fixture(scope='class')
    def html_content(self):
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_add_tool_message_function_defined(self, html_content):
        """addToolMessage function must be defined."""
        assert 'function addToolMessage' in html_content

    def test_add_tool_message_accepts_four_params(self, html_content):
        """addToolMessage must accept 4 parameters: toolName, toolInput, isResult, toolResult."""
        assert 'function addToolMessage(toolName, toolInput, isResult, toolResult)' in html_content

    def test_add_tool_message_uses_details_element(self, html_content):
        """addToolMessage must use <details> HTML element for collapsible content."""
        # Find the addToolMessage function body
        func_start = html_content.index('function addToolMessage(toolName, toolInput, isResult, toolResult)')
        func_section = html_content[func_start:func_start + 2000]
        assert '<details' in func_section

    def test_add_tool_message_uses_summary_element(self, html_content):
        """addToolMessage must use <summary> HTML element."""
        func_start = html_content.index('function addToolMessage(toolName, toolInput, isResult, toolResult)')
        func_section = html_content[func_start:func_start + 2000]
        assert '<summary' in func_section

    def test_add_tool_message_has_tool_use_block_class(self, html_content):
        """addToolMessage must assign tool-use-block class for tool calls."""
        func_start = html_content.index('function addToolMessage(toolName, toolInput, isResult, toolResult)')
        func_section = html_content[func_start:func_start + 2000]
        assert 'tool-use-block' in func_section

    def test_add_tool_message_has_tool_result_block_class(self, html_content):
        """addToolMessage must assign tool-result-block class for results."""
        func_start = html_content.index('function addToolMessage(toolName, toolInput, isResult, toolResult)')
        func_section = html_content[func_start:func_start + 2000]
        assert 'tool-result-block' in func_section

    def test_add_tool_message_strips_mcp_prefix(self, html_content):
        """addToolMessage must strip mcp__ prefix from tool names."""
        func_start = html_content.index('function addToolMessage(toolName, toolInput, isResult, toolResult)')
        func_section = html_content[func_start:func_start + 2000]
        assert 'mcp__' in func_section  # The replace logic must reference mcp__

    def test_add_tool_message_uses_wrench_icon(self, html_content):
        """addToolMessage must show 🔧 icon for tool calls."""
        func_start = html_content.index('function addToolMessage(toolName, toolInput, isResult, toolResult)')
        func_section = html_content[func_start:func_start + 2000]
        assert '🔧' in func_section

    def test_add_tool_message_uses_check_icon(self, html_content):
        """addToolMessage must show ✅ icon for tool results."""
        func_start = html_content.index('function addToolMessage(toolName, toolInput, isResult, toolResult)')
        func_section = html_content[func_start:func_start + 2000]
        assert '✅' in func_section

    def test_add_tool_message_appends_to_chat_messages(self, html_content):
        """addToolMessage must append to the chat-messages container."""
        func_start = html_content.index('function addToolMessage(toolName, toolInput, isResult, toolResult)')
        func_section = html_content[func_start:func_start + 3000]
        assert 'chat-messages' in func_section
        assert 'appendChild' in func_section

    def test_add_tool_message_shows_parameters_label(self, html_content):
        """addToolMessage must show 'Parameters' label in details."""
        func_start = html_content.index('function addToolMessage(toolName, toolInput, isResult, toolResult)')
        func_section = html_content[func_start:func_start + 2000]
        assert 'Parameters' in func_section

    def test_add_tool_message_shows_response_label(self, html_content):
        """addToolMessage must show 'Response' label in details."""
        func_start = html_content.index('function addToolMessage(toolName, toolInput, isResult, toolResult)')
        func_section = html_content[func_start:func_start + 2000]
        assert 'Response' in func_section

    def test_add_tool_message_uses_escape_html(self, html_content):
        """addToolMessage must call escapeHtml() to prevent XSS."""
        func_start = html_content.index('function addToolMessage(toolName, toolInput, isResult, toolResult)')
        func_section = html_content[func_start:func_start + 2000]
        assert 'escapeHtml' in func_section

    def test_add_tool_message_uses_json_stringify(self, html_content):
        """addToolMessage must use JSON.stringify() to format parameters."""
        func_start = html_content.index('function addToolMessage(toolName, toolInput, isResult, toolResult)')
        func_section = html_content[func_start:func_start + 2000]
        assert 'JSON.stringify' in func_section

    def test_add_tool_message_scrolls_chat(self, html_content):
        """addToolMessage must scroll chat to bottom."""
        func_start = html_content.index('function addToolMessage(toolName, toolInput, isResult, toolResult)')
        func_section = html_content[func_start:func_start + 3000]
        assert 'scrollTop' in func_section


# ============================================================
# Test Group 3: escapeHtml() function
# ============================================================

class TestEscapeHtmlFunction:
    """Verify escapeHtml() helper function exists and works correctly."""

    @pytest.fixture(scope='class')
    def html_content(self):
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_escape_html_function_defined(self, html_content):
        """escapeHtml function must be defined."""
        assert 'function escapeHtml' in html_content

    def test_escape_html_handles_text(self, html_content):
        """escapeHtml must use DOM-based or string-based escaping."""
        func_start = html_content.index('function escapeHtml')
        func_section = html_content[func_start:func_start + 300]
        # Either DOM-based or string-based approach
        assert ('textContent' in func_section or 'replace' in func_section)


# ============================================================
# Test Group 4: SSE Chunk Handler for tool_result
# ============================================================

class TestSSEChunkHandlerToolResult:
    """Verify SSE chunk handler correctly passes content to tool_result."""

    @pytest.fixture(scope='class')
    def html_content(self):
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_sse_handler_calls_add_tool_message_for_tool_use(self, html_content):
        """SSE handler must call addToolMessage for tool_use chunks."""
        assert "chunk.type === 'tool_use'" in html_content
        assert 'addToolMessage(chunk.tool_name' in html_content

    def test_sse_handler_passes_tool_input(self, html_content):
        """SSE handler must pass chunk.tool_input to addToolMessage."""
        assert 'chunk.tool_input' in html_content

    def test_sse_handler_calls_add_tool_message_for_tool_result(self, html_content):
        """SSE handler must call addToolMessage for tool_result chunks."""
        assert "chunk.type === 'tool_result'" in html_content

    def test_sse_handler_passes_chunk_content_for_tool_result(self, html_content):
        """SSE handler must pass chunk.content as the 4th parameter for tool_result."""
        # Find the tool_result handler
        result_idx = html_content.index("chunk.type === 'tool_result'")
        result_section = html_content[result_idx:result_idx + 200]
        assert 'chunk.content' in result_section

    def test_sse_handler_passes_false_for_tool_use_is_result(self, html_content):
        """SSE handler must pass false as isResult for tool_use."""
        use_idx = html_content.index("chunk.type === 'tool_use'")
        use_section = html_content[use_idx:use_idx + 200]
        assert 'false' in use_section

    def test_sse_handler_passes_true_for_tool_result_is_result(self, html_content):
        """SSE handler must pass true as isResult for tool_result."""
        result_idx = html_content.index("chunk.type === 'tool_result'")
        result_section = html_content[result_idx:result_idx + 200]
        assert 'true' in result_section

    def test_sse_handler_uses_tool_name_or_tool_id(self, html_content):
        """SSE handler must use chunk.tool_name || chunk.tool_id for tool_result display."""
        result_idx = html_content.index("chunk.type === 'tool_result'")
        result_section = html_content[result_idx:result_idx + 200]
        assert 'chunk.tool_name' in result_section or 'chunk.tool_id' in result_section


# ============================================================
# Test Group 5: chat_handler.py tool_result content field
# ============================================================

class TestChatHandlerToolResultContent:
    """Verify chat_handler.py tool_result events include content field."""

    @pytest.fixture(scope='class')
    def handler_content(self):
        handler_path = PROJECT_ROOT / 'dashboard' / 'chat_handler.py'
        return handler_path.read_text(encoding='utf-8')

    def _find_tool_result_section(self, handler_content, tool_id):
        """Find the tool_result dict for the given tool_id (second occurrence = result event)."""
        first = handler_content.index(f"'tool_id': '{tool_id}'")
        try:
            second = handler_content.index(f"'tool_id': '{tool_id}'", first + 1)
            return handler_content[second:second + 400]
        except ValueError:
            # Only one occurrence - return that section
            return handler_content[first:first + 400]

    def test_linear_tool_result_has_content(self, handler_content):
        """Linear tool_result event must include content field."""
        section = self._find_tool_result_section(handler_content, 'tool_mock_1')
        assert "'content'" in section

    def test_github_create_pr_result_has_content(self, handler_content):
        """GitHub CreatePR tool_result must include content field."""
        section = self._find_tool_result_section(handler_content, 'tool_github_create_pr')
        assert "'content'" in section

    def test_github_merge_pr_result_has_content(self, handler_content):
        """GitHub MergePR tool_result must include content field."""
        section = self._find_tool_result_section(handler_content, 'tool_github_merge_pr')
        assert "'content'" in section

    def test_github_get_pr_result_has_content(self, handler_content):
        """GitHub GetPR tool_result must include content field."""
        section = self._find_tool_result_section(handler_content, 'tool_github_get_pr')
        assert "'content'" in section

    def test_github_issues_result_has_content(self, handler_content):
        """GitHub ListIssues tool_result must include content field."""
        section = self._find_tool_result_section(handler_content, 'tool_github_issues')
        assert "'content'" in section

    def test_github_repo_result_has_content(self, handler_content):
        """GitHub GetRepository tool_result must include content field."""
        section = self._find_tool_result_section(handler_content, 'tool_github_repo')
        assert "'content'" in section

    def test_github_list_prs_result_has_content(self, handler_content):
        """GitHub ListPullRequests tool_result must include content field."""
        section = self._find_tool_result_section(handler_content, 'tool_github_list_prs')
        assert "'content'" in section

    def test_slack_send_result_has_content(self, handler_content):
        """Slack send tool_result must include content field."""
        section = self._find_tool_result_section(handler_content, 'tool_slack_send')
        assert "'content'" in section

    def test_slack_list_result_has_content(self, handler_content):
        """Slack list channels tool_result must include content field."""
        section = self._find_tool_result_section(handler_content, 'tool_slack_list')
        assert "'content'" in section

    def test_slack_react_result_has_content(self, handler_content):
        """Slack react tool_result must include content field."""
        section = self._find_tool_result_section(handler_content, 'tool_slack_react')
        assert "'content'" in section

    def test_slack_history_result_has_content(self, handler_content):
        """Slack history tool_result must include content field."""
        section = self._find_tool_result_section(handler_content, 'tool_slack_history')
        assert "'content'" in section

    def test_linear_tool_result_has_tool_name(self, handler_content):
        """Linear tool_result must include tool_name field for display."""
        section = self._find_tool_result_section(handler_content, 'tool_mock_1')
        assert "'tool_name'" in section


# ============================================================
# Test Group 6: Integration - stream mock includes tool_result content
# ============================================================

class TestStreamMockToolResultContent:
    """Verify stream_mock_response yields tool_result with content."""

    @pytest.fixture
    def clean_env(self):
        """Run with no API keys."""
        return {k: v for k, v in os.environ.items()
                if not k.endswith('_API_KEY') and k not in ('ANTHROPIC_API_KEY',)}

    def _collect_events(self, gen):
        """Collect all events from an async generator."""
        loop = asyncio.new_event_loop()
        events = []
        async def collect():
            async for event in gen:
                events.append(event)
        loop.run_until_complete(collect())
        loop.close()
        return events

    def test_linear_tool_result_event_has_content(self):
        """Linear mock tool_result event must have content field."""
        from dashboard.chat_handler import stream_mock_response
        events = self._collect_events(stream_mock_response('show linear issues', 'claude', 'sonnet-4.5'))
        tool_results = [e for e in events if e.get('type') == 'tool_result']
        assert len(tool_results) > 0
        assert 'content' in tool_results[0]
        assert tool_results[0]['content'] != ''

    def test_slack_tool_result_event_has_content(self):
        """Slack mock tool_result event must have content field."""
        from dashboard.chat_handler import stream_mock_response
        events = self._collect_events(stream_mock_response('send slack message', 'claude', 'sonnet-4.5'))
        tool_results = [e for e in events if e.get('type') == 'tool_result']
        assert len(tool_results) > 0
        assert 'content' in tool_results[0]

    def test_github_tool_result_event_has_content(self):
        """GitHub mock tool_result event must have content field."""
        from dashboard.chat_handler import stream_mock_response
        events = self._collect_events(stream_mock_response('show github pull requests', 'claude', 'sonnet-4.5'))
        tool_results = [e for e in events if e.get('type') == 'tool_result']
        assert len(tool_results) > 0
        assert 'content' in tool_results[0]

    def test_linear_tool_result_has_tool_name(self):
        """Linear mock tool_result event must include tool_name."""
        from dashboard.chat_handler import stream_mock_response
        events = self._collect_events(stream_mock_response('show linear issues', 'claude', 'sonnet-4.5'))
        tool_results = [e for e in events if e.get('type') == 'tool_result']
        assert len(tool_results) > 0
        assert 'tool_name' in tool_results[0]

    def test_tool_result_content_is_string(self):
        """tool_result content must be a string for display."""
        from dashboard.chat_handler import stream_mock_response
        events = self._collect_events(stream_mock_response('check linear tickets', 'claude', 'sonnet-4.5'))
        tool_results = [e for e in events if e.get('type') == 'tool_result']
        assert len(tool_results) > 0
        assert isinstance(tool_results[0]['content'], str)
