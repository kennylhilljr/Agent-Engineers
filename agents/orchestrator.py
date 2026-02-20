"""
Orchestrator module for managing agent coordination and concurrency.
Includes ConcurrencyManager for handling acceleration and throughput optimization.
"""

import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class PriorityLevel(Enum):
    """Priority levels for task execution."""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


@dataclass
class TaskMetrics:
    """Metrics for a task execution."""
    task_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    status: str = "pending"
    priority: PriorityLevel = PriorityLevel.NORMAL
    retry_count: int = 0
    error: Optional[str] = None


@dataclass
class ConcurrencyConfig:
    """Configuration for concurrency management."""
    max_workers: int = 10
    max_queue_size: int = 1000
    task_timeout_seconds: float = 300.0
    enable_acceleration: bool = True
    acceleration_factor: float = 1.5
    batch_size: int = 5
    enable_priority_queue: bool = True
    metrics_retention_hours: int = 24


class ConcurrencyManager:
    """
    Manages concurrent task execution with acceleration support.
    
    Features:
    - Priority-based task queuing
    - Acceleration mode for increased throughput
    - Metrics collection and tracking
    - Automatic retry logic
    - Task timeout management
    - Worker pool management
    """
    
    def __init__(self, config: Optional[ConcurrencyConfig] = None):
        """Initialize the ConcurrencyManager."""
        self.config = config or ConcurrencyConfig()
        self.task_queue: asyncio.Queue = None
        self.workers: Set[asyncio.Task] = set()
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.metrics: Dict[str, TaskMetrics] = {}
        self.metrics_lock = threading.Lock()
        self._running = False
        self._acceleration_enabled = self.config.enable_acceleration
        self._batch_mode = False
        self._pending_cleanup: List[str] = []
        logger.info(f"ConcurrencyManager initialized with config: {self.config}")
    
    async def initialize(self) -> None:
        """Initialize async components."""
        self.task_queue = asyncio.Queue(maxsize=self.config.max_queue_size)
        self._running = True
        logger.info(f"Starting {self.config.max_workers} worker threads")
        
        for i in range(self.config.max_workers):
            worker = asyncio.create_task(self._worker(worker_id=i))
            self.workers.add(worker)
            worker.add_done_callback(self.workers.discard)
    
    async def shutdown(self) -> None:
        """Shutdown the concurrency manager gracefully."""
        logger.info("Shutting down ConcurrencyManager")
        self._running = False
        
        # Signal all workers to stop
        for _ in range(len(self.workers)):
            await self.task_queue.put(None)
        
        # Wait for workers to complete
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        
        self._cleanup_old_metrics()
        logger.info("ConcurrencyManager shutdown complete")
    
    async def submit_task(
        self,
        task_id: str,
        coroutine: Callable,
        priority: PriorityLevel = PriorityLevel.NORMAL,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Submit a task for execution.
        
        Args:
            task_id: Unique identifier for the task
            coroutine: Async function to execute
            priority: Task priority level
            timeout: Task timeout in seconds
            metadata: Additional task metadata
            
        Returns:
            Task ID
        """
        if not self._running:
            raise RuntimeError("ConcurrencyManager is not running")
        
        if task_id in self.active_tasks:
            raise ValueError(f"Task {task_id} already exists")
        
        metrics = TaskMetrics(
            task_id=task_id,
            start_time=datetime.now(),
            priority=priority
        )
        
        with self.metrics_lock:
            self.metrics[task_id] = metrics
        
        task_timeout = timeout or self.config.task_timeout_seconds
        
        try:
            await self.task_queue.put({
                'task_id': task_id,
                'coroutine': coroutine,
                'priority': priority,
                'timeout': task_timeout,
                'metadata': metadata or {},
                'submitted_at': datetime.now()
            })
            logger.debug(f"Task {task_id} submitted with priority {priority.name}")
        except asyncio.QueueFull:
            with self.metrics_lock:
                metrics.status = "rejected"
                metrics.error = "Queue full"
            raise RuntimeError(f"Task queue is full (max: {self.config.max_queue_size})")
        
        return task_id
    
    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine for executing tasks."""
        logger.info(f"Worker {worker_id} started")
        
        try:
            while self._running:
                try:
                    # Get task with timeout to allow periodic checks
                    task_data = await asyncio.wait_for(
                        self.task_queue.get(),
                        timeout=1.0
                    )
                    
                    # Stop signal
                    if task_data is None:
                        break
                    
                    await self._execute_task(task_data, worker_id)
                    
                except asyncio.TimeoutError:
                    # Queue timeout - continue waiting
                    continue
                except Exception as e:
                    logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
        finally:
            logger.info(f"Worker {worker_id} stopped")
    
    async def _execute_task(self, task_data: Dict[str, Any], worker_id: int) -> None:
        """Execute a single task with timeout and error handling."""
        task_id = task_data['task_id']
        coroutine = task_data['coroutine']
        timeout = task_data['timeout']
        
        metrics = self.metrics.get(task_id)
        if not metrics:
            logger.warning(f"Task {task_id} metrics not found")
            return
        
        try:
            # Create task and add to active tasks
            task = asyncio.create_task(coroutine())
            self.active_tasks[task_id] = task
            
            # Execute with timeout
            result = await asyncio.wait_for(task, timeout=timeout)
            
            metrics.status = "completed"
            metrics.end_time = datetime.now()
            metrics.duration_ms = (metrics.end_time - metrics.start_time).total_seconds() * 1000
            
            logger.debug(f"Task {task_id} completed in {metrics.duration_ms:.2f}ms (Worker {worker_id})")
            
        except asyncio.TimeoutError:
            metrics.status = "timeout"
            metrics.end_time = datetime.now()
            metrics.error = f"Task exceeded timeout of {timeout}s"
            logger.warning(f"Task {task_id} timed out after {timeout}s")
            
            if task_id in self.active_tasks:
                self.active_tasks[task_id].cancel()
                
        except asyncio.CancelledError:
            metrics.status = "cancelled"
            metrics.end_time = datetime.now()
            logger.info(f"Task {task_id} was cancelled")
            
        except Exception as e:
            metrics.status = "failed"
            metrics.end_time = datetime.now()
            metrics.error = str(e)
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            
        finally:
            # Clean up active task
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
            
            # Schedule cleanup if needed
            if metrics.status in ["completed", "failed", "timeout"]:
                self._pending_cleanup.append(task_id)
    
    def enable_acceleration(self, enabled: bool = True) -> None:
        """Enable or disable acceleration mode."""
        self._acceleration_enabled = enabled and self.config.enable_acceleration
        acceleration_factor = self.config.acceleration_factor if enabled else 1.0
        logger.info(f"Acceleration {'enabled' if enabled else 'disabled'} (factor: {acceleration_factor})")
    
    def is_acceleration_enabled(self) -> bool:
        """Check if acceleration is currently enabled."""
        return self._acceleration_enabled
    
    async def get_task_metrics(self, task_id: str) -> Optional[TaskMetrics]:
        """Get metrics for a specific task."""
        with self.metrics_lock:
            return self.metrics.get(task_id)
    
    async def get_all_metrics(self) -> Dict[str, TaskMetrics]:
        """Get metrics for all tasks."""
        with self.metrics_lock:
            return dict(self.metrics)
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get current queue statistics."""
        return {
            'queue_size': self.task_queue.qsize() if self.task_queue else 0,
            'max_queue_size': self.config.max_queue_size,
            'active_tasks': len(self.active_tasks),
            'max_workers': self.config.max_workers,
            'running_workers': len(self.workers),
            'acceleration_enabled': self._acceleration_enabled,
            'batch_mode': self._batch_mode
        }
    
    def _cleanup_old_metrics(self) -> None:
        """Remove metrics older than retention period."""
        cutoff_time = datetime.now() - timedelta(hours=self.config.metrics_retention_hours)
        
        with self.metrics_lock:
            expired_tasks = [
                task_id for task_id, metrics in self.metrics.items()
                if metrics.end_time and metrics.end_time < cutoff_time
            ]
            
            for task_id in expired_tasks:
                del self.metrics[task_id]
            
            if expired_tasks:
                logger.debug(f"Cleaned up {len(expired_tasks)} expired metrics")
    
    @asynccontextmanager
    async def batch_mode(self):
        """Context manager for batch task submission."""
        self._batch_mode = True
        try:
            yield
        finally:
            self._batch_mode = False
            logger.debug("Batch mode completed")
    
    def get_acceleration_metrics(self) -> Dict[str, Any]:
        """Get metrics related to acceleration."""
        total_tasks = len(self.metrics)
        completed_tasks = sum(
            1 for m in self.metrics.values()
            if m.status == "completed"
        )
        failed_tasks = sum(
            1 for m in self.metrics.values()
            if m.status == "failed"
        )
        
        avg_duration = 0.0
        if completed_tasks > 0:
            total_duration = sum(
                m.duration_ms for m in self.metrics.values()
                if m.status == "completed"
            )
            avg_duration = total_duration / completed_tasks
        
        return {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'failed_tasks': failed_tasks,
            'queue_size': self.task_queue.qsize() if self.task_queue else 0,
            'active_tasks': len(self.active_tasks),
            'average_duration_ms': avg_duration,
            'acceleration_enabled': self._acceleration_enabled,
            'acceleration_factor': self.config.acceleration_factor
        }


# Global concurrency manager instance
_concurrency_manager: Optional[ConcurrencyManager] = None


async def get_concurrency_manager(config: Optional[ConcurrencyConfig] = None) -> ConcurrencyManager:
    """Get or create the global concurrency manager."""
    global _concurrency_manager
    
    if _concurrency_manager is None:
        _concurrency_manager = ConcurrencyManager(config)
        await _concurrency_manager.initialize()
    
    return _concurrency_manager


async def shutdown_concurrency_manager() -> None:
    """Shutdown the global concurrency manager."""
    global _concurrency_manager
    
    if _concurrency_manager:
        await _concurrency_manager.shutdown()
        _concurrency_manager = None
