"""Tests for REQ-PROVIDER-001: Provider Switcher UI.

Tests cover:
- /api/providers endpoint returns all 6 providers
- Provider availability detection via environment variables
- Provider status (available/unavailable) based on API key presence
- Dashboard serves modern index.html with provider selector
- Provider selector HTML structure and accessibility
"""

import os
import json
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Ensure project root is in path
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestProviderStatusEndpoint:
    """Test the /api/providers endpoint."""

    def _make_server(self, project_dir=None):
        """Create a DashboardServer instance for testing."""
        from scripts.dashboard_server import DashboardServer
        if project_dir is None:
            project_dir = PROJECT_ROOT
        return DashboardServer(project_dir=project_dir)

    @pytest.mark.asyncio
    async def test_providers_returns_all_six_providers(self):
        """Test that /api/providers returns all 6 expected providers."""
        server = self._make_server()
        # Simulate request (no web.Request needed - just test handler logic)
        request = MagicMock()

        with patch.dict(os.environ, {
            'ANTHROPIC_API_KEY': 'test-key',
            'OPENAI_API_KEY': 'test-key',
        }):
            response = await server.handle_providers(request)
            data = json.loads(response.text)

        assert 'providers' in data
        providers = data['providers']

        # All 6 providers must be present
        expected_providers = ['claude', 'openai', 'gemini', 'groq', 'kimi', 'windsurf']
        for provider_id in expected_providers:
            assert provider_id in providers, f"Provider '{provider_id}' not found in response"

    @pytest.mark.asyncio
    async def test_provider_available_when_api_key_set(self):
        """Test provider shows as available when its API key is set."""
        server = self._make_server()
        request = MagicMock()

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'sk-test-key'}, clear=False):
            response = await server.handle_providers(request)
            data = json.loads(response.text)

        claude = data['providers']['claude']
        assert claude['available'] is True
        assert claude['status'] == 'available'

    @pytest.mark.asyncio
    async def test_provider_unavailable_when_no_api_key(self):
        """Test provider shows as unavailable when API key is not set."""
        server = self._make_server()
        request = MagicMock()

        # Remove all provider keys
        env_without_keys = {
            k: v for k, v in os.environ.items()
            if k not in ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY',
                         'GROQ_API_KEY', 'KIMI_API_KEY', 'MOONSHOT_API_KEY',
                         'WINDSURF_API_KEY', 'GOOGLE_API_KEY']
        }

        with patch.dict(os.environ, env_without_keys, clear=True):
            response = await server.handle_providers(request)
            data = json.loads(response.text)

        for provider_id in ['claude', 'openai', 'gemini', 'groq', 'kimi', 'windsurf']:
            provider = data['providers'][provider_id]
            assert provider['available'] is False, f"{provider_id} should be unavailable without API key"
            assert provider['status'] == 'unavailable'

    @pytest.mark.asyncio
    async def test_provider_response_has_required_fields(self):
        """Test each provider entry has all required fields."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_providers(request)
        data = json.loads(response.text)

        required_fields = ['id', 'name', 'available', 'models', 'default_model', 'status']
        for provider_id, provider_info in data['providers'].items():
            for field in required_fields:
                assert field in provider_info, \
                    f"Provider '{provider_id}' missing field '{field}'"

    @pytest.mark.asyncio
    async def test_gemini_available_with_google_api_key(self):
        """Test Gemini can use GOOGLE_API_KEY as fallback."""
        server = self._make_server()
        request = MagicMock()

        env = {k: v for k, v in os.environ.items() if k not in ['GEMINI_API_KEY', 'GOOGLE_API_KEY']}
        with patch.dict(os.environ, {**env, 'GOOGLE_API_KEY': 'test-google-key'}, clear=True):
            response = await server.handle_providers(request)
            data = json.loads(response.text)

        assert data['providers']['gemini']['available'] is True

    @pytest.mark.asyncio
    async def test_kimi_available_with_moonshot_api_key(self):
        """Test KIMI can use MOONSHOT_API_KEY as fallback."""
        server = self._make_server()
        request = MagicMock()

        env = {k: v for k, v in os.environ.items() if k not in ['KIMI_API_KEY', 'MOONSHOT_API_KEY']}
        with patch.dict(os.environ, {**env, 'MOONSHOT_API_KEY': 'test-moonshot-key'}, clear=True):
            response = await server.handle_providers(request)
            data = json.loads(response.text)

        assert data['providers']['kimi']['available'] is True

    @pytest.mark.asyncio
    async def test_provider_models_are_correctly_defined(self):
        """Test each provider has the correct model list."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_providers(request)
        data = json.loads(response.text)
        providers = data['providers']

        # Claude models
        assert 'haiku-4.5' in providers['claude']['models']
        assert 'sonnet-4.5' in providers['claude']['models']
        assert 'opus-4.6' in providers['claude']['models']
        assert len(providers['claude']['models']) == 3

        # OpenAI models
        assert 'gpt-4o' in providers['openai']['models']
        assert 'o1' in providers['openai']['models']
        assert 'o3-mini' in providers['openai']['models']
        assert 'o4-mini' in providers['openai']['models']
        assert len(providers['openai']['models']) == 4

        # Gemini models
        assert '2.5-flash' in providers['gemini']['models']
        assert '2.5-pro' in providers['gemini']['models']
        assert '2.0-flash' in providers['gemini']['models']
        assert len(providers['gemini']['models']) == 3

        # Groq models
        assert 'llama-3.3-70b' in providers['groq']['models']
        assert 'mixtral-8x7b' in providers['groq']['models']
        assert len(providers['groq']['models']) == 2

        # KIMI models
        assert 'moonshot' in providers['kimi']['models']
        assert len(providers['kimi']['models']) == 1

        # Windsurf models
        assert 'cascade' in providers['windsurf']['models']
        assert len(providers['windsurf']['models']) == 1

    @pytest.mark.asyncio
    async def test_default_provider_is_claude(self):
        """Test that the default provider is claude."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_providers(request)
        data = json.loads(response.text)

        assert data['default_provider'] == 'claude'

    @pytest.mark.asyncio
    async def test_response_includes_timestamp(self):
        """Test that provider response includes a timestamp."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_providers(request)
        data = json.loads(response.text)

        assert 'timestamp' in data
        assert data['timestamp'].endswith('Z')  # UTC timestamp


class TestDashboardServesModernHTML:
    """Test that the dashboard server now serves the modern index.html."""

    def _make_server(self, project_dir=None):
        """Create a DashboardServer instance for testing."""
        from scripts.dashboard_server import DashboardServer
        if project_dir is None:
            project_dir = PROJECT_ROOT
        return DashboardServer(project_dir=project_dir)

    @pytest.mark.asyncio
    async def test_index_serves_modern_dashboard(self):
        """Test that the root endpoint serves modern dashboard HTML."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_index(request)

        assert response.status == 200
        assert 'text/html' in response.content_type

    @pytest.mark.asyncio
    async def test_index_html_contains_provider_selector(self):
        """Test that served HTML contains a provider selector."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_index(request)
        html = response.text

        # Must have all 6 provider options
        assert 'claude' in html.lower()
        assert 'openai' in html.lower() or 'chatgpt' in html.lower()
        assert 'gemini' in html.lower()
        assert 'groq' in html.lower()
        assert 'kimi' in html.lower()
        assert 'windsurf' in html.lower()

    @pytest.mark.asyncio
    async def test_index_html_contains_model_selector(self):
        """Test that served HTML contains a model selector."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_index(request)
        html = response.text

        assert 'model-select' in html

    @pytest.mark.asyncio
    async def test_index_html_has_provider_status_elements(self):
        """Test that served HTML has provider status indicator elements."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_index(request)
        html = response.text

        # Status badge element must be present
        assert 'provider-status-badge' in html
        assert 'provider-status-info' in html

    @pytest.mark.asyncio
    async def test_index_html_is_accessible(self):
        """Test that provider selector has accessibility attributes."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_index(request)
        html = response.text

        # Selectors must have aria-label
        assert 'aria-label' in html
        # Status elements must have aria-live for screen readers
        assert 'aria-live' in html


class TestProviderSwitcherHTMLStructure:
    """Test the HTML structure of the provider switcher in index.html."""

    @pytest.fixture
    def index_html(self):
        """Read the index.html file."""
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_all_six_providers_in_selector(self, index_html):
        """Test all 6 providers are in the provider select element."""
        assert 'value="claude"' in index_html
        assert 'value="openai"' in index_html
        assert 'value="gemini"' in index_html
        assert 'value="groq"' in index_html
        assert 'value="kimi"' in index_html
        assert 'value="windsurf"' in index_html

    def test_provider_select_has_id(self, index_html):
        """Test provider select element has correct id."""
        assert 'id="provider-select"' in index_html

    def test_model_select_has_id(self, index_html):
        """Test model select element has correct id."""
        assert 'id="model-select"' in index_html

    def test_provider_status_badge_present(self, index_html):
        """Test provider status badge element is present."""
        assert 'id="provider-status-badge"' in index_html

    def test_provider_status_info_present(self, index_html):
        """Test provider status info element is present."""
        assert 'id="provider-status-info"' in index_html

    def test_provider_labels_are_accessible(self, index_html):
        """Test provider and model labels are properly associated."""
        assert 'for="provider-select"' in index_html
        assert 'for="model-select"' in index_html

    def test_aria_labels_on_selectors(self, index_html):
        """Test selectors have aria-label for accessibility."""
        assert 'aria-label="Select AI provider"' in index_html
        assert 'aria-label="Select AI model"' in index_html

    def test_provider_models_config_defined(self, index_html):
        """Test providerModels configuration is defined in JavaScript."""
        assert 'const providerModels' in index_html
        assert 'haiku-4.5' in index_html
        assert 'gpt-4o' in index_html
        assert '2.5-flash' in index_html
        assert 'llama-3.3-70b' in index_html
        assert 'moonshot' in index_html
        assert 'cascade' in index_html

    def test_load_provider_status_function_defined(self, index_html):
        """Test loadProviderStatus function is defined."""
        assert 'loadProviderStatus' in index_html
        assert '/api/providers' in index_html

    def test_update_provider_status_function_defined(self, index_html):
        """Test updateCurrentProviderStatus function is defined."""
        assert 'updateCurrentProviderStatus' in index_html

    def test_provider_change_handler_updates_status(self, index_html):
        """Test handleProviderChange calls status update function."""
        assert 'handleProviderChange' in index_html
        assert 'updateCurrentProviderStatus' in index_html

    def test_init_calls_load_provider_status(self, index_html):
        """Test init() calls loadProviderStatus to load provider info."""
        assert 'loadProviderStatus()' in index_html

    def test_selection_persists_in_state(self, index_html):
        """Test provider selection is persisted in state object."""
        assert 'currentProvider' in index_html
        assert 'currentModel' in index_html

    def test_provider_status_css_defined(self, index_html):
        """Test CSS classes for provider status indicators are defined."""
        assert '.provider-status-badge' in index_html
        assert '.provider-status-dot' in index_html
        assert '.available' in index_html
        assert '.unavailable' in index_html


class TestProviderSelectorPersistence:
    """Test that provider selection persists correctly."""

    @pytest.fixture
    def index_html(self):
        """Read the index.html file."""
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_state_has_current_provider(self, index_html):
        """Test state object has currentProvider field."""
        assert 'currentProvider:' in index_html

    def test_default_provider_is_claude(self, index_html):
        """Test default provider is set to claude."""
        assert "currentProvider: 'claude'" in index_html

    def test_handle_provider_change_updates_state(self, index_html):
        """Test that provider change handler updates state.currentProvider."""
        assert 'state.currentProvider = event.target.value' in index_html

    def test_update_model_selector_called_on_provider_change(self, index_html):
        """Test updateModelSelector is called when provider changes."""
        assert 'updateModelSelector(state.currentProvider)' in index_html

    def test_stats_updated_on_provider_change(self, index_html):
        """Test stats are updated when provider changes."""
        # handleProviderChange should call updateStats
        assert 'updateStats()' in index_html

    def test_system_message_on_provider_switch(self, index_html):
        """Test system message is added when switching providers."""
        assert "Switched to provider:" in index_html
