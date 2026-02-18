"""Compatibility checks for dashboard server (AI-187 / REQ-COMPAT-001).

Verifies that the running Python interpreter meets the minimum version
requirement of Python 3.10+, matching the existing pyproject.toml target.
"""

import sys

MIN_PYTHON = (3, 10)


def check_python_version() -> None:
    """Raise RuntimeError if the running Python version is below 3.10.

    Raises:
        RuntimeError: When sys.version_info < (3, 10), with a clear message
            showing both the required and the actual version.
    """
    if sys.version_info < MIN_PYTHON:
        raise RuntimeError(
            f"Dashboard requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+, "
            f"got {sys.version_info.major}.{sys.version_info.minor}"
        )


def get_python_info() -> dict:
    """Return a dictionary describing the current Python runtime.

    Returns:
        dict with keys:
            - version (str): Full ``major.minor.micro`` version string.
            - major (int): Major version component.
            - minor (int): Minor version component.
            - meets_minimum (bool): True when current version >= (3, 10).
            - minimum_required (str): Human-readable minimum version string.
    """
    return {
        "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "major": sys.version_info.major,
        "minor": sys.version_info.minor,
        "meets_minimum": sys.version_info >= MIN_PYTHON,
        "minimum_required": f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
    }
