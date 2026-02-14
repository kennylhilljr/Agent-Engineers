"""
Ticket Daemon
=============

A long-running daemon that polls Linear for available tickets and
dispatches agent workers to process them concurrently. Ensures agents are
always working on tickets around the clock.

Usage:
    uv run python scripts/daemon.py --project-dir my-app
    uv run python scripts/daemon.py --project-dir my-app --max-workers 3 --poll-interval 60
"""

import asyncio
import logging
import os
import signal
import sys
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

# Add repo root to path so we can import top-level modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from agent import (
    SESSION_COMPLETE,
    SESSION_ERROR,
    SessionResult,
    run_agent_session,
)
from client import create_client
from progress import (
    is_project_initialized,
)
from prompts import copy_spec_to_project, get_continuation_task, get_initializer_task

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("daemon")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Available models
AVAILABLE_MODELS: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-5-20250929",
    "opus": "claude-opus-4-5-20251101",
}

# Default polling interval in seconds
DEFAULT_POLL_INTERVAL: int = 30

# Default maximum concurrent workers
DEFAULT_MAX_WORKERS: int = 3

# Delay between retries on error
ERROR_RETRY_DELAY: int = 30

# Maximum consecutive errors before backing off
MAX_CONSECUTIVE_ERRORS: int = 5

# Back-off ceiling in seconds after repeated errors
BACKOFF_CEILING: int = 300

# Cooldown after a worker finishes a ticket before it can pick up a new one
WORKER_COOLDOWN: int = 0


# ---------------------------------------------------------------------------
# Ticket representation
# ---------------------------------------------------------------------------

TicketStatus = Literal["todo", "in_progress", "review", "done"]


@dataclass
class Ticket:
    """A ticket from Linear that can be worked on."""

    key: str
    title: str
    description: str
    status: TicketStatus
    priority: str = "medium"
    test_steps: list[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Ticket):
            return NotImplemented
        return self.key == other.key


# ---------------------------------------------------------------------------
# Linear poller
# ---------------------------------------------------------------------------


def _poll_linear_tickets(project_dir: Path) -> list[Ticket]:
    """
    Poll Linear for actionable tickets.

    Since Linear uses MCP tools (not direct REST), we return a sentinel
    indicating the orchestrator should query Linear itself.
    """
    # Linear doesn't have a direct REST API we can call outside of MCP.
    # Instead, we return a single synthetic ticket that tells the orchestrator
    # to check Linear for available work. The orchestrator's continuation task
    # already handles this.
    return [
        Ticket(
            key="LINEAR_CHECK",
            title="Check Linear for available tickets",
            description=(
                "The daemon detected Linear is the tracker. "
                "Run a continuation session to check for work."
            ),
            status="todo",
        )
    ]


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


@dataclass
class WorkerState:
    """Tracks the state of a single agent worker."""

    worker_id: int
    current_ticket: Ticket | None = None
    busy: bool = False
    tickets_completed: int = 0
    consecutive_errors: int = 0
    started_at: datetime | None = None


async def run_worker(
    worker: WorkerState,
    project_dir: Path,
    model: str,
    ticket: Ticket,
) -> SessionResult:
    """
    Run a single agent worker session on a ticket.

    The worker creates a fresh SDK client, sends the continuation task
    (which includes the full orchestrator flow), and processes until
    the ticket is done or the session ends.

    Args:
        worker: Worker state tracking object
        project_dir: Project directory
        model: Model ID to use
        ticket: The ticket to work on

    Returns:
        SessionResult indicating outcome
    """
    worker.busy = True
    worker.current_ticket = ticket
    worker.started_at = datetime.now(UTC)

    logger.info(
        "Worker %d picking up %s: %s",
        worker.worker_id,
        ticket.key,
        ticket.title,
    )

    try:
        client = create_client(project_dir, model)

        # Use the standard continuation task which drives the full orchestrator flow
        prompt = get_continuation_task(project_dir)

        result: SessionResult = SessionResult(status=SESSION_ERROR, response="uninitialized")
        try:
            async with client:
                result = await run_agent_session(client, prompt, project_dir)
        except ConnectionError as e:
            logger.error("Worker %d connection error: %s", worker.worker_id, e)
            result = SessionResult(status=SESSION_ERROR, response=str(e))
        except Exception as e:
            logger.error("Worker %d unexpected error: %s", worker.worker_id, e)
            traceback.print_exc()
            result = SessionResult(status=SESSION_ERROR, response=str(e))

        if result.status == SESSION_ERROR:
            worker.consecutive_errors += 1
            logger.warning(
                "Worker %d error on %s (attempt %d): %s",
                worker.worker_id,
                ticket.key,
                worker.consecutive_errors,
                result.response[:200],
            )
        else:
            worker.consecutive_errors = 0
            worker.tickets_completed += 1
            logger.info(
                "Worker %d finished %s (status=%s, total_completed=%d)",
                worker.worker_id,
                ticket.key,
                result.status,
                worker.tickets_completed,
            )

        return result

    finally:
        worker.busy = False
        worker.current_ticket = None
        worker.started_at = None


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------


class TicketDaemon:
    """
    Long-running daemon that polls for tickets and dispatches workers.

    The daemon:
    1. Polls Linear at regular intervals for actionable tickets
    2. Assigns tickets to idle workers (up to max_workers concurrently)
    3. Tracks which tickets are being worked on to avoid duplicates
    4. Retries with exponential backoff on errors
    5. Runs until explicitly stopped (SIGINT/SIGTERM)
    """

    def __init__(
        self,
        project_dir: Path,
        model: str,
        max_workers: int = DEFAULT_MAX_WORKERS,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self.project_dir = project_dir
        self.model = model
        self.max_workers = max_workers
        self.poll_interval = poll_interval

        # Worker pool
        self.workers: list[WorkerState] = [WorkerState(worker_id=i) for i in range(max_workers)]

        # Tickets currently being processed (keys)
        self.active_ticket_keys: set[str] = set()

        # Running worker tasks
        self._worker_tasks: dict[int, asyncio.Task[None]] = {}

        # Shutdown flag
        self._shutdown = asyncio.Event()

        # Stats
        self.total_tickets_processed: int = 0
        self.daemon_start_time: datetime | None = None
        self.poll_count: int = 0
        self.consecutive_poll_errors: int = 0

    @property
    def idle_workers(self) -> list[WorkerState]:
        """Get workers that are not currently busy."""
        return [w for w in self.workers if not w.busy]

    @property
    def busy_workers(self) -> list[WorkerState]:
        """Get workers that are currently processing tickets."""
        return [w for w in self.workers if w.busy]

    def _print_status(self) -> None:
        """Print current daemon status."""
        busy = self.busy_workers
        idle = self.idle_workers

        logger.info(
            "Status: %d/%d workers busy, %d tickets processed, poll #%d",
            len(busy),
            self.max_workers,
            self.total_tickets_processed,
            self.poll_count,
        )

        for w in busy:
            ticket_info = (
                f"{w.current_ticket.key}: {w.current_ticket.title}"
                if w.current_ticket
                else "unknown"
            )
            logger.info("  Worker %d: BUSY — %s", w.worker_id, ticket_info)
        for w in idle:
            logger.info(
                "  Worker %d: IDLE (completed %d tickets)", w.worker_id, w.tickets_completed
            )

    def _poll_tickets(self) -> list[Ticket]:
        """Poll for available tickets from Linear."""
        return _poll_linear_tickets(self.project_dir)

    def _filter_actionable_tickets(self, tickets: list[Ticket]) -> list[Ticket]:
        """Filter out tickets that are already being worked on."""
        return [t for t in tickets if t.key not in self.active_ticket_keys]

    async def _run_worker_task(self, worker: WorkerState, ticket: Ticket) -> None:
        """Wrapper that runs a worker and cleans up when done."""
        self.active_ticket_keys.add(ticket.key)
        try:
            result = await run_worker(worker, self.project_dir, self.model, ticket)

            if result.status == SESSION_COMPLETE:
                logger.info("Worker %d reports PROJECT_COMPLETE", worker.worker_id)
                # Don't shut down — there may be new tickets added later.
                # Just log it.

            self.total_tickets_processed += 1

        except Exception as e:
            logger.error("Worker %d crashed: %s", worker.worker_id, e)
            traceback.print_exc()
            worker.consecutive_errors += 1
        finally:
            self.active_ticket_keys.discard(ticket.key)
            # Remove task reference
            self._worker_tasks.pop(worker.worker_id, None)
            # Brief cooldown before worker can pick up next ticket
            await asyncio.sleep(WORKER_COOLDOWN)

    def _dispatch_tickets(self, tickets: list[Ticket]) -> int:
        """
        Assign tickets to idle workers.

        Returns the number of tickets dispatched.
        """
        dispatched = 0
        idle = self.idle_workers

        for ticket in tickets:
            if not idle:
                break

            # Skip if worker has too many consecutive errors (back off)
            worker = idle.pop(0)
            if worker.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                backoff = min(
                    ERROR_RETRY_DELAY * (2**worker.consecutive_errors),
                    BACKOFF_CEILING,
                )
                logger.warning(
                    "Worker %d has %d consecutive errors, backing off %ds",
                    worker.worker_id,
                    worker.consecutive_errors,
                    backoff,
                )
                # Reset after backoff period (handled by next poll cycle)
                worker.consecutive_errors = 0
                continue

            # Launch worker task
            task = asyncio.create_task(
                self._run_worker_task(worker, ticket),
                name=f"worker-{worker.worker_id}-{ticket.key}",
            )
            self._worker_tasks[worker.worker_id] = task
            dispatched += 1

        return dispatched

    async def _ensure_initialized(self) -> bool:
        """
        Ensure the project is initialized. Run initialization if needed.

        Returns True if project is ready, False if initialization failed.
        """
        if is_project_initialized(self.project_dir):
            return True

        logger.info("Project not initialized — running initialization session...")
        self.project_dir.mkdir(parents=True, exist_ok=True)
        copy_spec_to_project(self.project_dir)

        try:
            client = create_client(self.project_dir, self.model)
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

    async def run(self) -> None:
        """
        Main daemon loop.

        Polls for tickets, dispatches workers, and runs until shutdown.
        """
        self.daemon_start_time = datetime.now(UTC)

        logger.info("=" * 70)
        logger.info("  TICKET DAEMON STARTED")
        logger.info("=" * 70)
        logger.info("Project directory: %s", self.project_dir)
        logger.info("Model: %s", self.model)
        logger.info("Max workers: %d", self.max_workers)
        logger.info("Poll interval: %ds", self.poll_interval)
        logger.info("Tracker: Linear")
        logger.info("=" * 70)

        # Ensure project is initialized
        if not await self._ensure_initialized():
            logger.error("Failed to initialize project — cannot start daemon")
            return

        while not self._shutdown.is_set():
            self.poll_count += 1

            try:
                # Poll for tickets
                all_tickets = self._poll_tickets()
                actionable = self._filter_actionable_tickets(all_tickets)

                logger.info(
                    "Poll #%d: %d total tickets, %d actionable, %d workers idle",
                    self.poll_count,
                    len(all_tickets),
                    len(actionable),
                    len(self.idle_workers),
                )

                # Dispatch to idle workers
                if actionable and self.idle_workers:
                    dispatched = self._dispatch_tickets(actionable)
                    if dispatched:
                        logger.info("Dispatched %d tickets to workers", dispatched)
                elif not actionable and not self.busy_workers:
                    logger.info("No actionable tickets and no busy workers — waiting...")

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

            # Print status
            self._print_status()

            # Wait for next poll interval or shutdown
            try:
                await asyncio.wait_for(
                    self._shutdown.wait(),
                    timeout=self.poll_interval,
                )
                # If we get here, shutdown was signaled
                break
            except TimeoutError:
                # Normal — poll interval elapsed
                pass

        # Graceful shutdown
        await self._shutdown_gracefully()

    async def _shutdown_gracefully(self) -> None:
        """Wait for active workers to finish and clean up."""
        logger.info("Shutting down daemon...")

        if self._worker_tasks:
            logger.info(
                "Waiting for %d active workers to finish...",
                len(self._worker_tasks),
            )
            # Give workers a chance to finish naturally
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

        # Print final stats
        logger.info("=" * 70)
        logger.info("  DAEMON STOPPED")
        logger.info("=" * 70)
        logger.info("Total tickets processed: %d", self.total_tickets_processed)
        logger.info("Total polls: %d", self.poll_count)
        if self.daemon_start_time:
            uptime = datetime.now(UTC) - self.daemon_start_time
            logger.info("Uptime: %s", uptime)
        for w in self.workers:
            logger.info(
                "  Worker %d: %d tickets completed",
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
    """
    Main entry point for the ticket daemon.

    Returns:
        Exit code (0 for success, 1 for error, 130 for keyboard interrupt)
    """
    import argparse

    # Default base path for generated projects
    default_generations_base = Path(os.environ.get("GENERATIONS_BASE_PATH", "./generations"))

    default_model = os.environ.get("ORCHESTRATOR_MODEL", "haiku").lower()
    if default_model not in AVAILABLE_MODELS:
        default_model = "haiku"

    parser = argparse.ArgumentParser(
        description="Ticket Daemon — Continuously polls for tickets and dispatches agent workers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start daemon for an existing project
  uv run python scripts/daemon.py --project-dir my-app

  # Start with 5 concurrent workers and 60s poll interval
  uv run python scripts/daemon.py --project-dir my-app --max-workers 5 --poll-interval 60

  # Use sonnet model for orchestrator
  uv run python scripts/daemon.py --project-dir my-app --model sonnet

Environment Variables:
  ARCADE_API_KEY             Arcade API key (required)
  ARCADE_GATEWAY_SLUG        MCP gateway slug (required)
  ORCHESTRATOR_MODEL         Default orchestrator model
  DAEMON_MAX_WORKERS         Default max workers (overridden by --max-workers)
  DAEMON_POLL_INTERVAL       Default poll interval in seconds (overridden by --poll-interval)
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
        "--max-workers",
        type=int,
        default=int(os.environ.get("DAEMON_MAX_WORKERS", str(DEFAULT_MAX_WORKERS))),
        help=f"Maximum concurrent agent workers (default: {DEFAULT_MAX_WORKERS})",
    )

    parser.add_argument(
        "--poll-interval",
        type=int,
        default=int(os.environ.get("DAEMON_POLL_INTERVAL", str(DEFAULT_POLL_INTERVAL))),
        help=f"Seconds between ticket polls (default: {DEFAULT_POLL_INTERVAL})",
    )

    parser.add_argument(
        "--model",
        type=str,
        choices=list(AVAILABLE_MODELS.keys()),
        default=default_model,
        help=f"Orchestrator model (default: {default_model})",
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

    model_id = AVAILABLE_MODELS[args.model]

    # Create daemon
    daemon = TicketDaemon(
        project_dir=project_dir,
        model=model_id,
        max_workers=args.max_workers,
        poll_interval=args.poll_interval,
    )

    # Set up signal handlers for graceful shutdown
    loop = asyncio.new_event_loop()

    def handle_signal(sig: int, frame: object) -> None:
        logger.info("Received signal %s", signal.Signals(sig).name)
        daemon.request_shutdown()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        loop.run_until_complete(daemon.run())
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
    import sys

    sys.exit(main())
