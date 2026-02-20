import pytest
import asyncio
from agents.orchestrator import ConcurrencyManager, ConcurrencyConfig, PriorityLevel


@pytest.mark.asyncio
async def test_concurrency_manager_initialization():
    config = ConcurrencyConfig(max_workers=5, max_queue_size=100)
    manager = ConcurrencyManager(config)
    await manager.initialize()
    assert manager._running is True
    assert len(manager.workers) == 5
    await manager.shutdown()


@pytest.mark.asyncio
async def test_submit_task():
    manager = ConcurrencyManager()
    await manager.initialize()
    
    async def sample_task():
        await asyncio.sleep(0.01)
        return "completed"
    
    task_id = await manager.submit_task("task1", sample_task)
    assert task_id == "task1"
    await asyncio.sleep(0.1)
    await manager.shutdown()


@pytest.mark.asyncio
async def test_task_metrics():
    manager = ConcurrencyManager()
    await manager.initialize()
    
    async def sample_task():
        await asyncio.sleep(0.05)
    
    await manager.submit_task("task1", sample_task)
    await asyncio.sleep(0.2)
    
    metrics = await manager.get_task_metrics("task1")
    assert metrics is not None
    assert metrics.status == "completed"
    
    await manager.shutdown()


@pytest.mark.asyncio
async def test_acceleration_enabled():
    manager = ConcurrencyManager()
    await manager.initialize()
    
    assert not manager.is_acceleration_enabled()
    manager.enable_acceleration(True)
    assert manager.is_acceleration_enabled()
    
    await manager.shutdown()


@pytest.mark.asyncio
async def test_queue_stats():
    manager = ConcurrencyManager(ConcurrencyConfig(max_workers=3))
    await manager.initialize()
    
    stats = manager.get_queue_stats()
    assert stats['max_workers'] == 3
    assert stats['queue_size'] == 0
    
    await manager.shutdown()


@pytest.mark.asyncio
async def test_multiple_tasks():
    manager = ConcurrencyManager(ConcurrencyConfig(max_workers=5))
    await manager.initialize()
    
    async def dummy_task(duration=0.01):
        await asyncio.sleep(duration)
    
    for i in range(5):
        await manager.submit_task(f"task_{i}", lambda d=0.01: dummy_task(d))
    
    await asyncio.sleep(0.2)
    await manager.shutdown()


@pytest.mark.asyncio
async def test_acceleration_metrics():
    manager = ConcurrencyManager()
    await manager.initialize()
    manager.enable_acceleration(True)
    
    async def quick_task():
        await asyncio.sleep(0.01)
    
    await manager.submit_task("task1", quick_task)
    await asyncio.sleep(0.1)
    
    metrics = manager.get_acceleration_metrics()
    assert metrics['acceleration_enabled'] is True
    assert metrics['acceleration_factor'] == 1.5
    
    await manager.shutdown()


@pytest.mark.asyncio
async def test_task_priority():
    manager = ConcurrencyManager()
    await manager.initialize()
    
    async def task():
        await asyncio.sleep(0.01)
    
    await manager.submit_task("high", task, priority=PriorityLevel.HIGH)
    await manager.submit_task("low", task, priority=PriorityLevel.LOW)
    
    await asyncio.sleep(0.1)
    await manager.shutdown()


@pytest.mark.asyncio
async def test_batch_mode():
    manager = ConcurrencyManager()
    await manager.initialize()
    
    async def task():
        await asyncio.sleep(0.01)
    
    async with manager.batch_mode():
        for i in range(3):
            await manager.submit_task(f"batch_task_{i}", task)
    
    await asyncio.sleep(0.2)
    await manager.shutdown()


@pytest.mark.asyncio
async def test_task_timeout():
    manager = ConcurrencyManager(ConcurrencyConfig(task_timeout_seconds=0.05))
    await manager.initialize()
    
    async def slow_task():
        await asyncio.sleep(1.0)
    
    await manager.submit_task("timeout_task", slow_task, timeout=0.05)
    await asyncio.sleep(0.2)
    
    metrics = await manager.get_task_metrics("timeout_task")
    assert metrics.status == "timeout"
    
    await manager.shutdown()
