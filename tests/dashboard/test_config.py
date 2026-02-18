"""Unit tests for Dashboard Configuration (AI-111).

Tests environment variable parsing, validation, and configuration fallback.
"""

import os
import pytest
from dashboard.config import DashboardConfig, get_config, reset_config


class TestDashboardConfigInit:
    """Test DashboardConfig initialization."""

    def setup_method(self):
        """Clean up environment before each test."""
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

    def test_defaults_no_env_vars(self):
        """Test that defaults are used when no env vars are set."""
        # Clean environment
        for key in ['DASHBOARD_WEB_PORT', 'DASHBOARD_WS_PORT', 'DASHBOARD_HOST',
                    'DASHBOARD_AUTH_TOKEN', 'DASHBOARD_CORS_ORIGINS']:
            os.environ.pop(key, None)

        config = DashboardConfig()

        assert config.web_port == 8420
        assert config.ws_port == 8421
        assert config.host == '0.0.0.0'
        assert config.auth_token is None
        assert config.cors_origins == '*'

    def test_web_port_from_env(self):
        """Test DASHBOARD_WEB_PORT environment variable."""
        os.environ['DASHBOARD_WEB_PORT'] = '9000'
        config = DashboardConfig()
        assert config.web_port == 9000

    def test_ws_port_from_env(self):
        """Test DASHBOARD_WS_PORT environment variable."""
        os.environ['DASHBOARD_WS_PORT'] = '9001'
        config = DashboardConfig()
        assert config.ws_port == 9001

    def test_host_from_env(self):
        """Test DASHBOARD_HOST environment variable."""
        os.environ['DASHBOARD_HOST'] = 'localhost'
        config = DashboardConfig()
        assert config.host == 'localhost'

    def test_host_127_0_0_1_from_env(self):
        """Test DASHBOARD_HOST set to 127.0.0.1."""
        os.environ['DASHBOARD_HOST'] = '127.0.0.1'
        config = DashboardConfig()
        assert config.host == '127.0.0.1'

    def test_auth_token_from_env(self):
        """Test DASHBOARD_AUTH_TOKEN environment variable."""
        os.environ['DASHBOARD_AUTH_TOKEN'] = 'secret-token-123'
        config = DashboardConfig()
        assert config.auth_token == 'secret-token-123'

    def test_cors_origins_from_env(self):
        """Test DASHBOARD_CORS_ORIGINS environment variable."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = 'https://example.com,https://app.example.com'
        config = DashboardConfig()
        assert config.cors_origins == 'https://example.com,https://app.example.com'

    def test_cors_origins_wildcard(self):
        """Test DASHBOARD_CORS_ORIGINS with wildcard."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = '*'
        config = DashboardConfig()
        assert config.cors_origins == '*'


class TestPortParsing:
    """Test port parsing and validation."""

    def setup_method(self):
        """Clean up environment before each test."""
        reset_config()

    def teardown_method(self):
        """Clean up after each test."""
        reset_config()

    def test_invalid_port_string(self):
        """Test invalid port string falls back to default."""
        os.environ['DASHBOARD_WEB_PORT'] = 'invalid'
        config = DashboardConfig()
        assert config.web_port == 8420  # default

    def test_invalid_port_negative(self):
        """Test negative port falls back to default."""
        os.environ['DASHBOARD_WEB_PORT'] = '-1'
        config = DashboardConfig()
        assert config.web_port == 8420  # default

    def test_invalid_port_too_high(self):
        """Test port above 65535 falls back to default."""
        os.environ['DASHBOARD_WEB_PORT'] = '70000'
        config = DashboardConfig()
        assert config.web_port == 8420  # default

    def test_valid_port_min(self):
        """Test minimum valid port."""
        os.environ['DASHBOARD_WEB_PORT'] = '1'
        config = DashboardConfig()
        assert config.web_port == 1

    def test_valid_port_max(self):
        """Test maximum valid port."""
        os.environ['DASHBOARD_WEB_PORT'] = '65535'
        config = DashboardConfig()
        assert config.web_port == 65535

    def test_valid_port_typical(self):
        """Test typical port values."""
        for port in [80, 443, 3000, 8000, 8080, 9000]:
            os.environ['DASHBOARD_WEB_PORT'] = str(port)
            config = DashboardConfig()
            assert config.web_port == port


class TestHostParsing:
    """Test host parsing and validation."""

    def setup_method(self):
        """Clean up environment before each test."""
        reset_config()

    def teardown_method(self):
        """Clean up after each test."""
        reset_config()

    def test_valid_host_localhost(self):
        """Test localhost as valid host."""
        os.environ['DASHBOARD_HOST'] = 'localhost'
        config = DashboardConfig()
        assert config.host == 'localhost'

    def test_valid_host_ip_address(self):
        """Test IP address as valid host."""
        os.environ['DASHBOARD_HOST'] = '192.168.1.1'
        config = DashboardConfig()
        assert config.host == '192.168.1.1'

    def test_valid_host_all_interfaces(self):
        """Test 0.0.0.0 as valid host."""
        os.environ['DASHBOARD_HOST'] = '0.0.0.0'
        config = DashboardConfig()
        assert config.host == '0.0.0.0'

    def test_valid_host_hostname(self):
        """Test hostname as valid host."""
        os.environ['DASHBOARD_HOST'] = 'example.com'
        config = DashboardConfig()
        assert config.host == 'example.com'

    def test_invalid_host_empty_string(self):
        """Test empty string host falls back to default."""
        os.environ['DASHBOARD_HOST'] = ''
        config = DashboardConfig()
        assert config.host == '0.0.0.0'  # default

    def test_host_whitespace_trimmed(self):
        """Test that whitespace is trimmed from host."""
        os.environ['DASHBOARD_HOST'] = '  localhost  '
        config = DashboardConfig()
        assert config.host == 'localhost'


class TestAuthToken:
    """Test authentication token handling."""

    def setup_method(self):
        """Clean up environment before each test."""
        reset_config()
        os.environ.pop('DASHBOARD_AUTH_TOKEN', None)

    def teardown_method(self):
        """Clean up after each test."""
        reset_config()

    def test_auth_disabled_by_default(self):
        """Test that auth is disabled by default."""
        config = DashboardConfig()
        assert config.auth_token is None
        assert config.auth_enabled is False

    def test_auth_enabled_when_token_set(self):
        """Test that auth is enabled when token is set."""
        os.environ['DASHBOARD_AUTH_TOKEN'] = 'test-token'
        config = DashboardConfig()
        assert config.auth_token == 'test-token'
        assert config.auth_enabled is True

    def test_auth_property_returns_boolean(self):
        """Test auth_enabled property returns boolean."""
        config = DashboardConfig()
        assert isinstance(config.auth_enabled, bool)
        assert config.auth_enabled is False

        os.environ['DASHBOARD_AUTH_TOKEN'] = 'token'
        config = DashboardConfig()
        assert config.auth_enabled is True


class TestCorsOrigins:
    """Test CORS origins parsing."""

    def setup_method(self):
        """Clean up environment before each test."""
        reset_config()
        os.environ['DASHBOARD_CORS_ORIGINS'] = '*'

    def teardown_method(self):
        """Clean up after each test."""
        reset_config()

    def test_cors_wildcard_default(self):
        """Test CORS defaults to wildcard."""
        os.environ.pop('DASHBOARD_CORS_ORIGINS', None)
        config = DashboardConfig()
        assert config.cors_origins == '*'

    def test_cors_wildcard_explicit(self):
        """Test explicit wildcard CORS."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = '*'
        config = DashboardConfig()
        assert config.cors_origins == '*'

    def test_cors_single_origin(self):
        """Test single CORS origin."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = 'https://example.com'
        config = DashboardConfig()
        assert config.cors_origins == 'https://example.com'

    def test_cors_multiple_origins(self):
        """Test multiple CORS origins."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = 'https://example.com,https://app.example.com'
        config = DashboardConfig()
        assert config.cors_origins == 'https://example.com,https://app.example.com'

    def test_get_cors_origins_list_wildcard(self):
        """Test get_cors_origins_list with wildcard."""
        config = DashboardConfig()
        assert config.get_cors_origins_list() == ['*']

    def test_get_cors_origins_list_single(self):
        """Test get_cors_origins_list with single origin."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = 'https://example.com'
        config = DashboardConfig()
        assert config.get_cors_origins_list() == ['https://example.com']

    def test_get_cors_origins_list_multiple(self):
        """Test get_cors_origins_list with multiple origins."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = 'https://example.com,https://app.example.com'
        config = DashboardConfig()
        origins = config.get_cors_origins_list()
        assert len(origins) == 2
        assert 'https://example.com' in origins
        assert 'https://app.example.com' in origins

    def test_get_cors_origins_list_trims_whitespace(self):
        """Test that whitespace is trimmed from origins."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = ' https://example.com , https://app.example.com '
        config = DashboardConfig()
        origins = config.get_cors_origins_list()
        assert origins == ['https://example.com', 'https://app.example.com']


class TestConfigValidation:
    """Test configuration validation."""

    def setup_method(self):
        """Clean up environment before each test."""
        reset_config()

    def teardown_method(self):
        """Clean up after each test."""
        reset_config()

    def test_validate_default_config(self):
        """Test validation of default configuration."""
        config = DashboardConfig()
        is_valid, error = config.validate()
        assert is_valid is True
        assert error is None

    def test_validate_port_conflict(self):
        """Test validation catches port conflicts."""
        os.environ['DASHBOARD_WEB_PORT'] = '8420'
        os.environ['DASHBOARD_WS_PORT'] = '8420'
        config = DashboardConfig()
        is_valid, error = config.validate()
        assert is_valid is False
        assert 'cannot be the same' in error

    def test_validate_different_ports(self):
        """Test validation passes with different ports."""
        os.environ['DASHBOARD_WEB_PORT'] = '8420'
        os.environ['DASHBOARD_WS_PORT'] = '8421'
        config = DashboardConfig()
        is_valid, error = config.validate()
        assert is_valid is True

    def test_validate_invalid_cors(self):
        """Test validation catches invalid CORS format."""
        os.environ['DASHBOARD_CORS_ORIGINS'] = ',,,'  # Only commas
        config = DashboardConfig()
        is_valid, error = config.validate()
        assert is_valid is False


class TestGlobalConfigInstance:
    """Test global configuration singleton."""

    def setup_method(self):
        """Clean up before each test."""
        reset_config()

    def teardown_method(self):
        """Clean up after each test."""
        reset_config()

    def test_get_config_returns_instance(self):
        """Test get_config returns DashboardConfig instance."""
        config = get_config()
        assert isinstance(config, DashboardConfig)

    def test_get_config_singleton(self):
        """Test get_config returns same instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reset_config(self):
        """Test reset_config creates new instance."""
        config1 = get_config()
        reset_config()
        config2 = get_config()
        assert config1 is not config2

    def test_get_config_with_env_vars(self):
        """Test get_config loads environment variables."""
        os.environ['DASHBOARD_WEB_PORT'] = '9000'
        config = get_config()
        assert config.web_port == 9000


class TestCompleteConfiguration:
    """Integration tests with multiple environment variables."""

    def setup_method(self):
        """Clean up before each test."""
        reset_config()
        # Clean all dashboard env vars
        for key in ['DASHBOARD_WEB_PORT', 'DASHBOARD_WS_PORT', 'DASHBOARD_HOST',
                    'DASHBOARD_AUTH_TOKEN', 'DASHBOARD_CORS_ORIGINS']:
            os.environ.pop(key, None)

    def teardown_method(self):
        """Clean up after each test."""
        reset_config()

    def test_all_env_vars_set(self):
        """Test configuration with all environment variables set."""
        os.environ['DASHBOARD_WEB_PORT'] = '9000'
        os.environ['DASHBOARD_WS_PORT'] = '9001'
        os.environ['DASHBOARD_HOST'] = 'localhost'
        os.environ['DASHBOARD_AUTH_TOKEN'] = 'secret-token'
        os.environ['DASHBOARD_CORS_ORIGINS'] = 'https://example.com'

        config = DashboardConfig()

        assert config.web_port == 9000
        assert config.ws_port == 9001
        assert config.host == 'localhost'
        assert config.auth_token == 'secret-token'
        assert config.auth_enabled is True
        assert config.cors_origins == 'https://example.com'

    def test_partial_env_vars_set(self):
        """Test configuration with only some environment variables set."""
        os.environ['DASHBOARD_WEB_PORT'] = '9000'
        os.environ['DASHBOARD_AUTH_TOKEN'] = 'token'

        config = DashboardConfig()

        assert config.web_port == 9000
        assert config.ws_port == 8421  # default
        assert config.host == '0.0.0.0'  # default
        assert config.auth_token == 'token'
        assert config.cors_origins == '*'  # default

    def test_mixed_valid_invalid_env_vars(self):
        """Test configuration with mix of valid and invalid values."""
        os.environ['DASHBOARD_WEB_PORT'] = '9000'  # valid
        os.environ['DASHBOARD_WS_PORT'] = 'invalid'  # invalid
        os.environ['DASHBOARD_HOST'] = 'localhost'  # valid

        config = DashboardConfig()

        assert config.web_port == 9000  # from env
        assert config.ws_port == 8421  # default (invalid value ignored)
        assert config.host == 'localhost'  # from env
