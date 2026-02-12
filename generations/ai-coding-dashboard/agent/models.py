"""
Pydantic Models for AI Agent State Management

This module defines all state models for the Pydantic AI agent including:
- Task: Individual task representation
- ProjectState: Project-level state
- AgentState: Core agent state with tasks, progress, and messages
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class TaskStatus(str, Enum):
    """Task status enumeration"""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskCategory(str, Enum):
    """Task category enumeration"""

    FEATURE = "feature"
    BUG = "bug"
    ENHANCEMENT = "enhancement"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    REFACTORING = "refactoring"
    RESEARCH = "research"
    OTHER = "other"


class AgentStatus(str, Enum):
    """Agent status enumeration"""

    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    PAUSED = "paused"
    COMPLETED = "completed"


class Task(BaseModel):
    """
    Task model representing an individual work item

    Attributes:
        id: Unique task identifier
        description: Task description
        status: Current task status
        category: Task category/type
        created_at: Task creation timestamp
        updated_at: Last update timestamp
        assigned_to: Optional assignee
        priority: Task priority (1-5, 1 being highest)
    """

    id: str = Field(..., description="Unique task identifier")
    description: str = Field(..., min_length=1, description="Task description")
    status: TaskStatus = Field(default=TaskStatus.TODO, description="Current task status")
    category: TaskCategory = Field(
        default=TaskCategory.OTHER, description="Task category"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Task creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )
    assigned_to: Optional[str] = Field(default=None, description="Optional assignee")
    priority: int = Field(default=3, ge=1, le=5, description="Task priority (1-5)")

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        """Validate that description is not empty or whitespace"""
        if not v or not v.strip():
            raise ValueError("Description cannot be empty")
        return v.strip()

    class Config:
        """Pydantic model configuration"""

        json_schema_extra = {
            "example": {
                "id": "TASK-001",
                "description": "Implement user authentication",
                "status": "in_progress",
                "category": "feature",
                "priority": 1,
            }
        }


class ProjectState(BaseModel):
    """
    Project state model representing project-level information

    Attributes:
        project_id: Unique project identifier
        name: Project name
        description: Project description
        tasks: List of tasks in the project
        created_at: Project creation timestamp
        updated_at: Last update timestamp
    """

    project_id: str = Field(..., description="Unique project identifier")
    name: str = Field(..., min_length=1, description="Project name")
    description: Optional[str] = Field(default=None, description="Project description")
    tasks: List[Task] = Field(default_factory=list, description="List of project tasks")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Project creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Validate that name is not empty or whitespace"""
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Get a task by its ID"""
        return next((task for task in self.tasks if task.id == task_id), None)

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Get all tasks with a specific status"""
        return [task for task in self.tasks if task.status == status]

    class Config:
        """Pydantic model configuration"""

        json_schema_extra = {
            "example": {
                "project_id": "PRJ-001",
                "name": "AI Coding Dashboard",
                "description": "An AI-powered coding dashboard",
                "tasks": [],
            }
        }


class AgentMessage(BaseModel):
    """
    Agent message model for conversation history

    Attributes:
        role: Message role (user, assistant, system)
        content: Message content
        timestamp: Message timestamp
    """

    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Message timestamp"
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is valid"""
        allowed_roles = ["user", "assistant", "system"]
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return v

    class Config:
        """Pydantic model configuration"""

        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "Create a new feature for authentication",
                "timestamp": "2024-01-01T00:00:00",
            }
        }


class Activity(BaseModel):
    """
    Activity log entry model

    Attributes:
        timestamp: Activity timestamp
        activity_type: Type of activity
        message: Activity message/description
    """

    timestamp: datetime = Field(
        default_factory=datetime.now, description="Activity timestamp"
    )
    activity_type: str = Field(..., description="Type of activity")
    message: str = Field(..., description="Activity message")


class AgentState(BaseModel):
    """
    Core agent state model tracking agent execution

    Attributes:
        project_id: Associated project identifier
        tasks: List of tasks being managed
        current_task_index: Index of the currently active task
        progress: Overall progress percentage (0-100)
        status: Current agent status
        messages: Recent conversation messages
        created_at: State creation timestamp
        updated_at: Last update timestamp
    """

    project_id: str = Field(..., description="Associated project identifier")
    tasks: List[Task] = Field(default_factory=list, description="List of tasks")
    current_task_index: int = Field(
        default=0, ge=0, description="Index of current task"
    )
    progress: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Progress percentage (0-100)"
    )
    status: AgentStatus = Field(default=AgentStatus.IDLE, description="Agent status")
    messages: List[AgentMessage] = Field(
        default_factory=list, description="Recent messages"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="State creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if status is ERROR"
    )

    @field_validator("current_task_index")
    @classmethod
    def validate_task_index(cls, v: int, info) -> int:
        """Validate that current_task_index is within bounds"""
        # Note: Can't validate against tasks length during initialization
        # This is validated at runtime
        return v

    @property
    def current_task(self) -> Optional[Task]:
        """Get the current task being worked on"""
        if 0 <= self.current_task_index < len(self.tasks):
            return self.tasks[self.current_task_index]
        return None

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history"""
        message = AgentMessage(role=role, content=content)
        self.messages.append(message)
        self.updated_at = datetime.now()

    def update_progress(self) -> None:
        """Calculate and update progress based on completed tasks"""
        if not self.tasks:
            self.progress = 0.0
            return

        completed_tasks = sum(
            1 for task in self.tasks if task.status == TaskStatus.COMPLETED
        )
        self.progress = (completed_tasks / len(self.tasks)) * 100
        self.updated_at = datetime.now()

    def next_task(self) -> bool:
        """
        Move to the next task

        Returns:
            True if there is a next task, False if at the end
        """
        if self.current_task_index < len(self.tasks) - 1:
            self.current_task_index += 1
            self.updated_at = datetime.now()
            return True
        return False

    class Config:
        """Pydantic model configuration"""

        json_schema_extra = {
            "example": {
                "project_id": "PRJ-001",
                "tasks": [],
                "current_task_index": 0,
                "progress": 0.0,
                "status": "idle",
                "messages": [],
            }
        }


class StateSnapshot(BaseModel):
    """
    State snapshot for AG-UI communication

    This model represents the current state of agent execution
    and is emitted after each significant state change.

    Attributes:
        project_id: Associated project identifier
        current_task: Currently executing task
        completed_tasks: List of completed tasks
        pending_tasks: List of pending tasks
        progress_percentage: Overall progress (0-100)
        recent_activities: Recent activity log entries
        status: Current agent status
        error_message: Error message if in error state
    """

    project_id: str = Field(..., description="Associated project identifier")
    current_task: Optional[Task] = Field(None, description="Currently executing task")
    completed_tasks: List[Task] = Field(
        default_factory=list, description="Completed tasks"
    )
    pending_tasks: List[Task] = Field(
        default_factory=list, description="Pending tasks"
    )
    progress_percentage: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Progress percentage"
    )
    recent_activities: List[Activity] = Field(
        default_factory=list, description="Recent activities"
    )
    status: AgentStatus = Field(default=AgentStatus.IDLE, description="Agent status")
    error_message: Optional[str] = Field(None, description="Error message if any")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Snapshot timestamp"
    )

    @classmethod
    def from_agent_state(
        cls, state: AgentState, activities: Optional[List[Activity]] = None
    ) -> "StateSnapshot":
        """
        Create a StateSnapshot from AgentState

        Args:
            state: Agent state to snapshot
            activities: Recent activities

        Returns:
            StateSnapshot instance
        """
        completed = [t for t in state.tasks if t.status == TaskStatus.COMPLETED]
        pending = [
            t for t in state.tasks
            if t.status in [TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]
        ]

        return cls(
            project_id=state.project_id,
            current_task=state.current_task,
            completed_tasks=completed,
            pending_tasks=pending,
            progress_percentage=state.progress,
            recent_activities=activities or [],
            status=state.status,
            error_message=state.error_message,
        )

    class Config:
        """Pydantic model configuration"""

        json_schema_extra = {
            "example": {
                "project_id": "PRJ-001",
                "current_task": None,
                "completed_tasks": [],
                "pending_tasks": [],
                "progress_percentage": 0.0,
                "recent_activities": [],
                "status": "idle",
            }
        }


class ApprovalRequest(BaseModel):
    """
    Approval request model for high-risk operations

    Attributes:
        approval_id: Unique approval identifier
        action: Action requiring approval
        description: Detailed description of the action
        risk_level: Risk level (low, medium, high)
        details: Additional context details
        timeout_seconds: Timeout for approval response
        created_at: Request creation timestamp
    """

    approval_id: str = Field(..., description="Unique approval identifier")
    action: str = Field(..., description="Action requiring approval")
    description: str = Field(..., description="Detailed description")
    risk_level: str = Field(
        default="medium",
        description="Risk level (low, medium, high)"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional details"
    )
    timeout_seconds: Optional[int] = Field(
        default=30, description="Timeout in seconds"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Request timestamp"
    )

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        """Validate risk level"""
        allowed_levels = ["low", "medium", "high"]
        if v.lower() not in allowed_levels:
            raise ValueError(f"Risk level must be one of: {', '.join(allowed_levels)}")
        return v.lower()

    class Config:
        """Pydantic model configuration"""

        json_schema_extra = {
            "example": {
                "approval_id": "APR-001",
                "action": "Delete production database",
                "description": "This will permanently delete all production data",
                "risk_level": "high",
                "details": {"database": "production", "records": 1000000},
                "timeout_seconds": 30,
            }
        }
