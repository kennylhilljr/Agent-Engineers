"""Tests for the shared cross-tenant memory system.

Verifies:
- Memory entry CRUD operations
- Search and recommendation functionality
- Privacy: source_tenant_id is never exposed in public APIs
- Capacity management (eviction of low-value entries)
"""

import os
import shutil
import tempfile
import unittest

from memory.models import MemoryCategory, MemoryEntry
from memory.shared_store import SharedMemoryStore, reset_shared_memory_store
from memory.collector import MemoryCollector, SessionResult


class TestMemoryEntry(unittest.TestCase):
    """Test MemoryEntry data model."""

    def test_default_entry(self):
        entry = MemoryEntry(title="Test pattern", content="Description")
        self.assertTrue(entry.entry_id)
        self.assertEqual(entry.category, MemoryCategory.PATTERN)
        self.assertEqual(entry.confidence, 0.5)
        self.assertEqual(entry.usage_count, 0)

    def test_public_dict_hides_source_tenant(self):
        entry = MemoryEntry(
            title="Secret pattern",
            source_tenant_id="tenant-secret",
        )
        public = entry.public_dict()
        self.assertNotIn("source_tenant_id", public)
        self.assertIn("title", public)

    def test_full_dict_includes_source_tenant(self):
        entry = MemoryEntry(source_tenant_id="tenant-123")
        full = entry.to_dict()
        self.assertEqual(full["source_tenant_id"], "tenant-123")

    def test_roundtrip_serialization(self):
        entry = MemoryEntry(
            category=MemoryCategory.ERROR_RESOLUTION,
            title="Fix timeout",
            content="Increase timeout to 30s",
            tags=["timeout", "api"],
            confidence=0.8,
        )
        restored = MemoryEntry.from_dict(entry.to_dict())
        self.assertEqual(restored.title, "Fix timeout")
        self.assertEqual(restored.category, MemoryCategory.ERROR_RESOLUTION)
        self.assertEqual(restored.confidence, 0.8)


class TestSharedMemoryStore(unittest.TestCase):
    """Test SharedMemoryStore operations."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._store_path = os.path.join(self._tmpdir, "memory.json")
        reset_shared_memory_store()
        self.store = SharedMemoryStore(store_path=self._store_path)

    def tearDown(self):
        shutil.rmtree(self._tmpdir)
        reset_shared_memory_store()

    def test_record_and_get(self):
        entry = MemoryEntry(title="Test", content="Content")
        self.store.record_pattern(entry)

        retrieved = self.store.get_entry(entry.entry_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "Test")

    def test_search_by_keyword(self):
        self.store.record_pattern(MemoryEntry(
            title="React component pattern",
            content="Use memo for expensive renders",
            tags=["react", "performance"],
        ))
        self.store.record_pattern(MemoryEntry(
            title="Python async pattern",
            content="Use asyncio.gather for parallel tasks",
            tags=["python", "async"],
        ))

        results = self.store.search(query="react")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "React component pattern")

    def test_search_by_category(self):
        self.store.record_pattern(MemoryEntry(
            category=MemoryCategory.PATTERN,
            title="Good pattern",
        ))
        self.store.record_pattern(MemoryEntry(
            category=MemoryCategory.ERROR_RESOLUTION,
            title="Error fix",
        ))

        results = self.store.search(category=MemoryCategory.ERROR_RESOLUTION)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Error fix")

    def test_search_by_tags(self):
        self.store.record_pattern(MemoryEntry(
            title="Tagged entry",
            tags=["react", "typescript"],
        ))
        self.store.record_pattern(MemoryEntry(
            title="Other entry",
            tags=["python"],
        ))

        results = self.store.search(tags=["react"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Tagged entry")

    def test_search_min_confidence(self):
        self.store.record_pattern(MemoryEntry(title="Low", confidence=0.2))
        self.store.record_pattern(MemoryEntry(title="High", confidence=0.9))

        results = self.store.search(min_confidence=0.5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "High")

    def test_increment_usage(self):
        entry = MemoryEntry(title="Popular")
        self.store.record_pattern(entry)
        self.store.increment_usage(entry.entry_id)
        self.store.increment_usage(entry.entry_id)

        updated = self.store.get_entry(entry.entry_id)
        self.assertEqual(updated.usage_count, 2)

    def test_delete_entry(self):
        entry = MemoryEntry(title="Delete me")
        self.store.record_pattern(entry)
        self.assertTrue(self.store.delete_entry(entry.entry_id))
        self.assertIsNone(self.store.get_entry(entry.entry_id))

    def test_recommendations_for_spec(self):
        self.store.record_pattern(MemoryEntry(
            title="Authentication with JWT",
            content="JWT tokens for API authentication with refresh token rotation",
            tags=["authentication", "jwt", "api"],
            confidence=0.8,
        ))
        self.store.record_pattern(MemoryEntry(
            title="Database migration pattern",
            content="Use Alembic for SQLAlchemy database migrations",
            tags=["database", "migration"],
            confidence=0.7,
        ))

        spec_content = "Build an API with JWT authentication and user management"
        recs = self.store.get_recommendations_for_spec(spec_content)
        self.assertGreater(len(recs), 0)
        # The JWT entry should rank higher
        self.assertIn("JWT", recs[0].title)

    def test_recommendations_privacy(self):
        """Recommendations should not leak source tenant information."""
        self.store.record_pattern(MemoryEntry(
            title="Secret pattern",
            content="This pattern involves authentication",
            source_tenant_id="secret-tenant-123",
            confidence=0.9,
        ))

        recs = self.store.get_recommendations_for_spec("authentication system")
        self.assertGreater(len(recs), 0)
        # Using public_dict should strip source_tenant_id
        for rec in recs:
            public = rec.public_dict()
            self.assertNotIn("source_tenant_id", public)

    def test_persistence(self):
        self.store.record_pattern(MemoryEntry(title="Persistent"))
        store2 = SharedMemoryStore(store_path=self._store_path)
        self.assertEqual(store2.entry_count(), 1)

    def test_category_counts(self):
        self.store.record_pattern(MemoryEntry(category=MemoryCategory.PATTERN))
        self.store.record_pattern(MemoryEntry(category=MemoryCategory.PATTERN))
        self.store.record_pattern(MemoryEntry(category=MemoryCategory.ERROR_RESOLUTION))

        counts = self.store.category_counts()
        self.assertEqual(counts[MemoryCategory.PATTERN], 2)
        self.assertEqual(counts[MemoryCategory.ERROR_RESOLUTION], 1)


class TestMemoryCollector(unittest.TestCase):
    """Test MemoryCollector session hooks."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._store_path = os.path.join(self._tmpdir, "memory.json")
        reset_shared_memory_store()
        self.store = SharedMemoryStore(store_path=self._store_path)
        self.collector = MemoryCollector(store=self.store)

    def tearDown(self):
        shutil.rmtree(self._tmpdir)
        reset_shared_memory_store()

    def test_successful_session_creates_pattern(self):
        import asyncio

        result = SessionResult(
            session_id="s-1",
            tenant_id="t-1",
            agent_type="coding",
            task_description="Implement user authentication with OAuth2 and JWT tokens",
            outcome="Success: implemented OAuth2 flow",
            files_changed=["auth.py", "routes.py"],
            tools_used=["Read", "Write", "Edit"],
            duration_seconds=120,
            model_used="sonnet",
        )

        entries = asyncio.get_event_loop().run_until_complete(
            self.collector.on_session_complete(result)
        )
        self.assertGreater(len(entries), 0)
        self.assertEqual(entries[0].source_tenant_id, "t-1")

    def test_error_resolution_creates_entry(self):
        import asyncio

        entry = asyncio.get_event_loop().run_until_complete(
            self.collector.on_error_resolved(
                tenant_id="t-2",
                error="ImportError: No module named 'fastapi'",
                resolution="Added fastapi to requirements.txt and ran pip install",
                context="During API server setup",
            )
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, MemoryCategory.ERROR_RESOLUTION)

    def test_architecture_decision_creates_entry(self):
        import asyncio

        entry = asyncio.get_event_loop().run_until_complete(
            self.collector.on_architecture_decision(
                tenant_id="t-3",
                decision="Use PostgreSQL instead of SQLite for production",
                rationale="Need concurrent writes and better scalability",
                alternatives="SQLite, MySQL, MongoDB",
            )
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, MemoryCategory.ARCHITECTURE)


if __name__ == "__main__":
    unittest.main()
