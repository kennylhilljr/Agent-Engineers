"""Agent Executor - Execute agent delegations and stream results.

This module handles the execution of agent actions parsed from chat messages.
It bridges the chat interface to the underlying agent system, executing
delegations and streaming results back via WebSocket.

Supported commands:
    status [issue]   - Get Linear issue status
    start [agent] [issue] - Start an agent on an issue
    pause [agent]    - Pause a running agent
    resume [agent]   - Resume a paused agent

Error handling:
    - All errors produce user-friendly messages
    - Errors are streamed back to the chat interface
    - No unhandled exceptions propagate to the caller
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Any, AsyncIterator, Optional, Set

import aiohttp

logger = logging.getLogger(__name__)

# Track paused agents (in-memory state for this session)
_paused_agents: Set[str] = set()


class AgentExecutor:
    """Executes agent delegations from chat messages.

    This class:
    1. Receives a ParsedIntent from the intent parser
    2. Executes the appropriate action via the Linear API or agent session
    3. Yields result chunks for streaming back to the client

    Usage:
        executor = AgentExecutor()
        async for chunk in executor.execute(intent):
            # Send chunk to WebSocket or HTTP response
            await ws.send_str(chunk)
    """

    def __init__(self, linear_api_key: Optional[str] = None):
        """Initialize the executor.

        Args:
            linear_api_key: Optional Linear API key. Defaults to LINEAR_API_KEY env var.
        """
        self.linear_api_key = linear_api_key or os.environ.get("LINEAR_API_KEY", "")

    async def execute(self, intent) -> AsyncIterator[str]:
        """Execute an agent action based on parsed intent.

        Args:
            intent: ParsedIntent object from intent_parser.parse_intent()

        Yields:
            Text chunks of the result, suitable for streaming
        """
        action = intent.action
        agent = intent.agent
        params = intent.params

        try:
            if intent.intent_type == "conversation":
                # Conversation is handled by AI provider, not here
                yield "[Bridge] This message will be handled by your AI provider."
                return

            if action == "status":
                async for chunk in self._execute_status(params):
                    yield chunk

            elif action == "start":
                async for chunk in self._execute_start(agent, params):
                    yield chunk

            elif action == "pause":
                async for chunk in self._execute_pause(agent, params):
                    yield chunk

            elif action == "resume":
                async for chunk in self._execute_resume(agent, params):
                    yield chunk

            elif action == "list":
                async for chunk in self._execute_list(params):
                    yield chunk

            elif action == "query" and agent == "github":
                async for chunk in self._execute_github_query(params):
                    yield chunk

            else:
                yield f"Unknown action: '{action}'. Supported: status, start, pause, resume, query."

        except asyncio.CancelledError:
            yield "[Bridge] Request was cancelled."
        except Exception as e:
            logger.exception(f"AgentExecutor error: {e}")
            yield f"[Bridge Error] An error occurred: {str(e)}"

    async def _execute_status(self, params: dict) -> AsyncIterator[str]:
        """Get the status of a Linear issue.

        Args:
            params: Must contain 'ticket' key with the issue identifier (e.g. 'AI-109')

        Yields:
            Formatted status message
        """
        ticket = params.get("ticket", "").upper()
        if not ticket:
            yield "No ticket specified. Usage: 'status AI-109' or 'What is AI-109 status?'"
            return

        if not re.match(r'^[A-Z]+-\d+$', ticket):
            yield f"Invalid ticket format: '{ticket}'. Expected format like 'AI-109'."
            return

        yield f"Querying Linear for {ticket} status...\n"

        if not self.linear_api_key:
            # No API key - return a helpful stub response
            yield (
                f"**{ticket} Status** (Linear API not configured)\n\n"
                f"To get live ticket status, configure the LINEAR_API_KEY environment variable.\n"
                f"The intent parser correctly routed your request to the linear agent."
            )
            return

        try:
            result = await self._query_linear_issue(ticket)
            if result:
                yield self._format_issue_status(result)
            else:
                yield f"Issue {ticket} not found in Linear."
        except Exception as e:
            logger.error(f"Linear API error for {ticket}: {e}")
            yield f"Could not fetch {ticket} from Linear: {str(e)}"

    async def _execute_start(self, agent: str, params: dict) -> AsyncIterator[str]:
        """Start an agent on a specific issue.

        Args:
            agent: Agent name to start
            params: Must contain 'ticket' key

        Yields:
            Status messages for the start operation
        """
        ticket = params.get("ticket", "").upper()
        target_agent = params.get("target_agent", agent or "coding")

        if not ticket:
            yield f"No ticket specified for starting {target_agent} agent."
            return

        # Check if agent was paused - resume it
        if target_agent in _paused_agents:
            _paused_agents.discard(target_agent)
            yield f"Resumed {target_agent} agent.\n"

        yield (
            f"**Delegating to {target_agent} agent**\n\n"
            f"Starting {target_agent} agent on {ticket}...\n\n"
            f"This request has been routed through the Chat-to-Agent Bridge.\n"
            f"The {target_agent} agent will:\n"
            f"  1. Read the {ticket} issue from Linear\n"
            f"  2. Execute the required tasks\n"
            f"  3. Update {ticket} status upon completion\n\n"
            f"Note: Full agent execution requires the Claude Agent SDK session loop."
        )

    async def _execute_pause(self, agent: str, params: dict) -> AsyncIterator[str]:
        """Pause a running agent.

        Args:
            agent: Agent name to pause
            params: Additional parameters

        Yields:
            Confirmation message
        """
        target_agent = params.get("target_agent", agent or "")
        if not target_agent:
            yield "No agent specified to pause."
            return

        _paused_agents.add(target_agent)
        yield f"**{target_agent} agent paused.**\n\nUse 'resume {target_agent}' to continue."

    async def _execute_resume(self, agent: str, params: dict) -> AsyncIterator[str]:
        """Resume a paused agent.

        Args:
            agent: Agent name to resume
            params: Additional parameters

        Yields:
            Confirmation message
        """
        target_agent = params.get("target_agent", agent or "")
        if not target_agent:
            yield "No agent specified to resume."
            return

        was_paused = target_agent in _paused_agents
        _paused_agents.discard(target_agent)

        if was_paused:
            yield f"**{target_agent} agent resumed.**\n\nThe agent will continue processing."
        else:
            yield f"**{target_agent} agent** was not paused. It may already be running."

    async def _execute_list(self, params: dict) -> AsyncIterator[str]:
        """List available agents or issues.

        Yields:
            Formatted list
        """
        from agents.definitions import KNOWN_AGENTS as AGENT_NAMES

        agents_list = "\n".join(f"  - {name}" for name in sorted(AGENT_NAMES))
        yield (
            f"**Available Agents:**\n\n"
            f"{agents_list}\n\n"
            f"Use 'start [agent] [ticket]' to delegate work to an agent."
        )

    async def _query_linear_issue(self, issue_key: str) -> Optional[dict]:
        """Query the Linear GraphQL API for issue details.

        Args:
            issue_key: Linear issue identifier (e.g. 'AI-109')

        Returns:
            Issue data dict or None if not found

        Raises:
            Exception: If the API call fails
        """
        query = """
        query SearchIssue($term: String!) {
            issueSearch(term: $term, first: 1) {
                nodes {
                    id
                    identifier
                    title
                    state {
                        name
                        type
                    }
                    assignee {
                        name
                    }
                    priority
                    createdAt
                    updatedAt
                    description
                    url
                }
            }
        }
        """

        headers = {
            "Authorization": f"Bearer {self.linear_api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.linear.app/graphql",
                json={"query": query, "variables": {"term": issue_key}},
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"Linear API returned HTTP {resp.status}")

                data = await resp.json()
                errors = data.get("errors")
                if errors:
                    raise Exception(f"Linear API error: {errors[0].get('message', 'Unknown error')}")

                nodes = data.get("data", {}).get("issueSearch", {}).get("nodes", [])
                if not nodes:
                    return None

                # Verify we got the right issue
                issue = nodes[0]
                if issue.get("identifier", "").upper() == issue_key.upper():
                    return issue

                return None

    async def _execute_github_query(self, params: dict) -> AsyncIterator[str]:
        """Execute a GitHub query using the gh CLI or GitHub API.

        Args:
            params: Must contain 'query' key with the user's original message

        Yields:
            Formatted GitHub response
        """
        query = params.get("query", "")
        repo = os.environ.get("GITHUB_REPO", "")

        if not repo:
            yield (
                "**GitHub query received** but `GITHUB_REPO` is not configured.\n\n"
                "Set the `GITHUB_REPO` environment variable (e.g. `owner/repo`) "
                "to enable GitHub integration."
            )
            return

        yield f"Querying GitHub ({repo})...\n\n"

        lower_q = query.lower()

        try:
            if any(kw in lower_q for kw in ["pr", "pull request"]):
                # Determine state filter
                if "merged" in lower_q:
                    state = "merged"
                elif "closed" in lower_q:
                    state = "closed"
                else:
                    state = "open"
                result = await self._gh_list_prs(repo, state)
                yield result
            elif "branch" in lower_q:
                result = await self._gh_list_branches(repo)
                yield result
            elif "commit" in lower_q:
                result = await self._gh_list_commits(repo)
                yield result
            else:
                yield (
                    f"GitHub query routed but could not determine specific action.\n"
                    f"Supported: list PRs, list branches, list commits.\n"
                    f"Your query: {query}"
                )
        except Exception as e:
            logger.error(f"GitHub query error: {e}")
            yield f"Error querying GitHub: {str(e)}"

    async def _gh_list_prs(self, repo: str, state: str = "open") -> str:
        """List pull requests via gh CLI."""
        proc = await asyncio.create_subprocess_exec(
            "gh", "pr", "list", "--repo", repo, "--state", state, "--limit", "10",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode().strip()
            return f"GitHub CLI error: {err}"

        output = stdout.decode().strip()
        if not output:
            return f"No {state} pull requests found in {repo}."

        lines = output.split("\n")
        formatted = [f"**{state.capitalize()} Pull Requests** ({repo}):\n"]
        for line in lines:
            parts = line.split("\t")
            if len(parts) >= 2:
                formatted.append(f"- #{parts[0]} {parts[1]}")
            else:
                formatted.append(f"- {line}")
        return "\n".join(formatted)

    async def _gh_list_branches(self, repo: str) -> str:
        """List branches via gh CLI."""
        proc = await asyncio.create_subprocess_exec(
            "gh", "api", f"repos/{repo}/branches", "--jq", ".[].name",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return f"GitHub CLI error: {stderr.decode().strip()}"

        output = stdout.decode().strip()
        if not output:
            return f"No branches found in {repo}."

        branches = output.split("\n")[:20]
        formatted = [f"**Branches** ({repo}, showing {len(branches)}):\n"]
        for b in branches:
            formatted.append(f"- `{b}`")
        return "\n".join(formatted)

    async def _gh_list_commits(self, repo: str) -> str:
        """List recent commits via gh CLI."""
        proc = await asyncio.create_subprocess_exec(
            "gh", "api", f"repos/{repo}/commits",
            "--jq", ".[:10][] | .sha[:7] + \" \" + (.commit.message | split(\"\\n\")[0])",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return f"GitHub CLI error: {stderr.decode().strip()}"

        output = stdout.decode().strip()
        if not output:
            return f"No recent commits found in {repo}."

        lines = output.split("\n")
        formatted = [f"**Recent Commits** ({repo}):\n"]
        for line in lines:
            formatted.append(f"- `{line}`")
        return "\n".join(formatted)

    def _format_issue_status(self, issue: dict) -> str:
        """Format a Linear issue as a readable status message.

        Args:
            issue: Issue data from Linear API

        Returns:
            Formatted status string
        """
        identifier = issue.get("identifier", "Unknown")
        title = issue.get("title", "No title")
        state = issue.get("state", {})
        state_name = state.get("name", "Unknown")
        state_type = state.get("type", "")
        assignee = issue.get("assignee")
        assignee_name = assignee.get("name") if assignee else "Unassigned"

        priority_map = {0: "No priority", 1: "Urgent", 2: "High", 3: "Medium", 4: "Low"}
        priority = priority_map.get(issue.get("priority", 0), "Unknown")

        url = issue.get("url", "")
        updated_at = issue.get("updatedAt", "")

        # Format timestamp
        time_str = ""
        if updated_at:
            try:
                dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                time_str = dt.strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                time_str = updated_at

        lines = [
            f"**{identifier}: {title}**\n",
            f"Status: {state_name} ({state_type})",
            f"Priority: {priority}",
            f"Assignee: {assignee_name}",
        ]

        if time_str:
            lines.append(f"Last updated: {time_str}")

        if url:
            lines.append(f"URL: {url}")

        return "\n".join(lines)


async def execute_intent(intent, linear_api_key: Optional[str] = None) -> str:
    """Convenience function to execute an intent and collect all output.

    Args:
        intent: ParsedIntent from intent_parser.parse_intent()
        linear_api_key: Optional Linear API key override

    Returns:
        Complete response string
    """
    executor = AgentExecutor(linear_api_key=linear_api_key)
    chunks = []
    async for chunk in executor.execute(intent):
        chunks.append(chunk)
    return "".join(chunks)


async def stream_intent_execution(
    intent,
    websockets: Optional[Set[Any]] = None,
    message_id: Optional[str] = None,
    linear_api_key: Optional[str] = None,
) -> str:
    """Execute an intent and optionally broadcast chunks to WebSocket clients.

    Args:
        intent: ParsedIntent from intent_parser.parse_intent()
        websockets: Optional set of WebSocket connections to broadcast to
        message_id: Optional message ID for tracking in WebSocket messages
        linear_api_key: Optional Linear API key override

    Returns:
        Complete response string (all chunks concatenated)
    """
    import json

    executor = AgentExecutor(linear_api_key=linear_api_key)
    chunks = []

    async for chunk in executor.execute(intent):
        chunks.append(chunk)

        if websockets:
            message = {
                "type": "chat_stream",
                "message_id": message_id,
                "chunk": chunk,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            disconnected = set()
            for ws in websockets:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.warning(f"WebSocket send error: {e}")
                    disconnected.add(ws)
            websockets -= disconnected

    # Signal completion
    if websockets:
        completion_message = {
            "type": "chat_stream_complete",
            "message_id": message_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        for ws in list(websockets):
            try:
                await ws.send_json(completion_message)
            except Exception:
                pass

    return "".join(chunks)
