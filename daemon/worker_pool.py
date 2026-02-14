"""
Worker Pool Management
======================

Typed worker pools with named workers, lease-based ticket tracking,
and dynamic scaling for the scalable daemon (v2).

Provides:
- PoolType enum (coding, review, linear)
- TypedWorker with per-worker state tracking
- WorkerPoolManager for pool lifecycle and ticket leasing
- DaemonConfig for JSON-based daemon configuration
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Literal

logger = logging.getLogger("worker_pool")

# ---------------------------------------------------------------------------
# Available models
# ---------------------------------------------------------------------------

AVAILABLE_MODELS: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-5-20250929",
    "opus": "claude-opus-4-5-20251101",
}

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PoolType(Enum):
    """Type of worker pool."""

    CODING = "coding"
    REVIEW = "review"
    LINEAR = "linear"


class WorkerStatus(Enum):
    """Current status of a worker."""

    IDLE = "idle"
    EXECUTING = "executing"
    DRAINING = "draining"


class TicketComplexity(Enum):
    """Estimated complexity of a ticket for model routing."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Ticket
# ---------------------------------------------------------------------------

TicketStatus = Literal["todo", "in_progress", "review", "done"]


@dataclass
class Ticket:
    """A ticket that can be worked on by a worker."""

    key: str
    title: str
    description: str
    status: TicketStatus
    priority: str = "medium"
    complexity: TicketComplexity = TicketComplexity.MEDIUM
    labels: list[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Ticket):
            return NotImplemented
        return self.key == other.key


# ---------------------------------------------------------------------------
# Typed Worker
# ---------------------------------------------------------------------------


@dataclass
class TypedWorker:
    """A named worker assigned to a specific pool."""

    worker_id: str
    pool_type: PoolType
    status: WorkerStatus = WorkerStatus.IDLE
    current_ticket: Ticket | None = None
    started_at: datetime | None = None
    consecutive_errors: int = 0
    tickets_completed: int = 0
    worktree_path: Path | None = None
    port: int | None = None

    @property
    def is_idle(self) -> bool:
        return self.status == WorkerStatus.IDLE


# ---------------------------------------------------------------------------
# Ticket Lease
# ---------------------------------------------------------------------------


@dataclass
class TicketLease:
    """Tracks which worker holds a ticket and when it expires."""

    ticket_key: str
    worker_id: str
    acquired_at: datetime
    ttl: int  # seconds

    @property
    def is_expired(self) -> bool:
        elapsed = (datetime.now(UTC) - self.acquired_at).total_seconds()
        return elapsed > self.ttl


# ---------------------------------------------------------------------------
# Pool Configuration
# ---------------------------------------------------------------------------


@dataclass
class PoolConfig:
    """Configuration for a single worker pool."""

    min_workers: int = 1
    max_workers: int = 3
    default_model: str = "sonnet"

    @staticmethod
    def from_dict(data: dict) -> PoolConfig:
        return PoolConfig(
            min_workers=data.get("min_workers", 1),
            max_workers=data.get("max_workers", 3),
            default_model=data.get("default_model", "sonnet"),
        )


@dataclass
class DaemonConfig:
    """Configuration for the scalable daemon."""

    control_port: int = 9100
    poll_interval: int = 30
    lease_ttl: int = 600
    pools: dict[str, PoolConfig] = field(default_factory=dict)
    routing_rules: list[dict] = field(default_factory=list)

    @staticmethod
    def default() -> DaemonConfig:
        """Create a default configuration with standard pool sizes."""
        return DaemonConfig(
            control_port=9100,
            poll_interval=30,
            lease_ttl=600,
            pools={
                "coding": PoolConfig(min_workers=1, max_workers=3, default_model="sonnet"),
                "review": PoolConfig(min_workers=1, max_workers=1, default_model="haiku"),
                "linear": PoolConfig(min_workers=1, max_workers=1, default_model="haiku"),
            },
            routing_rules=[
                {"match": {"labels": ["review"]}, "pool": "review", "model": "haiku"},
                {"match": {"labels": ["linear", "triage"]}, "pool": "linear", "model": "haiku"},
                {"match": {"complexity": "high"}, "pool": "coding", "model": "opus"},
                {"match": {"complexity": "low"}, "pool": "coding", "model": "haiku"},
            ],
        )

    @staticmethod
    def from_file(path: Path) -> DaemonConfig:
        """Load configuration from a JSON file."""
        data = json.loads(path.read_text())
        pools = {}
        for name, pool_data in data.get("pools", {}).items():
            pools[name] = PoolConfig.from_dict(pool_data)

        return DaemonConfig(
            control_port=data.get("control_port", 9100),
            poll_interval=data.get("poll_interval", 30),
            lease_ttl=data.get("lease_ttl", 600),
            pools=pools,
            routing_rules=data.get("routing_rules", []),
        )


# ---------------------------------------------------------------------------
# Worker Pool
# ---------------------------------------------------------------------------


@dataclass
class WorkerPool:
    """A pool of typed workers."""

    pool_type: PoolType
    config: PoolConfig
    workers: list[TypedWorker] = field(default_factory=list)

    def add_worker(self) -> TypedWorker | None:
        """Add a worker to the pool if under max_workers. Returns the new worker or None."""
        if len(self.workers) >= self.config.max_workers:
            return None
        worker_id = f"{self.pool_type.value}-{len(self.workers)}"
        worker = TypedWorker(worker_id=worker_id, pool_type=self.pool_type)
        self.workers.append(worker)
        return worker

    def get_idle_workers(self) -> list[TypedWorker]:
        """Get workers that are currently idle."""
        return [w for w in self.workers if w.is_idle]


# ---------------------------------------------------------------------------
# Worker Pool Manager
# ---------------------------------------------------------------------------


class WorkerPoolManager:
    """Manages multiple typed worker pools with ticket leasing and event queue."""

    def __init__(self, config: DaemonConfig) -> None:
        self.config = config
        self.pools: dict[PoolType, WorkerPool] = {}
        self._leases: dict[str, TicketLease] = {}  # ticket_key -> lease
        # Event queue for webhook-driven dispatch (Proposal 9)
        self.ticket_queue: asyncio.Queue[Ticket] = asyncio.Queue()

    def initialize_pools(self) -> None:
        """Create pools and spawn initial workers based on config."""
        for pool_name, pool_config in self.config.pools.items():
            try:
                pool_type = PoolType(pool_name)
            except ValueError:
                logger.warning("Unknown pool type '%s' — skipping", pool_name)
                continue

            pool = WorkerPool(pool_type=pool_type, config=pool_config)
            for _ in range(pool_config.min_workers):
                pool.add_worker()
            self.pools[pool_type] = pool
            logger.info(
                "Initialized %s pool: %d workers (min=%d, max=%d, model=%s)",
                pool_name,
                len(pool.workers),
                pool_config.min_workers,
                pool_config.max_workers,
                pool_config.default_model,
            )

    def get_idle_workers(self, pool_type: PoolType | None = None) -> list[TypedWorker]:
        """Get idle workers, optionally filtered by pool type."""
        if pool_type is not None:
            pool = self.pools.get(pool_type)
            if pool is None:
                return []
            return pool.get_idle_workers()

        idle: list[TypedWorker] = []
        for pool in self.pools.values():
            idle.extend(pool.get_idle_workers())
        return idle

    def claim_ticket(self, ticket: Ticket, worker: TypedWorker) -> None:
        """Create a lease for a ticket assigned to a worker.

        Raises:
            ValueError: If the ticket is already leased.
        """
        if ticket.key in self._leases:
            raise ValueError(f"Ticket '{ticket.key}' is already leased")

        self._leases[ticket.key] = TicketLease(
            ticket_key=ticket.key,
            worker_id=worker.worker_id,
            acquired_at=datetime.now(UTC),
            ttl=self.config.lease_ttl,
        )

    def release_ticket(self, ticket_key: str) -> None:
        """Release the lease on a ticket."""
        self._leases.pop(ticket_key, None)

    def get_expired_leases(self) -> list[TicketLease]:
        """Return all leases that have exceeded their TTL."""
        return [lease for lease in self._leases.values() if lease.is_expired]

    def resize_pool(self, pool_type: PoolType, max_workers: int) -> None:
        """Resize a pool's max_workers. Adds workers if below new min."""
        pool = self.pools.get(pool_type)
        if pool is None:
            raise KeyError(f"Pool '{pool_type.value}' not found")

        pool.config.max_workers = max_workers
        # Add workers up to min_workers if needed
        while len(pool.workers) < pool.config.min_workers:
            pool.add_worker()

    def status_summary(self) -> dict:
        """Return a status summary of all pools."""
        total_workers = 0
        pools_info: dict[str, dict] = {}

        for pool_type, pool in self.pools.items():
            idle = len(pool.get_idle_workers())
            busy = len(pool.workers) - idle
            total_workers += len(pool.workers)
            pools_info[pool_type.value] = {
                "worker_count": len(pool.workers),
                "idle": idle,
                "busy": busy,
                "default_model": pool.config.default_model,
                "max_workers": pool.config.max_workers,
            }

        return {
            "total_workers": total_workers,
            "pools": pools_info,
            "active_leases": len(self._leases),
        }
