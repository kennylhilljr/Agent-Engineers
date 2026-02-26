"""conftest.py for the project.

Bootstraps imports so dashboard modules can be tested via standard
'from dashboard.server import ...' calls.  Works in two layouts:

1. **Worktree** — running inside .worktrees/coding-0/ where the parent
   project's dashboard package lives two directories up.  In this mode
   every dashboard sub-module is explicitly loaded from the parent or
   worktree so that 'from dashboard.X import Y' resolves correctly.

2. **Repo root / CI** — running from the repository root where dashboard/
   is a direct sub-directory.  Python's normal import machinery works, so
   no module patching is needed.
"""
import importlib.util
import sys
from pathlib import Path

# Detect which layout we're in
_WORKTREE_ROOT = Path(__file__).parent
_LOCAL_DASHBOARD = _WORKTREE_ROOT / "dashboard"

# In repo-root layout the dashboard package is a direct child and standard
# imports work.  The heavy module-patching below is ONLY needed when running
# inside a git worktree where the dashboard package lives elsewhere.
_IN_WORKTREE = not (_LOCAL_DASHBOARD / "__init__.py").exists()

if _IN_WORKTREE:
    # agent-dashboard project root (2 levels up from coding-0)
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
        _init_path = _PARENT_DASHBOARD / "__init__.py"
        if _init_path.exists():
            _load_module_from_file("dashboard", _init_path)

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

    # 3a. Override dashboard.metrics_store with the worktree's AI-185 version
    _worktree_metrics_store_path = _WORKTREE_ROOT / "dashboard" / "metrics_store.py"
    if _worktree_metrics_store_path.exists():
        _load_module_from_file("dashboard.metrics_store", _worktree_metrics_store_path)

    # 3. Override dashboard.collector with the worktree's AI-171 version
    _worktree_collector_path = _WORKTREE_ROOT / "dashboard" / "collector.py"
    if _worktree_collector_path.exists():
        _load_module_from_file("dashboard.collector", _worktree_collector_path)

    # 4a. Load dashboard.chat_bridge from the worktree (AI-173) — must be before server.py
    _worktree_chat_bridge_path = _WORKTREE_ROOT / "dashboard" / "chat_bridge.py"
    if _worktree_chat_bridge_path.exists():
        _load_module_from_file("dashboard.chat_bridge", _worktree_chat_bridge_path)

    # 4a-2. Load dashboard.chat_handler from the worktree (AI-114 / multi-provider streaming)
    _worktree_chat_handler_path = _WORKTREE_ROOT / "dashboard" / "chat_handler.py"
    if _worktree_chat_handler_path.exists():
        try:
            _ch_mod = _load_module_from_file(
                "dashboard.chat_handler", _worktree_chat_handler_path
            )
            if "dashboard" in sys.modules and _ch_mod is not None:
                setattr(sys.modules["dashboard"], "chat_handler", _ch_mod)
        except Exception:
            pass

    # 4b-2. Load dashboard.provider_bridge from the worktree (AI-174 / REQ-TECH-009)
    _worktree_provider_bridge_path = _WORKTREE_ROOT / "dashboard" / "provider_bridge.py"
    if _worktree_provider_bridge_path.exists():
        try:
            _load_module_from_file("dashboard.provider_bridge", _worktree_provider_bridge_path)
        except Exception:
            pass

    # 4c. Load dashboard.config from the worktree (AI-175 / REQ-TECH-010)
    _worktree_config_path = _WORKTREE_ROOT / "dashboard" / "config.py"
    if _worktree_config_path.exists() and "dashboard.config" not in sys.modules:
        try:
            _load_module_from_file("dashboard.config", _worktree_config_path)
        except Exception:
            pass

    # 4d. Load dashboard.auth from the worktree (AI-176 / REQ-TECH-011 + AI-222)
    _worktree_auth_pkg = _WORKTREE_ROOT / "dashboard" / "auth"
    _worktree_auth_init = _worktree_auth_pkg / "__init__.py"
    _worktree_auth_py = _WORKTREE_ROOT / "dashboard" / "auth.py"

    if _worktree_auth_init.exists():
        try:
            import types as _types

            if "dashboard.auth" not in sys.modules:
                _auth_pkg = _types.ModuleType("dashboard.auth")
                _auth_pkg.__path__ = [str(_worktree_auth_pkg)]
                _auth_pkg.__package__ = "dashboard.auth"
                _auth_pkg.__file__ = str(_worktree_auth_init)
                sys.modules["dashboard.auth"] = _auth_pkg
                spec = importlib.util.spec_from_file_location(
                    "dashboard.auth",
                    _worktree_auth_init,
                    submodule_search_locations=[str(_worktree_auth_pkg)],
                )
                spec.loader.exec_module(_auth_pkg)
            for _auth_sub in ["user_store", "session_manager", "oauth_handler"]:
                _auth_sub_key = f"dashboard.auth.{_auth_sub}"
                if _auth_sub_key not in sys.modules:
                    _auth_sub_path = _worktree_auth_pkg / f"{_auth_sub}.py"
                    if _auth_sub_path.exists():
                        try:
                            _load_module_from_file(_auth_sub_key, _auth_sub_path)
                        except Exception:
                            pass
        except Exception:
            pass
    elif _worktree_auth_py.exists() and "dashboard.auth" not in sys.modules:
        try:
            _load_module_from_file("dashboard.auth", _worktree_auth_py)
        except Exception:
            pass

    # 4e–4m. Load remaining dashboard sub-modules from worktree
    _optional_subs = [
        "security",
        "latency_benchmark",
        "load_time_benchmark",
        "structured_logging",
        "compat",
        "rate_limiter",
        "usage_meter",
        "webhooks",
        "free_tier",
    ]
    for _sub_name in _optional_subs:
        _sub_path = _WORKTREE_ROOT / "dashboard" / f"{_sub_name}.py"
        _sub_key = f"dashboard.{_sub_name}"
        if _sub_path.exists() and _sub_key not in sys.modules:
            try:
                _load_module_from_file(_sub_key, _sub_path)
            except Exception:
                pass

    # 4b. Override dashboard.server with the worktree's AI-161 version
    _worktree_server_path = _WORKTREE_ROOT / "dashboard" / "server.py"
    if _worktree_server_path.exists():
        _load_module_from_file("dashboard.server", _worktree_server_path)

    # 5. Override dashboard.rest_api_server with the worktree's AI-169 version
    _worktree_rest_api_path = _WORKTREE_ROOT / "dashboard" / "rest_api_server.py"
    if _worktree_rest_api_path.exists():
        _load_module_from_file("dashboard.rest_api_server", _worktree_rest_api_path)

    # 6. Load dashboard.orchestrator_hook from the worktree (AI-172)
    _worktree_orchestrator_hook_path = _WORKTREE_ROOT / "dashboard" / "orchestrator_hook.py"
    if _worktree_orchestrator_hook_path.exists():
        _load_module_from_file("dashboard.orchestrator_hook", _worktree_orchestrator_hook_path)

    # 7. Load dashboard.crash_isolation from the worktree (AI-183 / REQ-REL-001)
    _worktree_crash_isolation_path = _WORKTREE_ROOT / "dashboard" / "crash_isolation.py"
    if _worktree_crash_isolation_path.exists() and "dashboard.crash_isolation" not in sys.modules:
        try:
            _load_module_from_file("dashboard.crash_isolation", _worktree_crash_isolation_path)
        except Exception:
            pass
