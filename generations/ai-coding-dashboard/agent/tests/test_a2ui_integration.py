"""
Comprehensive integration tests for A2UI validator with test fixtures

Tests end-to-end validation workflows using real fixture files
"""

import json
import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from a2ui_validator import (
    A2UIValidator,
    validate_a2ui_file,
    validate_a2ui_message,
)


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent.parent / "test_fixtures"


class TestA2UIFixturesValidation:
    """Test validation using test fixture files"""

    def test_valid_message_1_card_with_children(self):
        """Test valid_message_1.json - Card with text and button"""
        fixture_path = FIXTURES_DIR / "valid_message_1.json"
        assert fixture_path.exists(), f"Fixture not found: {fixture_path}"

        result = validate_a2ui_file(str(fixture_path))
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert result["message"]["messageType"] == "beginRendering"
        assert len(result["message"]["components"]) == 3

    def test_valid_message_2_grid_with_badges(self):
        """Test valid_message_2.json - Container with grid and badges"""
        fixture_path = FIXTURES_DIR / "valid_message_2.json"
        result = validate_a2ui_file(str(fixture_path))
        assert result["valid"] is True
        assert result["message"]["messageType"] == "surfaceUpdate"
        assert len(result["message"]["components"]) == 5

    def test_valid_message_3_input_form(self):
        """Test valid_message_3.json - Data model update with input"""
        fixture_path = FIXTURES_DIR / "valid_message_3.json"
        result = validate_a2ui_file(str(fixture_path))
        assert result["valid"] is True
        assert result["message"]["messageType"] == "dataModelUpdate"

    def test_invalid_missing_type(self):
        """Test invalid_missing_type.json - Component missing type field"""
        fixture_path = FIXTURES_DIR / "invalid_missing_type.json"
        result = validate_a2ui_file(str(fixture_path))
        assert result["valid"] is False
        assert any('Missing required field "type"' in e for e in result["errors"])

    def test_invalid_missing_id(self):
        """Test invalid_missing_id.json - Component missing id field"""
        fixture_path = FIXTURES_DIR / "invalid_missing_id.json"
        result = validate_a2ui_file(str(fixture_path))
        assert result["valid"] is False
        assert any('Missing required field "id"' in e for e in result["errors"])

    def test_invalid_missing_props(self):
        """Test invalid_missing_props.json - Component missing props field"""
        fixture_path = FIXTURES_DIR / "invalid_missing_props.json"
        result = validate_a2ui_file(str(fixture_path))
        assert result["valid"] is False
        assert any('Missing required field "props"' in e for e in result["errors"])

    def test_invalid_bad_message_type(self):
        """Test invalid_bad_message_type.json - Invalid messageType value"""
        fixture_path = FIXTURES_DIR / "invalid_bad_message_type.json"
        result = validate_a2ui_file(str(fixture_path))
        assert result["valid"] is False
        assert any("Invalid messageType" in e for e in result["errors"])

    def test_security_unauthorized_component(self):
        """Test security_unauthorized_component.json - SECURITY TEST"""
        fixture_path = FIXTURES_DIR / "security_unauthorized_component.json"
        result = validate_a2ui_file(str(fixture_path))
        assert result["valid"] is False
        assert any("Invalid component type" in e for e in result["errors"])
        assert any("Not in registered catalog" in e for e in result["errors"])

    def test_security_script_injection(self):
        """Test security_script_injection.json - Script injection attempt"""
        fixture_path = FIXTURES_DIR / "security_script_injection.json"
        result = validate_a2ui_file(str(fixture_path))
        assert result["valid"] is False
        assert any("Invalid component type" in e for e in result["errors"])

    def test_edge_circular_reference(self):
        """Test edge_circular_reference.json - Circular reference detection"""
        fixture_path = FIXTURES_DIR / "edge_circular_reference.json"
        result = validate_a2ui_file(str(fixture_path))
        assert result["valid"] is False
        assert any("Circular reference" in e for e in result["errors"])

    def test_edge_duplicate_ids(self):
        """Test edge_duplicate_ids.json - Duplicate component IDs"""
        fixture_path = FIXTURES_DIR / "edge_duplicate_ids.json"
        result = validate_a2ui_file(str(fixture_path))
        assert result["valid"] is False
        assert any("Duplicate component ID" in e for e in result["errors"])

    def test_edge_missing_child_ref(self):
        """Test edge_missing_child_ref.json - Missing child reference"""
        fixture_path = FIXTURES_DIR / "edge_missing_child_ref.json"
        result = validate_a2ui_file(str(fixture_path))
        assert result["valid"] is False
        assert any("references non-existent child" in e for e in result["errors"])


class TestA2UIEndToEndWorkflow:
    """Test complete A2UI validation workflows"""

    def test_batch_validation_of_all_fixtures(self):
        """Test validating all fixtures at once"""
        valid_fixtures = [
            "valid_message_1.json",
            "valid_message_2.json",
            "valid_message_3.json",
        ]

        invalid_fixtures = [
            "invalid_missing_type.json",
            "invalid_missing_id.json",
            "invalid_missing_props.json",
            "invalid_bad_message_type.json",
        ]

        security_fixtures = [
            "security_unauthorized_component.json",
            "security_script_injection.json",
        ]

        edge_fixtures = [
            "edge_circular_reference.json",
            "edge_duplicate_ids.json",
            "edge_missing_child_ref.json",
        ]

        # Validate all valid fixtures
        for fixture in valid_fixtures:
            result = validate_a2ui_file(str(FIXTURES_DIR / fixture))
            assert result["valid"] is True, f"Expected {fixture} to be valid"

        # Validate all invalid fixtures
        for fixture in invalid_fixtures + security_fixtures + edge_fixtures:
            result = validate_a2ui_file(str(FIXTURES_DIR / fixture))
            assert result["valid"] is False, f"Expected {fixture} to be invalid"

    def test_agent_emission_simulation(self):
        """Simulate agent emitting A2UI and validating before sending to frontend"""
        validator = A2UIValidator()

        # Simulate agent generating A2UI
        agent_output = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Card",
                    "id": "dashboard-card",
                    "props": {"title": "Agent Dashboard"},
                    "children": ["status-text", "action-btn"],
                },
                {
                    "type": "a2ui.Text",
                    "id": "status-text",
                    "props": {"content": "Task execution in progress..."},
                },
                {
                    "type": "a2ui.Button",
                    "id": "action-btn",
                    "props": {"text": "Cancel", "variant": "danger"},
                },
            ],
        }

        # Validate before sending
        result = validator.validate_message(agent_output)
        assert result.valid is True

        # Simulate sending to frontend (only if valid)
        if result.valid:
            frontend_message = result.message
            assert frontend_message["messageType"] == "beginRendering"
            assert len(frontend_message["components"]) == 3

    def test_security_pipeline(self):
        """Test that security violations are caught and blocked"""
        validator = A2UIValidator()

        # Malicious attempts
        malicious_attempts = [
            # Attempt 1: Unauthorized component type
            {
                "messageType": "beginRendering",
                "components": [
                    {
                        "type": "a2ui.FileSystem",
                        "id": "hack-1",
                        "props": {"path": "/etc/passwd"},
                    }
                ],
            },
            # Attempt 2: Script injection via type
            {
                "messageType": "beginRendering",
                "components": [
                    {
                        "type": "<script>fetch('evil.com')</script>",
                        "id": "xss-1",
                        "props": {},
                    }
                ],
            },
            # Attempt 3: SQL injection-like pattern
            {
                "messageType": "beginRendering",
                "components": [
                    {
                        "type": "a2ui.DatabaseQuery",
                        "id": "sql-1",
                        "props": {"query": "DROP TABLE users;"},
                    }
                ],
            },
        ]

        # All should be rejected
        for i, attempt in enumerate(malicious_attempts):
            result = validator.validate_message(attempt)
            assert result.valid is False, f"Security attempt {i+1} should be blocked"
            assert len(result.errors) > 0

    def test_real_world_dashboard_message(self):
        """Test a complex real-world dashboard message"""
        dashboard = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Container",
                    "id": "root",
                    "props": {"maxWidth": "max-w-7xl"},
                    "children": ["header", "stats-grid", "tasks-container"],
                },
                {
                    "type": "a2ui.Card",
                    "id": "header",
                    "props": {"title": "Project Dashboard"},
                    "children": ["title-text"],
                },
                {
                    "type": "a2ui.Text",
                    "id": "title-text",
                    "props": {
                        "variant": "h1",
                        "content": "Welcome to your coding assistant",
                    },
                },
                {
                    "type": "a2ui.Grid",
                    "id": "stats-grid",
                    "props": {"cols": "3", "gap": "4"},
                    "children": ["stat-tasks", "stat-progress", "stat-completed"],
                },
                {
                    "type": "a2ui.Card",
                    "id": "stat-tasks",
                    "props": {"title": "Total Tasks"},
                    "children": ["stat-tasks-badge"],
                },
                {
                    "type": "a2ui.Badge",
                    "id": "stat-tasks-badge",
                    "props": {"variant": "info"},
                },
                {
                    "type": "a2ui.Card",
                    "id": "stat-progress",
                    "props": {"title": "In Progress"},
                    "children": ["stat-progress-badge"],
                },
                {
                    "type": "a2ui.Badge",
                    "id": "stat-progress-badge",
                    "props": {"variant": "warning"},
                },
                {
                    "type": "a2ui.Card",
                    "id": "stat-completed",
                    "props": {"title": "Completed"},
                    "children": ["stat-completed-badge"],
                },
                {
                    "type": "a2ui.Badge",
                    "id": "stat-completed-badge",
                    "props": {"variant": "success"},
                },
                {
                    "type": "a2ui.Container",
                    "id": "tasks-container",
                    "props": {},
                    "children": ["tasks-input", "tasks-divider", "tasks-button"],
                },
                {
                    "type": "a2ui.Input",
                    "id": "tasks-input",
                    "props": {
                        "type": "text",
                        "placeholder": "Enter new task...",
                    },
                },
                {
                    "type": "a2ui.Divider",
                    "id": "tasks-divider",
                    "props": {},
                },
                {
                    "type": "a2ui.Button",
                    "id": "tasks-button",
                    "props": {"text": "Add Task", "variant": "primary"},
                },
            ],
        }

        result = validate_a2ui_message(dashboard)
        assert result["valid"] is True
        assert len(result["message"]["components"]) == 14

        # Verify all child references are valid
        component_ids = {c["id"] for c in dashboard["components"]}
        for component in dashboard["components"]:
            if "children" in component:
                for child_id in component["children"]:
                    assert child_id in component_ids

    def test_validation_statistics(self):
        """Test tracking validation statistics"""
        validator = A2UIValidator()

        # Validate multiple messages
        messages = [
            # Valid
            {
                "messageType": "beginRendering",
                "components": [
                    {"type": "a2ui.Button", "id": "b1", "props": {}}
                ],
            },
            # Invalid (missing type)
            {
                "messageType": "beginRendering",
                "components": [{"id": "x", "props": {}}],
            },
            # Valid
            {
                "messageType": "surfaceUpdate",
                "components": [
                    {"type": "a2ui.Text", "id": "t1", "props": {}}
                ],
            },
            # Invalid (bad type)
            {
                "messageType": "beginRendering",
                "components": [
                    {"type": "a2ui.Evil", "id": "e1", "props": {}}
                ],
            },
        ]

        results = [validator.validate_message(msg) for msg in messages]

        total = len(results)
        passed = sum(1 for r in results if r.valid)
        failed = sum(1 for r in results if not r.valid)

        assert total == 4
        assert passed == 2
        assert failed == 2

        # Calculate catalog compliance
        catalog_violations = sum(
            1
            for r in results
            if not r.valid
            and any("catalog" in e.lower() for e in r.errors)
        )
        assert catalog_violations == 1  # Only the "a2ui.Evil" one


class TestA2UILoggingAndReporting:
    """Test validation logging and reporting"""

    def test_validation_log_created(self):
        """Test that validation log file is created"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = str(Path(tmpdir) / "test_validation.log")
            validator = A2UIValidator(log_file=log_file)

            # Perform validation
            validator.validate_message(
                {
                    "messageType": "beginRendering",
                    "components": [
                        {"type": "a2ui.Button", "id": "btn-1", "props": {}}
                    ],
                }
            )

            # Check log exists
            assert Path(log_file).exists()

            # Check log content
            log_content = Path(log_file).read_text()
            assert "Validation PASSED" in log_content

    def test_security_violations_logged(self):
        """Test that security violations are logged with SECURITY marker"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = str(Path(tmpdir) / "security_test.log")
            validator = A2UIValidator(log_file=log_file)

            # Attempt unauthorized component
            validator.validate_message(
                {
                    "messageType": "beginRendering",
                    "components": [
                        {
                            "type": "a2ui.Unauthorized",
                            "id": "hack-1",
                            "props": {},
                        }
                    ],
                }
            )

            # Check log for security warning
            log_content = Path(log_file).read_text()
            assert "SECURITY" in log_content
            assert "unauthorized" in log_content.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
