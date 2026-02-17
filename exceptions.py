"""Custom Exception Hierarchy for Agent Dashboard.

This module defines a standardized exception hierarchy for all agent-related errors.
All exceptions inherit from AgentError as the base class, with specialized subclasses
for different error categories.

Exception Hierarchy:
    AgentError (base)
        ├── BridgeError (AI provider bridge errors)
        ├── SecurityError (authentication/authorization errors)
        └── [Future specialized exceptions]

Usage:
    from exceptions import BridgeError, SecurityError

    try:
        response = provider.chat(message)
    except BridgeError as e:
        logger.error(f"Provider error: {e.error_code}: {e}")
    except SecurityError as e:
        logger.error(f"Authentication failed: {e.error_code}: {e}")
"""


class AgentError(Exception):
    """Base exception class for all agent-related errors.

    All exceptions in the Agent Dashboard should inherit from this class
    to enable unified error handling and recovery strategies.

    Attributes:
        error_code (str): Optional error code for categorizing the error
        message (str): Human-readable error message
    """

    def __init__(self, message: str, error_code: str = None):
        """Initialize AgentError.

        Args:
            message: Human-readable error message
            error_code: Optional error code for categorizing the error
        """
        self.message = message
        self.error_code = error_code or "AGENT_ERROR"
        super().__init__(message)

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON serialization.

        Returns:
            Dictionary with error_code and message
        """
        return {
            "error_code": self.error_code,
            "error_type": self.__class__.__name__,
            "message": self.message
        }


class BridgeError(AgentError):
    """Exception for AI provider bridge errors.

    Raised when there are issues communicating with AI providers,
    including connection errors, API errors, and model-specific errors.

    Error Codes:
        BRIDGE_CONNECTION: Connection to provider failed
        BRIDGE_AUTH: Authentication with provider failed
        BRIDGE_MODEL_ERROR: Provider returned model/response error
        BRIDGE_RATE_LIMIT: Rate limit exceeded
        BRIDGE_TIMEOUT: Request timeout
        BRIDGE_INVALID_CONFIG: Invalid provider configuration
        BRIDGE_UNSUPPORTED_PROVIDER: Provider not supported
    """

    def __init__(self, message: str, error_code: str = "BRIDGE_ERROR", provider: str = None):
        """Initialize BridgeError.

        Args:
            message: Human-readable error message
            error_code: Error code for categorizing the bridge error
            provider: Name of the provider that failed (optional)
        """
        super().__init__(message, error_code)
        self.provider = provider

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON serialization."""
        data = super().to_dict()
        if self.provider:
            data["provider"] = self.provider
        return data


class SecurityError(AgentError):
    """Exception for authentication and security-related errors.

    Raised when there are authentication failures, authorization issues,
    or other security-related problems like invalid tokens or insufficient permissions.

    Error Codes:
        SECURITY_AUTH_FAILED: Authentication failed
        SECURITY_AUTH_MISSING: Missing authentication credentials
        SECURITY_TOKEN_INVALID: Invalid or expired token
        SECURITY_TOKEN_EXPIRED: Token has expired
        SECURITY_INSUFFICIENT_PERMISSIONS: User lacks required permissions
        SECURITY_INVALID_SIGNATURE: Invalid request signature
        SECURITY_INVALID_HEADER: Invalid security header format
    """

    def __init__(
        self,
        message: str,
        error_code: str = "SECURITY_ERROR",
        auth_type: str = None,
        details: dict = None
    ):
        """Initialize SecurityError.

        Args:
            message: Human-readable error message
            error_code: Error code for categorizing the security error
            auth_type: Type of authentication that failed (e.g., 'bearer_token', 'api_key')
            details: Additional error details as dictionary
        """
        super().__init__(message, error_code)
        self.auth_type = auth_type
        self.details = details or {}

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON serialization."""
        data = super().to_dict()
        if self.auth_type:
            data["auth_type"] = self.auth_type
        if self.details:
            data["details"] = self.details
        return data
