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

# 4b-2. Load dashboard.provider_bridge from the worktree (AI-174 / REQ-TECH-009)
_worktree_provider_bridge_path = _WORKTREE_ROOT / "dashboard" / "provider_bridge.py"
if _worktree_provider_bridge_path.exists():
    try:
        _load_module_from_file("dashboard.provider_bridge", _worktree_provider_bridge_path)
    except Exception:
        pass  # graceful degradation if bridge deps missing

# 4c. Load dashboard.config from the worktree (AI-175 / REQ-TECH-010) — before auth and server
_worktree_config_path = _WORKTREE_ROOT / "dashboard" / "config.py"
if _worktree_config_path.exists() and "dashboard.config" not in sys.modules:
    try:
        _load_module_from_file("dashboard.config", _worktree_config_path)
    except Exception:
        pass

# 4d. Load dashboard.auth from the worktree (AI-176 / REQ-TECH-011 + AI-222) — before server
# AI-222: dashboard.auth is now a package (directory).  Load the package __init__ first,
# then register the sub-modules so that imports like
#   from dashboard.auth.user_store import UserStore
# resolve to the worktree's files rather than the parent project's auth.py.
_worktree_auth_pkg = _WORKTREE_ROOT / "dashboard" / "auth"
_worktree_auth_init = _worktree_auth_pkg / "__init__.py"
_worktree_auth_py = _WORKTREE_ROOT / "dashboard" / "auth.py"

if _worktree_auth_init.exists():
    # New package layout (AI-222)
    try:
        import types as _types
        # Register the auth package in sys.modules so sub-module imports work
        if "dashboard.auth" not in sys.modules:
            _auth_pkg = _types.ModuleType("dashboard.auth")
            _auth_pkg.__path__ = [str(_worktree_auth_pkg)]
            _auth_pkg.__package__ = "dashboard.auth"
            _auth_pkg.__file__ = str(_worktree_auth_init)
            sys.modules["dashboard.auth"] = _auth_pkg
            spec = importlib.util.spec_from_file_location(
                "dashboard.auth", _worktree_auth_init,
                submodule_search_locations=[str(_worktree_auth_pkg)]
            )
            spec.loader.exec_module(_auth_pkg)
        # Register sub-modules
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
    # Legacy single-file layout (AI-176)
    try:
        _load_module_from_file("dashboard.auth", _worktree_auth_py)
    except Exception:
        pass

# 4e. Load dashboard.security from the worktree (AI-177 / REQ-TECH-012) — before server
_worktree_security_path = _WORKTREE_ROOT / "dashboard" / "security.py"
if _worktree_security_path.exists() and "dashboard.security" not in sys.modules:
    try:
        _load_module_from_file("dashboard.security", _worktree_security_path)
    except Exception:
        pass

# 4f. Load dashboard.latency_benchmark from the worktree (AI-180 / REQ-PERF-001) — before server
_worktree_latency_benchmark_path = _WORKTREE_ROOT / "dashboard" / "latency_benchmark.py"
if _worktree_latency_benchmark_path.exists() and "dashboard.latency_benchmark" not in sys.modules:
    try:
        _load_module_from_file("dashboard.latency_benchmark", _worktree_latency_benchmark_path)
    except Exception:
        pass

# 4g. Load dashboard.load_time_benchmark from the worktree (AI-181 / REQ-PERF-002)
_worktree_load_time_benchmark_path = _WORKTREE_ROOT / "dashboard" / "load_time_benchmark.py"
if _worktree_load_time_benchmark_path.exists() and "dashboard.load_time_benchmark" not in sys.modules:
    try:
        _load_module_from_file("dashboard.load_time_benchmark", _worktree_load_time_benchmark_path)
    except Exception:
        pass

# 4h. Load dashboard.structured_logging from the worktree (AI-186 / REQ-OBS-001) — before server
_worktree_structured_logging_path = _WORKTREE_ROOT / "dashboard" / "structured_logging.py"
if _worktree_structured_logging_path.exists() and "dashboard.structured_logging" not in sys.modules:
    try:
        _load_module_from_file("dashboard.structured_logging", _worktree_structured_logging_path)
    except Exception:
        pass

# 4i. Load dashboard.compat from the worktree (AI-187 / REQ-COMPAT-001) — before server
_worktree_compat_path = _WORKTREE_ROOT / "dashboard" / "compat.py"
if _worktree_compat_path.exists() and "dashboard.compat" not in sys.modules:
    try:
        _load_module_from_file("dashboard.compat", _worktree_compat_path)
    except Exception:
        pass

# 4j. Load dashboard.rate_limiter from the worktree (AI-224) — before server
_worktree_rate_limiter_path = _WORKTREE_ROOT / "dashboard" / "rate_limiter.py"
if _worktree_rate_limiter_path.exists() and "dashboard.rate_limiter" not in sys.modules:
    try:
        _load_module_from_file("dashboard.rate_limiter", _worktree_rate_limiter_path)
    except Exception:
        pass

# 4k. Load dashboard.usage_meter from the worktree (AI-224) — before server
_worktree_usage_meter_path = _WORKTREE_ROOT / "dashboard" / "usage_meter.py"
if _worktree_usage_meter_path.exists() and "dashboard.usage_meter" not in sys.modules:
    try:
        _load_module_from_file("dashboard.usage_meter", _worktree_usage_meter_path)
    except Exception:
        pass

# 4l. Load dashboard.webhooks from the worktree (AI-229 / Webhook Support) — before server
_worktree_webhooks_path = _WORKTREE_ROOT / "dashboard" / "webhooks.py"
if _worktree_webhooks_path.exists() and "dashboard.webhooks" not in sys.modules:
    try:
        _load_module_from_file("dashboard.webhooks", _worktree_webhooks_path)
    except Exception:
        pass

# 4m. Load dashboard.free_tier from the worktree (AI-220 / Free Tier) — before server
_worktree_free_tier_path = _WORKTREE_ROOT / "dashboard" / "free_tier.py"
if _worktree_free_tier_path.exists() and "dashboard.free_tier" not in sys.modules:
    try:
        _load_module_from_file("dashboard.free_tier", _worktree_free_tier_path)
    except Exception:
        pass

# 4b-3. Override dashboard.chat_handler with worktree version (AI-99/AI-114 streaming)
_worktree_chat_handler_path = _WORKTREE_ROOT / "dashboard" / "chat_handler.py"
if _worktree_chat_handler_path.exists():
    try:
        _load_module_from_file("dashboard.chat_handler", _worktree_chat_handler_path)
    except Exception:
        pass

# 4b-4. Override dashboard.intent_parser with worktree version
_worktree_intent_parser_path = _WORKTREE_ROOT / "dashboard" / "intent_parser.py"
if _worktree_intent_parser_path.exists() and "dashboard.intent_parser" not in sys.modules:
    try:
        _load_module_from_file("dashboard.intent_parser", _worktree_intent_parser_path)
    except Exception:
        pass

# 4b-5. Override dashboard.agent_executor with worktree version
_worktree_agent_executor_path = _WORKTREE_ROOT / "dashboard" / "agent_executor.py"
if _worktree_agent_executor_path.exists() and "dashboard.agent_executor" not in sys.modules:
    try:
        _load_module_from_file("dashboard.agent_executor", _worktree_agent_executor_path)
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
