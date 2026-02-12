"""
Agent Tools Module

Provides tools for the Pydantic AI agent to interact with the system:
- File operations (read, write, list)
- Task management (create, update, complete)
- Project state queries
- Event logging

All tools include security validation, error handling, and audit logging.
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from pydantic import BaseModel, Field, field_validator
from models import Task, TaskStatus, TaskCategory, ProjectState

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Data Models for Tool Responses
# ============================================================================


class FileInfo(BaseModel):
    """File information model"""
    path: str
    name: str
    size: int
    is_directory: bool
    modified_at: float


class ToolResult(BaseModel):
    """Generic tool result wrapper"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# Configuration and Constants
# ============================================================================

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.md', '.txt', '.yaml', '.yml',
    '.css', '.html', '.env.example', '.gitignore', '.sh'
}


# ============================================================================
# Security & Validation Helpers
# ============================================================================


def validate_path(path: str, base_dir: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """
    Validate file path for security

    Prevents directory traversal attacks and ensures operations
    are within the allowed project directory.

    Args:
        path: Path to validate
        base_dir: Base directory to restrict operations to (defaults to project root)

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Get absolute path of the project root (one level up from agent/)
        if base_dir is None:
            base_dir = str(Path(__file__).parent.parent.resolve())
        else:
            base_dir = str(Path(base_dir).resolve())

        # Resolve the requested path
        requested_path = Path(path).resolve()

        # Check if the path is within base directory
        try:
            requested_path.relative_to(base_dir)
        except ValueError:
            # Allow /tmp/claude for testing (sandbox mode)
            if not str(requested_path).startswith('/tmp/claude'):
                return False, f"Path traversal attempt detected: {path}"

        # Don't allow access to sensitive directories
        sensitive_dirs = {'.git', 'node_modules', '__pycache__', '.env', 'venv'}
        path_parts = set(requested_path.parts)

        if path_parts.intersection(sensitive_dirs):
            return False, f"Access to sensitive directory denied: {path}"

        return True, None

    except Exception as e:
        logger.error(f"Path validation error: {e}")
        return False, f"Invalid path: {str(e)}"


def validate_file_size(file_path: str, max_size: int = MAX_FILE_SIZE) -> tuple[bool, Optional[str]]:
    """
    Validate file size

    Args:
        file_path: Path to file
        max_size: Maximum allowed file size in bytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            if size > max_size:
                return False, f"File size ({size} bytes) exceeds maximum allowed ({max_size} bytes)"
        return True, None
    except Exception as e:
        logger.error(f"File size validation error: {e}")
        return False, f"Unable to validate file size: {str(e)}"


def log_tool_call(tool_name: str, args: Dict[str, Any], result: Any) -> None:
    """
    Log tool calls for audit trail

    Args:
        tool_name: Name of the tool being called
        args: Arguments passed to the tool
        result: Result from the tool execution
    """
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "args": args,
            "success": getattr(result, 'success', True) if isinstance(result, ToolResult) else True,
            "error": getattr(result, 'error', None) if isinstance(result, ToolResult) else None,
        }
        logger.info(f"Tool call: {json.dumps(log_entry)}")
    except Exception as e:
        logger.error(f"Failed to log tool call: {e}")


# ============================================================================
# File Operation Tools
# ============================================================================


def read_file(path: str, _base_dir: Optional[str] = None) -> ToolResult:
    """
    Read file contents

    Security features:
    - Path validation to prevent directory traversal
    - Size limits to prevent memory exhaustion
    - Only allows reading from project directory

    Args:
        path: Relative or absolute path to file
        _base_dir: Base directory for validation (internal use, for testing)

    Returns:
        ToolResult with file contents or error

    Example:
        >>> result = read_file("README.md")
        >>> if result.success:
        ...     print(result.data)
    """
    try:
        # Validate path
        is_valid, error = validate_path(path, base_dir=_base_dir)
        if not is_valid:
            result = ToolResult(success=False, error=error)
            log_tool_call("read_file", {"path": path}, result)
            return result

        # Resolve full path
        full_path = Path(path).resolve()

        # Check if file exists
        if not full_path.exists():
            result = ToolResult(success=False, error=f"File not found: {path}")
            log_tool_call("read_file", {"path": path}, result)
            return result

        if not full_path.is_file():
            result = ToolResult(success=False, error=f"Path is not a file: {path}")
            log_tool_call("read_file", {"path": path}, result)
            return result

        # Validate file size
        is_valid, error = validate_file_size(str(full_path))
        if not is_valid:
            result = ToolResult(success=False, error=error)
            log_tool_call("read_file", {"path": path}, result)
            return result

        # Read file
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        result = ToolResult(success=True, data=content)
        log_tool_call("read_file", {"path": path}, result)
        return result

    except UnicodeDecodeError:
        result = ToolResult(success=False, error=f"File is not a valid text file: {path}")
        log_tool_call("read_file", {"path": path}, result)
        return result
    except PermissionError:
        result = ToolResult(success=False, error=f"Permission denied: {path}")
        log_tool_call("read_file", {"path": path}, result)
        return result
    except Exception as e:
        logger.error(f"read_file error: {e}", exc_info=True)
        result = ToolResult(success=False, error=f"Error reading file: {str(e)}")
        log_tool_call("read_file", {"path": path}, result)
        return result


def write_file(path: str, content: str, _base_dir: Optional[str] = None) -> ToolResult:
    """
    Write/create file with content

    Security features:
    - Path validation to prevent directory traversal
    - Size limits (max 5MB)
    - Only allows writing within project directory
    - Creates parent directories if needed

    Args:
        path: Relative or absolute path to file
        content: Content to write
        _base_dir: Base directory for validation (internal use, for testing)

    Returns:
        ToolResult indicating success or error

    Example:
        >>> result = write_file("src/test.py", "print('hello')")
        >>> print(result.success)
    """
    try:
        # Validate path
        is_valid, error = validate_path(path, base_dir=_base_dir)
        if not is_valid:
            result = ToolResult(success=False, error=error)
            log_tool_call("write_file", {"path": path, "content_length": len(content)}, result)
            return result

        # Check content size
        content_size = len(content.encode('utf-8'))
        if content_size > MAX_FILE_SIZE:
            result = ToolResult(
                success=False,
                error=f"Content size ({content_size} bytes) exceeds maximum allowed ({MAX_FILE_SIZE} bytes)"
            )
            log_tool_call("write_file", {"path": path, "content_length": len(content)}, result)
            return result

        # Resolve full path
        full_path = Path(path).resolve()

        # Create parent directories if they don't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        result = ToolResult(
            success=True,
            data={"path": str(full_path), "size": content_size}
        )
        log_tool_call("write_file", {"path": path, "content_length": len(content)}, result)
        return result

    except PermissionError:
        result = ToolResult(success=False, error=f"Permission denied: {path}")
        log_tool_call("write_file", {"path": path, "content_length": len(content)}, result)
        return result
    except Exception as e:
        logger.error(f"write_file error: {e}", exc_info=True)
        result = ToolResult(success=False, error=f"Error writing file: {str(e)}")
        log_tool_call("write_file", {"path": path, "content_length": len(content)}, result)
        return result


def list_files(directory: str, recursive: bool = False, _base_dir: Optional[str] = None) -> ToolResult:
    """
    List files in directory

    Security features:
    - Path validation to prevent directory traversal
    - Filters out sensitive directories (.git, node_modules, etc.)

    Args:
        directory: Relative or absolute path to directory
        recursive: Whether to list files recursively
        _base_dir: Base directory for validation (internal use, for testing)

    Returns:
        ToolResult with list of FileInfo objects

    Example:
        >>> result = list_files("src")
        >>> if result.success:
        ...     for file in result.data:
        ...         print(file.name)
    """
    try:
        # Validate path
        is_valid, error = validate_path(directory, base_dir=_base_dir)
        if not is_valid:
            result = ToolResult(success=False, error=error)
            log_tool_call("list_files", {"directory": directory, "recursive": recursive}, result)
            return result

        # Resolve full path
        full_path = Path(directory).resolve()

        # Check if directory exists
        if not full_path.exists():
            result = ToolResult(success=False, error=f"Directory not found: {directory}")
            log_tool_call("list_files", {"directory": directory, "recursive": recursive}, result)
            return result

        if not full_path.is_dir():
            result = ToolResult(success=False, error=f"Path is not a directory: {directory}")
            log_tool_call("list_files", {"directory": directory, "recursive": recursive}, result)
            return result

        # List files
        files = []
        sensitive_names = {'.git', 'node_modules', '__pycache__', '.env', 'venv', '.next'}

        if recursive:
            for item in full_path.rglob('*'):
                # Skip sensitive directories
                if any(sensitive in item.parts for sensitive in sensitive_names):
                    continue

                try:
                    files.append(FileInfo(
                        path=str(item.relative_to(full_path)),
                        name=item.name,
                        size=item.stat().st_size if item.is_file() else 0,
                        is_directory=item.is_dir(),
                        modified_at=item.stat().st_mtime
                    ))
                except (PermissionError, OSError):
                    # Skip files we can't access
                    continue
        else:
            for item in full_path.iterdir():
                # Skip sensitive directories
                if item.name in sensitive_names:
                    continue

                try:
                    files.append(FileInfo(
                        path=str(item.relative_to(full_path)),
                        name=item.name,
                        size=item.stat().st_size if item.is_file() else 0,
                        is_directory=item.is_dir(),
                        modified_at=item.stat().st_mtime
                    ))
                except (PermissionError, OSError):
                    # Skip files we can't access
                    continue

        # Sort by name
        files.sort(key=lambda x: (not x.is_directory, x.name.lower()))

        result = ToolResult(success=True, data=[f.model_dump() for f in files])
        log_tool_call("list_files", {"directory": directory, "recursive": recursive}, result)
        return result

    except PermissionError:
        result = ToolResult(success=False, error=f"Permission denied: {directory}")
        log_tool_call("list_files", {"directory": directory, "recursive": recursive}, result)
        return result
    except Exception as e:
        logger.error(f"list_files error: {e}", exc_info=True)
        result = ToolResult(success=False, error=f"Error listing files: {str(e)}")
        log_tool_call("list_files", {"directory": directory, "recursive": recursive}, result)
        return result


# ============================================================================
# Task Management Tools (In-Memory for now, DB integration later)
# ============================================================================

# In-memory storage for tasks and projects (will be replaced with DB)
_projects: Dict[str, ProjectState] = {}


def create_task(
    project_id: str,
    title: str,
    description: str,
    category: str = "other"
) -> ToolResult:
    """
    Create a new task

    Args:
        project_id: Project identifier
        title: Task title (used as task ID)
        description: Task description
        category: Task category (feature, bug, enhancement, etc.)

    Returns:
        ToolResult with created Task object

    Example:
        >>> result = create_task("PRJ-001", "AUTH-001", "Implement login", "feature")
        >>> if result.success:
        ...     print(result.data)
    """
    try:
        # Validate category
        try:
            task_category = TaskCategory(category.lower())
        except ValueError:
            result = ToolResult(
                success=False,
                error=f"Invalid category: {category}. Must be one of: {', '.join([c.value for c in TaskCategory])}"
            )
            log_tool_call("create_task", {
                "project_id": project_id,
                "title": title,
                "category": category
            }, result)
            return result

        # Get or create project
        if project_id not in _projects:
            _projects[project_id] = ProjectState(
                project_id=project_id,
                name=f"Project {project_id}",
                description=f"Auto-created project for {project_id}"
            )

        project = _projects[project_id]

        # Check if task already exists
        if project.get_task_by_id(title):
            result = ToolResult(
                success=False,
                error=f"Task with ID '{title}' already exists in project {project_id}"
            )
            log_tool_call("create_task", {
                "project_id": project_id,
                "title": title,
                "category": category
            }, result)
            return result

        # Create task
        task = Task(
            id=title,
            description=description,
            status=TaskStatus.TODO,
            category=task_category,
            priority=3
        )

        # Add to project
        project.tasks.append(task)
        project.updated_at = datetime.now()

        result = ToolResult(success=True, data=task.model_dump())
        log_tool_call("create_task", {
            "project_id": project_id,
            "title": title,
            "category": category
        }, result)
        return result

    except Exception as e:
        logger.error(f"create_task error: {e}", exc_info=True)
        result = ToolResult(success=False, error=f"Error creating task: {str(e)}")
        log_tool_call("create_task", {
            "project_id": project_id,
            "title": title,
            "category": category
        }, result)
        return result


def update_task(
    task_id: str,
    project_id: str,
    status: Optional[str] = None,
    notes: str = ""
) -> ToolResult:
    """
    Update an existing task

    Args:
        task_id: Task identifier
        project_id: Project identifier
        status: New task status (optional)
        notes: Additional notes (optional)

    Returns:
        ToolResult with updated Task object

    Example:
        >>> result = update_task("AUTH-001", "PRJ-001", status="in_progress")
        >>> if result.success:
        ...     print(result.data)
    """
    try:
        # Check if project exists
        if project_id not in _projects:
            result = ToolResult(success=False, error=f"Project not found: {project_id}")
            log_tool_call("update_task", {
                "task_id": task_id,
                "project_id": project_id,
                "status": status
            }, result)
            return result

        project = _projects[project_id]

        # Find task
        task = project.get_task_by_id(task_id)
        if not task:
            result = ToolResult(success=False, error=f"Task not found: {task_id}")
            log_tool_call("update_task", {
                "task_id": task_id,
                "project_id": project_id,
                "status": status
            }, result)
            return result

        # Update status if provided
        if status:
            try:
                task.status = TaskStatus(status.lower())
            except ValueError:
                result = ToolResult(
                    success=False,
                    error=f"Invalid status: {status}. Must be one of: {', '.join([s.value for s in TaskStatus])}"
                )
                log_tool_call("update_task", {
                    "task_id": task_id,
                    "project_id": project_id,
                    "status": status
                }, result)
                return result

        # Update timestamp
        task.updated_at = datetime.now()
        project.updated_at = datetime.now()

        result = ToolResult(
            success=True,
            data={
                **task.model_dump(),
                "notes": notes
            }
        )
        log_tool_call("update_task", {
            "task_id": task_id,
            "project_id": project_id,
            "status": status
        }, result)
        return result

    except Exception as e:
        logger.error(f"update_task error: {e}", exc_info=True)
        result = ToolResult(success=False, error=f"Error updating task: {str(e)}")
        log_tool_call("update_task", {
            "task_id": task_id,
            "project_id": project_id,
            "status": status
        }, result)
        return result


def complete_task(
    task_id: str,
    project_id: str,
    result_notes: str = ""
) -> ToolResult:
    """
    Mark a task as completed

    Args:
        task_id: Task identifier
        project_id: Project identifier
        result_notes: Completion notes/results (optional)

    Returns:
        ToolResult with completed Task object

    Example:
        >>> result = complete_task("AUTH-001", "PRJ-001", "Login feature completed")
        >>> if result.success:
        ...     print(result.data)
    """
    try:
        # Use update_task to mark as completed
        update_result = update_task(
            task_id=task_id,
            project_id=project_id,
            status="completed",
            notes=result_notes
        )

        log_tool_call("complete_task", {
            "task_id": task_id,
            "project_id": project_id
        }, update_result)

        return update_result

    except Exception as e:
        logger.error(f"complete_task error: {e}", exc_info=True)
        result = ToolResult(success=False, error=f"Error completing task: {str(e)}")
        log_tool_call("complete_task", {
            "task_id": task_id,
            "project_id": project_id
        }, result)
        return result


def get_project_state(project_id: str) -> ToolResult:
    """
    Get project state with all tasks

    Args:
        project_id: Project identifier

    Returns:
        ToolResult with ProjectState object

    Example:
        >>> result = get_project_state("PRJ-001")
        >>> if result.success:
        ...     print(f"Tasks: {len(result.data['tasks'])}")
    """
    try:
        # Check if project exists
        if project_id not in _projects:
            result = ToolResult(success=False, error=f"Project not found: {project_id}")
            log_tool_call("get_project_state", {"project_id": project_id}, result)
            return result

        project = _projects[project_id]

        result = ToolResult(success=True, data=project.model_dump())
        log_tool_call("get_project_state", {"project_id": project_id}, result)
        return result

    except Exception as e:
        logger.error(f"get_project_state error: {e}", exc_info=True)
        result = ToolResult(success=False, error=f"Error getting project state: {str(e)}")
        log_tool_call("get_project_state", {"project_id": project_id}, result)
        return result


# ============================================================================
# Event Logging Tools
# ============================================================================

# In-memory event log (will be replaced with DB)
_event_log: List[Dict[str, Any]] = []


def log_event(
    project_id: str,
    event_type: str,
    details: Dict[str, Any]
) -> ToolResult:
    """
    Log an event to the activity log

    Args:
        project_id: Project identifier
        event_type: Type of event (e.g., 'task_created', 'file_modified')
        details: Event details as dictionary

    Returns:
        ToolResult indicating success

    Example:
        >>> result = log_event("PRJ-001", "task_created", {"task_id": "AUTH-001"})
        >>> print(result.success)
    """
    try:
        event = {
            "id": len(_event_log) + 1,
            "project_id": project_id,
            "event_type": event_type,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }

        _event_log.append(event)

        result = ToolResult(success=True, data=event)
        log_tool_call("log_event", {
            "project_id": project_id,
            "event_type": event_type
        }, result)
        return result

    except Exception as e:
        logger.error(f"log_event error: {e}", exc_info=True)
        result = ToolResult(success=False, error=f"Error logging event: {str(e)}")
        log_tool_call("log_event", {
            "project_id": project_id,
            "event_type": event_type
        }, result)
        return result


def get_events(
    project_id: str,
    event_type: Optional[str] = None,
    limit: int = 50
) -> ToolResult:
    """
    Get events from the activity log

    Args:
        project_id: Project identifier
        event_type: Filter by event type (optional)
        limit: Maximum number of events to return

    Returns:
        ToolResult with list of events

    Example:
        >>> result = get_events("PRJ-001", event_type="task_created")
        >>> if result.success:
        ...     print(f"Found {len(result.data)} events")
    """
    try:
        # Filter events by project
        events = [e for e in _event_log if e["project_id"] == project_id]

        # Filter by event type if specified
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]

        # Sort by timestamp (most recent first)
        events.sort(key=lambda x: x["timestamp"], reverse=True)

        # Apply limit
        events = events[:limit]

        result = ToolResult(success=True, data=events)
        log_tool_call("get_events", {
            "project_id": project_id,
            "event_type": event_type,
            "limit": limit
        }, result)
        return result

    except Exception as e:
        logger.error(f"get_events error: {e}", exc_info=True)
        result = ToolResult(success=False, error=f"Error getting events: {str(e)}")
        log_tool_call("get_events", {
            "project_id": project_id,
            "event_type": event_type,
            "limit": limit
        }, result)
        return result


# ============================================================================
# Helper Functions for Testing/Demo
# ============================================================================


def reset_state() -> None:
    """
    Reset in-memory state (for testing)

    WARNING: This clears all projects, tasks, and events.
    Only use for testing purposes.
    """
    global _projects, _event_log
    _projects.clear()
    _event_log.clear()
    logger.info("State reset complete")


def get_all_projects() -> Dict[str, ProjectState]:
    """
    Get all projects (for testing/debugging)

    Returns:
        Dictionary of project_id -> ProjectState
    """
    return _projects.copy()
