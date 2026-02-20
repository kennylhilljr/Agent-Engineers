"""KnowledgeBaseAgent — RAG query interface for all agents (AI-253).

Provides project-scoped context retrieval with tier gating.
Available for Team tier and above.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

from knowledge_base.embeddings import EmbeddingProvider
from knowledge_base.vector_store import VectorStore


# Tiers that may use the Knowledge Base feature
KB_TIERS: List[str] = ["team", "organization", "fleet", "enterprise"]


class KnowledgeBaseAgent:
    """RAG-based knowledge retrieval agent.

    Args:
        vector_store: Shared VectorStore instance.
        embedder:     EmbeddingProvider for query embedding.
        tier:         Billing tier of the requesting org (default 'team').
    """

    KB_TIERS: List[str] = KB_TIERS

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: EmbeddingProvider,
        tier: str = "team",
    ) -> None:
        self.vector_store = vector_store
        self.embedder = embedder
        self.tier = tier

    # ------------------------------------------------------------------ #
    # Tier gate
    # ------------------------------------------------------------------ #

    def is_available_for_tier(self, tier: str) -> bool:
        """Return True if *tier* may use the Knowledge Base feature.

        Available for Team, Organization, Fleet, and Enterprise tiers.

        Args:
            tier: Billing tier string (case-insensitive).

        Returns:
            True when the feature is available for *tier*.
        """
        if not tier:
            return False
        return tier.lower() in self.KB_TIERS

    # ------------------------------------------------------------------ #
    # Core query
    # ------------------------------------------------------------------ #

    def query(
        self,
        question: str,
        project_id: str,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Retrieve the most relevant context chunks for *question*.

        Args:
            question:   Natural-language query.
            project_id: Project namespace to search within.
            top_k:      Number of chunks to return (default 5).

        Returns:
            Dict with keys:
              - ``chunks``        (list[dict]): matched chunk objects
              - ``sources``       (list[str]):  doc IDs of matched chunks
              - ``query_time_ms`` (float):      query latency in ms
        """
        t0 = time.perf_counter()
        query_embedding = self.embedder.embed(question)
        results = self.vector_store.search(project_id, query_embedding, top_k=top_k)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        chunks = [r["chunk"] for r in results]
        sources = list({r["doc_id"] for r in results})

        return {
            "chunks": chunks,
            "sources": sources,
            "query_time_ms": round(elapsed_ms, 2),
        }

    # ------------------------------------------------------------------ #
    # Agent-specific formatted helpers
    # ------------------------------------------------------------------ #

    def query_for_coding_agent(
        self,
        task_description: str,
        project_id: str,
    ) -> str:
        """Return formatted KB context for the Coding Agent.

        Called before implementation to surface relevant patterns.

        Args:
            task_description: Description of the coding task.
            project_id:       Project namespace.

        Returns:
            Formatted string with relevant context sections.
        """
        result = self.query(task_description, project_id, top_k=5)
        if not result["chunks"]:
            return "No relevant project context found."

        lines = [
            "### Relevant Project Context (Knowledge Base)",
            "",
        ]
        for i, chunk in enumerate(result["chunks"], start=1):
            lines.append(f"**Context {i}:**")
            lines.append(chunk["text"].strip())
            lines.append("")
        lines.append(
            f"*Sources: {', '.join(result['sources'])} | "
            f"Query time: {result['query_time_ms']} ms*"
        )
        return "\n".join(lines)

    def query_for_pr_reviewer(
        self,
        pr_description: str,
        project_id: str,
    ) -> str:
        """Return formatted KB context for the PR Reviewer Agent.

        Called to surface past issues or patterns related to the PR.

        Args:
            pr_description: PR title/description text.
            project_id:     Project namespace.

        Returns:
            Formatted string with relevant context sections.
        """
        result = self.query(pr_description, project_id, top_k=5)
        if not result["chunks"]:
            return "No relevant historical context found for this PR."

        lines = [
            "### Historical Context (Knowledge Base)",
            "",
        ]
        for i, chunk in enumerate(result["chunks"], start=1):
            lines.append(f"**Historical Context {i}:**")
            lines.append(chunk["text"].strip())
            lines.append("")
        lines.append(
            f"*Sources: {', '.join(result['sources'])} | "
            f"Query time: {result['query_time_ms']} ms*"
        )
        return "\n".join(lines)
