"""Tests for dashboard/config.py — AI-175 (REQ-TECH-010).

Covers:
- Default values when no env vars set
- Each env var override works
- Port validation (0 → error, 65536 → error, 8080 → OK, "abc" → error)
- Interval validation (0 → error, 3600 → OK, 3601 → error, "xyz" → error)
- auth_required True/False based on DASHBOARD_AUTH_TOKEN
- cors_origins_list() with *, single origin, multiple origins
- get_config() singleton behaviour
- reset_config() resets singleton
- auth_enabled alias
- get_cors_origins_list() alias
- validate() method
"""
import os
import pytest
from unittest.mock import patch

from dashboard.config import DashboardConfig, get_config, reset_config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_env_and_singleton(monkeypatch):
    """Remove all DASHBOARD_* env vars and reset singleton before every test."""
    for var in [
        'DASHBOARD_HOST',
        'DASHBOARD_WEB_PORT',
        'DASHBOARD_AUTH_TOKEN',
        'DASHBOARD_CORS_ORIGINS',
        'DASHBOARD_BROADCAST_INTERVAL',
    ]:
        monkeypatch.delenv(var, raising=False)
    reset_config()
    yield
    reset_config()


# ---------------------------------------------------------------------------
# 1. Default values
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_default_host(self):
        """DASHBOARD_HOST defaults to 127.0.0.1."""
        cfg = DashboardConfig()
        assert cfg.host == '127.0.0.1'

    def test_default_port(self):
        """DASHBOARD_WEB_PORT defaults to 8080."""
        cfg = DashboardConfig()
        assert cfg.port == 8080

    def test_default_auth_token_empty(self):
        """DASHBOARD_AUTH_TOKEN defaults to empty string."""
        cfg = DashboardConfig()
        assert cfg.auth_token == ''

    def test_default_cors_origins(self):
        """DASHBOARD_CORS_ORIGINS defaults to '*'."""
        cfg = DashboardConfig()
        assert cfg.cors_origins == '*'

    def test_default_broadcast_interval(self):
        """DASHBOARD_BROADCAST_INTERVAL defaults to 5."""
        cfg = DashboardConfig()
        assert cfg.broadcast_interval == 5


# ---------------------------------------------------------------------------
# 2. Env var overrides
# ---------------------------------------------------------------------------

class TestEnvVarOverrides:
    def test_host_override(self, monkeypatch):
        """DASHBOARD_HOST env var is used."""
        monkeypatch.setenv('DASHBOARD_HOST', '0.0.0.0')
        cfg = DashboardConfig()
        assert cfg.host == '0.0.0.0'

    def test_port_override(self, monkeypatch):
        """DASHBOARD_WEB_PORT env var is used."""
        monkeypatch.setenv('DASHBOARD_WEB_PORT', '9090')
        cfg = DashboardConfig()
        assert cfg.port == 9090

    def test_auth_token_override(self, monkeypatch):
        """DASHBOARD_AUTH_TOKEN env var is used."""
        monkeypatch.setenv('DASHBOARD_AUTH_TOKEN', 'secret-token-123')
        cfg = DashboardConfig()
        assert cfg.auth_token == 'secret-token-123'

    def test_cors_origins_override(self, monkeypatch):
        """DASHBOARD_CORS_ORIGINS env var is used."""
        monkeypatch.setenv('DASHBOARD_CORS_ORIGINS', 'https://example.com')
        cfg = DashboardConfig()
        assert cfg.cors_origins == 'https://example.com'

    def test_broadcast_interval_override(self, monkeypatch):
        """DASHBOARD_BROADCAST_INTERVAL env var is used."""
        monkeypatch.setenv('DASHBOARD_BROADCAST_INTERVAL', '30')
        cfg = DashboardConfig()
        assert cfg.broadcast_interval == 30


# ---------------------------------------------------------------------------
# 3. Port validation
# ---------------------------------------------------------------------------

class TestPortValidation:
    def test_port_zero_raises(self, monkeypatch):
        """Port 0 is out of range and raises ValueError."""
        monkeypatch.setenv('DASHBOARD_WEB_PORT', '0')
        with pytest.raises(ValueError, match='DASHBOARD_WEB_PORT'):
            DashboardConfig()

    def test_port_negative_raises(self, monkeypatch):
        """Negative port raises ValueError."""
        monkeypatch.setenv('DASHBOARD_WEB_PORT', '-1')
        with pytest.raises(ValueError, match='DASHBOARD_WEB_PORT'):
            DashboardConfig()

    def test_port_65536_raises(self, monkeypatch):
        """Port 65536 exceeds maximum and raises ValueError."""
        monkeypatch.setenv('DASHBOARD_WEB_PORT', '65536')
        with pytest.raises(ValueError, match='DASHBOARD_WEB_PORT'):
            DashboardConfig()

    def test_port_non_integer_raises(self, monkeypatch):
        """Non-integer port string raises ValueError."""
        monkeypatch.setenv('DASHBOARD_WEB_PORT', 'abc')
        with pytest.raises(ValueError, match='DASHBOARD_WEB_PORT'):
            DashboardConfig()

    def test_port_8080_valid(self, monkeypatch):
        """Port 8080 is valid."""
        monkeypatch.setenv('DASHBOARD_WEB_PORT', '8080')
        cfg = DashboardConfig()
        assert cfg.port == 8080

    def test_port_1_valid(self, monkeypatch):
        """Minimum port (1) is valid."""
        monkeypatch.setenv('DASHBOARD_WEB_PORT', '1')
        cfg = DashboardConfig()
        assert cfg.port == 1

    def test_port_65535_valid(self, monkeypatch):
        """Maximum port (65535) is valid."""
        monkeypatch.setenv('DASHBOARD_WEB_PORT', '65535')
        cfg = DashboardConfig()
        assert cfg.port == 65535

    def test_port_float_raises(self, monkeypatch):
        """Float port string raises ValueError."""
        monkeypatch.setenv('DASHBOARD_WEB_PORT', '80.5')
        with pytest.raises(ValueError, match='DASHBOARD_WEB_PORT'):
            DashboardConfig()


# ---------------------------------------------------------------------------
# 4. Broadcast interval validation
# ---------------------------------------------------------------------------

class TestBroadcastIntervalValidation:
    def test_interval_zero_raises(self, monkeypatch):
        """Interval 0 is out of range (min=1) and raises ValueError."""
        monkeypatch.setenv('DASHBOARD_BROADCAST_INTERVAL', '0')
        with pytest.raises(ValueError, match='DASHBOARD_BROADCAST_INTERVAL'):
            DashboardConfig()

    def test_interval_negative_raises(self, monkeypatch):
        """Negative interval raises ValueError."""
        monkeypatch.setenv('DASHBOARD_BROADCAST_INTERVAL', '-5')
        with pytest.raises(ValueError, match='DASHBOARD_BROADCAST_INTERVAL'):
            DashboardConfig()

    def test_interval_3601_raises(self, monkeypatch):
        """Interval 3601 exceeds maximum (3600) and raises ValueError."""
        monkeypatch.setenv('DASHBOARD_BROADCAST_INTERVAL', '3601')
        with pytest.raises(ValueError, match='DASHBOARD_BROADCAST_INTERVAL'):
            DashboardConfig()

    def test_interval_non_integer_raises(self, monkeypatch):
        """Non-integer interval raises ValueError."""
        monkeypatch.setenv('DASHBOARD_BROADCAST_INTERVAL', 'xyz')
        with pytest.raises(ValueError, match='DASHBOARD_BROADCAST_INTERVAL'):
            DashboardConfig()

    def test_interval_1_valid(self, monkeypatch):
        """Minimum interval (1) is valid."""
        monkeypatch.setenv('DASHBOARD_BROADCAST_INTERVAL', '1')
        cfg = DashboardConfig()
        assert cfg.broadcast_interval == 1

    def test_interval_3600_valid(self, monkeypatch):
        """Maximum interval (3600) is valid."""
        monkeypatch.setenv('DASHBOARD_BROADCAST_INTERVAL', '3600')
        cfg = DashboardConfig()
        assert cfg.broadcast_interval == 3600


# ---------------------------------------------------------------------------
# 5. auth_required property
# ---------------------------------------------------------------------------

class TestAuthRequired:
    def test_auth_required_false_when_token_empty(self):
        """auth_required is False when DASHBOARD_AUTH_TOKEN is not set."""
        cfg = DashboardConfig()
        assert cfg.auth_required is False

    def test_auth_required_true_when_token_set(self, monkeypatch):
        """auth_required is True when DASHBOARD_AUTH_TOKEN is set."""
        monkeypatch.setenv('DASHBOARD_AUTH_TOKEN', 'my-secret')
        cfg = DashboardConfig()
        assert cfg.auth_required is True

    def test_auth_required_false_when_token_explicitly_empty(self, monkeypatch):
        """auth_required is False when DASHBOARD_AUTH_TOKEN is set to empty string."""
        monkeypatch.setenv('DASHBOARD_AUTH_TOKEN', '')
        cfg = DashboardConfig()
        assert cfg.auth_required is False

    def test_auth_enabled_alias_matches_auth_required(self, monkeypatch):
        """auth_enabled is an alias for auth_required."""
        monkeypatch.setenv('DASHBOARD_AUTH_TOKEN', 'tok')
        cfg = DashboardConfig()
        assert cfg.auth_enabled == cfg.auth_required


# ---------------------------------------------------------------------------
# 6. cors_origins_list()
# ---------------------------------------------------------------------------

class TestCorsOriginsList:
    def test_wildcard_returns_list_with_star(self):
        """When cors_origins='*', cors_origins_list() returns ['*']."""
        cfg = DashboardConfig()
        assert cfg.cors_origins_list() == ['*']

    def test_single_origin(self, monkeypatch):
        """Single origin string is returned as one-element list."""
        monkeypatch.setenv('DASHBOARD_CORS_ORIGINS', 'https://example.com')
        cfg = DashboardConfig()
        assert cfg.cors_origins_list() == ['https://example.com']

    def test_multiple_origins(self, monkeypatch):
        """Multiple comma-separated origins are split and stripped."""
        monkeypatch.setenv('DASHBOARD_CORS_ORIGINS', 'https://a.com, https://b.com ,https://c.com')
        cfg = DashboardConfig()
        assert cfg.cors_origins_list() == ['https://a.com', 'https://b.com', 'https://c.com']

    def test_get_cors_origins_list_alias(self):
        """get_cors_origins_list() is an alias for cors_origins_list()."""
        cfg = DashboardConfig()
        assert cfg.get_cors_origins_list() == cfg.cors_origins_list()


# ---------------------------------------------------------------------------
# 7. get_config() singleton behaviour
# ---------------------------------------------------------------------------

class TestGetConfigSingleton:
    def test_get_config_returns_config_instance(self):
        """get_config() returns a DashboardConfig instance."""
        cfg = get_config()
        assert isinstance(cfg, DashboardConfig)

    def test_get_config_returns_same_instance(self):
        """Subsequent calls to get_config() return the identical object."""
        cfg1 = get_config()
        cfg2 = get_config()
        assert cfg1 is cfg2

    def test_get_config_uses_defaults(self):
        """get_config() uses default values when no env vars set."""
        cfg = get_config()
        assert cfg.host == '127.0.0.1'
        assert cfg.port == 8080
        assert cfg.broadcast_interval == 5


# ---------------------------------------------------------------------------
# 8. reset_config() resets singleton
# ---------------------------------------------------------------------------

class TestResetConfig:
    def test_reset_config_forces_new_instance(self):
        """After reset_config(), get_config() returns a new instance."""
        cfg1 = get_config()
        reset_config()
        cfg2 = get_config()
        assert cfg1 is not cfg2

    def test_reset_config_picks_up_new_env_vars(self, monkeypatch):
        """After reset_config(), new env vars are picked up."""
        cfg1 = get_config()
        assert cfg1.port == 8080

        monkeypatch.setenv('DASHBOARD_WEB_PORT', '9999')
        reset_config()
        cfg2 = get_config()
        assert cfg2.port == 9999

    def test_reset_config_clears_singleton(self):
        """Calling reset_config() twice is safe."""
        get_config()
        reset_config()
        reset_config()  # Should not raise
        cfg = get_config()
        assert cfg.host == '127.0.0.1'
