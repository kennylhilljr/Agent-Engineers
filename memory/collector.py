"""Memory collector — session lifecycle hooks.

Hooks into agent session completion to extract reusable patterns and store
them in the shared memory system. Pattern extraction runs asynchronously
so it never blocks agent work.

The collector analyzes:
    - Successful session outcomes for implementation patterns
    - Error resolutions for diagnostic patterns
    - Architectural decisions for design patterns
    - Tool usage patterns for efficiency improvements
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from memory.models import MemoryCategory, MemoryEntry
from memory.shared_store import SharedMemoryStore, get_shared_memory_store

logger = logging.getLogger(__name__)


@dataclass
class SessionResult:
    """Summary of a completed agent session for pattern extraction.

    Attributes:
        session_id: Unique session identifier.
        tenant_id: Tenant that ran the session.
        agent_type: Type of agent (coding, review, etc.).
        task_description: What the session was asked to do.
        outcome: Success/failure/partial description.
        files_changed: List of files modified during the session.
        tools_used: List of tools invoked.
        errors_encountered: Any errors and their resolutions.
        duration_seconds: How long the session took.
        model_used: Claude model tier used.
    """

    session_id: str = ""
    tenant_id: str = ""
    agent_type: str = ""
    task_description: str = ""
    outcome: str = ""
    files_changed: List[str] = None  # type: ignore[assignment]
    tools_used: List[str] = None  # type: ignore[assignment]
    errors_encountered: List[Dict[str, str]] = None  # type: ignore[assignment]
    duration_seconds: float = 0
    model_used: str = ""

    def __post_init__(self):
        if self.files_changed is None:
            self.files_changed = []
        if self.tools_used is None:
            self.tools_used = []
        if self.errors_encountered is None:
            self.errors_encountered = []


class MemoryCollector:
    """Hooks into agent session lifecycle to extract patterns for shared memory.

    Args:
        store: SharedMemoryStore instance. Uses singleton if not provided.
    """

    def __init__(self, store: Optional[SharedMemoryStore] = None) -> None:
        self._store = store or get_shared_memory_store()

    async def on_session_complete(self, result: SessionResult) -> List[MemoryEntry]:
        """Analyze a completed session and extract reusable patterns.

        This runs asynchronously after session completion. Extracts:
        - Implementation patterns from successful sessions
        - Error resolution patterns from recovered errors
        - Tool usage patterns from efficient sessions

        Args:
            result: Summary of the completed session.

        Returns:
            List of newly created memory entries.
        """
        entries: List[MemoryEntry] = []

        # Extract implementation pattern from successful sessions
        if result.outcome and "success" in result.outcome.lower():
            pattern = self._extract_implementation_pattern(result)
            if pattern:
                self._store.record_pattern(pattern)
                entries.append(pattern)

        # Extract error resolution patterns
        for error in result.errors_encountered:
            if error.get("resolution"):
                resolution = self._extract_error_resolution(result, error)
                if resolution:
                    self._store.record_pattern(resolution)
                    entries.append(resolution)

        # Extract tool usage patterns from efficient sessions
        if result.duration_seconds > 0 and result.tools_used:
            tool_pattern = self._extract_tool_pattern(result)
            if tool_pattern:
                self._store.record_pattern(tool_pattern)
                entries.append(tool_pattern)

        if entries:
            logger.info(
                "Extracted %d patterns from session %s (tenant: %s)",
                len(entries),
                result.session_id,
                result.tenant_id,
            )
        return entries

    async def on_error_resolved(
        self,
        tenant_id: str,
        error: str,
        resolution: str,
        context: str = "",
    ) -> Optional[MemoryEntry]:
        """Record an error resolution pattern.

        Args:
            tenant_id: Tenant where the error occurred.
            error: Error description.
            resolution: How the error was resolved.
            context: Additional context about the error.

        Returns:
            The created memory entry, or None if not significant enough.
        """
        if len(error) < 10 or len(resolution) < 10:
            return None

        entry = MemoryEntry(
            category=MemoryCategory.ERROR_RESOLUTION,
            title=f"Error resolution: {error[:80]}",
            content=f"Error: {error}\n\nResolution: {resolution}\n\nContext: {context}",
            source_tenant_id=tenant_id,
            confidence=0.6,
            tags=_extract_tags(f"{error} {resolution}"),
        )
        self._store.record_pattern(entry)
        return entry

    async def on_architecture_decision(
        self,
        tenant_id: str,
        decision: str,
        rationale: str = "",
        alternatives: str = "",
    ) -> Optional[MemoryEntry]:
        """Record an architectural decision pattern.

        Args:
            tenant_id: Tenant where the decision was made.
            decision: The architectural decision.
            rationale: Why this approach was chosen.
            alternatives: Alternative approaches considered.

        Returns:
            The created memory entry.
        """
        content_parts = [f"Decision: {decision}"]
        if rationale:
            content_parts.append(f"Rationale: {rationale}")
        if alternatives:
            content_parts.append(f"Alternatives considered: {alternatives}")

        entry = MemoryEntry(
            category=MemoryCategory.ARCHITECTURE,
            title=f"Architecture: {decision[:80]}",
            content="\n\n".join(content_parts),
            source_tenant_id=tenant_id,
            confidence=0.7,
            tags=_extract_tags(decision),
        )
        self._store.record_pattern(entry)
        return entry

    # ------------------------------------------------------------------
    # Pattern extraction helpers
    # ------------------------------------------------------------------

    def _extract_implementation_pattern(self, result: SessionResult) -> Optional[MemoryEntry]:
        """Extract an implementation pattern from a successful session."""
        if not result.task_description or len(result.task_description) < 20:
            return None

        content = (
            f"Task: {result.task_description}\n\n"
            f"Agent: {result.agent_type}\n"
            f"Model: {result.model_used}\n"
            f"Files changed: {', '.join(result.files_changed[:10])}\n"
            f"Duration: {result.duration_seconds:.0f}s\n\n"
            f"Outcome: {result.outcome}"
        )

        return MemoryEntry(
            category=MemoryCategory.PATTERN,
            title=f"Implementation: {result.task_description[:80]}",
            content=content,
            source_tenant_id=result.tenant_id,
            confidence=0.5,
            tags=_extract_tags(result.task_description),
        )

    def _extract_error_resolution(
        self,
        result: SessionResult,
        error: Dict[str, str],
    ) -> Optional[MemoryEntry]:
        """Extract an error resolution pattern."""
        error_msg = error.get("error", "")
        resolution = error.get("resolution", "")

        if len(error_msg) < 10 or len(resolution) < 10:
            return None

        return MemoryEntry(
            category=MemoryCategory.ERROR_RESOLUTION,
            title=f"Error fix: {error_msg[:80]}",
            content=(
                f"Error: {error_msg}\n\n"
                f"Resolution: {resolution}\n\n"
                f"Context: {result.agent_type} agent, model {result.model_used}"
            ),
            source_tenant_id=result.tenant_id,
            confidence=0.6,
            tags=_extract_tags(f"{error_msg} {resolution}"),
        )

    def _extract_tool_pattern(self, result: SessionResult) -> Optional[MemoryEntry]:
        """Extract a tool usage pattern from an efficient session."""
        if not result.tools_used or result.duration_seconds > 600:
            return None  # Only record from reasonably fast sessions

        tools_str = ", ".join(sorted(set(result.tools_used)))
        return MemoryEntry(
            category=MemoryCategory.TOOL_USAGE,
            title=f"Tool usage: {result.agent_type} — {tools_str[:60]}",
            content=(
                f"Agent type: {result.agent_type}\n"
                f"Tools used: {tools_str}\n"
                f"Task: {result.task_description[:200]}\n"
                f"Duration: {result.duration_seconds:.0f}s\n"
                f"Files: {len(result.files_changed)} changed"
            ),
            source_tenant_id=result.tenant_id,
            confidence=0.4,
            tags=[result.agent_type] + list(set(result.tools_used))[:5],
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Common tech keywords to extract as tags
_TECH_KEYWORDS = {
    "react", "vue", "angular", "svelte", "nextjs", "fastapi", "django", "flask",
    "express", "node", "typescript", "python", "rust", "go", "java", "kotlin",
    "postgresql", "mysql", "mongodb", "redis", "sqlite", "graphql", "rest",
    "api", "websocket", "docker", "kubernetes", "terraform", "aws", "gcp",
    "azure", "authentication", "authorization", "oauth", "jwt", "csrf",
    "testing", "playwright", "jest", "pytest", "ci", "cd", "deployment",
    "migration", "refactor", "performance", "caching", "security",
}


def _extract_tags(text: str) -> List[str]:
    """Extract relevant technical tags from text."""
    words = set(text.lower().split())
    return sorted(words & _TECH_KEYWORDS)[:8]
