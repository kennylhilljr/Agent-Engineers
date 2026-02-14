"""AgentMetricsCollector - Core collector for tracking agent delegations.

This module provides the AgentMetricsCollector class which:
- Manages session lifecycle (start_session, end_session)
- Provides track_agent() context manager for tracking agent delegations
- Records AgentEvent objects with automatic token/cost/duration calculation
- Integrates with MetricsStore for persistence
- Handles both success and failure cases gracefully

Usage:
    collector = AgentMetricsCollector(project_name="my-project")

    # Start a session
    session_id = collector.start_session(session_type="initializer")

    # Track an agent delegation
    with collector.track_agent("coding", "AI-46", "claude-sonnet-4-5") as tracker:
        # Do work...
        tracker.add_tokens(input_tokens=1000, output_tokens=2000)
        tracker.add_artifact("file:agent_metrics_collector.py")

    # End the session
    collector.end_session(session_id, status="complete")
"""

import contextlib
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from metrics import AgentEvent, AgentProfile, DashboardState, SessionSummary
from metrics_store import MetricsStore


# Model pricing (USD per 1000 tokens)
MODEL_PRICING = {
    "claude-opus-4-6": {"input": 0.015, "output": 0.075},
    "claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5": {"input": 0.0008, "output": 0.004},
    "claude-sonnet-3-5": {"input": 0.003, "output": 0.015},
}


class AgentTracker:
    """Context manager helper for tracking a single agent delegation.

    This is yielded by track_agent() and allows the caller to:
    - Add token counts
    - Add artifacts produced
    - The tracker automatically records the event on exit
    """

    def __init__(
        self,
        event_id: str,
        agent_name: str,
        session_id: str,
        ticket_key: str,
        model_used: str,
        started_at: str,
    ):
        """Initialize tracker.

        Args:
            event_id: Unique event identifier
            agent_name: Name of the agent
            session_id: Parent session ID
            ticket_key: Linear ticket key
            model_used: Model identifier
            started_at: ISO 8601 start timestamp
        """
        self.event_id = event_id
        self.agent_name = agent_name
        self.session_id = session_id
        self.ticket_key = ticket_key
        self.model_used = model_used
        self.started_at = started_at
        self.start_time = time.time()

        # Accumulated data
        self.input_tokens = 0
        self.output_tokens = 0
        self.artifacts: list[str] = []
        self.error_message = ""
        self.status: Literal["success", "error", "timeout", "blocked"] = "success"

    def add_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Add token counts to this event.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def add_artifact(self, artifact: str) -> None:
        """Add an artifact to this event.

        Artifacts are strings like:
        - "file:src/foo.py"
        - "commit:abc123"
        - "pr:#42"
        - "issue:AI-12"

        Args:
            artifact: Artifact identifier
        """
        self.artifacts.append(artifact)

    def set_error(self, error_message: str) -> None:
        """Mark this event as an error.

        Args:
            error_message: Error description
        """
        self.status = "error"
        self.error_message = error_message

    def finalize(self) -> AgentEvent:
        """Finalize the event and return the AgentEvent object.

        Returns:
            Complete AgentEvent with all fields populated
        """
        ended_at = datetime.utcnow().isoformat() + "Z"
        duration_seconds = time.time() - self.start_time

        # Calculate cost
        total_tokens = self.input_tokens + self.output_tokens
        estimated_cost_usd = _calculate_cost(
            self.model_used,
            self.input_tokens,
            self.output_tokens
        )

        event: AgentEvent = {
            "event_id": self.event_id,
            "agent_name": self.agent_name,
            "session_id": self.session_id,
            "ticket_key": self.ticket_key,
            "started_at": self.started_at,
            "ended_at": ended_at,
            "duration_seconds": duration_seconds,
            "status": self.status,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "artifacts": self.artifacts,
            "error_message": self.error_message,
            "model_used": self.model_used,
        }

        return event


def _calculate_cost(model_used: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated cost in USD for token usage.

    Args:
        model_used: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Estimated cost in USD
    """
    # Default pricing if model not in table
    pricing = MODEL_PRICING.get(
        model_used,
        {"input": 0.003, "output": 0.015}  # Default to Sonnet pricing
    )

    # Cost per 1000 tokens
    input_cost = (input_tokens / 1000.0) * pricing["input"]
    output_cost = (output_tokens / 1000.0) * pricing["output"]

    return input_cost + output_cost


def _create_empty_profile(agent_name: str) -> AgentProfile:
    """Create an empty AgentProfile for a new agent.

    Args:
        agent_name: Name of the agent

    Returns:
        Empty AgentProfile with all counters at zero
    """
    now = datetime.utcnow().isoformat() + "Z"

    profile: AgentProfile = {
        "agent_name": agent_name,
        "total_invocations": 0,
        "successful_invocations": 0,
        "failed_invocations": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "total_duration_seconds": 0.0,
        "commits_made": 0,
        "prs_created": 0,
        "prs_merged": 0,
        "files_created": 0,
        "files_modified": 0,
        "lines_added": 0,
        "lines_removed": 0,
        "tests_written": 0,
        "issues_created": 0,
        "issues_completed": 0,
        "messages_sent": 0,
        "reviews_completed": 0,
        "success_rate": 0.0,
        "avg_duration_seconds": 0.0,
        "avg_tokens_per_call": 0.0,
        "cost_per_success_usd": 0.0,
        "xp": 0,
        "level": 1,
        "current_streak": 0,
        "best_streak": 0,
        "achievements": [],
        "strengths": [],
        "weaknesses": [],
        "recent_events": [],
        "last_error": "",
        "last_active": now,
    }

    return profile


def _update_agent_profile(profile: AgentProfile, event: AgentEvent) -> AgentProfile:
    """Update an agent profile with a new event.

    Args:
        profile: Existing agent profile
        event: New event to incorporate

    Returns:
        Updated agent profile
    """
    # Update counters
    profile["total_invocations"] += 1

    if event["status"] == "success":
        profile["successful_invocations"] += 1
        profile["current_streak"] += 1
        if profile["current_streak"] > profile["best_streak"]:
            profile["best_streak"] = profile["current_streak"]
    else:
        profile["failed_invocations"] += 1
        profile["current_streak"] = 0
        profile["last_error"] = event["error_message"]

    profile["total_tokens"] += event["total_tokens"]
    profile["total_cost_usd"] += event["estimated_cost_usd"]
    profile["total_duration_seconds"] += event["duration_seconds"]

    # Update artifact counters based on artifacts
    for artifact in event["artifacts"]:
        if artifact.startswith("commit:"):
            profile["commits_made"] += 1
        elif artifact.startswith("pr:") and "created" in artifact:
            profile["prs_created"] += 1
        elif artifact.startswith("pr:") and "merged" in artifact:
            profile["prs_merged"] += 1
        elif artifact.startswith("file:") and "created" in artifact:
            profile["files_created"] += 1
        elif artifact.startswith("file:") and "modified" in artifact:
            profile["files_modified"] += 1
        elif artifact.startswith("issue:") and "created" in artifact:
            profile["issues_created"] += 1
        elif artifact.startswith("issue:") and "completed" in artifact:
            profile["issues_completed"] += 1
        elif artifact.startswith("message:"):
            profile["messages_sent"] += 1
        elif artifact.startswith("review:"):
            profile["reviews_completed"] += 1

    # Update derived metrics
    if profile["total_invocations"] > 0:
        profile["success_rate"] = profile["successful_invocations"] / profile["total_invocations"]
        profile["avg_duration_seconds"] = profile["total_duration_seconds"] / profile["total_invocations"]
        profile["avg_tokens_per_call"] = profile["total_tokens"] / profile["total_invocations"]

    if profile["successful_invocations"] > 0:
        profile["cost_per_success_usd"] = profile["total_cost_usd"] / profile["successful_invocations"]

    # Update recent events (keep last 20)
    profile["recent_events"].append(event["event_id"])
    if len(profile["recent_events"]) > 20:
        profile["recent_events"] = profile["recent_events"][-20:]

    profile["last_active"] = event["ended_at"]

    return profile


class AgentMetricsCollector:
    """Core collector class for tracking agent delegations.

    Manages session lifecycle and provides a context manager for tracking
    individual agent invocations. Integrates with MetricsStore for persistence.

    Usage:
        collector = AgentMetricsCollector(project_name="my-project")

        session_id = collector.start_session(session_type="initializer")

        with collector.track_agent("coding", "AI-46", "claude-sonnet-4-5") as tracker:
            # Do work
            tracker.add_tokens(input_tokens=1000, output_tokens=2000)
            tracker.add_artifact("file:agent_metrics_collector.py")

        collector.end_session(session_id, status="complete")
    """

    def __init__(self, project_name: str, metrics_dir: Optional[Path] = None):
        """Initialize the collector.

        Args:
            project_name: Name of the project
            metrics_dir: Directory to store metrics files (default: current directory)
        """
        self.project_name = project_name
        self.store = MetricsStore(project_name=project_name, metrics_dir=metrics_dir)

        # Active session tracking
        self._active_sessions: dict[str, dict] = {}

    def start_session(
        self,
        session_type: Literal["initializer", "continuation"] = "initializer"
    ) -> str:
        """Start a new session.

        Args:
            session_type: Type of session ("initializer" or "continuation")

        Returns:
            Session ID (UUID)
        """
        session_id = str(uuid.uuid4())
        started_at = datetime.utcnow().isoformat() + "Z"

        # Load current state to get session number
        state = self.store.load()
        session_number = state["total_sessions"] + 1

        # Track session info
        self._active_sessions[session_id] = {
            "session_number": session_number,
            "session_type": session_type,
            "started_at": started_at,
            "agents_invoked": [],
            "tickets_worked": set(),
            "total_tokens": 0,
            "total_cost_usd": 0.0,
        }

        return session_id

    def end_session(
        self,
        session_id: str,
        status: Literal["continue", "error", "complete"] = "complete"
    ) -> None:
        """End an active session.

        Args:
            session_id: Session ID to end
            status: Final status of the session

        Raises:
            ValueError: If session_id is not an active session
        """
        if session_id not in self._active_sessions:
            raise ValueError(f"Session {session_id} is not an active session")

        session_info = self._active_sessions[session_id]
        ended_at = datetime.utcnow().isoformat() + "Z"

        # Create session summary
        session_summary: SessionSummary = {
            "session_id": session_id,
            "session_number": session_info["session_number"],
            "session_type": session_info["session_type"],
            "started_at": session_info["started_at"],
            "ended_at": ended_at,
            "status": status,
            "agents_invoked": session_info["agents_invoked"],
            "total_tokens": session_info["total_tokens"],
            "total_cost_usd": session_info["total_cost_usd"],
            "tickets_worked": list(session_info["tickets_worked"]),
        }

        # Load state, add session, save
        state = self.store.load()
        state["sessions"].append(session_summary)
        state["total_sessions"] += 1
        self.store.save(state)

        # Remove from active sessions
        del self._active_sessions[session_id]

    @contextlib.contextmanager
    def track_agent(
        self,
        agent_name: str,
        ticket_key: str,
        model_used: str,
        session_id: Optional[str] = None
    ):
        """Context manager for tracking an agent delegation.

        Usage:
            with collector.track_agent("coding", "AI-46", "claude-sonnet-4-5") as tracker:
                # Do work
                tracker.add_tokens(input_tokens=1000, output_tokens=2000)
                tracker.add_artifact("file:foo.py")

        The context manager:
        - Tracks start/end timestamps automatically
        - Accepts token counts and artifacts via the tracker
        - Records the event on exit (both success and exception)
        - Handles exceptions gracefully

        Args:
            agent_name: Name of the agent (e.g., "coding", "github", "linear")
            ticket_key: Linear ticket key (e.g., "AI-46")
            model_used: Model identifier (e.g., "claude-sonnet-4-5")
            session_id: Optional session ID (if None, creates a temporary session)

        Yields:
            AgentTracker instance for adding tokens and artifacts
        """
        # Generate event ID and timestamps
        event_id = str(uuid.uuid4())
        started_at = datetime.utcnow().isoformat() + "Z"

        # Use provided session or create temporary one
        temp_session = session_id is None
        if temp_session:
            session_id = self.start_session(session_type="continuation")

        # Create tracker
        tracker = AgentTracker(
            event_id=event_id,
            agent_name=agent_name,
            session_id=session_id,
            ticket_key=ticket_key,
            model_used=model_used,
            started_at=started_at,
        )

        try:
            # Yield tracker to caller
            yield tracker

        except Exception as e:
            # Mark as error but don't suppress the exception
            tracker.set_error(str(e))
            raise

        finally:
            # Always record the event (success or failure)
            event = tracker.finalize()
            self._record_event(event, session_id)

            # End temporary session
            if temp_session:
                self.end_session(session_id, status="complete")

    def _record_event(self, event: AgentEvent, session_id: str) -> None:
        """Record an event to the metrics store.

        Updates:
        - Global event log
        - Agent profile for this agent
        - Session tracking (if session is active)
        - Global counters

        Args:
            event: Event to record
            session_id: Session ID for this event
        """
        # Load current state
        state = self.store.load()

        # Add event to log
        state["events"].append(event)

        # Update or create agent profile
        if event["agent_name"] not in state["agents"]:
            state["agents"][event["agent_name"]] = _create_empty_profile(event["agent_name"])

        profile = state["agents"][event["agent_name"]]
        state["agents"][event["agent_name"]] = _update_agent_profile(profile, event)

        # Update global counters
        state["total_tokens"] += event["total_tokens"]
        state["total_cost_usd"] += event["estimated_cost_usd"]
        state["total_duration_seconds"] += event["duration_seconds"]

        # Update active session tracking
        if session_id in self._active_sessions:
            session_info = self._active_sessions[session_id]
            if event["agent_name"] not in session_info["agents_invoked"]:
                session_info["agents_invoked"].append(event["agent_name"])
            session_info["tickets_worked"].add(event["ticket_key"])
            session_info["total_tokens"] += event["total_tokens"]
            session_info["total_cost_usd"] += event["estimated_cost_usd"]

        # Save state
        self.store.save(state)

    def get_state(self) -> DashboardState:
        """Get the current dashboard state.

        Returns:
            Current DashboardState
        """
        return self.store.load()
