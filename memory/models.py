"""Shared memory data models.

Defines the MemoryEntry structure used to capture cross-tenant patterns,
anti-patterns, architectural decisions, and error resolutions.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class MemoryCategory(str, Enum):
    """Categories for shared memory entries."""

    PATTERN = "pattern"                  # Successful implementation patterns
    ANTI_PATTERN = "anti_pattern"        # Approaches that failed or caused issues
    ARCHITECTURE = "architecture"        # Architectural decisions and trade-offs
    TOOL_USAGE = "tool_usage"            # Effective tool/framework usage patterns
    ERROR_RESOLUTION = "error_resolution"  # Error diagnosis and fix patterns
    SPEC_TEMPLATE = "spec_template"      # Reusable spec structures and templates
    INTEGRATION = "integration"          # External service integration patterns

    def __str__(self) -> str:
        return self.value


@dataclass
class MemoryEntry:
    """A single cross-tenant memory entry.

    Source tenant identity is stored for platform team auditing but is
    never exposed through tenant-facing APIs.

    Attributes:
        entry_id: Unique identifier for this entry.
        category: Classification of the pattern.
        title: Short descriptive title.
        content: Detailed pattern description and context.
        source_tenant_id: Tenant where the pattern was observed (private).
        confidence: Confidence score 0.0-1.0 (higher = more validated).
        usage_count: Number of times this pattern has been applied.
        tags: Searchable tags for categorization.
        related_entries: IDs of related memory entries.
        created_at: ISO timestamp of creation.
        updated_at: ISO timestamp of last update.
    """

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: str = MemoryCategory.PATTERN
    title: str = ""
    content: str = ""
    source_tenant_id: str = ""  # PRIVATE — never exposed to tenants
    confidence: float = 0.5
    usage_count: int = 0
    tags: List[str] = field(default_factory=list)
    related_entries: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Full serialization including private fields (platform team only)."""
        return {
            "entry_id": self.entry_id,
            "category": self.category,
            "title": self.title,
            "content": self.content,
            "source_tenant_id": self.source_tenant_id,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "tags": self.tags,
            "related_entries": self.related_entries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def public_dict(self) -> Dict[str, Any]:
        """Tenant-safe serialization (excludes source_tenant_id)."""
        d = self.to_dict()
        d.pop("source_tenant_id", None)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Deserialize from dictionary."""
        return cls(
            entry_id=data.get("entry_id", str(uuid.uuid4())),
            category=data.get("category", MemoryCategory.PATTERN),
            title=data.get("title", ""),
            content=data.get("content", ""),
            source_tenant_id=data.get("source_tenant_id", ""),
            confidence=data.get("confidence", 0.5),
            usage_count=data.get("usage_count", 0),
            tags=data.get("tags", []),
            related_entries=data.get("related_entries", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
