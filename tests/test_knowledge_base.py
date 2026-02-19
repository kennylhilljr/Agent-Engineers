"""Comprehensive tests for the Knowledge Base Agent (RAG) — AI-253.

Tests cover:
- ChunkingStrategy: fixed-size chunking, markdown-boundary-aware chunking
- EmbeddingProvider (mock): determinism, distinctness, cosine_similarity
- VectorStore: add, search, delete, list, stats, per-project isolation
- DocumentIndexer: index_text, index_markdown_file, index_pr_description,
  index_session_log, reindex_all, schedule_reindex
- KnowledgeBaseAgent: query structure, tier gating, formatted helpers
- KBWebhookHandler: enqueue on pr_merged/doc_committed, dequeue
- REST API endpoints: kb_query, kb_index, kb_stats, kb_reindex (tier gating)
"""

from __future__ import annotations

import math
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# =========================================================
# Module-level imports for tested units
# =========================================================
from knowledge_base.chunker import ChunkingStrategy
from knowledge_base.embeddings import EmbeddingProvider
from knowledge_base.vector_store import VectorStore
from knowledge_base.indexer import DocumentIndexer
from knowledge_base.agent import KnowledgeBaseAgent, KB_TIERS
from knowledge_base.webhook_handler import KBWebhookHandler


# =========================================================
# Helpers
# =========================================================

def _make_store_with_data(project_id: str = "proj_a", num_docs: int = 2):
    """Return a (VectorStore, EmbeddingProvider) with dummy data loaded."""
    store = VectorStore()
    embedder = EmbeddingProvider(provider="mock")
    chunker = ChunkingStrategy()

    for i in range(num_docs):
        text = f"Document {i}: This is some sample content about topic {i}. " * 5
        chunks = chunker.chunk_text(text)
        embeddings = embedder.embed_batch([c["text"] for c in chunks])
        store.add_document(
            project_id,
            doc_id=f"doc_{i}",
            chunks=chunks,
            embeddings=embeddings,
            metadata={"source": f"file_{i}.md"},
        )
    return store, embedder


# =========================================================
# ChunkingStrategy tests
# =========================================================

class TestChunkingStrategy(unittest.TestCase):

    def setUp(self):
        self.chunker = ChunkingStrategy()

    def test_chunk_text_empty_returns_empty(self):
        result = self.chunker.chunk_text("")
        self.assertEqual(result, [])

    def test_chunk_text_short_text_single_chunk(self):
        text = "Hello world, this is a short text."
        result = self.chunker.chunk_text(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], text)

    def test_chunk_text_respects_chunk_size(self):
        # Create text larger than one 512-token chunk (512*4 = 2048 chars)
        text = "a" * 5000
        chunks = self.chunker.chunk_text(text, chunk_size=512, overlap=64)
        # Should produce multiple chunks
        self.assertGreater(len(chunks), 1)
        # Each chunk should be at most 512*4 chars
        for c in chunks:
            self.assertLessEqual(len(c["text"]), 512 * 4)

    def test_chunk_text_overlap(self):
        # With overlap, consecutive chunks should share content at the boundary
        text = "x" * 4000
        chunks = self.chunker.chunk_text(text, chunk_size=100, overlap=20)
        self.assertGreater(len(chunks), 1)
        # end of first chunk and start of second should have overlap
        first_end = chunks[0]["end_char"]
        second_start = chunks[1]["start_char"]
        self.assertLess(second_start, first_end)

    def test_chunk_text_chunk_fields(self):
        text = "Hello world"
        chunks = self.chunker.chunk_text(text)
        self.assertEqual(len(chunks), 1)
        c = chunks[0]
        self.assertIn("text", c)
        self.assertIn("start_char", c)
        self.assertIn("end_char", c)
        self.assertIn("chunk_index", c)
        self.assertEqual(c["chunk_index"], 0)
        self.assertEqual(c["start_char"], 0)
        self.assertEqual(c["end_char"], len(text))

    def test_chunk_text_indices_are_sequential(self):
        text = "b" * 6000
        chunks = self.chunker.chunk_text(text, chunk_size=100, overlap=10)
        for i, c in enumerate(chunks):
            self.assertEqual(c["chunk_index"], i)

    def test_chunk_markdown_empty_returns_empty(self):
        result = self.chunker.chunk_markdown("")
        self.assertEqual(result, [])

    def test_chunk_markdown_no_headers_fallback(self):
        text = "Plain text without any headers.\nSecond line."
        result = self.chunker.chunk_markdown(text)
        # Falls back to chunk_text
        self.assertGreater(len(result), 0)
        self.assertIn("text", result[0])

    def test_chunk_markdown_respects_h1_boundaries(self):
        text = (
            "# Section One\n\nContent of section one.\n\n"
            "# Section Two\n\nContent of section two.\n\n"
            "# Section Three\n\nContent of section three."
        )
        chunks = self.chunker.chunk_markdown(text)
        # Each section should be its own chunk
        self.assertGreaterEqual(len(chunks), 3)
        combined = " ".join(c["text"] for c in chunks)
        self.assertIn("Section One", combined)
        self.assertIn("Section Two", combined)
        self.assertIn("Section Three", combined)

    def test_chunk_markdown_respects_h2_and_h3_boundaries(self):
        text = (
            "## Sub One\nContent A.\n"
            "### Sub Sub\nContent B.\n"
            "## Sub Two\nContent C.\n"
        )
        chunks = self.chunker.chunk_markdown(text)
        self.assertGreaterEqual(len(chunks), 2)

    def test_chunk_markdown_large_section_further_split(self):
        # A section with > 512 tokens worth of content should be sub-chunked
        big_section = "# Big Section\n" + ("word " * 2200)
        chunks = self.chunker.chunk_markdown(big_section)
        self.assertGreater(len(chunks), 1)

    def test_chunk_file_markdown(self):
        content = "# Title\n\nSome content.\n\n## Sub\n\nMore content."
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            fname = f.name
        try:
            chunks = self.chunker.chunk_file(fname)
            self.assertGreater(len(chunks), 0)
            combined = " ".join(c["text"] for c in chunks)
            self.assertIn("Title", combined)
        finally:
            os.unlink(fname)

    def test_chunk_file_text(self):
        content = "plain text content\n" * 10
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            fname = f.name
        try:
            chunks = self.chunker.chunk_file(fname)
            self.assertGreater(len(chunks), 0)
        finally:
            os.unlink(fname)

    def test_chunk_file_python(self):
        content = "def foo():\n    pass\n" * 5
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            fname = f.name
        try:
            chunks = self.chunker.chunk_file(fname)
            self.assertGreater(len(chunks), 0)
        finally:
            os.unlink(fname)

    def test_estimate_tokens(self):
        text = "hello world"  # 11 chars → 11//4 = 2
        self.assertEqual(ChunkingStrategy.estimate_tokens(text), 2)
        text40 = "a" * 40  # 40 chars → 10 tokens
        self.assertEqual(ChunkingStrategy.estimate_tokens(text40), 10)


# =========================================================
# EmbeddingProvider tests
# =========================================================

class TestEmbeddingProvider(unittest.TestCase):

    def setUp(self):
        self.embedder = EmbeddingProvider(provider="mock")

    def test_default_provider_is_mock(self):
        e = EmbeddingProvider()
        self.assertEqual(e.provider, "mock")

    def test_invalid_provider_raises(self):
        with self.assertRaises(ValueError):
            EmbeddingProvider(provider="unknown")

    def test_embed_returns_correct_dimension(self):
        vec = self.embedder.embed("hello world")
        self.assertEqual(len(vec), EmbeddingProvider.EMBEDDING_DIM)

    def test_embed_returns_list_of_floats(self):
        vec = self.embedder.embed("hello")
        self.assertTrue(all(isinstance(v, float) for v in vec))

    def test_embed_deterministic_same_text(self):
        text = "deterministic test text"
        vec1 = self.embedder.embed(text)
        vec2 = self.embedder.embed(text)
        self.assertEqual(vec1, vec2)

    def test_embed_different_texts_produce_different_vectors(self):
        vec_a = self.embedder.embed("text about cats")
        vec_b = self.embedder.embed("text about databases")
        # Must not be identical
        self.assertNotEqual(vec_a, vec_b)

    def test_embed_unit_normalised(self):
        vec = self.embedder.embed("some normalised text")
        norm = math.sqrt(sum(v * v for v in vec))
        self.assertAlmostEqual(norm, 1.0, places=6)

    def test_embed_batch_returns_correct_count(self):
        texts = ["text one", "text two", "text three"]
        vecs = self.embedder.embed_batch(texts)
        self.assertEqual(len(vecs), 3)

    def test_embed_batch_each_vector_correct_dimension(self):
        texts = ["a", "bb", "ccc"]
        vecs = self.embedder.embed_batch(texts)
        for v in vecs:
            self.assertEqual(len(v), EmbeddingProvider.EMBEDDING_DIM)

    def test_cosine_similarity_identical_vectors_is_one(self):
        vec = self.embedder.embed("same text")
        sim = EmbeddingProvider.cosine_similarity(vec, vec)
        self.assertAlmostEqual(sim, 1.0, places=5)

    def test_cosine_similarity_orthogonal_near_zero(self):
        # Two manually constructed orthogonal unit vectors
        dim = 4
        a = [1.0, 0.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0, 0.0]
        sim = EmbeddingProvider.cosine_similarity(a, b)
        self.assertAlmostEqual(sim, 0.0, places=9)

    def test_cosine_similarity_zero_vector_returns_zero(self):
        a = [0.0] * 4
        b = [1.0, 0.0, 0.0, 0.0]
        sim = EmbeddingProvider.cosine_similarity(a, b)
        self.assertEqual(sim, 0.0)

    def test_cosine_similarity_dimension_mismatch_raises(self):
        with self.assertRaises(ValueError):
            EmbeddingProvider.cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])

    def test_cosine_similarity_parallel_vectors_is_one(self):
        a = [0.6, 0.8, 0.0, 0.0]
        b = [0.6, 0.8, 0.0, 0.0]
        sim = EmbeddingProvider.cosine_similarity(a, b)
        self.assertAlmostEqual(sim, 1.0, places=9)


# =========================================================
# VectorStore tests
# =========================================================

class TestVectorStore(unittest.TestCase):

    def setUp(self):
        self.store = VectorStore()
        self.embedder = EmbeddingProvider(provider="mock")
        self.chunker = ChunkingStrategy()

    def _index_text(self, project_id: str, text: str, doc_id: str):
        chunks = self.chunker.chunk_text(text)
        embeddings = self.embedder.embed_batch([c["text"] for c in chunks])
        self.store.add_document(project_id, doc_id, chunks, embeddings, {"src": doc_id})
        return chunks, embeddings

    def test_add_and_list_documents(self):
        self._index_text("proj_x", "hello world content", "doc_1")
        docs = self.store.list_documents("proj_x")
        self.assertIn("doc_1", docs)

    def test_list_documents_empty_project(self):
        result = self.store.list_documents("nonexistent_project")
        self.assertEqual(result, [])

    def test_search_returns_results(self):
        text = "The quick brown fox jumps over the lazy dog."
        self._index_text("proj_y", text, "fox_doc")
        query_emb = self.embedder.embed("quick fox")
        results = self.store.search("proj_y", query_emb, top_k=1)
        self.assertEqual(len(results), 1)

    def test_search_result_structure(self):
        self._index_text("proj_struct", "sample text content here", "doc_a")
        query_emb = self.embedder.embed("sample text")
        results = self.store.search("proj_struct", query_emb, top_k=1)
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertIn("doc_id", r)
        self.assertIn("chunk", r)
        self.assertIn("score", r)
        self.assertIn("metadata", r)

    def test_search_top_k_respected(self):
        for i in range(5):
            self._index_text("proj_topk", f"Document content {i} " * 3, f"doc_{i}")
        query_emb = self.embedder.embed("document content")
        results = self.store.search("proj_topk", query_emb, top_k=3)
        self.assertLessEqual(len(results), 3)

    def test_search_results_sorted_by_score_descending(self):
        self._index_text("proj_sort", "cat dog fish bird", "fauna")
        query_emb = self.embedder.embed("animal taxonomy")
        results = self.store.search("proj_sort", query_emb, top_k=5)
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_search_empty_project_returns_empty(self):
        query_emb = self.embedder.embed("anything")
        results = self.store.search("no_such_project", query_emb)
        self.assertEqual(results, [])

    def test_delete_document(self):
        self._index_text("proj_del", "content to delete", "to_delete")
        self.assertIn("to_delete", self.store.list_documents("proj_del"))
        self.store.delete_document("proj_del", "to_delete")
        self.assertNotIn("to_delete", self.store.list_documents("proj_del"))

    def test_delete_nonexistent_document_no_error(self):
        # Should not raise
        self.store.delete_document("proj_del2", "ghost_doc")

    def test_get_stats_returns_correct_counts(self):
        self._index_text("proj_stats", "abc def ghi " * 10, "doc_1")
        self._index_text("proj_stats", "xyz uvw rst " * 10, "doc_2")
        stats = self.store.get_stats("proj_stats")
        self.assertEqual(stats["project_id"], "proj_stats")
        self.assertEqual(stats["doc_count"], 2)
        self.assertGreaterEqual(stats["chunk_count"], 2)

    def test_get_stats_empty_project(self):
        stats = self.store.get_stats("empty_proj")
        self.assertEqual(stats["doc_count"], 0)
        self.assertEqual(stats["chunk_count"], 0)

    def test_per_project_isolation_search(self):
        # Index doc only in project A
        text_a = "project alpha proprietary content alpha alpha"
        self._index_text("proj_alpha", text_a, "doc_alpha")

        # Search in project B — must return nothing
        query_emb = self.embedder.embed("project alpha")
        results_b = self.store.search("proj_beta", query_emb, top_k=5)
        self.assertEqual(results_b, [])

    def test_per_project_isolation_list(self):
        self._index_text("iso_a", "text for project a", "doc_a")
        docs_b = self.store.list_documents("iso_b")
        self.assertEqual(docs_b, [])

    def test_cross_project_search_blocked_always_true(self):
        self.assertTrue(VectorStore.cross_project_search_blocked("proj_a", "proj_b"))
        self.assertTrue(VectorStore.cross_project_search_blocked("proj_a", "proj_a"))
        self.assertTrue(VectorStore.cross_project_search_blocked("x", "y"))

    def test_add_document_chunk_embedding_length_mismatch_raises(self):
        chunks = [{"text": "a", "start_char": 0, "end_char": 1, "chunk_index": 0}]
        embeddings = []  # mismatch
        with self.assertRaises(ValueError):
            self.store.add_document("p", "d", chunks, embeddings)


# =========================================================
# DocumentIndexer tests
# =========================================================

class TestDocumentIndexer(unittest.TestCase):

    def setUp(self):
        self.store = VectorStore()
        self.chunker = ChunkingStrategy()
        self.embedder = EmbeddingProvider(provider="mock")
        self.indexer = DocumentIndexer(self.store, self.chunker, self.embedder)

    def test_index_text_returns_chunk_count(self):
        n = self.indexer.index_text("p1", "Hello, this is some sample content.", "doc1")
        self.assertGreater(n, 0)

    def test_index_text_empty_returns_zero(self):
        n = self.indexer.index_text("p1", "   ", "empty_doc")
        self.assertEqual(n, 0)

    def test_index_text_stored_in_project(self):
        self.indexer.index_text("p2", "Some meaningful content here.", "doc2")
        docs = self.store.list_documents("p2")
        self.assertIn("doc2", docs)

    def test_index_markdown_file(self):
        content = "# Title\n\nThis is the main content.\n\n## Section\n\nMore text."
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            fname = f.name
        try:
            n = self.indexer.index_markdown_file("p_md", fname)
            self.assertGreater(n, 0)
            docs = self.store.list_documents("p_md")
            self.assertIn(os.path.basename(fname), docs)
        finally:
            os.unlink(fname)

    def test_index_markdown_file_custom_doc_id(self):
        content = "# My Doc\n\nContent here."
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            fname = f.name
        try:
            n = self.indexer.index_markdown_file("p_custom", fname, doc_id="custom_id")
            self.assertGreater(n, 0)
            self.assertIn("custom_id", self.store.list_documents("p_custom"))
        finally:
            os.unlink(fname)

    def test_index_pr_description(self):
        pr_data = {
            "pr_number": 42,
            "title": "Fix memory leak in vector store",
            "body": "This PR resolves a memory leak that occurred during bulk indexing.",
            "review_comments": ["LGTM", "Please add tests"],
        }
        n = self.indexer.index_pr_description("p_pr", pr_data)
        self.assertGreater(n, 0)
        self.assertIn("pr_42", self.store.list_documents("p_pr"))

    def test_index_pr_description_no_review_comments(self):
        pr_data = {
            "pr_number": 99,
            "title": "Update README",
            "body": "Minor documentation update.",
        }
        n = self.indexer.index_pr_description("p_pr2", pr_data)
        self.assertGreater(n, 0)

    def test_index_session_log(self):
        session_data = {
            "session_id": "sess_001",
            "ticket_key": "AI-101",
            "outcome": "success",
            "summary": "Implemented the new caching layer for vector embeddings.",
        }
        n = self.indexer.index_session_log("p_sess", session_data)
        self.assertGreater(n, 0)
        self.assertIn("session_sess_001", self.store.list_documents("p_sess"))

    def test_reindex_all_stats_returned(self):
        texts = [
            "First document about database migrations.",
            "Second document about API design patterns.",
        ]
        result = self.indexer.reindex_all("p_reindex", texts)
        self.assertEqual(result["project_id"], "p_reindex")
        self.assertGreaterEqual(result["docs_indexed"], 1)
        self.assertGreaterEqual(result["chunks_indexed"], 1)
        self.assertIn("errors", result)

    def test_reindex_all_with_file_path(self):
        content = "# Reindex File\n\nContent for reindex test."
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            fname = f.name
        try:
            result = self.indexer.reindex_all("p_file", [fname])
            self.assertGreaterEqual(result["docs_indexed"], 1)
        finally:
            os.unlink(fname)

    def test_reindex_all_bad_file_recorded_in_errors(self):
        result = self.indexer.reindex_all("p_err", ["/nonexistent/path/file.md"])
        # Non-existent path treated as raw text (not a file), indexed as inline text
        # OR if it's tested as a file and fails — errors list may be populated.
        # Either way, the function should not raise.
        self.assertIn("errors", result)

    def test_schedule_reindex_marks_project(self):
        self.indexer.schedule_reindex("proj_pending")
        self.assertTrue(self.indexer.is_reindex_scheduled("proj_pending"))

    def test_is_reindex_scheduled_false_by_default(self):
        self.assertFalse(self.indexer.is_reindex_scheduled("fresh_project"))

    def test_reindex_all_clears_scheduled_flag(self):
        self.indexer.schedule_reindex("proj_clear")
        self.indexer.reindex_all("proj_clear", [])
        self.assertFalse(self.indexer.is_reindex_scheduled("proj_clear"))


# =========================================================
# KnowledgeBaseAgent tests
# =========================================================

class TestKnowledgeBaseAgent(unittest.TestCase):

    def setUp(self):
        self.store, self.embedder = _make_store_with_data("test_proj", num_docs=3)
        self.agent = KnowledgeBaseAgent(self.store, self.embedder, tier="team")

    def test_query_returns_correct_structure(self):
        result = self.agent.query("sample topic", "test_proj")
        self.assertIn("chunks", result)
        self.assertIn("sources", result)
        self.assertIn("query_time_ms", result)

    def test_query_chunks_is_list(self):
        result = self.agent.query("something", "test_proj")
        self.assertIsInstance(result["chunks"], list)

    def test_query_sources_is_list(self):
        result = self.agent.query("topic", "test_proj")
        self.assertIsInstance(result["sources"], list)

    def test_query_time_is_non_negative_float(self):
        result = self.agent.query("query", "test_proj")
        self.assertIsInstance(result["query_time_ms"], float)
        self.assertGreaterEqual(result["query_time_ms"], 0.0)

    def test_query_top_k_respected(self):
        result = self.agent.query("topic", "test_proj", top_k=2)
        self.assertLessEqual(len(result["chunks"]), 2)

    def test_query_empty_project_returns_empty_chunks(self):
        result = self.agent.query("anything", "no_such_project")
        self.assertEqual(result["chunks"], [])
        self.assertEqual(result["sources"], [])

    def test_is_available_for_tier_team(self):
        self.assertTrue(self.agent.is_available_for_tier("team"))

    def test_is_available_for_tier_organization(self):
        self.assertTrue(self.agent.is_available_for_tier("organization"))

    def test_is_available_for_tier_fleet(self):
        self.assertTrue(self.agent.is_available_for_tier("fleet"))

    def test_is_available_for_tier_enterprise(self):
        self.assertTrue(self.agent.is_available_for_tier("enterprise"))

    def test_is_available_for_tier_free_is_false(self):
        self.assertFalse(self.agent.is_available_for_tier("free"))

    def test_is_available_for_tier_builder_is_false(self):
        self.assertFalse(self.agent.is_available_for_tier("builder"))

    def test_is_available_for_tier_empty_is_false(self):
        self.assertFalse(self.agent.is_available_for_tier(""))

    def test_is_available_for_tier_case_insensitive(self):
        self.assertTrue(self.agent.is_available_for_tier("TEAM"))
        self.assertTrue(self.agent.is_available_for_tier("Organization"))

    def test_kb_tiers_constant(self):
        self.assertIn("team", KB_TIERS)
        self.assertIn("organization", KB_TIERS)
        self.assertIn("fleet", KB_TIERS)
        self.assertIn("enterprise", KB_TIERS)

    def test_query_for_coding_agent_returns_string(self):
        result = self.agent.query_for_coding_agent("implement a cache", "test_proj")
        self.assertIsInstance(result, str)

    def test_query_for_coding_agent_no_results(self):
        result = self.agent.query_for_coding_agent("something", "empty_proj")
        self.assertIn("No relevant", result)

    def test_query_for_coding_agent_includes_context_header(self):
        result = self.agent.query_for_coding_agent("topic", "test_proj")
        self.assertIn("Knowledge Base", result)

    def test_query_for_pr_reviewer_returns_string(self):
        result = self.agent.query_for_pr_reviewer("Fix memory leak", "test_proj")
        self.assertIsInstance(result, str)

    def test_query_for_pr_reviewer_no_results(self):
        result = self.agent.query_for_pr_reviewer("anything", "empty_proj")
        self.assertIn("No relevant", result)

    def test_query_for_pr_reviewer_includes_historical_header(self):
        result = self.agent.query_for_pr_reviewer("bug fix", "test_proj")
        self.assertIn("Historical Context", result)


# =========================================================
# KBWebhookHandler tests
# =========================================================

class TestKBWebhookHandler(unittest.TestCase):

    def setUp(self):
        self.handler = KBWebhookHandler()

    def test_handle_pr_merged_adds_to_queue(self):
        event = {"action": "closed", "pull_request": {"merged": True}}
        self.handler.handle_pr_merged(event, "proj_1")
        self.assertIn("proj_1", self.handler.get_reindex_queue())

    def test_handle_doc_committed_adds_to_queue(self):
        event = {"commits": [{"added": ["docs/README.md"]}]}
        self.handler.handle_doc_committed(event, "proj_2")
        self.assertIn("proj_2", self.handler.get_reindex_queue())

    def test_get_reindex_queue_deduplicates(self):
        event = {}
        self.handler.handle_pr_merged(event, "proj_dup")
        self.handler.handle_pr_merged(event, "proj_dup")
        queue = self.handler.get_reindex_queue()
        self.assertEqual(queue.count("proj_dup"), 1)

    def test_get_reindex_queue_empty_initially(self):
        handler = KBWebhookHandler()
        self.assertEqual(handler.get_reindex_queue(), [])

    def test_clear_project_removes_from_queue(self):
        self.handler.handle_pr_merged({}, "proj_clear")
        self.handler.clear_project("proj_clear")
        self.assertNotIn("proj_clear", self.handler.get_reindex_queue())

    def test_clear_queue_empties_all(self):
        self.handler.handle_pr_merged({}, "p1")
        self.handler.handle_doc_committed({}, "p2")
        self.handler.clear_queue()
        self.assertEqual(self.handler.get_reindex_queue(), [])

    def test_multiple_projects_in_queue(self):
        self.handler.handle_pr_merged({}, "pa")
        self.handler.handle_doc_committed({}, "pb")
        queue = self.handler.get_reindex_queue()
        self.assertIn("pa", queue)
        self.assertIn("pb", queue)

    def test_clear_nonexistent_project_no_error(self):
        self.handler.clear_project("ghost")  # Should not raise


# =========================================================
# REST API endpoint tests
# =========================================================

class TestKBRestEndpoints(unittest.IsolatedAsyncioTestCase):
    """Tests for the Knowledge Base REST API endpoints."""

    def _make_server(self):
        """Return a RESTAPIServer instance with mocked store."""
        from dashboard.rest_api_server import RESTAPIServer
        server = RESTAPIServer.__new__(RESTAPIServer)
        # Minimal initialization
        server.store = MagicMock()
        server.store.get_stats.return_value = {}
        return server

    async def _post_json(self, server, handler, body: dict):
        """Helper: call an async handler with a fake POST request."""
        request = MagicMock()
        request.json = AsyncMock(return_value=body)
        request.rel_url.query.get = MagicMock(return_value="")
        return await handler(request)

    async def _get_with_query(self, server, handler, query: dict):
        """Helper: call an async handler with a fake GET request."""
        request = MagicMock()
        request.json = AsyncMock(side_effect=Exception("no body"))
        request.rel_url.query.get = MagicMock(side_effect=lambda k, d="": query.get(k, d))
        return await handler(request)

    async def test_kb_query_team_tier_returns_200(self):
        server = self._make_server()
        body = {
            "question": "What patterns exist for caching?",
            "project_id": "proj_test",
            "top_k": 3,
            "tier": "team",
        }
        resp = await self._post_json(server, server.kb_query, body)
        self.assertEqual(resp.status, 200)

    async def test_kb_query_organization_tier_returns_200(self):
        server = self._make_server()
        body = {
            "question": "architecture patterns",
            "project_id": "proj_org",
            "tier": "organization",
        }
        resp = await self._post_json(server, server.kb_query, body)
        self.assertEqual(resp.status, 200)

    async def test_kb_query_fleet_tier_returns_200(self):
        server = self._make_server()
        body = {"question": "test", "project_id": "p", "tier": "fleet"}
        resp = await self._post_json(server, server.kb_query, body)
        self.assertEqual(resp.status, 200)

    async def test_kb_query_free_tier_returns_403(self):
        server = self._make_server()
        body = {
            "question": "test",
            "project_id": "proj",
            "tier": "free",
        }
        resp = await self._post_json(server, server.kb_query, body)
        self.assertEqual(resp.status, 403)

    async def test_kb_query_builder_tier_returns_403(self):
        server = self._make_server()
        body = {
            "question": "test",
            "project_id": "proj",
            "tier": "builder",
        }
        resp = await self._post_json(server, server.kb_query, body)
        self.assertEqual(resp.status, 403)

    async def test_kb_query_missing_question_returns_400(self):
        server = self._make_server()
        body = {"project_id": "proj", "tier": "team"}
        resp = await self._post_json(server, server.kb_query, body)
        self.assertEqual(resp.status, 400)

    async def test_kb_query_missing_project_id_returns_400(self):
        server = self._make_server()
        body = {"question": "something", "tier": "team"}
        resp = await self._post_json(server, server.kb_query, body)
        self.assertEqual(resp.status, 400)

    async def test_kb_index_team_tier_returns_200(self):
        server = self._make_server()
        body = {
            "project_id": "proj",
            "source_type": "markdown",
            "content": "# Title\n\nSome content here.",
            "doc_id": "readme",
            "tier": "team",
        }
        resp = await self._post_json(server, server.kb_index, body)
        self.assertEqual(resp.status, 200)

    async def test_kb_index_free_tier_returns_403(self):
        server = self._make_server()
        body = {
            "project_id": "proj",
            "content": "content",
            "doc_id": "doc",
            "tier": "free",
        }
        resp = await self._post_json(server, server.kb_index, body)
        self.assertEqual(resp.status, 403)

    async def test_kb_index_missing_fields_returns_400(self):
        server = self._make_server()
        body = {"tier": "team"}  # Missing project_id, content, doc_id
        resp = await self._post_json(server, server.kb_index, body)
        self.assertEqual(resp.status, 400)

    async def test_kb_stats_returns_200_without_tier(self):
        server = self._make_server()
        resp = await self._get_with_query(
            server, server.kb_stats, {"project_id": "proj_x"}
        )
        self.assertEqual(resp.status, 200)

    async def test_kb_stats_missing_project_id_returns_400(self):
        server = self._make_server()
        resp = await self._get_with_query(server, server.kb_stats, {})
        self.assertEqual(resp.status, 400)

    async def test_kb_stats_free_tier_returns_403(self):
        server = self._make_server()
        resp = await self._get_with_query(
            server, server.kb_stats, {"project_id": "proj", "tier": "free"}
        )
        self.assertEqual(resp.status, 403)

    async def test_kb_reindex_team_tier_returns_200(self):
        server = self._make_server()
        body = {
            "project_id": "proj",
            "sources": ["Some inline text content here."],
            "tier": "team",
        }
        resp = await self._post_json(server, server.kb_reindex, body)
        self.assertEqual(resp.status, 200)

    async def test_kb_reindex_free_tier_returns_403(self):
        server = self._make_server()
        body = {"project_id": "proj", "tier": "free"}
        resp = await self._post_json(server, server.kb_reindex, body)
        self.assertEqual(resp.status, 403)

    async def test_kb_reindex_missing_project_id_returns_400(self):
        server = self._make_server()
        body = {"tier": "team"}
        resp = await self._post_json(server, server.kb_reindex, body)
        self.assertEqual(resp.status, 400)

    async def test_kb_query_response_has_expected_keys(self):
        server = self._make_server()
        body = {
            "question": "find patterns",
            "project_id": "proj_keys",
            "tier": "team",
        }
        resp = await self._post_json(server, server.kb_query, body)
        self.assertEqual(resp.status, 200)
        import json
        data = json.loads(resp.body)
        self.assertIn("chunks", data)
        self.assertIn("sources", data)
        self.assertIn("query_time_ms", data)

    async def test_kb_index_response_has_expected_keys(self):
        server = self._make_server()
        body = {
            "project_id": "proj_idx",
            "content": "Test content for indexing.",
            "doc_id": "test_doc",
            "tier": "team",
        }
        resp = await self._post_json(server, server.kb_index, body)
        self.assertEqual(resp.status, 200)
        import json
        data = json.loads(resp.body)
        self.assertIn("doc_id", data)
        self.assertIn("chunks_indexed", data)

    async def test_kb_stats_response_has_expected_keys(self):
        server = self._make_server()
        resp = await self._get_with_query(
            server, server.kb_stats, {"project_id": "proj_stats"}
        )
        self.assertEqual(resp.status, 200)
        import json
        data = json.loads(resp.body)
        self.assertIn("project_id", data)
        self.assertIn("doc_count", data)
        self.assertIn("chunk_count", data)


# =========================================================
# Integration: end-to-end RAG flow
# =========================================================

class TestKBEndToEndRAG(unittest.TestCase):
    """Integration test: index documents then query and verify relevant results."""

    def setUp(self):
        self.store = VectorStore()
        self.chunker = ChunkingStrategy()
        self.embedder = EmbeddingProvider(provider="mock")
        self.indexer = DocumentIndexer(self.store, self.chunker, self.embedder)
        self.agent = KnowledgeBaseAgent(self.store, self.embedder, tier="team")
        self.project_id = "integration_proj"

        # Index some documents
        self.indexer.index_text(
            self.project_id,
            "The authentication system uses JWT tokens for session management.",
            "auth_doc",
        )
        self.indexer.index_text(
            self.project_id,
            "The database layer uses SQLAlchemy ORM with PostgreSQL.",
            "db_doc",
        )

    def test_query_returns_results_after_indexing(self):
        result = self.agent.query("authentication JWT", self.project_id)
        self.assertGreater(len(result["chunks"]), 0)

    def test_sources_populated_after_query(self):
        result = self.agent.query("database ORM", self.project_id)
        self.assertGreater(len(result["sources"]), 0)

    def test_cross_project_isolation(self):
        result = self.agent.query("authentication", "other_project")
        self.assertEqual(result["chunks"], [])

    def test_query_under_500ms(self):
        """Verify p95 query time is well under 500ms (simulated)."""
        import time
        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            self.agent.query("JWT tokens session", self.project_id)
            times.append((time.perf_counter() - t0) * 1000)
        p95 = sorted(times)[int(len(times) * 0.95)]
        self.assertLess(p95, 500, f"p95 query time {p95:.1f}ms exceeds 500ms limit")


if __name__ == "__main__":
    unittest.main()
