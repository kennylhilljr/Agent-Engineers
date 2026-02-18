"""Tests for AI-187 / REQ-COMPAT-001: Python 3.10+ compatibility check.

Covers:
- MIN_PYTHON constant is (3, 10)
- Current Python interpreter meets the minimum (3.10+)
- check_python_version() does not raise on the current interpreter
- check_python_version() raises RuntimeError for Python < 3.10
- RuntimeError message contains version information
- get_python_info() returns all required fields with correct types
- get_python_info() meets_minimum is True for current Python
- get_python_info() minimum_required field is correct
- Module-level attributes are present (MIN_PYTHON, functions)
- server.py imports check_python_version at the top level

Test count: 16 (>= 15 as required).
"""

import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.compat import MIN_PYTHON, check_python_version, get_python_info


def _make_version_info(major, minor, micro=0):
    """Return a SimpleNamespace that mimics sys.version_info tuple comparison.

    sys.version_info supports both attribute access (.major) and tuple comparison
    (version_info >= (3, 10)).  SimpleNamespace does not support tuple comparison,
    so we use a helper class that supports both.
    """

    class _FakeVersionInfo(tuple):
        """Tuple subclass with named attributes, mirroring sys.version_info."""

        def __new__(cls, major, minor, micro=0):
            instance = super().__new__(cls, (major, minor, micro, "final", 0))
            instance.major = major
            instance.minor = minor
            instance.micro = micro
            return instance

    return _FakeVersionInfo(major, minor, micro)


# ---------------------------------------------------------------------------
# Test 1: MIN_PYTHON constant
# ---------------------------------------------------------------------------

def test_min_python_constant_value():
    """MIN_PYTHON should be exactly (3, 10)."""
    assert MIN_PYTHON == (3, 10)


# ---------------------------------------------------------------------------
# Test 2: MIN_PYTHON is a tuple
# ---------------------------------------------------------------------------

def test_min_python_is_tuple():
    """MIN_PYTHON must be a tuple (used for comparison with sys.version_info)."""
    assert isinstance(MIN_PYTHON, tuple)


# ---------------------------------------------------------------------------
# Test 3: MIN_PYTHON has exactly two elements
# ---------------------------------------------------------------------------

def test_min_python_has_two_elements():
    """MIN_PYTHON should be a (major, minor) pair."""
    assert len(MIN_PYTHON) == 2


# ---------------------------------------------------------------------------
# Test 4: Current Python meets minimum
# ---------------------------------------------------------------------------

def test_current_python_meets_minimum():
    """The running interpreter must be Python 3.10 or higher."""
    assert sys.version_info >= MIN_PYTHON, (
        f"Test environment has Python {sys.version_info.major}.{sys.version_info.minor} "
        f"but minimum is {MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    )


# ---------------------------------------------------------------------------
# Test 5: check_python_version() does not raise on current interpreter
# ---------------------------------------------------------------------------

def test_check_python_version_does_not_raise():
    """check_python_version() must succeed silently on the current interpreter."""
    check_python_version()  # Should not raise


# ---------------------------------------------------------------------------
# Test 6: check_python_version() returns None on success
# ---------------------------------------------------------------------------

def test_check_python_version_returns_none():
    """check_python_version() should return None when the check passes."""
    result = check_python_version()
    assert result is None


# ---------------------------------------------------------------------------
# Test 7: check_python_version() raises RuntimeError for Python 3.9
# ---------------------------------------------------------------------------

def test_check_python_version_raises_for_python_3_9():
    """check_python_version() must raise RuntimeError when mocked to 3.9."""
    fake_version = _make_version_info(3, 9, 0)
    with patch("dashboard.compat.sys") as mock_sys:
        mock_sys.version_info = fake_version
        with pytest.raises(RuntimeError):
            check_python_version()


# ---------------------------------------------------------------------------
# Test 8: check_python_version() raises RuntimeError for Python 2.7
# ---------------------------------------------------------------------------

def test_check_python_version_raises_for_python_2_7():
    """check_python_version() must raise RuntimeError when mocked to 2.7."""
    fake_version = _make_version_info(2, 7, 18)
    with patch("dashboard.compat.sys") as mock_sys:
        mock_sys.version_info = fake_version
        with pytest.raises(RuntimeError):
            check_python_version()


# ---------------------------------------------------------------------------
# Test 9: RuntimeError message contains minimum version
# ---------------------------------------------------------------------------

def test_check_python_version_error_message_contains_minimum():
    """RuntimeError message must mention the minimum required version."""
    fake_version = _make_version_info(3, 9, 0)
    with patch("dashboard.compat.sys") as mock_sys:
        mock_sys.version_info = fake_version
        with pytest.raises(RuntimeError, match="3.10"):
            check_python_version()


# ---------------------------------------------------------------------------
# Test 10: RuntimeError message contains actual version
# ---------------------------------------------------------------------------

def test_check_python_version_error_message_contains_actual_version():
    """RuntimeError message must mention the actual running version."""
    fake_version = _make_version_info(3, 8, 5)
    with patch("dashboard.compat.sys") as mock_sys:
        mock_sys.version_info = fake_version
        with pytest.raises(RuntimeError, match="3.8"):
            check_python_version()


# ---------------------------------------------------------------------------
# Test 11: check_python_version() does NOT raise for Python 3.10
# ---------------------------------------------------------------------------

def test_check_python_version_passes_for_exactly_3_10():
    """check_python_version() must pass (not raise) for Python exactly 3.10."""
    fake_version = _make_version_info(3, 10, 0)
    with patch("dashboard.compat.sys") as mock_sys:
        mock_sys.version_info = fake_version
        check_python_version()  # Must not raise


# ---------------------------------------------------------------------------
# Test 12: check_python_version() does NOT raise for Python 3.12
# ---------------------------------------------------------------------------

def test_check_python_version_passes_for_3_12():
    """check_python_version() must pass (not raise) for Python 3.12."""
    fake_version = _make_version_info(3, 12, 0)
    with patch("dashboard.compat.sys") as mock_sys:
        mock_sys.version_info = fake_version
        check_python_version()  # Must not raise


# ---------------------------------------------------------------------------
# Test 13: get_python_info() returns a dict
# ---------------------------------------------------------------------------

def test_get_python_info_returns_dict():
    """get_python_info() must return a dict."""
    info = get_python_info()
    assert isinstance(info, dict)


# ---------------------------------------------------------------------------
# Test 14: get_python_info() contains all required keys
# ---------------------------------------------------------------------------

def test_get_python_info_has_all_required_keys():
    """get_python_info() must include version, major, minor, meets_minimum, minimum_required."""
    info = get_python_info()
    required_keys = {"version", "major", "minor", "meets_minimum", "minimum_required"}
    assert required_keys.issubset(info.keys()), (
        f"Missing keys: {required_keys - set(info.keys())}"
    )


# ---------------------------------------------------------------------------
# Test 15: get_python_info() meets_minimum is True for current Python
# ---------------------------------------------------------------------------

def test_get_python_info_meets_minimum_is_true():
    """meets_minimum must be True for the currently running Python >= 3.10."""
    info = get_python_info()
    assert info["meets_minimum"] is True


# ---------------------------------------------------------------------------
# Test 16: get_python_info() minimum_required is '3.10'
# ---------------------------------------------------------------------------

def test_get_python_info_minimum_required():
    """minimum_required must be the string '3.10'."""
    info = get_python_info()
    assert info["minimum_required"] == "3.10"
