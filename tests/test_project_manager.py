"""Tests for projects/project_manager.py — AI-225: Multi-Project Support.

Covers:
- Project dataclass creation and serialisation
- ProjectManager.create_project()
- ProjectManager.list_projects()
- ProjectManager.delete_project()
- ProjectManager.switch_project() / get_active_project()
- Tier limit enforcement
- Persistence: save and reload from .agent_projects.json
- Active-project tracking across operations
- Edge cases: duplicate names, unknown tier, empty name, etc.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# ---- import path setup ----
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from projects.project_manager import (
    Project,
    ProjectManager,
    TierLimitError,
    TIER_PROJECT_LIMITS,
    _PROJECTS_FILE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir():
    """Temporary directory that is cleaned up after each test."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def pm(tmp_dir):
    """ProjectManager with a fresh temp base dir and team tier (max 5)."""
    return ProjectManager(base_dir=tmp_dir, tier="team")


# ---------------------------------------------------------------------------
# Project dataclass tests
# ---------------------------------------------------------------------------


class TestProjectDataclass:
    """Tests for the Project dataclass."""

    def test_project_has_required_fields(self):
        """Project dataclass should have all required fields."""
        p = Project(id="abc", name="Test", directory="/tmp/test")
        assert p.id == "abc"
        assert p.name == "Test"
        assert p.directory == "/tmp/test"

    def test_project_optional_fields_default_empty(self):
        """Optional fields default to empty strings."""
        p = Project(id="x", name="Y", directory="")
        assert p.git_repo_url == ""
        assert p.linear_project_id == ""

    def test_project_created_at_populated(self):
        """created_at is auto-populated."""
        p = Project(id="x", name="Y", directory="")
        assert p.created_at  # non-empty

    def test_project_to_dict_roundtrip(self):
        """to_dict -> from_dict round-trip preserves data."""
        p = Project(
            id="uuid-123",
            name="My Repo",
            directory="/repo",
            git_repo_url="https://github.com/org/repo",
            linear_project_id="PROJ-1",
            created_at="2025-01-01T00:00:00+00:00",
        )
        d = p.to_dict()
        p2 = Project.from_dict(d)
        assert p2.id == p.id
        assert p2.name == p.name
        assert p2.directory == p.directory
        assert p2.git_repo_url == p.git_repo_url
        assert p2.linear_project_id == p.linear_project_id
        assert p2.created_at == p.created_at

    def test_project_from_dict_missing_optional_fields(self):
        """from_dict tolerates missing optional fields."""
        d = {"id": "x", "name": "Minimal", "directory": ""}
        p = Project.from_dict(d)
        assert p.id == "x"
        assert p.git_repo_url == ""
        assert p.linear_project_id == ""


# ---------------------------------------------------------------------------
# ProjectManager creation tests
# ---------------------------------------------------------------------------


class TestProjectManagerCreate:
    """Tests for ProjectManager.create_project()."""

    def test_create_single_project(self, pm):
        """Creating a project returns a Project with correct fields."""
        p = pm.create_project(name="Alpha", directory="/alpha")
        assert p.name == "Alpha"
        assert p.directory == "/alpha"
        assert p.id  # non-empty UUID

    def test_create_project_with_optional_fields(self, pm):
        """Optional fields are stored correctly."""
        p = pm.create_project(
            name="Beta",
            git_repo_url="https://github.com/x/y",
            linear_project_id="LIN-42",
            directory="/beta",
        )
        assert p.git_repo_url == "https://github.com/x/y"
        assert p.linear_project_id == "LIN-42"

    def test_create_multiple_projects(self, pm):
        """Multiple projects can be created up to the tier limit."""
        names = ["A", "B", "C"]
        for n in names:
            pm.create_project(name=n)
        assert len(pm.list_projects()) == 3

    def test_create_project_empty_name_raises(self, pm):
        """Empty name raises ValueError."""
        with pytest.raises(ValueError, match="name"):
            pm.create_project(name="")

    def test_create_project_whitespace_name_raises(self, pm):
        """Whitespace-only name raises ValueError."""
        with pytest.raises(ValueError, match="name"):
            pm.create_project(name="   ")

    def test_create_project_ids_are_unique(self, pm):
        """Each project gets a unique ID."""
        ids = {pm.create_project(name=f"P{i}").id for i in range(5)}
        assert len(ids) == 5

    def test_create_project_duplicate_name_allowed(self, pm):
        """Duplicate project names are allowed (no uniqueness constraint on name)."""
        pm.create_project(name="Same")
        pm.create_project(name="Same")
        assert len(pm.list_projects()) == 2


# ---------------------------------------------------------------------------
# ProjectManager list tests
# ---------------------------------------------------------------------------


class TestProjectManagerList:
    """Tests for ProjectManager.list_projects()."""

    def test_list_empty_returns_empty_list(self, pm):
        """list_projects returns [] when no projects exist."""
        assert pm.list_projects() == []

    def test_list_returns_all_projects(self, pm):
        """list_projects returns all created projects."""
        pm.create_project(name="X")
        pm.create_project(name="Y")
        names = {p.name for p in pm.list_projects()}
        assert names == {"X", "Y"}

    def test_list_sorted_by_created_at(self, pm):
        """list_projects returns projects sorted oldest first."""
        p1 = pm.create_project(name="First")
        p2 = pm.create_project(name="Second")
        p3 = pm.create_project(name="Third")
        listed = pm.list_projects()
        assert [p.name for p in listed] == ["First", "Second", "Third"]


# ---------------------------------------------------------------------------
# ProjectManager delete tests
# ---------------------------------------------------------------------------


class TestProjectManagerDelete:
    """Tests for ProjectManager.delete_project()."""

    def test_delete_existing_project(self, pm):
        """Deleting an existing project removes it."""
        p = pm.create_project(name="ToDelete")
        result = pm.delete_project(p.id)
        assert result is True
        assert len(pm.list_projects()) == 0

    def test_delete_nonexistent_project_returns_false(self, pm):
        """Deleting a non-existent ID returns False without raising."""
        result = pm.delete_project("not-a-real-id")
        assert result is False

    def test_delete_clears_active_if_active(self, pm):
        """Deleting the active project clears the active tracking."""
        p = pm.create_project(name="Active")
        pm.switch_project(p.id)
        assert pm.get_active_project() is not None
        pm.delete_project(p.id)
        assert pm.get_active_project() is None

    def test_delete_does_not_clear_active_if_different(self, pm):
        """Deleting a non-active project does NOT clear the active project."""
        p1 = pm.create_project(name="Active")
        p2 = pm.create_project(name="Other")
        pm.switch_project(p1.id)
        pm.delete_project(p2.id)
        assert pm.get_active_project().id == p1.id


# ---------------------------------------------------------------------------
# ProjectManager switch / active project tests
# ---------------------------------------------------------------------------


class TestProjectManagerSwitch:
    """Tests for switch_project() and get_active_project()."""

    def test_no_active_project_initially(self, pm):
        """Active project is None before any switch."""
        assert pm.get_active_project() is None

    def test_switch_sets_active_project(self, pm):
        """switch_project sets the active project."""
        p = pm.create_project(name="Main")
        returned = pm.switch_project(p.id)
        assert returned.id == p.id
        assert pm.get_active_project().id == p.id

    def test_switch_updates_active_project(self, pm):
        """Switching to a different project updates the active tracking."""
        p1 = pm.create_project(name="P1")
        p2 = pm.create_project(name="P2")
        pm.switch_project(p1.id)
        pm.switch_project(p2.id)
        assert pm.get_active_project().id == p2.id

    def test_switch_nonexistent_raises_key_error(self, pm):
        """switch_project raises KeyError for unknown ID."""
        with pytest.raises(KeyError):
            pm.switch_project("does-not-exist")

    def test_get_project_by_id(self, pm):
        """get_project returns the correct project by ID."""
        p = pm.create_project(name="Lookup")
        found = pm.get_project(p.id)
        assert found is not None
        assert found.name == "Lookup"

    def test_get_project_unknown_id_returns_none(self, pm):
        """get_project returns None for unknown ID."""
        assert pm.get_project("ghost-id") is None


# ---------------------------------------------------------------------------
# Tier limit enforcement tests
# ---------------------------------------------------------------------------


class TestTierLimits:
    """Tests for tier-based project-count enforcement."""

    def test_explorer_limit_is_1(self, tmp_dir):
        """Explorer tier allows at most 1 project."""
        pm = ProjectManager(base_dir=tmp_dir, tier="explorer")
        assert pm.max_projects == 1
        pm.create_project(name="Only One")
        with pytest.raises(TierLimitError):
            pm.create_project(name="Over Limit")

    def test_builder_limit_is_1(self, tmp_dir):
        """Builder tier allows at most 1 project."""
        pm = ProjectManager(base_dir=tmp_dir, tier="builder")
        assert pm.max_projects == 1

    def test_team_limit_is_5(self, tmp_dir):
        """Team tier allows at most 5 projects."""
        pm = ProjectManager(base_dir=tmp_dir, tier="team")
        assert pm.max_projects == 5
        for i in range(5):
            pm.create_project(name=f"P{i}")
        with pytest.raises(TierLimitError):
            pm.create_project(name="Over Limit")

    def test_scale_limit_is_25(self, tmp_dir):
        """Scale tier allows at most 25 projects."""
        pm = ProjectManager(base_dir=tmp_dir, tier="scale")
        assert pm.max_projects == 25

    def test_max_projects_override(self, tmp_dir):
        """max_projects parameter overrides tier limit."""
        pm = ProjectManager(base_dir=tmp_dir, max_projects=2)
        pm.create_project(name="A")
        pm.create_project(name="B")
        with pytest.raises(TierLimitError):
            pm.create_project(name="C")

    def test_unknown_tier_uses_default(self, tmp_dir):
        """Unknown tier falls back to default limit (5)."""
        pm = ProjectManager(base_dir=tmp_dir, tier="enterprise")
        assert pm.max_projects == 5

    def test_tier_error_message_informative(self, tmp_dir):
        """TierLimitError message mentions tier and limit."""
        pm = ProjectManager(base_dir=tmp_dir, tier="explorer")
        pm.create_project(name="First")
        with pytest.raises(TierLimitError, match="explorer"):
            pm.create_project(name="Second")


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------


class TestProjectManagerPersistence:
    """Tests for .agent_projects.json persistence and reload."""

    def test_projects_file_created_on_first_create(self, tmp_dir):
        """Projects file is created when the first project is saved."""
        pm = ProjectManager(base_dir=tmp_dir)
        pm.create_project(name="Saved")
        assert (tmp_dir / _PROJECTS_FILE).exists()

    def test_projects_file_is_valid_json(self, tmp_dir):
        """Projects file contains valid JSON after creation."""
        pm = ProjectManager(base_dir=tmp_dir)
        pm.create_project(name="Valid JSON")
        raw = (tmp_dir / _PROJECTS_FILE).read_text()
        data = json.loads(raw)
        assert "projects" in data

    def test_reload_recovers_projects(self, tmp_dir):
        """A new ProjectManager instance loads projects saved by a previous one."""
        pm1 = ProjectManager(base_dir=tmp_dir)
        p = pm1.create_project(name="Persisted")

        pm2 = ProjectManager(base_dir=tmp_dir)
        listed = pm2.list_projects()
        assert len(listed) == 1
        assert listed[0].id == p.id
        assert listed[0].name == "Persisted"

    def test_delete_persists_across_reload(self, tmp_dir):
        """Deleting a project is reflected after reloading from file."""
        pm1 = ProjectManager(base_dir=tmp_dir)
        p = pm1.create_project(name="ToDelete")
        pm1.delete_project(p.id)

        pm2 = ProjectManager(base_dir=tmp_dir)
        assert len(pm2.list_projects()) == 0

    def test_multiple_projects_reload_correctly(self, tmp_dir):
        """Multiple projects are all reloaded correctly."""
        pm1 = ProjectManager(base_dir=tmp_dir)
        for i in range(3):
            pm1.create_project(name=f"Project {i}", git_repo_url=f"https://github.com/org/repo{i}")

        pm2 = ProjectManager(base_dir=tmp_dir)
        loaded = pm2.list_projects()
        assert len(loaded) == 3
        names = {p.name for p in loaded}
        assert names == {"Project 0", "Project 1", "Project 2"}

    def test_active_project_not_persisted(self, tmp_dir):
        """Active project is NOT saved to file — reloading starts with no active project."""
        pm1 = ProjectManager(base_dir=tmp_dir)
        p = pm1.create_project(name="Active")
        pm1.switch_project(p.id)
        assert pm1.get_active_project() is not None

        pm2 = ProjectManager(base_dir=tmp_dir)
        # After reload, no active project is set
        assert pm2.get_active_project() is None


# ---------------------------------------------------------------------------
# TIER_PROJECT_LIMITS constant tests
# ---------------------------------------------------------------------------


class TestTierConstants:
    """Tests for the TIER_PROJECT_LIMITS constant."""

    def test_all_required_tiers_present(self):
        """All required tiers are defined."""
        for tier in ("explorer", "builder", "team", "scale"):
            assert tier in TIER_PROJECT_LIMITS

    def test_tier_values(self):
        """Tier limits have the expected values."""
        assert TIER_PROJECT_LIMITS["explorer"] == 1
        assert TIER_PROJECT_LIMITS["builder"] == 1
        assert TIER_PROJECT_LIMITS["team"] == 5
        assert TIER_PROJECT_LIMITS["scale"] == 25
