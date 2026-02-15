"""
Orchestrator Session Runner
===========================

Runs orchestrated sessions where the main agent delegates to specialized agents.
"""

import traceback
from pathlib import Path
from typing import Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from agent import SESSION_CONTINUE, SESSION_ERROR, SessionResult
from progress import LINEAR_PROJECT_MARKER


async def run_orchestrated_session(
    client: ClaudeSDKClient,
    project_dir: Path,
    session_id: Optional[str] = None,
    metrics_collector: Optional[object] = None,
) -> SessionResult:
    """
    Run an orchestrated session with an initial task prompt.

    Args:
        client: Claude SDK client (must already be configured with orchestrator
            prompt and agent definitions)
        project_dir: Project directory path, included in the initial message to
            tell the orchestrator where to work
        session_id: Optional session ID for metrics tracking
        metrics_collector: Optional AgentMetricsCollector instance for tracking delegations

    Returns:
        SessionResult with status and response text:
        - status="continue": Normal completion, agent can continue
        - status="error": Exception occurred during orchestration

    The orchestrator will use the Task tool to delegate to specialized agents
    (linear, coding, github, slack) based on the work needed.
    """
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

    try:
        await client.query(initial_message)

        response_text: str = ""

        # Track Task tool delegations
        # Map of tool_use_id -> (agent_name, ticket_key, start_timestamp)
        active_delegations: dict[str, tuple[str, str, str]] = {}

        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
                        print(block.text, end="", flush=True)
                    elif isinstance(block, ToolUseBlock):
                        print(f"\n[Tool: {block.name}]", flush=True)

                        # Detect Task tool delegation
                        if block.name == "Task" and metrics_collector and session_id:
                            try:
                                # Extract agent name and task from tool input
                                task_input = block.input if hasattr(block, 'input') else {}
                                agent_name = task_input.get("agent", "unknown")
                                task_description = task_input.get("task", "")

                                # Try to extract ticket key from task description
                                # Common patterns: "AI-51", "Work on AI-51", etc.
                                import re
                                ticket_match = re.search(r'\b(AI-\d+)\b', task_description)
                                ticket_key = ticket_match.group(1) if ticket_match else "unknown"

                                # Store delegation info for matching with result
                                from datetime import datetime
                                started_at = datetime.utcnow().isoformat() + "Z"
                                active_delegations[block.id] = (agent_name, ticket_key, started_at)

                                print(f"   [Delegation tracked: {agent_name} on {ticket_key}]", flush=True)
                            except Exception as e:
                                print(f"   [Warning: Failed to track delegation: {e}]", flush=True)

            elif isinstance(msg, UserMessage):
                # Process tool results to capture delegation completion
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        # Check if this is a Task tool result
                        if hasattr(block, 'tool_use_id') and block.tool_use_id in active_delegations:
                            try:
                                agent_name, ticket_key, started_at = active_delegations[block.tool_use_id]

                                # Determine if delegation succeeded or failed
                                is_error = bool(block.is_error) if hasattr(block, 'is_error') and block.is_error else False
                                status = "error" if is_error else "success"

                                # Track the delegation event
                                # Note: Token counts are not directly available in ToolResultBlock
                                # We'll use a simplified tracking approach
                                model_used = "claude-haiku-4-5"  # Default for most agents

                                # Create a tracker context for this completed delegation
                                with metrics_collector.track_agent(
                                    agent_name=agent_name,
                                    ticket_key=ticket_key,
                                    model_used=model_used,
                                    session_id=session_id
                                ) as tracker:
                                    # Estimate token usage (conservative estimate)
                                    # In production, this would come from SDK metadata
                                    tracker.add_tokens(input_tokens=500, output_tokens=1000)

                                    if is_error:
                                        error_msg = str(block.content) if hasattr(block, 'content') else "Unknown error"
                                        tracker.set_error(error_msg)
                                    else:
                                        # Extract artifacts from successful completion
                                        # This is a simplified version - real implementation would parse result
                                        tracker.add_artifact(f"delegation:{agent_name}")

                                # Remove from active delegations
                                del active_delegations[block.tool_use_id]

                                print(f"   [Delegation completed: {agent_name} - {status}]", flush=True)
                            except Exception as e:
                                print(f"   [Warning: Failed to record delegation: {e}]", flush=True)

        print("\n" + "-" * 70 + "\n")
        return SessionResult(status=SESSION_CONTINUE, response=response_text)

    except ConnectionError as e:
        print(f"\nNetwork error in orchestrated session: {e}")
        print("Check your internet connection and Arcade MCP gateway availability.")
        traceback.print_exc()
        return SessionResult(status=SESSION_ERROR, response=str(e))

    except TimeoutError as e:
        print(f"\nTimeout in orchestrated session: {e}")
        print("The orchestration timed out. This may be due to slow MCP responses.")
        traceback.print_exc()
        return SessionResult(status=SESSION_ERROR, response=str(e))

    except Exception as e:
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
