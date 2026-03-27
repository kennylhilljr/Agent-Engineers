"""
Tenant-Aware Agent Pool Manager
================================

Wraps the existing WorkerPoolManager with per-tenant worker allocation,
a shared warm pool for fast provisioning, and tenant-scoped utilization
tracking.

Provides:
- TenantPoolManager: top-level API for tenant worker lifecycle
- Shared warm pool of pre-initialized workers for fast allocation
- Per-tenant reserved workers with burst into the shared pool
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from daemon.worker_pool import (
    PoolType,
    TypedWorker,
    WorkerPoolManager,
    WorkerStatus,
)
from tenants.models import PoolAllocation, TenantConfig

logger = logging.getLogger("tenant_pool")


class TenantPoolManager:
    """Manages worker allocation across tenants with shared warm pool fallback.

    Architecture:
        Each tenant gets reserved workers based on their PoolAllocation config.
        When a tenant's reserved workers are exhausted, the manager falls back
        to a shared warm pool of pre-initialized workers. If the warm pool is
        also empty, a new worker is created on-demand (up to tenant burst limit).

    Attributes:
        pool_manager: Underlying WorkerPoolManager for pool lifecycle.
    """

    def __init__(self, pool_manager: WorkerPoolManager) -> None:
        self.pool_manager = pool_manager
        # tenant_id -> pool_type_value -> list of reserved TypedWorker
        self._tenant_workers: dict[str, dict[str, list[TypedWorker]]] = {}
        # pool_type_value -> list of warm (pre-initialized, unassigned) workers
        self._warm_pool: dict[str, list[TypedWorker]] = {}
        # Track tenant configs for limit enforcement
        self._tenant_configs: dict[str, TenantConfig] = {}
        # Counter for unique worker IDs
        self._worker_counter: int = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_worker_id(self, tenant_id: str, pool_type: PoolType) -> str:
        """Generate a unique worker ID scoped to tenant and pool."""
        self._worker_counter += 1
        return f"{tenant_id[:8]}-{pool_type.value}-{self._worker_counter}"

    def _create_worker(self, tenant_id: str, pool_type: PoolType) -> TypedWorker:
        """Create a new TypedWorker assigned to a tenant."""
        worker = TypedWorker(
            worker_id=self._next_worker_id(tenant_id, pool_type),
            pool_type=pool_type,
            tenant_id=tenant_id,
        )
        return worker

    def _get_allocation(self, tenant_id: str, pool_type: PoolType) -> PoolAllocation | None:
        """Look up the tenant's PoolAllocation for a given pool type."""
        config = self._tenant_configs.get(tenant_id)
        if config is None:
            return None
        return config.pool_config.get(pool_type.value)

    # ------------------------------------------------------------------
    # Provisioning
    # ------------------------------------------------------------------

    def provision_tenant(self, tenant_config: TenantConfig) -> dict[str, int]:
        """Allocate reserved workers for a tenant based on their pool_config.

        Args:
            tenant_config: Tenant configuration with pool_config allocations.

        Returns:
            Dictionary mapping pool type names to the number of reserved workers
            that were created.
        """
        tenant_id = tenant_config.tenant_id
        self._tenant_configs[tenant_id] = tenant_config

        if tenant_id not in self._tenant_workers:
            self._tenant_workers[tenant_id] = {}

        provisioned: dict[str, int] = {}

        for pool_name, allocation in tenant_config.pool_config.items():
            try:
                pool_type = PoolType(pool_name)
            except ValueError:
                logger.warning(
                    "Unknown pool type '%s' for tenant %s — skipping",
                    pool_name,
                    tenant_id,
                )
                continue

            if pool_name not in self._tenant_workers[tenant_id]:
                self._tenant_workers[tenant_id][pool_name] = []

            existing = len(self._tenant_workers[tenant_id][pool_name])
            needed = max(0, allocation.min_reserved - existing)

            for _ in range(needed):
                # Try to pull from warm pool first
                warm = self._warm_pool.get(pool_name, [])
                if warm:
                    worker = warm.pop(0)
                    worker.tenant_id = tenant_id
                    worker.worker_id = self._next_worker_id(tenant_id, pool_type)
                else:
                    worker = self._create_worker(tenant_id, pool_type)

                self._tenant_workers[tenant_id][pool_name].append(worker)

            provisioned[pool_name] = needed
            logger.info(
                "Provisioned %d %s workers for tenant %s (reserved=%d)",
                needed,
                pool_name,
                tenant_id,
                allocation.min_reserved,
            )

        return provisioned

    def deprovision_tenant(self, tenant_id: str) -> int:
        """Release all workers for a tenant, returning idle ones to the warm pool.

        Args:
            tenant_id: Tenant to deprovision.

        Returns:
            Total number of workers released.
        """
        tenant_pools = self._tenant_workers.pop(tenant_id, {})
        self._tenant_configs.pop(tenant_id, None)
        released = 0

        for pool_name, workers in tenant_pools.items():
            for worker in workers:
                released += 1
                if worker.is_idle:
                    # Return idle workers to warm pool
                    worker.tenant_id = ""
                    warm = self._warm_pool.setdefault(pool_name, [])
                    warm.append(worker)
                else:
                    # Mark busy workers as draining; they will be reclaimed later
                    worker.status = WorkerStatus.DRAINING

        logger.info("Deprovisioned tenant %s — released %d workers", tenant_id, released)
        return released

    # ------------------------------------------------------------------
    # Worker acquisition / return
    # ------------------------------------------------------------------

    def get_worker(self, tenant_id: str, pool_type: PoolType) -> TypedWorker | None:
        """Get an idle worker for a tenant.

        Resolution order:
            1. Tenant's own reserved workers (idle)
            2. Shared warm pool
            3. Create new worker (if under tenant's max_burst limit)

        Args:
            tenant_id: Tenant requesting a worker.
            pool_type: Type of worker pool needed.

        Returns:
            An idle TypedWorker, or None if no capacity is available.
        """
        pool_name = pool_type.value

        # 1. Check tenant's reserved workers
        tenant_pools = self._tenant_workers.get(tenant_id, {})
        reserved = tenant_pools.get(pool_name, [])
        for worker in reserved:
            if worker.is_idle:
                worker.status = WorkerStatus.EXECUTING
                worker.started_at = datetime.now(UTC)
                return worker

        # 2. Check warm pool
        warm = self._warm_pool.get(pool_name, [])
        if warm:
            worker = warm.pop(0)
            worker.tenant_id = tenant_id
            worker.status = WorkerStatus.EXECUTING
            worker.started_at = datetime.now(UTC)
            # Track as tenant worker
            tenant_pools.setdefault(pool_name, []).append(worker)
            if tenant_id not in self._tenant_workers:
                self._tenant_workers[tenant_id] = tenant_pools
            return worker

        # 3. Create new worker if under burst limit
        allocation = self._get_allocation(tenant_id, pool_type)
        current_count = len(reserved)
        max_burst = allocation.max_burst if allocation else 3

        if current_count < max_burst:
            worker = self._create_worker(tenant_id, pool_type)
            worker.status = WorkerStatus.EXECUTING
            worker.started_at = datetime.now(UTC)
            if tenant_id not in self._tenant_workers:
                self._tenant_workers[tenant_id] = {}
            self._tenant_workers[tenant_id].setdefault(pool_name, []).append(worker)
            return worker

        logger.warning(
            "No capacity for tenant %s pool %s (reserved=%d, max_burst=%d)",
            tenant_id,
            pool_name,
            current_count,
            max_burst,
        )
        return None

    def return_worker(self, tenant_id: str, worker: TypedWorker) -> None:
        """Return a worker after task completion.

        If the worker exceeds the tenant's min_reserved count, it is returned
        to the shared warm pool instead.

        Args:
            tenant_id: Tenant returning the worker.
            worker: Worker to return.
        """
        worker.status = WorkerStatus.IDLE
        worker.current_ticket = None
        worker.started_at = None

        pool_name = worker.pool_type.value
        allocation = self._get_allocation(tenant_id, worker.pool_type)
        min_reserved = allocation.min_reserved if allocation else 0

        tenant_pools = self._tenant_workers.get(tenant_id, {})
        reserved = tenant_pools.get(pool_name, [])

        if len(reserved) > min_reserved:
            # Over minimum — return excess worker to warm pool
            if worker in reserved:
                reserved.remove(worker)
            worker.tenant_id = ""
            warm = self._warm_pool.setdefault(pool_name, [])
            warm.append(worker)
            logger.debug(
                "Returned excess worker %s to warm pool (tenant %s, pool %s)",
                worker.worker_id,
                tenant_id,
                pool_name,
            )
        else:
            logger.debug(
                "Worker %s returned to tenant %s reserved pool %s",
                worker.worker_id,
                tenant_id,
                pool_name,
            )

    # ------------------------------------------------------------------
    # Warm pool management
    # ------------------------------------------------------------------

    def pre_warm(self, count: int, pool_type: PoolType) -> int:
        """Pre-warm workers in the shared pool for fast allocation.

        Args:
            count: Number of workers to pre-warm.
            pool_type: Pool type to pre-warm.

        Returns:
            Number of workers actually created and added to warm pool.
        """
        pool_name = pool_type.value
        warm = self._warm_pool.setdefault(pool_name, [])
        created = 0

        for _ in range(count):
            self._worker_counter += 1
            worker = TypedWorker(
                worker_id=f"warm-{pool_name}-{self._worker_counter}",
                pool_type=pool_type,
                tenant_id="",
            )
            warm.append(worker)
            created += 1

        logger.info("Pre-warmed %d %s workers (warm pool size: %d)", created, pool_name, len(warm))
        return created

    # ------------------------------------------------------------------
    # Status / observability
    # ------------------------------------------------------------------

    def tenant_status(self, tenant_id: str) -> dict[str, Any]:
        """Per-tenant utilization summary.

        Args:
            tenant_id: Tenant to query.

        Returns:
            Dictionary with per-pool worker counts, idle/busy breakdown,
            and allocation limits.
        """
        tenant_pools = self._tenant_workers.get(tenant_id, {})
        config = self._tenant_configs.get(tenant_id)
        pools_info: dict[str, Any] = {}

        for pool_name, workers in tenant_pools.items():
            idle = sum(1 for w in workers if w.is_idle)
            busy = len(workers) - idle
            allocation = config.pool_config.get(pool_name) if config else None
            pools_info[pool_name] = {
                "total_workers": len(workers),
                "idle": idle,
                "busy": busy,
                "min_reserved": allocation.min_reserved if allocation else 0,
                "max_burst": allocation.max_burst if allocation else 0,
            }

        return {
            "tenant_id": tenant_id,
            "status": config.status if config else "unknown",
            "pools": pools_info,
        }

    def global_status(self) -> dict[str, Any]:
        """Platform-wide utilization summary.

        Returns:
            Dictionary with tenant count, warm pool sizes, and aggregate
            worker counts across all tenants.
        """
        total_reserved = 0
        total_warm = 0
        tenant_summaries: dict[str, dict[str, int]] = {}

        for tenant_id, tenant_pools in self._tenant_workers.items():
            tenant_total = sum(len(workers) for workers in tenant_pools.values())
            tenant_busy = sum(
                sum(1 for w in workers if not w.is_idle)
                for workers in tenant_pools.values()
            )
            total_reserved += tenant_total
            tenant_summaries[tenant_id] = {
                "total_workers": tenant_total,
                "busy": tenant_busy,
            }

        warm_pool_info: dict[str, int] = {}
        for pool_name, workers in self._warm_pool.items():
            warm_pool_info[pool_name] = len(workers)
            total_warm += len(workers)

        return {
            "tenant_count": len(self._tenant_workers),
            "total_reserved_workers": total_reserved,
            "total_warm_workers": total_warm,
            "warm_pool": warm_pool_info,
            "tenants": tenant_summaries,
        }
