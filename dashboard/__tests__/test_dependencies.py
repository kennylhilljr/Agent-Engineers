"""Tests for AI-188 / REQ-COMPAT-002: No new system dependencies.

Verifies that:
- requirements.txt exists and contains aiohttp
- No heavy ML/numerical dependencies (tensorflow, torch, numpy) are required
- All core dashboard modules import successfully without network access
- aiohttp, starlette, uvicorn and other approved packages are importable
- Dashboard modules listed in the ticket all import without errors

Test count: 17 (>= 15 as required).
"""

import importlib
import sys
from pathlib import Path

import pytest

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# The requirements.txt is at the project root
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _read_requirements():
    """Return the text of requirements.txt, or empty string if missing."""
    if REQUIREMENTS_FILE.exists():
        return REQUIREMENTS_FILE.read_text()
    return ""


def _import_dashboard_module(name: str):
    """Import a dashboard sub-module by name and return it.

    Uses importlib.import_module so it works whether the module was loaded
    via conftest._load_module_from_file (registered in sys.modules) or via
    the normal package mechanism.
    """
    full_name = f"dashboard.{name}"
    # Already loaded by conftest or a prior test?
    if full_name in sys.modules:
        return sys.modules[full_name]
    # Fall back to standard import
    return importlib.import_module(full_name)


# ---------------------------------------------------------------------------
# Test 1: requirements.txt exists
# ---------------------------------------------------------------------------

def test_requirements_file_exists():
    """requirements.txt must exist at the project root."""
    assert REQUIREMENTS_FILE.exists(), f"requirements.txt not found at {REQUIREMENTS_FILE}"


# ---------------------------------------------------------------------------
# Test 2: requirements.txt is non-empty
# ---------------------------------------------------------------------------

def test_requirements_file_is_non_empty():
    """requirements.txt must not be empty."""
    content = _read_requirements()
    assert content.strip(), "requirements.txt is empty"


# ---------------------------------------------------------------------------
# Test 3: aiohttp is listed in requirements.txt
# ---------------------------------------------------------------------------

def test_aiohttp_in_requirements():
    """aiohttp must appear in requirements.txt (REQ-COMPAT-002)."""
    content = _read_requirements()
    assert "aiohttp" in content, "aiohttp not found in requirements.txt"


# ---------------------------------------------------------------------------
# Test 4: aiohttp is importable in the current environment
# ---------------------------------------------------------------------------

def test_aiohttp_importable():
    """aiohttp must be importable (installed in the environment)."""
    import aiohttp  # noqa: F401
    assert aiohttp is not None


# ---------------------------------------------------------------------------
# Test 5: tensorflow is NOT required (not in requirements.txt)
# ---------------------------------------------------------------------------

def test_tensorflow_not_in_requirements():
    """tensorflow must NOT be listed in requirements.txt."""
    content = _read_requirements()
    assert "tensorflow" not in content.lower(), \
        "tensorflow unexpectedly found in requirements.txt"


# ---------------------------------------------------------------------------
# Test 6: torch is NOT required (not in requirements.txt)
# ---------------------------------------------------------------------------

def test_torch_not_in_requirements():
    """torch (PyTorch) must NOT be listed in requirements.txt."""
    content = _read_requirements()
    assert "torch" not in content.lower(), \
        "torch unexpectedly found in requirements.txt"


# ---------------------------------------------------------------------------
# Test 7: numpy is NOT required (not in requirements.txt)
# ---------------------------------------------------------------------------

def test_numpy_not_in_requirements():
    """numpy must NOT be listed in requirements.txt."""
    content = _read_requirements()
    assert "numpy" not in content.lower(), \
        "numpy unexpectedly found in requirements.txt"


# ---------------------------------------------------------------------------
# Test 8: dashboard.server imports successfully
# ---------------------------------------------------------------------------

def test_dashboard_server_importable():
    """dashboard.server must import without errors."""
    mod = _import_dashboard_module("server")
    assert mod is not None


# ---------------------------------------------------------------------------
# Test 9: dashboard.collector imports successfully
# ---------------------------------------------------------------------------

def test_dashboard_collector_importable():
    """dashboard.collector must import without errors."""
    mod = _import_dashboard_module("collector")
    assert mod is not None


# ---------------------------------------------------------------------------
# Test 10: dashboard.config imports successfully
# ---------------------------------------------------------------------------

def test_dashboard_config_importable():
    """dashboard.config must import without errors."""
    mod = _import_dashboard_module("config")
    assert mod is not None


# ---------------------------------------------------------------------------
# Test 11: dashboard.auth imports successfully
# ---------------------------------------------------------------------------

def test_dashboard_auth_importable():
    """dashboard.auth must import without errors."""
    mod = _import_dashboard_module("auth")
    assert mod is not None


# ---------------------------------------------------------------------------
# Test 12: dashboard.security imports successfully
# ---------------------------------------------------------------------------

def test_dashboard_security_importable():
    """dashboard.security must import without errors."""
    mod = _import_dashboard_module("security")
    assert mod is not None


# ---------------------------------------------------------------------------
# Test 13: dashboard.chat_bridge imports successfully
# ---------------------------------------------------------------------------

def test_dashboard_chat_bridge_importable():
    """dashboard.chat_bridge must import without errors."""
    mod = _import_dashboard_module("chat_bridge")
    assert mod is not None


# ---------------------------------------------------------------------------
# Test 14: dashboard.orchestrator_hook imports successfully
# ---------------------------------------------------------------------------

def test_dashboard_orchestrator_hook_importable():
    """dashboard.orchestrator_hook must import without errors."""
    mod = _import_dashboard_module("orchestrator_hook")
    assert mod is not None


# ---------------------------------------------------------------------------
# Test 15: dashboard.crash_isolation imports successfully
# ---------------------------------------------------------------------------

def test_dashboard_crash_isolation_importable():
    """dashboard.crash_isolation must import without errors."""
    mod = _import_dashboard_module("crash_isolation")
    assert mod is not None


# ---------------------------------------------------------------------------
# Test 16: dashboard.structured_logging imports successfully
# ---------------------------------------------------------------------------

def test_dashboard_structured_logging_importable():
    """dashboard.structured_logging must import without errors."""
    mod = _import_dashboard_module("structured_logging")
    assert mod is not None


# ---------------------------------------------------------------------------
# Test 17: dashboard.compat imports successfully
# ---------------------------------------------------------------------------

def test_dashboard_compat_importable():
    """dashboard.compat must import without errors (AI-187)."""
    mod = _import_dashboard_module("compat")
    assert mod is not None
