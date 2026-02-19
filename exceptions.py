"""Custom Exception Hierarchy for Agent Dashboard.

This module defines a standardized exception hierarchy for all agent-related errors.
All exceptions inherit from AgentError as the base class, with specialized subclasses
for different error categories.

Exception Hierarchy:
    AgentError (base)
        ├── BridgeError (AI provider bridge errors)
        │     └── RateLimitError (rate limit exceeded — retryable)
        ├── SecurityError (authentication/authorization errors)
        │     └── AuthenticationError (credential failures)
        ├── ConfigurationError (invalid config/env vars)
        └── TimeoutError (operation timeouts — retryable)

Usage:
    from exceptions import BridgeError, SecurityError, error_handler, is_retryable

    try:
        response = provider.chat(message)
    except RateLimitError as e:
        time.sleep(e.retry_after or 60)
    except BridgeError as e:
        logger.error(f"Provider error: {e.error_code}: {e}")
    except SecurityError as e:
        logger.error(f"Authentication failed: {e.error_code}: {e}")
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional


class AgentError(Exception):
    """Base exception class for all agent-related errors.

    All exceptions in the Agent Dashboard should inherit from this class
    to enable unified error handling and recovery strategies.

    Attributes:
        error_code (str): Optional error code for categorizing the error
        message (str): Human-readable error message
    """

    def __init__(self, message: str, error_code: Optional[str] = None):
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

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON serialization.

        Includes __cause__ chain if present.

        Returns:
            Dictionary with error_code, error_type, message, and optional cause
        """
        d: dict[str, Any] = {
            "error_code": self.error_code,
            "error_type": self.__class__.__name__,
            "message": self.message,
        }
        # Include exception chain if present
        if self.__cause__ is not None:
            cause = self.__cause__
            if isinstance(cause, AgentError):
                d["cause"] = cause.to_dict()
            else:
                d["cause"] = {
                    "error_type": type(cause).__name__,
                    "message": str(cause),
                }
        return d

    def to_json(self) -> str:
        """Serialize exception to JSON string.

        Returns:
            JSON string representation of the exception
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

    def __init__(
        self,
        message: str,
        error_code: str = "BRIDGE_ERROR",
        provider: Optional[str] = None,
    ):
        """Initialize BridgeError.

        Args:
            message: Human-readable error message
            error_code: Error code for categorizing the bridge error
            provider: Name of the provider that failed (optional)
        """
        super().__init__(message, error_code)
        self.provider = provider

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        data = super().to_dict()
        if self.provider is not None:
            data["provider"] = self.provider
        return data


class RateLimitError(BridgeError):
    """Exception raised when an AI provider rate limit is exceeded.

    This is a retryable error — callers should honour the retry_after
    delay before retrying the request.

    Attributes:
        retry_after: Seconds to wait before retrying (may be None if unknown)
        provider: Name of the provider that rate-limited the request
    """

    def __init__(
        self,
        message: str,
        error_code: str = "RATE_LIMIT_ERROR",
        retry_after: Optional[float] = None,
        provider: Optional[str] = None,
    ):
        """Initialize RateLimitError.

        Args:
            message: Human-readable error message
            error_code: Error code (default: RATE_LIMIT_ERROR)
            retry_after: Seconds to wait before retrying
            provider: Name of the provider that rate-limited the request
        """
        super().__init__(message, error_code=error_code, provider=provider)
        self.retry_after = retry_after

    def to_dict(self) -> dict[str, Any]:
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
        SECURITY_ERROR: Generic security error
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
        auth_type: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
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

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        data = super().to_dict()
        if self.auth_type is not None:
            data["auth_type"] = self.auth_type
        if self.details:
            data["details"] = self.details
        return data


class AuthenticationError(AgentError):
    """Exception for credential/authentication failures.

    Raised when user credentials are invalid, missing, or expired.
    Differs from SecurityError in that it specifically refers to
    credential validation rather than broader authorization/policy checks.

    Error Codes:
        AUTH_ERROR: Generic authentication error
        AUTH_INVALID_CREDENTIALS: Username/password invalid
        AUTH_TOKEN_EXPIRED: Session/JWT token expired
        AUTH_MISSING_CREDENTIALS: No credentials provided
    """

    def __init__(
        self,
        message: str,
        error_code: str = "AUTH_ERROR",
        username: Optional[str] = None,
    ):
        """Initialize AuthenticationError.

        Args:
            message: Human-readable error message
            error_code: Error code (default: AUTH_ERROR)
            username: Username that failed authentication (optional, for logging)
        """
        super().__init__(message, error_code)
        self.username = username

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        data = super().to_dict()
        if self.username is not None:
            data["username"] = self.username
        return data


class ConfigurationError(AgentError):
    """Exception for invalid or missing configuration values.

    Raised when required environment variables are missing, configuration
    files are malformed, or configuration values fail validation.

    Error Codes:
        CONFIG_ERROR: Generic configuration error
        CONFIG_MISSING: Required configuration key is absent
        CONFIG_INVALID: Configuration value is invalid
        CONFIG_PARSE_ERROR: Configuration file could not be parsed
    """

    def __init__(
        self,
        message: str,
        error_code: str = "CONFIG_ERROR",
        config_key: Optional[str] = None,
    ):
        """Initialize ConfigurationError.

        Args:
            message: Human-readable error message
            error_code: Error code (default: CONFIG_ERROR)
            config_key: The configuration key that caused the error (optional)
        """
        super().__init__(message, error_code)
        self.config_key = config_key

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        data = super().to_dict()
        if self.config_key is not None:
            data["config_key"] = self.config_key
        return data


class TimeoutError(AgentError):
    """Exception for operation timeout errors.

    Raised when an operation (agent turn, API call, subprocess) exceeds
    its allotted time. This is a retryable error in most cases.

    Error Codes:
        TIMEOUT_ERROR: Generic timeout error
        TIMEOUT_AGENT_TURN: Agent turn timed out
        TIMEOUT_API_CALL: External API call timed out
        TIMEOUT_SUBPROCESS: Subprocess execution timed out
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
            timeout_seconds: The timeout duration that was exceeded
        """
        super().__init__(message, error_code)
        self.timeout_seconds = timeout_seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        data = super().to_dict()
        if self.timeout_seconds is not None:
            data["timeout_seconds"] = self.timeout_seconds
        return data


# ---------------------------------------------------------------------------
# Retryable error codes for BridgeError
# ---------------------------------------------------------------------------

_RETRYABLE_BRIDGE_CODES: frozenset[str] = frozenset(
    {"BRIDGE_CONNECTION", "BRIDGE_RATE_LIMIT", "BRIDGE_TIMEOUT"}
)


def is_retryable(exc: BaseException) -> bool:
    """Return True if the exception represents a transient, retryable error.

    Retryable errors:
    - RateLimitError (always retryable)
    - TimeoutError (always retryable)
    - BridgeError with error_code in BRIDGE_CONNECTION, BRIDGE_RATE_LIMIT, BRIDGE_TIMEOUT

    Non-retryable errors (permanent failures):
    - SecurityError, AuthenticationError, ConfigurationError
    - Generic AgentError
    - Non-AgentError exceptions

    Args:
        exc: The exception to check

    Returns:
        True if the error is retryable, False otherwise
    """
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, BridgeError):
        return exc.error_code in _RETRYABLE_BRIDGE_CODES
    return False


def get_error_code(exc: BaseException) -> Optional[str]:
    """Extract the error_code from an AgentError, or None for other exceptions.

    Args:
        exc: The exception to inspect

    Returns:
        The error_code string if exc is an AgentError, None otherwise
    """
    if isinstance(exc, AgentError):
        return exc.error_code
    return None


class _ErrorHandlerContext:
    """Context object yielded by error_handler to expose the caught exception."""

    def __init__(self) -> None:
        self.exception: Optional[AgentError] = None


@contextmanager
def error_handler(
    reraise: bool = True,
    log_fn: Optional[Callable[[AgentError], None]] = None,
) -> Generator[_ErrorHandlerContext, None, None]:
    """Context manager for unified AgentError handling.

    Catches AgentError (and subclasses) within the block. Non-AgentError
    exceptions are always propagated regardless of reraise setting.

    Args:
        reraise: If True (default), re-raise the caught AgentError after
                 optionally logging it. If False, suppress the error and
                 expose it via ctx.exception.
        log_fn: Optional callable to receive the caught AgentError (e.g.
                logger.error or a list's .append method). Called before
                the decision to reraise or suppress.

    Yields:
        _ErrorHandlerContext: context object with `exception` attribute set
        to the caught AgentError, or None if no error occurred.

    Example::

        with error_handler(reraise=False) as ctx:
            do_risky_thing()
        if ctx.exception:
            handle_gracefully(ctx.exception)
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
    # Non-AgentError exceptions propagate naturally — no except clause catches them
