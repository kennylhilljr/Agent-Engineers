"""
Tests for AI-155 (Edit Requirements Mid-Flight) + AI-156 (Requirement Edit Flow)

Verifies:
- HTML: req-edit-trigger-btn, req-confirm-dialog, confirm title/text/buttons
- CSS: .req-editor-textarea, .req-editor-preview, .req-editor-actions, .req-editor-btn,
       .req-edit-trigger-btn, .req-confirm-dialog, .req-confirm-dialog.visible,
       .req-confirm-actions
- State: editedRequirements object, currentEditAgentId variable, both window-exposed
- enterRequirementsEditMode: defined, window-exposed, only for paused agents, shows editor
- exitRequirementsEditMode: defined, window-exposed, re-renders view mode
- saveRequirementsEdit: defined, window-exposed, saves to editedRequirements, updates mockRequirements
- discardRequirementsEdit: defined, window-exposed, exits edit mode, adds message
- renderRequirementsEditor: defined, window-exposed, returns HTML with textarea/preview/buttons
- showResumeConfirmation: defined, window-exposed, shows confirm dialog
- confirmResumeWithEdits: defined, window-exposed, calls resumeAgent and closes view
- init() wires req-confirm-no-btn listener
"""
import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def find_section(content, start_marker, size=2000):
    """Find a section of content starting at start_marker with given size."""
    idx = content.find(start_marker)
    if idx == -1:
        return ''
    return content[idx:idx + size]


# ============================================================
# Test Group 1: Edit Requirements HTML Elements
# ============================================================

class TestEditRequirementsHTML:
    """Verify the edit requirements HTML elements are present."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_req_edit_trigger_btn_exists(self, html_content):
        """req-edit-trigger-btn button must be present in HTML."""
        assert 'id="req-edit-trigger-btn"' in html_content

    def test_req_confirm_dialog_exists(self, html_content):
        """req-confirm-dialog element must be present in HTML."""
        assert 'id="req-confirm-dialog"' in html_content

    def test_req_confirm_title_exists(self, html_content):
        """req-confirm-title element must be present."""
        assert 'req-confirm-title' in html_content

    def test_req_confirm_yes_btn_exists(self, html_content):
        """req-confirm-yes-btn must exist for confirming resume."""
        assert 'id="req-confirm-yes-btn"' in html_content

    def test_req_confirm_no_btn_exists(self, html_content):
        """req-confirm-no-btn must exist for cancelling resume."""
        assert 'id="req-confirm-no-btn"' in html_content

    def test_req_confirm_text_id_exists(self, html_content):
        """req-confirm-text element must exist for dynamic confirmation message."""
        assert 'id="req-confirm-text"' in html_content

    def test_req_edit_trigger_btn_has_class(self, html_content):
        """req-edit-trigger-btn must have the req-edit-trigger-btn CSS class."""
        assert 'class="req-edit-trigger-btn"' in html_content

    def test_req_confirm_dialog_has_class(self, html_content):
        """req-confirm-dialog must have the req-confirm-dialog CSS class."""
        assert 'class="req-confirm-dialog"' in html_content


# ============================================================
# Test Group 2: Edit Requirements CSS
# ============================================================

class TestEditRequirementsCSS:
    """Verify the required CSS classes are defined."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def style_section(self, html_content):
        """Extract content between <style> and </style>."""
        start = html_content.find('<style>')
        end = html_content.find('</style>')
        return html_content[start:end] if start != -1 and end != -1 else ''

    def test_req_editor_textarea_css(self, style_section):
        """.req-editor-textarea CSS class must be defined."""
        assert '.req-editor-textarea' in style_section

    def test_req_editor_preview_css(self, style_section):
        """.req-editor-preview CSS class must be defined."""
        assert '.req-editor-preview' in style_section

    def test_req_editor_actions_css(self, style_section):
        """.req-editor-actions CSS class must be defined."""
        assert '.req-editor-actions' in style_section

    def test_req_editor_btn_css(self, style_section):
        """.req-editor-btn CSS class must be defined."""
        assert '.req-editor-btn' in style_section

    def test_req_editor_btn_save_btn_css(self, style_section):
        """.req-editor-btn.save-btn CSS must be defined."""
        assert '.req-editor-btn.save-btn' in style_section

    def test_req_editor_btn_discard_btn_css(self, style_section):
        """.req-editor-btn.discard-btn CSS must be defined."""
        assert '.req-editor-btn.discard-btn' in style_section

    def test_req_edit_trigger_btn_css(self, style_section):
        """.req-edit-trigger-btn CSS class must be defined."""
        assert '.req-edit-trigger-btn' in style_section

    def test_req_confirm_dialog_css(self, style_section):
        """.req-confirm-dialog CSS class must be defined."""
        assert '.req-confirm-dialog' in style_section

    def test_req_confirm_dialog_visible_css(self, style_section):
        """.req-confirm-dialog.visible CSS class must be defined."""
        assert '.req-confirm-dialog.visible' in style_section

    def test_req_confirm_actions_css(self, style_section):
        """.req-confirm-actions CSS class must be defined."""
        assert '.req-confirm-actions' in style_section


# ============================================================
# Test Group 3: editedRequirements State
# ============================================================

class TestEditedRequirementsState:
    """Verify editedRequirements and currentEditAgentId state are defined."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_edited_requirements_defined(self, html_content):
        """editedRequirements variable must be defined in JS."""
        assert 'editedRequirements' in html_content

    def test_edited_requirements_window_exposed(self, html_content):
        """editedRequirements must be exposed on window."""
        assert 'window.editedRequirements' in html_content

    def test_edited_requirements_is_object(self, html_content):
        """editedRequirements must be initialized as an object."""
        assert 'window.editedRequirements = {}' in html_content

    def test_current_edit_agent_id_defined(self, html_content):
        """currentEditAgentId variable must be defined in JS."""
        assert 'currentEditAgentId' in html_content

    def test_current_edit_agent_id_window_exposed(self, html_content):
        """currentEditAgentId must be exposed on window."""
        assert 'window.currentEditAgentId' in html_content

    def test_current_edit_agent_id_initialized_null(self, html_content):
        """currentEditAgentId must be initialized to null."""
        assert 'window.currentEditAgentId = null' in html_content


# ============================================================
# Test Group 4: enterRequirementsEditMode Function
# ============================================================

class TestEnterEditModeFunction:
    """Verify enterRequirementsEditMode function is defined and correct."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def fn_section(self, html_content):
        return find_section(html_content, 'function enterRequirementsEditMode', 2000)

    def test_function_exists(self, fn_section):
        """enterRequirementsEditMode function must be defined."""
        assert 'function enterRequirementsEditMode' in fn_section

    def test_window_exposed(self, html_content):
        """enterRequirementsEditMode must be exposed on window."""
        assert 'window.enterRequirementsEditMode = enterRequirementsEditMode' in html_content

    def test_checks_agent_paused(self, fn_section):
        """Function must check isAgentPaused before proceeding."""
        assert 'isAgentPaused' in fn_section

    def test_returns_if_not_paused(self, fn_section):
        """Function must return early if agent is not paused."""
        assert 'return' in fn_section

    def test_sets_current_edit_agent_id(self, fn_section):
        """Function must set window.currentEditAgentId."""
        assert 'currentEditAgentId = agentId' in fn_section

    def test_renders_editor_html(self, fn_section):
        """Function must call renderRequirementsEditor."""
        assert 'renderRequirementsEditor' in fn_section

    def test_updates_modal_body(self, fn_section):
        """Function must update modal body innerHTML."""
        assert 'requirements-modal-body' in fn_section

    def test_checks_edited_requirements(self, fn_section):
        """Function must check editedRequirements for existing edits."""
        assert 'editedRequirements' in fn_section


# ============================================================
# Test Group 5: exitRequirementsEditMode Function
# ============================================================

class TestExitEditModeFunction:
    """Verify exitRequirementsEditMode function is defined and correct."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def fn_section(self, html_content):
        return find_section(html_content, 'function exitRequirementsEditMode', 500)

    def test_function_exists(self, fn_section):
        """exitRequirementsEditMode function must be defined."""
        assert 'function exitRequirementsEditMode' in fn_section

    def test_window_exposed(self, html_content):
        """exitRequirementsEditMode must be exposed on window."""
        assert 'window.exitRequirementsEditMode = exitRequirementsEditMode' in html_content

    def test_removes_edit_mode_class(self, fn_section):
        """Function must remove req-edit-mode class from modal."""
        assert 'req-edit-mode' in fn_section

    def test_calls_open_requirements_view(self, fn_section):
        """Function must call openRequirementsView to re-render."""
        assert 'openRequirementsView' in fn_section


# ============================================================
# Test Group 6: saveRequirementsEdit Function
# ============================================================

class TestSaveRequirementsEditFunction:
    """Verify saveRequirementsEdit function is defined and correct."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def fn_section(self, html_content):
        return find_section(html_content, 'function saveRequirementsEdit', 1500)

    def test_function_exists(self, fn_section):
        """saveRequirementsEdit function must be defined."""
        assert 'function saveRequirementsEdit' in fn_section

    def test_window_exposed(self, html_content):
        """saveRequirementsEdit must be exposed on window."""
        assert 'window.saveRequirementsEdit = saveRequirementsEdit' in html_content

    def test_saves_to_edited_requirements(self, fn_section):
        """Function must save text to editedRequirements map."""
        assert 'editedRequirements[ticket]' in fn_section

    def test_adds_system_message(self, fn_section):
        """Function must call addSystemMessage after saving."""
        assert 'addSystemMessage' in fn_section

    def test_updates_mock_requirements(self, fn_section):
        """Function must update mockRequirements sources."""
        assert 'mockRequirements[ticket]' in fn_section

    def test_calls_exit_edit_mode(self, fn_section):
        """Function must call exitRequirementsEditMode after save."""
        assert 'exitRequirementsEditMode' in fn_section

    def test_system_message_mentions_requirements(self, fn_section):
        """System message must mention requirements update."""
        assert 'Requirements updated' in fn_section


# ============================================================
# Test Group 7: discardRequirementsEdit Function
# ============================================================

class TestDiscardRequirementsEditFunction:
    """Verify discardRequirementsEdit function is defined and correct."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def fn_section(self, html_content):
        return find_section(html_content, 'function discardRequirementsEdit', 400)

    def test_function_exists(self, fn_section):
        """discardRequirementsEdit function must be defined."""
        assert 'function discardRequirementsEdit' in fn_section

    def test_window_exposed(self, html_content):
        """discardRequirementsEdit must be exposed on window."""
        assert 'window.discardRequirementsEdit = discardRequirementsEdit' in html_content

    def test_calls_exit_edit_mode(self, fn_section):
        """Function must call exitRequirementsEditMode."""
        assert 'exitRequirementsEditMode' in fn_section

    def test_adds_system_message(self, fn_section):
        """Function must add a system message on discard."""
        assert 'addSystemMessage' in fn_section


# ============================================================
# Test Group 8: renderRequirementsEditor Function
# ============================================================

class TestRenderRequirementsEditorFunction:
    """Verify renderRequirementsEditor function is defined and returns correct HTML."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def fn_section(self, html_content):
        return find_section(html_content, 'function renderRequirementsEditor', 1200)

    def test_function_exists(self, fn_section):
        """renderRequirementsEditor function must be defined."""
        assert 'function renderRequirementsEditor' in fn_section

    def test_window_exposed(self, html_content):
        """renderRequirementsEditor must be exposed on window."""
        assert 'window.renderRequirementsEditor = renderRequirementsEditor' in html_content

    def test_returns_string_with_textarea(self, fn_section):
        """Function must include a textarea in its returned HTML."""
        assert 'req-editor-textarea' in fn_section

    def test_returns_string_with_preview(self, fn_section):
        """Function must include a preview area in its returned HTML."""
        assert 'req-editor-preview' in fn_section

    def test_returns_string_with_save_button(self, fn_section):
        """Function must include a save button in its returned HTML."""
        assert 'save-btn' in fn_section

    def test_returns_string_with_discard_button(self, fn_section):
        """Function must include a discard button in its returned HTML."""
        assert 'discard-btn' in fn_section

    def test_textarea_has_oninput_handler(self, fn_section):
        """Textarea must have an oninput handler for live preview."""
        assert 'oninput' in fn_section

    def test_includes_preview_label(self, fn_section):
        """Function must include a preview label element."""
        assert 'req-editor-preview-label' in fn_section


# ============================================================
# Test Group 9: showResumeConfirmation Function
# ============================================================

class TestShowResumeConfirmationFunction:
    """Verify showResumeConfirmation function is defined and correct."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def fn_section(self, html_content):
        return find_section(html_content, 'function showResumeConfirmation', 1200)

    def test_function_exists(self, fn_section):
        """showResumeConfirmation function must be defined."""
        assert 'function showResumeConfirmation' in fn_section

    def test_window_exposed(self, html_content):
        """showResumeConfirmation must be exposed on window."""
        assert 'window.showResumeConfirmation = showResumeConfirmation' in html_content

    def test_references_confirm_dialog(self, fn_section):
        """Function must reference the req-confirm-dialog element."""
        assert 'req-confirm-dialog' in fn_section

    def test_adds_visible_class(self, fn_section):
        """Function must add the 'visible' class to the dialog."""
        assert 'visible' in fn_section

    def test_wires_yes_btn(self, fn_section):
        """Function must wire the yes/confirm button onclick."""
        assert 'req-confirm-yes-btn' in fn_section


# ============================================================
# Test Group 10: confirmResumeWithEdits Function
# ============================================================

class TestConfirmResumeFunction:
    """Verify confirmResumeWithEdits function is defined and correct."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def fn_section(self, html_content):
        return find_section(html_content, 'function confirmResumeWithEdits', 400)

    def test_function_exists(self, fn_section):
        """confirmResumeWithEdits function must be defined."""
        assert 'function confirmResumeWithEdits' in fn_section

    def test_window_exposed(self, html_content):
        """confirmResumeWithEdits must be exposed on window."""
        assert 'window.confirmResumeWithEdits = confirmResumeWithEdits' in html_content

    def test_calls_resume_agent(self, fn_section):
        """Function must call resumeAgent to resume the agent."""
        assert 'resumeAgent' in fn_section

    def test_hides_dialog(self, fn_section):
        """Function must hide the confirmation dialog."""
        assert 'req-confirm-dialog' in fn_section


# ============================================================
# Test Group 11: Edit Flow in init()
# ============================================================

class TestEditFlowInInit:
    """Verify init() sets up the requirement editor event listeners."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def init_section(self, html_content):
        return find_section(html_content, 'function init()', 6000)

    def test_req_confirm_no_btn_listener_in_init(self, init_section):
        """init() must add event listener on req-confirm-no-btn."""
        assert 'req-confirm-no-btn' in init_section

    def test_req_confirm_no_btn_removes_visible_class(self, init_section):
        """req-confirm-no-btn listener must remove the visible class."""
        assert 'classList.remove' in init_section

    def test_req_confirm_no_btn_closes_dialog(self, init_section):
        """req-confirm-no-btn must target req-confirm-dialog."""
        assert 'req-confirm-dialog' in init_section

    def test_requirements_close_btn_listener_still_present(self, init_section):
        """Original requirements-close-btn listener must remain in init."""
        assert 'requirements-close-btn' in init_section


# ============================================================
# Test Group 12: openRequirementsView Integration
# ============================================================

class TestOpenRequirementsViewIntegration:
    """Verify openRequirementsView is updated to handle edit flow."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    @pytest.fixture(scope='class')
    def fn_section(self, html_content):
        return find_section(html_content, 'function openRequirementsView', 2000)

    def test_checks_agent_paused(self, fn_section):
        """openRequirementsView must check isAgentPaused."""
        assert 'isAgentPaused' in fn_section

    def test_shows_edit_btn_when_paused(self, fn_section):
        """openRequirementsView must show edit button when paused."""
        assert 'req-edit-trigger-btn' in fn_section

    def test_wires_edit_btn_click(self, fn_section):
        """openRequirementsView must wire edit button to enterRequirementsEditMode."""
        assert 'enterRequirementsEditMode' in fn_section

    def test_handles_confirm_dialog(self, fn_section):
        """openRequirementsView must show confirm dialog if edits exist."""
        assert 'req-confirm-dialog' in fn_section

    def test_checks_edited_requirements_map(self, fn_section):
        """openRequirementsView must check editedRequirements map."""
        assert 'editedRequirements' in fn_section
