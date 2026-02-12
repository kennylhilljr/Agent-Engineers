#!/usr/bin/env python3
"""
Review Worker — Peer Review of PRs and Jira Tasks
===================================================

Picks up Jira tickets in "Review" status, performs peer review of the
associated GitHub PR using a DIFFERENT AI provider than the one that
implemented the ticket (separation of duties), and transitions the ticket
to Done (approved) or back to To Do (changes requested).

Workflow:
  1. Query Jira for tickets in Review status
  2. For each ticket, find the implementing agent from labels (worker:<agent>)
  3. Choose a DIFFERENT provider to perform the review
  4. Fetch the PR diff from GitHub
  5. Send diff + ticket requirements to the reviewing provider
  6. Parse the review decision (APPROVED / CHANGES_REQUESTED)
  7. Post review comment on GitHub PR
  8. If approved: merge PR, transition Jira to Done
  9. If changes requested: post feedback, transition Jira back to To Do

Usage:
    # Review all tickets in Review column
    python scripts/review_worker.py --project-dir ai-coding-dashboard

    # Use a specific reviewer provider
    python scripts/review_worker.py --project-dir ai-coding-dashboard \
        --reviewer chatgpt

    # Dry run
    python scripts/review_worker.py --project-dir ai-coding-dashboard --dry-run

    # Review a single ticket
    python scripts/review_worker.py --project-dir ai-coding-dashboard \
        --ticket KAN-200
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

REVIEW_PROVIDERS = ("chatgpt", "gemini", "groq", "claude")

# Map of implementing agent -> preferred reviewer (round-robin separation)
REVIEWER_ROTATION = {
    "claude": "chatgpt",
    "chatgpt": "gemini",
    "gemini": "groq",
    "groq": "claude",
    "kimi": "chatgpt",
    "windsurf": "gemini",
}

# Model labels for the reviewing agent
REVIEWER_MODEL_LABELS = {
    "chatgpt": "reviewer-model:gpt-4o",
    "gemini": "reviewer-model:gemini-2.5-flash",
    "groq": "reviewer-model:llama-3.3-70b",
    "claude": "reviewer-model:claude-sonnet-4",
}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATEFMT = "%Y-%m-%dT%H:%M:%S"

logger = logging.getLogger("review_worker")


def setup_logging(log_dir: Path) -> None:
    """Configure logging to file + stderr."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "review_worker.log"

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))

    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stderr_handler)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class ReviewResult:
    """Result of a peer review."""
    ticket_key: str
    pr_number: Optional[int]
    decision: str  # "APPROVED" or "CHANGES_REQUESTED"
    reviewer: str
    implementer: str
    summary: str
    blocking_issues: list[str]
    suggestions: list[str]
    merged: bool
    error: Optional[str]


# ---------------------------------------------------------------------------
# Review Worker
# ---------------------------------------------------------------------------

class ReviewWorker:
    """Performs peer review of GitHub PRs linked to Jira tickets."""

    def __init__(
        self,
        project_dir: Path,
        reviewer: Optional[str] = None,
        dry_run: bool = False,
    ):
        self.project_dir = project_dir.resolve()
        self.forced_reviewer = reviewer
        self.dry_run = dry_run
        self.jira = JiraClient()
        self.github_repo = os.environ.get("GITHUB_REPO", "")

    def _get_implementing_agent(self, labels: list[str]) -> Optional[str]:
        """Extract the implementing agent from Jira labels (worker:<agent>)."""
        for label in labels:
            if label.startswith("worker:"):
                return label.split(":", 1)[1]
            if label.startswith("agent:"):
                return label.split(":", 1)[1]
        return None

    def _choose_reviewer(self, implementer: Optional[str]) -> str:
        """Choose a reviewer that is DIFFERENT from the implementer."""
        if self.forced_reviewer:
            return self.forced_reviewer

        if implementer and implementer in REVIEWER_ROTATION:
            return REVIEWER_ROTATION[implementer]

        # Default: use chatgpt
        return "chatgpt"

    def _init_bridge(self, reviewer: str):
        """Initialize the AI bridge for the reviewer."""
        if reviewer == "chatgpt":
            from openai_bridge import OpenAIBridge
            return OpenAIBridge.from_env()
        elif reviewer == "gemini":
            from gemini_bridge import GeminiBridge
            return GeminiBridge.from_env()
        elif reviewer == "groq":
            from groq_bridge import GroqBridge
            return GroqBridge()
        elif reviewer == "claude":
            # Use OpenAI bridge with Anthropic-compatible endpoint, or fallback
            # For now, use Gemini as Claude can't easily review its own PRs via API
            from gemini_bridge import GeminiBridge
            return GeminiBridge.from_env()
        else:
            raise ValueError(f"Unknown reviewer: {reviewer}")

    def _find_pr_for_ticket(self, ticket_key: str) -> Optional[dict]:
        """Find the GitHub PR associated with a Jira ticket."""
        if not self.github_repo:
            logger.warning("GITHUB_REPO not set, cannot find PR")
            return None

        owner, repo = self.github_repo.split("/", 1)

        # Search for open PRs mentioning the ticket key
        result = subprocess.run(
            ["gh", "pr", "list", "--repo", self.github_repo,
             "--state", "open", "--json", "number,title,headRefName,url,body",
             "--limit", "50"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.error(f"Failed to list PRs: {result.stderr}")
            return None

        try:
            prs = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse PR list: {result.stdout[:500]}")
            return None

        ticket_lower = ticket_key.lower()
        for pr in prs:
            # Match by branch name (feat/<agent>/<ticket>) or PR title/body
            branch = pr.get("headRefName", "").lower()
            title = pr.get("title", "").lower()
            body = pr.get("body", "").lower()

            if (ticket_lower in branch or
                ticket_lower in title or
                ticket_key in pr.get("title", "") or
                ticket_key in pr.get("body", "")):
                logger.info(f"Found PR #{pr['number']} for {ticket_key}: {pr['title']}")
                return pr

        logger.warning(f"No open PR found for {ticket_key}")
        return None

    def _get_pr_diff(self, pr_number: int) -> str:
        """Get the diff for a PR."""
        result = subprocess.run(
            ["gh", "pr", "diff", str(pr_number),
             "--repo", self.github_repo],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            logger.error(f"Failed to get PR diff: {result.stderr}")
            return ""

        diff = result.stdout
        # Truncate very large diffs
        if len(diff) > 15000:
            diff = diff[:15000] + "\n\n... (diff truncated, showing first 15000 chars)"

        return diff

    def _get_pr_files(self, pr_number: int) -> list[dict]:
        """Get the list of files changed in a PR."""
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number),
             "--repo", self.github_repo,
             "--json", "files"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return []

        try:
            data = json.loads(result.stdout)
            return data.get("files", [])
        except json.JSONDecodeError:
            return []

    def _build_review_prompt(self, ticket: dict, pr: dict, diff: str) -> str:
        """Build the review prompt for the AI provider."""
        return f"""You are performing a peer code review of a GitHub Pull Request.

## Jira Ticket
- Key: {ticket['key']}
- Title: {ticket['title']}
- Description:
{ticket.get('description', 'No description')}
{f"- Test Steps: {ticket.get('test_steps', '')}" if ticket.get('test_steps') else ""}

## Pull Request
- PR #{pr['number']}: {pr['title']}
- Branch: {pr.get('headRefName', 'unknown')}

## Code Changes (Diff)
```diff
{diff}
```

## Review Checklist

Evaluate ALL of the following:

1. **Code Quality**: Clean, readable, well-organized? No dead code or TODOs?
2. **Correctness**: Does the implementation match the Jira requirements? Edge cases handled?
3. **Security**: Any XSS, injection, exposed secrets, or OWASP vulnerabilities?
4. **Types**: TypeScript types correct and complete?
5. **Architecture**: Follows existing project patterns (Next.js App Router, Tailwind, shadcn/ui)?
6. **Error Handling**: Appropriate error handling in place?

## Your Response Format

You MUST respond in this exact format:

DECISION: APPROVED
or
DECISION: CHANGES_REQUESTED

SUMMARY: [1-2 sentence summary of review]

BLOCKING_ISSUES:
- [issue 1 with file:line reference]
- [issue 2]
(leave empty if APPROVED)

SUGGESTIONS:
- [non-blocking suggestion 1]
- [non-blocking suggestion 2]
(optional, can be empty)

## Important Rules
- Be thorough but fair — focus on correctness, not style preferences
- If the code compiles, passes tests, and meets the requirements, lean toward APPROVED
- Always reference specific files and line numbers when noting issues
- Missing or broken implementation of key requirements is always a blocking issue
- Minor style preferences are NEVER blocking issues
"""

    def _parse_review_response(self, response: str) -> dict:
        """Parse the AI provider's review response."""
        result = {
            "decision": "CHANGES_REQUESTED",  # Default to cautious
            "summary": "",
            "blocking_issues": [],
            "suggestions": [],
        }

        # Extract decision
        decision_match = re.search(r"DECISION:\s*(APPROVED|CHANGES_REQUESTED)", response, re.IGNORECASE)
        if decision_match:
            result["decision"] = decision_match.group(1).upper()

        # Extract summary
        summary_match = re.search(r"SUMMARY:\s*(.+?)(?=\n\n|\nBLOCKING|\nSUGGESTION)", response, re.DOTALL)
        if summary_match:
            result["summary"] = summary_match.group(1).strip()

        # Extract blocking issues
        blocking_match = re.search(r"BLOCKING_ISSUES:\s*\n((?:- .+\n?)*)", response)
        if blocking_match:
            issues = blocking_match.group(1).strip()
            result["blocking_issues"] = [
                line.lstrip("- ").strip()
                for line in issues.split("\n")
                if line.strip() and line.strip() != "-"
            ]

        # Extract suggestions
        suggestions_match = re.search(r"SUGGESTIONS:\s*\n((?:- .+\n?)*)", response)
        if suggestions_match:
            suggestions = suggestions_match.group(1).strip()
            result["suggestions"] = [
                line.lstrip("- ").strip()
                for line in suggestions.split("\n")
                if line.strip() and line.strip() != "-"
            ]

        return result

    def _post_review_comment(self, pr_number: int, review: dict,
                              reviewer: str, implementer: str) -> None:
        """Post a review comment on the GitHub PR."""
        if review["decision"] == "APPROVED":
            emoji = "white_check_mark"
            header = "PR Review: APPROVED"
            checklist = "All checks passed"
        else:
            emoji = "arrows_counterclockwise"
            header = "PR Review: CHANGES REQUESTED"
            checklist = "Issues found that need to be addressed"

        body_parts = [
            f"## {header}",
            f"",
            f"**Reviewer:** {reviewer} (AI peer reviewer)",
            f"**Implementer:** {implementer or 'unknown'}",
            f"",
            f"### Summary",
            review["summary"] or "Review complete.",
            "",
        ]

        if review["blocking_issues"]:
            body_parts.append("### Blocking Issues (must fix)")
            for i, issue in enumerate(review["blocking_issues"], 1):
                body_parts.append(f"{i}. {issue}")
            body_parts.append("")

        if review["suggestions"]:
            body_parts.append("### Non-blocking Suggestions")
            for s in review["suggestions"]:
                body_parts.append(f"- {s}")
            body_parts.append("")

        body_parts.append(f"### Decision: {'Merging this PR.' if review['decision'] == 'APPROVED' else 'Please address the blocking issues above.'}")
        body_parts.append("")
        body_parts.append(f"*Automated review by {reviewer} review worker*")

        body = "\n".join(body_parts)

        result = subprocess.run(
            ["gh", "pr", "comment", str(pr_number),
             "--repo", self.github_repo,
             "--body", body],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.error(f"Failed to post review comment: {result.stderr}")
        else:
            logger.info(f"Posted review comment on PR #{pr_number}")

    def _merge_pr(self, pr_number: int) -> bool:
        """Merge a PR using squash merge."""
        result = subprocess.run(
            ["gh", "pr", "merge", str(pr_number),
             "--repo", self.github_repo,
             "--squash", "--delete-branch"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            logger.error(f"Failed to merge PR #{pr_number}: {result.stderr}")
            return False

        logger.info(f"Merged PR #{pr_number}")
        return True

    def review_ticket(self, ticket: dict) -> ReviewResult:
        """Perform a full peer review of a single Jira ticket."""
        ticket_key = ticket["key"]
        labels = ticket.get("labels", [])
        implementer = self._get_implementing_agent(labels)
        reviewer = self._choose_reviewer(implementer)

        logger.info(
            f"Reviewing {ticket_key}: '{ticket['title']}' "
            f"(implementer={implementer}, reviewer={reviewer})"
        )

        try:
            # 1. Fetch full ticket details
            full_ticket = self.jira.get_issue(ticket_key)

            # 2. Find the associated PR
            pr = self._find_pr_for_ticket(ticket_key)
            if not pr:
                return ReviewResult(
                    ticket_key=ticket_key, pr_number=None,
                    decision="CHANGES_REQUESTED",
                    reviewer=reviewer, implementer=implementer or "unknown",
                    summary="No open PR found for this ticket.",
                    blocking_issues=["No PR found — implementation may not have been pushed."],
                    suggestions=[], merged=False, error="No PR found",
                )

            pr_number = pr["number"]

            # 3. Get the PR diff
            diff = self._get_pr_diff(pr_number)
            if not diff:
                return ReviewResult(
                    ticket_key=ticket_key, pr_number=pr_number,
                    decision="CHANGES_REQUESTED",
                    reviewer=reviewer, implementer=implementer or "unknown",
                    summary="PR has no changes (empty diff).",
                    blocking_issues=["Empty diff — no code changes found."],
                    suggestions=[], merged=False, error="Empty diff",
                )

            if self.dry_run:
                logger.info(f"[DRY RUN] Would review PR #{pr_number} with {reviewer}")
                print(f"\n{'='*70}")
                print(f"DRY RUN — Review {ticket_key} PR #{pr_number}")
                print(f"{'='*70}")
                print(f"  Implementer: {implementer}")
                print(f"  Reviewer: {reviewer}")
                print(f"  Diff length: {len(diff)} chars")
                print(f"  Would send to {reviewer} for review")
                return ReviewResult(
                    ticket_key=ticket_key, pr_number=pr_number,
                    decision="DRY_RUN", reviewer=reviewer,
                    implementer=implementer or "unknown",
                    summary="Dry run — no review performed.",
                    blocking_issues=[], suggestions=[],
                    merged=False, error=None,
                )

            # 4. Build review prompt
            prompt = self._build_review_prompt(full_ticket, pr, diff)
            logger.info(f"Built review prompt ({len(prompt)} chars)")

            # 5. Send to reviewer provider
            bridge = self._init_bridge(reviewer)
            system_prompt = (
                "You are an expert code reviewer for a Next.js/TypeScript web application. "
                "You review Pull Requests for correctness, code quality, security, and "
                "completeness against Jira ticket requirements. You follow the response "
                "format exactly as specified."
            )
            session = bridge.create_session(system_prompt=system_prompt)
            response = bridge.send_message(session, prompt)
            response_text = response.content
            logger.info(f"Received review from {reviewer} ({len(response_text)} chars)")

            # 6. Parse the review
            review = self._parse_review_response(response_text)
            logger.info(
                f"Review decision: {review['decision']} — "
                f"{len(review['blocking_issues'])} blocking, "
                f"{len(review['suggestions'])} suggestions"
            )

            # 7. Post review comment on PR
            self._post_review_comment(pr_number, review, reviewer, implementer)

            # 8. Act on the decision
            merged = False
            if review["decision"] == "APPROVED":
                # Merge the PR
                merged = self._merge_pr(pr_number)

                # Transition Jira to Done
                if not self.jira.transition_by_name(ticket_key, "Done"):
                    logger.warning(f"Could not transition {ticket_key} to Done")

                # Add reviewer label
                self.jira.add_label(ticket_key, f"reviewer:{reviewer}")
                try:
                    self.jira.add_label(ticket_key, REVIEWER_MODEL_LABELS.get(reviewer, f"reviewer-model:{reviewer}"))
                except Exception:
                    pass

                # Add approval comment to Jira
                self.jira.add_comment(
                    ticket_key,
                    f"[{reviewer}] PR #{pr_number} peer review: APPROVED and merged.\n"
                    f"Summary: {review['summary']}\n"
                    f"Timestamp: {datetime.now(timezone.utc).isoformat()}"
                )
            else:
                # Changes requested — move back to To Do
                self.jira.add_comment(
                    ticket_key,
                    f"[{reviewer}] PR #{pr_number} peer review: CHANGES REQUESTED.\n"
                    f"Summary: {review['summary']}\n"
                    f"Blocking issues:\n" +
                    "\n".join(f"  - {i}" for i in review['blocking_issues']) +
                    f"\nTimestamp: {datetime.now(timezone.utc).isoformat()}"
                )

                # Remove claim and transition back to To Do for rework
                if implementer:
                    self.jira.unclaim_ticket(ticket_key, implementer)
                else:
                    self.jira.transition_by_name(ticket_key, "To Do")

            return ReviewResult(
                ticket_key=ticket_key, pr_number=pr_number,
                decision=review["decision"], reviewer=reviewer,
                implementer=implementer or "unknown",
                summary=review["summary"],
                blocking_issues=review["blocking_issues"],
                suggestions=review["suggestions"],
                merged=merged, error=None,
            )

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.error(f"Review failed for {ticket_key}: {error_msg}")
            return ReviewResult(
                ticket_key=ticket_key, pr_number=None,
                decision="ERROR", reviewer=reviewer,
                implementer=implementer or "unknown",
                summary=f"Review failed: {error_msg}",
                blocking_issues=[], suggestions=[],
                merged=False, error=error_msg,
            )

    def run(self, ticket_key: Optional[str] = None) -> list[ReviewResult]:
        """Run the review worker.

        If ticket_key is provided, review just that ticket.
        Otherwise, query Jira for all tickets in Review status.
        """
        results = []

        if ticket_key:
            # Review a single ticket
            ticket = self.jira.get_issue(ticket_key)
            result = self.review_ticket(ticket)
            results.append(result)
        else:
            # Query for all Review tickets
            try:
                tickets = self.jira.get_review_tickets()
            except Exception as e:
                logger.error(f"Failed to query Review tickets: {e}")
                return results

            if not tickets:
                logger.info("No tickets in Review status")
                return results

            logger.info(f"Found {len(tickets)} tickets in Review status")

            for ticket in tickets:
                result = self.review_ticket(ticket)
                results.append(result)

        return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review Worker — peer review PRs and Jira tasks"
    )
    parser.add_argument(
        "--project-dir", required=True, type=Path,
        help="Project directory name (relative to GENERATIONS_BASE_PATH) or absolute path",
    )
    parser.add_argument(
        "--reviewer", choices=REVIEW_PROVIDERS,
        help="Force a specific reviewer provider (default: auto-select based on implementer)",
    )
    parser.add_argument(
        "--ticket",
        help="Review a single Jira ticket key (e.g., KAN-200)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Find review tickets and show what would be reviewed without sending to AI",
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
    print(f"  PEER REVIEW WORKER")
    print(f"{'='*70}")
    print(f"  Project: {project_dir}")
    print(f"  Reviewer: {args.reviewer or 'auto (separation of duties)'}")
    print(f"  Ticket: {args.ticket or 'all in Review'}")
    print(f"  Dry run: {args.dry_run}")
    print(f"{'='*70}\n")

    worker = ReviewWorker(
        project_dir=project_dir,
        reviewer=args.reviewer,
        dry_run=args.dry_run,
    )

    results = worker.run(ticket_key=args.ticket)

    # Print summary
    print(f"\n{'='*70}")
    print(f"  REVIEW RESULTS")
    print(f"{'='*70}")

    if not results:
        print("  No reviews performed.")
    else:
        for r in results:
            status = r.decision
            if r.merged:
                status += " + MERGED"
            print(
                f"  {r.ticket_key:10s}  PR#{r.pr_number or '?':4}  "
                f"{status:30s}  reviewer={r.reviewer}  impl={r.implementer}"
            )
            if r.summary:
                print(f"    Summary: {r.summary[:100]}")
            if r.blocking_issues:
                for issue in r.blocking_issues[:3]:
                    print(f"    BLOCKING: {issue[:100]}")
            if r.error:
                print(f"    ERROR: {r.error}")

    print(f"{'='*70}\n")

    # Output results as JSON
    for r in results:
        print(f"RESULT_JSON:{json.dumps(dataclasses.asdict(r))}")

    # Return non-zero if any review had errors
    has_errors = any(r.error for r in results)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
