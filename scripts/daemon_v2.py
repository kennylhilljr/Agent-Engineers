"""
Scalable Ticket Daemon (v2)
============================

A long-running daemon with typed worker pools, git worktree isolation,
complexity-based model routing, and an HTTP control plane for dynamic scaling.

This replaces daemon.py for parallel operation while keeping backward
compatibility (daemon.py still works for single-threaded use).

Usage:
    uv run python scripts/daemon_v2.py --project-dir my-app
    uv run python scripts/daemon_v2.py --project-dir my-app --config daemon_config.json
    uv run python scripts/daemon_v2.py --project-dir my-app --control-port 9100
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

# Add repo root to path so we can import top-level modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from agent import (
    SESSION_COMPLETE,
    SESSION_ERROR,
    SessionResult,
    run_agent_session,
)
from agents.definitions import create_agent_definitions_for_pool
from client import create_client
from daemon.control_plane import ControlPlane
from daemon.ticket_router import TicketRouter
from daemon.worker_pool import (
    AVAILABLE_MODELS,
    DaemonConfig,
    PoolType,
    Ticket,
    TypedWorker,
    WorkerPoolManager,
    WorkerStatus,
)
from daemon.worktree import WorktreeError, WorktreeManager
from progress import is_project_initialized
from prompts import copy_spec_to_project, get_continuation_task, get_initializer_task

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("daemon_v2")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CONSECUTIVE_ERRORS: int = 5
BACKOFF_CEILING: int = 300
ERROR_RETRY_DELAY: int = 30
WORKER_COOLDOWN: int = 0


# ---------------------------------------------------------------------------
# Scalable Daemon
# ---------------------------------------------------------------------------


class ScalableDaemon:
    """
    Scalable ticket daemon with typed worker pools.

    Key improvements over daemon.py:
    - Typed worker pools (coding, review, linear) with named workers
    - Git worktree isolation for parallel coding workers
    - Complexity-based model routing (haiku/sonnet/opus per ticket)
    - HTTP control plane for runtime management
    - Ticket leases with TTL to prevent stuck tickets
    - SIGHUP config reload without restart
    """

    def __init__(
        self,
        project_dir: Path,
        config: DaemonConfig,
    ) -> None:
        self.project_dir = project_dir
        self.config = config

        # Core subsystems
        self.pool_manager = WorkerPoolManager(config)
        self.worktree_manager = WorktreeManager(project_dir)
        self.ticket_router = TicketRouter.from_rule_dicts(config.routing_rules)
        self.control_plane = ControlPlane(
            pool_manager=self.pool_manager,
            port=config.control_port,
        )

        # Active worker tasks
        self._worker_tasks: dict[str, asyncio.Task] = {}

        # Shutdown flag
        self._shutdown = asyncio.Event()

        # Stats
        self.total_tickets_processed: int = 0
        self.daemon_start_time: datetime | None = None
        self.poll_count: int = 0
        self.consecutive_poll_errors: int = 0

        # Track tickets being processed (by key)
        self._active_ticket_keys: set[str] = set()

    # --- Initialization ---

    async def _ensure_initialized(self) -> bool:
        """Ensure the project is initialized. Run initialization if needed."""
        if is_project_initialized(self.project_dir):
            return True

        logger.info("Project not initialized — running initialization session...")
        self.project_dir.mkdir(parents=True, exist_ok=True)
        copy_spec_to_project(self.project_dir)

        model_id = AVAILABLE_MODELS.get("sonnet", AVAILABLE_MODELS["sonnet"])

        try:
            client = create_client(self.project_dir, model_id)
            prompt = get_initializer_task(self.project_dir)
            async with client:
                result = await run_agent_session(client, prompt, self.project_dir)

            if result.status == SESSION_ERROR:
                logger.error("Initialization failed: %s", result.response[:500])
                return False

            logger.info("Project initialized successfully")
            return True

        except Exception as e:
            logger.error("Initialization error: %s", e)
            traceback.print_exc()
            return False

    def _initialize_pools(self) -> None:
        """Create initial workers for each pool based on config."""
        self.pool_manager.initialize_pools()

    # --- Worker execution ---

    async def _run_coding_worker(
        self,
        worker: TypedWorker,
        ticket: Ticket,
    ) -> SessionResult:
        """Run a coding worker session with worktree isolation."""
        branch_name = self.worktree_manager.get_branch_for_ticket(ticket.key, ticket.title)

        try:
            worktree_path = self.worktree_manager.create_worktree(worker.worker_id, branch_name)
            worker.worktree_path = worktree_path
        except WorktreeError as e:
            logger.error("%s failed to create worktree: %s", worker.worker_id, e)
            return SessionResult(status=SESSION_ERROR, response=str(e))

        try:
            port = self.worktree_manager.allocate_port()
            worker.port = port
        except WorktreeError as e:
            logger.warning("%s no free port: %s", worker.worker_id, e)
            port = None

        try:
            _, model_id = self.ticket_router.route_and_select(ticket, self.pool_manager.pools)

            model_name = None
            for name, mid in AVAILABLE_MODELS.items():
                if mid == model_id:
                    model_name = name
                    break

            agent_defs = create_agent_definitions_for_pool(
                coding_model=model_name,
            )

            client = create_client(
                project_dir=self.project_dir,
                model=model_id,
                cwd=worktree_path,
                agent_overrides=agent_defs,
            )

            prompt = get_continuation_task(self.project_dir)

            logger.info(
                "%s running on %s (branch=%s, model=%s, port=%s)",
                worker.worker_id,
                ticket.key,
                branch_name,
                model_name or model_id,
                port,
            )

            result: SessionResult
            try:
                async with client:
                    result = await run_agent_session(client, prompt, self.project_dir)
            except Exception as e:
                logger.error("%s session error: %s", worker.worker_id, e)
                traceback.print_exc()
                result = SessionResult(status=SESSION_ERROR, response=str(e))

            if result.status != SESSION_ERROR:
                merged = self.worktree_manager.merge_to_main(branch_name)
                if merged:
                    logger.info("%s merged %s to main", worker.worker_id, branch_name)
                else:
                    logger.warning(
                        "%s merge conflict on %s — leaving branch for manual review",
                        worker.worker_id,
                        branch_name,
                    )

            return result

        finally:
            try:
                self.worktree_manager.remove_worktree(worker.worker_id)
            except WorktreeError as e:
                logger.warning("%s worktree cleanup failed: %s", worker.worker_id, e)
            if port is not None:
                self.worktree_manager.release_port(port)
            worker.worktree_path = None
            worker.port = None

    async def _run_standard_worker(
        self,
        worker: TypedWorker,
        ticket: Ticket,
    ) -> SessionResult:
        """Run a non-coding worker (review, linear) in the main project dir."""
        _, model_id = self.ticket_router.route_and_select(ticket, self.pool_manager.pools)

        client = create_client(self.project_dir, model_id)
        prompt = get_continuation_task(self.project_dir)

        logger.info(
            "%s running on %s (model=%s)",
            worker.worker_id,
            ticket.key,
            model_id,
        )

        try:
            async with client:
                return await run_agent_session(client, prompt, self.project_dir)
        except Exception as e:
            logger.error("%s session error: %s", worker.worker_id, e)
            traceback.print_exc()
            return SessionResult(status=SESSION_ERROR, response=str(e))

    async def _run_worker_task(
        self,
        worker: TypedWorker,
        ticket: Ticket,
    ) -> None:
        """Wrapper that runs a worker session and cleans up state."""
        worker.status = WorkerStatus.EXECUTING
        worker.current_ticket = ticket
        worker.started_at = datetime.now(UTC)
        self._active_ticket_keys.add(ticket.key)

        try:
            self.pool_manager.claim_ticket(ticket, worker)
        except ValueError as e:
            logger.warning("Could not claim %s: %s", ticket.key, e)
            return

        try:
            if worker.pool_type == PoolType.CODING:
                result = await self._run_coding_worker(worker, ticket)
            else:
                result = await self._run_standard_worker(worker, ticket)

            if result.status == SESSION_ERROR:
                worker.consecutive_errors += 1
                logger.warning(
                    "%s error on %s (attempt %d): %s",
                    worker.worker_id,
                    ticket.key,
                    worker.consecutive_errors,
                    result.response[:200],
                )
            else:
                worker.consecutive_errors = 0
                worker.tickets_completed += 1
                self.total_tickets_processed += 1
                logger.info(
                    "%s finished %s (status=%s, total=%d)",
                    worker.worker_id,
                    ticket.key,
                    result.status,
                    worker.tickets_completed,
                )

            if result.status == SESSION_COMPLETE:
                logger.info(
                    "%s reports PROJECT_COMPLETE for %s",
                    worker.worker_id,
                    ticket.key,
                )

        except Exception as e:
            logger.error("%s crashed: %s", worker.worker_id, e)
            traceback.print_exc()
            worker.consecutive_errors += 1

        finally:
            self.pool_manager.release_ticket(ticket.key)
            self._active_ticket_keys.discard(ticket.key)
            worker.status = WorkerStatus.IDLE
            worker.current_ticket = None
            worker.started_at = None
            self._worker_tasks.pop(worker.worker_id, None)

            await asyncio.sleep(WORKER_COOLDOWN)

    # --- Ticket polling and dispatch ---

    def _drain_event_queue(self) -> list[Ticket]:
        """Drain all tickets from the webhook event queue (Proposal 9)."""
        queued: list[Ticket] = []
        while not self.pool_manager.ticket_queue.empty():
            try:
                ticket = self.pool_manager.ticket_queue.get_nowait()
                queued.append(ticket)
            except asyncio.QueueEmpty:
                break
        return queued

    def _poll_tickets(self) -> list[Ticket]:
        """Poll for actionable tickets.

        First drains the webhook event queue for immediate dispatch.
        Falls back to synthetic LINEAR_CHECK if queue is empty.
        """
        # Drain webhook-delivered tickets first (instant, no latency)
        queued = self._drain_event_queue()
        if queued:
            logger.info("Event queue: %d tickets from webhooks", len(queued))
            return queued

        # Fallback: synthetic check (polling mode)
        return [
            Ticket(
                key="LINEAR_CHECK",
                title="Check Linear for available tickets",
                description="Run a continuation session to check for work.",
                status="todo",
            )
        ]

    def _filter_actionable_tickets(self, tickets: list[Ticket]) -> list[Ticket]:
        """Filter out tickets already being worked on."""
        return [t for t in tickets if t.key not in self._active_ticket_keys]

    def _dispatch_tickets(self, tickets: list[Ticket]) -> int:
        """Assign tickets to idle workers across pools."""
        dispatched = 0

        for ticket in tickets:
            pool_type = self.ticket_router.route(ticket)
            idle = self.pool_manager.get_idle_workers(pool_type)

            if not idle and pool_type != PoolType.CODING:
                idle = self.pool_manager.get_idle_workers(PoolType.CODING)

            if not idle:
                logger.debug("No idle workers for %s (pool=%s)", ticket.key, pool_type.value)
                continue

            worker = min(idle, key=lambda w: w.consecutive_errors)

            if worker.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                backoff = min(
                    ERROR_RETRY_DELAY * (2**worker.consecutive_errors),
                    BACKOFF_CEILING,
                )
                logger.warning(
                    "%s has %d consecutive errors, backing off %ds",
                    worker.worker_id,
                    worker.consecutive_errors,
                    backoff,
                )
                worker.consecutive_errors = 0
                continue

            task = asyncio.create_task(
                self._run_worker_task(worker, ticket),
                name=f"{worker.worker_id}-{ticket.key}",
            )
            self._worker_tasks[worker.worker_id] = task
            dispatched += 1

        return dispatched

    # --- Lease maintenance ---

    async def _maintain_leases(self) -> None:
        """Check for expired leases and recover stuck tickets."""
        expired = self.pool_manager.get_expired_leases()
        for lease in expired:
            logger.warning(
                "Lease expired for ticket '%s' (worker=%s) — releasing",
                lease.ticket_key,
                lease.worker_id,
            )
            self.pool_manager.release_ticket(lease.ticket_key)
            self._active_ticket_keys.discard(lease.ticket_key)

    # --- Status ---

    def _print_status(self) -> None:
        """Print current daemon status."""
        summary = self.pool_manager.status_summary()
        total_workers = summary.get("total_workers", 0)
        pools_info = summary.get("pools", {})

        logger.info(
            "Status: %d workers total, %d tickets processed, poll #%d",
            total_workers,
            self.total_tickets_processed,
            self.poll_count,
        )

        for pool_name, info in pools_info.items():
            info.get("idle", 0)
            busy = info.get("busy", 0)
            total = info.get("worker_count", 0)
            logger.info(
                "  Pool %s: %d/%d busy, model=%s",
                pool_name,
                busy,
                total,
                info.get("default_model", "?"),
            )

        for pool_type, pool in self.pool_manager.pools.items():
            for w in pool.workers:
                if w.current_ticket:
                    logger.info(
                        "  %s: BUSY — %s: %s",
                        w.worker_id,
                        w.current_ticket.key,
                        w.current_ticket.title,
                    )

    # --- Config reload ---

    def _reload_config(self, config_path: Path | None) -> None:
        """Reload configuration from file (triggered by SIGHUP)."""
        if not config_path or not config_path.exists():
            logger.warning("No config file to reload")
            return

        try:
            new_config = DaemonConfig.from_file(config_path)
            self.config = new_config

            for pool_name, pool_config in new_config.pools.items():
                try:
                    pool_type = PoolType(pool_name)
                    self.pool_manager.resize_pool(pool_type, pool_config.max_workers)
                    logger.info(
                        "Resized %s pool: max=%d",
                        pool_name,
                        pool_config.max_workers,
                    )
                except (ValueError, KeyError):
                    pass

            self.ticket_router = TicketRouter.from_rule_dicts(new_config.routing_rules)

            logger.info("Configuration reloaded successfully")

        except Exception as e:
            logger.error("Config reload failed: %s", e)

    # --- Main loop ---

    async def run(self, config_path: Path | None = None) -> None:
        """Main daemon loop."""
        self.daemon_start_time = datetime.now(UTC)

        logger.info("=" * 70)
        logger.info("  SCALABLE TICKET DAEMON v2")
        logger.info("=" * 70)
        logger.info("Project directory: %s", self.project_dir)
        logger.info("Control plane: http://127.0.0.1:%d", self.config.control_port)
        logger.info("Poll interval: %ds", self.config.poll_interval)
        logger.info("Lease TTL: %ds", self.config.lease_ttl)

        for pool_name, pool_cfg in self.config.pools.items():
            logger.info(
                "  Pool %s: min=%d, max=%d, model=%s",
                pool_name,
                pool_cfg.min_workers,
                pool_cfg.max_workers,
                pool_cfg.default_model,
            )
        logger.info("=" * 70)

        if not await self._ensure_initialized():
            logger.error("Failed to initialize project — cannot start daemon")
            return

        self._initialize_pools()

        try:
            await self.control_plane.start()
        except Exception as e:
            logger.warning("Control plane failed to start: %s", e)

        while not self._shutdown.is_set():
            self.poll_count += 1

            try:
                await self._maintain_leases()

                all_tickets = self._poll_tickets()
                actionable = self._filter_actionable_tickets(all_tickets)

                logger.info(
                    "Poll #%d: %d total, %d actionable, %d idle workers",
                    self.poll_count,
                    len(all_tickets),
                    len(actionable),
                    len(self.pool_manager.get_idle_workers()),
                )

                if actionable and self.pool_manager.get_idle_workers():
                    dispatched = self._dispatch_tickets(actionable)
                    if dispatched:
                        logger.info("Dispatched %d tickets", dispatched)

                self.consecutive_poll_errors = 0

            except Exception as e:
                self.consecutive_poll_errors += 1
                backoff = min(
                    ERROR_RETRY_DELAY * (2**self.consecutive_poll_errors),
                    BACKOFF_CEILING,
                )
                logger.error(
                    "Poll error (attempt %d, backoff %ds): %s",
                    self.consecutive_poll_errors,
                    backoff,
                    e,
                )
                await asyncio.sleep(backoff)
                continue

            self._print_status()

            try:
                await asyncio.wait_for(
                    self._shutdown.wait(),
                    timeout=self.config.poll_interval,
                )
                break
            except TimeoutError:
                pass

        await self._shutdown_gracefully()

    async def _shutdown_gracefully(self) -> None:
        """Wait for active workers to finish and clean up."""
        logger.info("Shutting down daemon...")

        await self.control_plane.stop()

        if self._worker_tasks:
            logger.info(
                "Waiting for %d active workers to finish...",
                len(self._worker_tasks),
            )
            pending = list(self._worker_tasks.values())
            done, still_pending = await asyncio.wait(pending, timeout=60)

            if still_pending:
                logger.warning(
                    "Cancelling %d workers that didn't finish in time",
                    len(still_pending),
                )
                for task in still_pending:
                    task.cancel()
                await asyncio.gather(*still_pending, return_exceptions=True)

        try:
            cleaned = self.worktree_manager.cleanup_stale_worktrees()
            if cleaned:
                logger.info("Cleaned up %d stale worktrees", cleaned)
        except WorktreeError as e:
            logger.warning("Worktree cleanup error: %s", e)

        logger.info("=" * 70)
        logger.info("  DAEMON STOPPED")
        logger.info("=" * 70)
        logger.info("Total tickets processed: %d", self.total_tickets_processed)
        logger.info("Total polls: %d", self.poll_count)
        if self.daemon_start_time:
            uptime = datetime.now(UTC) - self.daemon_start_time
            logger.info("Uptime: %s", uptime)

        for pool_type, pool in self.pool_manager.pools.items():
            for w in pool.workers:
                logger.info(
                    "  %s: %d tickets completed",
                    w.worker_id,
                    w.tickets_completed,
                )
        logger.info("=" * 70)

    def request_shutdown(self) -> None:
        """Signal the daemon to shut down gracefully."""
        logger.info("Shutdown requested")
        self._shutdown.set()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """Main entry point for the scalable daemon."""
    import argparse

    default_generations_base = Path(os.environ.get("GENERATIONS_BASE_PATH", "./generations"))

    parser = argparse.ArgumentParser(
        description="Scalable Ticket Daemon v2 — Typed worker pools with dynamic scaling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start with default config
  uv run python scripts/daemon_v2.py --project-dir my-app

  # Start with custom config file
  uv run python scripts/daemon_v2.py --project-dir my-app --config daemon_config.json

  # Custom control plane port
  uv run python scripts/daemon_v2.py --project-dir my-app --control-port 9200

  # Query control plane
  curl http://localhost:9100/health
  curl http://localhost:9100/workers
  curl http://localhost:9100/pools

  # Add workers at runtime
  curl -X POST http://localhost:9100/workers -d '{"pool": "coding", "count": 2}'

  # Resize pool
  curl -X PATCH http://localhost:9100/pools/coding -d '{"max_workers": 6}'

  # Reload config (send SIGHUP)
  kill -HUP $(pgrep -f daemon_v2)
        """,
    )

    parser.add_argument(
        "--generations-base",
        type=Path,
        default=None,
        help=f"Base directory for generated projects (default: {default_generations_base})",
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        required=True,
        help="Project name or path to monitor for tickets",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to daemon_config.json (default: use built-in defaults)",
    )

    parser.add_argument(
        "--control-port",
        type=int,
        default=int(os.environ.get("DAEMON_CONTROL_PORT", "9100")),
        help="Control plane HTTP port (default: 9100)",
    )

    parser.add_argument(
        "--poll-interval",
        type=int,
        default=None,
        help="Override poll interval from config (seconds)",
    )

    args = parser.parse_args()

    # Validate environment
    arcade_key = os.environ.get("ARCADE_API_KEY")
    if not arcade_key:
        print("Error: ARCADE_API_KEY environment variable not set")
        return 1

    # Resolve project directory
    generations_base = args.generations_base or default_generations_base
    if not generations_base.is_absolute():
        generations_base = Path.cwd() / generations_base

    project_dir = args.project_dir
    if not project_dir.is_absolute():
        project_name = str(project_dir).lstrip("./")
        project_dir = generations_base / project_name

    generations_base.mkdir(parents=True, exist_ok=True)

    # Load config
    if args.config and args.config.exists():
        config = DaemonConfig.from_file(args.config)
        logger.info("Loaded config from %s", args.config)
    else:
        config = DaemonConfig.default()
        logger.info("Using default config")

    # Apply CLI overrides
    config.control_port = args.control_port
    if args.poll_interval is not None:
        config.poll_interval = args.poll_interval

    # Create daemon
    daemon = ScalableDaemon(
        project_dir=project_dir,
        config=config,
    )

    # Set up signal handlers
    loop = asyncio.new_event_loop()
    config_path = args.config

    def handle_shutdown(sig: int, frame: object) -> None:
        logger.info("Received signal %s", signal.Signals(sig).name)
        daemon.request_shutdown()

    def handle_reload(sig: int, frame: object) -> None:
        logger.info("Received SIGHUP — reloading config")
        daemon._reload_config(config_path)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGHUP, handle_reload)

    try:
        loop.run_until_complete(daemon.run(config_path=config_path))
        return 0
    except KeyboardInterrupt:
        print("\n\nDaemon interrupted")
        daemon.request_shutdown()
        loop.run_until_complete(daemon._shutdown_gracefully())
        return 130
    except Exception as e:
        logger.error("Fatal error: %s", e)
        traceback.print_exc()
        return 1
    finally:
        loop.close()


if __name__ == "__main__":
    sys.exit(main())
