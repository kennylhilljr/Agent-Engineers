#!/usr/bin/env python3
"""
Agent Watchdog - Self-healing monitor for autonomous coding agents.
===================================================================

Monitors agent processes for stalls (0% CPU, no git commits, no child
processes) and automatically restarts them with safety limits.

Usage:
    python scripts/agent_watchdog.py --project-dir ai-coding-dashboard
    python scripts/agent_watchdog.py --project-dir ai-coding-dashboard --dry-run
    python scripts/agent_watchdog.py --project-dir my-app --once
    python scripts/agent_watchdog.py --project-dir proj-a --project-dir proj-b
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, NamedTuple, TypedDict

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).parent.parent
DEFAULT_CHECK_INTERVAL: int = 300  # 5 minutes
DEFAULT_STALL_THRESHOLD: int = 1800  # 30 minutes
DEFAULT_COMMIT_THRESHOLD: int = 3600  # 60 minutes
DEFAULT_MAX_RESTARTS: int = 3
SIGTERM_TIMEOUT: int = 10
MAX_BACKOFF_SECONDS: float = 600.0

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

HealthStatus = Literal["healthy", "warning", "stalled", "dead"]


class AgentHealthReport(TypedDict):
    pid: int
    project_dir: str
    is_alive: bool
    cpu_percent: float
    last_cpu_active: str
    last_git_commit: str | None
    has_children: bool
    status: HealthStatus
    reason: str


class RestartRecord(NamedTuple):
    timestamp: datetime
    pid: int
    project_dir: str
    reason: str


class WatchdogConfig(NamedTuple):
    check_interval: int
    stall_threshold: int
    commit_threshold: int
    max_restarts_per_hour: int
    dry_run: bool
    project_dirs: list[Path]
    log_file: Path
    pid_file: Path


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def setup_logging(log_file: Path) -> logging.Logger:
    """Configure logging to file and stderr."""
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("agent_watchdog")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    fh = logging.FileHandler(log_file, mode="a")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_project_dir(project_dir: Path, generations_base: Path | None = None) -> Path:
    """Resolve project directory, matching scripts/autonomous_agent_demo.py behaviour."""
    if project_dir.is_absolute():
        return project_dir
    if generations_base is None:
        generations_base = Path(os.environ.get("GENERATIONS_BASE_PATH", "./generations"))
    if not generations_base.is_absolute():
        generations_base = REPO_ROOT / generations_base
    return generations_base / str(project_dir).lstrip("./")


# ---------------------------------------------------------------------------
# AgentWatchdog
# ---------------------------------------------------------------------------


class AgentWatchdog:
    """Monitors and self-heals autonomous coding agent processes."""

    def __init__(self, config: WatchdogConfig) -> None:
        self.config = config
        self.logger = setup_logging(config.log_file)
        self._running = False

        # CPU tracking: pid -> last time CPU was non-zero
        self._last_cpu_active: dict[int, datetime] = {}
        # Track which projects had a running agent last cycle
        self._was_running: dict[str, int] = {}
        # Restart history per project dir (string key)
        self._restart_history: dict[str, list[RestartRecord]] = {}

    # ------------------------------------------------------------------
    # Process discovery
    # ------------------------------------------------------------------

    def find_agent_pid(self, project_dir: Path) -> int | None:
        """Find PID of the autonomous agent for *project_dir*."""
        project_name = project_dir.name
        try:
            result = subprocess.run(
                ["ps", "-eo", "pid,command"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None

        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if "autonomous_agent_demo" not in line:
                continue
            if project_name not in line:
                continue
            if "agent_watchdog" in line or "grep" in line:
                continue
            parts = line.split(None, 1)
            if parts:
                try:
                    return int(parts[0])
                except ValueError:
                    continue
        return None

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    def check_process_alive(self, pid: int) -> bool:
        """Return True if *pid* exists."""
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def check_cpu_usage(self, pid: int) -> float:
        """Return instantaneous CPU % for *pid* (macOS / POSIX)."""
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "%cpu="],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return float(result.stdout.strip()) if result.returncode == 0 else 0.0
        except (subprocess.TimeoutExpired, OSError, ValueError):
            return 0.0

    def check_child_processes(self, pid: int) -> bool:
        """Return True if *pid* has at least one child process."""
        try:
            result = subprocess.run(
                ["ps", "-eo", "pid,ppid"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            return False

        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) == 2:
                try:
                    if int(parts[1]) == pid:
                        return True
                except ValueError:
                    continue
        return False

    def check_git_recency(self, project_dir: Path) -> datetime | None:
        """Return timestamp of the most recent git commit, or None."""
        try:
            result = subprocess.run(
                ["git", "-C", str(project_dir), "log", "-1", "--format=%aI"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return datetime.fromisoformat(result.stdout.strip())
        except (subprocess.TimeoutExpired, OSError, ValueError):
            pass
        return None

    # ------------------------------------------------------------------
    # Health assessment
    # ------------------------------------------------------------------

    def assess_health(self, pid: int, project_dir: Path) -> AgentHealthReport:
        """Run all checks and return a composite health report."""
        now = datetime.now(UTC)
        tag = project_dir.name

        alive = self.check_process_alive(pid)
        if not alive:
            self._last_cpu_active.pop(pid, None)
            return AgentHealthReport(
                pid=pid,
                project_dir=str(project_dir),
                is_alive=False,
                cpu_percent=0.0,
                last_cpu_active=now.isoformat(),
                last_git_commit=None,
                has_children=False,
                status="dead",
                reason="Process not found",
            )

        cpu = self.check_cpu_usage(pid)
        has_children = self.check_child_processes(pid)
        last_commit_dt = self.check_git_recency(project_dir)
        last_commit_str = last_commit_dt.isoformat() if last_commit_dt else None

        # Track CPU activity
        if cpu > 0.0 or has_children:
            self._last_cpu_active[pid] = now

        if pid not in self._last_cpu_active:
            # First observation — give benefit of the doubt
            self._last_cpu_active[pid] = now

        last_active = self._last_cpu_active[pid]
        idle_seconds = (now - last_active).total_seconds()

        commit_age: float | None = None
        if last_commit_dt:
            commit_age = (now - last_commit_dt).total_seconds()

        # Decision tree
        if cpu > 0.0 or has_children:
            status: HealthStatus = "healthy"
            reason = f"CPU={cpu:.1f}% children={'yes' if has_children else 'no'}"
        elif idle_seconds < self.config.stall_threshold:
            status = "warning"
            reason = (
                f"CPU=0% for {_fmt_duration(idle_seconds)}, "
                f"within threshold ({_fmt_duration(self.config.stall_threshold)})"
            )
        else:
            # Past CPU threshold — check children and commits
            if has_children:
                status = "warning"
                reason = f"CPU=0% for {_fmt_duration(idle_seconds)} but has child processes"
            elif commit_age is not None and commit_age < self.config.commit_threshold:
                status = "warning"
                reason = (
                    f"CPU=0% for {_fmt_duration(idle_seconds)}, no children, "
                    f"but committed {_fmt_duration(commit_age)} ago"
                )
            else:
                status = "stalled"
                commit_info = (
                    f"last commit {_fmt_duration(commit_age)} ago"
                    if commit_age is not None
                    else "no commits found"
                )
                reason = f"CPU=0% for {_fmt_duration(idle_seconds)}, no children, {commit_info}"

        self.logger.log(
            logging.WARNING if status in ("stalled", "dead") else logging.INFO,
            f"[{tag}] PID={pid} status={status} | {reason}",
        )

        return AgentHealthReport(
            pid=pid,
            project_dir=str(project_dir),
            is_alive=alive,
            cpu_percent=cpu,
            last_cpu_active=last_active.isoformat(),
            last_git_commit=last_commit_str,
            has_children=has_children,
            status=status,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Kill / restart
    # ------------------------------------------------------------------

    def kill_process(self, pid: int) -> bool:
        """SIGTERM then SIGKILL after timeout. Returns True on success."""
        try:
            os.kill(pid, signal.SIGTERM)
            self.logger.info(f"Sent SIGTERM to PID {pid}")
        except ProcessLookupError:
            self.logger.info(f"PID {pid} already dead")
            return True
        except PermissionError:
            self.logger.error(f"Permission denied killing PID {pid}")
            return False

        for _ in range(SIGTERM_TIMEOUT):
            time.sleep(1)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                self.logger.info(f"PID {pid} terminated gracefully")
                return True

        try:
            os.kill(pid, signal.SIGKILL)
            self.logger.warning(f"Sent SIGKILL to PID {pid}")
            return True
        except ProcessLookupError:
            return True
        except PermissionError:
            self.logger.error(f"Permission denied for SIGKILL on PID {pid}")
            return False

    def _can_restart(self, key: str) -> bool:
        history = self._restart_history.get(key, [])
        cutoff = datetime.now(UTC) - timedelta(hours=1)
        recent = [r for r in history if r.timestamp > cutoff]
        return len(recent) < self.config.max_restarts_per_hour

    def _get_backoff_delay(self, key: str) -> float:
        history = self._restart_history.get(key, [])
        cutoff = datetime.now(UTC) - timedelta(hours=1)
        count = sum(1 for r in history if r.timestamp > cutoff)
        if count == 0:
            return 0.0
        return min(30.0 * (2 ** (count - 1)), MAX_BACKOFF_SECONDS)

    def restart_agent(self, project_dir: Path, reason: str) -> int | None:
        """Kill stalled process (if any) and start a new one."""
        key = str(project_dir)
        tag = project_dir.name

        if not self._can_restart(key):
            self.logger.warning(
                f"[{tag}] Max restarts ({self.config.max_restarts_per_hour}/hr) "
                f"exceeded — refusing restart"
            )
            return None

        backoff = self._get_backoff_delay(key)
        if backoff > 0:
            self.logger.info(f"[{tag}] Backoff delay: {backoff:.0f}s")
            if not self.config.dry_run:
                time.sleep(backoff)

        cmd = self._build_agent_command(project_dir)
        self.logger.info(f"[{tag}] Restarting: {' '.join(cmd)}")

        if self.config.dry_run:
            self.logger.info(f"[{tag}] [DRY RUN] Would restart — skipping")
            return None

        agent_log_path = self.config.log_file.parent / f"agent_{tag}.log"
        agent_log = open(agent_log_path, "a")  # noqa: SIM115

        process = subprocess.Popen(
            cmd,
            stdout=agent_log,
            stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT),
            start_new_session=True,
        )

        self._restart_history.setdefault(key, []).append(
            RestartRecord(
                timestamp=datetime.now(UTC),
                pid=process.pid,
                project_dir=key,
                reason=reason,
            )
        )

        self.logger.info(f"[{tag}] Agent restarted with PID {process.pid}")

        return process.pid

    def _build_agent_command(self, project_dir: Path) -> list[str]:
        venv_python = REPO_ROOT / "venv" / "bin" / "python"
        demo_script = REPO_ROOT / "scripts" / "autonomous_agent_demo.py"
        return [str(venv_python), str(demo_script), "--project-dir", project_dir.name]

    # ------------------------------------------------------------------
    # Check cycle
    # ------------------------------------------------------------------

    def run_check_cycle(self) -> list[AgentHealthReport]:
        """Run one health-check pass over all monitored projects."""
        reports: list[AgentHealthReport] = []

        for project_dir in self.config.project_dirs:
            tag = project_dir.name
            pid = self.find_agent_pid(project_dir)

            if pid is None:
                was_pid = self._was_running.get(str(project_dir))
                if was_pid is not None:
                    self.logger.warning(f"[{tag}] Agent disappeared (was PID {was_pid})")
                    self._last_cpu_active.pop(was_pid, None)
                    del self._was_running[str(project_dir)]
                    new_pid = self.restart_agent(project_dir, "process_disappeared")
                    if new_pid:
                        self._was_running[str(project_dir)] = new_pid
                    reports.append(
                        AgentHealthReport(
                            pid=was_pid,
                            project_dir=str(project_dir),
                            is_alive=False,
                            cpu_percent=0.0,
                            last_cpu_active=datetime.now(UTC).isoformat(),
                            last_git_commit=None,
                            has_children=False,
                            status="dead",
                            reason="Process disappeared — restarted",
                        )
                    )
                else:
                    self.logger.debug(f"[{tag}] No agent running (not previously tracked)")
                    reports.append(
                        AgentHealthReport(
                            pid=0,
                            project_dir=str(project_dir),
                            is_alive=False,
                            cpu_percent=0.0,
                            last_cpu_active="",
                            last_git_commit=None,
                            has_children=False,
                            status="dead",
                            reason="No agent process found",
                        )
                    )
                continue

            self._was_running[str(project_dir)] = pid
            health = self.assess_health(pid, project_dir)
            reports.append(health)

            if health["status"] == "stalled":
                self.logger.warning(f"[{tag}] STALL CONFIRMED — initiating restart")
                killed = self.kill_process(pid) if not self.config.dry_run else True
                if killed:
                    self._last_cpu_active.pop(pid, None)
                    new_pid = self.restart_agent(project_dir, health["reason"])
                    if new_pid:
                        self._was_running[str(project_dir)] = new_pid

        return reports

    # ------------------------------------------------------------------
    # Run modes
    # ------------------------------------------------------------------

    def run_once(self) -> int:
        """Single health check. Returns 0 if all healthy, 1 otherwise."""
        reports = self.run_check_cycle()
        print(json.dumps(reports, indent=2, default=str))
        return 1 if any(r["status"] in ("stalled", "dead") for r in reports) else 0

    def run(self) -> None:
        """Daemon loop — runs until SIGTERM/SIGINT."""
        dirs_str = ", ".join(p.name for p in self.config.project_dirs)
        self.logger.info(f"Watchdog started. Monitoring: {dirs_str}")
        self.logger.info(
            f"Config: interval={self.config.check_interval}s "
            f"stall={self.config.stall_threshold}s "
            f"commit={self.config.commit_threshold}s "
            f"max_restarts={self.config.max_restarts_per_hour}/hr "
            f"dry_run={self.config.dry_run}"
        )

        self._running = True
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        self._write_pid_file()

        try:
            while self._running:
                self.run_check_cycle()
                for _ in range(self.config.check_interval):
                    if not self._running:
                        break
                    time.sleep(1)
        finally:
            self._remove_pid_file()
            self.logger.info("Watchdog stopped")

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        name = signal.Signals(signum).name
        self.logger.info(f"Received {name}, shutting down...")
        self._running = False

    def _write_pid_file(self) -> None:
        self.config.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.pid_file.write_text(str(os.getpid()))

    def _remove_pid_file(self) -> None:
        try:
            self.config.pid_file.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_duration(seconds: float) -> str:
    """Format seconds into a human-friendly string like '1h 23m'."""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60}s"
    h, rem = divmod(s, 3600)
    return f"{h}h {rem // 60}m"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Self-healing watchdog for autonomous coding agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/agent_watchdog.py --project-dir ai-coding-dashboard
  python scripts/agent_watchdog.py --project-dir my-app --dry-run --once
  python scripts/agent_watchdog.py --project-dir a --project-dir b
        """,
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        action="append",
        required=True,
        help="Project to monitor (repeatable)",
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=DEFAULT_CHECK_INTERVAL,
        help=f"Seconds between checks (default: {DEFAULT_CHECK_INTERVAL})",
    )
    parser.add_argument(
        "--stall-threshold",
        type=int,
        default=DEFAULT_STALL_THRESHOLD,
        help=f"Seconds of 0%% CPU before stall (default: {DEFAULT_STALL_THRESHOLD})",
    )
    parser.add_argument(
        "--commit-threshold",
        type=int,
        default=DEFAULT_COMMIT_THRESHOLD,
        help=f"Seconds since last commit before flagging (default: {DEFAULT_COMMIT_THRESHOLD})",
    )
    parser.add_argument(
        "--max-restarts",
        type=int,
        default=DEFAULT_MAX_RESTARTS,
        help=f"Max restarts per project per hour (default: {DEFAULT_MAX_RESTARTS})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report only, no kill/restart")
    parser.add_argument("--once", action="store_true", help="Single check then exit")
    parser.add_argument(
        "--log-file",
        type=Path,
        default=REPO_ROOT / "logs" / "watchdog.log",
        help="Log file path (default: logs/watchdog.log)",
    )
    parser.add_argument(
        "--generations-base",
        type=Path,
        default=None,
        help="Base directory for projects (default: from env or ./generations)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    project_dirs = [resolve_project_dir(p, args.generations_base) for p in args.project_dir]

    config = WatchdogConfig(
        check_interval=args.check_interval,
        stall_threshold=args.stall_threshold,
        commit_threshold=args.commit_threshold,
        max_restarts_per_hour=args.max_restarts,
        dry_run=args.dry_run,
        project_dirs=project_dirs,
        log_file=args.log_file,
        pid_file=args.log_file.parent / "watchdog.pid",
    )

    watchdog = AgentWatchdog(config)

    if args.once:
        return watchdog.run_once()

    watchdog.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
