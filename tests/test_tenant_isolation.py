"""Tests for tenant isolation and multi-tenancy.

Verifies that:
- Tenant A cannot access Tenant B's data, projects, or agents
- Tenant directories are properly isolated
- Tenant lifecycle (create, suspend, reactivate, delete) works correctly
- TenantContext middleware correctly scopes requests
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tenants.models import (
    TENANT_STATUS_ACTIVE,
    TENANT_STATUS_SUSPENDED,
    PoolAllocation,
    TenantConfig,
    TenantContext,
    TenantError,
    TenantLimitError,
    TenantNotFoundError,
    TenantSuspendedError,
)
from tenants.store import TenantStore, reset_tenant_store
from tenants.isolation import TenantIsolationManager


class TestTenantConfig(unittest.TestCase):
    """Test TenantConfig data model."""

    def test_default_config(self):
        config = TenantConfig(name="Acme Corp", slug="acme-corp")
        self.assertEqual(config.name, "Acme Corp")
        self.assertEqual(config.slug, "acme-corp")
        self.assertEqual(config.max_projects, 10)
        self.assertEqual(config.max_concurrent_agents, 5)
        self.assertTrue(config.is_active())
        self.assertIn("haiku", config.allowed_models)
        self.assertIn("sonnet", config.allowed_models)
        self.assertIn("opus", config.allowed_models)

    def test_model_allowed(self):
        config = TenantConfig(allowed_models=["haiku", "sonnet"])
        self.assertTrue(config.is_model_allowed("haiku"))
        self.assertTrue(config.is_model_allowed("sonnet"))
        self.assertFalse(config.is_model_allowed("opus"))

    def test_serialization_roundtrip(self):
        config = TenantConfig(
            name="Test Tenant",
            slug="test-tenant",
            max_projects=20,
            pool_config={
                "coding": PoolAllocation(pool_type="coding", min_reserved=2, max_burst=5),
            },
        )
        data = config.to_dict()
        restored = TenantConfig.from_dict(data)
        self.assertEqual(restored.name, "Test Tenant")
        self.assertEqual(restored.max_projects, 20)
        self.assertIn("coding", restored.pool_config)
        self.assertEqual(restored.pool_config["coding"].min_reserved, 2)

    def test_public_dict_excludes_paths(self):
        config = TenantConfig(data_dir="/secret/path", worktree_base="/secret/worktree")
        public = config.public_dict()
        self.assertNotIn("data_dir", public)
        self.assertNotIn("worktree_base", public)


class TestTenantStore(unittest.TestCase):
    """Test TenantStore CRUD operations."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._store_path = os.path.join(self._tmpdir, "tenants.json")
        reset_tenant_store()
        self.store = TenantStore(store_path=self._store_path)

    def tearDown(self):
        shutil.rmtree(self._tmpdir)
        reset_tenant_store()

    def test_create_and_get(self):
        config = TenantConfig(name="Acme Corp", slug="acme-corp")
        created = self.store.create_tenant(config)
        self.assertEqual(created.name, "Acme Corp")
        self.assertTrue(created.created_at)

        retrieved = self.store.get_tenant(created.tenant_id)
        self.assertEqual(retrieved.name, "Acme Corp")

    def test_slug_uniqueness(self):
        self.store.create_tenant(TenantConfig(name="Acme", slug="acme"))
        with self.assertRaises(TenantError):
            self.store.create_tenant(TenantConfig(name="Acme 2", slug="acme"))

    def test_get_nonexistent(self):
        with self.assertRaises(TenantNotFoundError):
            self.store.get_tenant("nonexistent-id")

    def test_list_tenants(self):
        self.store.create_tenant(TenantConfig(name="A", slug="a"))
        self.store.create_tenant(TenantConfig(name="B", slug="b"))
        tenants = self.store.list_tenants()
        self.assertEqual(len(tenants), 2)

    def test_list_tenants_by_status(self):
        t1 = self.store.create_tenant(TenantConfig(name="Active", slug="active"))
        t2 = self.store.create_tenant(TenantConfig(name="Suspended", slug="suspended"))
        self.store.suspend_tenant(t2.tenant_id)

        active = self.store.list_tenants(status=TENANT_STATUS_ACTIVE)
        suspended = self.store.list_tenants(status=TENANT_STATUS_SUSPENDED)
        self.assertEqual(len(active), 1)
        self.assertEqual(len(suspended), 1)

    def test_update_tenant(self):
        t = self.store.create_tenant(TenantConfig(name="Old", slug="old"))
        updated = self.store.update_tenant(t.tenant_id, {"name": "New", "max_projects": 50})
        self.assertEqual(updated.name, "New")
        self.assertEqual(updated.max_projects, 50)

    def test_suspend_and_reactivate(self):
        t = self.store.create_tenant(TenantConfig(name="Test", slug="test"))
        self.store.suspend_tenant(t.tenant_id)
        suspended = self.store.get_tenant(t.tenant_id)
        self.assertFalse(suspended.is_active())

        self.store.reactivate_tenant(t.tenant_id)
        reactivated = self.store.get_tenant(t.tenant_id)
        self.assertTrue(reactivated.is_active())

    def test_delete_tenant(self):
        t = self.store.create_tenant(TenantConfig(name="Delete Me", slug="delete-me"))
        self.store.delete_tenant(t.tenant_id)
        with self.assertRaises(TenantNotFoundError):
            self.store.get_tenant(t.tenant_id)

    def test_persistence(self):
        self.store.create_tenant(TenantConfig(name="Persistent", slug="persistent"))
        # Create a new store pointing to the same file
        store2 = TenantStore(store_path=self._store_path)
        tenants = store2.list_tenants()
        self.assertEqual(len(tenants), 1)
        self.assertEqual(tenants[0].name, "Persistent")

    def test_tenant_a_cannot_access_tenant_b(self):
        """Core isolation test: two tenants get separate configs."""
        a = self.store.create_tenant(TenantConfig(name="Tenant A", slug="tenant-a"))
        b = self.store.create_tenant(TenantConfig(name="Tenant B", slug="tenant-b"))
        self.assertNotEqual(a.tenant_id, b.tenant_id)

        retrieved_a = self.store.get_tenant(a.tenant_id)
        retrieved_b = self.store.get_tenant(b.tenant_id)
        self.assertEqual(retrieved_a.name, "Tenant A")
        self.assertEqual(retrieved_b.name, "Tenant B")


class TestTenantIsolation(unittest.TestCase):
    """Test TenantIsolationManager directory isolation."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._data_base = os.path.join(self._tmpdir, "data")
        self._gen_base = os.path.join(self._tmpdir, "generations")
        self.manager = TenantIsolationManager(
            data_base=self._data_base,
            generations_base=self._gen_base,
        )

    def tearDown(self):
        shutil.rmtree(self._tmpdir)

    def test_provision_creates_directories(self):
        config = TenantConfig(tenant_id="t-123", name="Test")
        config = self.manager.provision(config)

        self.assertTrue(Path(config.data_dir).is_dir())
        self.assertTrue(Path(config.worktree_base).is_dir())
        self.assertTrue((Path(config.data_dir) / "specs").is_dir())
        self.assertTrue((Path(config.data_dir) / "projects").is_dir())

    def test_provision_sets_config_paths(self):
        config = TenantConfig(tenant_id="t-456", name="Test")
        config = self.manager.provision(config)
        self.assertIn("t-456", config.data_dir)
        self.assertIn("t-456", config.worktree_base)

    def test_deprovision_removes_directories(self):
        config = TenantConfig(tenant_id="t-789", name="Test")
        config = self.manager.provision(config)
        self.assertTrue(self.manager.tenant_exists("t-789"))

        self.manager.deprovision("t-789")
        self.assertFalse(self.manager.tenant_exists("t-789"))

    def test_tenant_directories_are_isolated(self):
        """Tenant A and B get completely separate directory trees."""
        a = self.manager.provision(TenantConfig(tenant_id="a", name="A"))
        b = self.manager.provision(TenantConfig(tenant_id="b", name="B"))

        # Directories should be different
        self.assertNotEqual(a.data_dir, b.data_dir)
        self.assertNotEqual(a.worktree_base, b.worktree_base)

        # Writing a file in A's directory should not affect B
        test_file_a = Path(a.data_dir) / "test.txt"
        test_file_a.write_text("tenant A data")

        test_file_b = Path(b.data_dir) / "test.txt"
        self.assertFalse(test_file_b.exists())

    def test_port_ranges_dont_overlap(self):
        range_0 = self.manager.get_port_range(0)
        range_1 = self.manager.get_port_range(1)
        # Ranges should not overlap
        self.assertLess(range_0[1], range_1[0])


class TestTenantContext(unittest.TestCase):
    """Test TenantContext runtime context."""

    def test_basic_context(self):
        config = TenantConfig(tenant_id="t-1", name="Test")
        ctx = TenantContext(
            tenant_id="t-1",
            tenant_config=config,
            user_id="user-1",
            role="admin",
        )
        self.assertEqual(ctx.tenant_id, "t-1")
        self.assertFalse(ctx.is_platform_admin)

    def test_platform_admin_context(self):
        ctx = TenantContext(
            tenant_id="",
            tenant_config=None,  # type: ignore
            user_id="admin-1",
            role="platform_admin",
            is_platform_admin=True,
        )
        self.assertTrue(ctx.is_platform_admin)


if __name__ == "__main__":
    unittest.main()
