"""
Orchestrator Session Runner
===========================

Runs orchestrated sessions where the main agent delegates to specialized agents.
"""

import traceback
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    TextBlock,
    ToolUseBlock,
)

from agent import SESSION_CONTINUE, SESSION_ERROR, SessionResult
from progress import LINEAR_PROJECT_MARKER

# Import WebSocket server for real-time status updates (Phase 2)
_websocket_server = None
try:
    from dashboard.websocket_server import WebSocketServer
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False


async def broadcast_orchestrator_status(status: str, metadata: dict = None):
    """Broadcast orchestrator status change via WebSocket if available.

    Args:
        status: New status ('idle', 'running', 'paused', 'error')
        metadata: Additional context (delegated_agent, reasoning, etc.)
    """
    global _websocket_server

    if not WEBSOCKET_AVAILABLE or _websocket_server is None:
        return

    try:
        await _websocket_server.broadcast_agent_status(
            agent_name="orchestrator",
            status=status,
            metadata=metadata or {}
        )
    except Exception as e:
        print(f"Warning: Failed to broadcast orchestrator status: {e}")


async def broadcast_reasoning(content: str, context: dict = None):
    """Broadcast orchestrator reasoning via WebSocket if available.

    Args:
        content: Reasoning text/decision explanation
        context: Additional context (ticket, complexity, etc.)
    """
    global _websocket_server

    if not WEBSOCKET_AVAILABLE or _websocket_server is None:
        return

    try:
        await _websocket_server.broadcast_reasoning(
            content=content,
            source="orchestrator",
            context=context or {}
        )
    except Exception as e:
        print(f"Warning: Failed to broadcast reasoning: {e}")


async def run_orchestrated_session(
    client: ClaudeSDKClient,
    project_dir: Path,
    websocket_server = None,
) -> SessionResult:
    """
    Run an orchestrated session with an initial task prompt.

    Args:
        client: Claude SDK client (must already be configured with orchestrator
            prompt and agent definitions)
        project_dir: Project directory path, included in the initial message to
            tell the orchestrator where to work
        websocket_server: Optional WebSocketServer instance for real-time updates

    Returns:
        SessionResult with status and response text:
        - status="continue": Normal completion, agent can continue
        - status="error": Exception occurred during orchestration

    The orchestrator will use the Task tool to delegate to specialized agents
    (linear, coding, github, slack) based on the work needed.
    """
    global _websocket_server
    _websocket_server = websocket_server
    initial_message = f"""
    Start a new session. Your working directory is: {project_dir}

    Issue tracker: Linear (use the `linear` agent for all issue operations)

    Begin by:
    1. Reading {LINEAR_PROJECT_MARKER} to understand project state
    2. Checking Linear for current issue status via the `linear` agent
    3. Deciding what to work on next
    4. Delegating to appropriate agents
    """

    print("Starting orchestrated session...\n")

    # Broadcast that orchestrator is starting
    await broadcast_orchestrator_status("running", {"message": "Analyzing project state"})
    await broadcast_reasoning("Starting new orchestration session", {"project_dir": str(project_dir)})

    try:
        await client.query(initial_message)

        response_text: str = ""
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
                        print(block.text, end="", flush=True)
                    elif isinstance(block, ToolUseBlock):
                        print(f"\n[Tool: {block.name}]", flush=True)

                        # Broadcast when orchestrator delegates to an agent
                        if block.name == "Task":
                            tool_input = block.input if hasattr(block, 'input') else {}
                            agent_name = tool_input.get('agent', 'unknown')
                            task_description = tool_input.get('task', '')[:100]  # First 100 chars

                            await broadcast_reasoning(
                                f"Delegating to {agent_name} agent",
                                {"agent": agent_name, "task_preview": task_description}
                            )

                            # Broadcast status change for delegated agent
                            if _websocket_server:
                                await _websocket_server.broadcast_agent_status(
                                    agent_name=agent_name,
                                    status="running",
                                    metadata={"delegated_by": "orchestrator"}
                                )

        print("\n" + "-" * 70 + "\n")

        # Broadcast that orchestrator finished
        await broadcast_orchestrator_status("idle", {"message": "Session complete"})

        return SessionResult(status=SESSION_CONTINUE, response=response_text)

    except ConnectionError as e:
        await broadcast_orchestrator_status("error", {"error": str(e)})
        print(f"\nNetwork error in orchestrated session: {e}")
        print("Check your internet connection and Arcade MCP gateway availability.")
        traceback.print_exc()
        return SessionResult(status=SESSION_ERROR, response=str(e))

    except TimeoutError as e:
        await broadcast_orchestrator_status("error", {"error": str(e)})
        print(f"\nTimeout in orchestrated session: {e}")
        print("The orchestration timed out. This may be due to slow MCP responses.")
        traceback.print_exc()
        return SessionResult(status=SESSION_ERROR, response=str(e))

    except Exception as e:
        await broadcast_orchestrator_status("error", {"error": str(e)})
        error_type: str = type(e).__name__
        error_msg: str = str(e)

        print(f"\nError in orchestrated session ({error_type}): {error_msg}")
        print("\nFull traceback:")
        traceback.print_exc()

        # Provide actionable guidance based on error type
        error_lower = error_msg.lower()
        if "arcade" in error_lower or "mcp" in error_lower:
            print("\nThis appears to be an Arcade MCP Gateway error.")
            print("Check your ARCADE_API_KEY and ARCADE_GATEWAY_SLUG configuration.")
        elif "agent" in error_lower or "delegation" in error_lower:
            print("\nThis appears to be an agent delegation error.")
            print("Check the agent definitions and ensure all required tools are authorized.")
        elif "auth" in error_lower or "token" in error_lower:
            print("\nThis appears to be an authentication error.")
            print("Check your CLAUDE_CODE_OAUTH_TOKEN environment variable.")
        else:
            # Unexpected error type - make this visible
            print(f"\nUnexpected error type: {error_type}")
            print("This may indicate a bug or an unhandled edge case.")
            print("The orchestrator will retry, but please report this if it persists.")

        return SessionResult(status=SESSION_ERROR, response=error_msg)
