"""Tests for REQ-PROVIDER-002: Model Selector with Provider-Specific Models.

Tests cover:
- Model list updates dynamically with provider
- Sensible defaults per provider (Sonnet for Claude, gpt-4o for OpenAI, etc.)
- Model selection persists during session via sessionStorage
- Cascade of dropdowns is smooth (CSS transition exists)
- /api/providers returns correct default_model per provider
"""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Ensure project root is in path
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestModelSelectorHTMLStructure:
    """Test the HTML structure of the model selector in index.html."""

    @pytest.fixture
    def index_html(self):
        """Read the index.html file."""
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_model_select_element_exists(self, index_html):
        """Test that the model select element exists."""
        assert 'id="model-select"' in index_html

    def test_model_selector_has_aria_label(self, index_html):
        """Test model selector has accessibility label."""
        assert 'aria-label="Select AI model"' in index_html

    def test_provider_models_config_has_all_providers(self, index_html):
        """Test providerModels config has all 6 providers."""
        assert 'const providerModels = {' in index_html
        for provider in ['claude', 'openai', 'gemini', 'groq', 'kimi', 'windsurf']:
            assert f'{provider}:' in index_html

    def test_claude_models_correct(self, index_html):
        """Test Claude has the correct 3 models."""
        assert 'haiku-4.5' in index_html
        assert 'sonnet-4.5' in index_html
        assert 'opus-4.6' in index_html

    def test_openai_models_correct(self, index_html):
        """Test OpenAI has the correct 4 models."""
        assert 'gpt-4o' in index_html
        assert "'o1'" in index_html or '"o1"' in index_html
        assert 'o3-mini' in index_html
        assert 'o4-mini' in index_html

    def test_gemini_models_correct(self, index_html):
        """Test Gemini has the correct 3 models."""
        assert '2.5-flash' in index_html
        assert '2.5-pro' in index_html
        assert '2.0-flash' in index_html

    def test_groq_models_correct(self, index_html):
        """Test Groq has the correct 2 models."""
        assert 'llama-3.3-70b' in index_html
        assert 'mixtral-8x7b' in index_html

    def test_kimi_models_correct(self, index_html):
        """Test KIMI has the moonshot model."""
        assert 'moonshot' in index_html

    def test_windsurf_models_correct(self, index_html):
        """Test Windsurf has the cascade model."""
        assert 'cascade' in index_html

    def test_update_model_selector_function_exists(self, index_html):
        """Test updateModelSelector function is defined."""
        assert 'function updateModelSelector(' in index_html

    def test_model_selector_css_transition(self, index_html):
        """Test model selector has CSS transition for smooth cascade."""
        assert '#model-select' in index_html
        assert 'transition' in index_html

    def test_provider_defaults_defined(self, index_html):
        """Test sensible provider defaults are defined."""
        assert 'providerDefaults' in index_html
        # Sonnet for Claude
        assert "claude: 'sonnet-4.5'" in index_html
        # GPT-4o for OpenAI
        assert "openai: 'gpt-4o'" in index_html
        # 2.5-flash for Gemini
        assert "gemini: '2.5-flash'" in index_html
        # Llama 3.3 for Groq
        assert "groq: 'llama-3.3-70b'" in index_html
        # moonshot for KIMI
        assert "kimi: 'moonshot'" in index_html
        # cascade for Windsurf
        assert "windsurf: 'cascade'" in index_html


class TestModelSelectorPersistence:
    """Test that model selection persists in sessionStorage."""

    @pytest.fixture
    def index_html(self):
        """Read the index.html file."""
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_session_storage_save_on_model_change(self, index_html):
        """Test sessionStorage.setItem is called on model change."""
        assert "sessionStorage.setItem('currentModel'" in index_html

    def test_session_storage_save_on_provider_change(self, index_html):
        """Test sessionStorage.setItem is called on provider change."""
        assert "sessionStorage.setItem('currentProvider'" in index_html

    def test_session_storage_restore_on_load(self, index_html):
        """Test sessionStorage.getItem is called on page load."""
        assert "sessionStorage.getItem('currentProvider')" in index_html
        assert "sessionStorage.getItem('currentModel')" in index_html

    def test_default_provider_claude_on_first_load(self, index_html):
        """Test Claude is the default when no session exists."""
        assert "|| 'claude'" in index_html

    def test_default_model_sonnet_on_first_load(self, index_html):
        """Test Sonnet 4.5 is the default Claude model on first load."""
        assert "|| 'sonnet-4.5'" in index_html

    def test_init_restores_provider_selection(self, index_html):
        """Test init() restores provider selection from sessionStorage."""
        assert 'providerSelect.value = state.currentProvider' in index_html

    def test_update_model_selector_accepts_preferred_model(self, index_html):
        """Test updateModelSelector accepts a preferred model parameter."""
        # The function signature should accept a preferred model
        assert 'function updateModelSelector(provider, preferredModel)' in index_html

    def test_init_passes_saved_model_to_update(self, index_html):
        """Test init() passes the saved model to updateModelSelector."""
        assert 'updateModelSelector(state.currentProvider, state.currentModel)' in index_html


class TestSensibleDefaults:
    """Test that sensible default models are applied for each provider."""

    @pytest.fixture
    def index_html(self):
        """Read the index.html file."""
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_claude_default_is_sonnet(self, index_html):
        """Test that Claude's default model is Sonnet 4.5."""
        assert "claude: 'sonnet-4.5'" in index_html

    def test_openai_default_is_gpt4o(self, index_html):
        """Test that OpenAI's default model is GPT-4o."""
        assert "openai: 'gpt-4o'" in index_html

    def test_gemini_default_is_25flash(self, index_html):
        """Test that Gemini's default model is 2.5 Flash."""
        assert "gemini: '2.5-flash'" in index_html

    def test_groq_default_is_llama(self, index_html):
        """Test that Groq's default model is Llama 3.3 70B."""
        assert "groq: 'llama-3.3-70b'" in index_html

    def test_kimi_default_is_moonshot(self, index_html):
        """Test that KIMI's default model is moonshot."""
        assert "kimi: 'moonshot'" in index_html

    def test_windsurf_default_is_cascade(self, index_html):
        """Test that Windsurf's default model is cascade."""
        assert "windsurf: 'cascade'" in index_html

    def test_provider_change_uses_default_model(self, index_html):
        """Test handleProviderChange uses provider-specific default model."""
        assert 'providerInfo.default_model' in index_html or 'providerDefaults[' in index_html


class TestProviderDefaultsInAPI:
    """Test that /api/providers returns correct default_model values."""

    def _make_server(self):
        from scripts.dashboard_server import DashboardServer
        return DashboardServer(project_dir=PROJECT_ROOT)

    @pytest.mark.asyncio
    async def test_claude_default_model_is_sonnet(self):
        """Test /api/providers returns sonnet-4.5 as Claude default."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_providers(request)
        data = json.loads(response.text)

        assert data['providers']['claude']['default_model'] == 'sonnet-4.5'

    @pytest.mark.asyncio
    async def test_openai_default_model_is_gpt4o(self):
        """Test /api/providers returns gpt-4o as OpenAI default."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_providers(request)
        data = json.loads(response.text)

        assert data['providers']['openai']['default_model'] == 'gpt-4o'

    @pytest.mark.asyncio
    async def test_gemini_default_model_is_25flash(self):
        """Test /api/providers returns 2.5-flash as Gemini default."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_providers(request)
        data = json.loads(response.text)

        assert data['providers']['gemini']['default_model'] == '2.5-flash'

    @pytest.mark.asyncio
    async def test_groq_default_model_is_llama(self):
        """Test /api/providers returns llama-3.3-70b as Groq default."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_providers(request)
        data = json.loads(response.text)

        assert data['providers']['groq']['default_model'] == 'llama-3.3-70b'

    @pytest.mark.asyncio
    async def test_kimi_default_model_is_moonshot(self):
        """Test /api/providers returns moonshot as KIMI default."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_providers(request)
        data = json.loads(response.text)

        assert data['providers']['kimi']['default_model'] == 'moonshot'

    @pytest.mark.asyncio
    async def test_windsurf_default_model_is_cascade(self):
        """Test /api/providers returns cascade as Windsurf default."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_providers(request)
        data = json.loads(response.text)

        assert data['providers']['windsurf']['default_model'] == 'cascade'

    @pytest.mark.asyncio
    async def test_all_providers_have_default_model(self):
        """Test all 6 providers have a default_model field."""
        server = self._make_server()
        request = MagicMock()

        response = await server.handle_providers(request)
        data = json.loads(response.text)

        for provider_id, provider_info in data['providers'].items():
            assert 'default_model' in provider_info, \
                f"Provider '{provider_id}' missing default_model"
            assert provider_info['default_model'] in provider_info['models'], \
                f"Provider '{provider_id}' default_model not in models list"


class TestModelSelectorBehavior:
    """Test model selector behavior logic."""

    @pytest.fixture
    def index_html(self):
        """Read the index.html file."""
        html_path = PROJECT_ROOT / 'dashboard' / 'index.html'
        return html_path.read_text(encoding='utf-8')

    def test_model_state_updated_on_change(self, index_html):
        """Test state.currentModel is updated when model changes."""
        assert 'state.currentModel = event.target.value' in index_html

    def test_system_message_on_model_switch(self, index_html):
        """Test system message is added when switching models."""
        assert "Switched to model:" in index_html

    def test_model_persisted_in_update_selector(self, index_html):
        """Test updateModelSelector persists model to sessionStorage."""
        assert "sessionStorage.setItem('currentModel', state.currentModel)" in index_html

    def test_provider_also_persisted_in_update_selector(self, index_html):
        """Test updateModelSelector also persists provider to sessionStorage."""
        assert "sessionStorage.setItem('currentProvider', provider)" in index_html

    def test_model_selector_dynamic_population(self, index_html):
        """Test model options are dynamically populated (not hardcoded)."""
        # The model-select element should have no hardcoded options
        # (they're populated by JavaScript)
        assert '<!-- Model options will be populated by JavaScript -->' in index_html

    def test_preferred_model_falls_back_to_default(self, index_html):
        """Test that if preferred model not available, falls back to default."""
        # The updateModelSelector should have logic to find model in list
        assert "models.find(m => m.value === preferredModel)" in index_html
