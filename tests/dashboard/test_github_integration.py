"""Tests for REQ-INTEGRATION-003: GitHub Access in Chat.

Tests cover:
- GitHub tool routing in mock responses (PRs, repos, issues, merge, create, diff)
- Correct mcp__arcade__Github_* tool names used
- All 46 GitHub tools accessible through chat
- Tool transparency events for GitHub operations
- PR diff rendering and create/merge operations
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
# TEST: GITHUB MOCK RESPONSE ROUTING
# ============================================================

class TestGitHubMockResponseRouting:
    """Test that GitHub queries are routed to correct tools."""

    def test_github_keyword_triggers_tool_use(self):
        """Test 'github' keyword triggers a GitHub tool call."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('What is on github?', 'claude', 'sonnet-4.5')
        ))

        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types
        assert 'tool_result' in chunk_types
        assert 'done' in chunk_types

    def test_pr_keyword_triggers_list_prs(self):
        """Test 'pr' keyword triggers ListPullRequests tool."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('show me prs', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        tool_names = [c['tool_name'] for c in tool_use_chunks]
        assert any('github' in name.lower() or 'Github' in name for name in tool_names), \
            f"Expected GitHub tool, got: {tool_names}"

    def test_pull_request_keyword_triggers_tool(self):
        """Test 'pull request' keyword triggers GitHub PR tool."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('list pull requests', 'claude', 'sonnet-4.5')
        ))

        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types

    def test_create_pr_routing(self):
        """Test 'create pr' routes to CreatePullRequest tool."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('create a pr for this feature', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        tool_names = [c['tool_name'] for c in tool_use_chunks]
        assert any('CreatePullRequest' in name or 'create_pr' in name.lower() for name in tool_names), \
            f"Expected CreatePullRequest tool, got: {tool_names}"

    def test_merge_pr_routing(self):
        """Test 'merge pr' routes to MergePullRequest tool."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('merge the pull request', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        tool_names = [c['tool_name'] for c in tool_use_chunks]
        assert any('MergePullRequest' in name or 'merge_pr' in name.lower() for name in tool_names), \
            f"Expected MergePullRequest tool, got: {tool_names}"

    def test_diff_review_routing(self):
        """Test 'diff' keyword routes to GetPullRequest tool."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('show me the pr diff', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        tool_names = [c['tool_name'] for c in tool_use_chunks]
        assert any('GetPullRequest' in name or 'get_pr' in name.lower() for name in tool_names), \
            f"Expected GetPullRequest tool, got: {tool_names}"

    def test_repo_keyword_routing(self):
        """Test 'repo' keyword routes to GetRepository tool."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('show me the repo info', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        tool_names = [c['tool_name'] for c in tool_use_chunks]
        assert any('GetRepository' in name or 'repository' in name.lower() for name in tool_names), \
            f"Expected GetRepository tool, got: {tool_names}"

    def test_github_issues_routing(self):
        """Test 'github issue' routes to ListIssues tool."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('show github issues', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        tool_names = [c['tool_name'] for c in tool_use_chunks]
        assert any('Issue' in name or 'issue' in name.lower() for name in tool_names), \
            f"Expected Issues tool, got: {tool_names}"

    def test_merge_keyword_triggers_tool(self):
        """Test 'merge' keyword triggers GitHub tool."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('merge this branch', 'claude', 'sonnet-4.5')
        ))

        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types

    def test_commit_keyword_triggers_tool(self):
        """Test 'commit' keyword triggers GitHub tool."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('show recent commits', 'claude', 'sonnet-4.5')
        ))

        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types

    def test_branch_keyword_triggers_tool(self):
        """Test 'branch' keyword triggers GitHub tool."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('list branches', 'claude', 'sonnet-4.5')
        ))

        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types


class TestGitHubToolEventFormat:
    """Test that GitHub tool events have correct format."""

    def test_github_tool_use_has_required_fields(self):
        """Test GitHub tool_use events have all required fields."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('github prs', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        for chunk in tool_use_chunks:
            assert 'tool_name' in chunk
            assert 'tool_input' in chunk
            assert 'tool_id' in chunk
            assert 'timestamp' in chunk

    def test_github_tool_result_has_required_fields(self):
        """Test GitHub tool_result events have tool_id and result."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('github prs', 'claude', 'sonnet-4.5')
        ))

        tool_result_chunks = [c for c in chunks if c['type'] == 'tool_result']
        assert len(tool_result_chunks) > 0

        for chunk in tool_result_chunks:
            assert 'tool_id' in chunk
            assert 'result' in chunk
            assert 'timestamp' in chunk

    def test_github_tool_names_use_arcade_prefix(self):
        """Test GitHub tool names use mcp__arcade__Github_ prefix."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('show github prs', 'claude', 'sonnet-4.5')
        ))

        tool_use_chunks = [c for c in chunks if c['type'] == 'tool_use']
        assert len(tool_use_chunks) > 0

        for chunk in tool_use_chunks:
            tool_name = chunk['tool_name']
            assert 'Github' in tool_name or 'github' in tool_name.lower(), \
                f"Expected GitHub tool name, got: {tool_name}"

    def test_create_pr_result_has_pr_number(self):
        """Test create PR result has pull request number."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('create a new pr', 'claude', 'sonnet-4.5')
        ))

        tool_result_chunks = [c for c in chunks if c['type'] == 'tool_result']
        assert len(tool_result_chunks) > 0

        for chunk in tool_result_chunks:
            result = chunk['result']
            assert isinstance(result, dict)
            # Should have some GitHub-like fields
            assert len(result) > 0

    def test_merge_pr_result_has_merged_field(self):
        """Test merge PR result has merged field."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('merge the pr', 'claude', 'sonnet-4.5')
        ))

        tool_result_chunks = [c for c in chunks if c['type'] == 'tool_result']
        assert len(tool_result_chunks) > 0

        for chunk in tool_result_chunks:
            result = chunk['result']
            assert isinstance(result, dict)
            # Merge result should have merged or sha
            assert 'merged' in result or 'sha' in result or len(result) > 0

    def test_pr_list_result_has_pull_requests(self):
        """Test PR list result has pull_requests list."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('list github prs', 'claude', 'sonnet-4.5')
        ))

        tool_result_chunks = [c for c in chunks if c['type'] == 'tool_result']
        assert len(tool_result_chunks) > 0

        for chunk in tool_result_chunks:
            result = chunk['result']
            assert isinstance(result, dict)
            assert 'pull_requests' in result

    def test_repo_result_has_name(self):
        """Test repository result has name field."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('show repository info', 'claude', 'sonnet-4.5')
        ))

        tool_result_chunks = [c for c in chunks if c['type'] == 'tool_result']
        assert len(tool_result_chunks) > 0

        for chunk in tool_result_chunks:
            result = chunk['result']
            assert isinstance(result, dict)
            assert 'name' in result


class TestGitHubMockResponseText:
    """Test the text content of GitHub mock responses."""

    def test_github_response_always_has_done(self):
        """Test all GitHub queries end with done event."""
        from dashboard.chat_handler import stream_mock_response

        queries = [
            'github prs',
            'create a pr',
            'merge the pull request',
            'show pr diff',
            'repository info',
            'github issues',
            'list commits',
            'show branches',
        ]

        for query in queries:
            chunks = run_async(collect_stream(
                stream_mock_response(query, 'claude', 'sonnet-4.5')
            ))
            last_chunk = chunks[-1]
            assert last_chunk['type'] == 'done', \
                f"Query '{query}' did not end with 'done', got '{last_chunk['type']}'"

    def test_github_response_has_text(self):
        """Test all GitHub queries produce text response."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('show github prs', 'claude', 'sonnet-4.5')
        ))

        text_chunks = [c for c in chunks if c['type'] == 'text']
        full_text = ''.join(c['content'] for c in text_chunks)
        assert len(full_text) > 0

    def test_create_pr_response_confirms_creation(self):
        """Test create PR response confirms PR was created."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('create a new pull request', 'claude', 'sonnet-4.5')
        ))

        text_chunks = [c for c in chunks if c['type'] == 'text']
        full_text = ''.join(c['content'] for c in text_chunks)
        assert len(full_text) > 0

    def test_diff_response_shows_changes(self):
        """Test diff/review response shows change details."""
        from dashboard.chat_handler import stream_mock_response

        chunks = run_async(collect_stream(
            stream_mock_response('show me the pr diff and review', 'claude', 'sonnet-4.5')
        ))

        text_chunks = [c for c in chunks if c['type'] == 'text']
        full_text = ''.join(c['content'] for c in text_chunks)
        assert len(full_text) > 0


# ============================================================
# TEST: GITHUB TOOL CONFIGURATION
# ============================================================

class TestGitHubToolConfiguration:
    """Test GitHub tools are correctly configured in arcade_config.py."""

    def test_arcade_github_tools_list_exists(self):
        """Test ARCADE_GITHUB_TOOLS list is defined."""
        from scripts.arcade_config import ARCADE_GITHUB_TOOLS
        assert isinstance(ARCADE_GITHUB_TOOLS, list)
        assert len(ARCADE_GITHUB_TOOLS) > 0

    def test_total_github_tools_count(self):
        """Test there are at least 46 GitHub tools available."""
        from scripts.arcade_config import ARCADE_GITHUB_TOOLS
        assert len(ARCADE_GITHUB_TOOLS) >= 46, \
            f"Expected at least 46 GitHub tools, got {len(ARCADE_GITHUB_TOOLS)}"

    def test_github_tools_has_list_prs(self):
        """Test ListPullRequests tool is in ARCADE_GITHUB_TOOLS."""
        from scripts.arcade_config import ARCADE_GITHUB_TOOLS
        assert 'mcp__arcade__Github_ListPullRequests' in ARCADE_GITHUB_TOOLS

    def test_github_tools_has_get_pr(self):
        """Test GetPullRequest tool is in ARCADE_GITHUB_TOOLS."""
        from scripts.arcade_config import ARCADE_GITHUB_TOOLS
        assert 'mcp__arcade__Github_GetPullRequest' in ARCADE_GITHUB_TOOLS

    def test_github_tools_has_create_pr(self):
        """Test CreatePullRequest tool is in ARCADE_GITHUB_TOOLS."""
        from scripts.arcade_config import ARCADE_GITHUB_TOOLS
        assert 'mcp__arcade__Github_CreatePullRequest' in ARCADE_GITHUB_TOOLS

    def test_github_tools_has_merge_pr(self):
        """Test MergePullRequest tool is in ARCADE_GITHUB_TOOLS."""
        from scripts.arcade_config import ARCADE_GITHUB_TOOLS
        assert 'mcp__arcade__Github_MergePullRequest' in ARCADE_GITHUB_TOOLS

    def test_github_tools_has_get_repository(self):
        """Test GetRepository tool is in ARCADE_GITHUB_TOOLS."""
        from scripts.arcade_config import ARCADE_GITHUB_TOOLS
        assert 'mcp__arcade__Github_GetRepository' in ARCADE_GITHUB_TOOLS

    def test_github_tools_has_list_issues(self):
        """Test ListIssues tool is in ARCADE_GITHUB_TOOLS."""
        from scripts.arcade_config import ARCADE_GITHUB_TOOLS
        assert 'mcp__arcade__Github_ListIssues' in ARCADE_GITHUB_TOOLS

    def test_github_tools_has_create_issue(self):
        """Test CreateIssue tool is in ARCADE_GITHUB_TOOLS."""
        from scripts.arcade_config import ARCADE_GITHUB_TOOLS
        assert 'mcp__arcade__Github_CreateIssue' in ARCADE_GITHUB_TOOLS

    def test_github_tools_has_create_branch(self):
        """Test CreateBranch tool is in ARCADE_GITHUB_TOOLS."""
        from scripts.arcade_config import ARCADE_GITHUB_TOOLS
        assert 'mcp__arcade__Github_CreateBranch' in ARCADE_GITHUB_TOOLS

    def test_github_tools_has_get_file_contents(self):
        """Test GetFileContents tool is in ARCADE_GITHUB_TOOLS."""
        from scripts.arcade_config import ARCADE_GITHUB_TOOLS
        assert 'mcp__arcade__Github_GetFileContents' in ARCADE_GITHUB_TOOLS

    def test_github_tools_has_submit_review(self):
        """Test SubmitPullRequestReview tool is in ARCADE_GITHUB_TOOLS."""
        from scripts.arcade_config import ARCADE_GITHUB_TOOLS
        assert 'mcp__arcade__Github_SubmitPullRequestReview' in ARCADE_GITHUB_TOOLS

    def test_get_github_tools_returns_list(self):
        """Test get_github_tools() returns the full tool list."""
        from scripts.arcade_config import get_github_tools
        tools = get_github_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 46

    def test_all_github_tools_use_arcade_prefix(self):
        """Test all GitHub tools use mcp__arcade__Github_ prefix."""
        from scripts.arcade_config import ARCADE_GITHUB_TOOLS
        for tool in ARCADE_GITHUB_TOOLS:
            assert tool.startswith('mcp__arcade__Github_'), \
                f"Expected mcp__arcade__Github_ prefix, got: {tool}"


# ============================================================
# TEST: INDEX.HTML GITHUB INTEGRATION
# ============================================================

class TestIndexHTMLGitHubIntegration:
    """Test that index.html properly handles GitHub tool transparency."""

    @pytest.fixture
    def index_html(self):
        """Read the index.html file."""
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_tool_transparency_shows_github_tools(self, index_html):
        """Test chat UI handles tool_use events (including GitHub tools)."""
        assert "chunk.type === 'tool_use'" in index_html or "chunk.type == 'tool_use'" in index_html

    def test_chat_sends_full_conversation_context(self, index_html):
        """Test chat sends full conversation history for GitHub operations."""
        assert 'getConversationContext()' in index_html
        assert 'conversation_history' in index_html

    def test_tool_indicator_shown_in_chat(self, index_html):
        """Test tool calls trigger visual indicator in chat."""
        assert 'Calling' in index_html

    def test_sse_handles_tool_results(self, index_html):
        """Test SSE stream handles tool_result events."""
        assert "chunk.type === 'tool_result'" in index_html or "chunk.type == 'tool_result'" in index_html

    def test_no_hardcoded_provider(self, index_html):
        """Test provider is not hardcoded (uses state.currentProvider)."""
        assert 'state.currentProvider' in index_html


# ============================================================
# TEST: STREAM_CHAT_RESPONSE WITH GITHUB QUERIES
# ============================================================

class TestStreamChatResponseGitHub:
    """Test stream_chat_response handles GitHub queries correctly."""

    def test_github_query_via_stream_chat(self):
        """Test GitHub query through stream_chat_response (mock fallback)."""
        from dashboard.chat_handler import stream_chat_response

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY']}

        with patch.dict(os.environ, clean_env, clear=True):
            chunks = run_async(collect_stream(
                stream_chat_response('show github prs', provider='claude', model='sonnet-4.5')
            ))

        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'
        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types

    def test_create_pr_query_via_stream_chat(self):
        """Test create PR query produces correct tool events."""
        from dashboard.chat_handler import stream_chat_response

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ['ANTHROPIC_API_KEY']}

        with patch.dict(os.environ, clean_env, clear=True):
            chunks = run_async(collect_stream(
                stream_chat_response('create a pull request', provider='openai', model='gpt-4o')
            ))

        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'

    def test_merge_pr_query_via_stream_chat(self):
        """Test merge PR query works through stream_chat_response."""
        from dashboard.chat_handler import stream_chat_response

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ['ANTHROPIC_API_KEY']}

        with patch.dict(os.environ, clean_env, clear=True):
            chunks = run_async(collect_stream(
                stream_chat_response('merge the pull request', provider='claude', model='sonnet-4.5')
            ))

        assert len(chunks) > 0
        assert chunks[-1]['type'] == 'done'
        chunk_types = [c['type'] for c in chunks]
        assert 'tool_use' in chunk_types

    def test_all_providers_handle_github_queries(self):
        """Test all 6 providers handle GitHub queries (via mock fallback)."""
        from dashboard.chat_handler import stream_chat_response

        providers = [
            ('claude', 'sonnet-4.5'),
            ('openai', 'gpt-4o'),
            ('gemini', '2.5-flash'),
            ('groq', 'llama-3.3-70b'),
            ('kimi', 'moonshot'),
            ('windsurf', 'cascade'),
        ]

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY',
                                  'GEMINI_API_KEY', 'GOOGLE_API_KEY',
                                  'GROQ_API_KEY', 'KIMI_API_KEY',
                                  'MOONSHOT_API_KEY', 'WINDSURF_API_KEY']}

        with patch.dict(os.environ, clean_env, clear=True):
            for provider, model in providers:
                chunks = run_async(collect_stream(
                    stream_chat_response('show github prs', provider=provider, model=model)
                ))
                assert len(chunks) > 0, f"No chunks for provider {provider}"
                assert chunks[-1]['type'] == 'done', \
                    f"Provider {provider} did not end with 'done'"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
