"""Tests for the spec lifecycle manager.

Verifies:
- Spec CRUD operations
- Version management
- Status lifecycle transitions
- Spec file persistence
- Recommendation tracking
"""

import os
import shutil
import tempfile
import unittest

from specs.spec_manager import Spec, SpecManager, SpecNotFoundError, SpecStatusError


class TestSpec(unittest.TestCase):
    """Test Spec data model."""

    def test_default_spec(self):
        spec = Spec(name="Test App", content="Build a todo app")
        self.assertTrue(spec.spec_id)
        self.assertEqual(spec.status, "draft")
        self.assertEqual(spec.version, 1)

    def test_serialization_roundtrip(self):
        spec = Spec(
            name="My App",
            content="Spec content",
            description="A test app",
            context="Use React",
            version=3,
            status="submitted",
        )
        restored = Spec.from_dict(spec.to_dict())
        self.assertEqual(restored.name, "My App")
        self.assertEqual(restored.version, 3)
        self.assertEqual(restored.status, "submitted")


class TestSpecManager(unittest.TestCase):
    """Test SpecManager lifecycle operations."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.manager = SpecManager(
            tenant_id="test-tenant",
            data_dir=self._tmpdir,
        )

    def tearDown(self):
        shutil.rmtree(self._tmpdir)

    def test_create_spec(self):
        spec = self.manager.create_spec(
            name="Todo App",
            content="Build a todo application with React and FastAPI",
            author_id="user-1",
        )
        self.assertEqual(spec.name, "Todo App")
        self.assertEqual(spec.status, "draft")
        self.assertEqual(spec.version, 1)
        self.assertEqual(spec.tenant_id, "test-tenant")

    def test_get_spec(self):
        created = self.manager.create_spec(
            name="Test", content="Content", author_id="user-1"
        )
        retrieved = self.manager.get_spec(created.spec_id)
        self.assertEqual(retrieved.name, "Test")

    def test_get_nonexistent(self):
        with self.assertRaises(SpecNotFoundError):
            self.manager.get_spec("nonexistent")

    def test_update_spec_increments_version(self):
        spec = self.manager.create_spec(
            name="V1", content="Version 1", author_id="user-1"
        )
        updated = self.manager.update_spec(
            spec_id=spec.spec_id,
            content="Version 2 content",
            author_id="user-1",
        )
        self.assertEqual(updated.version, 2)
        self.assertEqual(updated.content, "Version 2 content")

    def test_cannot_update_submitted_spec(self):
        spec = self.manager.create_spec(
            name="Test", content="Content", author_id="user-1"
        )
        self.manager.submit_spec(spec.spec_id)

        with self.assertRaises(SpecStatusError):
            self.manager.update_spec(
                spec_id=spec.spec_id,
                content="New content",
                author_id="user-1",
            )

    def test_submit_spec(self):
        spec = self.manager.create_spec(
            name="Test", content="Content", author_id="user-1"
        )
        submitted = self.manager.submit_spec(spec.spec_id)
        self.assertEqual(submitted.status, "submitted")

    def test_cannot_submit_empty_spec(self):
        spec = self.manager.create_spec(
            name="Empty", content="   ", author_id="user-1"
        )
        with self.assertRaises(SpecStatusError):
            self.manager.submit_spec(spec.spec_id)

    def test_cannot_submit_twice(self):
        spec = self.manager.create_spec(
            name="Test", content="Content", author_id="user-1"
        )
        self.manager.submit_spec(spec.spec_id)
        with self.assertRaises(SpecStatusError):
            self.manager.submit_spec(spec.spec_id)

    def test_full_lifecycle(self):
        # Create draft
        spec = self.manager.create_spec(
            name="Full Lifecycle",
            content="Build something",
            author_id="user-1",
        )
        self.assertEqual(spec.status, "draft")

        # Submit
        spec = self.manager.submit_spec(spec.spec_id)
        self.assertEqual(spec.status, "submitted")

        # Processing
        spec = self.manager.set_processing(spec.spec_id, project_id="proj-1")
        self.assertEqual(spec.status, "processing")
        self.assertEqual(spec.project_id, "proj-1")

        # Complete
        spec = self.manager.set_completed(spec.spec_id)
        self.assertEqual(spec.status, "completed")

    def test_revert_to_draft(self):
        spec = self.manager.create_spec(
            name="Test", content="Content", author_id="user-1"
        )
        self.manager.submit_spec(spec.spec_id)
        reverted = self.manager.revert_to_draft(spec.spec_id)
        self.assertEqual(reverted.status, "draft")

    def test_cannot_revert_processing(self):
        spec = self.manager.create_spec(
            name="Test", content="Content", author_id="user-1"
        )
        self.manager.submit_spec(spec.spec_id)
        self.manager.set_processing(spec.spec_id)
        with self.assertRaises(SpecStatusError):
            self.manager.revert_to_draft(spec.spec_id)

    def test_list_specs(self):
        self.manager.create_spec(name="A", content="A", author_id="u")
        self.manager.create_spec(name="B", content="B", author_id="u")
        specs = self.manager.list_specs()
        self.assertEqual(len(specs), 2)

    def test_list_specs_by_status(self):
        s1 = self.manager.create_spec(name="Draft", content="D", author_id="u")
        s2 = self.manager.create_spec(name="Submitted", content="S", author_id="u")
        self.manager.submit_spec(s2.spec_id)

        drafts = self.manager.list_specs(status="draft")
        submitted = self.manager.list_specs(status="submitted")
        self.assertEqual(len(drafts), 1)
        self.assertEqual(len(submitted), 1)

    def test_delete_draft_spec(self):
        spec = self.manager.create_spec(
            name="Delete Me", content="Content", author_id="u"
        )
        self.manager.delete_spec(spec.spec_id)
        with self.assertRaises(SpecNotFoundError):
            self.manager.get_spec(spec.spec_id)

    def test_cannot_delete_submitted(self):
        spec = self.manager.create_spec(
            name="Test", content="Content", author_id="u"
        )
        self.manager.submit_spec(spec.spec_id)
        with self.assertRaises(SpecStatusError):
            self.manager.delete_spec(spec.spec_id)

    def test_spec_file_created(self):
        spec = self.manager.create_spec(
            name="File Test", content="Spec content here", author_id="u"
        )
        spec_file = self.manager.get_spec_file_path(spec.spec_id)
        self.assertTrue(spec_file.exists())
        content = spec_file.read_text()
        self.assertIn("File Test", content)
        self.assertIn("Spec content here", content)

    def test_apply_recommendation(self):
        spec = self.manager.create_spec(
            name="Test", content="Content", author_id="u"
        )
        self.manager.apply_recommendation(spec.spec_id, "memory-entry-1")
        updated = self.manager.get_spec(spec.spec_id)
        self.assertIn("memory-entry-1", updated.recommendations_applied)

    def test_persistence(self):
        self.manager.create_spec(name="Persistent", content="C", author_id="u")
        # Create new manager pointing to same directory
        manager2 = SpecManager(tenant_id="test-tenant", data_dir=self._tmpdir)
        specs = manager2.list_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].name, "Persistent")


if __name__ == "__main__":
    unittest.main()
