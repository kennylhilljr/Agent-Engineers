#!/usr/bin/env python3
"""
CLI Agent Worker — For AI Coding Agents with Tool Access
=========================================================

Unlike the API-only provider_worker.py (ChatGPT/Gemini/Groq) which must
build structured prompts, parse responses, and write files manually,
CLI agent workers launch full coding agents that have their own tool access
(file read/write, shell commands, search, etc.).

Supported CLI agents:
  - kimi: Moonshot AI's Kimi CLI (pip install kimi-cli)
          Headless: kimi -p "prompt" -w /path -y --quiet
  - windsurf: Codeium's Windsurf Cascade agent (Docker-based headless)
              Uses windsurf-instructions.txt / windsurf-output.txt protocol

Architecture:
  1. Fetch Jira ticket details
  2. Create git branch (feat/<agent>/<ticket>)
  3. Build task description
  4. Launch CLI agent as subprocess — agent handles file writes directly
  5. After agent completes: stage changes, commit, push
  6. Create PR via gh
  7. Update Jira

Usage:
    python scripts/cli_agent_worker.py --agent kimi --ticket KAN-200 \
        --project-dir ai-coding-dashboard

    python scripts/cli_agent_worker.py --agent windsurf --ticket KAN-201 \
        --project-dir ai-coding-dashboard --dry-run
"""

import argparse
import dataclasses
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
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

CLI_AGENTS = ("kimi", "windsurf")

# Model labels per CLI agent (for Jira labeling on completion)
AGENT_MODEL_LABELS = {
    "kimi": "model:kimi-k2.5",
    "windsurf": "model:windsurf-cascade",
}

# Kimi CLI settings
KIMI_TIMEOUT = 600  # 10 minutes max per ticket
KIMI_MAX_STEPS = 50  # Max tool-call steps per turn

# Windsurf Docker settings
WINDSURF_TIMEOUT = 900  # 15 minutes (Docker startup + processing)
WINDSURF_POLL_INTERVAL = 5  # seconds between checking output file
WINDSURF_IMAGE = "windsurfinabox:latest"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATEFMT = "%Y-%m-%dT%H:%M:%S"

logger = logging.getLogger("cli_agent_worker")


def setup_logging(log_dir: Path, agent: str, ticket_key: str) -> None:
    """Configure logging to file + stderr."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"worker_{agent}_{ticket_key}.log"

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))

    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stderr_handler)


# JiraClient imported from scripts.jira_client


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class WorkerResult:
    """Result of a CLI agent worker run."""
    success: bool
    agent: str
    ticket_key: str
    files_changed: list[str]
    tests_passed: bool
    pr_url: Optional[str]
    error: Optional[str]


# ---------------------------------------------------------------------------
# CLI Agent Worker
# ---------------------------------------------------------------------------

class CLIAgentWorker:
    """Implements a Jira ticket using a CLI-based coding agent."""

    def __init__(
        self,
        agent: str,
        ticket_key: str,
        project_dir: Path,
        dry_run: bool = False,
    ):
        if agent not in CLI_AGENTS:
            raise ValueError(f"Unknown agent: {agent}. Must be one of {CLI_AGENTS}")

        self.agent = agent
        self.ticket_key = ticket_key
        self.project_dir = project_dir.resolve()
        self.dry_run = dry_run
        self.jira = JiraClient()
        self.ticket: Optional[dict] = None

    def _fetch_ticket_details(self) -> dict:
        """Fetch full ticket details from Jira."""
        self.ticket = self.jira.get_issue(self.ticket_key)
        logger.info(
            f"Fetched ticket {self.ticket['key']}: {self.ticket['title']} "
            f"(status: {self.ticket['status']})"
        )
        return self.ticket

    def _build_task_prompt(self) -> str:
        """Build the task prompt for the CLI agent.

        Unlike the structured prompt for API providers (which asks for file:path
        code blocks), this prompt simply describes what to implement. The CLI agent
        has its own file tools and can read/write files directly.
        """
        prompt = f"""Implement the following Jira ticket for a Next.js web application.

## Ticket
- Key: {self.ticket['key']}
- Title: {self.ticket['title']}
- Description:
{self.ticket['description']}
"""
        if self.ticket.get('test_steps'):
            prompt += f"""
## Test Steps
{self.ticket['test_steps']}
"""

        prompt += """
## Requirements
- This is a Next.js App Router project using TypeScript, Tailwind CSS, and shadcn/ui
- Read the existing codebase to understand the project structure before making changes
- Check package.json for available dependencies
- If app_spec.txt exists, read it for the full project specification
- Write complete, production-ready TypeScript code with proper types
- Follow the existing code patterns and conventions in the project
- After implementing, run `npm run build` to verify the code compiles without errors
- If build fails, fix the errors and rebuild until it passes
- Do NOT create git commits — the worker handles git operations
"""
        return prompt

    def _create_branch(self) -> str:
        """Create a git branch for this agent+ticket."""
        branch_name = f"feat/{self.agent}/{self.ticket_key.lower()}"

        # Ensure we're on main first
        subprocess.run(
            ["git", "checkout", "main"],
            capture_output=True, text=True, cwd=self.project_dir,
        )
        subprocess.run(
            ["git", "pull", "--ff-only"],
            capture_output=True, text=True, cwd=self.project_dir,
        )

        # Create and switch to feature branch
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            capture_output=True, text=True, cwd=self.project_dir,
        )
        if result.returncode != 0:
            # Branch might already exist
            subprocess.run(
                ["git", "checkout", branch_name],
                capture_output=True, text=True, cwd=self.project_dir,
            )

        logger.info(f"On branch: {branch_name}")
        return branch_name

    def _run_kimi(self, prompt: str) -> bool:
        """Launch Kimi CLI agent with the task prompt."""
        cmd = [
            "kimi",
            "--prompt", prompt,
            "--work-dir", str(self.project_dir),
            "--yolo",  # Auto-approve all tool actions
            "--print",
            "--output-format", "text",
            "--final-message-only",
            "--max-steps-per-turn", str(KIMI_MAX_STEPS),
        ]

        logger.info(f"Launching Kimi CLI: kimi --prompt '...' --work-dir {self.project_dir} --yolo --quiet")
        logger.info(f"Prompt length: {len(prompt)} chars")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=KIMI_TIMEOUT,
                cwd=self.project_dir,
            )

            # Log output
            if result.stdout:
                logger.info(f"Kimi stdout ({len(result.stdout)} chars):\n{result.stdout[:2000]}")
            if result.stderr:
                logger.warning(f"Kimi stderr:\n{result.stderr[:1000]}")

            if result.returncode != 0:
                logger.error(f"Kimi exited with code {result.returncode}")
                return False

            logger.info("Kimi completed successfully")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"Kimi timed out after {KIMI_TIMEOUT}s")
            return False
        except FileNotFoundError:
            logger.error(
                "Kimi CLI not found. Install with: pip install kimi-cli\n"
                "Then authenticate with: kimi (then /login)"
            )
            return False

    def _run_windsurf(self, prompt: str) -> bool:
        """Launch Windsurf Cascade agent via Docker headless mode.

        Uses the windsurf-instructions.txt / windsurf-output.txt protocol
        from the windsurfinabox Docker image.
        """
        windsurf_token = os.environ.get("WINDSURF_TOKEN", "")
        if not windsurf_token:
            logger.error(
                "WINDSURF_TOKEN not set. Get your token from Windsurf settings.\n"
                "Also ensure Docker is running and windsurfinabox image is built.\n"
                "See: https://github.com/pfcoperez/windsurfinabox"
            )
            return False

        # Check if Docker is available
        docker_check = subprocess.run(
            ["docker", "info"], capture_output=True, text=True,
        )
        if docker_check.returncode != 0:
            logger.error("Docker is not running or not installed")
            return False

        # Write instructions file
        instructions_file = self.project_dir / "windsurf-instructions.txt"
        output_file = self.project_dir / "windsurf-output.txt"

        # Clean up any previous output
        if output_file.exists():
            output_file.unlink()

        instructions_file.write_text(prompt)
        logger.info(f"Wrote windsurf-instructions.txt ({len(prompt)} chars)")

        # Launch Docker container
        container_name = f"windsurf-{self.agent}-{self.ticket_key.lower()}"
        cmd = [
            "docker", "run", "--rm",
            "--name", container_name,
            "-e", f"WINDSURF_TOKEN={windsurf_token}",
            "-v", f"{self.project_dir}:/home/ubuntu/workspace",
            WINDSURF_IMAGE,
        ]

        logger.info(f"Launching Windsurf Docker container: {container_name}")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Poll for completion via output file
            start_time = time.time()
            while time.time() - start_time < WINDSURF_TIMEOUT:
                # Check if process has exited
                if process.poll() is not None:
                    if process.returncode != 0:
                        stderr = process.stderr.read().decode() if process.stderr else ""
                        logger.error(f"Windsurf container exited with code {process.returncode}: {stderr[:500]}")
                        return False
                    break

                # Check for completion signal in output file
                if output_file.exists():
                    output_text = output_file.read_text()
                    if "WORK-COMPLETED" in output_text:
                        logger.info("Windsurf signaled WORK-COMPLETED")
                        # Kill the container gracefully
                        subprocess.run(
                            ["docker", "stop", container_name],
                            capture_output=True, timeout=30,
                        )
                        break

                time.sleep(WINDSURF_POLL_INTERVAL)
            else:
                # Timeout
                logger.error(f"Windsurf timed out after {WINDSURF_TIMEOUT}s")
                subprocess.run(
                    ["docker", "stop", container_name],
                    capture_output=True, timeout=30,
                )
                return False

            # Clean up instructions file
            if instructions_file.exists():
                instructions_file.unlink()

            logger.info("Windsurf completed successfully")
            return True

        except FileNotFoundError:
            logger.error("Docker not found in PATH")
            return False

    def _run_agent(self, prompt: str) -> bool:
        """Dispatch to the correct agent runner."""
        if self.agent == "kimi":
            return self._run_kimi(prompt)
        elif self.agent == "windsurf":
            return self._run_windsurf(prompt)
        else:
            raise ValueError(f"Unknown agent: {self.agent}")

    def _get_changed_files(self) -> list[str]:
        """Get list of files changed by the agent."""
        result = subprocess.run(
            ["git", "diff", "--name-only", "main"],
            capture_output=True, text=True, cwd=self.project_dir,
        )
        if result.returncode != 0:
            # Also try untracked files
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, cwd=self.project_dir,
            )
            if result.returncode == 0:
                files = []
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        # Status is first 2 chars, then space, then filename
                        files.append(line[3:].strip())
                return files
            return []

        tracked_changes = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

        # Also get untracked files
        untracked_result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, cwd=self.project_dir,
        )
        untracked = []
        if untracked_result.returncode == 0:
            untracked = [f.strip() for f in untracked_result.stdout.strip().split("\n") if f.strip()]

        return tracked_changes + untracked

    def _run_tests(self) -> bool:
        """Run project tests. Returns True if tests pass."""
        pkg_json = self.project_dir / "package.json"
        if not pkg_json.exists():
            logger.info("No package.json found, skipping tests")
            return True

        try:
            pkg = json.loads(pkg_json.read_text())
            scripts = pkg.get("scripts", {})

            if "build" in scripts:
                build_result = subprocess.run(
                    ["npm", "run", "build"],
                    capture_output=True, text=True, timeout=300,
                    cwd=self.project_dir,
                )
                if build_result.returncode != 0:
                    logger.warning(f"Build failed:\n{build_result.stderr[:1000]}")
                    return False
                logger.info("Build passed")
                return True

        except (json.JSONDecodeError, IOError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Test execution error: {e}")
            return False

        logger.info("No build script found, skipping tests")
        return True

    def _commit_and_push(self, files_changed: list[str], branch_name: str) -> bool:
        """Stage, commit, and push changes."""
        if not files_changed:
            logger.warning("No files changed by agent")
            return False

        # Stage all changes (agent may have created, modified, or deleted files)
        subprocess.run(
            ["git", "add", "-A"],
            capture_output=True, text=True, cwd=self.project_dir,
        )

        # Commit
        commit_msg = (
            f"feat({self.ticket_key}): {self.ticket['title']}\n\n"
            f"Implemented by {self.agent} CLI agent.\n"
            f"Jira: {self.ticket_key}\n\n"
            f"Co-Authored-By: {self.agent} <noreply@{self.agent}.ai>"
        )
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            capture_output=True, text=True, cwd=self.project_dir,
        )
        if result.returncode != 0:
            logger.error(f"Commit failed: {result.stderr}")
            return False
        logger.info(f"Committed: {result.stdout.strip()}")

        # Push
        result = subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            capture_output=True, text=True, cwd=self.project_dir,
        )
        if result.returncode != 0:
            logger.error(f"Push failed: {result.stderr}")
            return False
        logger.info(f"Pushed to origin/{branch_name}")
        return True

    def _create_pr(self, branch_name: str, tests_passed: bool) -> Optional[str]:
        """Create a GitHub PR. Returns PR URL or None."""
        github_repo = os.environ.get("GITHUB_REPO", "")
        if not github_repo:
            logger.info("GITHUB_REPO not set, skipping PR creation")
            return None

        pr_title = f"feat({self.ticket_key}): {self.ticket['title']}"
        pr_body = (
            f"## Summary\n"
            f"- Implements Jira ticket **{self.ticket_key}**: {self.ticket['title']}\n"
            f"- Generated by **{self.agent}** CLI coding agent\n"
            f"- Tests: {'Passed' if tests_passed else 'Failed (draft PR)'}\n\n"
            f"## Test Plan\n"
            f"- [ ] Verify implementation matches ticket requirements\n"
            f"- [ ] Run `npm run build` to check for type errors\n"
            f"- [ ] Manual browser testing\n\n"
            f"Generated with cli-agent-worker ({self.agent})"
        )

        cmd = [
            "gh", "pr", "create",
            "--title", pr_title,
            "--body", pr_body,
            "--base", "main",
            "--head", branch_name,
        ]
        if not tests_passed:
            cmd.append("--draft")

        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=self.project_dir,
        )
        if result.returncode != 0:
            logger.error(f"PR creation failed: {result.stderr}")
            return None

        pr_url = result.stdout.strip()
        logger.info(f"Created PR: {pr_url}")
        return pr_url

    def _add_completion_labels(self, files_changed: list[str]) -> None:
        """Add agent, model, and technology labels to the Jira ticket."""
        labels = [
            f"agent:{self.agent}",
            AGENT_MODEL_LABELS.get(self.agent, f"model:{self.agent}"),
        ]

        # Detect technology/language from files changed
        tech_labels = set()
        for f in files_changed:
            ext = f.rsplit(".", 1)[-1] if "." in f else ""
            if ext in ("ts", "tsx"):
                tech_labels.add("typescript")
            if ext in ("js", "jsx"):
                tech_labels.add("javascript")
            if ext == "css":
                tech_labels.add("css")
            if ext == "py":
                tech_labels.add("python")
            if ext == "json" and "package" in f:
                tech_labels.add("nodejs")
            if "tailwind" in f.lower():
                tech_labels.add("tailwind")
            if "components/ui" in f or "shadcn" in f.lower():
                tech_labels.add("shadcn")
            if "app/" in f or "next" in f.lower():
                tech_labels.add("nextjs")

        labels.extend(sorted(tech_labels))

        for label in labels:
            try:
                self.jira.add_label(self.ticket_key, label)
            except Exception as e:
                logger.warning(f"Failed to add label '{label}': {e}")

        logger.info(f"Added completion labels: {labels}")

    def _update_jira(self, pr_url: Optional[str], success: bool) -> None:
        """Update Jira ticket with results.

        On success: transition to Review (for peer review).
        On failure: remove claim label, transition back to To Do.
        """
        if success and pr_url:
            comment = (
                f"[{self.agent}] Implementation complete.\n"
                f"PR: {pr_url}\n"
                f"Branch: feat/{self.agent}/{self.ticket_key.lower()}\n"
                f"Ready for peer review.\n"
                f"Timestamp: {datetime.now(timezone.utc).isoformat()}"
            )
            self.jira.add_comment(self.ticket_key, comment)
            # Transition to Review for peer review
            if not self.jira.transition_by_name(self.ticket_key, "Review"):
                logger.warning(
                    f"Could not transition {self.ticket_key} to Review. "
                    f"Ticket stays in current status for manual review."
                )
        elif not success:
            comment = (
                f"[{self.agent}] Implementation attempt failed.\n"
                f"Returning ticket to To Do.\n"
                f"Timestamp: {datetime.now(timezone.utc).isoformat()}"
            )
            self.jira.add_comment(self.ticket_key, comment)
            self.jira.unclaim_ticket(self.ticket_key, self.agent)

    def run(self) -> WorkerResult:
        """Full pipeline: fetch → branch → prompt → agent → test → git → jira."""
        logger.info(f"Starting {self.agent} CLI agent worker for {self.ticket_key}")

        try:
            # 1. Fetch ticket details
            self._fetch_ticket_details()

            # 2. Build task prompt
            prompt = self._build_task_prompt()
            logger.info(f"Built task prompt ({len(prompt)} chars)")

            if self.dry_run:
                logger.info("[DRY RUN] Would launch CLI agent")
                print(f"\n{'='*70}")
                print(f"DRY RUN — {self.agent} CLI agent for {self.ticket_key}")
                print(f"{'='*70}")
                print(f"Ticket: {self.ticket['title']}")
                print(f"Prompt length: {len(prompt)} chars")
                print(f"\nPrompt:\n{prompt}")
                print(f"\n[DRY RUN] Would launch {self.agent} agent, then handle git/PR/Jira")

                return WorkerResult(
                    success=True, agent=self.agent,
                    ticket_key=self.ticket_key,
                    files_changed=[], tests_passed=True,
                    pr_url=None, error=None,
                )

            # 3. Create git branch
            branch_name = self._create_branch()

            # 4. Launch CLI agent
            agent_success = self._run_agent(prompt)

            if not agent_success:
                raise RuntimeError(f"{self.agent} agent failed to complete the task")

            # 5. Check what files changed
            files_changed = self._get_changed_files()
            logger.info(f"Agent changed {len(files_changed)} files: {files_changed}")

            if not files_changed:
                raise RuntimeError(f"{self.agent} agent completed but no files were changed")

            # 6. Run tests
            tests_passed = self._run_tests()

            # 7. Commit and push
            pushed = self._commit_and_push(files_changed, branch_name)

            # 8. Create PR
            pr_url = None
            if pushed:
                pr_url = self._create_pr(branch_name, tests_passed)

            # 9. Update Jira
            self._update_jira(pr_url, success=True)

            # 10. Add agent/model/tech labels
            self._add_completion_labels(files_changed)

            logger.info(
                f"Worker complete: {len(files_changed)} files, "
                f"tests={'pass' if tests_passed else 'fail'}, "
                f"PR={pr_url or 'none'}"
            )

            return WorkerResult(
                success=True, agent=self.agent,
                ticket_key=self.ticket_key,
                files_changed=files_changed,
                tests_passed=tests_passed,
                pr_url=pr_url, error=None,
            )

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.error(f"Worker failed: {error_msg}")

            # Try to update Jira on failure (skip in dry-run mode)
            if not self.dry_run:
                try:
                    self._update_jira(pr_url=None, success=False)
                except Exception:
                    logger.warning("Failed to update Jira after worker failure")

            # Try to switch back to main
            try:
                subprocess.run(
                    ["git", "checkout", "main"],
                    capture_output=True, text=True, cwd=self.project_dir,
                )
            except Exception:
                pass

            return WorkerResult(
                success=False, agent=self.agent,
                ticket_key=self.ticket_key,
                files_changed=[], tests_passed=False,
                pr_url=None, error=error_msg,
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CLI Agent Worker — implement a Jira ticket using a CLI coding agent"
    )
    parser.add_argument(
        "--agent", required=True,
        choices=CLI_AGENTS,
        help=f"CLI agent to use ({', '.join(CLI_AGENTS)})",
    )
    parser.add_argument(
        "--ticket", required=True,
        help="Jira ticket key (e.g., KAN-200)",
    )
    parser.add_argument(
        "--project-dir", required=True, type=Path,
        help="Project directory name (relative to GENERATIONS_BASE_PATH) or absolute path",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch ticket and build prompt but don't launch agent or write files",
    )
    return parser.parse_args()


def resolve_project_dir(project_dir_arg: Path) -> Path:
    """Resolve project directory, handling relative paths via GENERATIONS_BASE_PATH."""
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
    setup_logging(log_dir, args.agent, args.ticket)

    # Run worker
    worker = CLIAgentWorker(
        agent=args.agent,
        ticket_key=args.ticket,
        project_dir=project_dir,
        dry_run=args.dry_run,
    )
    result = worker.run()

    # Print summary
    print(f"\n{'='*70}")
    print(f"CLI Agent Result: {args.agent} / {args.ticket}")
    print(f"{'='*70}")
    print(f"  Success: {result.success}")
    print(f"  Files changed: {len(result.files_changed)}")
    for f in result.files_changed:
        print(f"    - {f}")
    print(f"  Tests passed: {result.tests_passed}")
    print(f"  PR URL: {result.pr_url or 'none'}")
    if result.error:
        print(f"  Error: {result.error}")

    # Output result as JSON for parent process
    print(f"\nRESULT_JSON:{json.dumps(dataclasses.asdict(result))}")

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
