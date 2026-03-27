"""Tenant resource isolation manager.

Creates and manages isolated directory structures for each tenant to ensure
complete data segregation between enterprise customers.

Directory layout per tenant:
    data/tenants/{tenant_id}/           — tenant-specific state and config
    data/tenants/{tenant_id}/specs/     — tenant's spec files
    data/tenants/{tenant_id}/projects/  — project state files
    generations/{tenant_id}/            — generated project code
    generations/{tenant_id}/.worktrees/ — git worktree isolation
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from tenants.models import TenantConfig

logger = logging.getLogger(__name__)

# Base directories (configurable via env)
DATA_BASE = os.environ.get("DATA_BASE_PATH", "data")
GENERATIONS_BASE = os.environ.get("GENERATIONS_BASE_PATH", "generations")


class TenantIsolationManager:
    """Manages isolated directory structures for tenants.

    Args:
        data_base: Root data directory. Defaults to ``data/``.
        generations_base: Root generations directory. Defaults to ``generations/``.
    """

    def __init__(
        self,
        data_base: str = DATA_BASE,
        generations_base: str = GENERATIONS_BASE,
    ) -> None:
        self._data_base = Path(data_base)
        self._generations_base = Path(generations_base)

    def provision(self, config: TenantConfig) -> TenantConfig:
        """Create isolated directories for a new tenant.

        Updates the config's ``data_dir`` and ``worktree_base`` fields
        with the created paths.

        Args:
            config: Tenant configuration to provision directories for.

        Returns:
            The updated TenantConfig with populated path fields.
        """
        tenant_id = config.tenant_id

        # Data directories
        data_dir = self._data_base / "tenants" / tenant_id
        specs_dir = data_dir / "specs"
        projects_dir = data_dir / "projects"

        for d in (data_dir, specs_dir, projects_dir):
            d.mkdir(parents=True, exist_ok=True)

        # Generation directories
        gen_dir = self._generations_base / tenant_id
        worktree_dir = gen_dir / ".worktrees"

        for d in (gen_dir, worktree_dir):
            d.mkdir(parents=True, exist_ok=True)

        config.data_dir = str(data_dir)
        config.worktree_base = str(worktree_dir)

        logger.info(
            "Provisioned directories for tenant %s: data=%s, generations=%s",
            tenant_id,
            data_dir,
            gen_dir,
        )
        return config

    def deprovision(self, tenant_id: str) -> None:
        """Remove all directories for a deprovisioned tenant.

        Args:
            tenant_id: Tenant to clean up.
        """
        data_dir = self._data_base / "tenants" / tenant_id
        gen_dir = self._generations_base / tenant_id

        for d in (data_dir, gen_dir):
            if d.exists():
                shutil.rmtree(d)
                logger.info("Removed directory %s for tenant %s", d, tenant_id)

    def get_tenant_data_dir(self, tenant_id: str) -> Path:
        """Return the data directory for a tenant."""
        return self._data_base / "tenants" / tenant_id

    def get_tenant_specs_dir(self, tenant_id: str) -> Path:
        """Return the specs directory for a tenant."""
        return self._data_base / "tenants" / tenant_id / "specs"

    def get_tenant_project_dir(self, tenant_id: str, project_name: str) -> Path:
        """Return the generation directory for a tenant's project."""
        return self._generations_base / tenant_id / project_name

    def get_tenant_worktree_base(self, tenant_id: str) -> Path:
        """Return the worktree base directory for a tenant."""
        return self._generations_base / tenant_id / ".worktrees"

    def get_port_range(self, tenant_index: int, ports_per_tenant: int = 20) -> tuple[int, int]:
        """Return an isolated port range for a tenant's dev servers.

        Args:
            tenant_index: Zero-based index of the tenant (order of creation).
            ports_per_tenant: Number of ports allocated per tenant.

        Returns:
            Tuple of (start_port, end_port) inclusive.
        """
        base = 3100
        start = base + (tenant_index * ports_per_tenant)
        end = start + ports_per_tenant - 1
        return (start, end)

    def tenant_exists(self, tenant_id: str) -> bool:
        """Check if directories exist for a tenant."""
        return (self._data_base / "tenants" / tenant_id).is_dir()
