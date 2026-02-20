"""Tests for AI-209 Documentation Completeness.

Verifies that:
- All key modules have module-level docstrings
- All public functions and methods have docstrings with content
- docs/api/ directory exists with all expected files
- Docstrings contain usage examples where required
- Bridge interface methods are documented
- Exception classes have docstrings with usage examples
- scripts/generate_api_docs.sh exists and is executable
"""
import ast
import os
import stat
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(path: Path) -> ast.Module:
    """Return parsed AST for the given Python file."""
    return ast.parse(path.read_text())


def _public_functions(tree: ast.Module):
    """Yield (name, node) for all top-level public function defs."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                yield node.name, node


def _public_methods(cls_node: ast.ClassDef):
    """Yield (name, node) for public method defs in a class node."""
    for node in cls_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                yield node.name, node


def _class_nodes(tree: ast.Module):
    """Yield top-level ClassDef nodes."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            yield node


# ---------------------------------------------------------------------------
# 1. Module-level docstrings
# ---------------------------------------------------------------------------

class TestModuleDocstrings:
    """Every key module must have a non-trivial module-level docstring."""

    @pytest.mark.parametrize("rel_path", [
        "bridges/base_bridge.py",
        "config.py",
        "protocols.py",
        "exceptions.py",
    ])
    def test_module_has_docstring(self, rel_path):
        path = PROJECT_ROOT / rel_path
        assert path.exists(), f"{rel_path} does not exist"
        tree = _parse(path)
        docstring = ast.get_docstring(tree)
        assert docstring, f"{rel_path} is missing a module-level docstring"
        assert len(docstring) > 30, (
            f"{rel_path} module docstring is too short: {docstring!r}"
        )

    @pytest.mark.parametrize("rel_path,keyword", [
        ("bridges/base_bridge.py", "Example"),
        ("config.py", "example"),
        ("protocols.py", "example"),
        ("exceptions.py", "Usage"),
    ])
    def test_module_docstring_contains_example(self, rel_path, keyword):
        path = PROJECT_ROOT / rel_path
        assert path.exists()
        tree = _parse(path)
        docstring = ast.get_docstring(tree) or ""
        assert keyword.lower() in docstring.lower(), (
            f"{rel_path} module docstring should contain '{keyword}'"
        )


# ---------------------------------------------------------------------------
# 2. BridgeResponse docstring
# ---------------------------------------------------------------------------

class TestBridgeResponseDocstring:
    """BridgeResponse dataclass must be fully documented."""

    def test_bridge_response_class_docstring(self):
        path = PROJECT_ROOT / "bridges/base_bridge.py"
        tree = _parse(path)
        for cls in _class_nodes(tree):
            if cls.name == "BridgeResponse":
                docstring = ast.get_docstring(cls)
                assert docstring, "BridgeResponse is missing a class docstring"
                assert len(docstring) > 50
                return
        pytest.fail("BridgeResponse class not found in base_bridge.py")

    def test_bridge_response_docstring_contains_example(self):
        path = PROJECT_ROOT / "bridges/base_bridge.py"
        tree = _parse(path)
        for cls in _class_nodes(tree):
            if cls.name == "BridgeResponse":
                docstring = ast.get_docstring(cls) or ""
                assert "example" in docstring.lower() or "Example" in docstring


# ---------------------------------------------------------------------------
# 3. BaseBridge method docstrings
# ---------------------------------------------------------------------------

class TestBaseBridgeDocstrings:
    """Every public method of BaseBridge must be documented."""

    @pytest.fixture(scope="class")
    def base_bridge_cls(self):
        path = PROJECT_ROOT / "bridges/base_bridge.py"
        tree = _parse(path)
        for cls in _class_nodes(tree):
            if cls.name == "BaseBridge":
                return cls
        pytest.fail("BaseBridge class not found")

    def test_base_bridge_class_docstring(self, base_bridge_cls):
        docstring = ast.get_docstring(base_bridge_cls)
        assert docstring, "BaseBridge is missing a class docstring"
        assert "example" in docstring.lower() or "Example" in docstring

    @pytest.mark.parametrize("method_name", [
        "provider_name",
        "send_task",
        "get_auth_info",
        "validate_response",
    ])
    def test_bridge_method_has_docstring(self, base_bridge_cls, method_name):
        for name, node in _public_methods(base_bridge_cls):
            if name == method_name:
                docstring = ast.get_docstring(node)
                assert docstring, f"BaseBridge.{method_name} is missing a docstring"
                assert len(docstring) > 20
                return
        pytest.fail(f"BaseBridge.{method_name} not found")

    @pytest.mark.parametrize("method_name,keyword", [
        ("send_task", "Args"),
        ("send_task", "Returns"),
        ("get_auth_info", "Returns"),
        ("validate_response", "Returns"),
        ("validate_response", "example"),
    ])
    def test_bridge_method_docstring_has_section(self, base_bridge_cls, method_name, keyword):
        for name, node in _public_methods(base_bridge_cls):
            if name == method_name:
                docstring = ast.get_docstring(node) or ""
                assert keyword.lower() in docstring.lower(), (
                    f"BaseBridge.{method_name} docstring should contain '{keyword}'"
                )
                return
        pytest.fail(f"BaseBridge.{method_name} not found")


# ---------------------------------------------------------------------------
# 4. AgentConfig docstrings
# ---------------------------------------------------------------------------

class TestAgentConfigDocstrings:
    """AgentConfig and its key methods must be documented."""

    @pytest.fixture(scope="class")
    def config_tree(self):
        return _parse(PROJECT_ROOT / "config.py")

    def test_agent_config_class_docstring(self, config_tree):
        for cls in _class_nodes(config_tree):
            if cls.name == "AgentConfig":
                docstring = ast.get_docstring(cls)
                assert docstring, "AgentConfig is missing a class docstring"
                return
        pytest.fail("AgentConfig not found in config.py")

    @pytest.mark.parametrize("func_name", [
        "get_config",
        "reset_config",
    ])
    def test_config_public_function_has_docstring(self, config_tree, func_name):
        for name, node in _public_functions(config_tree):
            if name == func_name:
                docstring = ast.get_docstring(node)
                assert docstring, f"{func_name} is missing a docstring"
                assert len(docstring) > 20
                return
        pytest.fail(f"{func_name} not found in config.py")

    @pytest.mark.parametrize("func_name", [
        "get_config",
        "reset_config",
    ])
    def test_config_function_docstring_has_example(self, config_tree, func_name):
        for name, node in _public_functions(config_tree):
            if name == func_name:
                docstring = ast.get_docstring(node) or ""
                assert "example" in docstring.lower(), (
                    f"{func_name} docstring should contain an example"
                )
                return


# ---------------------------------------------------------------------------
# 5. Exception class docstrings
# ---------------------------------------------------------------------------

class TestExceptionDocstrings:
    """Every exception class must have a docstring with a usage example."""

    @pytest.fixture(scope="class")
    def exc_tree(self):
        return _parse(PROJECT_ROOT / "exceptions.py")

    @pytest.mark.parametrize("class_name", [
        "AgentError",
        "BridgeError",
        "SecurityError",
        "ConfigurationError",
        "TimeoutError",
        "RateLimitError",
        "AuthenticationError",
    ])
    def test_exception_class_has_docstring(self, exc_tree, class_name):
        for cls in _class_nodes(exc_tree):
            if cls.name == class_name:
                docstring = ast.get_docstring(cls)
                assert docstring, f"{class_name} is missing a class docstring"
                assert len(docstring) > 30
                return
        pytest.fail(f"{class_name} not found in exceptions.py")

    @pytest.mark.parametrize("class_name", [
        "AgentError",
        "BridgeError",
        "SecurityError",
        "ConfigurationError",
        "TimeoutError",
        "RateLimitError",
        "AuthenticationError",
    ])
    def test_exception_class_docstring_has_example(self, exc_tree, class_name):
        for cls in _class_nodes(exc_tree):
            if cls.name == class_name:
                docstring = ast.get_docstring(cls) or ""
                assert "example" in docstring.lower(), (
                    f"{class_name} docstring should contain an Example section"
                )
                return


# ---------------------------------------------------------------------------
# 6. protocols.py docstrings
# ---------------------------------------------------------------------------

class TestProtocolDocstrings:
    """Protocol classes must be documented with examples."""

    @pytest.fixture(scope="class")
    def proto_tree(self):
        return _parse(PROJECT_ROOT / "protocols.py")

    @pytest.mark.parametrize("class_name", [
        "BridgeProtocol",
        "ConfigProtocol",
        "ProgressTrackerProtocol",
        "ExceptionProtocol",
    ])
    def test_protocol_class_has_docstring(self, proto_tree, class_name):
        for cls in _class_nodes(proto_tree):
            if cls.name == class_name:
                docstring = ast.get_docstring(cls)
                assert docstring, f"{class_name} is missing a class docstring"
                return
        pytest.fail(f"{class_name} not found in protocols.py")

    @pytest.mark.parametrize("class_name", [
        "BridgeProtocol",
        "ConfigProtocol",
        "ProgressTrackerProtocol",
        "ExceptionProtocol",
    ])
    def test_protocol_class_has_example(self, proto_tree, class_name):
        for cls in _class_nodes(proto_tree):
            if cls.name == class_name:
                docstring = ast.get_docstring(cls) or ""
                assert "example" in docstring.lower(), (
                    f"{class_name} docstring should contain an Example"
                )
                return


# ---------------------------------------------------------------------------
# 7. docs/api/ directory and files
# ---------------------------------------------------------------------------

class TestDocsApiDirectory:
    """The docs/api/ directory must exist with all expected documentation files."""

    @pytest.fixture(scope="class")
    def api_dir(self):
        return PROJECT_ROOT / "docs" / "api"

    def test_docs_api_directory_exists(self, api_dir):
        assert api_dir.exists(), "docs/api/ directory does not exist"
        assert api_dir.is_dir(), "docs/api/ is not a directory"

    @pytest.mark.parametrize("filename", [
        "README.md",
        "bridges.md",
        "config.md",
        "exceptions.md",
        "protocols.md",
    ])
    def test_api_doc_file_exists(self, api_dir, filename):
        target = api_dir / filename
        assert target.exists(), f"docs/api/{filename} does not exist"
        assert target.is_file()

    @pytest.mark.parametrize("filename,keyword", [
        ("README.md", "BaseBridge"),
        ("README.md", "AgentConfig"),
        ("bridges.md", "BridgeResponse"),
        ("bridges.md", "send_task"),
        ("config.md", "AgentConfig"),
        ("config.md", "get_config"),
        ("exceptions.md", "AgentError"),
        ("exceptions.md", "is_retryable"),
        ("protocols.md", "BridgeProtocol"),
        ("protocols.md", "isinstance"),
    ])
    def test_api_doc_file_contains_keyword(self, api_dir, filename, keyword):
        content = (api_dir / filename).read_text()
        assert keyword in content, (
            f"docs/api/{filename} should mention '{keyword}'"
        )

    @pytest.mark.parametrize("filename", [
        "bridges.md",
        "config.md",
        "exceptions.md",
        "protocols.md",
    ])
    def test_api_doc_has_code_block(self, api_dir, filename):
        content = (api_dir / filename).read_text()
        assert "```python" in content, (
            f"docs/api/{filename} should have at least one Python code block"
        )


# ---------------------------------------------------------------------------
# 8. scripts/generate_api_docs.sh
# ---------------------------------------------------------------------------

class TestGenerateApiDocsScript:
    """The generate_api_docs.sh script must exist and be executable."""

    @pytest.fixture(scope="class")
    def script_path(self):
        return PROJECT_ROOT / "scripts" / "generate_api_docs.sh"

    def test_script_exists(self, script_path):
        assert script_path.exists(), "scripts/generate_api_docs.sh does not exist"
        assert script_path.is_file()

    def test_script_is_executable(self, script_path):
        mode = script_path.stat().st_mode
        assert bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)), (
            "scripts/generate_api_docs.sh is not executable"
        )

    def test_script_contains_pdoc(self, script_path):
        content = script_path.read_text()
        assert "pdoc" in content, "generate_api_docs.sh should invoke pdoc"

    def test_script_has_shebang(self, script_path):
        content = script_path.read_text()
        assert content.startswith("#!/"), (
            "generate_api_docs.sh should start with a shebang line"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
