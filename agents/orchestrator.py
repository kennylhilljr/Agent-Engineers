"""
Orchestrator Session Runner
===========================

Runs orchestrated sessions where the main agent delegates to specialized agents.
Emits reasoning and delegation decision events to the dashboard via WebSocket.
"""

import asyncio
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    TextBlock,
    ToolUseBlock,
)

from agent import SESSION_CONTINUE, SESSION_ERROR, SessionResult
from dashboard.metrics import AgentEvent
from dashboard.metrics_store import MetricsStore
from progress import LINEAR_PROJECT_MARKER

# WebSocket server availability (lazy loaded)
WEBSOCKET_AVAILABLE: bool = False
_websocket_server: Optional[object] = None
_metrics_store: Optional[MetricsStore] = None


def _initialize_websocket():
    """Initialize WebSocket server connection if available."""
    global WEBSOCKET_AVAILABLE, _websocket_server

    if _websocket_server is not None:
        return

    try:
        # Try to import and get the WebSocket server instance
        # This will be available when the dashboard server is running
        from dashboard.server import DashboardServer
        # For now, we'll emit events via metrics store
        # WebSocket integration will be handled by the server's broadcast
        WEBSOCKET_AVAILABLE = True
    except ImportError:
        WEBSOCKET_AVAILABLE = False


def _initialize_metrics_store(project_dir: Path):
    """Initialize metrics store for event persistence."""
    global _metrics_store

    if _metrics_store is None:
        try:
            _metrics_store = MetricsStore(
                project_name="agent-dashboard",
                metrics_dir=project_dir
            )
        except Exception as e:
            print(f"Warning: Could not initialize metrics store: {e}")


async def emit_reasoning_event(
    content: str,
    context: dict,
    project_dir: Path,
    session_id: str = "",
    event_type: str = "reasoning"
) -> None:
    """Emit a reasoning event to the dashboard.

    Args:
        content: Reasoning text content
        context: Context dictionary with metadata (complexity, agent_selection, etc.)
        project_dir: Project directory for metrics store
        session_id: Session identifier
        event_type: Type of reasoning event (reasoning, decision, delegation)
    """
    try:
        _initialize_metrics_store(project_dir)

        if _metrics_store is None:
            return

        # Create a special reasoning event that will be stored
        # These events will be broadcast via WebSocket by the dashboard server
        event_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Create AgentEvent for reasoning (status will be 'success' for reasoning events)
        reasoning_event: AgentEvent = {
            "event_id": event_id,
            "agent_name": "orchestrator",
            "session_id": session_id or str(uuid.uuid4()),
            "ticket_key": context.get("ticket_key", ""),
            "started_at": timestamp,
            "ended_at": timestamp,
            "duration_seconds": 0.0,
            "status": "success",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "artifacts": [
                f"reasoning:{event_type}",
                f"content:{content[:100]}",  # Store truncated content in artifacts
            ],
            "error_message": "",
            "model_used": "orchestrator",
        }

        # Add context as artifacts
        if "complexity" in context:
            reasoning_event["artifacts"].append(f"complexity:{context['complexity']}")
        if "agent_selection" in context:
            reasoning_event["artifacts"].append(f"agent_selection:{context['agent_selection']}")
        if "alternatives" in context:
            reasoning_event["artifacts"].append(f"alternatives:{','.join(context['alternatives'])}")

        # Store event
        state = _metrics_store.load()
        state["events"].append(reasoning_event)
        _metrics_store.save(state)

        # Print reasoning to console for visibility
        print(f"\n[Orchestrator {event_type.upper()}] {content}")
        if context:
            print(f"  Context: {context}")

    except Exception as e:
        # Graceful degradation - don't fail if event emission fails
        print(f"Warning: Failed to emit reasoning event: {e}")


async def run_orchestrated_session(
    client: ClaudeSDKClient,
    project_dir: Path,
) -> SessionResult:
    """
    Run an orchestrated session with an initial task prompt.

    Args:
        client: Claude SDK client (must already be configured with orchestrator
            prompt and agent definitions)
        project_dir: Project directory path, included in the initial message to
            tell the orchestrator where to work

    Returns:
        SessionResult with status and response text:
        - status="continue": Normal completion, agent can continue
        - status="error": Exception occurred during orchestration

    The orchestrator will use the Task tool to delegate to specialized agents
    (linear, coding, github, slack) based on the work needed.

    Event Emission:
        - Emits reasoning events when analyzing project state
        - Emits decision events when selecting work items
        - Emits delegation events when assigning to agents
        - All events are stored in metrics and broadcast via WebSocket
    """
    session_id = str(uuid.uuid4())

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
    print(f"Session ID: {session_id}\n")

    # Initialize event emission
    _initialize_metrics_store(project_dir)

    # Emit session start reasoning
    await emit_reasoning_event(
        content="Starting orchestrated session - analyzing project state and checking Linear for available work",
        context={
            "session_id": session_id,
            "project_dir": str(project_dir),
            "phase": "initialization"
        },
        project_dir=project_dir,
        session_id=session_id,
        event_type="session_start"
    )

    try:
        await client.query(initial_message)

        response_text: str = ""
        tool_use_count = 0
        delegation_count = 0

        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
                        print(block.text, end="", flush=True)

                        # Emit reasoning event for text blocks that contain decision-making content
                        if any(keyword in block.text.lower() for keyword in
                               ["delegat", "reasoning", "decid", "choos", "select", "complex"]):
                            await emit_reasoning_event(
                                content=block.text[:500],  # Limit content length
                                context={
                                    "session_id": session_id,
                                    "message_type": "reasoning",
                                    "block_number": tool_use_count
                                },
                                project_dir=project_dir,
                                session_id=session_id,
                                event_type="reasoning"
                            )

                    elif isinstance(block, ToolUseBlock):
                        tool_use_count += 1
                        print(f"\n[Tool: {block.name}]", flush=True)

                        # Emit delegation event when Task tool is used
                        if block.name == "Task":
                            delegation_count += 1
                            agent_name = block.input.get("agent", "unknown")
                            task_description = block.input.get("task", "")

                            await emit_reasoning_event(
                                content=f"Delegating to {agent_name} agent: {task_description[:200]}",
                                context={
                                    "session_id": session_id,
                                    "agent_selection": agent_name,
                                    "task": task_description[:100],
                                    "delegation_number": delegation_count,
                                    "complexity": _assess_complexity(task_description)
                                },
                                project_dir=project_dir,
                                session_id=session_id,
                                event_type="delegation"
                            )

        # Emit session completion reasoning
        await emit_reasoning_event(
            content=f"Session completed - {tool_use_count} tools used, {delegation_count} delegations made",
            context={
                "session_id": session_id,
                "tool_use_count": tool_use_count,
                "delegation_count": delegation_count,
                "phase": "completion",
                "status": "success"
            },
            project_dir=project_dir,
            session_id=session_id,
            event_type="session_complete"
        )

        print("\n" + "-" * 70 + "\n")
        return SessionResult(status=SESSION_CONTINUE, response=response_text)

    except ConnectionError as e:
        await emit_reasoning_event(
            content=f"Network error in orchestrated session: {str(e)}",
            context={
                "session_id": session_id,
                "error_type": "ConnectionError",
                "phase": "error"
            },
            project_dir=project_dir,
            session_id=session_id,
            event_type="error"
        )
        print(f"\nNetwork error in orchestrated session: {e}")
        print("Check your internet connection and Arcade MCP gateway availability.")
        traceback.print_exc()
        return SessionResult(status=SESSION_ERROR, response=str(e))

    except TimeoutError as e:
        await emit_reasoning_event(
            content=f"Timeout in orchestrated session: {str(e)}",
            context={
                "session_id": session_id,
                "error_type": "TimeoutError",
                "phase": "error"
            },
            project_dir=project_dir,
            session_id=session_id,
            event_type="error"
        )
        print(f"\nTimeout in orchestrated session: {e}")
        print("The orchestration timed out. This may be due to slow MCP responses.")
        traceback.print_exc()
        return SessionResult(status=SESSION_ERROR, response=str(e))

    except Exception as e:
        error_type: str = type(e).__name__
        error_msg: str = str(e)

        await emit_reasoning_event(
            content=f"Error in orchestrated session ({error_type}): {error_msg}",
            context={
                "session_id": session_id,
                "error_type": error_type,
                "error_message": error_msg,
                "phase": "error"
            },
            project_dir=project_dir,
            session_id=session_id,
            event_type="error"
        )

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


def _assess_complexity(task_description: str) -> str:
    """Assess task complexity based on task description.

    Args:
        task_description: Task description text

    Returns:
        Complexity level: "SIMPLE", "MODERATE", or "COMPLEX"
    """
    # Simple heuristic based on task length and keywords
    task_lower = task_description.lower()

    # Complex indicators
    complex_keywords = ["implement", "refactor", "architect", "design", "integration", "test"]
    if any(keyword in task_lower for keyword in complex_keywords) or len(task_description) > 200:
        return "COMPLEX"

    # Simple indicators
    simple_keywords = ["check", "list", "view", "read", "get"]
    if any(keyword in task_lower for keyword in simple_keywords) or len(task_description) < 50:
        return "SIMPLE"

    return "MODERATE"
