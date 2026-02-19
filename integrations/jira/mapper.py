"""Jira ↔ Agent-Engineers field mapper (AI-250).

Provides bidirectional field mapping between Jira concepts
(issue types, priorities, statuses) and Agent-Engineers concepts.
"""

from __future__ import annotations

import re
from typing import List


# ---------------------------------------------------------------------------
# Issue type mapping  (Jira → Agent-Engineers)
# ---------------------------------------------------------------------------

_ISSUE_TYPE_MAP: dict[str, str] = {
    "story": "feature",
    "bug": "bug fix",
    "task": "task",
    "epic": "epic",
    "sub-task": "task",
    "subtask": "task",
    "improvement": "feature",
    "new feature": "feature",
    "technical task": "task",
    "test": "task",
    "spike": "task",
}

# ---------------------------------------------------------------------------
# Priority mapping  (Jira → integer 1-4)
# ---------------------------------------------------------------------------

_PRIORITY_MAP: dict[str, int] = {
    "highest": 1,
    "critical": 1,
    "blocker": 1,
    "high": 2,
    "major": 2,
    "medium": 3,
    "normal": 3,
    "low": 4,
    "minor": 4,
    "lowest": 4,
    "trivial": 4,
}

# ---------------------------------------------------------------------------
# Status mapping  (Jira → Agent-Engineers)
# ---------------------------------------------------------------------------

_STATUS_MAP: dict[str, str] = {
    "to do": "backlog",
    "open": "backlog",
    "new": "backlog",
    "reopened": "backlog",
    "in progress": "in_progress",
    "in development": "in_progress",
    "in review": "in_review",
    "code review": "in_review",
    "pr review": "in_review",
    "done": "done",
    "closed": "done",
    "resolved": "done",
    "won't do": "cancelled",
    "wont do": "cancelled",
    "duplicate": "cancelled",
    "cancelled": "cancelled",
}


class JiraIssueMapper:
    """Maps Jira fields to Agent-Engineers internal representation.

    All methods are stateless and can be used as classmethods or on an
    instance interchangeably.
    """

    # ------------------------------------------------------------------
    # Issue type
    # ------------------------------------------------------------------

    @staticmethod
    def map_issue_type(jira_type: str) -> str:
        """Map a Jira issue type string to an Agent-Engineers type.

        Mapping:
            Story      → feature
            Bug        → bug fix
            Task       → task
            Epic       → epic
            (unknown)  → task  (safe default)

        Args:
            jira_type: Jira issue type string (case-insensitive).

        Returns:
            Agent-Engineers issue type string.
        """
        return _ISSUE_TYPE_MAP.get(jira_type.lower().strip(), "task")

    # ------------------------------------------------------------------
    # Priority
    # ------------------------------------------------------------------

    @staticmethod
    def map_priority(jira_priority: str) -> int:
        """Map a Jira priority string to an integer urgency level.

        Mapping:
            Highest / Critical / Blocker → 1
            High / Major                 → 2
            Medium / Normal              → 3
            Low / Minor / Lowest         → 4
            (unknown)                    → 3  (medium default)

        Args:
            jira_priority: Jira priority string (case-insensitive).

        Returns:
            Integer priority (1 = most urgent).
        """
        return _PRIORITY_MAP.get(jira_priority.lower().strip(), 3)

    # ------------------------------------------------------------------
    # Acceptance criteria extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_acceptance_criteria(description: str) -> List[str]:
        """Parse acceptance-criteria lines from a Jira issue description.

        Looks for a section labelled "Acceptance Criteria" (case-insensitive)
        and extracts bullet-point lines that follow it.  Accepts both
        Markdown-style (``- item``, ``* item``) and numbered (``1. item``)
        bullets, as well as plain lines until the next heading.

        Args:
            description: Raw description text from the Jira issue.

        Returns:
            List of acceptance criteria strings (stripped, no leading bullet).
            Empty list if no section is found.
        """
        if not description:
            return []

        # Find the "Acceptance Criteria" section header
        ac_pattern = re.compile(
            r"(?:^|\n)\s*#+\s*acceptance\s+criteria[:\s]*\n(.*?)(?=\n\s*#|\Z)",
            re.IGNORECASE | re.DOTALL,
        )
        match = ac_pattern.search(description)

        # Fallback: look for "Acceptance Criteria:" as a plain header
        if not match:
            ac_pattern2 = re.compile(
                r"acceptance\s+criteria[:\s]*\n(.*?)(?=\n\s*[A-Z][^\n]*:|$)",
                re.IGNORECASE | re.DOTALL,
            )
            match = ac_pattern2.search(description)

        if not match:
            return []

        section = match.group(1)
        criteria: List[str] = []
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Strip leading bullet markers (handles "- [ ] item", "- [x] item",
            # "- item", "* item", "1. item", and "[ ] item" patterns)
            item = re.sub(
                r"^[-*•]\s+\[\s*[xX ]?\]\s*"   # "- [ ] " or "- [x] "
                r"|^[-*•]\s+"                    # "- " or "* "
                r"|^\d+\.\s+"                    # "1. "
                r"|^\[\s*[xX ]?\]\s*",           # "[ ] " or "[x] "
                "",
                stripped,
            )
            item = item.strip()
            if item:
                criteria.append(item)
        return criteria

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @staticmethod
    def map_status(jira_status: str) -> str:
        """Map a Jira issue status to an Agent-Engineers status.

        Mapping:
            To Do / Open / New           → backlog
            In Progress / In Development → in_progress
            In Review / Code Review      → in_review
            Done / Closed / Resolved     → done
            Won't Do / Duplicate         → cancelled
            (unknown)                    → backlog  (safe default)

        Args:
            jira_status: Jira status name (case-insensitive).

        Returns:
            Agent-Engineers status string.
        """
        return _STATUS_MAP.get(jira_status.lower().strip(), "backlog")

    # ------------------------------------------------------------------
    # Smart commit formatting
    # ------------------------------------------------------------------

    @staticmethod
    def format_smart_commit(issue_key: str, message: str) -> str:
        """Format a git commit message using Jira Smart Commit syntax.

        Smart commits allow Jira to automatically transition issues and
        add comments when commits are pushed.

        Format: ``PROJECT-123: message``

        Args:
            issue_key: Jira issue key, e.g. ``PROJECT-123``.
            message: Commit message body.

        Returns:
            Formatted commit message string.
        """
        return f"{issue_key}: {message}"
