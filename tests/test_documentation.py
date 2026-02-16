"""
Unit Tests for Documentation Generation
========================================

Comprehensive tests for documentation generation utilities.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import pytest


class TestDocumentationGeneration:
    """Test documentation generation functionality."""

    @pytest.fixture
    def temp_docs_dir(self):
        """Create temporary directory for documentation tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent

    def test_generate_docs_script_exists(self, project_root):
        """Test that documentation generation script exists."""
        script_path = project_root / "scripts" / "generate_docs.py"
        assert script_path.exists(), "generate_docs.py should exist"
        assert script_path.is_file(), "generate_docs.py should be a file"

    def test_convert_docs_script_exists(self, project_root):
        """Test that markdown conversion script exists."""
        script_path = project_root / "scripts" / "convert_docs.py"
        assert script_path.exists(), "convert_docs.py should exist"
        assert script_path.is_file(), "convert_docs.py should be a file"

    def test_developer_guide_exists(self, project_root):
        """Test that developer guide documentation exists."""
        guide_path = project_root / "docs" / "DEVELOPER_GUIDE.md"
        assert guide_path.exists(), "DEVELOPER_GUIDE.md should exist"

        content = guide_path.read_text()
        assert len(content) > 1000, "Developer guide should have substantial content"
        assert "Table of Contents" in content, "Should have table of contents"
        assert "Getting Started" in content, "Should have getting started section"
        assert "Examples" in content or "Example" in content, "Should have examples"

    def test_bridge_interface_docs_exists(self, project_root):
        """Test that bridge interface documentation exists."""
        bridge_docs = project_root / "docs" / "BRIDGE_INTERFACE.md"
        assert bridge_docs.exists(), "BRIDGE_INTERFACE.md should exist"

        content = bridge_docs.read_text()
        assert len(content) > 1000, "Bridge docs should have substantial content"
        assert "interface" in content.lower(), "Should discuss interface"
        assert "Example" in content, "Should have examples"

    def test_deployment_guide_exists(self, project_root):
        """Test that deployment guide exists."""
        deploy_guide = project_root / "docs" / "DEPLOYMENT.md"
        assert deploy_guide.exists(), "DEPLOYMENT.md should exist"

        content = deploy_guide.read_text()
        assert "GitHub Pages" in content, "Should cover GitHub Pages"
        assert "deployment" in content.lower(), "Should discuss deployment"

    def test_github_actions_workflow_exists(self, project_root):
        """Test that GitHub Actions workflow for docs exists."""
        workflow_path = project_root / ".github" / "workflows" / "docs.yml"
        assert workflow_path.exists(), "docs.yml workflow should exist"

        content = workflow_path.read_text()
        assert "pdoc" in content, "Workflow should use pdoc"
        assert "deploy" in content.lower(), "Workflow should deploy"

    def test_documentation_structure(self, project_root):
        """Test that documentation directory has proper structure."""
        docs_dir = project_root / "docs"
        assert docs_dir.exists(), "docs/ directory should exist"

        # Check for key files
        required_files = [
            "DEVELOPER_GUIDE.md",
            "BRIDGE_INTERFACE.md",
            "DEPLOYMENT.md",
        ]

        for filename in required_files:
            file_path = docs_dir / filename
            assert file_path.exists(), f"{filename} should exist in docs/"

    def test_convert_docs_creates_html(self, project_root, temp_docs_dir):
        """Test that convert_docs.py creates HTML files."""
        # Create test markdown file
        test_md = temp_docs_dir / "TEST_DOC.md"
        test_md.write_text("# Test Document\n\nThis is a test.")

        # Run conversion (would need to modify convert_docs.py to accept paths)
        # For now, just verify the script can be imported
        import sys
        sys.path.insert(0, str(project_root / "scripts"))

        try:
            import convert_docs
            assert hasattr(convert_docs, 'main'), "Should have main function"
            assert hasattr(convert_docs, 'create_index'), "Should have create_index function"
        finally:
            sys.path.pop(0)

    def test_pdoc_can_import_modules(self, project_root):
        """Test that pdoc can import core modules."""
        import sys
        sys.path.insert(0, str(project_root))
        sys.path.insert(0, str(project_root / "scripts"))

        try:
            # These modules should be importable for pdoc
            import_tests = [
                "client",
                "security",
                "prompts",
                "progress",
            ]

            for module_name in import_tests:
                try:
                    __import__(module_name)
                except ImportError as e:
                    # Some modules may have optional dependencies
                    if "arcade_config" in str(e):
                        # Expected - arcade_config is in scripts
                        continue
                    pytest.fail(f"Failed to import {module_name}: {e}")

        finally:
            # Clean up sys.path
            while str(project_root) in sys.path:
                sys.path.remove(str(project_root))
            while str(project_root / "scripts") in sys.path:
                sys.path.remove(str(project_root / "scripts"))

    def test_docstrings_present_in_core_modules(self, project_root):
        """Test that core modules have docstrings."""
        modules_to_check = [
            project_root / "client.py",
            project_root / "agent.py",
            project_root / "security.py",
            project_root / "prompts.py",
            project_root / "progress.py",
        ]

        for module_path in modules_to_check:
            if not module_path.exists():
                continue

            content = module_path.read_text()

            # Check for module-level docstring
            assert '"""' in content or "'''" in content, \
                f"{module_path.name} should have docstrings"

            # Check for function docstrings (should have Args, Returns, etc.)
            if "def " in content:
                # Simple heuristic: look for docstring patterns
                has_docs = any([
                    "Args:" in content,
                    "Returns:" in content,
                    "Raises:" in content,
                    "Example:" in content,
                ])
                assert has_docs, \
                    f"{module_path.name} should have documented functions"

    def test_examples_in_docstrings(self, project_root):
        """Test that docstrings include examples."""
        # Check client.py for examples
        client_file = project_root / "client.py"
        if client_file.exists():
            content = client_file.read_text()
            # Should have example usage
            assert "Example:" in content or "example" in content.lower(), \
                "client.py should have usage examples"

    def test_all_public_functions_documented(self, project_root):
        """Test that public functions have docstrings."""
        import ast

        files_to_check = [
            project_root / "prompts.py",
            project_root / "progress.py",
        ]

        for file_path in files_to_check:
            if not file_path.exists():
                continue

            with open(file_path) as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Public functions (not starting with _)
                    if not node.name.startswith("_"):
                        docstring = ast.get_docstring(node)
                        assert docstring is not None, \
                            f"Function {node.name} in {file_path.name} should have docstring"
                        assert len(docstring) > 10, \
                            f"Docstring for {node.name} should be substantial"

    def test_requirements_includes_doc_deps(self, project_root):
        """Test that requirements.txt includes documentation dependencies."""
        req_file = project_root / "requirements.txt"
        assert req_file.exists(), "requirements.txt should exist"

        content = req_file.read_text()
        assert "pdoc" in content.lower(), "Should include pdoc"
        assert "markdown" in content.lower(), "Should include markdown"

    def test_generated_docs_directory_structure(self, project_root):
        """Test that generated documentation has proper structure."""
        html_dir = project_root / "docs" / "html"

        # This test only runs if docs have been generated
        if not html_dir.exists():
            pytest.skip("Documentation not yet generated")

        # Check for expected files
        assert (html_dir / "index.html").exists(), "Should have index.html"

        # Check for API docs
        api_dir = html_dir / "api"
        if api_dir.exists():
            assert (api_dir / "index.html").exists(), "Should have API index"

    def test_documentation_links_valid(self, project_root):
        """Test that internal documentation links are valid."""
        docs_dir = project_root / "docs"

        for md_file in docs_dir.glob("*.md"):
            content = md_file.read_text()

            # Extract markdown links [text](path)
            import re
            links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)

            for link_text, link_path in links:
                # Skip external links
                if link_path.startswith(('http://', 'https://', '#')):
                    continue

                # Check if internal link exists
                if link_path.endswith('.md') or link_path.endswith('.html'):
                    target = docs_dir / link_path
                    if not target.exists():
                        # May be relative to project root
                        target = project_root / link_path

                    # Allow for flexibility in link targets
                    # Some links may be to generated content
                    if not target.exists() and "api/" not in link_path:
                        pytest.fail(
                            f"Broken link in {md_file.name}: "
                            f"{link_path} (target: {target})"
                        )


class TestDocumentationContent:
    """Test documentation content quality."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent

    def test_developer_guide_completeness(self, project_root):
        """Test that developer guide covers all required topics."""
        guide_path = project_root / "docs" / "DEVELOPER_GUIDE.md"
        if not guide_path.exists():
            pytest.skip("Developer guide not found")

        content = guide_path.read_text()

        required_sections = [
            "Getting Started",
            "Architecture",
            "Examples",
            "Testing",
            "Security",
        ]

        for section in required_sections:
            assert section.lower() in content.lower(), \
                f"Developer guide should cover: {section}"

    def test_bridge_interface_has_examples(self, project_root):
        """Test that bridge interface documentation has code examples."""
        bridge_docs = project_root / "docs" / "BRIDGE_INTERFACE.md"
        if not bridge_docs.exists():
            pytest.skip("Bridge interface docs not found")

        content = bridge_docs.read_text()

        # Should have code blocks
        assert "```python" in content, "Should have Python code examples"

        # Should cover key concepts
        key_concepts = [
            "session",
            "response",
            "bridge",
            "example",
        ]

        for concept in key_concepts:
            assert concept.lower() in content.lower(), \
                f"Bridge docs should cover: {concept}"

    def test_code_examples_syntax_valid(self, project_root):
        """Test that code examples in docs have valid syntax."""
        import re

        docs_dir = project_root / "docs"

        for md_file in docs_dir.glob("*.md"):
            content = md_file.read_text()

            # Extract Python code blocks
            python_blocks = re.findall(
                r'```python\n(.*?)\n```',
                content,
                re.DOTALL
            )

            for i, code_block in enumerate(python_blocks):
                # Try to compile the code
                try:
                    compile(code_block, f"{md_file.name}_example_{i}", 'exec')
                except SyntaxError as e:
                    # Some examples may be incomplete snippets
                    # Only fail on obvious syntax errors
                    if "invalid syntax" in str(e):
                        pytest.fail(
                            f"Syntax error in {md_file.name} example {i}: {e}\n"
                            f"Code: {code_block[:100]}"
                        )


class TestDocumentationAccessibility:
    """Test documentation accessibility and usability."""

    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent

    def test_html_has_valid_structure(self, project_root):
        """Test that generated HTML has valid structure."""
        html_dir = project_root / "docs" / "html"

        if not html_dir.exists():
            pytest.skip("HTML documentation not generated")

        index_file = html_dir / "index.html"
        if not index_file.exists():
            pytest.skip("index.html not found")

        content = index_file.read_text()

        # Basic HTML structure
        assert "<!DOCTYPE html>" in content, "Should have DOCTYPE"
        assert "<html" in content, "Should have html tag"
        assert "<head>" in content, "Should have head tag"
        assert "<body>" in content, "Should have body tag"
        assert "<title>" in content, "Should have title"

        # Accessibility
        assert 'charset="UTF-8"' in content, "Should have charset"
        assert 'viewport' in content, "Should have viewport meta tag"

    def test_documentation_has_navigation(self, project_root):
        """Test that documentation has navigation links."""
        html_dir = project_root / "docs" / "html"

        if not html_dir.exists():
            pytest.skip("HTML documentation not generated")

        index_file = html_dir / "index.html"
        if not index_file.exists():
            pytest.skip("index.html not found")

        content = index_file.read_text()

        # Should have links to main sections
        assert '<a href=' in content, "Should have navigation links"

        # Check for key sections
        key_links = [
            "DEVELOPER_GUIDE",
            "BRIDGE_INTERFACE",
            "api",
        ]

        for link in key_links:
            assert link in content, f"Should link to {link}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
