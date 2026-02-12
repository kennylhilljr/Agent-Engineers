#!/usr/bin/env python3
"""
Provider Worker — Per-Provider Coding Agent
============================================

Takes a single Jira ticket and an AI provider (chatgpt/gemini/groq),
sends a structured coding prompt to the provider, parses the response
into files, writes them to disk, runs tests, creates a git branch + PR,
and updates Jira.

Usage:
    python scripts/provider_worker.py --provider chatgpt --ticket KAN-200 \
        --project-dir ai-coding-dashboard

    python scripts/provider_worker.py --provider gemini --ticket KAN-201 \
        --project-dir ai-coding-dashboard --dry-run
"""

import argparse
import dataclasses
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple, Optional

# Setup path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

from jira_client import JiraClient


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class FileOutput(NamedTuple):
    """A file extracted from the provider's response."""
    path: str
    content: str


@dataclass
class TicketDetails:
    """Jira ticket information."""
    key: str
    title: str
    description: str
    test_steps: str
    labels: list[str]
    status: str


@dataclass
class WorkerResult:
    """Result of a provider worker run."""
    success: bool
    provider: str
    ticket_key: str
    files_written: list[str]
    tests_passed: bool
    pr_url: Optional[str]
    error: Optional[str]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATEFMT = "%Y-%m-%dT%H:%M:%S"

logger = logging.getLogger("provider_worker")


def setup_logging(log_dir: Path, provider: str, ticket_key: str) -> None:
    """Configure logging to file + stderr."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"worker_{provider}_{ticket_key}.log"

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))

    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stderr_handler)


# JiraClient imported from scripts.jira_client

# Model labels per provider (for Jira labeling on completion)
PROVIDER_MODEL_LABELS = {
    "chatgpt": "model:gpt-4o",
    "gemini": "model:gemini-2.5-flash",
    "groq": "model:llama-3.3-70b",
}


# ---------------------------------------------------------------------------
# Response Parser
# ---------------------------------------------------------------------------

def parse_response(text: str) -> list[FileOutput]:
    """
    Parse provider response to extract file outputs.

    Three-tier fallback:
    1. Structured: file:<path> followed by fenced code block
    2. Named markdown: ```language:path or ```path patterns
    3. Heuristic: code blocks preceded by path-like comments
    """
    files = _parse_structured(text)
    if files:
        return files

    files = _parse_named_markdown(text)
    if files:
        return files

    files = _parse_heuristic(text)
    return files


def _parse_structured(text: str) -> list[FileOutput]:
    """Tier 1: Look for file:<path> followed by a fenced code block."""
    pattern = r"file:([^\s`]+)\s*\n```[^\n]*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [FileOutput(path=m[0].strip(), content=m[1]) for m in matches]


def _parse_named_markdown(text: str) -> list[FileOutput]:
    """Tier 2: Look for ```language:path or ```path patterns."""
    # Match ```tsx:src/components/Foo.tsx or ```src/components/Foo.tsx
    pattern = r"```(?:\w+:)?([^\s`]+\.\w+)\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    # Filter out matches that don't look like file paths
    return [
        FileOutput(path=m[0].strip(), content=m[1])
        for m in matches
        if "/" in m[0] or m[0].endswith((".tsx", ".ts", ".js", ".jsx", ".css", ".json"))
    ]


def _parse_heuristic(text: str) -> list[FileOutput]:
    """Tier 3: Look for code blocks preceded by path-like comments."""
    results = []
    # Split on code fences
    blocks = re.split(r"```\w*\n", text)

    for i in range(1, len(blocks)):
        code_and_rest = blocks[i].split("```", 1)
        if not code_and_rest:
            continue
        code = code_and_rest[0]

        # Look at the text before this code block for a path hint
        preceding = blocks[i - 1].strip().split("\n")
        if not preceding:
            continue
        last_line = preceding[-1].strip()

        # Try to extract a path from comments like "// src/foo.tsx" or "/* src/foo.tsx */"
        path_match = re.search(
            r"(?://|/\*|#)\s*([^\s*]+\.\w+)", last_line
        )
        if path_match:
            path = path_match.group(1)
            if "/" in path or path.endswith((".tsx", ".ts", ".js", ".jsx", ".css", ".json")):
                results.append(FileOutput(path=path, content=code))

    return results


# ---------------------------------------------------------------------------
# Provider Worker
# ---------------------------------------------------------------------------

class ProviderWorker:
    """Implements a Jira ticket using a non-Claude AI provider."""

    PROVIDERS = ("chatgpt", "gemini", "groq")

    def __init__(
        self,
        provider: str,
        ticket_key: str,
        project_dir: Path,
        dry_run: bool = False,
    ):
        if provider not in self.PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}. Must be one of {self.PROVIDERS}")

        self.provider = provider
        self.ticket_key = ticket_key
        self.project_dir = project_dir.resolve()
        self.dry_run = dry_run
        self.jira = JiraClient()
        self.bridge = None
        self.ticket: Optional[TicketDetails] = None

    def _init_bridge(self):
        """Instantiate the correct provider bridge."""
        if self.provider == "chatgpt":
            from openai_bridge import OpenAIBridge
            self.bridge = OpenAIBridge.from_env()
        elif self.provider == "gemini":
            from gemini_bridge import GeminiBridge
            self.bridge = GeminiBridge.from_env()
        elif self.provider == "groq":
            from groq_bridge import GroqBridge
            self.bridge = GroqBridge()
        logger.info(f"Initialized {self.provider} bridge")

    def _fetch_ticket_details(self) -> TicketDetails:
        """Fetch full ticket details from Jira."""
        data = self.jira.get_issue(self.ticket_key)
        self.ticket = TicketDetails(
            key=data["key"],
            title=data["title"],
            description=data["description"],
            test_steps=data["test_steps"],
            labels=data["labels"],
            status=data["status"],
        )
        logger.info(
            f"Fetched ticket {self.ticket.key}: {self.ticket.title} "
            f"(status: {self.ticket.status})"
        )
        return self.ticket

    def _gather_project_context(self) -> str:
        """Gather project context: file tree, package.json, key source files."""
        context_parts = []

        # File tree (top 3 levels, excluding node_modules/.git)
        try:
            tree_result = subprocess.run(
                ["find", ".", "-maxdepth", "3",
                 "-not", "-path", "*/node_modules/*",
                 "-not", "-path", "*/.git/*",
                 "-not", "-path", "*/.next/*",
                 "-not", "-path", "*/screenshots/*"],
                capture_output=True, text=True, timeout=10,
                cwd=self.project_dir,
            )
            context_parts.append(f"Project structure:\n{tree_result.stdout[:3000]}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            context_parts.append("Project structure: (unavailable)")

        # package.json
        pkg_json = self.project_dir / "package.json"
        if pkg_json.exists():
            try:
                pkg_data = json.loads(pkg_json.read_text())
                relevant = {
                    k: pkg_data[k]
                    for k in ("dependencies", "devDependencies", "scripts")
                    if k in pkg_data
                }
                context_parts.append(f"package.json (relevant):\n{json.dumps(relevant, indent=2)}")
            except (json.JSONDecodeError, IOError):
                pass

        # tsconfig.json
        tsconfig = self.project_dir / "tsconfig.json"
        if tsconfig.exists():
            try:
                context_parts.append(f"tsconfig.json:\n{tsconfig.read_text()[:1000]}")
            except IOError:
                pass

        # app_spec.txt (project specification)
        spec = self.project_dir / "app_spec.txt"
        if spec.exists():
            try:
                context_parts.append(f"App specification:\n{spec.read_text()[:2000]}")
            except IOError:
                pass

        # Key source files (layout, main page)
        for rel_path in [
            "src/app/layout.tsx", "src/app/page.tsx", "app/layout.tsx", "app/page.tsx",
            "lib/utils.ts", "lib/db.ts",
        ]:
            full_path = self.project_dir / rel_path
            if full_path.exists():
                try:
                    content = full_path.read_text()
                    if len(content) > 2000:
                        content = content[:2000] + "\n... (truncated)"
                    context_parts.append(f"Existing file {rel_path}:\n{content}")
                except IOError:
                    pass

        return "\n\n---\n\n".join(context_parts)

    def _build_prompt(self) -> str:
        """Build the structured coding prompt."""
        context = self._gather_project_context()

        prompt = f"""You are implementing a Jira ticket for a web application.

## Ticket
- Key: {self.ticket.key}
- Title: {self.ticket.title}
- Description: {self.ticket.description}
{f"- Test Steps: {self.ticket.test_steps}" if self.ticket.test_steps else ""}

## Project Context
{context}

## Instructions
Implement this feature completely. Output ALL files you create or modify using this exact format:

file:src/components/Example.tsx
```tsx
// complete file contents
```

file:src/app/page.tsx
```tsx
// complete file contents
```

Rules:
- Output COMPLETE file contents for every file (not diffs or patches)
- Include ALL imports and type definitions
- Use one file:<path> block per file
- Paths must be relative to the project root
- Use TypeScript (.tsx/.ts) with proper type annotations
- Follow existing project patterns (Next.js App Router, Tailwind CSS, shadcn/ui)
- Do NOT include explanations or commentary between file blocks
- If modifying an existing file, output the ENTIRE updated file contents
"""
        return prompt

    def _send_to_provider(self, prompt: str) -> str:
        """Send prompt to provider and return raw response text."""
        system_prompt = (
            "You are an expert TypeScript/React developer. You implement features "
            "for Next.js applications using TypeScript, Tailwind CSS, and shadcn/ui. "
            "You output complete, production-ready code in the specified format. "
            "Never output partial code, diffs, or patches."
        )

        session = self.bridge.create_session(system_prompt=system_prompt)
        logger.info(f"Sending prompt to {self.provider} ({len(prompt)} chars)")

        response = self.bridge.send_message(session, prompt)
        content = response.content
        logger.info(f"Received response from {self.provider} ({len(content)} chars)")
        return content

    def _write_files(self, files: list[FileOutput]) -> list[str]:
        """Write extracted files to the project directory."""
        written = []
        for f in files:
            # Security: prevent path traversal
            clean_path = os.path.normpath(f.path).lstrip("/")
            if ".." in clean_path:
                logger.warning(f"Skipping suspicious path: {f.path}")
                continue

            full_path = self.project_dir / clean_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(f.content)
            written.append(clean_path)
            logger.info(f"Wrote: {clean_path} ({len(f.content)} bytes)")

        return written

    def _run_tests(self) -> bool:
        """Run project tests. Returns True if tests pass."""
        # Try npm test first
        pkg_json = self.project_dir / "package.json"
        if pkg_json.exists():
            try:
                pkg = json.loads(pkg_json.read_text())
                scripts = pkg.get("scripts", {})

                # Try lint first (fast check)
                if "lint" in scripts:
                    lint_result = subprocess.run(
                        ["npm", "run", "lint"],
                        capture_output=True, text=True, timeout=120,
                        cwd=self.project_dir,
                    )
                    if lint_result.returncode != 0:
                        logger.warning(f"Lint failed:\n{lint_result.stderr[:500]}")

                # Try build (type checking)
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

        logger.info("No test scripts found, skipping tests")
        return True

    def _create_branch(self) -> str:
        """Create a git branch for this provider+ticket."""
        branch_name = f"feat/{self.provider}/{self.ticket_key.lower()}"

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

    def _commit_and_push(self, files_written: list[str], branch_name: str) -> bool:
        """Stage, commit, and push changes."""
        if not files_written:
            logger.warning("No files to commit")
            return False

        # Stage specific files
        for f in files_written:
            subprocess.run(
                ["git", "add", f],
                capture_output=True, text=True, cwd=self.project_dir,
            )

        # Commit
        commit_msg = (
            f"feat({self.ticket_key}): {self.ticket.title}\n\n"
            f"Implemented by {self.provider} provider worker.\n"
            f"Jira: {self.ticket_key}\n\n"
            f"Co-Authored-By: {self.provider} <noreply@{self.provider}.ai>"
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

        pr_title = f"feat({self.ticket_key}): {self.ticket.title}"
        pr_body = (
            f"## Summary\n"
            f"- Implements Jira ticket **{self.ticket_key}**: {self.ticket.title}\n"
            f"- Generated by **{self.provider}** provider worker\n"
            f"- Tests: {'Passed' if tests_passed else 'Failed (draft PR)'}\n\n"
            f"## Test Plan\n"
            f"- [ ] Verify implementation matches ticket requirements\n"
            f"- [ ] Run `npm run build` to check for type errors\n"
            f"- [ ] Manual browser testing\n\n"
            f"Generated with provider-worker ({self.provider})"
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

    def _add_completion_labels(self, files_written: list[str]) -> None:
        """Add agent, model, and technology labels to the Jira ticket."""
        labels = [
            f"agent:{self.provider}",
            PROVIDER_MODEL_LABELS.get(self.provider, f"model:{self.provider}"),
        ]

        # Detect technology/language from files written
        tech_labels = set()
        for f in files_written:
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
            # Detect frameworks from path
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
                f"[{self.provider}] Implementation complete.\n"
                f"PR: {pr_url}\n"
                f"Branch: feat/{self.provider}/{self.ticket_key.lower()}\n"
                f"Ready for peer review.\n"
                f"Timestamp: {datetime.now(timezone.utc).isoformat()}"
            )
            self.jira.add_comment(self.ticket_key, comment)
            # Transition to Review for peer review
            if not self.jira.transition_by_name(self.ticket_key, "Review"):
                # Fallback: if no Review status exists, log a warning
                logger.warning(
                    f"Could not transition {self.ticket_key} to Review. "
                    f"Ticket stays in current status for manual review."
                )
        elif not success:
            comment = (
                f"[{self.provider}] Implementation attempt failed.\n"
                f"Returning ticket to To Do.\n"
                f"Timestamp: {datetime.now(timezone.utc).isoformat()}"
            )
            self.jira.add_comment(self.ticket_key, comment)
            self.jira.unclaim_ticket(self.ticket_key, self.provider)

    def run(self) -> WorkerResult:
        """Full pipeline: fetch -> prompt -> parse -> write -> test -> git -> jira."""
        logger.info(f"Starting {self.provider} worker for {self.ticket_key}")

        try:
            # 1. Initialize bridge
            self._init_bridge()

            # 2. Fetch ticket details
            self._fetch_ticket_details()

            # 3. Build prompt
            prompt = self._build_prompt()
            logger.info(f"Built prompt ({len(prompt)} chars)")

            if self.dry_run:
                logger.info("[DRY RUN] Would send prompt to provider")
                print(f"\n{'='*70}")
                print(f"DRY RUN — {self.provider} worker for {self.ticket_key}")
                print(f"{'='*70}")
                print(f"Ticket: {self.ticket.title}")
                print(f"Prompt length: {len(prompt)} chars")
                print(f"\nPrompt preview (first 500 chars):\n{prompt[:500]}...")

                # Still send to provider in dry run to test parsing
                response_text = self._send_to_provider(prompt)
                files = parse_response(response_text)
                print(f"\nParsed {len(files)} files:")
                for f in files:
                    print(f"  {f.path} ({len(f.content)} bytes)")
                print(f"\n[DRY RUN] Would write files, run tests, create branch + PR")

                return WorkerResult(
                    success=True, provider=self.provider,
                    ticket_key=self.ticket_key,
                    files_written=[f.path for f in files],
                    tests_passed=True, pr_url=None, error=None,
                )

            # 4. Create git branch
            branch_name = self._create_branch()

            # 5. Send to provider and parse response
            response_text = self._send_to_provider(prompt)
            files = parse_response(response_text)

            if not files:
                raise RuntimeError(
                    f"Provider {self.provider} returned no parseable files. "
                    f"Response length: {len(response_text)} chars"
                )

            logger.info(f"Parsed {len(files)} files from response")

            # 6. Write files
            files_written = self._write_files(files)

            # 7. Run tests
            tests_passed = self._run_tests()

            # 8. Commit and push
            pushed = self._commit_and_push(files_written, branch_name)

            # 9. Create PR
            pr_url = None
            if pushed:
                pr_url = self._create_pr(branch_name, tests_passed)

            # 10. Update Jira
            self._update_jira(pr_url, success=True)

            # 11. Add agent/model/tech labels
            self._add_completion_labels(files_written)

            logger.info(
                f"Worker complete: {len(files_written)} files, "
                f"tests={'pass' if tests_passed else 'fail'}, "
                f"PR={pr_url or 'none'}"
            )

            return WorkerResult(
                success=True, provider=self.provider,
                ticket_key=self.ticket_key,
                files_written=files_written,
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
                success=False, provider=self.provider,
                ticket_key=self.ticket_key,
                files_written=[], tests_passed=False,
                pr_url=None, error=error_msg,
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provider Worker — implement a Jira ticket using an AI provider"
    )
    parser.add_argument(
        "--provider", required=True,
        choices=ProviderWorker.PROVIDERS,
        help="AI provider to use",
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
        help="Fetch ticket and parse response but don't write files or create PR",
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
    setup_logging(log_dir, args.provider, args.ticket)

    # Run worker
    worker = ProviderWorker(
        provider=args.provider,
        ticket_key=args.ticket,
        project_dir=project_dir,
        dry_run=args.dry_run,
    )
    result = worker.run()

    # Print summary
    print(f"\n{'='*70}")
    print(f"Worker Result: {args.provider} / {args.ticket}")
    print(f"{'='*70}")
    print(f"  Success: {result.success}")
    print(f"  Files written: {len(result.files_written)}")
    for f in result.files_written:
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
