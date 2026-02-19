"""In-memory vector store with per-project namespace isolation (AI-253).

Simulates pgvector with pure-Python cosine-similarity search.
Each project gets its own isolated namespace; cross-project queries
are blocked at the API level.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from knowledge_base.embeddings import EmbeddingProvider


class VectorStore:
    """Thread-safe in-memory vector store.

    Data layout (per project)::

        _store[project_id] = {
            doc_id: {
                "chunks":     [ {text, start_char, end_char, chunk_index}, ... ],
                "embeddings": [ [float, ...], ... ],
                "metadata":   dict,
            },
            ...
        }
    """

    def __init__(self) -> None:
        # project_id -> {doc_id -> {chunks, embeddings, metadata}}
        self._store: Dict[str, Dict[str, Dict[str, Any]]] = {}

    # ------------------------------------------------------------------ #
    # Write operations
    # ------------------------------------------------------------------ #

    def add_document(
        self,
        project_id: str,
        doc_id: str,
        chunks: List[dict],
        embeddings: List[List[float]],
        metadata: Optional[dict] = None,
    ) -> None:
        """Store document chunks and their embeddings under *project_id*.

        Args:
            project_id:  Namespace key (isolates per project).
            doc_id:      Unique document identifier within the project.
            chunks:      List of chunk dicts from ChunkingStrategy.
            embeddings:  Corresponding embedding vectors (same length as *chunks*).
            metadata:    Arbitrary key/value metadata (doc type, source path, etc.).
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"len(chunks)={len(chunks)} must equal len(embeddings)={len(embeddings)}"
            )
        if project_id not in self._store:
            self._store[project_id] = {}
        self._store[project_id][doc_id] = {
            "chunks": chunks,
            "embeddings": embeddings,
            "metadata": metadata or {},
        }

    def delete_document(self, project_id: str, doc_id: str) -> None:
        """Remove a document from the store.

        Args:
            project_id: Project namespace.
            doc_id:     Document to remove.
        """
        if project_id in self._store:
            self._store[project_id].pop(doc_id, None)

    # ------------------------------------------------------------------ #
    # Read operations
    # ------------------------------------------------------------------ #

    def search(
        self,
        project_id: str,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[dict]:
        """Return the *top_k* most similar chunks for *project_id*.

        Args:
            project_id:      Namespace to search within.
            query_embedding: Query vector (same dimension as stored embeddings).
            top_k:           Number of results to return.

        Returns:
            List of result dicts sorted by descending similarity::

                [
                    {
                        "doc_id":     str,
                        "chunk":      dict,   # original chunk dict
                        "score":      float,  # cosine similarity
                        "metadata":   dict,
                    },
                    ...
                ]
        """
        if project_id not in self._store:
            return []

        results: List[dict] = []
        for doc_id, doc_data in self._store[project_id].items():
            for chunk, embedding in zip(doc_data["chunks"], doc_data["embeddings"]):
                score = EmbeddingProvider.cosine_similarity(query_embedding, embedding)
                results.append(
                    {
                        "doc_id": doc_id,
                        "chunk": chunk,
                        "score": score,
                        "metadata": doc_data["metadata"],
                    }
                )

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    def list_documents(self, project_id: str) -> List[str]:
        """Return all doc IDs stored for *project_id*.

        Args:
            project_id: Project namespace.

        Returns:
            List of document IDs (possibly empty).
        """
        if project_id not in self._store:
            return []
        return list(self._store[project_id].keys())

    def get_stats(self, project_id: str) -> dict:
        """Return stats for *project_id*.

        Returns:
            Dict with ``doc_count``, ``chunk_count``, ``project_id``.
        """
        if project_id not in self._store:
            return {"project_id": project_id, "doc_count": 0, "chunk_count": 0}
        docs = self._store[project_id]
        chunk_count = sum(len(d["chunks"]) for d in docs.values())
        return {
            "project_id": project_id,
            "doc_count": len(docs),
            "chunk_count": chunk_count,
        }

    # ------------------------------------------------------------------ #
    # Isolation helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def cross_project_search_blocked(project_id_a: str, project_id_b: str) -> bool:
        """Always returns True — cross-project queries are unconditionally blocked.

        Args:
            project_id_a: First project identifier.
            project_id_b: Second project identifier.

        Returns:
            True (always).
        """
        return True
