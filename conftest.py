"""conftest.py for the coding-0 worktree.

Bootstraps imports so the worktree's dashboard/server.py (with AI-161 changes)
can be tested via standard 'from dashboard.server import ...' calls while
reusing the parent project's dashboard sub-modules (metrics_store, metrics, etc.).

Directory layout:
    .../generations/agent-dashboard/              <- _PARENT_PROJECT
    .../generations/agent-dashboard/.worktrees/   <- worktrees parent
    .../generations/agent-dashboard/.worktrees/coding-0/  <- _WORKTREE_ROOT
"""
import importlib.util
import sys
from pathlib import Path

# coding-0 worktree root
_WORKTREE_ROOT = Path(__file__).parent

# agent-dashboard project root (2 levels up from coding-0: coding-0 -> .worktrees -> agent-dashboard)
_PARENT_PROJECT = _WORKTREE_ROOT.parent.parent

_PARENT_DASHBOARD = _PARENT_PROJECT / "dashboard"


def _load_module_from_file(full_key: str, filepath: Path):
    """Load a Python file as a named module and register it in sys.modules."""
    spec = importlib.util.spec_from_file_location(full_key, filepath)
    if spec is None:
        raise ImportError(f"Cannot create spec for {filepath}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_key] = mod
    spec.loader.exec_module(mod)
    return mod


# 1. Load the parent's 'dashboard' package itself (its __init__.py)
if "dashboard" not in sys.modules:
    _load_module_from_file("dashboard", _PARENT_DASHBOARD / "__init__.py")

# 2. Load sub-modules that server.py depends on (in dependency order)
for _sub in ["logging_config", "metrics", "metrics_store", "collector"]:
    _key = f"dashboard.{_sub}"
    if _key not in sys.modules:
        _src = _PARENT_DASHBOARD / f"{_sub}.py"
        if _src.exists():
            try:
                _load_module_from_file(_key, _src)
            except Exception:
                pass  # best-effort; some sub-modules may have further deps

# 3. Override dashboard.server with the worktree's AI-161 version
_worktree_server_path = _WORKTREE_ROOT / "dashboard" / "server.py"
if _worktree_server_path.exists():
    _load_module_from_file("dashboard.server", _worktree_server_path)

# 4. Override dashboard.rest_api_server with the worktree's AI-169 version
_worktree_rest_api_path = _WORKTREE_ROOT / "dashboard" / "rest_api_server.py"
if _worktree_rest_api_path.exists():
    _load_module_from_file("dashboard.rest_api_server", _worktree_rest_api_path)
