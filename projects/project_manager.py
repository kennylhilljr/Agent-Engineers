"""Project Manager — multi-project support for Agent-Engineers dashboard.

Implements AI-225: Multi-Project Support - Project Switcher and Isolation.

Data Model:
    Project: id (uuid), name, git_repo_url, linear_project_id, directory, created_at
    Storage: .agent_projects.json in the base directory

Tier Limits:
    Explorer: 1  | Builder: 1  | Team: 5  | Scale: 25
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier project-count limits
# ---------------------------------------------------------------------------

TIER_PROJECT_LIMITS: Dict[str, int] = {
    "explorer": 1,
    "builder": 1,
    "team": 5,
    "scale": 25,
}

_DEFAULT_MAX_PROJECTS = 5  # fallback when tier is unknown

# Storage file name
_PROJECTS_FILE = ".agent_projects.json"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TierLimitError(Exception):
    """Raised when a project-count tier limit would be exceeded."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Project:
    """Represents a single Agent-Engineers project."""

    id: str
    name: str
    directory: str
    git_repo_url: str = ""
    linear_project_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary (JSON-safe)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        """Deserialise from a plain dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            directory=data.get("directory", ""),
            git_repo_url=data.get("git_repo_url", ""),
            linear_project_id=data.get("linear_project_id", ""),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


# ---------------------------------------------------------------------------
# ProjectManager
# ---------------------------------------------------------------------------


class ProjectManager:
    """Manage multiple Agent-Engineers projects.

    Projects are persisted to ``<base_dir>/.agent_projects.json``.
    The active project is tracked in-memory only (not persisted) so it
    resets to ``None`` when the process restarts — the caller is expected
    to call ``get_active_project()`` and activate a project on startup.

    Args:
        base_dir: Directory where ``.agent_projects.json`` is stored.
                  Defaults to ``Path.cwd()``.
        tier: Tier name (explorer/builder/team/scale) for limit enforcement.
              Defaults to ``"team"`` (5 projects).
        max_projects: Override max project count regardless of tier.
                      If provided, takes priority over *tier*.
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        tier: str = "team",
        max_projects: Optional[int] = None,
    ) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else Path.cwd()
        self._projects_file = self.base_dir / _PROJECTS_FILE

        # Determine limit
        if max_projects is not None:
            self._max_projects = max_projects
        else:
            self._max_projects = TIER_PROJECT_LIMITS.get(
                tier.lower(), _DEFAULT_MAX_PROJECTS
            )

        self._tier = tier

        # In-memory active project tracking
        self._active_project_id: Optional[str] = None

        # Load persisted projects
        self._projects: Dict[str, Project] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load projects from the JSON file (silently skips if missing)."""
        if not self._projects_file.exists():
            return
        try:
            raw = json.loads(self._projects_file.read_text(encoding="utf-8"))
            projects_data = raw.get("projects", [])
            self._projects = {
                p["id"]: Project.from_dict(p) for p in projects_data
            }
            logger.debug(
                "Loaded %d project(s) from %s",
                len(self._projects),
                self._projects_file,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to load %s: %s — starting with empty project list",
                self._projects_file,
                exc,
            )
            self._projects = {}

    def _save(self) -> None:
        """Persist projects to the JSON file."""
        data = {
            "projects": [p.to_dict() for p in self._projects.values()],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._projects_file.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        logger.debug("Saved %d project(s) to %s", len(self._projects), self._projects_file)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_project(
        self,
        name: str,
        directory: str = "",
        git_repo_url: str = "",
        linear_project_id: str = "",
    ) -> Project:
        """Create a new project and persist it.

        Args:
            name: Human-readable project name (must be non-empty).
            directory: Filesystem path to the project directory.
            git_repo_url: Optional git repository URL.
            linear_project_id: Optional Linear project ID.

        Returns:
            The newly created :class:`Project`.

        Raises:
            ValueError: If *name* is empty.
            TierLimitError: If the tier project-count limit would be exceeded.
        """
        name = name.strip()
        if not name:
            raise ValueError("Project name must not be empty")

        if len(self._projects) >= self._max_projects:
            raise TierLimitError(
                f"Tier '{self._tier}' allows at most {self._max_projects} project(s). "
                f"Delete an existing project or upgrade your tier."
            )

        project = Project(
            id=str(uuid.uuid4()),
            name=name,
            directory=directory,
            git_repo_url=git_repo_url,
            linear_project_id=linear_project_id,
        )
        self._projects[project.id] = project
        self._save()
        logger.info("Created project '%s' (id=%s)", name, project.id)
        return project

    def delete_project(self, project_id: str) -> bool:
        """Delete a project by ID.

        If the deleted project was active, the active project is cleared.

        Args:
            project_id: UUID string of the project to delete.

        Returns:
            ``True`` if the project was found and deleted, ``False`` otherwise.
        """
        if project_id not in self._projects:
            return False
        name = self._projects[project_id].name
        del self._projects[project_id]
        if self._active_project_id == project_id:
            self._active_project_id = None
        self._save()
        logger.info("Deleted project '%s' (id=%s)", name, project_id)
        return True

    def list_projects(self) -> List[Project]:
        """Return all projects sorted by creation date (oldest first)."""
        return sorted(
            self._projects.values(),
            key=lambda p: p.created_at,
        )

    def switch_project(self, project_id: str) -> Project:
        """Set the active project.

        Args:
            project_id: UUID string of the project to activate.

        Returns:
            The activated :class:`Project`.

        Raises:
            KeyError: If *project_id* does not exist.
        """
        if project_id not in self._projects:
            raise KeyError(f"Project with id='{project_id}' not found")
        self._active_project_id = project_id
        project = self._projects[project_id]
        logger.info("Switched active project to '%s' (id=%s)", project.name, project_id)
        return project

    def get_active_project(self) -> Optional[Project]:
        """Return the currently active project, or ``None`` if not set."""
        if self._active_project_id is None:
            return None
        return self._projects.get(self._active_project_id)

    def get_project(self, project_id: str) -> Optional[Project]:
        """Return a project by ID, or ``None`` if not found."""
        return self._projects.get(project_id)

    @property
    def max_projects(self) -> int:
        """Maximum number of projects allowed under the current tier."""
        return self._max_projects

    @property
    def tier(self) -> str:
        """Current tier name."""
        return self._tier
