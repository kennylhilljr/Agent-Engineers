"""
Duplicate Issue Detection and Cleanup
======================================

Utilities for preventing duplicate ticket creation in Linear,
and for cleaning up any duplicates that already exist.

Duplicates are detected by normalized title matching. The local state file
(.linear_project.json) tracks all created issue keys and titles so that
re-runs of the initializer don't create duplicates.
"""

import json
import re
from pathlib import Path
from typing import TypedDict

from progress import (
    ProjectState,
    LINEAR_PROJECT_MARKER,
    load_project_state,
)


class TrackedIssue(TypedDict):
    """An issue tracked in the local state file for dedup purposes."""

    key: str    # e.g. "AI-42"
    title: str  # Original issue title


def normalize_title(title: str) -> str:
    """
    Normalize an issue title for duplicate comparison.

    Strips whitespace, lowercases, and removes common prefixes/suffixes
    that might differ between duplicate creations.

    Args:
        title: Raw issue title

    Returns:
        Normalized title string for comparison
    """
    normalized = title.strip().lower()
    # Remove leading issue-key-style prefixes like "[AI-5]" or "ENG-42:"
    normalized = re.sub(r"^\[?[A-Z]+-\d+\]?\s*[:–—-]?\s*", "", normalized)
    # Collapse multiple whitespace
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def find_duplicates(issues: list[TrackedIssue]) -> dict[str, list[TrackedIssue]]:
    """
    Find duplicate issues by normalized title.

    Args:
        issues: List of tracked issues (key + title)

    Returns:
        Dict mapping normalized title -> list of issues with that title.
        Only includes titles that appear more than once.
    """
    by_title: dict[str, list[TrackedIssue]] = {}
    for issue in issues:
        norm = normalize_title(issue["title"])
        by_title.setdefault(norm, []).append(issue)

    return {title: group for title, group in by_title.items() if len(group) > 1}


def get_tracked_issues(project_dir: Path) -> list[TrackedIssue]:
    """
    Load the list of tracked issues from the project state file.

    Args:
        project_dir: Project directory containing the state file

    Returns:
        List of tracked issues, or empty list if none tracked yet
    """
    state = load_project_state(project_dir)
    if state is None:
        return []
    raw_issues = state.get("issues", [])
    if not isinstance(raw_issues, list):
        return []
    # Validate each entry has key and title
    result: list[TrackedIssue] = []
    for item in raw_issues:
        if isinstance(item, dict) and "key" in item and "title" in item:
            result.append(TrackedIssue(key=str(item["key"]), title=str(item["title"])))
    return result


def save_tracked_issues(
    project_dir: Path,
    issues: list[TrackedIssue],
) -> None:
    """
    Save the tracked issues list back to the project state file.

    Merges the issues list into the existing state without overwriting
    other fields.

    Args:
        project_dir: Project directory containing the state file
        issues: Updated list of tracked issues
    """
    marker_file = project_dir / LINEAR_PROJECT_MARKER

    # Load existing state or start fresh
    state: dict = {}
    if marker_file.exists():
        try:
            with open(marker_file, "r") as f:
                state = json.load(f)
        except (json.JSONDecodeError, IOError):
            state = {}

    state["issues"] = [{"key": i["key"], "title": i["title"]} for i in issues]

    with open(marker_file, "w") as f:
        json.dump(state, f, indent=2)


def is_duplicate_title(title: str, existing_issues: list[TrackedIssue]) -> bool:
    """
    Check if a title would be a duplicate of any existing tracked issue.

    Args:
        title: Proposed new issue title
        existing_issues: Already-created issues

    Returns:
        True if an issue with a matching normalized title already exists
    """
    norm = normalize_title(title)
    return any(normalize_title(issue["title"]) == norm for issue in existing_issues)


def deduplicate_issues(issues: list[TrackedIssue]) -> tuple[list[TrackedIssue], list[TrackedIssue]]:
    """
    Separate a list of issues into unique and duplicate groups.

    Keeps the first occurrence of each normalized title as the "keeper"
    and marks subsequent occurrences as duplicates.

    Args:
        issues: Full list of tracked issues

    Returns:
        Tuple of (keepers, duplicates) where:
        - keepers: First occurrence of each unique title
        - duplicates: All subsequent occurrences (to be archived/deleted)
    """
    seen: dict[str, TrackedIssue] = {}
    keepers: list[TrackedIssue] = []
    duplicates: list[TrackedIssue] = []

    for issue in issues:
        norm = normalize_title(issue["title"])
        if norm not in seen:
            seen[norm] = issue
            keepers.append(issue)
        else:
            duplicates.append(issue)

    return keepers, duplicates


def get_dedup_summary(project_dir: Path) -> str:
    """
    Generate a human-readable summary of duplicate issues.

    Args:
        project_dir: Project directory

    Returns:
        Summary string describing any duplicates found, or a clean message
    """
    issues = get_tracked_issues(project_dir)
    if not issues:
        return "No tracked issues found in project state."

    dups = find_duplicates(issues)
    if not dups:
        return f"No duplicates found among {len(issues)} tracked issues."

    lines = [f"Found {sum(len(g) - 1 for g in dups.values())} duplicate(s):"]
    for norm_title, group in dups.items():
        keeper = group[0]
        for dup in group[1:]:
            lines.append(f"  - {dup['key']} \"{dup['title']}\" (duplicate of {keeper['key']})")
    return "\n".join(lines)
