"""Cross-tenant shared memory store.

Persists and retrieves pattern entries that capture learnings across all tenant
builds. The store is append-friendly and supports keyword-based search with
category filtering.

Privacy invariant: ``source_tenant_id`` is persisted but NEVER returned by
any method that serves tenant-facing API responses. Use ``entry.public_dict()``
for tenant-visible output.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from memory.models import MemoryCategory, MemoryEntry

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = os.path.join("data", "shared_memory.json")
MAX_ENTRIES = 50_000  # cap to prevent unbounded growth


class SharedMemoryStore:
    """Cross-tenant memory store that captures patterns from all builds.

    Args:
        store_path: Path to the JSON persistence file.
    """

    def __init__(self, store_path: str = DEFAULT_STORE_PATH) -> None:
        self._store_path = store_path
        self._entries: Dict[str, MemoryEntry] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if os.path.exists(self._store_path):
            try:
                with open(self._store_path, "r") as f:
                    raw = json.load(f)
                for eid, data in raw.items():
                    self._entries[eid] = MemoryEntry.from_dict(data)
                logger.info(
                    "Loaded %d shared memory entries from %s",
                    len(self._entries),
                    self._store_path,
                )
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Failed to load shared memory: %s", exc)
                self._entries = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._store_path) or ".", exist_ok=True)
        with open(self._store_path, "w") as f:
            json.dump(
                {eid: e.to_dict() for eid, e in self._entries.items()},
                f,
                indent=2,
            )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def record_pattern(self, entry: MemoryEntry) -> MemoryEntry:
        """Record a new pattern entry.

        Args:
            entry: The memory entry to store.

        Returns:
            The stored entry with populated metadata.
        """
        now = datetime.now(timezone.utc).isoformat()
        entry.created_at = entry.created_at or now
        entry.updated_at = now

        self._entries[entry.entry_id] = entry
        self._enforce_cap()
        self._save()
        logger.info(
            "Recorded pattern %s: %s [%s]",
            entry.entry_id,
            entry.title,
            entry.category,
        )
        return entry

    def update_entry(self, entry_id: str, updates: Dict) -> Optional[MemoryEntry]:
        """Update fields on an existing entry.

        Returns:
            The updated entry, or None if not found.
        """
        entry = self._entries.get(entry_id)
        if not entry:
            return None

        for key, value in updates.items():
            if hasattr(entry, key) and key not in ("entry_id", "created_at"):
                setattr(entry, key, value)

        entry.updated_at = datetime.now(timezone.utc).isoformat()
        self._entries[entry_id] = entry
        self._save()
        return entry

    def increment_usage(self, entry_id: str) -> None:
        """Increment the usage count when a pattern is applied."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.usage_count += 1
            entry.updated_at = datetime.now(timezone.utc).isoformat()
            self._save()

    def delete_entry(self, entry_id: str) -> bool:
        """Delete a memory entry. Returns True if it existed."""
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._save()
            return True
        return False

    # ------------------------------------------------------------------
    # Read / search operations
    # ------------------------------------------------------------------

    def get_entry(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get a single entry by ID."""
        return self._entries.get(entry_id)

    def search(
        self,
        query: str = "",
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_confidence: float = 0.0,
        limit: int = 20,
    ) -> List[MemoryEntry]:
        """Search memory entries by keyword, category, and tags.

        Args:
            query: Keyword search across title, content, and tags.
            category: Filter by MemoryCategory value.
            tags: Filter entries that have ALL specified tags.
            min_confidence: Minimum confidence threshold.
            limit: Maximum results to return.

        Returns:
            List of matching entries sorted by relevance (usage_count * confidence).
        """
        results = []
        query_lower = query.lower()

        for entry in self._entries.values():
            # Category filter
            if category and entry.category != category:
                continue

            # Confidence filter
            if entry.confidence < min_confidence:
                continue

            # Tag filter (all specified tags must be present)
            if tags and not all(t in entry.tags for t in tags):
                continue

            # Keyword search
            if query_lower:
                searchable = f"{entry.title} {entry.content} {' '.join(entry.tags)}".lower()
                if query_lower not in searchable:
                    continue

            results.append(entry)

        # Sort by relevance: usage_count * confidence, then recency
        results.sort(
            key=lambda e: (e.usage_count * e.confidence, e.updated_at),
            reverse=True,
        )
        return results[:limit]

    def get_recommendations_for_spec(
        self,
        spec_content: str,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """Find relevant patterns for a given spec.

        Extracts keywords from the spec content and searches for matching
        patterns. This powers the spec page recommendation sidebar.

        Args:
            spec_content: The raw spec text to find recommendations for.
            limit: Maximum recommendations to return.

        Returns:
            List of relevant MemoryEntry objects (use .public_dict() for API).
        """
        # Extract meaningful keywords from spec (simple word frequency approach)
        words = spec_content.lower().split()
        # Filter common words and short tokens
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "and",
            "but", "or", "nor", "not", "so", "yet", "both", "either",
            "neither", "each", "every", "all", "any", "few", "more",
            "most", "other", "some", "such", "no", "only", "own", "same",
            "than", "too", "very", "just", "because", "if", "when", "that",
            "this", "these", "those", "it", "its", "i", "we", "you", "they",
            "he", "she", "my", "your", "their", "our", "his", "her",
        }
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]

        # Score each entry by keyword overlap
        scored: List[tuple[float, MemoryEntry]] = []
        for entry in self._entries.values():
            entry_text = f"{entry.title} {entry.content} {' '.join(entry.tags)}".lower()
            hits = sum(1 for kw in keywords if kw in entry_text)
            if hits > 0:
                score = hits * entry.confidence * (1 + entry.usage_count * 0.1)
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def list_entries(
        self,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MemoryEntry]:
        """List entries with optional category filter and pagination."""
        entries = list(self._entries.values())
        if category:
            entries = [e for e in entries if e.category == category]
        entries.sort(key=lambda e: e.updated_at, reverse=True)
        return entries[offset : offset + limit]

    def entry_count(self) -> int:
        """Return total number of entries."""
        return len(self._entries)

    def category_counts(self) -> Dict[str, int]:
        """Return entry counts per category."""
        counts: Dict[str, int] = {}
        for entry in self._entries.values():
            counts[entry.category] = counts.get(entry.category, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _enforce_cap(self) -> None:
        """Remove oldest low-confidence entries if over capacity."""
        if len(self._entries) <= MAX_ENTRIES:
            return
        # Sort by confidence * usage (keep high-value entries)
        sorted_entries = sorted(
            self._entries.values(),
            key=lambda e: e.confidence * (1 + e.usage_count),
        )
        # Remove lowest-value entries to get back under cap
        to_remove = len(self._entries) - MAX_ENTRIES
        for entry in sorted_entries[:to_remove]:
            del self._entries[entry.entry_id]
        logger.info("Evicted %d low-value memory entries", to_remove)


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

_shared_store: Optional[SharedMemoryStore] = None


def get_shared_memory_store(store_path: str = DEFAULT_STORE_PATH) -> SharedMemoryStore:
    """Return the module-level SharedMemoryStore singleton."""
    global _shared_store
    if _shared_store is None:
        _shared_store = SharedMemoryStore(store_path)
    return _shared_store


def reset_shared_memory_store() -> None:
    """Reset the singleton (for testing)."""
    global _shared_store
    _shared_store = None
