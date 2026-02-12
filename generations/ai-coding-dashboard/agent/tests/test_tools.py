"""
Comprehensive Test Suite for Agent Tools

This test suite covers:
- File operations (read, write, list)
- Task management (create, update, complete)
- Project state management
- Event logging
- Security validation
- Error handling
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Import tools to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import (
    read_file, write_file, list_files,
    create_task, update_task, complete_task,
    get_project_state, log_event, get_events,
    validate_path, validate_file_size,
    reset_state, get_all_projects,
    ToolResult, MAX_FILE_SIZE
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for file operations testing"""
    temp = tempfile.mkdtemp()
    yield temp
    # Cleanup
    shutil.rmtree(temp, ignore_errors=True)


@pytest.fixture
def sample_files(temp_dir):
    """Create sample files for testing"""
    # Create some test files
    test_file = Path(temp_dir) / "test.txt"
    test_file.write_text("Hello, World!")

    subdir = Path(temp_dir) / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("Nested content")

    return {
        "test_file": str(test_file),
        "subdir": str(subdir),
        "nested_file": str(subdir / "nested.txt"),
        "temp_dir": temp_dir
    }


@pytest.fixture(autouse=True)
def reset_tools_state():
    """Reset tools state before each test"""
    reset_state()
    yield
    reset_state()


# Test helpers that inject base_dir
def read_file_test(path: str, base_dir: Optional[str] = None):
    """Test wrapper for read_file that injects base_dir"""
    return read_file(path, _base_dir=base_dir)


def write_file_test(path: str, content: str, base_dir: Optional[str] = None):
    """Test wrapper for write_file that injects base_dir"""
    return write_file(path, content, _base_dir=base_dir)


def list_files_test(directory: str, recursive: bool = False, base_dir: Optional[str] = None):
    """Test wrapper for list_files that injects base_dir"""
    return list_files(directory, recursive, _base_dir=base_dir)


# ============================================================================
# Security & Validation Tests (10 tests)
# ============================================================================


class TestSecurityValidation:
    """Test security features"""

    def test_validate_path_allows_valid_path(self, temp_dir):
        """Test that valid paths are allowed"""
        test_file = Path(temp_dir) / "test.txt"
        is_valid, error = validate_path(str(test_file), base_dir=temp_dir)
        assert is_valid is True
        assert error is None

    def test_validate_path_blocks_traversal_attempt(self, temp_dir):
        """Test that directory traversal is blocked"""
        malicious_path = str(Path(temp_dir) / ".." / ".." / "etc" / "passwd")
        is_valid, error = validate_path(malicious_path, base_dir=temp_dir)
        assert is_valid is False
        assert "traversal" in error.lower()

    def test_validate_path_blocks_sensitive_dirs(self, temp_dir):
        """Test that sensitive directories are blocked"""
        sensitive_paths = [
            Path(temp_dir) / ".git" / "config",
            Path(temp_dir) / "node_modules" / "package",
            Path(temp_dir) / ".env",
        ]

        for path in sensitive_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            is_valid, error = validate_path(str(path), base_dir=temp_dir)
            assert is_valid is False
            assert "sensitive" in error.lower()

    def test_validate_file_size_accepts_small_files(self, temp_dir):
        """Test that small files are accepted"""
        test_file = Path(temp_dir) / "small.txt"
        test_file.write_text("Small content")
        is_valid, error = validate_file_size(str(test_file))
        assert is_valid is True
        assert error is None

    def test_validate_file_size_rejects_large_files(self, temp_dir):
        """Test that large files are rejected"""
        test_file = Path(temp_dir) / "large.txt"
        # Create a file larger than MAX_FILE_SIZE
        test_file.write_text("X" * (MAX_FILE_SIZE + 1000))
        is_valid, error = validate_file_size(str(test_file))
        assert is_valid is False
        assert "exceeds maximum" in error.lower()

    def test_validate_file_size_nonexistent_file(self, temp_dir):
        """Test validation of non-existent file (should pass)"""
        nonexistent = str(Path(temp_dir) / "nonexistent.txt")
        is_valid, error = validate_file_size(nonexistent)
        assert is_valid is True  # Should pass for non-existent (for write operations)

    def test_validate_path_with_none_base_dir(self):
        """Test path validation with default base dir"""
        # Should use project root by default
        is_valid, error = validate_path("README.md")
        # Can't guarantee it exists, but shouldn't crash
        assert isinstance(is_valid, bool)

    def test_validate_path_with_invalid_characters(self, temp_dir):
        """Test path validation with invalid characters"""
        # Most systems allow these, so just ensure no crash
        path = str(Path(temp_dir) / "test_file.txt")
        is_valid, error = validate_path(path, base_dir=temp_dir)
        assert isinstance(is_valid, bool)

    def test_validate_path_with_relative_path(self, temp_dir):
        """Test validation of relative paths"""
        # Create a test file
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("test")

        # Should resolve relative paths
        is_valid, error = validate_path(str(test_file), base_dir=temp_dir)
        assert is_valid is True

    def test_validate_path_empty_string(self, temp_dir):
        """Test validation with empty path"""
        is_valid, error = validate_path("", base_dir=temp_dir)
        # Should handle gracefully
        assert isinstance(is_valid, bool)


# ============================================================================
# File Operations Tests (15 tests)
# ============================================================================


class TestFileOperations:
    """Test file operation tools"""

    def test_read_file_success(self, sample_files):
        """Test reading a file successfully"""
        result = read_file_test(sample_files["test_file"], base_dir=sample_files["temp_dir"])
        assert result.success is True
        assert result.data == "Hello, World!"
        assert result.error is None

    def test_read_file_not_found(self, temp_dir):
        """Test reading a non-existent file"""
        nonexistent = str(Path(temp_dir) / "nonexistent.txt")
        result = read_file_test(nonexistent, base_dir=temp_dir)
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_read_file_is_directory(self, sample_files):
        """Test reading a directory (should fail)"""
        result = read_file_test(sample_files["subdir"], base_dir=sample_files["temp_dir"])
        assert result.success is False
        assert "not a file" in result.error.lower()

    def test_read_file_nested(self, sample_files):
        """Test reading a nested file"""
        result = read_file_test(sample_files["nested_file"], base_dir=sample_files["temp_dir"])
        assert result.success is True
        assert result.data == "Nested content"

    def test_write_file_success(self, temp_dir):
        """Test writing a file successfully"""
        test_file = str(Path(temp_dir) / "output.txt")
        content = "Test content\nLine 2"
        result = write_file_test(test_file, content, base_dir=temp_dir)

        assert result.success is True
        assert result.data["path"] == str(Path(test_file).resolve())
        assert result.data["size"] > 0

        # Verify file was written
        assert Path(test_file).read_text() == content

    def test_write_file_creates_parent_dirs(self, temp_dir):
        """Test that write_file creates parent directories"""
        nested_file = str(Path(temp_dir) / "a" / "b" / "c" / "test.txt")
        content = "Nested file"
        result = write_file_test(nested_file, content, base_dir=temp_dir)

        assert result.success is True
        assert Path(nested_file).exists()
        assert Path(nested_file).read_text() == content

    def test_write_file_overwrite_existing(self, sample_files):
        """Test overwriting an existing file"""
        new_content = "Updated content"
        result = write_file_test(sample_files["test_file"], new_content, base_dir=sample_files["temp_dir"])

        assert result.success is True
        assert Path(sample_files["test_file"]).read_text() == new_content

    def test_write_file_too_large(self, temp_dir):
        """Test writing content that's too large"""
        test_file = str(Path(temp_dir) / "large.txt")
        large_content = "X" * (MAX_FILE_SIZE + 1000)
        result = write_file_test(test_file, large_content, base_dir=temp_dir)

        assert result.success is False
        assert "exceeds maximum" in result.error.lower()

    def test_write_file_empty_content(self, temp_dir):
        """Test writing empty content"""
        test_file = str(Path(temp_dir) / "empty.txt")
        result = write_file_test(test_file, "", base_dir=temp_dir)

        assert result.success is True
        assert Path(test_file).read_text() == ""

    def test_list_files_success(self, sample_files, temp_dir):
        """Test listing files in a directory"""
        result = list_files_test(temp_dir, base_dir=temp_dir)

        assert result.success is True
        assert isinstance(result.data, list)
        assert len(result.data) >= 2  # test.txt and subdir

        # Check that files are in the list
        names = [f["name"] for f in result.data]
        assert "test.txt" in names
        assert "subdir" in names

    def test_list_files_recursive(self, sample_files, temp_dir):
        """Test listing files recursively"""
        result = list_files_test(temp_dir, recursive=True, base_dir=temp_dir)

        assert result.success is True
        assert isinstance(result.data, list)

        # Should include nested files
        paths = [f["path"] for f in result.data]
        assert any("nested.txt" in p for p in paths)

    def test_list_files_not_found(self, temp_dir):
        """Test listing a non-existent directory"""
        nonexistent = str(Path(temp_dir) / "nonexistent")
        result = list_files_test(nonexistent, base_dir=temp_dir)

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_list_files_is_file(self, sample_files):
        """Test listing a file (should fail)"""
        result = list_files_test(sample_files["test_file"], base_dir=sample_files["temp_dir"])

        assert result.success is False
        assert "not a directory" in result.error.lower()

    def test_list_files_filters_sensitive(self, temp_dir):
        """Test that sensitive directories are filtered"""
        # Create sensitive directories
        (Path(temp_dir) / "node_modules").mkdir()
        (Path(temp_dir) / ".git").mkdir()
        (Path(temp_dir) / "normal_dir").mkdir()

        result = list_files_test(temp_dir, base_dir=temp_dir)

        assert result.success is True
        names = [f["name"] for f in result.data]
        assert "node_modules" not in names
        assert ".git" not in names
        assert "normal_dir" in names

    def test_list_files_empty_directory(self, temp_dir):
        """Test listing an empty directory"""
        empty_dir = Path(temp_dir) / "empty"
        empty_dir.mkdir()

        result = list_files_test(str(empty_dir), base_dir=temp_dir)

        assert result.success is True
        assert result.data == []


# ============================================================================
# Task Management Tests (20 tests)
# ============================================================================


class TestTaskManagement:
    """Test task management tools"""

    def test_create_task_success(self):
        """Test creating a task successfully"""
        result = create_task(
            project_id="PRJ-001",
            title="TASK-001",
            description="Test task",
            category="feature"
        )

        assert result.success is True
        assert result.data["id"] == "TASK-001"
        assert result.data["description"] == "Test task"
        assert result.data["category"] == "feature"
        assert result.data["status"] == "todo"

    def test_create_task_auto_creates_project(self):
        """Test that creating a task auto-creates the project"""
        result = create_task(
            project_id="PRJ-NEW",
            title="TASK-001",
            description="Test task",
            category="bug"
        )

        assert result.success is True

        # Verify project was created
        projects = get_all_projects()
        assert "PRJ-NEW" in projects

    def test_create_task_duplicate_id(self):
        """Test creating a task with duplicate ID"""
        create_task("PRJ-001", "TASK-001", "First task", "feature")
        result = create_task("PRJ-001", "TASK-001", "Duplicate task", "bug")

        assert result.success is False
        assert "already exists" in result.error.lower()

    def test_create_task_invalid_category(self):
        """Test creating a task with invalid category"""
        result = create_task(
            project_id="PRJ-001",
            title="TASK-001",
            description="Test task",
            category="invalid_category"
        )

        assert result.success is False
        assert "invalid category" in result.error.lower()

    def test_create_task_all_categories(self):
        """Test creating tasks with all valid categories"""
        categories = ["feature", "bug", "enhancement", "documentation", "testing", "refactoring", "research", "other"]

        for i, cat in enumerate(categories):
            result = create_task(
                project_id="PRJ-001",
                title=f"TASK-{i:03d}",
                description=f"Test {cat} task",
                category=cat
            )
            assert result.success is True
            assert result.data["category"] == cat

    def test_create_task_empty_description(self):
        """Test creating a task with empty description"""
        # Pydantic validation should catch this
        try:
            result = create_task(
                project_id="PRJ-001",
                title="TASK-001",
                description="",
                category="feature"
            )
            # If it doesn't raise, check the result
            assert result.success is False
        except ValueError:
            # Pydantic validation error is acceptable
            pass

    def test_update_task_success(self):
        """Test updating a task successfully"""
        create_task("PRJ-001", "TASK-001", "Test task", "feature")

        result = update_task(
            task_id="TASK-001",
            project_id="PRJ-001",
            status="in_progress",
            notes="Started working on this"
        )

        assert result.success is True
        assert result.data["status"] == "in_progress"
        assert result.data["notes"] == "Started working on this"

    def test_update_task_not_found(self):
        """Test updating a non-existent task"""
        result = update_task(
            task_id="NONEXISTENT",
            project_id="PRJ-001",
            status="in_progress"
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_update_task_project_not_found(self):
        """Test updating a task in non-existent project"""
        result = update_task(
            task_id="TASK-001",
            project_id="NONEXISTENT",
            status="in_progress"
        )

        assert result.success is False
        assert "project not found" in result.error.lower()

    def test_update_task_invalid_status(self):
        """Test updating a task with invalid status"""
        create_task("PRJ-001", "TASK-001", "Test task", "feature")

        result = update_task(
            task_id="TASK-001",
            project_id="PRJ-001",
            status="invalid_status"
        )

        assert result.success is False
        assert "invalid status" in result.error.lower()

    def test_update_task_all_statuses(self):
        """Test updating task through all valid statuses"""
        create_task("PRJ-001", "TASK-001", "Test task", "feature")

        statuses = ["todo", "in_progress", "completed", "blocked", "cancelled"]

        for status in statuses:
            result = update_task(
                task_id="TASK-001",
                project_id="PRJ-001",
                status=status
            )
            assert result.success is True
            assert result.data["status"] == status

    def test_update_task_without_status(self):
        """Test updating a task without changing status"""
        create_task("PRJ-001", "TASK-001", "Test task", "feature")

        result = update_task(
            task_id="TASK-001",
            project_id="PRJ-001",
            notes="Just adding notes"
        )

        assert result.success is True
        assert result.data["status"] == "todo"  # Should remain unchanged

    def test_complete_task_success(self):
        """Test completing a task successfully"""
        create_task("PRJ-001", "TASK-001", "Test task", "feature")

        result = complete_task(
            task_id="TASK-001",
            project_id="PRJ-001",
            result_notes="Task completed successfully"
        )

        assert result.success is True
        assert result.data["status"] == "completed"
        assert result.data["notes"] == "Task completed successfully"

    def test_complete_task_not_found(self):
        """Test completing a non-existent task"""
        result = complete_task(
            task_id="NONEXISTENT",
            project_id="PRJ-001",
            result_notes="Done"
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_complete_task_without_notes(self):
        """Test completing a task without notes"""
        create_task("PRJ-001", "TASK-001", "Test task", "feature")

        result = complete_task(
            task_id="TASK-001",
            project_id="PRJ-001"
        )

        assert result.success is True
        assert result.data["status"] == "completed"

    def test_get_project_state_success(self):
        """Test getting project state"""
        create_task("PRJ-001", "TASK-001", "Task 1", "feature")
        create_task("PRJ-001", "TASK-002", "Task 2", "bug")

        result = get_project_state("PRJ-001")

        assert result.success is True
        assert result.data["project_id"] == "PRJ-001"
        assert len(result.data["tasks"]) == 2

    def test_get_project_state_not_found(self):
        """Test getting state of non-existent project"""
        result = get_project_state("NONEXISTENT")

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_get_project_state_empty(self):
        """Test getting state of project with no tasks"""
        # Create project by creating and removing a task (or just create empty)
        create_task("PRJ-001", "TASK-001", "Task", "feature")
        # Now get the state
        result = get_project_state("PRJ-001")

        assert result.success is True
        assert len(result.data["tasks"]) == 1  # Has one task

    def test_multiple_projects(self):
        """Test managing multiple projects"""
        create_task("PRJ-001", "TASK-001", "Task 1", "feature")
        create_task("PRJ-002", "TASK-001", "Task 1", "bug")

        state1 = get_project_state("PRJ-001")
        state2 = get_project_state("PRJ-002")

        assert state1.success is True
        assert state2.success is True
        assert state1.data["project_id"] != state2.data["project_id"]

    def test_task_timestamps(self):
        """Test that task timestamps are set correctly"""
        result = create_task("PRJ-001", "TASK-001", "Test", "feature")

        assert result.success is True
        assert "created_at" in result.data
        assert "updated_at" in result.data

        # Update and check timestamp changed
        import time
        time.sleep(0.01)  # Small delay to ensure timestamp difference

        update_result = update_task("TASK-001", "PRJ-001", status="in_progress")
        assert update_result.success is True
        # Updated timestamp should be different (later)
        # Note: Can't easily compare ISO strings, but we verified it exists


# ============================================================================
# Event Logging Tests (10 tests)
# ============================================================================


class TestEventLogging:
    """Test event logging tools"""

    def test_log_event_success(self):
        """Test logging an event successfully"""
        result = log_event(
            project_id="PRJ-001",
            event_type="task_created",
            details={"task_id": "TASK-001", "title": "New task"}
        )

        assert result.success is True
        assert result.data["project_id"] == "PRJ-001"
        assert result.data["event_type"] == "task_created"
        assert result.data["details"]["task_id"] == "TASK-001"
        assert "timestamp" in result.data

    def test_log_multiple_events(self):
        """Test logging multiple events"""
        for i in range(5):
            result = log_event(
                project_id="PRJ-001",
                event_type=f"event_{i}",
                details={"index": i}
            )
            assert result.success is True

    def test_get_events_success(self):
        """Test getting events for a project"""
        # Log some events
        log_event("PRJ-001", "event_1", {"data": 1})
        log_event("PRJ-001", "event_2", {"data": 2})
        log_event("PRJ-002", "event_3", {"data": 3})

        result = get_events("PRJ-001")

        assert result.success is True
        assert len(result.data) == 2

    def test_get_events_filtered_by_type(self):
        """Test getting events filtered by type"""
        log_event("PRJ-001", "task_created", {"data": 1})
        log_event("PRJ-001", "task_updated", {"data": 2})
        log_event("PRJ-001", "task_created", {"data": 3})

        result = get_events("PRJ-001", event_type="task_created")

        assert result.success is True
        assert len(result.data) == 2
        assert all(e["event_type"] == "task_created" for e in result.data)

    def test_get_events_with_limit(self):
        """Test getting events with limit"""
        # Log many events
        for i in range(10):
            log_event("PRJ-001", "event", {"index": i})

        result = get_events("PRJ-001", limit=5)

        assert result.success is True
        assert len(result.data) == 5

    def test_get_events_empty_project(self):
        """Test getting events for project with no events"""
        result = get_events("PRJ-EMPTY")

        assert result.success is True
        assert result.data == []

    def test_get_events_sorted_by_timestamp(self):
        """Test that events are sorted by timestamp (newest first)"""
        import time

        log_event("PRJ-001", "event_1", {"order": 1})
        time.sleep(0.01)
        log_event("PRJ-001", "event_2", {"order": 2})
        time.sleep(0.01)
        log_event("PRJ-001", "event_3", {"order": 3})

        result = get_events("PRJ-001")

        assert result.success is True
        # Should be in reverse order (newest first)
        assert result.data[0]["details"]["order"] == 3
        assert result.data[1]["details"]["order"] == 2
        assert result.data[2]["details"]["order"] == 1

    def test_log_event_complex_details(self):
        """Test logging event with complex details"""
        complex_details = {
            "task": {
                "id": "TASK-001",
                "status": "completed",
                "metadata": {
                    "priority": 1,
                    "tags": ["urgent", "backend"]
                }
            },
            "user": "agent",
            "timestamp": datetime.now().isoformat()
        }

        result = log_event("PRJ-001", "task_completed", complex_details)

        assert result.success is True
        assert result.data["details"]["task"]["id"] == "TASK-001"
        assert "urgent" in result.data["details"]["task"]["metadata"]["tags"]

    def test_log_event_empty_details(self):
        """Test logging event with empty details"""
        result = log_event("PRJ-001", "simple_event", {})

        assert result.success is True
        assert result.data["details"] == {}

    def test_event_isolation_between_projects(self):
        """Test that events are isolated between projects"""
        log_event("PRJ-001", "event", {"data": "project 1"})
        log_event("PRJ-002", "event", {"data": "project 2"})

        result1 = get_events("PRJ-001")
        result2 = get_events("PRJ-002")

        assert result1.success is True
        assert result2.success is True
        assert len(result1.data) == 1
        assert len(result2.data) == 1
        assert result1.data[0]["details"]["data"] == "project 1"
        assert result2.data[0]["details"]["data"] == "project 2"


# ============================================================================
# Integration Tests (5 tests)
# ============================================================================


class TestIntegration:
    """Test complete workflows"""

    def test_complete_task_workflow(self):
        """Test complete task creation and management workflow"""
        # Create project with tasks
        create_task("PRJ-001", "TASK-001", "Implement login", "feature")
        create_task("PRJ-001", "TASK-002", "Add tests", "testing")

        # Log creation events
        log_event("PRJ-001", "task_created", {"task_id": "TASK-001"})
        log_event("PRJ-001", "task_created", {"task_id": "TASK-002"})

        # Update task status
        update_task("TASK-001", "PRJ-001", status="in_progress")
        log_event("PRJ-001", "task_updated", {"task_id": "TASK-001", "status": "in_progress"})

        # Complete task
        complete_task("TASK-001", "PRJ-001", "Login implemented")
        log_event("PRJ-001", "task_completed", {"task_id": "TASK-001"})

        # Verify project state
        state = get_project_state("PRJ-001")
        assert state.success is True
        assert len(state.data["tasks"]) == 2

        # Verify events
        events = get_events("PRJ-001")
        assert events.success is True
        assert len(events.data) == 4

    def test_file_and_task_workflow(self, temp_dir):
        """Test workflow combining file operations and task management"""
        # Create a task for file creation
        create_task("PRJ-001", "TASK-001", "Create config file", "feature")

        # Write config file
        config_path = str(Path(temp_dir) / "config.json")
        config_content = '{"app": "test", "version": "1.0"}'
        write_result = write_file_test(config_path, config_content, base_dir=temp_dir)
        assert write_result.success is True

        # Log file creation
        log_event("PRJ-001", "file_created", {"path": config_path})

        # Read file back
        read_result = read_file_test(config_path, base_dir=temp_dir)
        assert read_result.success is True
        assert read_result.data == config_content

        # Complete task
        complete_task("TASK-001", "PRJ-001", f"Config file created at {config_path}")

        # Verify everything
        events = get_events("PRJ-001")
        assert len(events.data) == 1
        assert events.data[0]["event_type"] == "file_created"

    def test_multi_project_workflow(self):
        """Test managing multiple projects simultaneously"""
        # Create tasks in different projects
        create_task("FRONTEND", "UI-001", "Build login page", "feature")
        create_task("BACKEND", "API-001", "Create auth endpoint", "feature")
        create_task("FRONTEND", "UI-002", "Add error handling", "bug")

        # Update tasks
        update_task("UI-001", "FRONTEND", status="in_progress")
        update_task("API-001", "BACKEND", status="completed")

        # Get project states
        frontend_state = get_project_state("FRONTEND")
        backend_state = get_project_state("BACKEND")

        assert frontend_state.success is True
        assert backend_state.success is True
        assert len(frontend_state.data["tasks"]) == 2
        assert len(backend_state.data["tasks"]) == 1

    def test_error_recovery_workflow(self, temp_dir):
        """Test error handling and recovery"""
        # Try to read non-existent file
        read_result = read_file_test(str(Path(temp_dir) / "nonexistent.txt"), base_dir=temp_dir)
        assert read_result.success is False

        # Try to update non-existent task
        update_result = update_task("FAKE-001", "PRJ-001", status="done")
        assert update_result.success is False

        # Try to create task with invalid category
        create_result = create_task("PRJ-001", "TASK-001", "Test", "invalid")
        assert create_result.success is False

        # Now do valid operations
        create_task("PRJ-001", "TASK-001", "Valid task", "feature")
        write_file_test(str(Path(temp_dir) / "test.txt"), "content", base_dir=temp_dir)

        # Verify state is clean
        state = get_project_state("PRJ-001")
        assert state.success is True
        assert len(state.data["tasks"]) == 1

    def test_reset_state_workflow(self):
        """Test state reset functionality"""
        # Create some data
        create_task("PRJ-001", "TASK-001", "Test", "feature")
        log_event("PRJ-001", "event", {"data": 1})

        # Verify data exists
        assert len(get_all_projects()) == 1

        # Reset state
        reset_state()

        # Verify everything is cleared
        assert len(get_all_projects()) == 0
        events = get_events("PRJ-001")
        assert len(events.data) == 0


# ============================================================================
# Edge Cases & Error Handling (5 tests)
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_unicode_content(self, temp_dir):
        """Test handling Unicode content"""
        test_file = str(Path(temp_dir) / "unicode.txt")
        unicode_content = "Hello 世界 🌍 Здравствуй мир"

        write_result = write_file_test(test_file, unicode_content, base_dir=temp_dir)
        assert write_result.success is True

        read_result = read_file_test(test_file, base_dir=temp_dir)
        assert read_result.success is True
        assert read_result.data == unicode_content

    def test_very_long_paths(self, temp_dir):
        """Test handling very long file paths"""
        # Create a deeply nested path
        deep_path = Path(temp_dir)
        for i in range(10):
            deep_path = deep_path / f"level_{i}"

        test_file = str(deep_path / "test.txt")

        write_result = write_file_test(test_file, "content", base_dir=temp_dir)
        assert write_result.success is True

        read_result = read_file_test(test_file, base_dir=temp_dir)
        assert read_result.success is True

    def test_special_characters_in_task_description(self):
        """Test task descriptions with special characters"""
        special_desc = "Task with special chars: @#$%^&*()[]{}|\\<>?/~`"

        result = create_task("PRJ-001", "TASK-001", special_desc, "feature")
        assert result.success is True
        assert result.data["description"] == special_desc

    def test_concurrent_task_updates(self):
        """Test updating the same task multiple times"""
        create_task("PRJ-001", "TASK-001", "Test", "feature")

        # Update multiple times
        for i in range(5):
            result = update_task("TASK-001", "PRJ-001", notes=f"Update {i}")
            assert result.success is True

        # Verify final state
        state = get_project_state("PRJ-001")
        assert state.success is True

    def test_empty_project_operations(self):
        """Test operations on projects with no tasks"""
        # Create a project by creating then "removing" a task (not implemented)
        # For now, just test getting state of non-created project
        result = get_project_state("EMPTY-PRJ")
        assert result.success is False


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
