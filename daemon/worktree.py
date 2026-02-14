"""
Git Worktree Manager
====================

Provides isolated git worktrees for parallel coding workers so they
can operate on different branches without interfering with each other.

Each worker gets its own worktree checkout under a `.worktrees/` directory
inside the project. Ports are allocated from a range to avoid dev server
collisions.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger("worktree")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORKTREE_DIR_NAME = ".worktrees"
PORT_RANGE_START = 3100
PORT_RANGE_END = 3199


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class WorktreeError(Exception):
    """Raised when a worktree operation fails."""


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _run_git(
    args: list[str],
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result."""
    cmd = ["git"] + args
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=check,
            timeout=60,
        )
    except subprocess.CalledProcessError as e:
        raise WorktreeError(
            f"git {' '.join(args)} failed (code {e.returncode}): {e.stderr.strip()}"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise WorktreeError(f"git {' '.join(args)} timed out after 60s") from e


def _sanitize_branch_name(name: str) -> str:
    """Convert a ticket title into a valid git branch name."""
    # Lowercase, replace non-alphanumeric with hyphens, collapse multiples
    sanitized = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    # Truncate to reasonable length
    return sanitized[:60]


# ---------------------------------------------------------------------------
# Worktree Manager
# ---------------------------------------------------------------------------


class WorktreeManager:
    """Manages git worktrees for parallel worker isolation.

    Each worker gets a separate worktree checkout so multiple coding agents
    can work on different branches simultaneously without conflicts.
    """

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self._worktrees_base = project_dir / WORKTREE_DIR_NAME
        self._allocated_ports: set[int] = set()
        self._worker_worktrees: dict[str, Path] = {}

    def get_branch_for_ticket(self, ticket_key: str, ticket_title: str) -> str:
        """Generate a branch name for a ticket.

        Args:
            ticket_key: The ticket identifier (e.g. "ENG-123")
            ticket_title: Human-readable ticket title

        Returns:
            A git-safe branch name like "eng-123-fix-login-flow"
        """
        slug = _sanitize_branch_name(ticket_title)
        key_slug = ticket_key.lower().replace(" ", "-")
        return f"{key_slug}-{slug}" if slug else key_slug

    def create_worktree(self, worker_id: str, branch_name: str) -> Path:
        """Create a git worktree for a worker.

        Args:
            worker_id: Unique worker identifier
            branch_name: Branch to create/checkout in the worktree

        Returns:
            Path to the worktree directory

        Raises:
            WorktreeError: If worktree creation fails
        """
        self._worktrees_base.mkdir(parents=True, exist_ok=True)
        worktree_path = self._worktrees_base / worker_id

        # Clean up if a stale worktree exists for this worker
        if worktree_path.exists():
            self.remove_worktree(worker_id)

        # Ensure the branch exists (create from HEAD if not)
        result = _run_git(
            ["branch", "--list", branch_name],
            cwd=self.project_dir,
        )
        if branch_name not in result.stdout:
            _run_git(
                ["branch", branch_name],
                cwd=self.project_dir,
            )

        # Create the worktree
        _run_git(
            ["worktree", "add", str(worktree_path), branch_name],
            cwd=self.project_dir,
        )

        self._worker_worktrees[worker_id] = worktree_path
        logger.info(
            "Created worktree for %s at %s (branch=%s)",
            worker_id,
            worktree_path,
            branch_name,
        )
        return worktree_path

    def remove_worktree(self, worker_id: str) -> None:
        """Remove a worker's worktree.

        Args:
            worker_id: The worker whose worktree to remove

        Raises:
            WorktreeError: If removal fails
        """
        worktree_path = self._worker_worktrees.pop(worker_id, None)
        if worktree_path is None:
            worktree_path = self._worktrees_base / worker_id

        if worktree_path.exists():
            _run_git(
                ["worktree", "remove", str(worktree_path), "--force"],
                cwd=self.project_dir,
            )
            logger.info("Removed worktree for %s", worker_id)

    def merge_to_main(self, branch_name: str) -> bool:
        """Merge a branch back to main.

        Args:
            branch_name: The branch to merge

        Returns:
            True if merged successfully, False if there was a conflict.
        """
        try:
            _run_git(
                ["merge", "--no-ff", branch_name, "-m", f"Merge {branch_name}"],
                cwd=self.project_dir,
            )
            logger.info("Merged %s to main", branch_name)
            return True
        except WorktreeError as e:
            if "conflict" in str(e).lower() or "CONFLICT" in str(e):
                # Abort the failed merge
                _run_git(["merge", "--abort"], cwd=self.project_dir, check=False)
                logger.warning("Merge conflict on %s — aborting", branch_name)
                return False
            raise

    def allocate_port(self) -> int:
        """Allocate a free port from the range for a dev server.

        Returns:
            An allocated port number

        Raises:
            WorktreeError: If no ports are available
        """
        for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
            if port not in self._allocated_ports:
                self._allocated_ports.add(port)
                return port
        raise WorktreeError(f"No free ports in range {PORT_RANGE_START}-{PORT_RANGE_END}")

    def release_port(self, port: int) -> None:
        """Release a previously allocated port."""
        self._allocated_ports.discard(port)

    def cleanup_stale_worktrees(self) -> int:
        """Remove worktrees that no longer have active workers.

        Returns:
            Number of stale worktrees removed
        """
        cleaned = 0
        if not self._worktrees_base.exists():
            return 0

        # Get list of registered worktrees from git
        _run_git(
            ["worktree", "list", "--porcelain"],
            cwd=self.project_dir,
            check=False,
        )

        active_worker_ids = set(self._worker_worktrees.keys())
        worktrees_dir = self._worktrees_base

        for child in worktrees_dir.iterdir():
            if child.is_dir() and child.name not in active_worker_ids:
                try:
                    _run_git(
                        ["worktree", "remove", str(child), "--force"],
                        cwd=self.project_dir,
                    )
                    cleaned += 1
                    logger.info("Cleaned stale worktree: %s", child.name)
                except WorktreeError as e:
                    logger.warning("Failed to clean worktree %s: %s", child.name, e)

        return cleaned
