"""
A2UI Protocol Validator (Python)

Validates A2UI messages against v0.8 specification.
Ensures JSON structure, required fields, component catalog compliance, and security constraints.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
from datetime import datetime
from pathlib import Path


class A2UIMessageType(str, Enum):
    """Message types supported by A2UI protocol v0.8"""

    BEGIN_RENDERING = "beginRendering"
    SURFACE_UPDATE = "surfaceUpdate"
    DATA_MODEL_UPDATE = "dataModelUpdate"


# Component types registered in A2UI catalog (security constraint)
A2UI_COMPONENT_TYPES = [
    "a2ui.Button",
    "a2ui.Card",
    "a2ui.Text",
    "a2ui.Input",
    "a2ui.Container",
    "a2ui.Grid",
    "a2ui.Badge",
    "a2ui.Divider",
]


class ValidationResult:
    """Result of A2UI validation"""

    def __init__(self, valid: bool = True):
        self.valid = valid
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.message: Optional[Dict[str, Any]] = None

    def add_error(self, error: str) -> None:
        """Add validation error"""
        self.errors.append(error)
        self.valid = False

    def add_warning(self, warning: str) -> None:
        """Add validation warning"""
        self.warnings.append(warning)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "valid": self.valid,
            "errors": self.errors,
        }
        if self.warnings:
            result["warnings"] = self.warnings
        if self.message:
            result["message"] = self.message
        return result


class A2UIValidator:
    """A2UI Protocol Validator"""

    def __init__(
        self,
        log_file: Optional[str] = None,
        strict: bool = False,
        allow_unknown_types: bool = False,
        custom_catalog: Optional[List[str]] = None,
    ):
        """
        Initialize validator

        Args:
            log_file: Path to validation log file (default: agent/a2ui_validation.log)
            strict: Strict mode - treat warnings as errors
            allow_unknown_types: Allow unknown component types (UNSAFE - testing only)
            custom_catalog: Custom component type allowlist
        """
        self.strict = strict
        self.allow_unknown_types = allow_unknown_types
        self.catalog = custom_catalog if custom_catalog else A2UI_COMPONENT_TYPES

        # Setup logging
        if log_file is None:
            log_file = str(Path(__file__).parent / "a2ui_validation.log")

        self.log_file = log_file
        self.logger = self._setup_logger(log_file)

    def _setup_logger(self, log_file: str) -> logging.Logger:
        """Setup validation logger"""
        logger = logging.getLogger("a2ui_validator")
        logger.setLevel(logging.DEBUG)

        # File handler
        fh = logging.FileHandler(log_file, mode="a")
        fh.setLevel(logging.DEBUG)

        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(formatter)

        logger.addHandler(fh)
        return logger

    def validate_message(self, message: Any) -> ValidationResult:
        """
        Validate A2UI message against v0.8 specification

        Args:
            message: Message to validate (dict or JSON string)

        Returns:
            ValidationResult with errors/warnings
        """
        result = ValidationResult()

        # Parse JSON if string
        if isinstance(message, str):
            try:
                message = json.loads(message)
            except json.JSONDecodeError as e:
                result.add_error(f"Invalid JSON: {str(e)}")
                self.logger.error(f"JSON parsing failed: {str(e)}")
                return result

        # Check if message is a dict
        if not isinstance(message, dict):
            result.add_error("Message must be a JSON object")
            self.logger.error("Message is not a dict")
            return result

        # Validate messageType
        if "messageType" not in message:
            result.add_error("Missing required field: messageType")
        else:
            message_type = message["messageType"]
            if message_type not in [t.value for t in A2UIMessageType]:
                result.add_error(
                    f'Invalid messageType: "{message_type}". '
                    f"Must be one of: {', '.join(t.value for t in A2UIMessageType)}"
                )

        # Validate components array
        if "components" not in message:
            result.add_error("Missing required field: components")
        elif not isinstance(message["components"], list):
            result.add_error("Field 'components' must be an array")
        else:
            components = message["components"]
            component_ids: Set[str] = set()

            # Validate each component
            for index, component in enumerate(components):
                self._validate_component(
                    component, index, result, component_ids
                )

            # Validate child references
            for component in components:
                if "children" in component and isinstance(component["children"], list):
                    for child_id in component["children"]:
                        if child_id not in component_ids:
                            result.add_error(
                                f'Component "{component.get("id", "unknown")}" '
                                f'references non-existent child: "{child_id}"'
                            )

            # Check for circular references
            circular_errors = self._detect_circular_references(components)
            for error in circular_errors:
                result.add_error(error)

        # Warnings
        if "components" in message and len(message["components"]) == 0:
            result.add_warning("Message contains no components")

        # Apply strict mode
        if self.strict and result.warnings:
            result.valid = False

        # Store validated message if valid
        if result.valid:
            result.message = message

        # Log result
        self.logger.info(
            f"Validation {'PASSED' if result.valid else 'FAILED'} "
            f"- Errors: {len(result.errors)}, Warnings: {len(result.warnings)}"
        )
        if not result.valid:
            for error in result.errors:
                self.logger.error(f"  - {error}")

        return result

    def _validate_component(
        self,
        component: Any,
        index: int,
        result: ValidationResult,
        component_ids: Set[str],
    ) -> None:
        """Validate a single component"""
        prefix = f"Component[{index}]"

        # Check if component is a dict
        if not isinstance(component, dict):
            result.add_error(f"{prefix}: Must be an object")
            return

        # Validate required field: type
        if "type" not in component:
            result.add_error(f'{prefix}: Missing required field "type"')
        elif not isinstance(component["type"], str):
            result.add_error(f'{prefix}: Field "type" must be a string')
        else:
            component_type = component["type"]

            # Validate component type is in catalog (SECURITY CHECK)
            if not self.allow_unknown_types and component_type not in self.catalog:
                result.add_error(
                    f'{prefix}: Invalid component type "{component_type}". '
                    f"Not in registered catalog. Allowed types: {', '.join(self.catalog)}"
                )
                self.logger.warning(
                    f"SECURITY: Attempt to use unauthorized component type: {component_type}"
                )

        # Validate required field: id
        if "id" not in component:
            result.add_error(f'{prefix}: Missing required field "id"')
        elif not isinstance(component["id"], str):
            result.add_error(f'{prefix}: Field "id" must be a string')
        elif not component["id"].strip():
            result.add_error(f'{prefix}: Field "id" cannot be empty')
        else:
            component_id = component["id"]

            # Check for duplicate IDs
            if component_id in component_ids:
                result.add_error(f'Duplicate component ID: "{component_id}"')
            else:
                component_ids.add(component_id)

        # Validate required field: props
        if "props" not in component:
            result.add_error(f'{prefix}: Missing required field "props"')
        elif not isinstance(component["props"], dict):
            result.add_error(f'{prefix}: Field "props" must be an object')

        # Validate optional field: children
        if "children" in component:
            children = component["children"]
            if not isinstance(children, list):
                result.add_error(f'{prefix}: Field "children" must be an array of strings')
            else:
                for child_index, child in enumerate(children):
                    if not isinstance(child, str):
                        result.add_error(
                            f"{prefix}: children[{child_index}] must be a string (component ID)"
                        )

    def _detect_circular_references(self, components: List[Dict[str, Any]]) -> List[str]:
        """Detect circular references in component tree"""
        errors: List[str] = []
        component_map = {c["id"]: c for c in components if "id" in c}

        for component in components:
            if "children" not in component or not component.get("id"):
                continue

            visited: Set[str] = set()
            stack = [component["id"]]

            while stack:
                current_id = stack.pop()

                if current_id in visited:
                    errors.append(
                        f'Circular reference detected involving component "{current_id}"'
                    )
                    break

                visited.add(current_id)
                current = component_map.get(current_id)

                if current and "children" in current:
                    for child_id in current["children"]:
                        if child_id == component["id"]:
                            errors.append(
                                f'Circular reference: Component "{component["id"]}" '
                                f'references itself through child "{current_id}"'
                            )
                        else:
                            stack.append(child_id)

        return errors

    def validate_file(self, file_path: str) -> ValidationResult:
        """
        Validate A2UI message from JSON file

        Args:
            file_path: Path to JSON file

        Returns:
            ValidationResult
        """
        self.logger.info(f"Validating file: {file_path}")

        try:
            with open(file_path, "r") as f:
                message = json.load(f)
            return self.validate_message(message)
        except FileNotFoundError:
            result = ValidationResult()
            result.add_error(f"File not found: {file_path}")
            self.logger.error(f"File not found: {file_path}")
            return result
        except json.JSONDecodeError as e:
            result = ValidationResult()
            result.add_error(f"Invalid JSON in file: {str(e)}")
            self.logger.error(f"JSON parsing failed for {file_path}: {str(e)}")
            return result

    def is_component_type_allowed(self, component_type: str) -> bool:
        """
        Check if component type is in registered catalog

        Args:
            component_type: Component type to check

        Returns:
            True if allowed, False otherwise
        """
        return component_type in self.catalog

    def get_allowed_component_types(self) -> List[str]:
        """Get list of all allowed component types"""
        return list(self.catalog)


def validate_a2ui_message(
    message: Any,
    strict: bool = False,
    log_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function to validate A2UI message

    Args:
        message: Message to validate (dict or JSON string)
        strict: Strict mode (treat warnings as errors)
        log_file: Path to log file

    Returns:
        Validation result as dictionary
    """
    validator = A2UIValidator(log_file=log_file, strict=strict)
    result = validator.validate_message(message)
    return result.to_dict()


def validate_a2ui_file(
    file_path: str,
    strict: bool = False,
    log_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function to validate A2UI message from file

    Args:
        file_path: Path to JSON file
        strict: Strict mode (treat warnings as errors)
        log_file: Path to log file

    Returns:
        Validation result as dictionary
    """
    validator = A2UIValidator(log_file=log_file, strict=strict)
    result = validator.validate_file(file_path)
    return result.to_dict()
