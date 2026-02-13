#!/usr/bin/env python3
"""
Parallel Dispatch — Multi-Provider Ticket Dispatcher
=====================================================

Queries Jira for To Do tickets, claims one per provider, and launches
parallel workers (Claude + ChatGPT + Gemini + Groq) to implement them
simultaneously.

Usage:
    # Run all 4 providers in parallel
    python scripts/parallel_dispatch.py --project-dir ai-coding-dashboard

    # Specific providers only
    python scripts/parallel_dispatch.py --project-dir ai-coding-dashboard \
        --providers chatgpt gemini groq

    # One round only (default loops)
    python scripts/parallel_dispatch.py --project-dir ai-coding-dashboard --once

    # Dry run
    python scripts/parallel_dispatch.py --project-dir ai-coding-dashboard --dry-run
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Setup path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

from jira_client import JiraClient


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALL_PROVIDERS = ("claude", "chatgpt", "gemini", "groq", "kimi", "windsurf")
NON_CLAUDE_PROVIDERS = ("chatgpt", "gemini", "groq")
CLI_AGENT_PROVIDERS = ("kimi", "windsurf")

# Time between dispatch rounds (seconds)
DISPATCH_INTERVAL = 30

# Max consecutive failures before disabling a provider
MAX_FAILURES = 3

# Worker timeout (seconds) — kill workers that take too long
WORKER_TIMEOUT = 600  # 10 minutes

# Review worker timeout (shorter — reviews are faster than implementations)
REVIEW_WORKER_TIMEOUT = 300  # 5 minutes

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATEFMT = "%Y-%m-%dT%H:%M:%S"

logger = logging.getLogger("parallel_dispatch")


def setup_logging(log_dir: Path) -> None:
    """Configure logging to file + stderr."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "dispatch.log"

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))

    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stderr_handler)


# JiraClient imported from scripts.jira_client


# ---------------------------------------------------------------------------
# Worker tracking
# ---------------------------------------------------------------------------

@dataclass
class WorkerInfo:
    """Tracks a running worker subprocess."""
    provider: str
    ticket_key: str
    process: subprocess.Popen
    started_at: float
    log_file: Optional[str] = None


@dataclass
class ProviderState:
    """Tracks the health state of a provider."""
    consecutive_failures: int = 0
    disabled: bool = False
    last_ticket: Optional[str] = None
    total_completed: int = 0
    total_failed: int = 0


# ---------------------------------------------------------------------------
# Parallel Dispatcher
# ---------------------------------------------------------------------------

class ParallelDispatcher:
    """Dispatches Jira tickets to parallel AI provider workers."""

    def __init__(
        self,
        project_dir: Path,
        providers: tuple[str, ...] = ALL_PROVIDERS,
        dry_run: bool = False,
        once: bool = False,
    ):
        self.project_dir = project_dir.resolve()
        self.providers = providers
        self.dry_run = dry_run
        self.once = once
        self.jira = JiraClient()
        self.workers: dict[str, WorkerInfo] = {}
        self.provider_states: dict[str, ProviderState] = {
            p: ProviderState() for p in providers
        }
        self._shutdown = False

        # Paths
        self.repo_root = Path(__file__).parent.parent
        self.venv_python = self.repo_root / "venv" / "bin" / "python"
        self.log_dir = self.repo_root / "logs"

    def _get_worker_labels(self) -> list[str]:
        """Get all possible worker claim labels."""
        return [f"worker:{p}" for p in ALL_PROVIDERS]

    def _available_providers(self) -> list[str]:
        """Get providers that are idle and not disabled."""
        available = []
        for p in self.providers:
            state = self.provider_states[p]
            if state.disabled:
                continue
            if p in self.workers:
                continue  # Already running
            available.append(p)
        return available

    def _launch_claude_worker(self, ticket_key: str) -> WorkerInfo:
        """Launch a Claude worker via scripts/autonomous_agent_demo.py."""
        log_file = self.log_dir / f"worker_claude_{ticket_key}.log"
        log_handle = open(log_file, "w")

        cmd = [
            str(self.venv_python),
            str(self.repo_root / "scripts" / "autonomous_agent_demo.py"),
            "--project-dir", str(self.project_dir),
            "--max-iterations", "1",
        ]

        logger.info(f"Launching Claude worker for {ticket_key}: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(self.repo_root),
            start_new_session=True,
        )

        return WorkerInfo(
            provider="claude",
            ticket_key=ticket_key,
            process=process,
            started_at=time.time(),
            log_file=str(log_file),
        )

    def _launch_provider_worker(self, provider: str, ticket_key: str) -> WorkerInfo:
        """Launch a non-Claude API-based provider worker (chatgpt/gemini/groq)."""
        log_file = self.log_dir / f"worker_{provider}_{ticket_key}.log"
        log_handle = open(log_file, "w")

        cmd = [
            str(self.venv_python),
            str(self.repo_root / "scripts" / "provider_worker.py"),
            "--provider", provider,
            "--ticket", ticket_key,
            "--project-dir", str(self.project_dir),
        ]
        if self.dry_run:
            cmd.append("--dry-run")

        logger.info(f"Launching {provider} worker for {ticket_key}: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(self.repo_root),
            start_new_session=True,
        )

        return WorkerInfo(
            provider=provider,
            ticket_key=ticket_key,
            process=process,
            started_at=time.time(),
            log_file=str(log_file),
        )

    def _launch_cli_agent_worker(self, provider: str, ticket_key: str) -> WorkerInfo:
        """Launch a CLI-based coding agent worker (kimi/windsurf)."""
        log_file = self.log_dir / f"worker_{provider}_{ticket_key}.log"
        log_handle = open(log_file, "w")

        cmd = [
            str(self.venv_python),
            str(self.repo_root / "scripts" / "cli_agent_worker.py"),
            "--agent", provider,
            "--ticket", ticket_key,
            "--project-dir", str(self.project_dir),
        ]
        if self.dry_run:
            cmd.append("--dry-run")

        logger.info(f"Launching {provider} CLI agent for {ticket_key}: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(self.repo_root),
            start_new_session=True,
        )

        return WorkerInfo(
            provider=provider,
            ticket_key=ticket_key,
            process=process,
            started_at=time.time(),
            log_file=str(log_file),
        )

    def _launch_review_worker(self, ticket_key: str, reviewer: Optional[str] = None) -> WorkerInfo:
        """Launch a review worker for a ticket in Review status."""
        log_file = self.log_dir / f"review_{ticket_key}.log"
        log_handle = open(log_file, "w")

        cmd = [
            str(self.venv_python),
            str(self.repo_root / "scripts" / "review_worker.py"),
            "--ticket", ticket_key,
            "--project-dir", str(self.project_dir),
        ]
        if reviewer:
            cmd.extend(["--reviewer", reviewer])
        if self.dry_run:
            cmd.append("--dry-run")

        logger.info(f"Launching review worker for {ticket_key}: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(self.repo_root),
            start_new_session=True,
        )

        return WorkerInfo(
            provider=f"reviewer-{ticket_key}",
            ticket_key=ticket_key,
            process=process,
            started_at=time.time(),
            log_file=str(log_file),
        )

    def _check_workers(self) -> None:
        """Check on running workers, handle completion/failure/timeout."""
        finished = []

        for provider, worker in self.workers.items():
            returncode = worker.process.poll()

            # Determine timeout based on worker type
            timeout = REVIEW_WORKER_TIMEOUT if provider.startswith("reviewer-") else WORKER_TIMEOUT

            # Still running — check timeout
            if returncode is None:
                elapsed = time.time() - worker.started_at
                if elapsed > timeout:
                    logger.warning(
                        f"{provider} worker for {worker.ticket_key} timed out "
                        f"after {elapsed:.0f}s, killing"
                    )
                    try:
                        os.killpg(os.getpgid(worker.process.pid), signal.SIGTERM)
                        worker.process.wait(timeout=10)
                    except (ProcessLookupError, subprocess.TimeoutExpired):
                        try:
                            os.killpg(os.getpgid(worker.process.pid), signal.SIGKILL)
                        except ProcessLookupError:
                            pass

                    self._handle_failure(provider, worker.ticket_key, "timeout")
                    finished.append(provider)
                continue

            # Worker finished
            if returncode == 0:
                self._handle_success(provider, worker.ticket_key)
            else:
                self._handle_failure(provider, worker.ticket_key, f"exit code {returncode}")

            finished.append(provider)

        for p in finished:
            del self.workers[p]

    def _handle_success(self, provider: str, ticket_key: str) -> None:
        """Handle a successful worker completion."""
        state = self.provider_states[provider]
        state.consecutive_failures = 0
        state.total_completed += 1
        state.last_ticket = ticket_key
        logger.info(
            f"{provider} completed {ticket_key} successfully "
            f"(total: {state.total_completed})"
        )

    def _handle_failure(self, provider: str, ticket_key: str, reason: str) -> None:
        """Handle a worker failure."""
        state = self.provider_states[provider]
        state.consecutive_failures += 1
        state.total_failed += 1
        logger.error(
            f"{provider} failed on {ticket_key}: {reason} "
            f"(consecutive failures: {state.consecutive_failures})"
        )

        # Release ticket back to To Do
        try:
            self.jira.unclaim_ticket(ticket_key, provider)
        except Exception as e:
            logger.warning(f"Failed to unclaim {ticket_key}: {e}")

        # Disable provider after too many failures
        if state.consecutive_failures >= MAX_FAILURES:
            state.disabled = True
            logger.warning(
                f"Disabling {provider} after {MAX_FAILURES} consecutive failures"
            )

    def _dispatch_reviews(self) -> int:
        """Dispatch review workers for tickets in Review status.

        Returns number of review workers launched.
        """
        # Don't launch reviews if we have too many workers already
        active_reviews = sum(1 for k in self.workers if k.startswith("reviewer-"))
        if active_reviews >= 2:
            return 0

        try:
            review_tickets = self.jira.get_review_tickets()
        except Exception as e:
            logger.error(f"Failed to query Review tickets: {e}")
            return 0

        if not review_tickets:
            return 0

        launched = 0
        for ticket in review_tickets:
            ticket_key = ticket["key"]
            worker_key = f"reviewer-{ticket_key}"

            # Skip if already being reviewed
            if worker_key in self.workers:
                continue

            logger.info(f"Dispatching review for {ticket_key}: {ticket['title']}")

            if self.dry_run:
                logger.info(f"[DRY RUN] Would launch review worker for {ticket_key}")
                continue

            worker = self._launch_review_worker(ticket_key)
            self.workers[worker_key] = worker
            launched += 1

            # Limit to 2 concurrent reviews
            if launched >= 2:
                break

        return launched

    def _dispatch_round(self) -> int:
        """
        Run one dispatch round (implementation + review).
        Returns the number of new workers launched.
        """
        # 1. Check on running workers
        self._check_workers()

        # 2. Dispatch review workers for tickets in Review status
        reviews_launched = self._dispatch_reviews()
        if reviews_launched:
            logger.info(f"Launched {reviews_launched} review worker(s)")

        # 3. Find available providers for implementation
        available = self._available_providers()
        if not available:
            logger.info("No available providers (all busy or disabled)")
            return reviews_launched

        # 4. Query Jira for unclaimed To Do tickets
        try:
            tickets = self.jira.get_todo_tickets(
                exclude_labels=self._get_worker_labels()
            )
        except Exception as e:
            logger.error(f"Failed to query Jira: {e}")
            return reviews_launched

        if not tickets:
            logger.info("No unclaimed To Do tickets available")
            return reviews_launched

        logger.info(f"Found {len(tickets)} unclaimed tickets, {len(available)} providers available")

        # 5. Assign tickets to providers
        launched = 0
        for provider in available:
            if not tickets:
                break

            ticket = tickets.pop(0)
            ticket_key = ticket["key"]

            logger.info(f"Assigning {ticket_key} ({ticket['title']}) to {provider}")

            if self.dry_run:
                logger.info(f"[DRY RUN] Would claim {ticket_key} for {provider}")
                continue

            # Claim in Jira
            if not self.jira.claim_ticket(ticket_key, provider):
                logger.warning(f"Failed to claim {ticket_key} for {provider}, skipping")
                tickets.insert(0, ticket)  # Put it back
                continue

            # Launch worker (route to correct worker type)
            if provider == "claude":
                worker = self._launch_claude_worker(ticket_key)
            elif provider in CLI_AGENT_PROVIDERS:
                worker = self._launch_cli_agent_worker(provider, ticket_key)
            else:
                worker = self._launch_provider_worker(provider, ticket_key)

            self.workers[provider] = worker
            launched += 1

        return launched + reviews_launched

    def _wait_for_all_workers(self) -> None:
        """Wait for all running workers to finish."""
        if not self.workers:
            return

        logger.info(f"Waiting for {len(self.workers)} workers to finish...")
        while self.workers and not self._shutdown:
            self._check_workers()
            if self.workers:
                time.sleep(5)

    def _print_status(self) -> None:
        """Print current dispatch status."""
        print(f"\n{'='*70}")
        print(f"  PARALLEL DISPATCH STATUS — {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
        print(f"{'='*70}")

        # Implementation workers
        print("  IMPLEMENTATION WORKERS:")
        for p in self.providers:
            state = self.provider_states[p]
            status = "DISABLED" if state.disabled else (
                f"RUNNING ({self.workers[p].ticket_key})" if p in self.workers else "IDLE"
            )
            print(
                f"    {p:10s}  {status:30s}  "
                f"done={state.total_completed} fail={state.total_failed}"
            )

        # Review workers
        review_workers = {k: v for k, v in self.workers.items() if k.startswith("reviewer-")}
        if review_workers:
            print("  REVIEW WORKERS:")
            for key, worker in review_workers.items():
                elapsed = time.time() - worker.started_at
                print(f"    {worker.ticket_key:10s}  REVIEWING ({elapsed:.0f}s)")

        print(f"{'='*70}\n")

    def run_once(self) -> None:
        """Run a single dispatch round, then wait for all workers."""
        logger.info("Starting single dispatch round")
        self._dispatch_round()
        self._print_status()
        self._wait_for_all_workers()
        self._print_status()
        logger.info("Single round complete")

    def run(self) -> None:
        """Run continuous dispatch loop."""
        logger.info(
            f"Starting parallel dispatch loop "
            f"(providers: {', '.join(self.providers)}, "
            f"project: {self.project_dir})"
        )

        # Handle graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Shutdown signal received, finishing current workers...")
            self._shutdown = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        while not self._shutdown:
            launched = self._dispatch_round()
            self._print_status()

            if self._shutdown:
                break

            # Check if all providers are disabled
            all_disabled = all(
                self.provider_states[p].disabled for p in self.providers
            )
            if all_disabled:
                logger.error("All providers disabled due to failures. Stopping.")
                break

            # Wait before next round
            wait_time = DISPATCH_INTERVAL if launched == 0 else 5
            logger.info(f"Next dispatch in {wait_time}s...")

            for _ in range(wait_time):
                if self._shutdown:
                    break
                time.sleep(1)

        # Wait for remaining workers
        self._wait_for_all_workers()

        # Final summary
        self._print_summary()

    def _print_summary(self) -> None:
        """Print final session summary."""
        print(f"\n{'='*70}")
        print(f"  DISPATCH SESSION SUMMARY")
        print(f"{'='*70}")

        total_completed = 0
        total_failed = 0

        for p in self.providers:
            state = self.provider_states[p]
            total_completed += state.total_completed
            total_failed += state.total_failed
            status = "disabled" if state.disabled else "ok"
            print(
                f"  {p:10s}  completed={state.total_completed}  "
                f"failed={state.total_failed}  status={status}"
            )

        print(f"\n  Total completed: {total_completed}")
        print(f"  Total failed: {total_failed}")
        print(f"{'='*70}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parallel Dispatch — run multiple AI providers on Jira tickets simultaneously"
    )
    parser.add_argument(
        "--project-dir", required=True, type=Path,
        help="Project directory name (relative to GENERATIONS_BASE_PATH) or absolute path",
    )
    parser.add_argument(
        "--providers", nargs="+",
        choices=ALL_PROVIDERS, default=list(ALL_PROVIDERS),
        help=f"Providers to use (default: all — {', '.join(ALL_PROVIDERS)})",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run one dispatch round then exit (default: continuous loop)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Query tickets and show assignments but don't launch workers",
    )
    return parser.parse_args()


def resolve_project_dir(project_dir_arg: Path) -> Path:
    """Resolve project directory."""
    if project_dir_arg.is_absolute():
        return project_dir_arg
    base = Path(os.environ.get(
        "GENERATIONS_BASE_PATH",
        str(Path(__file__).parent.parent / "generations"),
    ))
    return (base / str(project_dir_arg).lstrip("./")).resolve()


def main() -> int:
    args = parse_args()
    project_dir = resolve_project_dir(args.project_dir)

    if not project_dir.exists():
        print(f"Error: Project directory does not exist: {project_dir}")
        return 1

    # Setup logging
    log_dir = Path(__file__).parent.parent / "logs"
    setup_logging(log_dir)

    # Print banner
    print(f"\n{'='*70}")
    print(f"  PARALLEL MULTI-PROVIDER DISPATCHER")
    print(f"{'='*70}")
    print(f"  Project: {project_dir}")
    print(f"  Providers: {', '.join(args.providers)}")
    print(f"  Mode: {'single round' if args.once else 'continuous'}")
    print(f"  Dry run: {args.dry_run}")
    print(f"{'='*70}\n")

    dispatcher = ParallelDispatcher(
        project_dir=project_dir,
        providers=tuple(args.providers),
        dry_run=args.dry_run,
        once=args.once,
    )

    try:
        if args.once:
            dispatcher.run_once()
        else:
            dispatcher.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
