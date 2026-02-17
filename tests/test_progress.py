"""Unit tests for the progress tracking utilities in progress.py

Tests cover:
- .linear_project.json reading and writing via load_project_state
- is_project_initialized behavior
- Ticket locking mechanism: acquire, release, list locked
- Lock TTL expiration (stale locks auto-released)
- Verification status updates
- Concurrent lock acquisition attempts
- cleanup_stale_locks behavior
- should_run_verification logic
- increment_tickets_since_verification
"""

import json
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from progress import (
    LOCK_TTL,
    LOCKS_DIR_NAME,
    LINEAR_PROJECT_MARKER,
    VERIFICATION_INTERVAL,
    acquire_ticket_lock,
    cleanup_stale_locks,
    get_locked_tickets,
    increment_tickets_since_verification,
    is_project_initialized,
    load_project_state,
    print_progress_summary,
    print_session_header,
    release_ticket_lock,
    should_run_verification,
    update_verification_status,
)


class TestLoadProjectState:
    """Test suite for load_project_state function."""

    def setup_method(self):
        """Set up a temporary directory for each test."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up after each test."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_returns_none_when_no_marker_file(self):
        """Test that None is returned when .linear_project.json does not exist."""
        result = load_project_state(self.temp_dir)
        assert result is None

    def test_returns_state_when_marker_file_exists(self):
        """Test that state dict is returned when marker file exists."""
        state = {"initialized": True, "project_name": "test-project", "total_issues": 5}
        marker = self.temp_dir / LINEAR_PROJECT_MARKER
        marker.write_text(json.dumps(state))

        result = load_project_state(self.temp_dir)
        assert result is not None
        assert result["initialized"] is True
        assert result["project_name"] == "test-project"
        assert result["total_issues"] == 5

    def test_raises_value_error_on_corrupted_json(self):
        """Test that ValueError is raised for corrupted JSON in marker file."""
        marker = self.temp_dir / LINEAR_PROJECT_MARKER
        marker.write_text("this is not valid json {{{{")

        with pytest.raises(ValueError, match="Corrupted state file"):
            load_project_state(self.temp_dir)

    def test_raises_value_error_when_not_dict(self):
        """Test that ValueError is raised when file contains non-dict JSON."""
        marker = self.temp_dir / LINEAR_PROJECT_MARKER
        marker.write_text(json.dumps([1, 2, 3]))  # A list, not a dict

        with pytest.raises(ValueError, match="Invalid state file"):
            load_project_state(self.temp_dir)

    def test_loads_all_fields(self):
        """Test that all project state fields are correctly loaded."""
        state = {
            "initialized": True,
            "created_at": "2024-01-01T00:00:00",
            "team_id": "team-123",
            "team_key": "AI",
            "project_id": "proj-456",
            "project_name": "My Project",
            "project_slug": "my-project",
            "meta_issue_id": "meta-789",
            "total_issues": 42,
            "notes": "Test notes",
            "issues": [{"key": "AI-1", "title": "Feature 1"}],
        }
        marker = self.temp_dir / LINEAR_PROJECT_MARKER
        marker.write_text(json.dumps(state))

        result = load_project_state(self.temp_dir)
        assert result["team_id"] == "team-123"
        assert result["total_issues"] == 42
        assert len(result["issues"]) == 1


class TestIsProjectInitialized:
    """Test suite for is_project_initialized."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_returns_false_when_no_marker_file(self):
        """Test that False is returned when no marker file exists."""
        assert is_project_initialized(self.temp_dir) is False

    def test_returns_false_when_not_initialized(self):
        """Test that False is returned when initialized flag is False."""
        state = {"initialized": False}
        marker = self.temp_dir / LINEAR_PROJECT_MARKER
        marker.write_text(json.dumps(state))
        assert is_project_initialized(self.temp_dir) is False

    def test_returns_true_when_initialized(self):
        """Test that True is returned when initialized flag is True."""
        state = {"initialized": True}
        marker = self.temp_dir / LINEAR_PROJECT_MARKER
        marker.write_text(json.dumps(state))
        assert is_project_initialized(self.temp_dir) is True

    def test_returns_false_for_corrupted_file(self):
        """Test that False is returned for corrupted state file (graceful degradation)."""
        marker = self.temp_dir / LINEAR_PROJECT_MARKER
        marker.write_text("corrupted {{{")
        # Should return False with a warning rather than raising
        result = is_project_initialized(self.temp_dir)
        assert result is False


class TestPrintSessionHeader:
    """Test print_session_header does not raise errors."""

    def test_initializer_header(self, capsys):
        """Test that initializer session header is printed."""
        print_session_header(1, True)
        captured = capsys.readouterr()
        assert "SESSION 1" in captured.out
        assert "ORCHESTRATOR" in captured.out
        assert "init" in captured.out

    def test_continuation_header(self, capsys):
        """Test that continuation session header is printed."""
        print_session_header(5, False)
        captured = capsys.readouterr()
        assert "SESSION 5" in captured.out
        assert "continue" in captured.out


class TestPrintProgressSummary:
    """Test print_progress_summary output."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_no_state_message(self, capsys):
        """Test output when no state file exists."""
        print_progress_summary(self.temp_dir)
        captured = capsys.readouterr()
        assert "not yet initialized" in captured.out

    def test_with_state_shows_total(self, capsys):
        """Test that progress summary shows total issues."""
        state = {
            "initialized": True,
            "total_issues": 20,
            "meta_issue_id": "META-1",
        }
        marker = self.temp_dir / LINEAR_PROJECT_MARKER
        marker.write_text(json.dumps(state))

        print_progress_summary(self.temp_dir)
        captured = capsys.readouterr()
        assert "20" in captured.out


class TestTicketLocking:
    """Tests for ticket locking mechanism."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_acquire_new_lock(self):
        """Test acquiring a lock on a ticket that is not locked."""
        result = acquire_ticket_lock(self.temp_dir, "AI-42", "worker-1")
        assert result is True

    def test_second_worker_cannot_acquire_same_ticket(self):
        """Test that a second worker cannot acquire an already-locked ticket."""
        acquire_ticket_lock(self.temp_dir, "AI-10", "worker-1")
        result = acquire_ticket_lock(self.temp_dir, "AI-10", "worker-2")
        assert result is False

    def test_same_worker_cannot_acquire_twice(self):
        """Test that the same worker cannot double-acquire a ticket."""
        acquire_ticket_lock(self.temp_dir, "AI-11", "worker-1")
        result = acquire_ticket_lock(self.temp_dir, "AI-11", "worker-1")
        assert result is False

    def test_release_allows_reacquisition(self):
        """Test that releasing a lock allows another worker to acquire it."""
        acquire_ticket_lock(self.temp_dir, "AI-20", "worker-1")
        release_ticket_lock(self.temp_dir, "AI-20")
        result = acquire_ticket_lock(self.temp_dir, "AI-20", "worker-2")
        assert result is True

    def test_release_nonexistent_lock_does_not_raise(self):
        """Test that releasing a non-existent lock does not raise an error."""
        # Should not raise
        release_ticket_lock(self.temp_dir, "AI-999")

    def test_get_locked_tickets_empty_initially(self):
        """Test that no tickets are locked when starting fresh."""
        locked = get_locked_tickets(self.temp_dir)
        assert locked == []

    def test_get_locked_tickets_returns_acquired_tickets(self):
        """Test that get_locked_tickets returns currently locked tickets."""
        acquire_ticket_lock(self.temp_dir, "AI-30", "worker-1")
        acquire_ticket_lock(self.temp_dir, "AI-31", "worker-2")
        locked = get_locked_tickets(self.temp_dir)
        assert "AI-30" in locked
        assert "AI-31" in locked

    def test_released_ticket_not_in_locked_list(self):
        """Test that released tickets no longer appear in locked list."""
        acquire_ticket_lock(self.temp_dir, "AI-40", "worker-1")
        release_ticket_lock(self.temp_dir, "AI-40")
        locked = get_locked_tickets(self.temp_dir)
        assert "AI-40" not in locked

    def test_expired_lock_allows_new_acquisition(self):
        """Test that an expired lock (TTL elapsed) can be overwritten."""
        # Acquire with a very short TTL (1 second)
        acquire_ticket_lock(self.temp_dir, "AI-50", "worker-1", ttl=1)

        # Simulate lock expiry by patching time.time to return a future timestamp
        future_time = time.time() + 10  # 10 seconds in the future
        with patch("time.time", return_value=future_time):
            result = acquire_ticket_lock(self.temp_dir, "AI-50", "worker-2", ttl=LOCK_TTL)
        assert result is True

    def test_lock_creates_lock_file(self):
        """Test that acquiring a lock creates a .lock file."""
        acquire_ticket_lock(self.temp_dir, "AI-60", "worker-1")
        lock_file = self.temp_dir / LOCKS_DIR_NAME / "AI-60.lock"
        assert lock_file.exists()

    def test_lock_file_contains_correct_data(self):
        """Test that the lock file contains the correct worker and ticket info."""
        acquire_ticket_lock(self.temp_dir, "AI-70", "worker-123")
        lock_file = self.temp_dir / LOCKS_DIR_NAME / "AI-70.lock"
        data = json.loads(lock_file.read_text())
        assert data["ticket_key"] == "AI-70"
        assert data["worker_id"] == "worker-123"
        assert "acquired_at" in data
        assert "ttl" in data

    def test_corrupted_lock_file_allows_reacquisition(self):
        """Test that a corrupted lock file does not block new acquisition."""
        lock_dir = self.temp_dir / LOCKS_DIR_NAME
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_file = lock_dir / "AI-80.lock"
        lock_file.write_text("corrupted {{{ not json")

        result = acquire_ticket_lock(self.temp_dir, "AI-80", "worker-1")
        assert result is True


class TestCleanupStaleLocks:
    """Tests for cleanup_stale_locks function."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cleanup_returns_zero_when_no_locks(self):
        """Test that cleanup returns 0 when no lock files exist."""
        count = cleanup_stale_locks(self.temp_dir)
        assert count == 0

    def test_cleanup_does_not_remove_active_locks(self):
        """Test that active (non-expired) locks are preserved."""
        acquire_ticket_lock(self.temp_dir, "AI-100", "worker-1", ttl=LOCK_TTL)
        count = cleanup_stale_locks(self.temp_dir)
        assert count == 0
        # Lock file should still exist
        lock_file = self.temp_dir / LOCKS_DIR_NAME / "AI-100.lock"
        assert lock_file.exists()

    def test_cleanup_removes_expired_locks(self):
        """Test that expired locks are removed by cleanup."""
        acquire_ticket_lock(self.temp_dir, "AI-110", "worker-1", ttl=1)

        future_time = time.time() + 10
        with patch("time.time", return_value=future_time):
            count = cleanup_stale_locks(self.temp_dir)

        assert count == 1
        lock_file = self.temp_dir / LOCKS_DIR_NAME / "AI-110.lock"
        assert not lock_file.exists()

    def test_cleanup_removes_corrupted_locks(self):
        """Test that corrupted lock files are removed by cleanup."""
        lock_dir = self.temp_dir / LOCKS_DIR_NAME
        lock_dir.mkdir(parents=True, exist_ok=True)
        corrupted = lock_dir / "AI-120.lock"
        corrupted.write_text("{corrupted}")

        count = cleanup_stale_locks(self.temp_dir)
        assert count == 1
        assert not corrupted.exists()


class TestVerificationStatus:
    """Tests for verification status tracking."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        # Set up a minimal initialized state file
        state = {
            "initialized": True,
            "last_verification_status": "",
            "last_verification_ticket": "",
            "tickets_since_verification": 0,
        }
        marker = self.temp_dir / LINEAR_PROJECT_MARKER
        marker.write_text(json.dumps(state))

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_should_run_verification_with_no_state(self):
        """Test that verification runs when no state exists."""
        empty_dir = Path(tempfile.mkdtemp())
        try:
            result = should_run_verification(empty_dir)
            assert result is True
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)

    def test_should_run_when_last_status_unknown(self):
        """Test that verification runs when last status is empty."""
        result = should_run_verification(self.temp_dir)
        assert result is True

    def test_should_run_when_last_status_failed(self):
        """Test that verification runs when last verification failed."""
        update_verification_status(self.temp_dir, "fail", "AI-1")
        result = should_run_verification(self.temp_dir)
        assert result is True

    def test_no_run_when_just_passed(self):
        """Test that verification is skipped right after a passing run."""
        update_verification_status(self.temp_dir, "pass", "AI-2")
        result = should_run_verification(self.temp_dir)
        assert result is False

    def test_run_after_verification_interval(self):
        """Test that verification is triggered after VERIFICATION_INTERVAL tickets."""
        update_verification_status(self.temp_dir, "pass", "AI-3")

        # Increment tickets_since_verification up to the interval
        for _ in range(VERIFICATION_INTERVAL):
            increment_tickets_since_verification(self.temp_dir)

        result = should_run_verification(self.temp_dir)
        assert result is True

    def test_update_verification_status_pass_resets_counter(self):
        """Test that updating status to pass resets the ticket counter."""
        # Increment a few times
        increment_tickets_since_verification(self.temp_dir)
        increment_tickets_since_verification(self.temp_dir)

        update_verification_status(self.temp_dir, "pass", "AI-4")

        state = load_project_state(self.temp_dir)
        assert state["tickets_since_verification"] == 0

    def test_update_verification_status_records_ticket_key(self):
        """Test that the ticket key is recorded in the state."""
        update_verification_status(self.temp_dir, "pass", "AI-99")
        state = load_project_state(self.temp_dir)
        assert state["last_verification_ticket"] == "AI-99"

    def test_increment_tickets_since_verification(self):
        """Test that incrementing the counter works correctly."""
        increment_tickets_since_verification(self.temp_dir)
        state = load_project_state(self.temp_dir)
        assert state["tickets_since_verification"] == 1

        increment_tickets_since_verification(self.temp_dir)
        state = load_project_state(self.temp_dir)
        assert state["tickets_since_verification"] == 2

    def test_update_verification_noop_with_no_state(self):
        """Test that update_verification_status does nothing if no state file."""
        empty_dir = Path(tempfile.mkdtemp())
        try:
            # Should not raise
            update_verification_status(empty_dir, "pass", "AI-1")
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)

    def test_increment_noop_with_no_state(self):
        """Test that incrementing tickets does nothing if no state file."""
        empty_dir = Path(tempfile.mkdtemp())
        try:
            # Should not raise
            increment_tickets_since_verification(empty_dir)
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)
