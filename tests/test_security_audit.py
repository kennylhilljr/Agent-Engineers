"""
Tests for AI-206: Dependency Security Audit
Verifies that security infrastructure is correctly configured.

Uses only stdlib so no extra dependencies are required.
"""
import os
import re
import stat

import pytest

# Base directory for the project
BASE_DIR = "/Users/bkh223/Documents/GitHub/agent-engineers"
REQUIREMENTS_TXT = os.path.join(BASE_DIR, "requirements.txt")
REQUIREMENTS_DEV_TXT = os.path.join(BASE_DIR, "requirements-dev.txt")
PIP_AUDIT_TOML = os.path.join(BASE_DIR, ".pip-audit.toml")
SECURITY_WORKFLOW = os.path.join(BASE_DIR, ".github", "workflows", "security.yml")
PIN_SCRIPT = os.path.join(BASE_DIR, "scripts", "pin_dependencies.sh")

# Expected core dependencies
EXPECTED_DEPENDENCIES = [
    "openai",
    "httpx",
    "pydantic",
    "uvicorn",
    "starlette",
    "python-dotenv",
    "cryptography",
    "PyJWT",
    "mcp",
    "rich",
    "aiohttp",
    "psutil",
    "pytest",
    "click",
]

# Known-vulnerable pinned versions to check for (package, bad_version pattern)
KNOWN_BAD_PINS = [
    ("cryptography", r"==1\.[0-9]"),       # cryptography < 2.x has many CVEs
    ("cryptography", r"==2\.[0-3]"),       # cryptography 2.0-2.3 vulnerable
    ("PyJWT", r"==1\.[0-3]"),              # PyJWT < 1.4.x has algorithm confusion
    ("pydantic", r"==1\.[0-4]"),           # pydantic < 1.5 has dos vulnerability
    ("httpx", r"==0\.[0-9]\."),            # very old httpx
    ("starlette", r"==0\.[0-9]\."),        # very old starlette
]


def _read(path):
    """Return file contents as a string."""
    with open(path) as f:
        return f.read()


# -----------------------------------------------------------------------
# Helpers for lightweight YAML-like parsing (no PyYAML dependency)
# -----------------------------------------------------------------------

def _workflow_raw_text():
    """Return raw text of security.yml."""
    return _read(SECURITY_WORKFLOW)


# -----------------------------------------------------------------------
# requirements.txt existence and parseability
# -----------------------------------------------------------------------

class TestRequirementsTxtExists:
    """Test that requirements.txt exists and is readable."""

    def test_requirements_txt_exists(self):
        assert os.path.isfile(REQUIREMENTS_TXT), (
            f"requirements.txt not found at {REQUIREMENTS_TXT}"
        )

    def test_requirements_txt_is_not_empty(self):
        assert os.path.getsize(REQUIREMENTS_TXT) > 0, "requirements.txt is empty"

    def test_requirements_txt_is_parseable(self):
        """Ensure every non-comment, non-blank line is a valid requirement spec."""
        lines = _read(REQUIREMENTS_TXT).splitlines()
        errors = []
        for lineno, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-r"):
                continue
            if not re.match(r"^[A-Za-z0-9_.\-\[\]]+", line):
                errors.append(f"Line {lineno}: {line!r}")
        assert not errors, "Unparseable lines in requirements.txt:\n" + "\n".join(errors)

    def test_requirements_txt_has_no_trailing_backslash(self):
        """Lines with trailing backslashes can cause parse errors."""
        lines = _read(REQUIREMENTS_TXT).splitlines()
        bad = [l for l in lines if l.rstrip().endswith("\\")]
        assert not bad, f"Lines with trailing backslash: {bad}"

    def test_requirements_dev_txt_exists(self):
        assert os.path.isfile(REQUIREMENTS_DEV_TXT), (
            f"requirements-dev.txt not found at {REQUIREMENTS_DEV_TXT}"
        )


# -----------------------------------------------------------------------
# Dependency presence
# -----------------------------------------------------------------------

class TestExpectedDependencies:
    """Verify that key dependencies are declared in requirements.txt."""

    @pytest.fixture(scope="class")
    def requirements_content(self):
        return _read(REQUIREMENTS_TXT)

    @pytest.mark.parametrize("package", EXPECTED_DEPENDENCIES)
    def test_dependency_present(self, requirements_content, package):
        # Match case-insensitively; treat hyphens and underscores as interchangeable
        pattern = re.escape(package).replace(r"\-", r"[\-_]").replace(r"\_", r"[\-_]")
        assert re.search(pattern, requirements_content, re.IGNORECASE), (
            f"Expected dependency '{package}' not found in requirements.txt"
        )


# -----------------------------------------------------------------------
# No obviously vulnerable pinned versions
# -----------------------------------------------------------------------

class TestNoKnownVulnerableVersions:
    """Check that requirements.txt does not pin known-vulnerable versions."""

    @pytest.fixture(scope="class")
    def requirements_content(self):
        return _read(REQUIREMENTS_TXT)

    @pytest.mark.parametrize("package,bad_pattern", KNOWN_BAD_PINS)
    def test_no_known_bad_pin(self, requirements_content, package, bad_pattern):
        pkg_pattern = re.escape(package).replace(r"\-", r"[\-_]").replace(r"\_", r"[\-_]")
        full_pattern = rf"(?i){pkg_pattern}\s*{bad_pattern}"
        match = re.search(full_pattern, requirements_content)
        assert not match, (
            f"Potentially vulnerable pinned version found for '{package}': "
            f"{match.group(0) if match else ''}"
        )


# -----------------------------------------------------------------------
# pip-audit configuration
# -----------------------------------------------------------------------

class TestPipAuditConfig:
    """Test that .pip-audit.toml exists and contains required settings."""

    def test_pip_audit_toml_exists(self):
        assert os.path.isfile(PIP_AUDIT_TOML), (
            f".pip-audit.toml not found at {PIP_AUDIT_TOML}"
        )

    def test_pip_audit_toml_has_tool_section(self):
        content = _read(PIP_AUDIT_TOML)
        assert "[tool.pip-audit]" in content, (
            ".pip-audit.toml missing [tool.pip-audit] section"
        )

    def test_pip_audit_toml_has_vulnerability_service(self):
        content = _read(PIP_AUDIT_TOML)
        assert "vulnerability-service" in content, (
            ".pip-audit.toml missing 'vulnerability-service' key"
        )

    def test_pip_audit_toml_uses_osv_service(self):
        content = _read(PIP_AUDIT_TOML)
        assert '"osv"' in content or "'osv'" in content, (
            ".pip-audit.toml should use OSV vulnerability service"
        )

    def test_pip_audit_toml_has_format_key(self):
        content = _read(PIP_AUDIT_TOML)
        assert "format" in content, ".pip-audit.toml missing 'format' key"

    def test_pip_audit_toml_has_output_key(self):
        content = _read(PIP_AUDIT_TOML)
        assert "output" in content, ".pip-audit.toml missing 'output' key"


# -----------------------------------------------------------------------
# GitHub Actions security workflow - structural checks via raw text
# -----------------------------------------------------------------------

class TestSecurityWorkflow:
    """Test that the security.yml GitHub Actions workflow is correct."""

    def test_security_workflow_exists(self):
        assert os.path.isfile(SECURITY_WORKFLOW), (
            f"security.yml not found at {SECURITY_WORKFLOW}"
        )

    def test_workflow_has_name(self):
        content = _workflow_raw_text()
        assert re.search(r"^name\s*:", content, re.MULTILINE), (
            "Workflow missing top-level 'name:' key"
        )

    def test_workflow_has_on_trigger(self):
        content = _workflow_raw_text()
        assert re.search(r"^on\s*:", content, re.MULTILINE), (
            "Workflow missing top-level 'on:' trigger"
        )

    def test_workflow_triggers_on_requirements_push(self):
        content = _workflow_raw_text()
        assert "requirements" in content, (
            "Workflow should reference requirements files in push trigger"
        )

    def test_workflow_has_schedule_trigger(self):
        content = _workflow_raw_text()
        assert "schedule" in content, "Workflow should have a schedule trigger"

    def test_workflow_has_cron_expression(self):
        content = _workflow_raw_text()
        assert "cron" in content, "Workflow schedule should contain a cron expression"

    def test_workflow_has_workflow_dispatch(self):
        content = _workflow_raw_text()
        assert "workflow_dispatch" in content, (
            "Workflow should support manual dispatch via workflow_dispatch"
        )

    def test_workflow_has_audit_job(self):
        content = _workflow_raw_text()
        assert re.search(r"^\s+audit\s*:", content, re.MULTILINE), (
            "Workflow missing 'audit' job"
        )

    def test_workflow_runs_on_ubuntu(self):
        content = _workflow_raw_text()
        assert "ubuntu-latest" in content, (
            "Audit job should run on ubuntu-latest"
        )

    def test_workflow_installs_pip_audit(self):
        content = _workflow_raw_text()
        assert re.search(r"pip install pip-audit", content), (
            "Workflow should have a step that installs pip-audit"
        )

    def test_workflow_runs_pip_audit_on_requirements(self):
        content = _workflow_raw_text()
        assert re.search(r"pip-audit.*requirement", content), (
            "Workflow should run pip-audit against requirements.txt"
        )

    def test_workflow_uploads_audit_artifact(self):
        content = _workflow_raw_text()
        assert "upload-artifact" in content, (
            "Workflow should upload audit results as an artifact"
        )

    def test_workflow_uses_python_311(self):
        content = _workflow_raw_text()
        assert "3.11" in content, "Workflow should use Python 3.11"

    def test_workflow_uses_checkout_action(self):
        content = _workflow_raw_text()
        assert "actions/checkout" in content, (
            "Workflow should use actions/checkout"
        )

    def test_workflow_artifact_named_pip_audit_results(self):
        content = _workflow_raw_text()
        assert "pip-audit-results" in content, (
            "Workflow artifact should be named 'pip-audit-results'"
        )


# -----------------------------------------------------------------------
# Pin dependencies script
# -----------------------------------------------------------------------

class TestPinDependenciesScript:
    """Test that the pin_dependencies.sh script exists and is valid."""

    def test_pin_script_exists(self):
        assert os.path.isfile(PIN_SCRIPT), (
            f"scripts/pin_dependencies.sh not found at {PIN_SCRIPT}"
        )

    def test_pin_script_is_executable(self):
        st = os.stat(PIN_SCRIPT)
        assert bool(st.st_mode & stat.S_IXUSR), (
            "scripts/pin_dependencies.sh is not executable"
        )

    def test_pin_script_has_shebang(self):
        with open(PIN_SCRIPT) as f:
            first_line = f.readline()
        assert first_line.startswith("#!"), (
            "pin_dependencies.sh should have a shebang (#!) on the first line"
        )

    def test_pin_script_uses_pip_tools(self):
        content = _read(PIN_SCRIPT)
        assert "pip-tools" in content or "pip-compile" in content, (
            "pin_dependencies.sh should use pip-tools / pip-compile"
        )

    def test_pin_script_references_requirements_pinned(self):
        content = _read(PIN_SCRIPT)
        assert "requirements-pinned.txt" in content, (
            "pin_dependencies.sh should reference requirements-pinned.txt as output"
        )
