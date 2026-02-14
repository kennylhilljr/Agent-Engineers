"""
Progress Tracking Utilities
===========================

Functions for tracking and displaying progress of the autonomous coding agent.
Progress is tracked via Linear issues, with local state cached in
.linear_project.json.

Includes:
- Project initialization state
- Verification status tracking (Proposal 3)
- Ticket locking for parallel workers (Proposal 4)
"""

import json
import time
from pathlib import Path
from typing import Literal, TypedDict

# Local marker file to track project initialization
LINEAR_PROJECT_MARKER: str = ".linear_project.json"

# Lock file directory for parallel ticket processing
LOCKS_DIR_NAME: str = ".locks"

# Lock expiry in seconds (stale locks are auto-released)
LOCK_TTL: int = 600


class ProjectState(TypedDict, total=False):
    """Structure of the project state file."""

    initialized: bool
    created_at: str
    team_id: str
    team_key: str
    project_id: str
    project_name: str
    project_slug: str
    meta_issue_id: str
    total_issues: int
    notes: str
    # Dedup tracking: list of {"key": "AI-42", "title": "Feature Name"} dicts
    issues: list[dict[str, str]]
    # Verification tracking (Proposal 3)
    last_verification_status: str  # "pass", "fail", or ""
    last_verification_ticket: str  # key of the ticket that was verified
    tickets_since_verification: int  # count since last full verification


def load_project_state(project_dir: Path) -> ProjectState | None:
    """
    Load the project state from the marker file.

    Args:
        project_dir: Directory containing the state file

    Returns:
        Project state dict or None if not initialized

    Raises:
        ValueError: If the state file exists but is corrupted or malformed
    """
    marker_file = project_dir / LINEAR_PROJECT_MARKER

    if not marker_file.exists():
        return None

    try:
        with open(marker_file) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Corrupted state file at {marker_file}: {e}\n"
            f"Delete the file to restart initialization, or restore from backup."
        ) from e
    except OSError as e:
        raise ValueError(
            f"Cannot read state file at {marker_file}: {e}\nCheck file permissions."
        ) from e

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid state file at {marker_file}: expected object, got {type(data).__name__}"
        )

    return data  # type: ignore[return-value]


# Backward compatibility alias
def load_linear_project_state(project_dir: Path) -> ProjectState | None:
    """Load Linear project state. Backward-compatible alias."""
    return load_project_state(project_dir)


def is_project_initialized(project_dir: Path) -> bool:
    """
    Check if project has been initialized with Linear.

    Args:
        project_dir: Directory to check

    Returns:
        True if .linear_project.json exists and is valid
    """
    try:
        state = load_project_state(project_dir)
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

    Reads the local state file for cached information.
    """
    try:
        state = load_project_state(project_dir)
    except ValueError as e:
        print(f"\nProgress: Error loading state - {e}")
        return

    if state is None:
        print("\nProgress: Linear project not yet initialized")
        return

    total: int = state.get("total_issues", 0)
    meta_ref: str = state.get("meta_issue_id", "unknown")
    print("\nLinear Project Status:")
    print(f"  Total issues created: {total}")
    print(f"  META issue ID: {meta_ref}")
    print("  (Check Linear for current Done/In Progress/Todo counts)")


# ---------------------------------------------------------------------------
# Verification Status Tracking (Proposal 3)
# ---------------------------------------------------------------------------

VerificationStatus = Literal["pass", "fail", ""]

# Run a full verification every N tickets even if last was passing
VERIFICATION_INTERVAL: int = 3


def should_run_verification(project_dir: Path) -> bool:
    """Determine if a full verification test should run.

    Verification is skipped when:
    - Last verification passed, AND
    - No errors since then, AND
    - Fewer than VERIFICATION_INTERVAL tickets have been completed since
      the last verification.

    Returns:
        True if verification should run, False if it can be skipped.
    """
    state = load_project_state(project_dir)
    if state is None:
        return True  # No state = first run, always verify

    last_status = state.get("last_verification_status", "")
    tickets_since = state.get("tickets_since_verification", 0)

    # Always verify if last verification failed or unknown
    if last_status != "pass":
        return True

    # Verify every VERIFICATION_INTERVAL tickets
    if tickets_since >= VERIFICATION_INTERVAL:
        return True

    return False


def update_verification_status(
    project_dir: Path,
    status: VerificationStatus,
    ticket_key: str = "",
) -> None:
    """Record the result of a verification test.

    Args:
        project_dir: Project directory
        status: "pass" or "fail"
        ticket_key: Key of the ticket context
    """
    state = load_project_state(project_dir)
    if state is None:
        return

    state["last_verification_status"] = status
    state["last_verification_ticket"] = ticket_key
    if status == "pass":
        state["tickets_since_verification"] = 0

    marker = project_dir / LINEAR_PROJECT_MARKER
    marker.write_text(json.dumps(state, indent=2))


def increment_tickets_since_verification(project_dir: Path) -> None:
    """Increment the counter of tickets completed since last verification."""
    state = load_project_state(project_dir)
    if state is None:
        return

    state["tickets_since_verification"] = state.get("tickets_since_verification", 0) + 1
    marker = project_dir / LINEAR_PROJECT_MARKER
    marker.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# Ticket Locking (Proposal 4)
# ---------------------------------------------------------------------------


class TicketLock(TypedDict):
    """A ticket lock entry."""

    ticket_key: str
    worker_id: str
    acquired_at: float  # time.time()
    ttl: int


def _locks_dir(project_dir: Path) -> Path:
    """Return the locks directory, creating it if needed."""
    d = project_dir / LOCKS_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def acquire_ticket_lock(
    project_dir: Path,
    ticket_key: str,
    worker_id: str,
    ttl: int = LOCK_TTL,
) -> bool:
    """Try to acquire a lock on a ticket for a specific worker.

    Args:
        project_dir: Project directory
        ticket_key: Ticket identifier
        worker_id: Worker claiming the lock
        ttl: Lock time-to-live in seconds

    Returns:
        True if lock was acquired, False if ticket is already locked.
    """
    locks = _locks_dir(project_dir)
    lock_file = locks / f"{ticket_key}.lock"

    # Check for existing lock
    if lock_file.exists():
        try:
            data = json.loads(lock_file.read_text())
            elapsed = time.time() - data.get("acquired_at", 0)
            if elapsed < data.get("ttl", LOCK_TTL):
                return False  # Lock is still held
            # Lock expired — fall through to acquire
        except (json.JSONDecodeError, KeyError):
            pass  # Corrupted lock — overwrite

    lock_data = TicketLock(
        ticket_key=ticket_key,
        worker_id=worker_id,
        acquired_at=time.time(),
        ttl=ttl,
    )
    lock_file.write_text(json.dumps(lock_data, indent=2))
    return True


def release_ticket_lock(project_dir: Path, ticket_key: str) -> None:
    """Release a ticket lock."""
    locks = _locks_dir(project_dir)
    lock_file = locks / f"{ticket_key}.lock"
    if lock_file.exists():
        lock_file.unlink()


def get_locked_tickets(project_dir: Path) -> list[str]:
    """Return list of currently locked ticket keys."""
    locks = _locks_dir(project_dir)
    if not locks.exists():
        return []

    locked: list[str] = []
    for lock_file in locks.glob("*.lock"):
        try:
            data = json.loads(lock_file.read_text())
            elapsed = time.time() - data.get("acquired_at", 0)
            if elapsed < data.get("ttl", LOCK_TTL):
                locked.append(data["ticket_key"])
            else:
                # Expired — clean up
                lock_file.unlink()
        except (json.JSONDecodeError, KeyError):
            lock_file.unlink()  # Corrupted

    return locked


def cleanup_stale_locks(project_dir: Path) -> int:
    """Remove expired lock files. Returns count of removed locks."""
    locks = _locks_dir(project_dir)
    if not locks.exists():
        return 0

    cleaned = 0
    for lock_file in locks.glob("*.lock"):
        try:
            data = json.loads(lock_file.read_text())
            elapsed = time.time() - data.get("acquired_at", 0)
            if elapsed >= data.get("ttl", LOCK_TTL):
                lock_file.unlink()
                cleaned += 1
        except (json.JSONDecodeError, KeyError):
            lock_file.unlink()
            cleaned += 1

    return cleaned
