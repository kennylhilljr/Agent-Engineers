"""Agent Metrics Collection System - Phase 2 Implementation.

This module provides the AgentMetricsCollector and MetricsStore classes that
implement session lifecycle tracking and metrics persistence for the Agent Status
Dashboard. It integrates all Phase 1 components (TypedDict types, XP calculations,
strengths/weaknesses detection, and achievement checking).

Key Components:
- MetricsStore: JSON persistence with atomic writes and corruption recovery
- AgentMetricsCollector: Session lifecycle management (start_session, end_session)
- Integration with XP calculations, achievements, and strengths/weaknesses

Usage:
    collector = AgentMetricsCollector(project_dir="/path/to/project")

    # Start a session
    collector.start_session(session_num=1, is_initializer=True)

    # Track agent work (to be implemented in Phase 2, AI-51)
    # with collector.track_agent("coding", ticket_key="AI-50") as tracker:
    #     ... agent work ...

    # End session
    collector.end_session(status="continue")
"""

import json
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal

from achievements import check_all_achievements
from metrics import AgentEvent, AgentProfile, DashboardState, SessionSummary
from strengths_weaknesses import (
    calculate_rolling_window_stats,
    calculate_agent_percentiles,
    detect_strengths,
    detect_weaknesses,
)
from xp_calculations import calculate_level_from_xp


class MetricsStore:
    """JSON persistence layer for metrics data.

    Provides atomic writes, FIFO eviction, and corruption recovery for the
    .agent_metrics.json file that stores all dashboard state.

    Features:
    - Atomic writes: Uses temp file + rename to prevent corruption
    - FIFO eviction: Caps events at 500 and sessions at 50
    - Corruption recovery: Creates fresh state if JSON is invalid
    - Thread-safe: Each operation is atomic at the filesystem level
    """

    METRICS_FILENAME = ".agent_metrics.json"
    EVENTS_CAP = 500  # Maximum events to retain
    SESSIONS_CAP = 50  # Maximum session summaries to retain

    def __init__(self, project_dir: Path):
        """Initialize the metrics store.

        Args:
            project_dir: Path to the project directory where metrics will be stored
        """
        self.project_dir = Path(project_dir)
        self.metrics_file = self.project_dir / self.METRICS_FILENAME

    def load(self) -> DashboardState:
        """Load the dashboard state from disk.

        Returns:
            DashboardState with current metrics, or fresh state if file doesn't exist

        Note:
            If the file is corrupted, this will create a fresh state and back up
            the corrupted file with a .corrupted suffix.
        """
        if not self.metrics_file.exists():
            return self._create_fresh_state()

        try:
            with open(self.metrics_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data  # type: ignore[return-value]
        except (json.JSONDecodeError, OSError) as e:
            # Corruption detected - back up the corrupted file
            backup_path = self.metrics_file.with_suffix('.json.corrupted')
            try:
                self.metrics_file.rename(backup_path)
                print(f"Warning: Corrupted metrics file backed up to {backup_path}")
            except OSError:
                print(f"Warning: Could not back up corrupted metrics file: {e}")

            # Return fresh state
            return self._create_fresh_state()

    def save(self, state: DashboardState) -> None:
        """Save the dashboard state to disk using atomic write.

        Args:
            state: The dashboard state to persist

        Note:
            Uses temp file + rename for atomic writes. This prevents corruption
            if the process is interrupted during writing.
        """
        # Ensure project directory exists
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # Apply FIFO eviction before saving
        self._apply_fifo_eviction(state)

        # Update timestamp
        state["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Write to temporary file first (atomic write pattern)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.project_dir,
            prefix='.agent_metrics_',
            suffix='.tmp'
        )

        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)

            # Atomic rename (overwrites existing file)
            os.replace(temp_path, self.metrics_file)
        except Exception:
            # Clean up temp file if write failed
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def _create_fresh_state(self) -> DashboardState:
        """Create a fresh dashboard state.

        Returns:
            New DashboardState with all fields initialized to defaults
        """
        now = datetime.now(timezone.utc).isoformat()
        project_name = self.project_dir.name or "unnamed-project"

        state: DashboardState = {
            "version": 1,
            "project_name": project_name,
            "created_at": now,
            "updated_at": now,
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": []
        }
        return state

    def _apply_fifo_eviction(self, state: DashboardState) -> None:
        """Apply FIFO eviction to events and sessions.

        Args:
            state: Dashboard state to modify in-place

        Note:
            This keeps only the most recent EVENTS_CAP events and SESSIONS_CAP sessions.
            Oldest entries are evicted first.
        """
        # Evict oldest events if over cap
        if len(state["events"]) > self.EVENTS_CAP:
            state["events"] = state["events"][-self.EVENTS_CAP:]

        # Evict oldest sessions if over cap
        if len(state["sessions"]) > self.SESSIONS_CAP:
            state["sessions"] = state["sessions"][-self.SESSIONS_CAP:]


class AgentMetricsCollector:
    """Collects and persists agent performance metrics with session lifecycle.

    This is the main instrumentation class that tracks session start/end and
    integrates with the XP system, achievements, and strengths/weaknesses detection.

    Session Lifecycle:
        1. start_session() - Begin tracking a new session
        2. [track_agent() calls - to be implemented in AI-51]
        3. end_session() - Finalize session and update rollups

    Example:
        collector = AgentMetricsCollector(project_dir)

        # Start session
        collector.start_session(session_num=1, is_initializer=True)

        # ... agent work happens ...

        # End session
        collector.end_session(status="continue")
    """

    def __init__(self, project_dir: Path):
        """Initialize the metrics collector.

        Args:
            project_dir: Path to the project directory
        """
        self.project_dir = Path(project_dir)
        self.store = MetricsStore(project_dir)
        self.state = self.store.load()

        # Current session tracking
        self.current_session_id: str | None = None
        self.current_session_started_at: str | None = None
        self.current_session_number: int | None = None
        self.current_session_type: Literal["initializer", "continuation"] | None = None
        self.current_session_agents: list[str] = []
        self.current_session_tickets: list[str] = []

    def start_session(
        self,
        session_num: int,
        is_initializer: bool = False,
    ) -> str:
        """Start tracking a new session.

        Args:
            session_num: Sequential session number (1, 2, 3, ...)
            is_initializer: True if this is the first session that creates Linear issues

        Returns:
            Session ID (UUID) for this session

        Raises:
            RuntimeError: If a session is already in progress
        """
        if self.current_session_id is not None:
            raise RuntimeError(
                f"Session {self.current_session_id} is already in progress. "
                "Call end_session() before starting a new one."
            )

        # Generate session ID and timestamp
        session_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()

        # Track current session
        self.current_session_id = session_id
        self.current_session_started_at = started_at
        self.current_session_number = session_num
        self.current_session_type = "initializer" if is_initializer else "continuation"
        self.current_session_agents = []
        self.current_session_tickets = []

        return session_id

    def end_session(
        self,
        status: Literal["continue", "error", "complete"] = "continue",
    ) -> SessionSummary:
        """End the current session and update rollups.

        Args:
            status: Session outcome:
                - "continue": Normal completion, more work to do
                - "error": Session encountered an error
                - "complete": All work done, project complete

        Returns:
            SessionSummary for the completed session

        Raises:
            RuntimeError: If no session is in progress
        """
        if self.current_session_id is None:
            raise RuntimeError("No session in progress. Call start_session() first.")

        # Calculate session metrics
        ended_at = datetime.now(timezone.utc).isoformat()

        # Get events from this session
        session_events = [
            event for event in self.state["events"]
            if event["session_id"] == self.current_session_id
        ]

        # Calculate totals
        total_tokens = sum(event["total_tokens"] for event in session_events)
        total_cost_usd = sum(event["estimated_cost_usd"] for event in session_events)

        # Get unique agents invoked (preserve order)
        agents_invoked = []
        for agent in self.current_session_agents:
            if agent not in agents_invoked:
                agents_invoked.append(agent)

        # Get unique tickets worked (preserve order)
        tickets_worked = []
        for ticket in self.current_session_tickets:
            if ticket not in tickets_worked:
                tickets_worked.append(ticket)

        # Create session summary
        summary: SessionSummary = {
            "session_id": self.current_session_id,
            "session_number": self.current_session_number or 0,
            "session_type": self.current_session_type or "continuation",
            "started_at": self.current_session_started_at or ended_at,
            "ended_at": ended_at,
            "status": status,
            "agents_invoked": agents_invoked,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost_usd,
            "tickets_worked": tickets_worked,
        }

        # Add to session history
        self.state["sessions"].append(summary)

        # Update global counters
        self.state["total_sessions"] += 1

        # Reset current session tracking
        self.current_session_id = None
        self.current_session_started_at = None
        self.current_session_number = None
        self.current_session_type = None
        self.current_session_agents = []
        self.current_session_tickets = []

        # Persist updated state
        self.store.save(self.state)

        return summary

    @contextmanager
    def track_agent(
        self,
        agent_name: str,
        ticket_key: str = "",
    ) -> Iterator["AgentTracker"]:
        """Context manager for tracking an agent delegation.

        This will be fully implemented in AI-51 (Instrument orchestrator.py).
        For now, this provides the interface that will be used.

        Args:
            agent_name: Name of the agent ("coding", "github", "linear", etc.)
            ticket_key: Linear ticket key being worked on (e.g., "AI-50")

        Yields:
            AgentTracker instance for recording tokens, artifacts, etc.

        Example:
            with collector.track_agent("coding", ticket_key="AI-50") as tracker:
                # ... do agent work ...
                tracker.set_tokens(input_tokens=1000, output_tokens=500)
                tracker.add_artifact("file:agent_metrics.py")
        """
        if self.current_session_id is None:
            raise RuntimeError("No session in progress. Call start_session() first.")

        # Track this agent and ticket for session summary
        self.current_session_agents.append(agent_name)
        if ticket_key:
            self.current_session_tickets.append(ticket_key)

        # Create tracker
        tracker = AgentTracker(
            collector=self,
            agent_name=agent_name,
            ticket_key=ticket_key,
            session_id=self.current_session_id,
        )

        try:
            yield tracker
        finally:
            tracker._finalize()

    def get_dashboard_state(self) -> DashboardState:
        """Get the current dashboard state.

        Returns:
            Complete DashboardState for rendering
        """
        return self.state

    def get_agent_profile(self, agent_name: str) -> AgentProfile | None:
        """Get the profile for a specific agent.

        Args:
            agent_name: Name of the agent

        Returns:
            AgentProfile if the agent exists, None otherwise
        """
        return self.state["agents"].get(agent_name)

    def _ensure_agent_profile(self, agent_name: str) -> AgentProfile:
        """Ensure an agent profile exists, creating it if necessary.

        Args:
            agent_name: Name of the agent

        Returns:
            AgentProfile for the agent (existing or newly created)
        """
        if agent_name not in self.state["agents"]:
            now = datetime.now(timezone.utc).isoformat()
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
            self.state["agents"][agent_name] = profile

        return self.state["agents"][agent_name]

    def _record_event(self, event: AgentEvent) -> None:
        """Record an agent event and update all derived metrics.

        This is called by AgentTracker._finalize() when an agent delegation completes.

        Args:
            event: The event to record
        """
        # Add event to log
        self.state["events"].append(event)

        # Update global counters
        self.state["total_tokens"] += event["total_tokens"]
        self.state["total_cost_usd"] += event["estimated_cost_usd"]
        self.state["total_duration_seconds"] += event["duration_seconds"]

        # Get or create agent profile
        profile = self._ensure_agent_profile(event["agent_name"])

        # Update lifetime counters
        profile["total_invocations"] += 1
        profile["total_tokens"] += event["total_tokens"]
        profile["total_cost_usd"] += event["estimated_cost_usd"]
        profile["total_duration_seconds"] += event["duration_seconds"]
        profile["last_active"] = event["ended_at"]

        # Update success/failure counts and streak
        if event["status"] == "success":
            profile["successful_invocations"] += 1
            profile["current_streak"] += 1
            if profile["current_streak"] > profile["best_streak"]:
                profile["best_streak"] = profile["current_streak"]
        else:
            profile["failed_invocations"] += 1
            profile["current_streak"] = 0
            profile["last_error"] = event["error_message"]

        # Update derived metrics
        if profile["total_invocations"] > 0:
            profile["success_rate"] = (
                profile["successful_invocations"] / profile["total_invocations"]
            )
            profile["avg_duration_seconds"] = (
                profile["total_duration_seconds"] / profile["total_invocations"]
            )
            profile["avg_tokens_per_call"] = (
                profile["total_tokens"] / profile["total_invocations"]
            )

        if profile["successful_invocations"] > 0:
            profile["cost_per_success_usd"] = (
                profile["total_cost_usd"] / profile["successful_invocations"]
            )

        # Update XP and level (only for successful invocations)
        if event["status"] == "success":
            # Base XP for success
            profile["xp"] += 10

            # Streak bonus
            profile["xp"] += profile["current_streak"]

            # Update level based on new XP
            profile["level"] = calculate_level_from_xp(profile["xp"])

        # Update recent events (keep last 20)
        profile["recent_events"].append(event["event_id"])
        if len(profile["recent_events"]) > 20:
            profile["recent_events"] = profile["recent_events"][-20:]

        # Check for newly earned achievements
        agent_events = [
            e for e in self.state["events"]
            if e["agent_name"] == event["agent_name"]
        ]
        session_events = [
            e for e in self.state["events"]
            if e["session_id"] == event["session_id"]
        ]

        newly_earned = check_all_achievements(
            profile,
            event,
            agent_events,
            session_events
        )

        # Add new achievements to profile
        for achievement_id in newly_earned:
            if achievement_id not in profile["achievements"]:
                profile["achievements"].append(achievement_id)

        # Update strengths and weaknesses
        # Calculate rolling window statistics for this agent
        stats = calculate_rolling_window_stats(
            self.state["events"],
            event["agent_name"],
            window_size=20
        )

        # Calculate percentiles across all agents for comparison
        percentiles = calculate_agent_percentiles(self.state, window_size=20)

        # Detect strengths and weaknesses
        profile["strengths"] = detect_strengths(event["agent_name"], stats, percentiles)
        profile["weaknesses"] = detect_weaknesses(event["agent_name"], stats, percentiles)

        # Persist updated state
        self.store.save(self.state)


class AgentTracker:
    """Tracks a single agent delegation.

    This is yielded by AgentMetricsCollector.track_agent() and allows recording
    tokens, artifacts, and errors during the agent's execution.

    Note: This is a placeholder for AI-51. Full implementation will come when
    we instrument orchestrator.py to emit delegation events.
    """

    def __init__(
        self,
        collector: AgentMetricsCollector,
        agent_name: str,
        ticket_key: str,
        session_id: str,
    ):
        """Initialize the agent tracker.

        Args:
            collector: Parent collector instance
            agent_name: Name of the agent being tracked
            ticket_key: Linear ticket key
            session_id: Current session ID
        """
        self.collector = collector
        self.agent_name = agent_name
        self.ticket_key = ticket_key
        self.session_id = session_id
        self.event_id = str(uuid.uuid4())
        self.started_at = datetime.now(timezone.utc).isoformat()

        # Event data (will be populated during tracking)
        self.input_tokens = 0
        self.output_tokens = 0
        self.artifacts: list[str] = []
        self.error_message = ""
        self.status: Literal["success", "error", "timeout", "blocked"] = "success"
        self.model_used = "claude-sonnet-4-5-20250929"  # Default model

    def set_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Set token counts for this delegation.

        Args:
            input_tokens: Input tokens consumed
            output_tokens: Output tokens generated
        """
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def add_artifact(self, artifact: str) -> None:
        """Add an artifact produced by this delegation.

        Args:
            artifact: Artifact identifier (e.g., "file:agent_metrics.py", "commit:abc123")
        """
        self.artifacts.append(artifact)

    def set_error(self, error_message: str) -> None:
        """Record an error for this delegation.

        Args:
            error_message: Error description
        """
        self.error_message = error_message
        self.status = "error"

    def set_model(self, model: str) -> None:
        """Set the model used for this delegation.

        Args:
            model: Model identifier
        """
        self.model_used = model

    def _finalize(self) -> None:
        """Finalize the event and record it (called automatically by context manager)."""
        ended_at = datetime.now(timezone.utc).isoformat()

        # Calculate duration
        started_time = datetime.fromisoformat(self.started_at)
        ended_time = datetime.fromisoformat(ended_at)
        duration_seconds = (ended_time - started_time).total_seconds()

        # Calculate cost (simple model for now)
        total_tokens = self.input_tokens + self.output_tokens
        # Using Sonnet 4.5 pricing: $0.003/1k input, $0.015/1k output
        estimated_cost_usd = (
            (self.input_tokens / 1000) * 0.003 +
            (self.output_tokens / 1000) * 0.015
        )

        # Create event
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

        # Record the event
        self.collector._record_event(event)
