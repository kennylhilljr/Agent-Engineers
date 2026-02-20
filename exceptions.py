"""Custom Exception Hierarchy for Agent Dashboard.

This module defines a standardized exception hierarchy for all agent-related errors.
All exceptions inherit from AgentError as the base class, with specialized subclasses
for different error categories.

Exception Hierarchy:
    AgentError (base)
        ├── BridgeError (AI provider bridge errors)
        │     └── RateLimitError (rate limit exceeded)
        ├── SecurityError (authentication/authorization errors)
        ├── ConfigurationError (configuration-related errors)
        ├── TimeoutError (request timeout errors)
        └── AuthenticationError (authentication failure errors)

Helper Functions:
    is_retryable(exc): Returns True if the exception type is retryable
    get_error_code(exc): Returns the error_code attribute or None
    error_handler(reraise, log_fn): Context manager for structured exception handling

Usage:
    from exceptions import BridgeError, SecurityError, is_retryable, error_handler

    try:
        response = provider.chat(message)
    except BridgeError as e:
        if is_retryable(e):
            retry_later()
        logger.error(f"Provider error: {e.error_code}: {e}")
    except SecurityError as e:
        logger.error(f"Authentication failed: {e.error_code}: {e}")

    with error_handler(reraise=False) as ctx:
        risky_operation()
    if ctx.exception:
        handle_error(ctx.exception)
"""

import json
from contextlib import contextmanager
from typing import Any, Callable, Optional


class AgentError(Exception):
    """Base exception class for all agent-related errors.

    All exceptions in the Agent Dashboard should inherit from this class
    to enable unified error handling and recovery strategies.

    Attributes:
        error_code (str): Error code for categorizing the error
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
        return f"[{self.error_code}] {self.message}"

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON serialization.

        Includes __cause__ chain under the 'cause' key when present.

        Returns:
            Dictionary with error_code, error_type, message, and optionally cause
        """
        data = {
            "error_code": self.error_code,
            "error_type": self.__class__.__name__,
            "message": self.message,
        }
        if self.__cause__ is not None:
            cause = self.__cause__
            if isinstance(cause, AgentError):
                data["cause"] = cause.to_dict()
            else:
                data["cause"] = {
                    "error_type": type(cause).__name__,
                    "message": str(cause),
                }
        return data

    def to_json(self) -> str:
        """Serialize this exception to a JSON string.

        Returns:
            JSON string representation of to_dict()
        """
        return json.dumps(self.to_dict())


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


class RateLimitError(BridgeError):
    """Exception for rate limit errors from AI providers.

    Raised when an AI provider returns a rate limit response.
    This error is retryable after the retry_after duration.

    Attributes:
        retry_after: Seconds to wait before retrying (optional)
        provider: Name of the provider that rate-limited (optional)

    Error Codes:
        RATE_LIMIT_ERROR: General rate limit exceeded
    """

    def __init__(
        self,
        message: str,
        error_code: str = "RATE_LIMIT_ERROR",
        retry_after: Optional[float] = None,
        provider: str = None,
    ):
        """Initialize RateLimitError.

        Args:
            message: Human-readable error message
            error_code: Error code (default: RATE_LIMIT_ERROR)
            retry_after: Seconds before the client may retry (optional)
            provider: Name of the provider that rate-limited (optional)
        """
        super().__init__(message, error_code, provider=provider)
        self.retry_after = retry_after

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON serialization."""
        data = super().to_dict()
        if self.retry_after is not None:
            data["retry_after"] = self.retry_after
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
        details: dict = None,
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
        self.details = details if details is not None else {}

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON serialization."""
        data = super().to_dict()
        if self.auth_type:
            data["auth_type"] = self.auth_type
        if self.details:
            data["details"] = self.details
        return data


class ConfigurationError(AgentError):
    """Exception for configuration-related errors.

    Raised when the application configuration is invalid, incomplete,
    or missing required values.

    Error Codes:
        CONFIG_ERROR: General configuration error
        CONFIG_MISSING_KEY: Required configuration key is absent
        CONFIG_INVALID_VALUE: Configuration value is invalid
    """

    def __init__(
        self,
        message: str,
        error_code: str = "CONFIG_ERROR",
        config_key: str = None,
    ):
        """Initialize ConfigurationError.

        Args:
            message: Human-readable error message
            error_code: Error code (default: CONFIG_ERROR)
            config_key: The configuration key that caused the error (optional)
        """
        super().__init__(message, error_code)
        self.config_key = config_key

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON serialization."""
        data = super().to_dict()
        if self.config_key:
            data["config_key"] = self.config_key
        return data


class TimeoutError(AgentError):
    """Exception for request timeout errors.

    Raised when an operation exceeds its allotted time budget.
    This error is generally retryable.

    Error Codes:
        TIMEOUT_ERROR: General timeout
        TIMEOUT_PROVIDER: AI provider request timed out
        TIMEOUT_AGENT: Agent execution timed out
    """

    def __init__(
        self,
        message: str,
        error_code: str = "TIMEOUT_ERROR",
        timeout_seconds: Optional[float] = None,
    ):
        """Initialize TimeoutError.

        Args:
            message: Human-readable error message
            error_code: Error code (default: TIMEOUT_ERROR)
            timeout_seconds: The timeout threshold that was exceeded (optional)
        """
        super().__init__(message, error_code)
        self.timeout_seconds = timeout_seconds

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON serialization."""
        data = super().to_dict()
        if self.timeout_seconds is not None:
            data["timeout_seconds"] = self.timeout_seconds
        return data


class AuthenticationError(AgentError):
    """Exception for authentication failures.

    Raised when credentials are invalid, expired, or missing during
    user or service authentication (distinct from SecurityError which
    covers broader authorization concerns).

    Error Codes:
        AUTH_ERROR: General authentication error
        AUTH_INVALID_CREDENTIALS: Invalid username/password or API key
        AUTH_EXPIRED_TOKEN: Authentication token has expired
        AUTH_MISSING_CREDENTIALS: No credentials provided
    """

    def __init__(
        self,
        message: str,
        error_code: str = "AUTH_ERROR",
        username: str = None,
    ):
        """Initialize AuthenticationError.

        Args:
            message: Human-readable error message
            error_code: Error code (default: AUTH_ERROR)
            username: The username that failed authentication (optional)
        """
        super().__init__(message, error_code)
        self.username = username

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON serialization."""
        data = super().to_dict()
        if self.username:
            data["username"] = self.username
        return data


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

#: Bridge error codes that indicate the operation can be retried
_RETRYABLE_BRIDGE_CODES = frozenset({
    "BRIDGE_CONNECTION",
    "BRIDGE_RATE_LIMIT",
    "BRIDGE_TIMEOUT",
})


def is_retryable(exc: Any) -> bool:
    """Determine whether an exception is safe to retry.

    Args:
        exc: Any exception instance

    Returns:
        True if the exception type / code indicates a transient failure
        that may succeed on retry; False otherwise.
    """
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, BridgeError):
        return exc.error_code in _RETRYABLE_BRIDGE_CODES
    return False


def get_error_code(exc: Any) -> Optional[str]:
    """Return the error_code attribute of an AgentError, or None.

    Args:
        exc: Any exception instance

    Returns:
        The error_code string if exc is an AgentError subclass, else None.
    """
    if isinstance(exc, AgentError):
        return exc.error_code
    return None


# ---------------------------------------------------------------------------
# error_handler context manager
# ---------------------------------------------------------------------------

class _ErrorHandlerContext:
    """Holds the captured exception (if any) after error_handler exits."""

    def __init__(self):
        self.exception: Optional[AgentError] = None


@contextmanager
def error_handler(reraise: bool = True, log_fn: Optional[Callable] = None):
    """Context manager for structured AgentError handling.

    Captures AgentError (and subclasses) that occur in the managed block.
    Non-AgentError exceptions are always re-raised regardless of reraise.

    Args:
        reraise: If True (default), re-raise the caught AgentError after
                 logging. If False, suppress it and store in ctx.exception.
        log_fn:  Optional callable to receive the exception for logging,
                 called before the reraise decision is made.

    Yields:
        _ErrorHandlerContext: Object with an ``exception`` attribute that
        is populated if an AgentError is caught.

    Example:
        with error_handler(reraise=False) as ctx:
            risky_operation()
        if ctx.exception:
            print(ctx.exception.error_code)
    """
    ctx = _ErrorHandlerContext()
    try:
        yield ctx
    except AgentError as exc:
        ctx.exception = exc
        if log_fn is not None:
            log_fn(exc)
        if reraise:
            raise
    # Non-AgentError exceptions propagate unmodified
