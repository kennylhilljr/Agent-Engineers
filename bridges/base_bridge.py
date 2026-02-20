"""Base bridge abstract class for AI provider integrations."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class BridgeResponse:
    """Standard response from any bridge."""
    content: str
    model: str
    provider: str
    tokens_used: Optional[int] = None
    error: Optional[str] = None
    success: bool = True


class BaseBridge(ABC):
    """Abstract base class for all AI provider bridges.

    All bridge implementations must inherit from this class
    and implement the abstract methods.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the AI provider."""
        ...

    @abstractmethod
    async def send_task(self, task: str, **kwargs) -> BridgeResponse:
        """Send a task to the AI provider and return a response."""
        ...

    @abstractmethod
    def get_auth_info(self) -> dict[str, str]:
        """Return authentication information for this provider."""
        ...

    def create_session(self, **kwargs) -> Any:
        """Create and return a new session for the provider.

        Subclasses that support session-based interaction must override this
        method.  The default implementation raises NotImplementedError so that
        bridges which need it are reminded to implement it, without forcing
        every minimal test-only subclass to provide a stub.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement create_session()"
        )

    def validate_response(self, response: BridgeResponse) -> bool:
        """Validate a bridge response. Can be overridden."""
        return response.success and bool(response.content)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider_name})"
