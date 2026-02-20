"""Webhook handler for automatic Knowledge Base reindexing (AI-253).

Triggers index updates when PRs are merged or docs are committed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class KBWebhookHandler:
    """Handles inbound webhook events and queues reindex tasks.

    Keeps an internal queue of project IDs that need reindexing.
    The actual reindex is performed asynchronously by calling
    :meth:`get_reindex_queue` and processing the results.
    """

    def __init__(self) -> None:
        # list of project_ids waiting for reindex (preserves insertion order)
        self._reindex_queue: List[str] = []

    # ------------------------------------------------------------------ #
    # Webhook handlers
    # ------------------------------------------------------------------ #

    def handle_pr_merged(self, event: Dict[str, Any], project_id: str) -> None:
        """Trigger reindex when a PR is merged.

        Args:
            event:      GitHub/GitLab webhook payload (not validated here).
            project_id: Project to reindex.
        """
        self._enqueue(project_id)

    def handle_doc_committed(self, event: Dict[str, Any], project_id: str) -> None:
        """Trigger reindex when a documentation file is committed.

        Args:
            event:      Push webhook payload (not validated here).
            project_id: Project to reindex.
        """
        self._enqueue(project_id)

    # ------------------------------------------------------------------ #
    # Queue management
    # ------------------------------------------------------------------ #

    def get_reindex_queue(self) -> List[str]:
        """Return all project IDs currently pending reindex.

        Returns:
            Snapshot of the reindex queue (unordered deduplicated list).
        """
        return list(self._reindex_queue)

    def clear_project(self, project_id: str) -> None:
        """Remove *project_id* from the reindex queue (after processing).

        Args:
            project_id: Project to dequeue.
        """
        self._reindex_queue = [p for p in self._reindex_queue if p != project_id]

    def clear_queue(self) -> None:
        """Empty the entire reindex queue."""
        self._reindex_queue.clear()

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _enqueue(self, project_id: str) -> None:
        """Add *project_id* to queue (deduplicating)."""
        if project_id not in self._reindex_queue:
            self._reindex_queue.append(project_id)
