"""GitHub PR comment reporter for benchmark results (AI-248).

GitHubReporter formats BenchmarkResult data as markdown and posts it
as a comment on GitHub pull requests via the `gh` CLI.
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Optional

from benchmarks.runner import BenchmarkResult

logger = logging.getLogger(__name__)


class GitHubReporter:
    """Formats and posts benchmark results as GitHub PR comments.

    Uses the ``gh`` CLI to post comments, which must be authenticated
    (``gh auth login``) in the CI environment.

    Args:
        repo: Optional ``owner/repo`` slug.  If not given, ``gh`` infers
              it from the local git remote.
    """

    def __init__(self, repo: Optional[str] = None) -> None:
        self.repo = repo

    def format_benchmark_comment(self, result: BenchmarkResult) -> str:
        """Generate a markdown PR comment summarising a benchmark result.

        Args:
            result: The BenchmarkResult to format.

        Returns:
            A markdown-formatted string suitable for a GitHub PR comment.
        """
        regression_badge = (
            ":warning: **REGRESSION DETECTED**"
            if result.regression_detected
            else ":white_check_mark: No regression"
        )

        lines = [
            "## :bar_chart: Benchmark Results — AI-248",
            "",
            f"**Agent type:** `{result.agent_type}`  ",
            f"**Run ID:** `{result.run_id}`  ",
            f"**Timestamp:** {result.timestamp}  ",
            f"**Status:** {regression_badge}",
            "",
            "### Speed Metrics",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Avg task completion time | {result.speed.avg_task_completion_time:.3f}s |",
            f"| p50 latency | {result.speed.p50_latency:.3f}s |",
            f"| p95 latency | {result.speed.p95_latency:.3f}s |",
            f"| p99 latency | {result.speed.p99_latency:.3f}s |",
            f"| Ticket → PR time | {result.speed.ticket_to_pr_time:.1f}s |",
            "",
            "### Quality Metrics",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| PR approval rate (first review) | {result.quality.pr_approval_rate:.1%} |",
            f"| Test coverage delta | {result.quality.test_coverage_delta:+.2f}% |",
            f"| Defect density | {result.quality.defect_density:.2f} per 100 LOC |",
            "",
            "### Cost Metrics",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Cost per agent-hour | ${result.cost.cost_per_agent_hour:.4f} |",
            f"| Cost per ticket | ${result.cost.cost_per_ticket:.4f} |",
            f"| Haiku utilization | {result.cost.haiku_utilization:.1%} |",
            f"| Sonnet utilization | {result.cost.sonnet_utilization:.1%} |",
            f"| Opus utilization | {result.cost.opus_utilization:.1%} |",
            "",
        ]

        if result.metadata:
            lines += [
                "### Metadata",
                "",
                "```json",
                json.dumps(result.metadata, indent=2),
                "```",
                "",
            ]

        lines.append(
            "_Generated automatically by the AI-248 benchmark suite. "
            "View historical trends at `/api/benchmarks` on the dashboard._"
        )

        return "\n".join(lines)

    def post_pr_comment(
        self,
        pr_number: int,
        comment: str,
        repo: Optional[str] = None,
    ) -> bool:
        """Post a comment to a GitHub PR using the ``gh`` CLI.

        Args:
            pr_number: The pull request number to comment on.
            comment: The comment body (markdown).
            repo: Optional ``owner/repo`` override.  Falls back to
                  ``self.repo`` then to ``gh`` auto-detection.

        Returns:
            True if the comment was posted successfully, False otherwise.
        """
        effective_repo = repo or self.repo
        cmd = ["gh", "pr", "comment", str(pr_number), "--body", comment]
        if effective_repo:
            cmd += ["--repo", effective_repo]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info(
                    "Benchmark comment posted to PR #%d (repo=%s)",
                    pr_number,
                    effective_repo or "<auto>",
                )
                return True
            else:
                logger.warning(
                    "gh pr comment failed (rc=%d): %s",
                    result.returncode,
                    result.stderr.strip(),
                )
                return False
        except FileNotFoundError:
            logger.warning("gh CLI not found; cannot post PR comment")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("gh pr comment timed out for PR #%d", pr_number)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unexpected error posting PR comment: %s", exc)
            return False
