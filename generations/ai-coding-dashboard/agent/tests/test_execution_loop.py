"""
Tests for Execution Loop Module

Tests cover:
- TaskQueue sequencing and prioritization
- ExecutionEngine main loop
- State snapshot emissions
- Approval workflow
- Error recovery with exponential backoff
- Task dependencies
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from models import (
    AgentState,
    Task,
    TaskStatus,
    AgentStatus,
    TaskCategory,
    StateSnapshot,
)
from execution_loop import TaskQueue, ExecutionEngine
from events import EventEmitter


class TestTaskQueue:
    """Test TaskQueue class"""

    def test_initialization(self):
        """Test task queue initialization"""
        tasks = [
            Task(id="T1", description="Task 1", priority=2),
            Task(id="T2", description="Task 2", priority=1),
            Task(id="T3", description="Task 3", priority=3),
        ]

        queue = TaskQueue(tasks)

        # Should be sorted by priority
        assert queue.tasks[0].id == "T2"  # Priority 1
        assert queue.tasks[1].id == "T1"  # Priority 2
        assert queue.tasks[2].id == "T3"  # Priority 3

    def test_get_pending_tasks(self):
        """Test getting pending tasks"""
        tasks = [
            Task(id="T1", description="Task 1", status=TaskStatus.TODO),
            Task(id="T2", description="Task 2", status=TaskStatus.COMPLETED),
            Task(id="T3", description="Task 3", status=TaskStatus.BLOCKED),
            Task(id="T4", description="Task 4", status=TaskStatus.IN_PROGRESS),
        ]

        queue = TaskQueue(tasks)
        pending = queue.get_pending_tasks()

        assert len(pending) == 2
        assert any(t.id == "T1" for t in pending)
        assert any(t.id == "T3" for t in pending)

    def test_get_next_task(self):
        """Test getting next task to execute"""
        tasks = [
            Task(id="T1", description="Task 1", priority=2, status=TaskStatus.TODO),
            Task(id="T2", description="Task 2", priority=1, status=TaskStatus.TODO),
            Task(id="T3", description="Task 3", priority=3, status=TaskStatus.COMPLETED),
        ]

        queue = TaskQueue(tasks)
        next_task = queue.get_next_task()

        # Should get highest priority pending task
        assert next_task is not None
        assert next_task.id == "T2"  # Priority 1

    def test_get_next_task_empty(self):
        """Test getting next task when all completed"""
        tasks = [
            Task(id="T1", description="Task 1", status=TaskStatus.COMPLETED),
            Task(id="T2", description="Task 2", status=TaskStatus.COMPLETED),
        ]

        queue = TaskQueue(tasks)
        next_task = queue.get_next_task()

        assert next_task is None

    def test_update_priority(self):
        """Test updating task priority"""
        tasks = [
            Task(id="T1", description="Task 1", priority=2),
            Task(id="T2", description="Task 2", priority=1),
        ]

        queue = TaskQueue(tasks)
        assert queue.tasks[0].id == "T2"  # Priority 1

        # Update T1 to priority 1 (same as T2)
        result = queue.update_priority("T1", 1)

        assert result is True
        # Tasks should still be sorted
        assert queue.tasks[0].priority == 1
        assert queue.tasks[1].priority == 1

    def test_update_priority_not_found(self):
        """Test updating priority for non-existent task"""
        tasks = [Task(id="T1", description="Task 1", priority=2)]

        queue = TaskQueue(tasks)
        result = queue.update_priority("T999", 1)

        assert result is False

    def test_add_task(self):
        """Test adding a new task"""
        tasks = [Task(id="T1", description="Task 1", priority=2)]

        queue = TaskQueue(tasks)
        new_task = Task(id="T2", description="Task 2", priority=1)
        queue.add_task(new_task)

        assert len(queue.tasks) == 2
        assert queue.tasks[0].id == "T2"  # Should be first (priority 1)

    def test_remove_task(self):
        """Test removing a task"""
        tasks = [
            Task(id="T1", description="Task 1", priority=1),
            Task(id="T2", description="Task 2", priority=2),
        ]

        queue = TaskQueue(tasks)
        result = queue.remove_task("T1")

        assert result is True
        assert len(queue.tasks) == 1
        assert queue.tasks[0].id == "T2"

    def test_remove_task_not_found(self):
        """Test removing non-existent task"""
        tasks = [Task(id="T1", description="Task 1", priority=1)]

        queue = TaskQueue(tasks)
        result = queue.remove_task("T999")

        assert result is False
        assert len(queue.tasks) == 1

    def test_get_task_by_id(self):
        """Test getting task by ID"""
        tasks = [
            Task(id="T1", description="Task 1", priority=1),
            Task(id="T2", description="Task 2", priority=2),
        ]

        queue = TaskQueue(tasks)
        task = queue.get_task_by_id("T2")

        assert task is not None
        assert task.id == "T2"
        assert task.description == "Task 2"

    def test_get_task_by_id_not_found(self):
        """Test getting non-existent task"""
        tasks = [Task(id="T1", description="Task 1", priority=1)]

        queue = TaskQueue(tasks)
        task = queue.get_task_by_id("T999")

        assert task is None


class TestExecutionEngine:
    """Test ExecutionEngine class"""

    @pytest.fixture
    def agent_state(self):
        """Create test agent state"""
        tasks = [
            Task(id="T1", description="Task 1", priority=1, status=TaskStatus.TODO),
            Task(id="T2", description="Task 2", priority=2, status=TaskStatus.TODO),
        ]
        return AgentState(
            project_id="1",
            tasks=tasks,
            status=AgentStatus.IDLE,
        )

    @pytest.fixture
    def event_emitter(self):
        """Create test event emitter"""
        return EventEmitter()

    @pytest.fixture
    def engine(self, agent_state, event_emitter):
        """Create test execution engine"""
        return ExecutionEngine(
            state=agent_state,
            api_base_url="http://localhost:3010",
            max_retries=2,
            retry_delay=0.1,  # Fast retry for tests
            event_emitter=event_emitter,
        )

    def test_initialization(self, engine, agent_state):
        """Test execution engine initialization"""
        assert engine.state == agent_state
        assert engine.api_base_url == "http://localhost:3010"
        assert engine.max_retries == 2
        assert engine.retry_delay == 0.1
        assert len(engine.task_queue.tasks) == 2
        assert not engine.is_running
        assert not engine.is_paused

    def test_log_activity(self, engine):
        """Test activity logging"""
        engine._log_activity("test_type", "Test message")

        assert len(engine.activities) == 1
        assert engine.activities[0].activity_type == "test_type"
        assert engine.activities[0].message == "Test message"

    def test_log_activity_max_50(self, engine):
        """Test activity log max size"""
        # Add 60 activities
        for i in range(60):
            engine._log_activity("test", f"Message {i}")

        # Should keep only last 50
        assert len(engine.activities) == 50
        assert engine.activities[-1].message == "Message 59"

    @pytest.mark.asyncio
    async def test_emit_state_snapshot_success(self, engine):
        """Test state snapshot emission"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            mock_client_class.return_value = mock_client

            await engine._emit_state_snapshot()

            # Verify API was called
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "/api/dashboard/event" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_emit_state_snapshot_failure(self, engine):
        """Test state snapshot emission handles errors gracefully"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("API error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            mock_client_class.return_value = mock_client

            # Should not raise exception
            await engine._emit_state_snapshot()

    @pytest.mark.asyncio
    async def test_request_approval_timeout(self, engine):
        """Test approval request timeout"""
        with patch("httpx.AsyncClient") as mock_client_class:
            # Mock POST (emit event) success
            mock_post_response = AsyncMock()
            mock_post_response.raise_for_status = Mock()

            # Mock GET (poll for response) - always return pending
            mock_get_response = AsyncMock()
            mock_get_response.raise_for_status = Mock()
            mock_get_response.json = Mock(return_value={
                "success": True,
                "pending_responses": [
                    {"id": "some-id", "response_type": "approval"}
                ],
            })

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_post_response)
            mock_client.get = AsyncMock(return_value=mock_get_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            mock_client_class.return_value = mock_client

            # Should timeout quickly
            with pytest.raises(TimeoutError):
                await engine._request_approval(
                    action="Test action",
                    description="Test description",
                    timeout_seconds=1,
                )

    @pytest.mark.asyncio
    async def test_request_approval_approved(self, engine):
        """Test approval request approved"""
        with patch("httpx.AsyncClient") as mock_client_class:
            # Mock POST success
            mock_post_response = AsyncMock()
            mock_post_response.raise_for_status = Mock()

            # Mock GET - return empty pending (approved)
            mock_get_response = AsyncMock()
            mock_get_response.raise_for_status = Mock()
            mock_get_response.json = Mock(return_value={
                "success": True,
                "pending_responses": [],  # Empty = approved
            })

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_post_response)
            mock_client.get = AsyncMock(return_value=mock_get_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            mock_client_class.return_value = mock_client

            result = await engine._request_approval(
                action="Test action",
                description="Test description",
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_execute_single_task(self, engine):
        """Test single task execution"""
        task = Task(id="T1", description="Test task", status=TaskStatus.TODO)

        with patch("execution_loop.ExecutionEngine._emit_state_snapshot") as mock_emit:
            await engine._execute_single_task(task)

            # Task should be completed
            assert task.status == TaskStatus.COMPLETED
            # State snapshot should be emitted
            assert mock_emit.call_count >= 1

    @pytest.mark.asyncio
    async def test_execute_task_with_retry_success(self, engine):
        """Test task execution with retry - succeeds on first attempt"""
        task = Task(id="T1", description="Test task", status=TaskStatus.TODO)

        with patch("execution_loop.ExecutionEngine._execute_single_task") as mock_execute:
            mock_execute.return_value = None  # Success

            await engine._execute_task_with_retry(task)

            # Should only call once (success)
            assert mock_execute.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_task_with_retry_eventual_success(self, engine):
        """Test task execution with retry - succeeds after retries"""
        task = Task(id="T1", description="Test task", status=TaskStatus.TODO)

        call_count = 0

        async def mock_execute(t):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            # Success on 2nd attempt

        with patch("execution_loop.ExecutionEngine._execute_single_task", side_effect=mock_execute):
            await engine._execute_task_with_retry(task)

            # Should call twice (fail once, then succeed)
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_task_with_retry_all_fail(self, engine):
        """Test task execution with retry - all attempts fail"""
        task = Task(id="T1", description="Test task", status=TaskStatus.TODO)

        with patch("execution_loop.ExecutionEngine._execute_single_task") as mock_execute:
            mock_execute.side_effect = Exception("Permanent failure")

            with pytest.raises(Exception) as exc_info:
                await engine._execute_task_with_retry(task)

            assert "failed after 2 retries" in str(exc_info.value)
            # Should call max_retries times
            assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    async def test_run_success(self, engine):
        """Test successful execution run"""
        with patch("execution_loop.ExecutionEngine._execute_single_task") as mock_execute, \
             patch("execution_loop.ExecutionEngine._emit_state_snapshot") as mock_emit:

            mock_execute.return_value = None  # Success

            await engine.run()

            # Should execute both tasks
            assert mock_execute.call_count == 2
            # Should emit snapshots
            assert mock_emit.call_count >= 3  # Initial + per task + final
            # State should be completed
            assert engine.state.status == AgentStatus.COMPLETED
            assert engine.state.progress == 100.0

    @pytest.mark.asyncio
    async def test_run_already_running(self, engine):
        """Test running when already running"""
        engine._running = True

        with pytest.raises(RuntimeError) as exc_info:
            await engine.run()

        assert "already running" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_with_error(self, engine):
        """Test execution run with error"""
        with patch("execution_loop.ExecutionEngine._execute_single_task") as mock_execute, \
             patch("execution_loop.ExecutionEngine._emit_state_snapshot") as mock_emit:

            # First task succeeds, second fails
            call_count = 0

            async def mock_execute_func(t):
                nonlocal call_count
                call_count += 1
                if call_count > 1:
                    raise Exception("Task failed")

            mock_execute.side_effect = mock_execute_func

            # Mock retry to fail immediately
            with patch("execution_loop.ExecutionEngine._execute_task_with_retry") as mock_retry:
                async def mock_retry_func(t):
                    nonlocal call_count
                    call_count += 1
                    if call_count > 2:
                        raise Exception("Task failed")

                mock_retry.side_effect = mock_retry_func

                with pytest.raises(Exception):
                    await engine.run()

                # State should be error
                assert engine.state.status == AgentStatus.ERROR

    def test_pause_resume_stop(self, engine):
        """Test pause, resume, and stop operations"""
        # Pause
        engine.pause()
        assert engine.is_paused
        assert engine.state.status == AgentStatus.PAUSED

        # Resume
        engine.resume()
        assert not engine.is_paused
        assert engine.state.status == AgentStatus.RUNNING

        # Stop
        engine.stop()
        assert not engine.is_running
        assert engine.state.status == AgentStatus.IDLE


class TestStateSnapshot:
    """Test StateSnapshot model"""

    def test_from_agent_state(self):
        """Test creating snapshot from agent state"""
        tasks = [
            Task(id="T1", description="Task 1", status=TaskStatus.COMPLETED),
            Task(id="T2", description="Task 2", status=TaskStatus.IN_PROGRESS),
            Task(id="T3", description="Task 3", status=TaskStatus.TODO),
        ]

        state = AgentState(
            project_id="1",
            tasks=tasks,
            current_task_index=1,
            progress=33.3,
            status=AgentStatus.RUNNING,
        )

        snapshot = StateSnapshot.from_agent_state(state)

        assert snapshot.project_id == "1"
        assert snapshot.status == AgentStatus.RUNNING
        assert snapshot.progress_percentage == 33.3
        assert len(snapshot.completed_tasks) == 1
        assert len(snapshot.pending_tasks) == 2
        assert snapshot.current_task is not None
        assert snapshot.current_task.id == "T2"


class TestIntegration:
    """Integration tests for execution loop"""

    @pytest.mark.asyncio
    async def test_full_execution_flow(self):
        """Test complete execution flow"""
        # Create state with 3 tasks
        tasks = [
            Task(id="T1", description="Task 1", priority=1, status=TaskStatus.TODO),
            Task(id="T2", description="Task 2", priority=2, status=TaskStatus.TODO),
            Task(id="T3", description="Task 3", priority=3, status=TaskStatus.TODO),
        ]

        state = AgentState(
            project_id="1",
            tasks=tasks,
            status=AgentStatus.IDLE,
        )

        engine = ExecutionEngine(
            state=state,
            max_retries=2,
            retry_delay=0.1,
        )

        # Mock API calls
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()
            mock_response.json = Mock(return_value={"success": True, "pending_responses": []})

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            mock_client_class.return_value = mock_client

            # Run execution
            await engine.run()

            # All tasks should be completed
            assert all(t.status == TaskStatus.COMPLETED for t in state.tasks)
            assert state.status == AgentStatus.COMPLETED
            assert state.progress == 100.0

            # Should have logged activities
            assert len(engine.activities) > 0
