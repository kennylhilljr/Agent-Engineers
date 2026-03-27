"""Tenant configuration persistence.

JSON-file-backed CRUD store for tenant configurations.
Follows the same singleton pattern as TeamStore and OrganizationStore.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from tenants.models import (
    TENANT_STATUS_ACTIVE,
    TENANT_STATUS_DEPROVISIONING,
    TENANT_STATUS_SUSPENDED,
    TenantConfig,
    TenantError,
    TenantNotFoundError,
)

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = os.path.join("data", "tenants.json")


class TenantStore:
    """Manages tenant CRUD operations with JSON file persistence.

    Args:
        store_path: Path to the JSON file. Defaults to ``data/tenants.json``.
    """

    def __init__(self, store_path: str = DEFAULT_STORE_PATH) -> None:
        self._store_path = store_path
        self._tenants: Dict[str, TenantConfig] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load tenant data from disk."""
        if os.path.exists(self._store_path):
            try:
                with open(self._store_path, "r") as f:
                    raw = json.load(f)
                for tid, data in raw.items():
                    self._tenants[tid] = TenantConfig.from_dict(data)
                logger.info("Loaded %d tenants from %s", len(self._tenants), self._store_path)
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Failed to load tenant store: %s", exc)
                self._tenants = {}
        else:
            logger.info("No tenant store at %s — starting empty", self._store_path)

    def _save(self) -> None:
        """Persist tenant data to disk."""
        os.makedirs(os.path.dirname(self._store_path) or ".", exist_ok=True)
        with open(self._store_path, "w") as f:
            json.dump(
                {tid: tc.to_dict() for tid, tc in self._tenants.items()},
                f,
                indent=2,
            )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_tenant(self, config: TenantConfig) -> TenantConfig:
        """Create a new tenant.

        Args:
            config: Tenant configuration. ``tenant_id`` is auto-generated if empty.

        Returns:
            The created TenantConfig with populated metadata.

        Raises:
            TenantError: If the slug is already in use.
        """
        if not config.slug:
            config.slug = _slugify(config.name)

        # Ensure slug uniqueness
        for existing in self._tenants.values():
            if existing.slug == config.slug:
                raise TenantError(f"Tenant slug '{config.slug}' is already in use")

        now = datetime.now(timezone.utc).isoformat()
        config.created_at = now
        config.updated_at = now
        config.status = TENANT_STATUS_ACTIVE

        self._tenants[config.tenant_id] = config
        self._save()
        logger.info("Created tenant %s (%s)", config.tenant_id, config.name)
        return config

    def get_tenant(self, tenant_id: str) -> TenantConfig:
        """Retrieve a tenant by ID.

        Raises:
            TenantNotFoundError: If no tenant matches the given ID.
        """
        if tenant_id not in self._tenants:
            raise TenantNotFoundError(f"Tenant not found: {tenant_id}")
        return self._tenants[tenant_id]

    def get_tenant_by_slug(self, slug: str) -> Optional[TenantConfig]:
        """Retrieve a tenant by slug. Returns None if not found."""
        for tc in self._tenants.values():
            if tc.slug == slug:
                return tc
        return None

    def list_tenants(self, status: Optional[str] = None) -> List[TenantConfig]:
        """List all tenants, optionally filtered by status."""
        tenants = list(self._tenants.values())
        if status:
            tenants = [t for t in tenants if t.status == status]
        return sorted(tenants, key=lambda t: t.created_at)

    def update_tenant(self, tenant_id: str, updates: Dict) -> TenantConfig:
        """Update a tenant's configuration fields.

        Args:
            tenant_id: Tenant to update.
            updates: Dictionary of field names to new values.

        Returns:
            The updated TenantConfig.

        Raises:
            TenantNotFoundError: If tenant doesn't exist.
        """
        config = self.get_tenant(tenant_id)

        for key, value in updates.items():
            if hasattr(config, key) and key not in ("tenant_id", "created_at"):
                setattr(config, key, value)

        config.updated_at = datetime.now(timezone.utc).isoformat()
        self._tenants[tenant_id] = config
        self._save()
        logger.info("Updated tenant %s: %s", tenant_id, list(updates.keys()))
        return config

    def suspend_tenant(self, tenant_id: str) -> TenantConfig:
        """Suspend a tenant, blocking all operations.

        Raises:
            TenantNotFoundError: If tenant doesn't exist.
        """
        return self.update_tenant(tenant_id, {"status": TENANT_STATUS_SUSPENDED})

    def reactivate_tenant(self, tenant_id: str) -> TenantConfig:
        """Reactivate a suspended tenant.

        Raises:
            TenantNotFoundError: If tenant doesn't exist.
        """
        return self.update_tenant(tenant_id, {"status": TENANT_STATUS_ACTIVE})

    def delete_tenant(self, tenant_id: str) -> None:
        """Mark a tenant for deprovisioning and remove from store.

        Raises:
            TenantNotFoundError: If tenant doesn't exist.
        """
        self.get_tenant(tenant_id)  # validate exists
        self.update_tenant(tenant_id, {"status": TENANT_STATUS_DEPROVISIONING})
        del self._tenants[tenant_id]
        self._save()
        logger.info("Deleted tenant %s", tenant_id)

    def tenant_count(self) -> int:
        """Return total number of tenants."""
        return len(self._tenants)


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

_tenant_store: Optional[TenantStore] = None


def get_tenant_store(store_path: str = DEFAULT_STORE_PATH) -> TenantStore:
    """Return the module-level TenantStore singleton."""
    global _tenant_store
    if _tenant_store is None:
        _tenant_store = TenantStore(store_path)
    return _tenant_store


def reset_tenant_store() -> None:
    """Reset the singleton (for testing)."""
    global _tenant_store
    _tenant_store = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    """Convert a tenant name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "tenant"
