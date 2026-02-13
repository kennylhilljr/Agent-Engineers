"""
Progress Tracking Utilities
===========================

Functions for tracking and displaying progress of the autonomous coding agent.
Progress is tracked via Linear or Jira issues, with local state cached in
.linear_project.json or .jira_project.json.
"""

import json
import os
from pathlib import Path
from typing import Literal, TypedDict


# Local marker files to track project initialization
LINEAR_PROJECT_MARKER: str = ".linear_project.json"
JIRA_PROJECT_MARKER: str = ".jira_project.json"

# Which issue tracker is in use
TrackerType = Literal["linear", "jira"]


class ProjectState(TypedDict, total=False):
    """Structure of the project state file (works for both Linear and Jira)."""

    initialized: bool
    created_at: str
    # Linear-specific
    team_id: str
    team_key: str
    project_id: str
    project_name: str
    project_slug: str
    meta_issue_id: str
    # Jira-specific
    project_key: str
    meta_issue_key: str
    # Common
    total_issues: int
    notes: str
    # Dedup tracking: list of {"key": "ENG-42", "title": "Feature Name"} dicts
    issues: list[dict[str, str]]


def detect_tracker(project_dir: Path) -> TrackerType:
    """
    Detect which issue tracker is configured.

    Priority:
    1. If .jira_project.json exists -> jira
    2. If .linear_project.json exists -> linear
    3. If JIRA_SERVER env var is set -> jira
    4. Default -> linear

    Args:
        project_dir: Directory to check for state files

    Returns:
        "jira" or "linear"
    """
    if (project_dir / JIRA_PROJECT_MARKER).exists():
        return "jira"
    if (project_dir / LINEAR_PROJECT_MARKER).exists():
        return "linear"
    if os.environ.get("JIRA_SERVER"):
        return "jira"
    return "linear"


def _get_marker_file(project_dir: Path, tracker: TrackerType) -> Path:
    """Get the marker file path for the given tracker."""
    if tracker == "jira":
        return project_dir / JIRA_PROJECT_MARKER
    return project_dir / LINEAR_PROJECT_MARKER


def load_project_state(project_dir: Path, tracker: TrackerType | None = None) -> ProjectState | None:
    """
    Load the project state from the marker file.

    Args:
        project_dir: Directory containing the state file
        tracker: Which tracker to load state for (auto-detected if None)

    Returns:
        Project state dict or None if not initialized

    Raises:
        ValueError: If the state file exists but is corrupted or malformed
    """
    if tracker is None:
        tracker = detect_tracker(project_dir)

    marker_file = _get_marker_file(project_dir, tracker)

    if not marker_file.exists():
        return None

    try:
        with open(marker_file, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Corrupted state file at {marker_file}: {e}\n"
            f"Delete the file to restart initialization, or restore from backup."
        ) from e
    except IOError as e:
        raise ValueError(
            f"Cannot read state file at {marker_file}: {e}\n"
            f"Check file permissions."
        ) from e

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid state file at {marker_file}: expected object, got {type(data).__name__}"
        )

    return data  # type: ignore[return-value]


# Backward compatibility alias
def load_linear_project_state(project_dir: Path) -> ProjectState | None:
    """Load Linear project state. Backward-compatible alias."""
    return load_project_state(project_dir, "linear")


def is_project_initialized(project_dir: Path) -> bool:
    """
    Check if project has been initialized with either Linear or Jira.

    Args:
        project_dir: Directory to check

    Returns:
        True if either .linear_project.json or .jira_project.json exists and is valid
    """
    tracker = detect_tracker(project_dir)
    try:
        state = load_project_state(project_dir, tracker)
        return state is not None and state.get("initialized", False)
    except ValueError:
        print(f"Warning: Corrupted state file in {project_dir}, treating as uninitialized")
        return False


# Backward compatibility alias
def is_linear_initialized(project_dir: Path) -> bool:
    """Check if project is initialized. Backward-compatible alias."""
    return is_project_initialized(project_dir)


def print_session_header(session_num: int, is_initializer: bool) -> None:
    """Print a formatted header for the session."""
    session_type: str = "ORCHESTRATOR (init)" if is_initializer else "ORCHESTRATOR (continue)"

    print("\n" + "=" * 70)
    print(f"  SESSION {session_num}: {session_type}")
    print("=" * 70)
    print()


def print_progress_summary(project_dir: Path) -> None:
    """
    Print a summary of current progress.

    Reads the local state file for cached information. Supports both
    Linear and Jira project state files.
    """
    tracker = detect_tracker(project_dir)
    tracker_name = "Jira" if tracker == "jira" else "Linear"

    try:
        state = load_project_state(project_dir, tracker)
    except ValueError as e:
        print(f"\nProgress: Error loading state - {e}")
        return

    if state is None:
        print(f"\nProgress: {tracker_name} project not yet initialized")
        return

    total: int = state.get("total_issues", 0)

    if tracker == "jira":
        meta_ref: str = state.get("meta_issue_key", "unknown")
        project_key: str = state.get("project_key", "unknown")
        print(f"\nJira Project Status:")
        print(f"  Project key: {project_key}")
        print(f"  Total issues created: {total}")
        print(f"  META issue key: {meta_ref}")
        print(f"  (Check Jira for current Done/In Progress/Todo counts)")
    else:
        meta_ref = state.get("meta_issue_id", "unknown")
        print(f"\nLinear Project Status:")
        print(f"  Total issues created: {total}")
        print(f"  META issue ID: {meta_ref}")
        print(f"  (Check Linear for current Done/In Progress/Todo counts)")
