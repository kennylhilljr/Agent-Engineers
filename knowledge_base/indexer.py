"""Document indexer for the Knowledge Base RAG pipeline (AI-253).

Orchestrates the full ingest pipeline:
  1. Chunk source text
  2. Embed each chunk
  3. Store in the VectorStore under the project namespace
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from knowledge_base.chunker import ChunkingStrategy
from knowledge_base.embeddings import EmbeddingProvider
from knowledge_base.vector_store import VectorStore


class DocumentIndexer:
    """Ingests documents into the vector store.

    Args:
        vector_store: Target VectorStore instance.
        chunker:      ChunkingStrategy instance.
        embedder:     EmbeddingProvider instance.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        chunker: ChunkingStrategy,
        embedder: EmbeddingProvider,
    ) -> None:
        self.vector_store = vector_store
        self.chunker = chunker
        self.embedder = embedder
        # Set of project_ids scheduled for reindex
        self._reindex_flags: set[str] = set()

    # ------------------------------------------------------------------ #
    # Indexing methods
    # ------------------------------------------------------------------ #

    def index_markdown_file(
        self,
        project_id: str,
        filepath: str,
        doc_id: Optional[str] = None,
    ) -> int:
        """Index a Markdown file into the vector store.

        Args:
            project_id: Project namespace.
            filepath:   Path to the Markdown file.
            doc_id:     Optional doc identifier (defaults to basename).

        Returns:
            Number of chunks indexed.
        """
        if doc_id is None:
            doc_id = os.path.basename(filepath)
        chunks = self.chunker.chunk_file(filepath)
        if not chunks:
            return 0
        embeddings = self.embedder.embed_batch([c["text"] for c in chunks])
        metadata = {"source": filepath, "doc_type": "markdown"}
        self.vector_store.add_document(project_id, doc_id, chunks, embeddings, metadata)
        return len(chunks)

    def index_pr_description(
        self,
        project_id: str,
        pr_data: Dict[str, Any],
    ) -> int:
        """Index a PR's title, body, and review comments.

        Expected keys in *pr_data*:
            ``pr_number`` (int), ``title`` (str), ``body`` (str),
            ``review_comments`` (list[str], optional).

        Args:
            project_id: Project namespace.
            pr_data:    PR data dict.

        Returns:
            Number of chunks indexed.
        """
        pr_number = pr_data.get("pr_number", "unknown")
        title = pr_data.get("title", "")
        body = pr_data.get("body", "")
        review_comments = pr_data.get("review_comments", [])

        parts = []
        if title:
            parts.append(f"PR #{pr_number}: {title}")
        if body:
            parts.append(body)
        if review_comments:
            parts.extend(review_comments)

        full_text = "\n\n".join(parts)
        doc_id = f"pr_{pr_number}"
        return self.index_text(
            project_id,
            full_text,
            doc_id,
            metadata={"source": f"PR #{pr_number}", "doc_type": "pr"},
        )

    def index_session_log(
        self,
        project_id: str,
        session_data: Dict[str, Any],
    ) -> int:
        """Index a completed agent session summary.

        Expected keys in *session_data*:
            ``session_id`` (str), ``summary`` (str),
            ``ticket_key`` (str, optional), ``outcome`` (str, optional).

        Args:
            project_id:   Project namespace.
            session_data: Session summary dict.

        Returns:
            Number of chunks indexed.
        """
        session_id = session_data.get("session_id", "unknown")
        summary = session_data.get("summary", "")
        ticket_key = session_data.get("ticket_key", "")
        outcome = session_data.get("outcome", "")

        parts = []
        if ticket_key:
            parts.append(f"Ticket: {ticket_key}")
        if outcome:
            parts.append(f"Outcome: {outcome}")
        if summary:
            parts.append(summary)

        full_text = "\n\n".join(parts)
        doc_id = f"session_{session_id}"
        return self.index_text(
            project_id,
            full_text,
            doc_id,
            metadata={"source": f"session_{session_id}", "doc_type": "session_log"},
        )

    def index_text(
        self,
        project_id: str,
        text: str,
        doc_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Generic indexer: chunk, embed, and store arbitrary text.

        Args:
            project_id: Project namespace.
            text:       Raw text content.
            doc_id:     Unique document identifier.
            metadata:   Optional metadata dict.

        Returns:
            Number of chunks indexed.
        """
        if not text.strip():
            return 0
        chunks = self.chunker.chunk_text(text)
        if not chunks:
            return 0
        embeddings = self.embedder.embed_batch([c["text"] for c in chunks])
        self.vector_store.add_document(
            project_id, doc_id, chunks, embeddings, metadata or {}
        )
        return len(chunks)

    # ------------------------------------------------------------------ #
    # Bulk reindex
    # ------------------------------------------------------------------ #

    def reindex_all(
        self,
        project_id: str,
        sources: List[str],
    ) -> Dict[str, Any]:
        """Full reindex from a list of file paths or raw text strings.

        Files are detected by path existence; non-existent strings are
        treated as inline text and indexed as-is.

        Args:
            project_id: Project namespace.
            sources:    List of file paths or raw text strings.

        Returns:
            Stats dict::

                {
                    "project_id": str,
                    "docs_indexed": int,
                    "chunks_indexed": int,
                    "errors": list[str],
                }
        """
        docs_indexed = 0
        chunks_indexed = 0
        errors: List[str] = []

        for i, source in enumerate(sources):
            try:
                if os.path.isfile(source):
                    n = self.index_markdown_file(project_id, source)
                else:
                    # Treat as raw text
                    doc_id = f"source_{i}"
                    n = self.index_text(project_id, source, doc_id)
                if n > 0:
                    docs_indexed += 1
                    chunks_indexed += n
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{source}: {exc}")

        # Clear reindex flag
        self._reindex_flags.discard(project_id)

        return {
            "project_id": project_id,
            "docs_indexed": docs_indexed,
            "chunks_indexed": chunks_indexed,
            "errors": errors,
        }

    def schedule_reindex(self, project_id: str) -> None:
        """Mark *project_id* as pending full reindex.

        Args:
            project_id: Project to schedule.
        """
        self._reindex_flags.add(project_id)

    def is_reindex_scheduled(self, project_id: str) -> bool:
        """Return True if *project_id* has a pending reindex scheduled.

        Args:
            project_id: Project to check.
        """
        return project_id in self._reindex_flags
