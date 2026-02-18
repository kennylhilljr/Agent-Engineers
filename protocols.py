"""typing.Protocol definitions for Agent-Engineers interfaces.

These protocols define structural subtyping contracts for core
components, enabling better type checking without tight coupling.
"""
from typing import Protocol, Optional, Any, runtime_checkable
from pathlib import Path


@runtime_checkable
class BridgeProtocol(Protocol):
    """Protocol for AI provider bridge implementations."""

    @property
    def provider_name(self) -> str:
        """Return the name of the AI provider."""
        ...

    async def send_task(self, task: str, **kwargs: Any) -> Any:
        """Send a task to the AI provider."""
        ...

    def get_auth_info(self) -> dict[str, str]:
        """Return authentication information."""
        ...


@runtime_checkable
class ConfigProtocol(Protocol):
    """Protocol for configuration objects."""

    def validate(self) -> list[str]:
        """Return list of validation errors."""
        ...

    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        ...


@runtime_checkable
class ProgressTrackerProtocol(Protocol):
    """Protocol for progress tracking implementations."""

    def load_project_state(self) -> dict[str, Any]:
        """Load the current project state."""
        ...


@runtime_checkable
class ExceptionProtocol(Protocol):
    """Protocol for structured exceptions."""

    @property
    def error_code(self) -> Optional[str]:
        """Return the error code."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception to dictionary."""
        ...
