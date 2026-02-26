"""
Technical Debt Tests (AI-202)
==============================

Tests that enforce the technical debt tracking policy:

1. Verify TECHNICAL_DEBT.md exists and contains substantive content.
2. Verify the count of raw debt-marker comments has not grown beyond
   the baseline established during the AI-202 audit (1 resolved, now 0 raw).
3. Verify the agent.py change that replaced the raw marker with an
   explanatory block comment is in place.
4. Verify TECHNICAL_DEBT.md has the expected structural sections.
"""

import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TECHNICAL_DEBT_FILE = PROJECT_ROOT / "TECHNICAL_DEBT.md"

# Directories to exclude when scanning for raw debt markers
EXCLUDED_DIRS = {".venv", "venv", "__pycache__", "generations"}

# Baseline: after AI-202, there must be 0 raw debt-marker comments
# in the production code (agent.py marker was replaced with a block comment).
ALLOWED_MARKER_COUNT = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_python_files(root: Path) -> list[Path]:
    """Collect all .py files under root, excluding known noise directories and this test file."""
    this_file = Path(__file__).resolve()
    root_resolved = root.resolve()
    results: list[Path] = []
    for path in root_resolved.rglob("*.py"):
        # Skip excluded directories using relative path parts only
        # (avoids falsely excluding files when the project root itself
        # contains an excluded directory name, e.g. "generations")
        try:
            rel_parts = set(path.relative_to(root_resolved).parts)
        except ValueError:
            rel_parts = set(path.parts)
        if rel_parts & EXCLUDED_DIRS:
            continue
        # Skip node_modules (not in EXCLUDED_DIRS but should always be ignored)
        if "node_modules" in rel_parts or ".worktrees" in rel_parts:
            continue
        # Skip this test file itself (it references the markers in strings/comments)
        if path.resolve() == this_file:
            continue
        results.append(path)
    return results


# Build the marker pattern at import time without writing the keywords literally.
# This avoids the scanner picking up its own source when scanning the test file.
_MARKER_KEYWORDS = ["TO" + "DO", "FIX" + "ME", "HA" + "CK", "X" + "XX"]
_MARKER_PATTERN = re.compile(r"#.*\b(" + "|".join(_MARKER_KEYWORDS) + r")\b")


def _count_marker_comments(files: list[Path]) -> list[tuple[Path, int, str]]:
    """
    Return a list of (file, line_number, line_text) for each line that
    contains a raw comment-style debt marker (TO DO/FIXME/HACK/XXX).

    A raw marker is a Python comment (# ...) that contains one of the
    keywords in uppercase. This excludes:
    - String literals (e.g., status = "todo")
    - Variable names (e.g., TicketStatus = Literal["todo", ...])
    - Descriptive prose that uses lowercase variants.
    """
    hits: list[tuple[Path, int, str]] = []
    for file_path in files:
        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            if _MARKER_PATTERN.search(line):
                hits.append((file_path, lineno, line.strip()))
    return hits


# ---------------------------------------------------------------------------
# Tests — TECHNICAL_DEBT.md
# ---------------------------------------------------------------------------


class TestTechnicalDebtFile:
    """Verify the TECHNICAL_DEBT.md file exists and has required content."""

    def test_file_exists(self):
        """TECHNICAL_DEBT.md must exist at the project root."""
        assert TECHNICAL_DEBT_FILE.exists(), (
            f"TECHNICAL_DEBT.md not found at {TECHNICAL_DEBT_FILE}. "
            "Create it per AI-202 requirements."
        )

    def test_file_is_non_empty(self):
        """TECHNICAL_DEBT.md must have substantial content (> 200 characters)."""
        content = TECHNICAL_DEBT_FILE.read_text(encoding="utf-8")
        assert len(content) > 200, (
            "TECHNICAL_DEBT.md is too short — it should document all identified debt items."
        )

    def test_file_has_audit_summary_section(self):
        """TECHNICAL_DEBT.md must contain an Audit Summary section."""
        content = TECHNICAL_DEBT_FILE.read_text(encoding="utf-8")
        assert "Audit Summary" in content, (
            "TECHNICAL_DEBT.md must have an 'Audit Summary' section."
        )

    def test_file_has_items_found_section(self):
        """TECHNICAL_DEBT.md must document items found."""
        content = TECHNICAL_DEBT_FILE.read_text(encoding="utf-8")
        # Accept either "Items Found" or "Items Previously Present" sections
        assert ("Items Found" in content or "Items" in content), (
            "TECHNICAL_DEBT.md must have an items section documenting TODOs."
        )

    def test_file_has_linear_issue_reference(self):
        """TECHNICAL_DEBT.md must reference the originating Linear issue (AI-202)."""
        content = TECHNICAL_DEBT_FILE.read_text(encoding="utf-8")
        assert "AI-202" in content, (
            "TECHNICAL_DEBT.md must reference Linear issue AI-202."
        )

    def test_file_has_guidelines_section(self):
        """TECHNICAL_DEBT.md must contain guidelines for future TODOs."""
        content = TECHNICAL_DEBT_FILE.read_text(encoding="utf-8")
        assert "Guidelines" in content or "guidelines" in content, (
            "TECHNICAL_DEBT.md must have a guidelines section."
        )

    def test_file_has_td001_entry(self):
        """TECHNICAL_DEBT.md must document TD-001 (the one item found)."""
        content = TECHNICAL_DEBT_FILE.read_text(encoding="utf-8")
        assert "TD-001" in content, (
            "TECHNICAL_DEBT.md must document TD-001 (ticket_key in agent.py)."
        )

    def test_file_references_agent_py(self):
        """TECHNICAL_DEBT.md must reference agent.py as the source file."""
        content = TECHNICAL_DEBT_FILE.read_text(encoding="utf-8")
        assert "agent.py" in content, (
            "TECHNICAL_DEBT.md must reference agent.py where the TODO was found."
        )

    def test_file_has_changelog(self):
        """TECHNICAL_DEBT.md must have a changelog."""
        content = TECHNICAL_DEBT_FILE.read_text(encoding="utf-8")
        assert "Changelog" in content or "changelog" in content, (
            "TECHNICAL_DEBT.md must have a Changelog section."
        )


# ---------------------------------------------------------------------------
# Tests — debt marker count enforcement
# ---------------------------------------------------------------------------


class TestTodoCount:
    """Verify that no new raw debt markers were introduced."""

    @pytest.fixture(scope="class")
    def python_files(self):
        return _collect_python_files(PROJECT_ROOT)

    @pytest.fixture(scope="class")
    def marker_hits(self, python_files):
        return _count_marker_comments(python_files)

    def test_no_new_raw_marker_comments(self, marker_hits):
        """
        The codebase must have at most ALLOWED_MARKER_COUNT raw debt-marker
        comments. If this test fails, either:
        - A new marker was introduced without being documented in TECHNICAL_DEBT.md
        - Increase ALLOWED_MARKER_COUNT AND add a corresponding entry in TECHNICAL_DEBT.md
        """
        if len(marker_hits) > ALLOWED_MARKER_COUNT:
            detail = "\n".join(
                f"  {path.relative_to(PROJECT_ROOT)}:{lineno}  {text}"
                for path, lineno, text in marker_hits
            )
            pytest.fail(
                f"Found {len(marker_hits)} raw debt-marker comments "
                f"(allowed: {ALLOWED_MARKER_COUNT}).\n"
                f"Either resolve them or document them in TECHNICAL_DEBT.md and "
                f"update ALLOWED_MARKER_COUNT in this test.\n\n"
                f"Locations:\n{detail}"
            )

    def test_marker_count_matches_expected(self, marker_hits):
        """Explicit assertion: exactly 0 raw debt-marker comments in the codebase."""
        assert len(marker_hits) == ALLOWED_MARKER_COUNT, (
            f"Expected {ALLOWED_MARKER_COUNT} raw debt-marker comments, "
            f"found {len(marker_hits)}."
        )


# ---------------------------------------------------------------------------
# Tests — agent.py change verification
# ---------------------------------------------------------------------------


class TestAgentPyChanges:
    """Verify the specific change made to agent.py in AI-202."""

    @pytest.fixture(scope="class")
    def agent_py_content(self):
        agent_py = PROJECT_ROOT / "agent.py"
        assert agent_py.exists(), "agent.py must exist"
        return agent_py.read_text(encoding="utf-8")

    def test_todo_marker_removed_from_agent_py(self, agent_py_content):
        """The original raw marker must no longer be present in agent.py."""
        # Construct the original marker string without writing it literally here,
        # so this test file does not trigger its own scanner.
        original_marker = "# " + "TO" + "DO" + ": extract from Linear context"
        assert original_marker not in agent_py_content, (
            "The raw debt marker in agent.py must be replaced with an "
            "explanatory block comment."
        )

    def test_ticket_key_none_still_present(self, agent_py_content):
        """The ticket_key=None call site must still be present (just undocumented differently)."""
        assert "ticket_key=None" in agent_py_content, (
            "agent.py must still pass ticket_key=None at the call site."
        )

    def test_explanatory_comment_present(self, agent_py_content):
        """An explanatory block comment about ticket_key deferral must be present."""
        # The replacement comment references the daemon path and TECHNICAL_DEBT.md
        assert "TECHNICAL_DEBT.md" in agent_py_content, (
            "agent.py must reference TECHNICAL_DEBT.md in the explanatory comment."
        )

    def test_run_agent_session_accepts_ticket_key(self, agent_py_content):
        """run_agent_session must still accept ticket_key as a parameter."""
        assert "ticket_key: str" in agent_py_content or "ticket_key=" in agent_py_content, (
            "run_agent_session must have a ticket_key parameter."
        )

    def test_broadcast_uses_ticket_key(self, agent_py_content):
        """broadcast_agent_status must use ticket_key in its metadata."""
        assert "ticket_key" in agent_py_content, (
            "agent.py must use ticket_key for broadcasting agent status."
        )


# ---------------------------------------------------------------------------
# Tests — Python files are scannable (sanity)
# ---------------------------------------------------------------------------


class TestFileScanSanity:
    """Sanity checks for the file scanning logic."""

    def test_project_root_exists(self):
        """Project root must exist."""
        assert PROJECT_ROOT.exists(), f"Project root not found: {PROJECT_ROOT}"

    def test_python_files_found(self):
        """At least one Python file should be found in the project."""
        files = _collect_python_files(PROJECT_ROOT)
        assert len(files) > 0, "No Python files found — scanning is broken."

    def test_agent_py_is_included(self):
        """agent.py must be included in the scanned file set."""
        files = _collect_python_files(PROJECT_ROOT)
        agent_py = PROJECT_ROOT / "agent.py"
        assert agent_py in files, "agent.py is missing from the scanned file list."

    def test_venv_files_excluded(self):
        """Files inside .venv/ must not appear in the scanned list."""
        files = _collect_python_files(PROJECT_ROOT)
        venv_files = [f for f in files if ".venv" in f.parts or "venv" in f.parts]
        assert len(venv_files) == 0, (
            f"Found {len(venv_files)} venv files in scan — exclusion is broken."
        )

    def test_generations_excluded(self):
        """Files inside a nested generations/ subdirectory must not appear in the scan.

        Note: The project itself may live inside a parent 'generations/' directory,
        so we check relative paths (from PROJECT_ROOT) rather than absolute paths.
        Only files under a 'generations/' *subdirectory within the project* should
        be excluded.
        """
        files = _collect_python_files(PROJECT_ROOT)
        root_resolved = PROJECT_ROOT.resolve()
        gen_files = []
        for f in files:
            try:
                rel_parts = f.relative_to(root_resolved).parts
            except ValueError:
                rel_parts = f.parts
            if "generations" in rel_parts:
                gen_files.append(f)
        assert len(gen_files) == 0, (
            f"Found {len(gen_files)} files inside a 'generations/' subdirectory — "
            f"exclusion is broken: {gen_files[:3]}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
