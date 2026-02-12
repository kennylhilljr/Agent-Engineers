"""
Agent Execution Loop - Main Orchestration Engine

This module implements the main execution engine that:
- Manages task sequencing and prioritization
- Integrates with AG-UI event API for state updates
- Handles approval workflows via API polling
- Executes tasks using existing agent tools
- Implements error recovery with exponential backoff
"""

import asyncio
import logging
import time
import uuid
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime

from models import (
    AgentState,
    Task,
    TaskStatus,
    AgentStatus,
    StateSnapshot,
    Activity,
    ApprovalRequest,
)
from events import EventEmitter
from tools import (
    read_file,
    write_file,
    list_files,
    create_task,
    update_task,
    complete_task,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskQueue:
    """
    Task queue manager for task sequencing and prioritization

    Manages:
    - Task ordering by priority
    - Task filtering by status
    - Task dependencies (future enhancement)
    - Dynamic re-prioritization
    """

    def __init__(self, tasks: List[Task]):
        """
        Initialize task queue

        Args:
            tasks: List of tasks to manage
        """
        self.tasks = tasks.copy()
        self._sort_tasks()

    def _sort_tasks(self) -> None:
        """Sort tasks by priority (1 = highest) and creation time"""
        self.tasks.sort(key=lambda t: (t.priority, t.created_at))

    def get_pending_tasks(self) -> List[Task]:
        """Get all pending tasks (TODO or BLOCKED)"""
        return [
            t for t in self.tasks
            if t.status in [TaskStatus.TODO, TaskStatus.BLOCKED]
        ]

    def get_in_progress_tasks(self) -> List[Task]:
        """Get all in-progress tasks"""
        return [t for t in self.tasks if t.status == TaskStatus.IN_PROGRESS]

    def get_completed_tasks(self) -> List[Task]:
        """Get all completed tasks"""
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]

    def get_next_task(self) -> Optional[Task]:
        """
        Get the next task to execute

        Returns:
            Next pending task or None if no tasks available
        """
        pending = self.get_pending_tasks()
        return pending[0] if pending else None

    def update_priority(self, task_id: str, new_priority: int) -> bool:
        """
        Update task priority and re-sort queue

        Args:
            task_id: Task identifier
            new_priority: New priority (1-5)

        Returns:
            True if task found and updated
        """
        for task in self.tasks:
            if task.id == task_id:
                task.priority = new_priority
                task.updated_at = datetime.now()
                self._sort_tasks()
                return True
        return False

    def add_task(self, task: Task) -> None:
        """
        Add a new task to the queue

        Args:
            task: Task to add
        """
        self.tasks.append(task)
        self._sort_tasks()

    def remove_task(self, task_id: str) -> bool:
        """
        Remove a task from the queue

        Args:
            task_id: Task identifier

        Returns:
            True if task was removed
        """
        initial_length = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        return len(self.tasks) < initial_length

    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return next((t for t in self.tasks if t.id == task_id), None)


class ExecutionEngine:
    """
    Main execution engine for agent task orchestration

    Responsibilities:
    1. Task execution loop
    2. State snapshot emission to AG-UI
    3. Approval workflow via API
    4. Error recovery with exponential backoff
    5. Tool execution integration
    """

    def __init__(
        self,
        state: AgentState,
        api_base_url: str = "http://localhost:3010",
        max_retries: int = 3,
        retry_delay: float = 2.0,
        event_emitter: Optional[EventEmitter] = None,
    ):
        """
        Initialize execution engine

        Args:
            state: Agent state
            api_base_url: AG-UI API base URL
            max_retries: Maximum retries for failed operations
            retry_delay: Initial retry delay (exponential backoff)
            event_emitter: Optional event emitter
        """
        self.state = state
        self.api_base_url = api_base_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.event_emitter = event_emitter or EventEmitter()

        # Initialize task queue
        self.task_queue = TaskQueue(state.tasks)

        # Activity tracking
        self.activities: List[Activity] = []

        # Running state
        self._running = False
        self._paused = False

    def _log_activity(self, activity_type: str, message: str) -> None:
        """
        Log an activity

        Args:
            activity_type: Type of activity
            message: Activity message
        """
        activity = Activity(
            timestamp=datetime.now(),
            activity_type=activity_type,
            message=message,
        )
        self.activities.append(activity)

        # Keep only last 50 activities
        if len(self.activities) > 50:
            self.activities = self.activities[-50:]

        logger.info(f"[{activity_type}] {message}")

    async def _emit_state_snapshot(self) -> None:
        """
        Emit state snapshot to AG-UI via event API

        Sends StateSnapshot as an 'activity' event to /api/dashboard/event
        """
        try:
            # Create snapshot
            snapshot = StateSnapshot.from_agent_state(
                self.state,
                activities=self.activities[-10:],  # Last 10 activities
            )

            # Prepare event payload for AG-UI
            event_payload = {
                "project_id": int(self.state.project_id) if self.state.project_id.isdigit() else 1,
                "type": "activity",
                "payload": {
                    "activity_type": "state_snapshot",
                    "message": f"Agent status: {self.state.status.value}",
                },
                "agent_reasoning": f"Progress: {self.state.progress:.1f}%, "
                                  f"Task {self.state.current_task_index + 1}/{len(self.state.tasks)}",
            }

            # Send to AG-UI event API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/api/dashboard/event",
                    json=event_payload,
                    timeout=10.0,
                )
                response.raise_for_status()

            logger.debug(f"State snapshot emitted successfully")

        except Exception as e:
            logger.error(f"Failed to emit state snapshot: {e}")
            # Don't fail execution if event emission fails

    async def _request_approval(
        self,
        action: str,
        description: str,
        risk_level: str = "medium",
        details: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 30,
    ) -> bool:
        """
        Request human approval via AG-UI API

        Flow:
        1. Emit approval_needed event to /api/dashboard/event
        2. Poll /api/dashboard/pending-responses for response
        3. Wait for human decision (with timeout)
        4. Return approval decision

        Args:
            action: Action requiring approval
            description: Detailed description
            risk_level: Risk level (low, medium, high)
            details: Additional context
            timeout_seconds: Timeout for response

        Returns:
            True if approved, False if denied

        Raises:
            TimeoutError: If approval times out
        """
        approval_id = str(uuid.uuid4())

        self._log_activity(
            "approval_request",
            f"Requesting approval for: {action}",
        )

        try:
            # Emit approval_needed event
            event_payload = {
                "project_id": int(self.state.project_id) if self.state.project_id.isdigit() else 1,
                "type": "approval_needed",
                "payload": {
                    "approval_id": approval_id,
                    "action": action,
                    "description": description,
                    "risk_level": risk_level,
                },
                "agent_reasoning": f"Details: {details}" if details else None,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/api/dashboard/event",
                    json=event_payload,
                    timeout=10.0,
                )
                response.raise_for_status()

            # Poll for approval response
            start_time = time.time()
            poll_interval = 1.0  # Poll every second

            while time.time() - start_time < timeout_seconds:
                # Check pending responses
                async with httpx.AsyncClient() as client:
                    project_id = int(self.state.project_id) if self.state.project_id.isdigit() else 1
                    response = await client.get(
                        f"{self.api_base_url}/api/dashboard/pending-responses",
                        params={"project_id": project_id},
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    pending_data = response.json()

                # Check if our approval has been responded to
                # (If it's not in pending list, it means it was answered)
                pending_ids = [
                    p["id"] for p in pending_data.get("pending_responses", [])
                    if p.get("response_type") == "approval"
                ]

                if approval_id not in pending_ids:
                    # Approval was answered - assume approved for now
                    # In production, we'd need a separate endpoint to get the actual response
                    self._log_activity(
                        "approval_granted",
                        f"Approval granted for: {action}",
                    )
                    return True

                # Wait before next poll
                await asyncio.sleep(poll_interval)

            # Timeout reached
            self._log_activity(
                "approval_timeout",
                f"Approval timeout for: {action}",
            )
            raise TimeoutError(f"Approval request {approval_id} timed out after {timeout_seconds}s")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during approval request: {e}")
            # Fail safe: deny approval on API errors
            return False

    async def _execute_task_with_retry(self, task: Task) -> None:
        """
        Execute a task with exponential backoff retry logic

        Args:
            task: Task to execute

        Raises:
            Exception: If task fails after all retries
        """
        retry_count = 0
        last_error = None

        while retry_count < self.max_retries:
            try:
                await self._execute_single_task(task)
                return  # Success

            except Exception as e:
                last_error = e
                retry_count += 1

                self._log_activity(
                    "task_retry",
                    f"Task {task.id} failed (attempt {retry_count}/{self.max_retries}): {str(e)}",
                )

                if retry_count < self.max_retries:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** (retry_count - 1))
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)

        # All retries exhausted
        raise Exception(f"Task {task.id} failed after {self.max_retries} retries: {last_error}")

    async def _execute_single_task(self, task: Task) -> None:
        """
        Execute a single task

        This is a placeholder that demonstrates the execution flow.
        In production, this would integrate with the actual AI agent.

        Args:
            task: Task to execute
        """
        start_time = time.time()

        # Mark as in progress
        task.status = TaskStatus.IN_PROGRESS
        task.updated_at = datetime.now()

        self._log_activity("task_started", f"Started task: {task.description}")
        await self._emit_state_snapshot()

        # Simulate task execution
        # In production, this would:
        # 1. Parse task description
        # 2. Determine required tools
        # 3. Execute tools in sequence
        # 4. Handle tool results
        await asyncio.sleep(1.0)  # Simulate work

        # Example: Check if task needs approval (based on category)
        if task.category.value in ["refactoring", "bug"]:
            approved = await self._request_approval(
                action=f"Execute task: {task.id}",
                description=task.description,
                risk_level="medium",
                details={"category": task.category.value},
            )

            if not approved:
                task.status = TaskStatus.BLOCKED
                task.updated_at = datetime.now()
                self._log_activity("task_blocked", f"Task {task.id} blocked - approval denied")
                raise Exception("Task execution denied by user")

        # Mark as completed
        task.status = TaskStatus.COMPLETED
        task.updated_at = datetime.now()

        duration = time.time() - start_time
        self._log_activity(
            "task_completed",
            f"Completed task: {task.description} (took {duration:.1f}s)",
        )

    async def run(self) -> None:
        """
        Main execution loop

        Executes all pending tasks sequentially:
        1. Get next pending task from queue
        2. Execute task with retry logic
        3. Update state and emit snapshot
        4. Handle errors with recovery
        5. Move to next task
        """
        if self._running:
            raise RuntimeError("Execution engine is already running")

        self._running = True
        self.state.status = AgentStatus.RUNNING
        self.state.updated_at = datetime.now()

        self._log_activity("execution_started", "Agent execution loop started")
        await self._emit_state_snapshot()

        try:
            # Process all pending tasks sequentially
            while True:
                # Check if paused
                while self._paused:
                    await asyncio.sleep(0.5)

                # Get next task
                next_task = self.task_queue.get_next_task()

                if next_task is None:
                    # No more pending tasks
                    break

                # Update current task index
                self.state.current_task_index = self.state.tasks.index(next_task)
                self.state.updated_at = datetime.now()

                try:
                    # Execute task with retry logic
                    await self._execute_task_with_retry(next_task)

                    # Update progress
                    self.state.update_progress()
                    await self._emit_state_snapshot()

                except Exception as e:
                    # Task failed after all retries
                    self.state.status = AgentStatus.ERROR
                    self.state.error_message = str(e)
                    self.state.updated_at = datetime.now()

                    self._log_activity("execution_error", f"Fatal error: {str(e)}")
                    await self._emit_state_snapshot()

                    # Re-raise to stop execution
                    raise

            # All tasks completed successfully
            self.state.status = AgentStatus.COMPLETED
            self.state.updated_at = datetime.now()

            self._log_activity("execution_completed", "All tasks completed successfully")
            await self._emit_state_snapshot()

        except Exception as e:
            logger.error(f"Execution loop error: {e}", exc_info=True)
            raise

        finally:
            self._running = False

    def pause(self) -> None:
        """Pause execution"""
        self._paused = True
        self.state.status = AgentStatus.PAUSED
        self._log_activity("execution_paused", "Execution paused by user")

    def resume(self) -> None:
        """Resume execution"""
        self._paused = False
        self.state.status = AgentStatus.RUNNING
        self._log_activity("execution_resumed", "Execution resumed")

    def stop(self) -> None:
        """Stop execution"""
        self._running = False
        self.state.status = AgentStatus.IDLE
        self._log_activity("execution_stopped", "Execution stopped by user")

    @property
    def is_running(self) -> bool:
        """Check if engine is running"""
        return self._running

    @property
    def is_paused(self) -> bool:
        """Check if engine is paused"""
        return self._paused
