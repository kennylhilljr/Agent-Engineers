"""Unit tests for the prompt loading utilities in prompts.py

Tests cover:
- Prompt template loading from the prompts directory
- Path traversal prevention
- Missing template handling
- All prompt names load successfully
- copy_spec_to_project functionality
- find_active_spec functionality
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from prompts import (
    PROMPTS_DIR,
    copy_spec_to_project,
    find_active_spec,
    get_continuation_task,
    get_initializer_task,
    load_prompt,
)


class TestLoadPrompt:
    """Test suite for the load_prompt function."""

    def test_load_valid_prompt(self):
        """Test that a valid prompt name loads successfully."""
        content = load_prompt("initializer_task")
        assert isinstance(content, str)
        assert len(content) > 0

    def test_load_continuation_prompt(self):
        """Test that continuation_task prompt loads successfully."""
        content = load_prompt("continuation_task")
        assert isinstance(content, str)
        assert len(content) > 0

    def test_load_orchestrator_prompt(self):
        """Test that orchestrator_prompt loads successfully."""
        content = load_prompt("orchestrator_prompt")
        assert isinstance(content, str)
        assert len(content) > 0

    def test_path_traversal_with_dotdot(self):
        """Test that path traversal using .. is rejected."""
        with pytest.raises(ValueError, match="path traversal not allowed"):
            load_prompt("../etc/passwd")

    def test_path_traversal_double_dotdot(self):
        """Test that double dotdot path traversal is rejected."""
        with pytest.raises(ValueError, match="path traversal not allowed"):
            load_prompt("../../etc/passwd")

    def test_path_traversal_with_dotdot_in_middle(self):
        """Test that .. anywhere in name is rejected."""
        with pytest.raises(ValueError, match="path traversal not allowed"):
            load_prompt("foo/../bar")

    def test_absolute_path_rejected(self):
        """Test that absolute paths starting with / are rejected."""
        with pytest.raises(ValueError, match="path traversal not allowed"):
            load_prompt("/etc/passwd")

    def test_absolute_path_backslash_rejected(self):
        """Test that absolute paths starting with backslash are rejected."""
        with pytest.raises(ValueError, match="path traversal not allowed"):
            load_prompt("\\windows\\system32")

    def test_missing_prompt_raises_file_not_found(self):
        """Test that a missing prompt raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Prompt file not found"):
            load_prompt("nonexistent_prompt_name_xyz")

    def test_prompt_content_is_string(self):
        """Test that prompt content is returned as a string."""
        content = load_prompt("coding_agent_prompt")
        assert isinstance(content, str)

    def test_prompt_not_empty(self):
        """Test that loaded prompts are not empty."""
        content = load_prompt("linear_agent_prompt")
        assert content.strip() != ""

    def test_all_known_prompts_load(self):
        """Test that all known prompt names load without error."""
        known_prompts = [
            "chatgpt_agent_prompt",
            "coding_agent_prompt",
            "continuation_task",
            "gemini_agent_prompt",
            "github_agent_prompt",
            "groq_agent_prompt",
            "initializer_task",
            "kimi_agent_prompt",
            "linear_agent_prompt",
            "ops_agent_prompt",
            "orchestrator_prompt",
            "pr_reviewer_agent_prompt",
            "slack_agent_prompt",
            "windsurf_agent_prompt",
        ]
        for name in known_prompts:
            content = load_prompt(name)
            assert isinstance(content, str), f"Prompt {name!r} should return a string"
            assert len(content) > 0, f"Prompt {name!r} should not be empty"


class TestGetInitializerTask:
    """Tests for the get_initializer_task function."""

    def test_returns_string_with_project_dir(self):
        """Test that initializer task includes the project directory."""
        project_dir = Path("/some/test/project")
        result = get_initializer_task(project_dir)
        assert isinstance(result, str)
        assert str(project_dir) in result

    def test_format_substitution_works(self):
        """Test that {project_dir} placeholder is substituted."""
        project_dir = Path("/my/unique/path_12345")
        result = get_initializer_task(project_dir)
        assert "/my/unique/path_12345" in result
        # The raw placeholder should not appear after substitution
        assert "{project_dir}" not in result


class TestGetContinuationTask:
    """Tests for the get_continuation_task function."""

    def test_returns_string_with_project_dir(self):
        """Test that continuation task includes the project directory."""
        project_dir = Path("/some/test/project")
        result = get_continuation_task(project_dir)
        assert isinstance(result, str)
        assert str(project_dir) in result

    def test_format_substitution_works(self):
        """Test that {project_dir} placeholder is substituted."""
        project_dir = Path("/my/unique/cont_path_12345")
        result = get_continuation_task(project_dir)
        assert "/my/unique/cont_path_12345" in result
        assert "{project_dir}" not in result

    def test_different_from_initializer(self):
        """Test that continuation task differs from initializer task."""
        project_dir = Path("/test/path")
        initializer = get_initializer_task(project_dir)
        continuation = get_continuation_task(project_dir)
        assert initializer != continuation


class TestFindActiveSpec:
    """Tests for the find_active_spec function."""

    def test_finds_spec_in_specs_dir(self):
        """Test that find_active_spec returns a valid path."""
        # This test is skipped if no spec file exists
        try:
            result = find_active_spec()
            assert isinstance(result, Path)
            assert result.exists()
        except FileNotFoundError:
            pytest.skip("No spec file found in specs/ directory")

    def test_raises_when_no_spec_exists(self):
        """Test that FileNotFoundError is raised when no spec file exists."""
        with patch("prompts.SPECS_DIR", Path("/nonexistent/specs/dir")):
            with pytest.raises(FileNotFoundError, match="No spec file found"):
                find_active_spec()


class TestCopySpecToProject:
    """Tests for the copy_spec_to_project function."""

    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up temporary directory after each test."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_copy_with_explicit_spec_path(self):
        """Test copying a spec file to project directory."""
        # Create a fake spec file
        spec_file = self.temp_dir / "test_spec.md"
        spec_file.write_text("# Test Spec\nThis is a test spec.")

        project_dir = self.temp_dir / "project"
        project_dir.mkdir()

        copy_spec_to_project(project_dir, spec_path=spec_file)

        dest = project_dir / "app_spec.txt"
        assert dest.exists()
        assert dest.read_text() == "# Test Spec\nThis is a test spec."

    def test_no_copy_if_dest_exists(self):
        """Test that copy is skipped if app_spec.txt already exists."""
        spec_file = self.temp_dir / "test_spec.md"
        spec_file.write_text("New content")

        project_dir = self.temp_dir / "project"
        project_dir.mkdir()

        # Pre-create the destination file
        existing_dest = project_dir / "app_spec.txt"
        existing_dest.write_text("Existing content")

        copy_spec_to_project(project_dir, spec_path=spec_file)

        # Should still have old content
        assert existing_dest.read_text() == "Existing content"

    def test_raises_when_spec_source_missing(self):
        """Test that FileNotFoundError is raised when source spec doesn't exist."""
        project_dir = self.temp_dir / "project"
        project_dir.mkdir()
        missing_spec = self.temp_dir / "nonexistent_spec.md"

        with pytest.raises(FileNotFoundError):
            copy_spec_to_project(project_dir, spec_path=missing_spec)

    def test_auto_detect_spec_raises_when_none(self):
        """Test that auto-detection raises FileNotFoundError with no specs."""
        project_dir = self.temp_dir / "project"
        project_dir.mkdir()

        with patch("prompts.SPECS_DIR", Path("/nonexistent/specs/dir")):
            with pytest.raises(FileNotFoundError):
                copy_spec_to_project(project_dir)
