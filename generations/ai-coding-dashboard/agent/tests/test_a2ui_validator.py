"""
Comprehensive test suite for A2UI Protocol Validator

Tests all validation rules, messageType values, catalog compliance,
security constraints, and edge cases.
"""

import json
import pytest
import tempfile
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from a2ui_validator import (
    A2UIValidator,
    A2UIMessageType,
    A2UI_COMPONENT_TYPES,
    validate_a2ui_message,
    validate_a2ui_file,
)


class TestA2UIMessageTypeValidation:
    """Test messageType validation"""

    def test_valid_begin_rendering(self):
        """Test valid beginRendering messageType"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Button",
                    "id": "btn-1",
                    "props": {"text": "Click me"},
                }
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_valid_surface_update(self):
        """Test valid surfaceUpdate messageType"""
        message = {
            "messageType": "surfaceUpdate",
            "components": [
                {
                    "type": "a2ui.Text",
                    "id": "text-1",
                    "props": {"content": "Updated"},
                }
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is True

    def test_valid_data_model_update(self):
        """Test valid dataModelUpdate messageType"""
        message = {
            "messageType": "dataModelUpdate",
            "components": [
                {
                    "type": "a2ui.Card",
                    "id": "card-1",
                    "props": {"title": "Data"},
                }
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is True

    def test_invalid_message_type(self):
        """Test invalid messageType"""
        message = {
            "messageType": "invalidType",
            "components": [],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is False
        assert any("Invalid messageType" in e for e in result["errors"])

    def test_missing_message_type(self):
        """Test missing messageType"""
        message = {
            "components": [],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is False
        assert any("Missing required field: messageType" in e for e in result["errors"])


class TestA2UIComponentValidation:
    """Test component structure validation"""

    def test_valid_component_all_fields(self):
        """Test valid component with all required fields"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Button",
                    "id": "btn-1",
                    "props": {
                        "variant": "primary",
                        "onClick": "handleClick",
                    },
                }
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is True

    def test_missing_component_type(self):
        """Test component missing type field"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "id": "btn-1",
                    "props": {},
                }
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is False
        assert any('Missing required field "type"' in e for e in result["errors"])

    def test_missing_component_id(self):
        """Test component missing id field"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Button",
                    "props": {},
                }
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is False
        assert any('Missing required field "id"' in e for e in result["errors"])

    def test_missing_component_props(self):
        """Test component missing props field"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Button",
                    "id": "btn-1",
                }
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is False
        assert any('Missing required field "props"' in e for e in result["errors"])

    def test_empty_component_id(self):
        """Test component with empty id"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Button",
                    "id": "",
                    "props": {},
                }
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is False
        assert any('Field "id" cannot be empty' in e for e in result["errors"])

    def test_invalid_props_type(self):
        """Test component with invalid props type"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Button",
                    "id": "btn-1",
                    "props": "invalid",
                }
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is False
        assert any('Field "props" must be an object' in e for e in result["errors"])


class TestCatalogCompliance:
    """Test component catalog compliance (SECURITY)"""

    def test_all_registered_components_valid(self):
        """Test all registered component types are valid"""
        for component_type in A2UI_COMPONENT_TYPES:
            message = {
                "messageType": "beginRendering",
                "components": [
                    {
                        "type": component_type,
                        "id": "test-1",
                        "props": {},
                    }
                ],
            }
            result = validate_a2ui_message(message)
            assert result["valid"] is True, f"Failed for {component_type}"

    def test_unauthorized_component_type_rejected(self):
        """Test unauthorized component type is rejected (SECURITY)"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.MaliciousComponent",
                    "id": "evil-1",
                    "props": {},
                }
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is False
        assert any("Invalid component type" in e for e in result["errors"])
        assert any("Not in registered catalog" in e for e in result["errors"])

    def test_custom_catalog(self):
        """Test custom component catalog"""
        validator = A2UIValidator(custom_catalog=["a2ui.Custom"])
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Custom",
                    "id": "custom-1",
                    "props": {},
                }
            ],
        }
        result = validator.validate_message(message)
        assert result.valid is True

    def test_allow_unknown_types_flag(self):
        """Test allow_unknown_types flag (UNSAFE mode)"""
        validator = A2UIValidator(allow_unknown_types=True)
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Unknown",
                    "id": "unknown-1",
                    "props": {},
                }
            ],
        }
        result = validator.validate_message(message)
        assert result.valid is True


class TestComponentReferences:
    """Test component ID references and children"""

    def test_valid_child_references(self):
        """Test valid child references"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Container",
                    "id": "container-1",
                    "props": {},
                    "children": ["btn-1", "text-1"],
                },
                {
                    "type": "a2ui.Button",
                    "id": "btn-1",
                    "props": {},
                },
                {
                    "type": "a2ui.Text",
                    "id": "text-1",
                    "props": {},
                },
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is True

    def test_missing_child_reference(self):
        """Test reference to non-existent child"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Container",
                    "id": "container-1",
                    "props": {},
                    "children": ["btn-1", "missing-id"],
                },
                {
                    "type": "a2ui.Button",
                    "id": "btn-1",
                    "props": {},
                },
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is False
        assert any("references non-existent child" in e for e in result["errors"])

    def test_duplicate_component_ids(self):
        """Test duplicate component IDs"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Button",
                    "id": "btn-1",
                    "props": {},
                },
                {
                    "type": "a2ui.Text",
                    "id": "btn-1",
                    "props": {},
                },
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is False
        assert any("Duplicate component ID" in e for e in result["errors"])

    def test_circular_reference_detection(self):
        """Test circular reference detection"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Container",
                    "id": "container-1",
                    "props": {},
                    "children": ["container-2"],
                },
                {
                    "type": "a2ui.Container",
                    "id": "container-2",
                    "props": {},
                    "children": ["container-1"],
                },
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is False
        assert any("Circular reference" in e for e in result["errors"])


class TestJSONStructure:
    """Test JSON structure validation"""

    def test_valid_json_string(self):
        """Test valid JSON string input"""
        json_string = json.dumps(
            {
                "messageType": "beginRendering",
                "components": [
                    {
                        "type": "a2ui.Button",
                        "id": "btn-1",
                        "props": {},
                    }
                ],
            }
        )
        result = validate_a2ui_message(json_string)
        assert result["valid"] is True

    def test_invalid_json_string(self):
        """Test invalid JSON string"""
        result = validate_a2ui_message("{ invalid json }")
        assert result["valid"] is False
        assert any("Invalid JSON" in e for e in result["errors"])

    def test_non_object_message(self):
        """Test non-object message"""
        result = validate_a2ui_message("[]")
        assert result["valid"] is False
        assert any("Message must be a JSON object" in e for e in result["errors"])

    def test_flat_list_structure(self):
        """Test flat list structure (LLM-friendly)"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {"type": "a2ui.Container", "id": "c1", "props": {}, "children": ["c2"]},
                {"type": "a2ui.Container", "id": "c2", "props": {}, "children": ["b1"]},
                {"type": "a2ui.Button", "id": "b1", "props": {}},
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is True


class TestFileValidation:
    """Test file-based validation"""

    def test_validate_valid_file(self):
        """Test validating valid JSON file"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Button",
                    "id": "btn-1",
                    "props": {"text": "Click"},
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(message, f)
            temp_file = f.name

        try:
            result = validate_a2ui_file(temp_file)
            assert result["valid"] is True
        finally:
            Path(temp_file).unlink()

    def test_validate_invalid_file(self):
        """Test validating invalid JSON file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            temp_file = f.name

        try:
            result = validate_a2ui_file(temp_file)
            assert result["valid"] is False
        finally:
            Path(temp_file).unlink()

    def test_validate_missing_file(self):
        """Test validating non-existent file"""
        result = validate_a2ui_file("/tmp/non_existent_file.json")
        assert result["valid"] is False
        assert any("File not found" in e for e in result["errors"])


class TestStrictMode:
    """Test strict mode validation"""

    def test_warnings_fail_in_strict_mode(self):
        """Test warnings cause failure in strict mode"""
        validator = A2UIValidator(strict=True)
        message = {
            "messageType": "beginRendering",
            "components": [],  # This generates a warning
        }
        result = validator.validate_message(message)
        assert result.valid is False
        assert len(result.warnings) > 0

    def test_warnings_pass_in_normal_mode(self):
        """Test warnings don't cause failure in normal mode"""
        validator = A2UIValidator(strict=False)
        message = {
            "messageType": "beginRendering",
            "components": [],
        }
        result = validator.validate_message(message)
        assert result.valid is True
        assert len(result.warnings) > 0


class TestLogging:
    """Test validation logging"""

    def test_log_file_created(self):
        """Test validation log file is created"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = str(Path(tmpdir) / "test.log")
            validator = A2UIValidator(log_file=log_file)

            message = {
                "messageType": "beginRendering",
                "components": [
                    {"type": "a2ui.Button", "id": "btn-1", "props": {}}
                ],
            }
            validator.validate_message(message)

            assert Path(log_file).exists()

    def test_errors_logged(self):
        """Test errors are logged to file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = str(Path(tmpdir) / "test.log")
            validator = A2UIValidator(log_file=log_file)

            message = {
                "messageType": "invalid",
                "components": [],
            }
            validator.validate_message(message)

            log_content = Path(log_file).read_text()
            assert "FAILED" in log_content


class TestSecurityConstraints:
    """Test security constraints"""

    def test_prevents_script_injection_via_component_type(self):
        """Test component type validation prevents injection"""
        malicious_types = [
            "a2ui.Script",
            "a2ui.Eval",
            "<script>alert('xss')</script>",
            "../../../etc/passwd",
        ]

        for malicious_type in malicious_types:
            message = {
                "messageType": "beginRendering",
                "components": [
                    {
                        "type": malicious_type,
                        "id": "test-1",
                        "props": {},
                    }
                ],
            }
            result = validate_a2ui_message(message)
            assert result["valid"] is False, f"Failed to block: {malicious_type}"

    def test_catalog_is_whitelist_not_blacklist(self):
        """Test catalog uses allowlist approach (more secure)"""
        validator = A2UIValidator()

        # Only explicitly allowed types should pass
        assert validator.is_component_type_allowed("a2ui.Button")
        assert not validator.is_component_type_allowed("a2ui.UnknownComponent")
        assert not validator.is_component_type_allowed("anything.else")


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_components_array(self):
        """Test empty components array generates warning"""
        message = {
            "messageType": "beginRendering",
            "components": [],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is True
        assert "warnings" in result
        assert any("no components" in w for w in result["warnings"])

    def test_deeply_nested_references(self):
        """Test deeply nested component references"""
        components = [
            {"type": "a2ui.Container", "id": f"c{i}", "props": {}, "children": [f"c{i+1}"]}
            for i in range(10)
        ]
        components.append({"type": "a2ui.Button", "id": "c10", "props": {}})

        message = {
            "messageType": "beginRendering",
            "components": components,
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is True

    def test_complex_props(self):
        """Test complex nested props"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Card",
                    "id": "card-1",
                    "props": {
                        "title": "Test",
                        "data": {
                            "nested": {
                                "deep": {
                                    "value": [1, 2, 3],
                                }
                            }
                        },
                        "config": {
                            "enabled": True,
                            "count": 42,
                        },
                    },
                }
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is True

    def test_unicode_in_props(self):
        """Test unicode characters in props"""
        message = {
            "messageType": "beginRendering",
            "components": [
                {
                    "type": "a2ui.Text",
                    "id": "text-1",
                    "props": {
                        "content": "Hello 世界 🌍",
                    },
                }
            ],
        }
        result = validate_a2ui_message(message)
        assert result["valid"] is True


class TestHelperFunctions:
    """Test helper functions"""

    def test_is_component_type_allowed(self):
        """Test is_component_type_allowed helper"""
        validator = A2UIValidator()
        assert validator.is_component_type_allowed("a2ui.Button") is True
        assert validator.is_component_type_allowed("a2ui.Invalid") is False

    def test_get_allowed_component_types(self):
        """Test get_allowed_component_types helper"""
        validator = A2UIValidator()
        types = validator.get_allowed_component_types()
        assert isinstance(types, list)
        assert "a2ui.Button" in types
        assert len(types) == len(A2UI_COMPONENT_TYPES)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
