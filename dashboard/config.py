"""Dashboard Configuration - Environment Variables Management (AI-111).

This module provides centralized configuration management for the dashboard server,
including port, host, WebSocket configuration, authentication, and CORS settings.

All environment variables are optional with sensible defaults for development.
Invalid values are handled gracefully with fallback to defaults.

Environment Variables:
    DASHBOARD_WEB_PORT (int): Port for the web dashboard server
        Default: 8420
        Valid: 1-65535

    DASHBOARD_WS_PORT (int): Port for WebSocket connections
        Default: 8421
        Valid: 1-65535

    DASHBOARD_HOST (str): Host to bind the dashboard server
        Default: 0.0.0.0 (all interfaces)
        Valid: Any valid hostname or IP address

    DASHBOARD_AUTH_TOKEN (str): Bearer token for dashboard API authentication
        Default: None (authentication disabled)
        Valid: Any non-empty string

    DASHBOARD_CORS_ORIGINS (str): Allowed CORS origins
        Default: * (allow all origins)
        Valid: Comma-separated list or *
        Format: https://example.com,https://app.example.com or *

Example Usage:
    from dashboard.config import DashboardConfig

    config = DashboardConfig()

    # Access configuration
    print(f"Server running on {config.host}:{config.web_port}")
    print(f"WebSocket on {config.host}:{config.ws_port}")
    print(f"Auth enabled: {config.auth_enabled}")
    print(f"CORS origins: {config.cors_origins}")
"""

import os
import sys
from typing import Optional, List
from dataclasses import dataclass

# Setup logging
import logging
logger = logging.getLogger(__name__)


@dataclass
class DashboardConfig:
    """Dashboard server configuration from environment variables.

    All values have sensible defaults and are validated.
    Invalid values fall back to defaults with warning logs.
    """

    web_port: int
    ws_port: int
    host: str
    auth_token: Optional[str]
    cors_origins: str

    def __init__(self):
        """Initialize configuration from environment variables."""
        self.web_port = self._parse_port('DASHBOARD_WEB_PORT', 8420)
        self.ws_port = self._parse_port('DASHBOARD_WS_PORT', 8421)
        self.host = self._parse_host('DASHBOARD_HOST', '0.0.0.0')
        self.auth_token = os.getenv('DASHBOARD_AUTH_TOKEN')
        self.cors_origins = os.getenv('DASHBOARD_CORS_ORIGINS', '*')

        # Log configuration
        self._log_config()

    @staticmethod
    def _parse_port(env_var: str, default: int) -> int:
        """Parse port from environment variable with validation.

        Args:
            env_var: Environment variable name
            default: Default port if not set or invalid

        Returns:
            Valid port number (1-65535) or default
        """
        value = os.getenv(env_var)
        if value is None:
            logger.debug(f"{env_var} not set, using default: {default}")
            return default

        try:
            port = int(value)
            if port < 1 or port > 65535:
                raise ValueError(f"Port must be 1-65535, got {port}")
            logger.debug(f"{env_var}={port}")
            return port
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Invalid {env_var}={value}: {e}. Using default {default}. "
                f"Port must be an integer between 1 and 65535."
            )
            return default

    @staticmethod
    def _parse_host(env_var: str, default: str) -> str:
        """Parse host from environment variable with validation.

        Args:
            env_var: Environment variable name
            default: Default host if not set or invalid

        Returns:
            Valid hostname or IP address
        """
        value = os.getenv(env_var)
        if value is None:
            logger.debug(f"{env_var} not set, using default: {default}")
            return default

        # Basic validation - just check it's not empty
        if isinstance(value, str) and value.strip():
            logger.debug(f"{env_var}={value}")
            return value.strip()
        else:
            logger.warning(
                f"Invalid {env_var}={value}. Using default {default}. "
                f"Host must be a non-empty string (hostname or IP address)."
            )
            return default

    @property
    def auth_enabled(self) -> bool:
        """Check if authentication is enabled.

        Returns:
            True if DASHBOARD_AUTH_TOKEN is set, False otherwise
        """
        return self.auth_token is not None and len(self.auth_token) > 0

    def get_cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list.

        Returns:
            List of allowed origins or ['*'] for wildcard
        """
        if self.cors_origins == '*':
            return ['*']
        return [o.strip() for o in self.cors_origins.split(',') if o.strip()]

    def _log_config(self):
        """Log configuration with security warnings where applicable."""
        logger.info("=" * 60)
        logger.info("Dashboard Configuration (AI-111)")
        logger.info("=" * 60)

        # Web port
        logger.info(f"Web Port:      {self.web_port}")

        # WebSocket port
        logger.info(f"WebSocket Port: {self.ws_port}")

        # Host with security warning if needed
        logger.info(f"Host:          {self.host}")
        if self.host == "0.0.0.0":
            logger.warning(
                "SECURITY WARNING: Host is 0.0.0.0 (all interfaces). "
                "This exposes the server to your network. "
                "For production, use a reverse proxy with TLS/SSL or set host to 127.0.0.1."
            )

        # Auth
        if self.auth_enabled:
            logger.info("Auth:          ENABLED (bearer token required)")
        else:
            logger.info("Auth:          DISABLED (all endpoints open)")

        # CORS with security warning if needed
        logger.info(f"CORS Origins:  {self.cors_origins}")
        if self.cors_origins == '*':
            logger.warning(
                "SECURITY WARNING: CORS is set to allow all origins (*). "
                "This is acceptable for development but NOT recommended for production. "
                "Set DASHBOARD_CORS_ORIGINS to specific domains for production."
            )

        logger.info("=" * 60)

    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate configuration for consistency.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for port conflicts
        if self.web_port == self.ws_port:
            return False, (
                f"DASHBOARD_WEB_PORT ({self.web_port}) and "
                f"DASHBOARD_WS_PORT ({self.ws_port}) cannot be the same"
            )

        # Check CORS origins format
        if self.cors_origins != '*':
            origins = self.get_cors_origins_list()
            if not origins:
                return False, (
                    f"Invalid DASHBOARD_CORS_ORIGINS={self.cors_origins}. "
                    f"Must be '*' or comma-separated list of URLs."
                )

        return True, None


# Global configuration instance
_config: Optional[DashboardConfig] = None


def get_config() -> DashboardConfig:
    """Get the global dashboard configuration instance.

    Lazily initializes configuration on first call.

    Returns:
        DashboardConfig instance
    """
    global _config
    if _config is None:
        _config = DashboardConfig()
    return _config


def reset_config():
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
