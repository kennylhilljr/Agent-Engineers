"""Integration tests for Dashboard Configuration with server startup (AI-111).

These tests verify that environment variables are correctly applied when starting
the dashboard server.
"""

import os
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add dashboard to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.config import DashboardConfig, reset_config
from dashboard.server import DashboardServer


class TestServerWithConfig:
    """Test DashboardServer initialization with configuration."""

    def setup_method(self):
        """Clean up before each test."""
        reset_config()
        # Store original env vars
        self.original_env = {}
        for key in ['DASHBOARD_WEB_PORT', 'DASHBOARD_WS_PORT', 'DASHBOARD_HOST',
                    'DASHBOARD_AUTH_TOKEN', 'DASHBOARD_CORS_ORIGINS']:
            self.original_env[key] = os.environ.get(key)

    def teardown_method(self):
        """Restore original environment."""
        reset_config()
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_server_uses_default_port(self):
        """Test server uses default port 8420 from config."""
        # Clean environment
        for key in ['DASHBOARD_WEB_PORT', 'DASHBOARD_WS_PORT', 'DASHBOARD_HOST',
                    'DASHBOARD_AUTH_TOKEN', 'DASHBOARD_CORS_ORIGINS']:
            os.environ.pop(key, None)

        server = DashboardServer(use_config=True)
        assert server.port == 8420

    def test_server_uses_custom_port_from_env(self):
        """Test server uses custom port from DASHBOARD_WEB_PORT."""
        os.environ['DASHBOARD_WEB_PORT'] = '9000'

        # Reset to pick up new env var
        reset_config()

        server = DashboardServer(use_config=True)
        assert server.port == 9000

    def test_server_uses_default_host(self):
        """Test server uses default host 0.0.0.0 from config."""
        # Clean environment
        for key in ['DASHBOARD_WEB_PORT', 'DASHBOARD_WS_PORT', 'DASHBOARD_HOST',
                    'DASHBOARD_AUTH_TOKEN', 'DASHBOARD_CORS_ORIGINS']:
            os.environ.pop(key, None)

        server = DashboardServer(use_config=True)
        assert server.host == '0.0.0.0'

    def test_server_uses_custom_host_from_env(self):
        """Test server uses custom host from DASHBOARD_HOST."""
        os.environ['DASHBOARD_HOST'] = 'localhost'

        # Reset to pick up new env var
        reset_config()

        server = DashboardServer(use_config=True)
        assert server.host == 'localhost'

    def test_server_port_overrides_env(self):
        """Test that port parameter overrides environment variable."""
        os.environ['DASHBOARD_WEB_PORT'] = '9000'
        reset_config()

        server = DashboardServer(use_config=True, port=9999)
        assert server.port == 9999

    def test_server_host_overrides_env(self):
        """Test that host parameter overrides environment variable."""
        os.environ['DASHBOARD_HOST'] = 'localhost'
        reset_config()

        server = DashboardServer(use_config=True, host='0.0.0.0')
        assert server.host == '0.0.0.0'

    def test_server_stores_config(self):
        """Test that server stores the configuration object."""
        server = DashboardServer(use_config=True)
        assert server.config is not None
        assert isinstance(server.config, DashboardConfig)

    def test_server_legacy_mode_no_config(self):
        """Test server in legacy mode without config loading."""
        os.environ['DASHBOARD_WEB_PORT'] = '9000'

        server = DashboardServer(use_config=False, port=8080, host='127.0.0.1')
        assert server.port == 8080
        assert server.host == '127.0.0.1'
        assert server.config is None

    def test_server_validates_config_on_init(self):
        """Test that server validates configuration on initialization."""
        os.environ['DASHBOARD_WEB_PORT'] = '8420'
        os.environ['DASHBOARD_WS_PORT'] = '8420'  # Same port - conflict
        reset_config()

        with pytest.raises(ValueError) as exc_info:
            DashboardServer(use_config=True)

        assert 'cannot be the same' in str(exc_info.value)


class TestConfigurationFallbacks:
    """Test that configuration gracefully falls back to defaults."""

    def setup_method(self):
        """Clean up before each test."""
        reset_config()
        # Store original env vars
        self.original_env = {}
        for key in ['DASHBOARD_WEB_PORT', 'DASHBOARD_WS_PORT', 'DASHBOARD_HOST',
                    'DASHBOARD_AUTH_TOKEN', 'DASHBOARD_CORS_ORIGINS']:
            self.original_env[key] = os.environ.get(key)

    def teardown_method(self):
        """Restore original environment."""
        reset_config()
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_invalid_port_falls_back_to_default(self):
        """Test that invalid port falls back to default."""
        os.environ['DASHBOARD_WEB_PORT'] = 'invalid'
        config = DashboardConfig()
        assert config.web_port == 8420

    def test_invalid_host_falls_back_to_default(self):
        """Test that invalid host falls back to default."""
        os.environ['DASHBOARD_HOST'] = ''
        config = DashboardConfig()
        assert config.host == '0.0.0.0'

    def test_invalid_port_range_falls_back_to_default(self):
        """Test that port out of range falls back to default."""
        os.environ['DASHBOARD_WEB_PORT'] = '99999'
        config = DashboardConfig()
        assert config.web_port == 8420

    def test_auth_token_optional(self):
        """Test that auth token is optional."""
        os.environ.pop('DASHBOARD_AUTH_TOKEN', None)
        config = DashboardConfig()
        assert config.auth_token is None
        assert config.auth_enabled is False

    def test_cors_origins_optional(self):
        """Test that CORS origins are optional."""
        os.environ.pop('DASHBOARD_CORS_ORIGINS', None)
        config = DashboardConfig()
        assert config.cors_origins == '*'


class TestConfigurationValidation:
    """Test configuration validation."""

    def setup_method(self):
        """Clean up before each test."""
        reset_config()
        # Store original env vars
        self.original_env = {}
        for key in ['DASHBOARD_WEB_PORT', 'DASHBOARD_WS_PORT', 'DASHBOARD_HOST',
                    'DASHBOARD_AUTH_TOKEN', 'DASHBOARD_CORS_ORIGINS']:
            self.original_env[key] = os.environ.get(key)

    def teardown_method(self):
        """Restore original environment."""
        reset_config()
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_port_conflict_detected(self):
        """Test that port conflict is detected."""
        os.environ['DASHBOARD_WEB_PORT'] = '8000'
        os.environ['DASHBOARD_WS_PORT'] = '8000'
        config = DashboardConfig()

        is_valid, error = config.validate()
        assert is_valid is False
        assert 'cannot be the same' in error

    def test_valid_config_passes_validation(self):
        """Test that valid config passes validation."""
        os.environ['DASHBOARD_WEB_PORT'] = '8420'
        os.environ['DASHBOARD_WS_PORT'] = '8421'
        config = DashboardConfig()

        is_valid, error = config.validate()
        assert is_valid is True
        assert error is None

    def test_cors_validation_wildcard(self):
        """Test that wildcard CORS passes validation."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = '*'
        config = DashboardConfig()

        is_valid, error = config.validate()
        assert is_valid is True

    def test_cors_validation_single_origin(self):
        """Test that single CORS origin passes validation."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = 'https://example.com'
        config = DashboardConfig()

        is_valid, error = config.validate()
        assert is_valid is True

    def test_cors_validation_multiple_origins(self):
        """Test that multiple CORS origins pass validation."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = 'https://example.com,https://app.example.com'
        config = DashboardConfig()

        is_valid, error = config.validate()
        assert is_valid is True


class TestConfigurationProperties:
    """Test configuration properties and methods."""

    def setup_method(self):
        """Clean up before each test."""
        reset_config()
        # Store original env vars
        self.original_env = {}
        for key in ['DASHBOARD_WEB_PORT', 'DASHBOARD_WS_PORT', 'DASHBOARD_HOST',
                    'DASHBOARD_AUTH_TOKEN', 'DASHBOARD_CORS_ORIGINS']:
            self.original_env[key] = os.environ.get(key)

    def teardown_method(self):
        """Restore original environment."""
        reset_config()
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_auth_enabled_property(self):
        """Test auth_enabled property."""
        # No token - disabled
        os.environ.pop('DASHBOARD_AUTH_TOKEN', None)
        config = DashboardConfig()
        assert config.auth_enabled is False

        # With token - enabled
        reset_config()
        os.environ['DASHBOARD_AUTH_TOKEN'] = 'token'
        config = DashboardConfig()
        assert config.auth_enabled is True

    def test_get_cors_origins_list_wildcard(self):
        """Test get_cors_origins_list with wildcard."""
        config = DashboardConfig()
        origins = config.get_cors_origins_list()
        assert origins == ['*']

    def test_get_cors_origins_list_single(self):
        """Test get_cors_origins_list with single origin."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = 'https://example.com'
        config = DashboardConfig()
        origins = config.get_cors_origins_list()
        assert origins == ['https://example.com']

    def test_get_cors_origins_list_multiple(self):
        """Test get_cors_origins_list with multiple origins."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = 'https://example.com,https://app.example.com'
        config = DashboardConfig()
        origins = config.get_cors_origins_list()
        assert len(origins) == 2
        assert 'https://example.com' in origins
        assert 'https://app.example.com' in origins

    def test_get_cors_origins_list_trims_whitespace(self):
        """Test that whitespace is trimmed."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = ' https://example.com , https://app.example.com '
        config = DashboardConfig()
        origins = config.get_cors_origins_list()
        assert origins == ['https://example.com', 'https://app.example.com']
