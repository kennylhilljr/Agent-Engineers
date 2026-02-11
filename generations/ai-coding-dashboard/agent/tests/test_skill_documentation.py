"""
Unit tests for the Claude Code integration skill documentation

Tests validate:
- SKILL.md file exists and is readable
- All required sections are present
- API endpoint documentation is complete
- Event type examples are valid JSON
- Code examples are syntactically correct
"""

import os
import json
import re
import pytest
from pathlib import Path


# Path to the skill documentation
SKILL_PATH = Path(__file__).parent.parent.parent / ".claude" / "skills" / "coding-dashboard" / "SKILL.md"


class TestSkillDocumentation:
    """Test suite for SKILL.md documentation"""

    def test_skill_file_exists(self):
        """Test that SKILL.md exists at the correct path"""
        assert SKILL_PATH.exists(), f"SKILL.md not found at {SKILL_PATH}"

    def test_skill_file_readable(self):
        """Test that SKILL.md is readable"""
        assert SKILL_PATH.is_file(), "SKILL.md is not a file"
        content = SKILL_PATH.read_text()
        assert len(content) > 0, "SKILL.md is empty"

    def test_has_title(self):
        """Test that skill has a main title"""
        content = SKILL_PATH.read_text()
        assert re.search(r"^#\s+.*Integration Skill", content, re.MULTILINE), \
            "Missing main title with 'Integration Skill'"

    def test_has_overview_section(self):
        """Test that Overview section exists"""
        content = SKILL_PATH.read_text()
        assert "## Overview" in content, "Missing Overview section"

    def test_has_quick_start_section(self):
        """Test that Quick Start section exists"""
        content = SKILL_PATH.read_text()
        assert "## Quick Start" in content, "Missing Quick Start section"

    def test_has_api_endpoints_section(self):
        """Test that API Endpoints section exists"""
        content = SKILL_PATH.read_text()
        assert "## API Endpoints" in content, "Missing API Endpoints section"

    def test_has_event_types_section(self):
        """Test that Event Types section exists"""
        content = SKILL_PATH.read_text()
        assert "## Event Types" in content, "Missing Event Types section"

    def test_has_response_endpoints_section(self):
        """Test that Response Endpoints section exists"""
        content = SKILL_PATH.read_text()
        assert "## Response Endpoints" in content, "Missing Response Endpoints section"

    def test_has_typical_workflow_section(self):
        """Test that Typical Workflow section exists"""
        content = SKILL_PATH.read_text()
        assert "## Typical Workflow" in content, "Missing Typical Workflow section"

    def test_has_troubleshooting_section(self):
        """Test that Troubleshooting section exists"""
        content = SKILL_PATH.read_text()
        assert "## Troubleshooting" in content, "Missing Troubleshooting section"

    def test_has_claude_code_integration_section(self):
        """Test that Claude Code integration section exists"""
        content = SKILL_PATH.read_text()
        assert "## Integration with Claude Code" in content, \
            "Missing Integration with Claude Code section"

    def test_base_url_documented(self):
        """Test that base URL is documented"""
        content = SKILL_PATH.read_text()
        assert "http://localhost:8000" in content, "Base URL not documented"

    def test_all_event_types_documented(self):
        """Test that all required event types are documented"""
        content = SKILL_PATH.read_text()
        required_events = [
            "task_started",
            "task_completed",
            "decision_needed",
            "approval_needed",
            "error",
            "milestone",
            "file_changed",
            "activity"
        ]
        for event in required_events:
            assert event in content, f"Event type '{event}' not documented"

    def test_project_creation_endpoint_documented(self):
        """Test that project creation endpoint is documented"""
        content = SKILL_PATH.read_text()
        assert "POST" in content and "/api/projects" in content, \
            "Project creation endpoint not documented"

    def test_event_push_endpoint_documented(self):
        """Test that event push endpoint is documented"""
        content = SKILL_PATH.read_text()
        assert "POST" in content and "/api/events" in content, \
            "Event push endpoint not documented"

    def test_get_response_endpoint_documented(self):
        """Test that get response endpoint is documented"""
        content = SKILL_PATH.read_text()
        assert "GET" in content and "/api/responses/" in content, \
            "Get response endpoint not documented"

    def test_pending_endpoint_documented(self):
        """Test that pending responses endpoint is documented"""
        content = SKILL_PATH.read_text()
        assert "/api/responses/pending" in content, \
            "Pending responses endpoint not documented"

    def test_curl_examples_present(self):
        """Test that curl examples are present"""
        content = SKILL_PATH.read_text()
        curl_count = content.count("curl ")
        assert curl_count >= 10, \
            f"Expected at least 10 curl examples, found {curl_count}"

    def test_json_examples_valid(self):
        """Test that JSON examples in code blocks are valid"""
        content = SKILL_PATH.read_text()

        # Extract JSON code blocks
        json_blocks = re.findall(r"```json\n(.*?)\n```", content, re.DOTALL)

        assert len(json_blocks) > 0, "No JSON code blocks found"

        for i, block in enumerate(json_blocks):
            try:
                json.loads(block)
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in block {i+1}: {e}\n{block[:100]}")

    def test_bash_examples_present(self):
        """Test that bash examples are present"""
        content = SKILL_PATH.read_text()
        bash_blocks = re.findall(r"```bash\n(.*?)\n```", content, re.DOTALL)
        assert len(bash_blocks) >= 5, \
            f"Expected at least 5 bash examples, found {len(bash_blocks)}"

    def test_troubleshooting_has_solutions(self):
        """Test that troubleshooting section has problems and solutions"""
        content = SKILL_PATH.read_text()

        # Find the troubleshooting section (match ## but not ###)
        troubleshooting_match = re.search(
            r"## Troubleshooting(.*?)(?=\n## [^#]|$)",
            content,
            re.DOTALL
        )

        assert troubleshooting_match, "Troubleshooting section not found"
        troubleshooting_text = troubleshooting_match.group(1)

        # Should have problem/solution pairs
        assert "**Problem**" in troubleshooting_text, \
            "No problems documented in troubleshooting"
        assert "**Solution**" in troubleshooting_text, \
            "No solutions documented in troubleshooting"

    def test_skill_location_documented(self):
        """Test that skill location for Claude Code is documented"""
        content = SKILL_PATH.read_text()
        assert ".claude/skills/coding-dashboard/SKILL.md" in content, \
            "Skill location path not documented"

    def test_all_event_types_have_examples(self):
        """Test that each event type has a curl example"""
        content = SKILL_PATH.read_text()
        event_types = [
            "task_started",
            "task_completed",
            "decision_needed",
            "approval_needed",
            "error",
            "milestone",
            "file_changed",
            "activity"
        ]

        for event_type in event_types:
            # Check for event_type in curl examples
            pattern = rf'"event_type":\s*"{event_type}"'
            assert re.search(pattern, content), \
                f"No curl example found for event type '{event_type}'"

    def test_response_polling_example_present(self):
        """Test that response polling example is present"""
        content = SKILL_PATH.read_text()
        assert "while true" in content or "polling" in content.lower(), \
            "No polling example found for response handling"

    def test_workflow_completeness(self):
        """Test that typical workflow covers all main steps"""
        content = SKILL_PATH.read_text()

        # Find the workflow section (match ## but not ###)
        workflow_match = re.search(
            r"## Typical Workflow(.*?)(?=\n## [^#]|$)",
            content,
            re.DOTALL
        )

        assert workflow_match, "Typical Workflow section not found"
        workflow_text = workflow_match.group(1)

        # Check for key workflow steps
        steps = [
            "Initialize Project",
            "Start Task",
            "Report Progress",
            "Request Decision",
            "Complete Task"
        ]

        for step in steps:
            assert step in workflow_text, f"Workflow missing step: {step}"

    def test_has_license_section(self):
        """Test that license information is present"""
        content = SKILL_PATH.read_text()
        assert "## License" in content or "license" in content.lower(), \
            "No license information found"

    def test_has_support_section(self):
        """Test that support section is present"""
        content = SKILL_PATH.read_text()
        assert "## Support" in content, "Missing Support section"

    def test_documentation_link_present(self):
        """Test that OpenAPI documentation link is present"""
        content = SKILL_PATH.read_text()
        assert "/docs" in content, "OpenAPI docs link not mentioned"

    def test_environment_setup_documented(self):
        """Test that environment setup is documented"""
        content = SKILL_PATH.read_text()
        assert ".env" in content, "Environment setup not documented"

    def test_http_methods_documented(self):
        """Test that HTTP methods are clearly marked"""
        content = SKILL_PATH.read_text()
        http_methods = ["GET", "POST", "PUT", "DELETE"]
        found_methods = sum(1 for method in http_methods if f"**{method}**" in content)
        assert found_methods >= 2, \
            "HTTP methods not clearly documented with bold formatting"

    def test_response_status_codes_present(self):
        """Test that response status codes are documented"""
        content = SKILL_PATH.read_text()
        status_codes = ["200", "201", "202", "404", "500"]
        found_codes = sum(1 for code in status_codes if code in content)
        assert found_codes >= 3, \
            "Not enough HTTP status codes documented"

    def test_full_integration_script_present(self):
        """Test that a full integration script example exists"""
        content = SKILL_PATH.read_text()
        assert "#!/bin/bash" in content, \
            "No bash script example with shebang found"

        # Should have a complete script with all major components
        script_match = re.search(
            r"```bash\n#!/bin/bash.*?```",
            content,
            re.DOTALL
        )
        assert script_match, "No complete bash script found"

        script = script_match.group(0)
        assert len(script) > 500, \
            "Integration script seems too short to be comprehensive"


class TestSkillDocumentationContent:
    """Test the content quality of the skill documentation"""

    def test_no_placeholder_text(self):
        """Test that there's no obvious placeholder text"""
        content = SKILL_PATH.read_text()
        placeholders = [
            "TODO",
            "FIXME",
            "XXX",
            "your-api-key-here" if "OPENROUTER_API_KEY" not in content else None,
            "placeholder"
        ]
        placeholders = [p for p in placeholders if p is not None]

        for placeholder in placeholders:
            assert placeholder.lower() not in content.lower(), \
                f"Found placeholder text: {placeholder}"

    def test_has_real_examples(self):
        """Test that examples use realistic data"""
        content = SKILL_PATH.read_text()

        # Check for realistic example data
        realistic_patterns = [
            r"TASK-\d+",  # Task IDs
            r"DEC-\d+",   # Decision IDs
            r"APR-\d+",   # Approval IDs
            r"ERR-\d+",   # Error IDs
            r"\.tsx?",    # TypeScript files
        ]

        for pattern in realistic_patterns:
            assert re.search(pattern, content), \
                f"Missing realistic example pattern: {pattern}"

    def test_comprehensive_error_coverage(self):
        """Test that common errors are covered in troubleshooting"""
        content = SKILL_PATH.read_text()

        # Common API integration issues
        common_errors = [
            "Connection Refused",
            "404",
            "CORS"
        ]

        for error in common_errors:
            assert error in content, \
                f"Common error '{error}' not covered in troubleshooting"


def test_skill_directory_structure():
    """Test that the skill directory structure is correct"""
    skill_dir = SKILL_PATH.parent
    assert skill_dir.name == "coding-dashboard", \
        "Skill directory should be named 'coding-dashboard'"

    skills_dir = skill_dir.parent
    assert skills_dir.name == "skills", \
        "Parent directory should be 'skills'"

    claude_dir = skills_dir.parent
    assert claude_dir.name == ".claude", \
        "Grandparent directory should be '.claude'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
