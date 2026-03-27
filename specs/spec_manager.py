"""Spec lifecycle manager.

Manages the creation, versioning, and submission of application specifications
that drive agent work. Each tenant's specs are stored in their isolated
data directory.

Spec lifecycle:
    draft → submitted → processing → completed
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Spec:
    """An application specification that drives agent work.

    Attributes:
        spec_id: Unique identifier.
        tenant_id: Owning tenant.
        name: Human-readable spec name.
        description: Brief description of what this spec builds.
        content: Full spec content (markdown/structured text).
        context: Additional context (URLs, file references, constraints).
        version: Auto-incrementing version number.
        status: Lifecycle status (draft, submitted, processing, completed).
        author_id: User who created/last edited the spec.
        project_id: Linked project once submitted and assigned.
        recommendations_applied: IDs of shared memory entries used.
        created_at: ISO timestamp of creation.
        updated_at: ISO timestamp of last update.
    """

    spec_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    content: str = ""
    context: str = ""
    version: int = 1
    status: str = "draft"  # draft | submitted | processing | completed
    author_id: str = ""
    project_id: str = ""
    recommendations_applied: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "context": self.context,
            "version": self.version,
            "status": self.status,
            "author_id": self.author_id,
            "project_id": self.project_id,
            "recommendations_applied": self.recommendations_applied,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Spec":
        return cls(
            spec_id=data.get("spec_id", str(uuid.uuid4())),
            tenant_id=data.get("tenant_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            content=data.get("content", ""),
            context=data.get("context", ""),
            version=data.get("version", 1),
            status=data.get("status", "draft"),
            author_id=data.get("author_id", ""),
            project_id=data.get("project_id", ""),
            recommendations_applied=data.get("recommendations_applied", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SpecError(Exception):
    """Base exception for spec operations."""


class SpecNotFoundError(SpecError):
    """Raised when a spec ID does not match any known spec."""


class SpecStatusError(SpecError):
    """Raised when an operation is invalid for the spec's current status."""


# ---------------------------------------------------------------------------
# Spec Manager
# ---------------------------------------------------------------------------


class SpecManager:
    """Manages spec lifecycle for a single tenant.

    Each tenant gets an isolated SpecManager that reads/writes to their
    own data directory.

    Args:
        tenant_id: Tenant this manager serves.
        data_dir: Tenant's data directory (e.g., ``data/tenants/{id}``).
    """

    def __init__(self, tenant_id: str, data_dir: str) -> None:
        self._tenant_id = tenant_id
        self._specs_dir = Path(data_dir) / "specs"
        self._specs_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._specs_dir / "specs_index.json"
        self._specs: Dict[str, Spec] = {}
        self._load()

    def _load(self) -> None:
        if self._index_path.exists():
            try:
                with open(self._index_path, "r") as f:
                    raw = json.load(f)
                for sid, data in raw.items():
                    self._specs[sid] = Spec.from_dict(data)
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Failed to load spec index: %s", exc)

    def _save(self) -> None:
        with open(self._index_path, "w") as f:
            json.dump(
                {sid: s.to_dict() for sid, s in self._specs.items()},
                f,
                indent=2,
            )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_spec(
        self,
        name: str,
        content: str,
        author_id: str,
        description: str = "",
        context: str = "",
    ) -> Spec:
        """Create a new spec in draft status.

        Args:
            name: Spec name.
            content: Full spec content.
            author_id: User creating the spec.
            description: Brief description.
            context: Additional context.

        Returns:
            The created Spec.
        """
        now = datetime.now(timezone.utc).isoformat()
        spec = Spec(
            tenant_id=self._tenant_id,
            name=name,
            description=description,
            content=content,
            context=context,
            version=1,
            status="draft",
            author_id=author_id,
            created_at=now,
            updated_at=now,
        )
        self._specs[spec.spec_id] = spec

        # Also write the spec content to a standalone file for agent consumption
        self._write_spec_file(spec)
        self._save()

        logger.info("Created spec %s: %s (tenant: %s)", spec.spec_id, name, self._tenant_id)
        return spec

    def get_spec(self, spec_id: str) -> Spec:
        """Retrieve a spec by ID.

        Raises:
            SpecNotFoundError: If spec doesn't exist.
        """
        if spec_id not in self._specs:
            raise SpecNotFoundError(f"Spec not found: {spec_id}")
        return self._specs[spec_id]

    def update_spec(
        self,
        spec_id: str,
        content: str,
        author_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Spec:
        """Update a spec, creating a new version.

        Only drafts can be updated. Submitted/processing specs must be
        reverted to draft first.

        Args:
            spec_id: Spec to update.
            content: New spec content.
            author_id: User making the edit.

        Returns:
            The updated Spec with incremented version.

        Raises:
            SpecNotFoundError: If spec doesn't exist.
            SpecStatusError: If spec is not in draft status.
        """
        spec = self.get_spec(spec_id)
        if spec.status not in ("draft",):
            raise SpecStatusError(
                f"Cannot edit spec in '{spec.status}' status. Revert to draft first."
            )

        spec.content = content
        spec.version += 1
        spec.author_id = author_id
        spec.updated_at = datetime.now(timezone.utc).isoformat()

        if name is not None:
            spec.name = name
        if description is not None:
            spec.description = description
        if context is not None:
            spec.context = context

        self._write_spec_file(spec)
        self._save()
        return spec

    def submit_spec(self, spec_id: str) -> Spec:
        """Submit a spec for agent processing.

        Transitions status from draft → submitted. A downstream ticket
        will be created and routed to the tenant's agent pool.

        Args:
            spec_id: Spec to submit.

        Returns:
            The submitted Spec.

        Raises:
            SpecNotFoundError: If spec doesn't exist.
            SpecStatusError: If spec is not in draft status.
        """
        spec = self.get_spec(spec_id)
        if spec.status != "draft":
            raise SpecStatusError(f"Only draft specs can be submitted (current: {spec.status})")

        if not spec.content.strip():
            raise SpecStatusError("Cannot submit an empty spec")

        spec.status = "submitted"
        spec.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()

        logger.info("Submitted spec %s for processing (tenant: %s)", spec_id, self._tenant_id)
        return spec

    def set_processing(self, spec_id: str, project_id: str = "") -> Spec:
        """Mark a spec as being actively processed by agents.

        Args:
            spec_id: Spec being processed.
            project_id: Generated project ID (if created).

        Returns:
            The updated Spec.
        """
        spec = self.get_spec(spec_id)
        spec.status = "processing"
        if project_id:
            spec.project_id = project_id
        spec.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return spec

    def set_completed(self, spec_id: str, project_id: str = "") -> Spec:
        """Mark a spec as completed.

        Args:
            spec_id: Completed spec.
            project_id: Final project ID.

        Returns:
            The updated Spec.
        """
        spec = self.get_spec(spec_id)
        spec.status = "completed"
        if project_id:
            spec.project_id = project_id
        spec.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return spec

    def revert_to_draft(self, spec_id: str) -> Spec:
        """Revert a spec back to draft status for editing."""
        spec = self.get_spec(spec_id)
        if spec.status == "processing":
            raise SpecStatusError("Cannot revert a spec that is actively being processed")
        spec.status = "draft"
        spec.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return spec

    def list_specs(self, status: Optional[str] = None) -> List[Spec]:
        """List all specs, optionally filtered by status."""
        specs = list(self._specs.values())
        if status:
            specs = [s for s in specs if s.status == status]
        return sorted(specs, key=lambda s: s.updated_at, reverse=True)

    def delete_spec(self, spec_id: str) -> None:
        """Delete a draft spec.

        Raises:
            SpecNotFoundError: If spec doesn't exist.
            SpecStatusError: If spec is not in draft status.
        """
        spec = self.get_spec(spec_id)
        if spec.status != "draft":
            raise SpecStatusError("Only draft specs can be deleted")

        # Remove spec file
        spec_file = self._specs_dir / f"{spec_id}.txt"
        if spec_file.exists():
            spec_file.unlink()

        del self._specs[spec_id]
        self._save()

    def apply_recommendation(self, spec_id: str, memory_entry_id: str) -> None:
        """Track that a shared memory recommendation was applied to a spec."""
        spec = self.get_spec(spec_id)
        if memory_entry_id not in spec.recommendations_applied:
            spec.recommendations_applied.append(memory_entry_id)
            spec.updated_at = datetime.now(timezone.utc).isoformat()
            self._save()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _write_spec_file(self, spec: Spec) -> None:
        """Write spec content to a standalone text file for agent consumption."""
        spec_file = self._specs_dir / f"{spec.spec_id}.txt"
        with open(spec_file, "w") as f:
            f.write(f"# {spec.name}\n\n")
            if spec.description:
                f.write(f"{spec.description}\n\n")
            f.write(f"---\n\n")
            f.write(spec.content)
            if spec.context:
                f.write(f"\n\n---\n\n## Additional Context\n\n{spec.context}")

    def get_spec_file_path(self, spec_id: str) -> Path:
        """Return the path to the spec's text file."""
        return self._specs_dir / f"{spec_id}.txt"
