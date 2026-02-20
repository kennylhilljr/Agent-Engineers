"""
Unit tests for ConcurrencyManager (AI-263).

Tests cover:
- Initialization
- Enable/disable acceleration
- Task submission and prioritization
- Metrics collection
- Status reporting
"""

import asyncio
import pytest
from agents.orchestrator import (
    ConcurrencyManager,
    TaskPriority,
    AccelerationMode,
    get_concurrency_manager
)


class TestConcurrencyManager:
    """Test suite for ConcurrencyManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh ConcurrencyManager for each test."""
        return ConcurrencyManager(max_concurrent_tasks=5, default_timeout=10.0)

    def test_initialization(self, manager):
        """Test ConcurrencyManager initializes with correct defaults."""
        assert manager.max_concurrent_tasks == 5
        assert manager.default_timeout == 10.0
        assert manager.enabled is False
        assert manager.acceleration_factor == 1.0
        assert manager.mode == AccelerationMode.DISABLED
        assert len(manager.task_queue) == 0
        assert len(manager.active_tasks) == 0
        assert len(manager.completed_tasks) == 0

    @pytest.mark.asyncio
    async def test_enable_acceleration(self, manager):
        """Test enabling acceleration with valid factor."""
        result = await manager.enable_acceleration(factor=2.0)

        assert result["status"] == "enabled"
        assert result["factor"] == 2.0
        assert manager.enabled is True
        assert manager.acceleration_factor == 2.0
        assert manager.mode == AccelerationMode.ENABLED

    @pytest.mark.asyncio
    async def test_enable_acceleration_invalid_factor(self, manager):
        """Test enabling acceleration with invalid factor raises error."""
        with pytest.raises(ValueError, match="between 1.0 and 10.0"):
            await manager.enable_acceleration(factor=15.0)

        with pytest.raises(ValueError, match="between 1.0 and 10.0"):
            await manager.enable_acceleration(factor=0.5)

    @pytest.mark.asyncio
    async def test_disable_acceleration(self, manager):
        """Test disabling acceleration."""
        # First enable it
        await manager.enable_acceleration(factor=3.0)
        assert manager.enabled is True

        # Now disable
        result = await manager.disable_acceleration()

        assert result["status"] == "disabled"
        assert manager.enabled is False
        assert manager.acceleration_factor == 1.0
        assert manager.mode == AccelerationMode.DISABLED

    @pytest.mark.asyncio
    async def test_submit_task(self, manager):
        """Test submitting a task to the queue."""
        task = await manager.submit_task(
            task_id="test-1",
            description="Test task",
            priority=TaskPriority.HIGH
        )

        assert task.task_id == "test-1"
        assert task.description == "Test task"
        assert task.priority == TaskPriority.HIGH
        assert task.status == "pending"
        assert len(manager.task_queue) == 1
        assert manager.metrics.queue_size == 1

    @pytest.mark.asyncio
    async def test_task_priority_ordering(self, manager):
        """Test that tasks are ordered by priority in queue."""
        # Submit tasks in random order
        await manager.submit_task("low", "Low priority", TaskPriority.LOW)
        await manager.submit_task("critical", "Critical priority", TaskPriority.CRITICAL)
        await manager.submit_task("normal", "Normal priority", TaskPriority.NORMAL)
        await manager.submit_task("high", "High priority", TaskPriority.HIGH)

        # Verify they are ordered correctly: CRITICAL > HIGH > NORMAL > LOW
        assert manager.task_queue[0].priority == TaskPriority.CRITICAL
        assert manager.task_queue[1].priority == TaskPriority.HIGH
        assert manager.task_queue[2].priority == TaskPriority.NORMAL
        assert manager.task_queue[3].priority == TaskPriority.LOW

    @pytest.mark.asyncio
    async def test_get_status(self, manager):
        """Test getting acceleration status."""
        status = manager.get_status()

        assert "enabled" in status
        assert "mode" in status
        assert "acceleration_factor" in status
        assert "max_concurrent_tasks" in status
        assert "metrics" in status
        assert "timestamp" in status

        assert status["enabled"] is False
        assert status["mode"] == "disabled"
        assert status["acceleration_factor"] == 1.0

    @pytest.mark.asyncio
    async def test_get_metrics(self, manager):
        """Test getting acceleration metrics."""
        metrics = manager.get_metrics()

        assert metrics.active_tasks == 0
        assert metrics.completed_tasks == 0
        assert metrics.failed_tasks == 0
        assert metrics.queue_size == 0
        assert metrics.avg_task_duration == 0.0
        assert metrics.acceleration_factor == 1.0
        assert metrics.mode == AccelerationMode.DISABLED

    @pytest.mark.asyncio
    async def test_task_execution_without_callback(self, manager):
        """Test task execution when no callback is provided."""
        task = await manager.submit_task(
            task_id="test-no-callback",
            description="Task without callback",
            priority=TaskPriority.NORMAL
        )

        await manager.process_tasks()

        # Task should complete immediately without callback
        assert len(manager.completed_tasks) == 1
        assert manager.completed_tasks[0].status == "completed"
        assert manager.completed_tasks[0].task_id == "test-no-callback"

    @pytest.mark.asyncio
    async def test_task_execution_with_callback(self, manager):
        """Test task execution with a callback function."""
        executed = []

        async def test_callback():
            executed.append(True)
            return "success"

        task = await manager.submit_task(
            task_id="test-callback",
            description="Task with callback",
            priority=TaskPriority.NORMAL,
            callback=test_callback
        )

        await manager.process_tasks()

        # Verify callback was executed
        assert len(executed) == 1
        assert len(manager.completed_tasks) == 1
        assert manager.completed_tasks[0].result == "success"

    @pytest.mark.asyncio
    async def test_batch_mode_acceleration(self, manager):
        """Test enabling acceleration in batch mode."""
        result = await manager.enable_acceleration(
            factor=5.0,
            mode=AccelerationMode.BATCH
        )

        assert result["status"] == "enabled"
        assert result["mode"] == "batch"
        assert manager.mode == AccelerationMode.BATCH

    def test_get_global_concurrency_manager(self):
        """Test getting the global concurrency manager singleton."""
        manager1 = get_concurrency_manager()
        manager2 = get_concurrency_manager()

        # Should return the same instance
        assert manager1 is manager2
