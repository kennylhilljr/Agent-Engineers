"""Dashboard Configuration - Environment Variables Management (AI-111 / AI-175).

This module provides centralized configuration management for the dashboard server,
including port, host, WebSocket configuration, authentication, CORS settings, and
broadcast interval.

All environment variables are optional with sensible defaults for development.
Invalid values raise ValueError with clear messages.

Environment Variables:
    DASHBOARD_WEB_PORT (int): Port for the web dashboard server
        Default: 8080
        Valid: 1-65535

    DASHBOARD_HOST (str): Host to bind the dashboard server
        Default: 127.0.0.1
        Valid: Any valid hostname or IP address

    DASHBOARD_AUTH_TOKEN (str): Bearer token for dashboard API authentication
        Default: '' (authentication disabled)
        Valid: Any non-empty string

    DASHBOARD_CORS_ORIGINS (str): Allowed CORS origins
        Default: * (allow all origins)
        Valid: Comma-separated list or *
        Format: https://example.com,https://app.example.com or *

    DASHBOARD_BROADCAST_INTERVAL (int): WebSocket broadcast interval in seconds
        Default: 5
        Valid: 1-3600

Example Usage:
    from dashboard.config import get_config

    config = get_config()

    # Access configuration
    print(f"Server running on {config.host}:{config.port}")
    print(f"Auth required: {config.auth_required}")
    print(f"CORS origins: {config.cors_origins}")
    print(f"Broadcast interval: {config.broadcast_interval}s")
"""

import os
from typing import Optional, List

# Setup logging
import logging
logger = logging.getLogger(__name__)


class DashboardConfig:
    """Dashboard server configuration from environment variables.

    All values have sensible defaults and are validated.
    Invalid values raise ValueError with clear error messages.
    """

    def __init__(self):
        """Initialize configuration from environment variables."""
        self.host = self._parse_host('DASHBOARD_HOST', '127.0.0.1')
        self.port = self._parse_int('DASHBOARD_WEB_PORT', 8080, 1, 65535)
        self.auth_token = os.getenv('DASHBOARD_AUTH_TOKEN', '') or ''
        self.cors_origins = os.getenv('DASHBOARD_CORS_ORIGINS', '*')
        self.broadcast_interval = self._parse_int('DASHBOARD_BROADCAST_INTERVAL', 5, 1, 3600)

        # Log configuration
        self._log_config()

    @staticmethod
    def _parse_int(env_var: str, default: int, min_val: int, max_val: int) -> int:
        """Parse an integer from environment variable with range validation.

        Args:
            env_var: Environment variable name
            default: Default value if not set
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)

        Returns:
            Validated integer value

        Raises:
            ValueError: If the value cannot be parsed or is out of range
        """
        val = os.getenv(env_var)
        if val is None:
            return default
        try:
            parsed = int(val)
            if not (min_val <= parsed <= max_val):
                raise ValueError(
                    f"{env_var}={parsed} out of range [{min_val}, {max_val}]"
                )
            return parsed
        except ValueError as e:
            raise ValueError(f"Invalid {env_var}: {e}") from e

    @staticmethod
    def _parse_host(env_var: str, default: str) -> str:
        """Parse host from environment variable with basic validation.

        Args:
            env_var: Environment variable name
            default: Default host if not set or invalid

        Returns:
            Valid hostname or IP address
        """
        value = os.getenv(env_var)
        if value is None:
            return default

        # Basic validation — just check it's not empty after stripping
        if isinstance(value, str) and value.strip():
            return value.strip()
        else:
            logger.warning(
                f"Invalid {env_var}={value!r}. Using default {default}. "
                f"Host must be a non-empty string (hostname or IP address)."
            )
            return default

    @property
    def auth_required(self) -> bool:
        """Check if authentication is required.

        Returns:
            True if DASHBOARD_AUTH_TOKEN is set and non-empty, False otherwise
        """
        return bool(self.auth_token)

    # Alias for backwards compatibility with code that used auth_enabled
    @property
    def auth_enabled(self) -> bool:
        """Alias for auth_required (backwards compatibility)."""
        return self.auth_required

    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list.

        Returns:
            ['*'] for wildcard, or list of individual origin strings
        """
        if self.cors_origins == '*':
            return ['*']
        return [o.strip() for o in self.cors_origins.split(',') if o.strip()]

    # Alias for backwards compatibility
    def get_cors_origins_list(self) -> List[str]:
        """Alias for cors_origins_list() (backwards compatibility)."""
        return self.cors_origins_list()

    def _log_config(self):
        """Log configuration with security warnings where applicable."""
        logger.info("=" * 60)
        logger.info("Dashboard Configuration (AI-175 / REQ-TECH-010)")
        logger.info("=" * 60)
        logger.info(f"Host:               {self.host}")
        if self.host == "0.0.0.0":
            logger.warning(
                "SECURITY WARNING: Host is 0.0.0.0 (all interfaces). "
                "This exposes the server to your network. "
                "For production, use a reverse proxy with TLS/SSL or set DASHBOARD_HOST to 127.0.0.1."
            )
        logger.info(f"Port:               {self.port}")
        logger.info(f"Broadcast Interval: {self.broadcast_interval}s")
        if self.auth_required:
            logger.info("Auth:               ENABLED (bearer token required)")
        else:
            logger.info("Auth:               DISABLED (all endpoints open)")
        logger.info(f"CORS Origins:       {self.cors_origins}")
        if self.cors_origins == '*':
            logger.warning(
                "SECURITY WARNING: CORS is set to allow all origins (*). "
                "This is acceptable for development but NOT recommended for production. "
                "Set DASHBOARD_CORS_ORIGINS to specific domains for production."
            )
        logger.info("=" * 60)

    def validate(self) -> tuple:
        """Validate configuration for consistency.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check CORS origins format
        if self.cors_origins != '*':
            origins = self.cors_origins_list()
            if not origins:
                return False, (
                    f"Invalid DASHBOARD_CORS_ORIGINS={self.cors_origins}. "
                    f"Must be '*' or comma-separated list of URLs."
                )

        return True, None


# Global configuration singleton
_config: Optional[DashboardConfig] = None


def get_config() -> DashboardConfig:
    """Get the global dashboard configuration instance (singleton).

    Lazily initializes configuration on first call. Subsequent calls return
    the same instance. Use reset_config() to force re-initialization (e.g. in tests).

    Returns:
        DashboardConfig instance
    """
    global _config
    if _config is None:
        _config = DashboardConfig()
    return _config


def reset_config():
    """Reset the global configuration singleton (useful for testing)."""
    global _config
    _config = None
