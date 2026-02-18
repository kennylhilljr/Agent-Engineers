"""REST API Server - Complete REST API for Agent Dashboard.

This module extends the existing dashboard/server.py with all required REST API endpoints
specified in REQ-TECH-004. It includes authentication, agent control, and chat functionality.

Endpoints:
    GET  /api/health - Health check
    GET  /api/metrics - Current DashboardState
    GET  /api/agents - All agent profiles
    GET  /api/agents/{name} - Single agent profile
    GET  /api/agents/{name}/events - Recent events for an agent
    GET  /api/sessions - Session history
    GET  /api/providers - Available AI providers and models
    POST /api/chat - Send chat message (streaming response)
    POST /api/agents/{name}/pause - Pause an agent
    POST /api/agents/{name}/resume - Resume an agent
    PUT  /api/requirements/{ticket_key} - Update requirement instructions
    GET  /api/requirements/{ticket_key} - Get current requirement instructions
    GET  /api/decisions - Decision history log
    GET  / - Serve dashboard HTML

Authentication:
    - Optional bearer token via DASHBOARD_AUTH_TOKEN environment variable
    - Header format: Authorization: Bearer <token>
    - If DASHBOARD_AUTH_TOKEN is not set, all endpoints are open (dev mode)
"""

import asyncio
import hmac
import json
import os
import signal
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from aiohttp import web
from aiohttp.web import Request, Response, middleware

from dashboard.metrics_store import MetricsStore, ALL_AGENT_NAMES
from exceptions import SecurityError

# Import only if needed - avoid importing agents.definitions which has Python 3.10+ dependencies
# from agents.definitions import DEFAULT_MODELS, AGENT_DEFINITIONS


# Agent state tracking (in-memory for pause/resume)
_agent_states: Dict[str, str] = {}  # agent_name -> "running" | "paused" | "idle"
_requirements_cache: Dict[str, str] = {}  # ticket_key -> requirement text (legacy simple cache)
# AI-90/AI-91: Rich requirements store - ticket_key -> requirement dict
# Each entry: {ticket_key, title, description, spec_text, edited_description, last_edited, sync_to_linear}
_requirements_store: Dict[str, Dict[str, Any]] = {}
_decisions_log: list[Dict[str, Any]] = []  # Decision history

# AI-92: Pause→Edit→Resume cycle tracking
# Maps agent_name -> {ticket_key, requirement, acknowledged: bool, updated_at}
_agent_active_requirements: Dict[str, Dict[str, Any]] = {}

# AI-93: Linear sync queue
# List of {ticket_key, edited_description, queued_at, processed: bool}
_linear_sync_queue: list = []

# Agent Status Panel (AI-79 / REQ-MONITOR-001): extended per-agent status details
# Tracks: status (idle|running|paused|error), current_ticket, elapsed_time start
# AI-80 / REQ-MONITOR-002: also tracks ticket_title, description, token_count, estimated_cost
_agent_status_details: Dict[str, Dict[str, Any]] = {}

# Valid agent statuses for the status panel
VALID_AGENT_STATUSES = ("idle", "running", "paused", "error")

# AI-81: Agent Detail View (REQ-MONITOR-003) - per-agent recent events store
# {agent_name: [list of last 20 event dicts]}
_rest_agent_recent_events: Dict[str, list] = {}

# AI-84: Agent Leaderboard (REQ-METRICS-002) - in-memory per-agent XP store
# {agent_name: {"xp": int, "level": int, "success_rate": float, "avg_duration_s": float, "total_cost_usd": float, "status": str}}
_rest_agent_xp_store: Dict[str, Dict[str, Any]] = {}

# AI-86: Live Activity Feed (REQ-FEED-001) - in-memory event feed store (newest last, capped at 50)
_rest_feed_events: list = []
_REST_FEED_MAX = 50

# AI-83: Global Metrics Bar (REQ-METRICS-001) - in-memory global metrics store
_rest_global_metrics: Dict[str, Any] = {
    "total_sessions": 0,
    "total_tokens": 0,
    "total_cost_usd": 0.0,
    "uptime_seconds": 0,
    "current_session": 0,
    "agents_active": 0,
    "tasks_completed_today": 0,
    "_server_start_time": None,  # set at server startup
}

# AI-82: Orchestrator Pipeline Visualization (REQ-MONITOR-004)
# Pipeline state: {"active": bool, "ticket_key": str, "ticket_title": str, "steps": [...]}
_PIPELINE_STEP_IDS = [
    "ops-start", "coding", "github", "ops-review", "pr_reviewer", "ops-done"
]
_PIPELINE_DEFAULT_STEPS = [
    {"id": "ops-start",    "label": "ops: Starting",          "status": "pending", "duration": None},
    {"id": "coding",       "label": "coding: Implement",      "status": "pending", "duration": None},
    {"id": "github",       "label": "github: Commit & PR",    "status": "pending", "duration": None},
    {"id": "ops-review",   "label": "ops: PR Ready",          "status": "pending", "duration": None},
    {"id": "pr_reviewer",  "label": "pr_reviewer: Review",    "status": "pending", "duration": None},
    {"id": "ops-done",     "label": "ops: Done",              "status": "pending", "duration": None},
]

def _make_default_pipeline() -> Dict[str, Any]:
    """Return a fresh default (inactive) pipeline state."""
    import copy
    return {
        "active": False,
        "ticket_key": None,
        "ticket_title": None,
        "steps": copy.deepcopy(_PIPELINE_DEFAULT_STEPS),
    }

_pipeline_state: Dict[str, Any] = _make_default_pipeline()

# AI-81: Fallback DEFAULT_MODELS mapping (avoids importing claude_agent_sdk)
_REST_DEFAULT_MODELS: Dict[str, str] = {
    "linear": "haiku",
    "coding": "sonnet",
    "github": "haiku",
    "slack": "haiku",
    "pr_reviewer": "sonnet",
    "ops": "haiku",
    "coding_fast": "haiku",
    "pr_reviewer_fast": "haiku",
    "chatgpt": "haiku",
    "gemini": "haiku",
    "groq": "haiku",
    "kimi": "haiku",
    "windsurf": "haiku",
    "openrouter_dev": "haiku",
    "product_manager": "sonnet",
    "designer": "haiku",
}

# The 16 canonical agents for the status panel (excludes orchestrator)
PANEL_AGENT_NAMES = [
    "linear", "coding", "github", "slack", "pr_reviewer",
    "ops", "coding_fast", "pr_reviewer_fast", "chatgpt",
    "gemini", "groq", "kimi", "windsurf",
    "openrouter_dev", "product_manager", "designer",
]

# AI-89: Global system pause flag
_system_paused: bool = False

# WebSocket clients connected to /api/ws for agent_status broadcasts
_ws_clients: set = set()

# AI-85: Cost and Token Charts (REQ-METRICS-003) - in-memory chart data stores
_rest_chart_token_usage: Dict[str, int] = {
    name: 0 for name in [
        "linear", "coding", "github", "slack", "pr_reviewer",
        "ops", "coding_fast", "pr_reviewer_fast", "chatgpt",
        "gemini", "groq", "kimi", "windsurf",
        "openrouter_dev", "product_manager", "designer",
    ]
}
_rest_chart_cost_trend: list = []  # list of {"session": int, "cost": float}
_REST_CHART_COST_TREND_MAX = 10

# PM Task Launcher state
_pm_process: Optional[subprocess.Popen] = None
_pm_task_log: list[Dict[str, Any]] = []
_REPO_ROOT = Path(__file__).parent.parent
PM_TASKS: Dict[str, str] = {
    "full-review": "Comprehensive project review: issues, PRs, agents, risks",
    "backlog-review": "Backlog grooming: stale issues, gaps, priorities",
    "sprint-planning": "Sprint planning: prioritize, estimate, organize",
    "prompt-review": "Audit agent prompts for quality and alignment",
    "agent-analysis": "Agent performance analysis and optimization",
    "custom": "Custom task with user-provided prompt",
}


def get_auth_token() -> Optional[str]:
    """Get authentication token from environment variable."""
    return os.getenv("DASHBOARD_AUTH_TOKEN")


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks.

    Args:
        a: First string to compare
        b: Second string to compare

    Returns:
        True if strings are equal, False otherwise

    Security Note:
        Uses Python's built-in hmac.compare_digest() which is specifically
        designed for constant-time comparison to prevent timing side-channel
        attacks. This prevents attackers from determining the correct token
        character by character based on response time differences.

        Strings are encoded to UTF-8 bytes before comparison to support
        unicode characters and ensure compatibility with hmac.compare_digest().
    """
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


def create_auth_middleware():
    """Create authentication middleware that checks token on each request."""
    import logging
    logger = logging.getLogger(__name__)

    @middleware
    async def auth_middleware(request: Request, handler):
        """Authentication middleware - checks bearer token if DASHBOARD_AUTH_TOKEN is set."""
        # Check auth token on every request (dynamic)
        auth_token = get_auth_token()

        # Skip auth if token not configured (dev mode)
        if not auth_token:
            return await handler(request)

        # Skip auth for health endpoint
        if request.path == "/api/health":
            return await handler(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            logger.warning(
                f"Authentication failed: Missing or invalid Authorization header from {request.remote}"
            )
            error = SecurityError(
                message="Missing or invalid Authorization header. Expected format: 'Authorization: Bearer <token>'",
                error_code="SECURITY_AUTH_MISSING",
                auth_type="bearer_token"
            )
            return web.json_response(
                {
                    "error": "Unauthorized",
                    "message": error.message,
                    **error.to_dict()
                },
                status=401
            )

        token = auth_header[7:]  # Remove "Bearer " prefix

        # Use constant-time comparison to prevent timing attacks
        if not constant_time_compare(token, auth_token):
            logger.warning(
                f"Authentication failed: Invalid token from {request.remote}"
            )
            error = SecurityError(
                message="Invalid authentication token",
                error_code="SECURITY_TOKEN_INVALID",
                auth_type="bearer_token"
            )
            return web.json_response(
                {
                    "error": "Unauthorized",
                    "message": error.message,
                    **error.to_dict()
                },
                status=401
            )

        # Token valid, proceed
        return await handler(request)

    return auth_middleware


class RESTAPIServer:
    """Complete REST API server with all required endpoints."""

    def __init__(
        self,
        project_name: str = "agent-dashboard",
        metrics_dir: Optional[Path] = None,
        port: int = 8420,
        host: str = "0.0.0.0"
    ):
        """Initialize REST API server.

        Args:
            project_name: Project name for metrics store
            metrics_dir: Directory containing .agent_metrics.json
            port: HTTP server port (default: 8420)
            host: HTTP server host (default: 0.0.0.0)
        """
        self.project_name = project_name
        self.metrics_dir = metrics_dir or Path.cwd()
        self.port = port
        self.host = host

        # Initialize metrics store
        self.store = MetricsStore(
            project_name=project_name,
            metrics_dir=self.metrics_dir
        )

        # Create app with middlewares
        self.app = web.Application(
            middlewares=[create_auth_middleware(), self._cors_middleware, self._error_middleware]
        )

        # Register routes
        self._setup_routes()

        # Initialize agent states
        for agent_name in ALL_AGENT_NAMES:
            _agent_states[agent_name] = "idle"

        # Initialize agent status details for all panel agents (AI-79 / REQ-MONITOR-001)
        for agent_name in PANEL_AGENT_NAMES:
            if agent_name not in _agent_status_details:
                _agent_status_details[agent_name] = {
                    "name": agent_name,
                    "status": "idle",
                    "current_ticket": None,
                    "started_at": None,
                    # AI-80 / REQ-MONITOR-002: active requirement display fields
                    "ticket_title": None,
                    "description": None,
                    "token_count": 0,
                    "estimated_cost": 0.0,
                }
        # Also ensure ALL_AGENT_NAMES have entries (covers orchestrator etc.)
        for agent_name in ALL_AGENT_NAMES:
            if agent_name not in _agent_status_details:
                _agent_status_details[agent_name] = {
                    "name": agent_name,
                    "status": "idle",
                    "current_ticket": None,
                    "started_at": None,
                    # AI-80 / REQ-MONITOR-002: active requirement display fields
                    "ticket_title": None,
                    "description": None,
                    "token_count": 0,
                    "estimated_cost": 0.0,
                }

        # AI-83: Record server start time for uptime calculation (REQ-METRICS-001)
        if _rest_global_metrics.get("_server_start_time") is None:
            _rest_global_metrics["_server_start_time"] = datetime.utcnow()

    @middleware
    async def _cors_middleware(self, request: Request, handler):
        """Add CORS headers to all responses."""
        response = await handler(request)

        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'

        return response

    @middleware
    async def _error_middleware(self, request: Request, handler):
        """Catch and format errors as JSON responses."""
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except Exception as ex:
            return web.json_response(
                {
                    'error': type(ex).__name__,
                    'message': str(ex),
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                },
                status=500
            )

    def _setup_routes(self):
        """Register all REST API routes."""
        # Health and metrics
        self.app.router.add_get('/api/health', self.health_check)
        self.app.router.add_get('/health', self.health_check)  # alias for playwright config
        self.app.router.add_get('/api/metrics', self.get_metrics)

        # Agents - static routes BEFORE parameterized routes to avoid shadowing
        self.app.router.add_get('/api/agents', self.get_all_agents)
        # Agent Controls - global pause/resume (AI-130/AI-89) registered before {name} routes
        self.app.router.add_post('/api/agents/pause-all', self.pause_all_agents)
        self.app.router.add_post('/api/agents/resume-all', self.resume_all_agents)
        self.app.router.add_get('/api/agents/system-status', self.get_system_status)
        self.app.router.add_get('/api/agent-controls', self.get_all_agent_controls)
        # Agent Status Panel endpoints (AI-79 / REQ-MONITOR-001)
        self.app.router.add_get('/api/agents/status', self.get_all_agents_status)
        # AI-84: Agent Leaderboard (REQ-METRICS-002) - register BEFORE /{name}
        self.app.router.add_get('/api/agents/leaderboard', self.get_agent_leaderboard)
        # AI-81: Agent Detail View (REQ-MONITOR-003) - register BEFORE /{name}
        self.app.router.add_get('/api/agents/{name}/profile', self.get_agent_profile)
        self.app.router.add_post('/api/agents/{name}/events', self.post_agent_recent_event)
        self.app.router.add_get('/api/agents/{name}', self.get_agent)
        self.app.router.add_get('/api/agents/{name}/events', self.get_agent_events)
        self.app.router.add_post('/api/agents/{name}/pause', self.pause_agent)
        self.app.router.add_post('/api/agents/{name}/resume', self.resume_agent)
        self.app.router.add_post('/api/agents/{name}/status', self.update_agent_status)
        self.app.router.add_post('/api/agents/{name}/xp', self.post_agent_xp)
        self.app.router.add_get('/api/agents/{name}/requirements', self.get_agent_requirements_by_name)
        self.app.router.add_put('/api/agents/{name}/requirements', self.update_agent_requirements_by_name)
        # AI-80 / REQ-MONITOR-002: Active Requirement Display endpoints
        self.app.router.add_get('/api/agents/{name}/requirement', self.get_agent_requirement)
        self.app.router.add_post('/api/agents/{name}/metrics', self.update_agent_metrics)

        # Sessions and providers
        self.app.router.add_get('/api/sessions', self.get_sessions)
        self.app.router.add_get('/api/providers', self.get_providers)
        self.app.router.add_get('/api/providers/status', self.get_provider_status)

        # Chat
        self.app.router.add_post('/api/chat', self.chat)

        # Requirements - static routes BEFORE parameterized to avoid shadowing
        # AI-93: Linear sync queue (static paths first)
        self.app.router.add_get('/api/requirements/sync-queue', self.get_sync_queue)
        self.app.router.add_post('/api/requirements/process-sync', self.process_sync)
        # AI-90/AI-91: parameterized routes
        self.app.router.add_put('/api/requirements/{ticket_key}', self.update_requirement)
        self.app.router.add_get('/api/requirements/{ticket_key}', self.get_requirement)
        self.app.router.add_post('/api/requirements/{ticket_key}/sync', self.sync_requirement_to_linear)

        # AI-92: Pause→Edit→Resume cycle
        self.app.router.add_get('/api/agents/{name}/active-requirement', self.get_active_requirement)
        self.app.router.add_post('/api/agents/{name}/acknowledge-requirement', self.acknowledge_requirement)

        # Decisions
        self.app.router.add_get('/api/decisions', self.get_decisions)

        # Dashboard HTML
        self.app.router.add_get('/', self.serve_dashboard)

        # WebSocket for agent_status broadcasts
        self.app.router.add_get('/api/ws', self.ws_handler)

        # AI-82: Orchestrator Pipeline Visualization (REQ-MONITOR-004)
        self.app.router.add_get('/api/orchestrator/pipeline', self.get_pipeline)
        self.app.router.add_post('/api/orchestrator/pipeline', self.set_pipeline)
        self.app.router.add_post('/api/orchestrator/pipeline/step', self.update_pipeline_step)

        # AI-83: Global Metrics Bar (REQ-METRICS-001)
        self.app.router.add_get('/api/metrics/global', self.get_global_metrics)
        self.app.router.add_post('/api/metrics/global', self.post_global_metrics)

        # AI-86: Live Activity Feed (REQ-FEED-001)
        self.app.router.add_get('/api/feed', self.get_feed)
        self.app.router.add_post('/api/feed', self.post_feed)
        self.app.router.add_route('OPTIONS', '/api/feed', self.handle_options)

        # AI-85: Cost and Token Charts (REQ-METRICS-003)
        self.app.router.add_get('/api/charts/token-usage', self.get_chart_token_usage)
        self.app.router.add_post('/api/charts/token-usage', self.post_chart_token_usage)
        self.app.router.add_get('/api/charts/cost-trend', self.get_chart_cost_trend)
        self.app.router.add_get('/api/charts/success-rate', self.get_chart_success_rate)

        # AI-77: GitHub Access - PR and Issue Management (REQ-INTEGRATION-003)
        self.app.router.add_post('/api/github/query', self.github_query)
        self.app.router.add_get('/api/github/prs', self.github_get_prs)
        self.app.router.add_get('/api/github/issues', self.github_get_issues)
        self.app.router.add_get('/api/github/repo', self.github_get_repo)
        self.app.router.add_route('OPTIONS', '/api/github/query', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/github/prs', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/github/issues', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/github/repo', self.handle_options)

        # PM Task Launcher endpoints
        self.app.router.add_get('/api/pm/tasks', self.get_pm_tasks)
        self.app.router.add_post('/api/pm/run', self.run_pm_task)
        self.app.router.add_get('/api/pm/status', self.get_pm_status)
        self.app.router.add_post('/api/pm/stop', self.stop_pm_task)
        self.app.router.add_get('/api/pm/history', self.get_pm_history)

        # AI-229: Webhook Support for CI/CD Pipeline Integration
        self.app.router.add_get('/api/webhooks', self.rest_list_webhooks)
        self.app.router.add_post('/api/webhooks', self.rest_create_webhook)
        self.app.router.add_get('/api/webhooks/deliveries', self.rest_webhook_deliveries)
        self.app.router.add_delete('/api/webhooks/{webhook_id}', self.rest_delete_webhook)
        self.app.router.add_post('/api/webhooks/{webhook_id}/test', self.rest_test_webhook)
        self.app.router.add_post('/api/webhooks/inbound/run-ticket', self.rest_inbound_run_ticket)
        self.app.router.add_post('/api/webhooks/inbound/run-spec', self.rest_inbound_run_spec)

        # AI-220: Free Tier / Billing endpoints
        self.app.router.add_get('/api/billing/usage', self.get_billing_usage)
        self.app.router.add_get('/api/billing/plan', self.get_billing_plan)
        self.app.router.add_post('/api/billing/upgrade', self.post_billing_upgrade)
        self.app.router.add_post('/api/billing/session/start', self.post_billing_session_start)
        self.app.router.add_post('/api/billing/session/end', self.post_billing_session_end)
        # Also expose usage at legacy path used by dashboard.html
        self.app.router.add_get('/api/usage', self.get_billing_usage)

        # OPTIONS for CORS preflight
        for route in ['/api/metrics', '/api/agents', '/api/sessions', '/api/providers',
                      '/api/chat', '/api/decisions', '/api/agents/status',
                      '/api/orchestrator/pipeline', '/api/metrics/global',
                      '/api/charts/token-usage', '/api/charts/cost-trend',
                      '/api/charts/success-rate',
                      '/api/pm/tasks', '/api/pm/run', '/api/pm/status',
                      '/api/pm/stop', '/api/pm/history',
                      '/api/webhooks', '/api/webhooks/deliveries',
                      '/api/webhooks/inbound/run-ticket',
                      '/api/webhooks/inbound/run-spec',
                      '/api/billing/usage', '/api/billing/plan',
                      '/api/billing/upgrade',
                      '/api/billing/session/start', '/api/billing/session/end',
                      '/api/usage']:
            self.app.router.add_route('OPTIONS', route, self.handle_options)

    async def handle_options(self, request: Request) -> Response:
        """Handle CORS preflight OPTIONS requests."""
        return web.Response(status=204)

    async def health_check(self, request: Request) -> Response:
        """GET /api/health - Health check endpoint.

        Returns:
            200 OK with status information
        """
        try:
            stats = self.store.get_stats()

            health_data = {
                'status': 'ok',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'project': self.project_name,
                'metrics_file_exists': stats['metrics_file_exists'],
                'event_count': stats['event_count'],
                'session_count': stats['session_count'],
                'agent_count': stats['agent_count']
            }

            return web.json_response(health_data)
        except Exception as e:
            return web.json_response({
                'status': 'error',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'error': str(e)
            }, status=503)

    async def get_metrics(self, request: Request) -> Response:
        """GET /api/metrics - Get current DashboardState.

        Returns:
            200 OK with complete DashboardState
        """
        state = self.store.load()
        return web.json_response(state)

    async def get_all_agents(self, request: Request) -> Response:
        """GET /api/agents - Get all agent profiles.

        Returns:
            200 OK with list of all agent profiles
        """
        state = self.store.load()

        # Return agents as a list with their current state
        agents_list = []
        for agent_name in ALL_AGENT_NAMES:
            agent_data = state['agents'].get(agent_name, {})
            agent_data['current_state'] = _agent_states.get(agent_name, 'idle')
            agents_list.append(agent_data)

        return web.json_response({
            'agents': agents_list,
            'total_agents': len(agents_list),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def get_agent(self, request: Request) -> Response:
        """GET /api/agents/{name} - Get single agent profile.

        Args:
            name: Agent name (path parameter)

        Returns:
            200 OK with agent profile
            404 Not Found if agent doesn't exist
        """
        agent_name = request.match_info['name']
        state = self.store.load()

        if agent_name not in ALL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
                'available_agents': ALL_AGENT_NAMES
            }, status=404)

        agent_data = state['agents'].get(agent_name, {})
        agent_data['current_state'] = _agent_states.get(agent_name, 'idle')

        return web.json_response({
            'agent': agent_data,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def get_agent_events(self, request: Request) -> Response:
        """GET /api/agents/{name}/events - Get recent events for an agent.

        Args:
            name: Agent name (path parameter)
            limit: Maximum number of events to return (query param, default: 20)

        Returns:
            200 OK with list of recent events
            404 Not Found if agent doesn't exist
        """
        agent_name = request.match_info['name']
        limit = int(request.query.get('limit', '20'))

        if agent_name not in ALL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name
            }, status=404)

        state = self.store.load()

        # Filter events for this agent
        agent_events = [
            event for event in state['events']
            if event['agent_name'] == agent_name
        ]

        # Return last N events
        recent_events = agent_events[-limit:]

        return web.json_response({
            'agent_name': agent_name,
            'events': recent_events,
            'total_events': len(agent_events),
            'returned_events': len(recent_events),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def get_sessions(self, request: Request) -> Response:
        """GET /api/sessions - Get session history.

        Args:
            limit: Maximum number of sessions to return (query param, default: 50)

        Returns:
            200 OK with list of sessions
        """
        limit = int(request.query.get('limit', '50'))
        state = self.store.load()

        sessions = state['sessions'][-limit:]

        return web.json_response({
            'sessions': sessions,
            'total_sessions': len(state['sessions']),
            'returned_sessions': len(sessions),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def get_providers(self, request: Request) -> Response:
        """GET /api/providers - Get available AI providers and models.

        Provider availability is determined by checking environment variables:
        - Claude: ANTHROPIC_API_KEY
        - ChatGPT: OPENAI_API_KEY
        - Gemini: GEMINI_API_KEY or GOOGLE_API_KEY
        - Groq: GROQ_API_KEY
        - KIMI: KIMI_API_KEY or MOONSHOT_API_KEY
        - Windsurf: WINDSURF_API_KEY

        Returns:
            200 OK with list of providers and their models
        """
        providers = [
            {
                'name': 'Claude',
                'provider_id': 'claude',
                'models': ['haiku-4-5', 'sonnet-4-5', 'opus-4-6'],
                'default_model': 'sonnet-4-5',
                'available': bool(os.getenv('ANTHROPIC_API_KEY')),
                'description': 'Anthropic Claude models (default)'
            },
            {
                'name': 'ChatGPT',
                'provider_id': 'openai',
                'models': ['gpt-4o', 'o1', 'o3-mini', 'o4-mini'],
                'default_model': 'gpt-4o',
                'available': bool(os.getenv('OPENAI_API_KEY')),
                'description': 'OpenAI ChatGPT models'
            },
            {
                'name': 'Gemini',
                'provider_id': 'gemini',
                'models': ['2.5-flash', '2.5-pro', '2.0-flash'],
                'default_model': '2.5-flash',
                'available': bool(os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')),
                'description': 'Google Gemini models'
            },
            {
                'name': 'Groq',
                'provider_id': 'groq',
                'models': ['llama-3.3-70b', 'mixtral-8x7b'],
                'default_model': 'llama-3.3-70b',
                'available': bool(os.getenv('GROQ_API_KEY')),
                'description': 'Groq ultra-fast inference'
            },
            {
                'name': 'KIMI',
                'provider_id': 'kimi',
                'models': ['moonshot-v1'],
                'default_model': 'moonshot-v1',
                'available': bool(os.getenv('KIMI_API_KEY') or os.getenv('MOONSHOT_API_KEY')),
                'description': 'Moonshot KIMI (2M token context)'
            },
            {
                'name': 'Windsurf',
                'provider_id': 'windsurf',
                'models': ['cascade'],
                'default_model': 'cascade',
                'available': bool(os.getenv('WINDSURF_API_KEY')),
                'description': 'Codeium Windsurf IDE'
            }
        ]

        return web.json_response({
            'providers': providers,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def get_provider_status(self, request: Request) -> Response:
        """GET /api/providers/status - Get detailed provider status with API key validation.

        Returns:
            200 OK with provider status details including bridge availability
        """
        providers_status = []

        # Claude / Anthropic
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        claude_status = 'available' if anthropic_key else 'unconfigured'
        providers_status.append({
            'provider_id': 'claude',
            'name': 'Claude',
            'available': bool(anthropic_key),
            'has_api_key': bool(anthropic_key),
            'status': claude_status,
            'status_indicator': 'green' if anthropic_key else 'yellow',
            'models': ['haiku-4.5', 'sonnet-4.5', 'opus-4.6'],
            'default_model': 'sonnet-4.5',
            'bridge_available': True,
            'description': 'Anthropic Claude models'
        })

        # OpenAI / ChatGPT
        openai_key = os.getenv('OPENAI_API_KEY')
        openai_status = 'available' if openai_key else 'unconfigured'
        try:
            from bridges.openai_bridge import OpenAIBridge
            openai_bridge_available = True
        except ImportError:
            openai_bridge_available = False

        providers_status.append({
            'provider_id': 'openai',
            'name': 'ChatGPT',
            'available': bool(openai_key),
            'has_api_key': bool(openai_key),
            'status': openai_status,
            'status_indicator': 'green' if openai_key else 'yellow',
            'models': ['gpt-4o', 'o1', 'o3-mini', 'o4-mini'],
            'default_model': 'gpt-4o',
            'bridge_available': openai_bridge_available,
            'description': 'OpenAI ChatGPT models'
        })

        # Gemini
        gemini_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        gemini_status = 'available' if gemini_key else 'unconfigured'
        try:
            from bridges.gemini_bridge import GeminiBridge
            gemini_bridge_available = True
        except ImportError:
            gemini_bridge_available = False
            if gemini_key:
                gemini_status = 'error'

        providers_status.append({
            'provider_id': 'gemini',
            'name': 'Gemini',
            'available': bool(gemini_key) and gemini_bridge_available,
            'has_api_key': bool(gemini_key),
            'status': gemini_status,
            'status_indicator': 'green' if (gemini_key and gemini_bridge_available) else ('red' if gemini_key else 'yellow'),
            'models': ['2.5-flash', '2.5-pro', '2.0-flash'],
            'default_model': '2.5-flash',
            'bridge_available': gemini_bridge_available,
            'description': 'Google Gemini models'
        })

        # Groq
        groq_key = os.getenv('GROQ_API_KEY')
        groq_status = 'available' if groq_key else 'unconfigured'
        try:
            from bridges.groq_bridge import GroqBridge
            groq_bridge_available = True
        except ImportError:
            groq_bridge_available = False
            if groq_key:
                groq_status = 'error'

        providers_status.append({
            'provider_id': 'groq',
            'name': 'Groq',
            'available': bool(groq_key) and groq_bridge_available,
            'has_api_key': bool(groq_key),
            'status': groq_status,
            'status_indicator': 'green' if (groq_key and groq_bridge_available) else ('red' if groq_key else 'yellow'),
            'models': ['llama-3.3-70b', 'mixtral-8x7b'],
            'default_model': 'llama-3.3-70b',
            'bridge_available': groq_bridge_available,
            'description': 'Groq ultra-fast LPU inference'
        })

        # KIMI
        kimi_key = os.getenv('KIMI_API_KEY') or os.getenv('MOONSHOT_API_KEY')
        kimi_status = 'available' if kimi_key else 'unconfigured'
        try:
            from bridges.kimi_bridge import KimiBridge
            kimi_bridge_available = True
        except ImportError:
            kimi_bridge_available = False
            if kimi_key:
                kimi_status = 'error'

        providers_status.append({
            'provider_id': 'kimi',
            'name': 'KIMI',
            'available': bool(kimi_key) and kimi_bridge_available,
            'has_api_key': bool(kimi_key),
            'status': kimi_status,
            'status_indicator': 'green' if (kimi_key and kimi_bridge_available) else ('red' if kimi_key else 'yellow'),
            'models': ['moonshot-v1'],
            'default_model': 'moonshot-v1',
            'bridge_available': kimi_bridge_available,
            'description': 'Moonshot KIMI (2M token context)'
        })

        # Windsurf
        windsurf_key = os.getenv('WINDSURF_API_KEY')
        windsurf_status = 'unconfigured'  # Not yet implemented
        try:
            from bridges.windsurf_bridge import WindsurfBridge
            windsurf_bridge_available = True
        except ImportError:
            windsurf_bridge_available = False

        providers_status.append({
            'provider_id': 'windsurf',
            'name': 'Windsurf',
            'available': False,  # Not implemented yet
            'has_api_key': bool(windsurf_key),
            'status': windsurf_status,
            'status_indicator': 'yellow',
            'models': ['cascade'],
            'default_model': 'cascade',
            'bridge_available': windsurf_bridge_available,
            'description': 'Codeium Windsurf IDE (coming soon)'
        })

        return web.json_response({
            'providers': providers_status,
            'total_providers': len(providers_status),
            'active_providers': sum(1 for p in providers_status if p['available']),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def chat(self, request: Request) -> Response:
        """POST /api/chat - Send chat message (streaming response).

        Request body:
            {
                "message": "User message",
                "provider": "claude" (optional, default: claude),
                "model": "sonnet-4-5" (optional),
                "session_id": "session-123" (optional),
                "conversation_history": [] (optional)
            }

        Returns:
            200 OK with streaming Server-Sent Events (SSE) response
            400 Bad Request for invalid input
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({
                'error': 'Invalid JSON in request body'
            }, status=400)

        message = data.get('message')
        if not message:
            return web.json_response({
                'error': 'Missing required field: message'
            }, status=400)

        provider = data.get('provider', 'claude')
        model = data.get('model', 'sonnet-4.5')
        session_id = data.get('session_id')
        conversation_history = data.get('conversation_history', [])

        # Import chat handler
        try:
            from dashboard.chat_handler import stream_chat_response
        except ImportError:
            # Fallback to mock response if chat_handler not available
            return web.json_response({
                'response': f'Received message: {message}',
                'provider': provider,
                'model': model,
                'session_id': session_id,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'status': 'success',
                'note': 'Chat handler not available, using fallback'
            })

        # Stream response using Server-Sent Events
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )

        await response.prepare(request)

        try:
            async for chunk in stream_chat_response(
                message=message,
                provider=provider,
                model=model,
                conversation_history=conversation_history
            ):
                # Send as Server-Sent Event
                event_data = f"data: {json.dumps(chunk)}\n\n"
                await response.write(event_data.encode('utf-8'))
                await response.drain()

        except Exception as e:
            # Send error event
            error_chunk = {
                'type': 'error',
                'content': str(e),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
            event_data = f"data: {json.dumps(error_chunk)}\n\n"
            await response.write(event_data.encode('utf-8'))

        await response.write_eof()
        return response

    async def pause_agent(self, request: Request) -> Response:
        """POST /api/agents/{name}/pause - Pause an agent (AI-87).

        Marks the agent as paused so it will not accept new delegations.
        Does NOT abort any in-progress task.

        Args:
            name: Agent name (path parameter)

        Returns:
            200 OK with {name, previous_status, new_status, message}
            404 Not Found if agent doesn't exist
        """
        agent_name = request.match_info['name']

        if agent_name not in ALL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name
            }, status=404)

        # Track previous status (idempotent: already paused is fine)
        previous_status = _agent_states.get(agent_name, 'idle')

        # Update agent state
        _agent_states[agent_name] = 'paused'

        # Also sync the status panel details
        if agent_name in _agent_status_details:
            _agent_status_details[agent_name]['status'] = 'paused'

        # Capture current ticket for feed event
        current_ticket = None
        if agent_name in _agent_status_details:
            current_ticket = _agent_status_details[agent_name].get('current_ticket')

        # AI-92: Store active requirement entry (unacknowledged) so resume can return it
        if current_ticket:
            existing_active = _agent_active_requirements.get(agent_name, {})
            # Only reset acknowledgement if this is a new ticket
            if existing_active.get('ticket_key') != current_ticket:
                _agent_active_requirements[agent_name] = {
                    'ticket_key': current_ticket,
                    'acknowledged': False,
                    'updated_at': datetime.utcnow().isoformat() + 'Z',
                }

        # Log decision
        _decisions_log.append({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'decision_type': 'agent_pause',
            'agent_name': agent_name,
            'previous_state': previous_status,
            'new_state': 'paused'
        })

        # Add feed event (AI-87)
        import json as _json
        from uuid import uuid4 as _uuid4
        feed_event = {
            'id': str(_uuid4()),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'agent': agent_name,
            'status': 'in_progress',
            'ticket_key': current_ticket,
            'duration_s': None,
            'description': f'Agent {agent_name} paused by user',
        }
        _rest_feed_events.append(feed_event)
        while len(_rest_feed_events) > _REST_FEED_MAX:
            del _rest_feed_events[0]

        # Broadcast status change via WebSocket
        await self._broadcast_agent_status(agent_name, 'paused')

        # Broadcast feed_update via WebSocket
        feed_payload = _json.dumps({
            'type': 'feed_update',
            'event': feed_event,
            'timestamp': feed_event['timestamp'],
        })
        dead_clients: set = set()
        for ws in list(_ws_clients):
            try:
                await ws.send_str(feed_payload)
            except Exception:
                dead_clients.add(ws)
        for ws in dead_clients:
            _ws_clients.discard(ws)

        # Broadcast system chat message via WebSocket
        chat_payload = _json.dumps({
            'type': 'system_message',
            'text': f'Agent {agent_name} paused by user',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })
        for ws in list(_ws_clients):
            try:
                await ws.send_str(chat_payload)
            except Exception:
                pass

        return web.json_response({
            'name': agent_name,
            'previous_status': previous_status,
            'new_status': 'paused',
            'message': f'Agent {agent_name} paused',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def resume_agent(self, request: Request) -> Response:
        """POST /api/agents/{name}/resume - Resume a paused agent (AI-88).

        Restores the agent to idle so it can accept new delegations.

        Args:
            name: Agent name (path parameter)

        Returns:
            200 OK with {name, previous_status, new_status, message}
            404 Not Found if agent doesn't exist
        """
        agent_name = request.match_info['name']

        if agent_name not in ALL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name
            }, status=404)

        # Track previous status (idempotent: already idle is fine)
        previous_status = _agent_states.get(agent_name, 'paused')

        # Update agent state
        _agent_states[agent_name] = 'idle'

        # Also sync the status panel details
        if agent_name in _agent_status_details:
            _agent_status_details[agent_name]['status'] = 'idle'

        # Log decision
        _decisions_log.append({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'decision_type': 'agent_resume',
            'agent_name': agent_name,
            'previous_state': previous_status,
            'new_state': 'idle'
        })

        # Add feed event (AI-88)
        import json as _json
        from uuid import uuid4 as _uuid4
        feed_event = {
            'id': str(_uuid4()),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'agent': agent_name,
            'status': 'success',
            'ticket_key': None,
            'duration_s': None,
            'description': f'Agent {agent_name} resumed by user',
        }
        _rest_feed_events.append(feed_event)
        while len(_rest_feed_events) > _REST_FEED_MAX:
            del _rest_feed_events[0]

        # Broadcast status change via WebSocket
        await self._broadcast_agent_status(agent_name, 'idle')

        # Broadcast feed_update via WebSocket
        feed_payload = _json.dumps({
            'type': 'feed_update',
            'event': feed_event,
            'timestamp': feed_event['timestamp'],
        })
        dead_clients: set = set()
        for ws in list(_ws_clients):
            try:
                await ws.send_str(feed_payload)
            except Exception:
                dead_clients.add(ws)
        for ws in dead_clients:
            _ws_clients.discard(ws)

        # Broadcast system chat message via WebSocket
        chat_payload = _json.dumps({
            'type': 'system_message',
            'text': f'Agent {agent_name} resumed by user',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })
        for ws in list(_ws_clients):
            try:
                await ws.send_str(chat_payload)
            except Exception:
                pass

        # AI-92: Check for an edited (unacknowledged) requirement for this agent
        updated_requirement = None
        active_req = _agent_active_requirements.get(agent_name)
        if active_req and not active_req.get('acknowledged', False):
            ticket_key = active_req.get('ticket_key')
            req_entry = _requirements_store.get(ticket_key) if ticket_key else None
            if req_entry:
                updated_requirement = {
                    'ticket_key': ticket_key,
                    'edited_description': req_entry.get('edited_description', ''),
                    'last_edited': req_entry.get('last_edited'),
                }

        response_body = {
            'name': agent_name,
            'previous_status': previous_status,
            'new_status': 'idle',
            'message': f'Agent {agent_name} resumed',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        }
        if updated_requirement is not None:
            response_body['updated_requirement'] = updated_requirement

        return web.json_response(response_body)

    # -------------------------------------------------------------------------
    # AI-130: Global Pause/Resume & Agent Controls
    # -------------------------------------------------------------------------

    async def pause_all_agents(self, request: Request) -> Response:
        """POST /api/agents/pause-all - Pause all 13 panel agents (AI-89).

        Sets ALL agents to "paused" status, sets _system_paused = True,
        adds a single orchestrator feed event, and broadcasts a
        system_status_change WebSocket event.

        Returns:
            200 OK with paused_count and message
        """
        global _system_paused

        for agent_name in ALL_AGENT_NAMES:
            _agent_states[agent_name] = 'paused'
            # Sync the status panel details
            if agent_name in _agent_status_details:
                _agent_status_details[agent_name]['status'] = 'paused'
            # Ensure requirements entry exists in cache
            if agent_name not in _requirements_cache:
                _requirements_cache[agent_name] = ''

        _system_paused = True

        timestamp = datetime.utcnow().isoformat() + 'Z'

        # Add single orchestrator feed event
        feed_event = {
            'agent': 'orchestrator',
            'ticket_key': None,
            'duration_s': None,
            'description': 'All agents paused by user',
            'status': 'in_progress',
            'timestamp': timestamp,
        }
        _rest_feed_events.append(feed_event)
        if len(_rest_feed_events) > _REST_FEED_MAX:
            _rest_feed_events.pop(0)

        _decisions_log.append({
            'timestamp': timestamp,
            'decision_type': 'pause_all',
            'agent_count': len(ALL_AGENT_NAMES)
        })

        # Broadcast system_status_change via WebSocket
        await self._broadcast_system_status()

        return web.json_response({
            'status': 'ok',
            'paused_count': len(ALL_AGENT_NAMES),
            'message': f'All {len(ALL_AGENT_NAMES)} agents paused',
            'timestamp': timestamp,
        })

    async def resume_all_agents(self, request: Request) -> Response:
        """POST /api/agents/resume-all - Resume all paused agents (AI-89).

        Sets agents that are "paused" back to "idle" (does not affect
        running agents), sets _system_paused = False, adds a feed event,
        and broadcasts a system_status_change WebSocket event.

        Returns:
            200 OK with resumed_count and message
        """
        global _system_paused

        # Only resume agents that are currently paused (don't affect running)
        resumed = []
        for agent_name in ALL_AGENT_NAMES:
            if _agent_states.get(agent_name, 'idle') == 'paused':
                _agent_states[agent_name] = 'idle'
                if agent_name in _agent_status_details:
                    _agent_status_details[agent_name]['status'] = 'idle'
                resumed.append(agent_name)

        _system_paused = False

        timestamp = datetime.utcnow().isoformat() + 'Z'

        # Add orchestrator feed event
        feed_event = {
            'agent': 'orchestrator',
            'ticket_key': None,
            'duration_s': None,
            'description': 'All agents resumed by user',
            'status': 'success',
            'timestamp': timestamp,
        }
        _rest_feed_events.append(feed_event)
        if len(_rest_feed_events) > _REST_FEED_MAX:
            _rest_feed_events.pop(0)

        _decisions_log.append({
            'timestamp': timestamp,
            'decision_type': 'resume_all',
            'agent_count': len(resumed)
        })

        # Broadcast system_status_change via WebSocket
        await self._broadcast_system_status()

        return web.json_response({
            'status': 'ok',
            'resumed_count': len(resumed),
            'message': f'{len(resumed)} agents resumed',
            'timestamp': timestamp,
        })

    async def get_system_status(self, request: Request) -> Response:
        """GET /api/agents/system-status - Return global pause state (AI-89).

        Returns:
            200 OK with system_paused flag and per-status agent counts
        """
        paused_count = sum(
            1 for s in _agent_states.values() if s == 'paused'
        )
        running_count = sum(
            1 for s in _agent_states.values() if s == 'running'
        )
        return web.json_response({
            'system_paused': _system_paused,
            'paused_agent_count': paused_count,
            'running_count': running_count,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })

    async def _broadcast_system_status(self) -> None:
        """Broadcast a system_status_change event to all WebSocket clients (AI-89)."""
        if not _ws_clients:
            return

        paused_count = sum(1 for s in _agent_states.values() if s == 'paused')
        running_count = sum(1 for s in _agent_states.values() if s == 'running')

        payload = json.dumps({
            'type': 'system_status_change',
            'system_paused': _system_paused,
            'paused_agent_count': paused_count,
            'running_count': running_count,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })

        dead_clients = set()
        for ws in list(_ws_clients):
            try:
                await ws.send_str(payload)
            except Exception:
                dead_clients.add(ws)

        for ws in dead_clients:
            _ws_clients.discard(ws)

    async def get_all_agent_controls(self, request: Request) -> Response:
        """GET /api/agent-controls - Get pause/resume state and requirements for all agents.

        Returns:
            200 OK with control state for all agents
        """
        controls = {}
        for agent_name in ALL_AGENT_NAMES:
            controls[agent_name] = {
                'paused': _agent_states.get(agent_name, 'idle') == 'paused',
                'requirements': _requirements_cache.get(agent_name, '')
            }

        paused_count = sum(1 for s in _agent_states.values() if s == 'paused')

        return web.json_response({
            'agent_controls': controls,
            'total_agents': len(ALL_AGENT_NAMES),
            'paused_count': paused_count,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def get_agent_requirements_by_name(self, request: Request) -> Response:
        """GET /api/agents/{name}/requirements - Get requirements for a specific agent.

        Returns:
            200 OK with requirements and pause state
        """
        agent_name = request.match_info['name']
        requirements = _requirements_cache.get(agent_name, '')
        paused = _agent_states.get(agent_name, 'idle') == 'paused'

        return web.json_response({
            'agent_id': agent_name,
            'requirements': requirements,
            'paused': paused,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def update_agent_requirements_by_name(self, request: Request) -> Response:
        """PUT /api/agents/{name}/requirements - Update requirements for a specific agent.

        Request body:
            {"requirements": "Updated requirement text"}

        Returns:
            200 OK with confirmation
            400 Bad Request for invalid input
        """
        agent_name = request.match_info['name']

        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({'error': 'Invalid JSON in request body'}, status=400)

        requirements = data.get('requirements')
        if requirements is None:
            return web.json_response(
                {'error': 'Missing required field: requirements'},
                status=400
            )

        if len(requirements) > 50_000:
            return web.json_response(
                {'error': 'Requirements text exceeds maximum length of 50000 characters'},
                status=400
            )

        _requirements_cache[agent_name] = requirements

        _decisions_log.append({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'decision_type': 'requirement_update',
            'agent_name': agent_name,
            'requirements_length': len(requirements)
        })

        return web.json_response({
            'status': 'ok',
            'agent_id': agent_name,
            'requirements': requirements,
            'paused': _agent_states.get(agent_name, 'idle') == 'paused',
            'message': f'Requirements for {agent_name} updated successfully',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def update_requirement(self, request: Request) -> Response:
        """PUT /api/requirements/{ticket_key} - Update requirement instructions.

        AI-90/AI-91: Enhanced to store full requirement data model including
        title, description, edited_description, spec_text, sync_to_linear, last_edited.

        Args:
            ticket_key: Linear ticket key (path parameter)

        Request body (flexible - accepts either legacy or new format):
            {
                "requirements": "Updated requirement text",        # legacy field
                "edited_description": "Edited description text",  # new field (AI-91)
                "title": "Ticket title",                          # optional
                "description": "Original description",            # optional
                "spec_text": "App spec text",                     # optional
                "sync_to_linear": false                           # optional toggle
            }

        Returns:
            200 OK with confirmation
            400 Bad Request for invalid input
        """
        ticket_key = request.match_info['ticket_key']

        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({
                'error': 'Invalid JSON in request body'
            }, status=400)

        # Support both legacy 'requirements' field and new 'edited_description' field
        edited_description = data.get('edited_description') or data.get('requirements')
        if edited_description is None:
            return web.json_response({
                'error': 'Missing required field: requirements or edited_description'
            }, status=400)

        if len(edited_description) > 50_000:
            return web.json_response({
                'error': 'Requirements text exceeds maximum length of 50000 characters'
            }, status=400)

        now = datetime.utcnow().isoformat() + 'Z'

        # Build or update the rich requirements entry
        existing = _requirements_store.get(ticket_key, {})
        entry = {
            'ticket_key': ticket_key,
            'title': data.get('title') or existing.get('title') or '',
            'description': data.get('description') or existing.get('description') or '',
            'spec_text': data.get('spec_text') or existing.get('spec_text') or '',
            'edited_description': edited_description,
            'last_edited': now,
            'sync_to_linear': data.get('sync_to_linear', existing.get('sync_to_linear', False)),
            'linear_synced': False,
        }
        _requirements_store[ticket_key] = entry

        # Also keep legacy cache in sync
        _requirements_cache[ticket_key] = edited_description

        # AI-93: if sync_to_linear is requested, add to sync queue
        queued_for_sync = False
        sync_to_linear = entry.get('sync_to_linear', False)
        if sync_to_linear:
            _linear_sync_queue.append({
                'ticket_key': ticket_key,
                'edited_description': edited_description,
                'queued_at': now,
                'processed': False,
            })
            queued_for_sync = True

        # Log decision
        _decisions_log.append({
            'timestamp': now,
            'decision_type': 'requirement_update',
            'ticket_key': ticket_key,
            'requirements_length': len(edited_description),
            'queued_for_sync': queued_for_sync,
        })

        return web.json_response({
            'status': 'success',
            'ticket_key': ticket_key,
            'message': f'Requirements for {ticket_key} updated',
            'requirement': entry,
            'queued_for_sync': queued_for_sync,
            'timestamp': now
        })

    async def get_requirement(self, request: Request) -> Response:
        """GET /api/requirements/{ticket_key} - Get current requirement instructions.

        AI-90/AI-91: Returns full requirement data model including title, description,
        edited_description, spec_text, last_edited, sync_to_linear.

        Args:
            ticket_key: Linear ticket key (path parameter)

        Returns:
            200 OK with full requirement object
            404 Not Found if requirement doesn't exist
        """
        ticket_key = request.match_info['ticket_key']

        entry = _requirements_store.get(ticket_key)

        if entry is None:
            # Also check legacy cache for backwards compatibility
            legacy_text = _requirements_cache.get(ticket_key)
            if legacy_text is None:
                return web.json_response({
                    'error': 'Requirement not found',
                    'ticket_key': ticket_key,
                    'message': f'No requirements found for {ticket_key}'
                }, status=404)
            # Promote legacy entry to rich format
            entry = {
                'ticket_key': ticket_key,
                'title': '',
                'description': legacy_text,
                'spec_text': '',
                'edited_description': legacy_text,
                'last_edited': None,
                'sync_to_linear': False,
                'linear_synced': False,
            }

        return web.json_response({
            'ticket_key': ticket_key,
            'title': entry.get('title', ''),
            'description': entry.get('description', ''),
            'spec_text': entry.get('spec_text', ''),
            'edited_description': entry.get('edited_description', ''),
            'last_edited': entry.get('last_edited'),
            'sync_to_linear': entry.get('sync_to_linear', False),
            'linear_synced': entry.get('linear_synced', False),
            # Legacy compat field
            'requirements': entry.get('edited_description', ''),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def sync_requirement_to_linear(self, request: Request) -> Response:
        """POST /api/requirements/{ticket_key}/sync - Sync requirement changes to Linear.

        AI-91: Marks the stored requirement as synced. In practice stores the sync
        state in-memory and marks linear_synced=True. A real integration would call
        the Linear API here.

        Args:
            ticket_key: Linear ticket key (path parameter)

        Returns:
            200 OK with sync confirmation
            404 Not Found if requirement doesn't exist
        """
        ticket_key = request.match_info['ticket_key']

        entry = _requirements_store.get(ticket_key)
        if entry is None:
            return web.json_response({
                'error': 'Requirement not found',
                'ticket_key': ticket_key,
                'message': f'No requirements found for {ticket_key}. Save requirement first.'
            }, status=404)

        # Mark as synced
        entry['linear_synced'] = True
        entry['sync_to_linear'] = True
        _requirements_store[ticket_key] = entry

        now = datetime.utcnow().isoformat() + 'Z'
        _decisions_log.append({
            'timestamp': now,
            'decision_type': 'requirement_sync',
            'ticket_key': ticket_key,
        })

        return web.json_response({
            'status': 'success',
            'ticket_key': ticket_key,
            'message': f'Requirement for {ticket_key} marked as synced to Linear',
            'linear_synced': True,
            'timestamp': now
        })

    # -------------------------------------------------------------------------
    # AI-92: Pause → Edit → Resume cycle endpoints
    # -------------------------------------------------------------------------

    async def get_active_requirement(self, request: Request) -> Response:
        """GET /api/agents/{name}/active-requirement - Return current active requirement for an agent.

        AI-92: Returns the requirement the agent is currently working on, including
        a ``used_on_resume`` flag indicating whether it has been acknowledged since
        the last edit.

        Returns:
            200 OK with {agent_name, ticket_key, requirement, acknowledged, used_on_resume}
            404 Not Found if no active requirement is set for this agent
        """
        agent_name = request.match_info['name']

        if agent_name not in ALL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
            }, status=404)

        active_req = _agent_active_requirements.get(agent_name)
        if active_req is None:
            return web.json_response({
                'error': 'No active requirement found',
                'agent_name': agent_name,
            }, status=404)

        ticket_key = active_req.get('ticket_key')
        req_entry = _requirements_store.get(ticket_key, {}) if ticket_key else {}
        acknowledged = active_req.get('acknowledged', False)

        return web.json_response({
            'agent_name': agent_name,
            'ticket_key': ticket_key,
            'requirement': req_entry,
            'acknowledged': acknowledged,
            'used_on_resume': acknowledged,
            'updated_at': active_req.get('updated_at'),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })

    async def acknowledge_requirement(self, request: Request) -> Response:
        """POST /api/agents/{name}/acknowledge-requirement - Acknowledge the active requirement.

        AI-92: Marks the requirement as acknowledged (i.e., used after resume).
        The orchestrator calls this after resuming an agent so the dashboard
        knows the edited requirement has been consumed.

        Returns:
            200 OK with {agent_name, ticket_key, acknowledged}
            404 Not Found if no active requirement is set for this agent
        """
        agent_name = request.match_info['name']

        if agent_name not in ALL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
            }, status=404)

        active_req = _agent_active_requirements.get(agent_name)
        if active_req is None:
            # Allow creating an acknowledgement via request body
            try:
                body = await request.json()
            except Exception:
                body = {}
            ticket_key = body.get('ticket_key', '')
            if not ticket_key:
                return web.json_response({
                    'error': 'No active requirement to acknowledge',
                    'agent_name': agent_name,
                }, status=404)
            _agent_active_requirements[agent_name] = {
                'ticket_key': ticket_key,
                'acknowledged': True,
                'updated_at': datetime.utcnow().isoformat() + 'Z',
            }
            return web.json_response({
                'agent_name': agent_name,
                'ticket_key': ticket_key,
                'acknowledged': True,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
            })

        active_req['acknowledged'] = True
        active_req['acknowledged_at'] = datetime.utcnow().isoformat() + 'Z'
        _agent_active_requirements[agent_name] = active_req

        now = datetime.utcnow().isoformat() + 'Z'
        _decisions_log.append({
            'timestamp': now,
            'decision_type': 'requirement_acknowledged',
            'agent_name': agent_name,
            'ticket_key': active_req.get('ticket_key'),
        })

        return web.json_response({
            'agent_name': agent_name,
            'ticket_key': active_req.get('ticket_key'),
            'acknowledged': True,
            'timestamp': now,
        })

    # -------------------------------------------------------------------------
    # AI-93: Linear sync queue endpoints
    # -------------------------------------------------------------------------

    async def get_sync_queue(self, request: Request) -> Response:
        """GET /api/requirements/sync-queue - Return list of tickets queued for Linear sync.

        AI-93: Returns all items in the sync queue with their processing status.
        Query param ``pending_only=true`` filters to only unprocessed items.

        Returns:
            200 OK with {queue, total, pending_count}
        """
        pending_only = request.query.get('pending_only', 'false').lower() == 'true'
        if pending_only:
            queue = [item for item in _linear_sync_queue if not item.get('processed', False)]
        else:
            queue = list(_linear_sync_queue)

        pending_count = sum(1 for item in _linear_sync_queue if not item.get('processed', False))

        return web.json_response({
            'queue': queue,
            'total': len(_linear_sync_queue),
            'pending_count': pending_count,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })

    async def process_sync(self, request: Request) -> Response:
        """POST /api/requirements/process-sync - Mark sync queue items as processed.

        AI-93: The orchestrator calls this after successfully syncing requirement
        changes to Linear. Accepts a list of ticket_keys to mark as processed.
        If no ticket_keys provided, marks ALL pending items as processed.

        Request body (optional):
            {"ticket_keys": ["AI-123", "AI-456"]}

        Returns:
            200 OK with {processed_count, items}
        """
        try:
            body = await request.json()
        except Exception:
            body = {}

        ticket_keys = body.get('ticket_keys')
        now = datetime.utcnow().isoformat() + 'Z'
        processed_items = []

        for item in _linear_sync_queue:
            if item.get('processed', False):
                continue
            if ticket_keys is None or item.get('ticket_key') in ticket_keys:
                item['processed'] = True
                item['processed_at'] = now
                processed_items.append(item.get('ticket_key'))

                # Mark linear_synced in requirements store
                tk = item.get('ticket_key')
                if tk and tk in _requirements_store:
                    _requirements_store[tk]['linear_synced'] = True

        _decisions_log.append({
            'timestamp': now,
            'decision_type': 'sync_processed',
            'processed_ticket_keys': processed_items,
        })

        return web.json_response({
            'processed_count': len(processed_items),
            'items': processed_items,
            'timestamp': now,
        })

    async def get_decisions(self, request: Request) -> Response:
        """GET /api/decisions - Get decision history log.

        Args:
            limit: Maximum number of decisions to return (query param, default: 100)

        Returns:
            200 OK with list of decisions
        """
        limit = int(request.query.get('limit', '100'))

        decisions = _decisions_log[-limit:]

        return web.json_response({
            'decisions': decisions,
            'total_decisions': len(_decisions_log),
            'returned_decisions': len(decisions),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def ws_handler(self, request: Request):
        """GET /api/ws - WebSocket endpoint for real-time agent status broadcasts.

        Clients connecting here receive agent_status events whenever an agent
        is paused or resumed via the REST API.
        """
        from aiohttp import web as _web
        ws = _web.WebSocketResponse()
        await ws.prepare(request)

        _ws_clients.add(ws)
        try:
            async for msg in ws:
                pass  # We only broadcast; inbound messages are ignored
        finally:
            _ws_clients.discard(ws)

        return ws

    # -------------------------------------------------------------------------
    # AI-81: Agent Detail View - REQ-MONITOR-003
    # -------------------------------------------------------------------------

    async def get_agent_profile(self, request: Request) -> Response:
        """GET /api/agents/{name}/profile - Full agent profile for detail view.

        Returns agent profile with lifetime stats, gamification data,
        contribution counters, strengths/weaknesses, and recent events (last 20).

        Returns:
            200 OK with profile data
            404 Not Found if agent not in panel list
        """
        import uuid as _uuid
        agent_name = request.match_info['name']

        if agent_name not in PANEL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
                'available_agents': PANEL_AGENT_NAMES,
            }, status=404)

        # Get current status from status details
        status_info = _agent_status_details.get(agent_name, {})
        current_status = status_info.get('status', 'idle')
        model = _REST_DEFAULT_MODELS.get(agent_name, 'haiku')

        # Try to load from metrics store
        agent_profile_data: Dict[str, Any] = {}
        try:
            state = self.store.load()
            agent_profile_data = state.get('agents', {}).get(agent_name, {})
        except Exception:
            pass

        # Lifetime stats
        total_inv = agent_profile_data.get('total_invocations', 0)
        successful_inv = agent_profile_data.get('successful_invocations', 0)
        failed_inv = agent_profile_data.get('failed_invocations', 0)
        total_tokens = agent_profile_data.get('total_tokens', 0)
        total_cost = agent_profile_data.get('total_cost_usd', 0.0)
        total_duration = agent_profile_data.get('total_duration_seconds', 0.0)
        success_rate = agent_profile_data.get('success_rate', 0.0)
        avg_duration = agent_profile_data.get('avg_duration_seconds', 0.0)

        # Gamification
        xp = agent_profile_data.get('xp', 0)
        level = agent_profile_data.get('level', 1)
        streak = agent_profile_data.get('current_streak', 0)
        best_streak = agent_profile_data.get('best_streak', 0)
        achievements = agent_profile_data.get('achievements', [])

        # Contribution counters
        commits = agent_profile_data.get('commits_made', 0)
        prs_created = agent_profile_data.get('prs_created', 0)
        prs_merged = agent_profile_data.get('prs_merged', 0)
        issues_closed = agent_profile_data.get('issues_completed', 0)
        files_created = agent_profile_data.get('files_created', 0)
        files_modified = agent_profile_data.get('files_modified', 0)
        tests_written = agent_profile_data.get('tests_written', 0)
        messages_sent = agent_profile_data.get('messages_sent', 0)
        reviews_completed = agent_profile_data.get('reviews_completed', 0)

        strengths = agent_profile_data.get('strengths', [])
        weaknesses = agent_profile_data.get('weaknesses', [])
        last_active = agent_profile_data.get('last_active', None)

        # Recent events from in-memory store
        recent_events = list(_rest_agent_recent_events.get(agent_name, []))

        profile = {
            'name': agent_name,
            'model': model,
            'status': current_status,
            'last_active': last_active,
            'lifetime_stats': {
                'tasks_completed': successful_inv,
                'tasks_failed': failed_inv,
                'total_invocations': total_inv,
                'success_rate': success_rate,
                'total_tokens': total_tokens,
                'total_cost': total_cost,
                'avg_duration': avg_duration,
                'total_duration': total_duration,
            },
            'gamification': {
                'xp': xp,
                'level': level,
                'streak': streak,
                'best_streak': best_streak,
                'achievements': achievements,
            },
            'contribution_counters': {
                'commits': commits,
                'prs_created': prs_created,
                'prs_merged': prs_merged,
                'linear_issues_closed': issues_closed,
                'files_created': files_created,
                'files_modified': files_modified,
                'tests_written': tests_written,
                'messages_sent': messages_sent,
                'reviews_completed': reviews_completed,
            },
            'strengths': strengths,
            'weaknesses': weaknesses,
            'recent_events': recent_events,
        }

        return web.json_response({
            'profile': profile,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })

    async def post_agent_recent_event(self, request: Request) -> Response:
        """POST /api/agents/{name}/events - Add an event to agent's recent history.

        Maintains a rolling window of the last 20 events per agent.

        Request body:
            {
                "type": "task_started|task_completed|error_occurred|...",
                "title": "Event title",
                "status": "success|error|in_progress|...",
                "ticket_key": "AI-123",
                "duration": 12.5
            }

        Returns:
            201 Created with event data
            404 Not Found if agent not in panel list
            400 Bad Request if body is invalid
        """
        import uuid as _uuid
        agent_name = request.match_info['name']

        if agent_name not in PANEL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
                'available_agents': PANEL_AGENT_NAMES,
            }, status=404)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        event_type = body.get('type', 'task_completed')
        title = body.get('title', '')
        status = body.get('status', 'success')
        ticket_key = body.get('ticket_key', '')
        duration = body.get('duration', None)

        if not title:
            return web.json_response({'error': 'title is required'}, status=400)

        event = {
            'id': str(_uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'type': event_type,
            'title': title,
            'status': status,
            'ticket_key': ticket_key,
            'duration': duration,
        }

        if agent_name not in _rest_agent_recent_events:
            _rest_agent_recent_events[agent_name] = []
        _rest_agent_recent_events[agent_name].append(event)
        _rest_agent_recent_events[agent_name] = _rest_agent_recent_events[agent_name][-20:]

        return web.json_response({
            'event': event,
            'agent_name': agent_name,
            'total_events': len(_rest_agent_recent_events[agent_name]),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        }, status=201)

    # -------------------------------------------------------------------------
    # AI-79: Agent Status Panel - REQ-MONITOR-001
    # -------------------------------------------------------------------------

    async def get_all_agents_status(self, request: Request) -> Response:
        """GET /api/agents/status - Get current status of all 13 agents.

        Returns a list of all panel agents with their status (idle/running/paused/error),
        current ticket (if running), and elapsed_time (if running).

        Returns:
            200 OK with list of agent status objects
        """
        timestamp = datetime.utcnow().isoformat() + 'Z'
        agents_status = []

        for agent_name in PANEL_AGENT_NAMES:
            detail = _agent_status_details.get(agent_name, {
                "name": agent_name,
                "status": "idle",
                "current_ticket": None,
                "started_at": None,
            })
            elapsed_time = None
            if detail.get("status") == "running" and detail.get("started_at"):
                try:
                    started = datetime.fromisoformat(detail["started_at"].rstrip('Z'))
                    elapsed_time = round((datetime.utcnow() - started).total_seconds())
                except (ValueError, AttributeError):
                    elapsed_time = None

            agents_status.append({
                "name": agent_name,
                "status": detail.get("status", "idle"),
                "current_ticket": detail.get("current_ticket"),
                "elapsed_time": elapsed_time,
                # AI-80 / REQ-MONITOR-002: active requirement display fields
                "ticket_title": detail.get("ticket_title"),
                "description": detail.get("description"),
                "token_count": detail.get("token_count", 0),
                "estimated_cost": detail.get("estimated_cost", 0.0),
            })

        return web.json_response({
            "agents": agents_status,
            "total": len(agents_status),
            "timestamp": timestamp,
        })

    async def update_agent_status(self, request: Request) -> Response:
        """POST /api/agents/{name}/status - Update agent status.

        Supports status transitions:
            idle -> running, idle -> paused, idle -> error
            running -> idle, running -> paused, running -> error
            paused -> idle, paused -> running, paused -> error
            any -> error

        Request body:
            {
                "status": "idle|running|paused|error",
                "current_ticket": "AI-XX"  (optional, used when running),
                "ticket_title": "Title of the ticket"  (optional, AI-80),
                "description": "Full requirement description"  (optional, AI-80),
                "token_count": 0  (optional, AI-80),
                "estimated_cost": 0.0  (optional, AI-80)
            }

        Returns:
            200 OK with updated agent status
            400 Bad Request for invalid status
            404 Not Found if agent name not in panel agents
        """
        agent_name = request.match_info['name']

        # Validate agent name - must be one of the 13 panel agents
        if agent_name not in PANEL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
                'available_agents': PANEL_AGENT_NAMES,
            }, status=404)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        new_status = body.get('status', '')
        if new_status not in VALID_AGENT_STATUSES:
            return web.json_response({
                'error': f'Invalid status. Must be one of: {list(VALID_AGENT_STATUSES)}',
                'provided': new_status,
            }, status=400)

        current_ticket = body.get('current_ticket', None)
        timestamp = datetime.utcnow().isoformat() + 'Z'

        # AI-80 / REQ-MONITOR-002: new optional fields for active requirement display
        ticket_title = body.get('ticket_title', None)
        description = body.get('description', None)
        token_count = body.get('token_count', 0)
        estimated_cost = body.get('estimated_cost', 0.0)

        # Update in-memory details
        if agent_name not in _agent_status_details:
            _agent_status_details[agent_name] = {
                "name": agent_name,
                "status": "idle",
                "current_ticket": None,
                "started_at": None,
                "ticket_title": None,
                "description": None,
                "token_count": 0,
                "estimated_cost": 0.0,
            }

        previous_status = _agent_status_details[agent_name].get("status", "idle")
        _agent_status_details[agent_name]["status"] = new_status
        _agent_status_details[agent_name]["current_ticket"] = current_ticket if new_status == "running" else None

        # Track start time for elapsed_time calculation
        if new_status == "running":
            _agent_status_details[agent_name]["started_at"] = timestamp
            # Store active requirement display fields
            _agent_status_details[agent_name]["ticket_title"] = ticket_title
            _agent_status_details[agent_name]["description"] = description
            _agent_status_details[agent_name]["token_count"] = token_count
            _agent_status_details[agent_name]["estimated_cost"] = estimated_cost
        elif new_status in ("idle", "error"):
            _agent_status_details[agent_name]["started_at"] = None
            # Clear active requirement display fields when not running
            _agent_status_details[agent_name]["ticket_title"] = None
            _agent_status_details[agent_name]["description"] = None
            _agent_status_details[agent_name]["token_count"] = 0
            _agent_status_details[agent_name]["estimated_cost"] = 0.0

        # Also keep _agent_states in sync (for backward compat with pause/resume endpoints)
        _agent_states[agent_name] = new_status

        # Broadcast via WebSocket
        await self._broadcast_agent_status(agent_name, new_status)

        return web.json_response({
            'status': 'success',
            'agent_name': agent_name,
            'previous_status': previous_status,
            'new_status': new_status,
            'current_ticket': current_ticket if new_status == "running" else None,
            'ticket_title': ticket_title if new_status == "running" else None,
            'description': description if new_status == "running" else None,
            'token_count': token_count if new_status == "running" else 0,
            'estimated_cost': estimated_cost if new_status == "running" else 0.0,
            'timestamp': timestamp,
        })

    async def get_agent_requirement(self, request: Request) -> Response:
        """GET /api/agents/{name}/requirement - Get full requirement details for a running agent.

        AI-80 / REQ-MONITOR-002: Returns ticket key, title, description, token_count,
        estimated_cost, and elapsed_time for a running agent.

        Args:
            name: Agent name (path parameter)

        Returns:
            200 OK with requirement details
            404 Not Found if agent not in panel agents
        """
        agent_name = request.match_info['name']

        if agent_name not in PANEL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
                'available_agents': PANEL_AGENT_NAMES,
            }, status=404)

        detail = _agent_status_details.get(agent_name, {
            "name": agent_name,
            "status": "idle",
            "current_ticket": None,
            "started_at": None,
            "ticket_title": None,
            "description": None,
            "token_count": 0,
            "estimated_cost": 0.0,
        })

        # Calculate elapsed time
        elapsed_time = None
        if detail.get("status") == "running" and detail.get("started_at"):
            try:
                started = datetime.fromisoformat(detail["started_at"].rstrip('Z'))
                elapsed_time = round((datetime.utcnow() - started).total_seconds())
            except (ValueError, AttributeError):
                elapsed_time = None

        return web.json_response({
            "agent_name": agent_name,
            "status": detail.get("status", "idle"),
            "current_ticket": detail.get("current_ticket"),
            "ticket_title": detail.get("ticket_title"),
            "description": detail.get("description"),
            "token_count": detail.get("token_count", 0),
            "estimated_cost": detail.get("estimated_cost", 0.0),
            "elapsed_time": elapsed_time,
            "started_at": detail.get("started_at"),
            "timestamp": datetime.utcnow().isoformat() + 'Z',
        })

    async def update_agent_metrics(self, request: Request) -> Response:
        """POST /api/agents/{name}/metrics - Update token_count and estimated_cost for a running agent.

        AI-80 / REQ-MONITOR-002: Real-time metrics update endpoint. Broadcasts
        agent_metrics_update WebSocket message with updated values.

        Request body:
            {
                "token_count": 1234,
                "estimated_cost": 0.0042
            }

        Returns:
            200 OK with updated metrics
            400 Bad Request for invalid input
            404 Not Found if agent not in panel agents
        """
        agent_name = request.match_info['name']

        if agent_name not in PANEL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
                'available_agents': PANEL_AGENT_NAMES,
            }, status=404)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        token_count = body.get('token_count')
        estimated_cost = body.get('estimated_cost')

        if token_count is None and estimated_cost is None:
            return web.json_response({
                'error': 'At least one of token_count or estimated_cost must be provided'
            }, status=400)

        # Initialize if needed
        if agent_name not in _agent_status_details:
            _agent_status_details[agent_name] = {
                "name": agent_name,
                "status": "idle",
                "current_ticket": None,
                "started_at": None,
                "ticket_title": None,
                "description": None,
                "token_count": 0,
                "estimated_cost": 0.0,
            }

        # Update metrics
        if token_count is not None:
            _agent_status_details[agent_name]["token_count"] = token_count
        if estimated_cost is not None:
            _agent_status_details[agent_name]["estimated_cost"] = estimated_cost

        timestamp = datetime.utcnow().isoformat() + 'Z'
        detail = _agent_status_details[agent_name]

        # Broadcast agent_metrics_update via WebSocket
        await self._broadcast_metrics_update(agent_name, detail)

        return web.json_response({
            'status': 'success',
            'agent_name': agent_name,
            'token_count': detail.get("token_count", 0),
            'estimated_cost': detail.get("estimated_cost", 0.0),
            'timestamp': timestamp,
        })

    async def _broadcast_metrics_update(self, agent_name: str, detail: Dict[str, Any]) -> None:
        """Broadcast an agent_metrics_update event to all connected WebSocket clients.

        AI-80 / REQ-MONITOR-002: Emits real-time token/cost updates.

        Args:
            agent_name: Name of the agent whose metrics changed
            detail: Current agent status detail dict
        """
        if not _ws_clients:
            return

        payload = json.dumps({
            "type": "agent_metrics_update",
            "agent": agent_name,
            "token_count": detail.get("token_count", 0),
            "estimated_cost": detail.get("estimated_cost", 0.0),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

        dead_clients = set()
        for ws in list(_ws_clients):
            try:
                await ws.send_str(payload)
            except Exception:
                dead_clients.add(ws)

        for ws in dead_clients:
            _ws_clients.discard(ws)

    async def _broadcast_agent_status(self, agent_name: str, status: str) -> None:
        """Broadcast an agent_status event to all connected WebSocket clients.

        Args:
            agent_name: Name of the agent whose status changed
            status: New status string (e.g. "paused" or "idle")
        """
        if not _ws_clients:
            return

        payload = json.dumps({
            "type": "agent_status",
            "agent": agent_name,
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

        dead_clients = set()
        for ws in list(_ws_clients):
            try:
                await ws.send_str(payload)
            except Exception:
                dead_clients.add(ws)

        for ws in dead_clients:
            _ws_clients.discard(ws)

    # -------------------------------------------------------------------------
    # AI-82: Orchestrator Pipeline Visualization - REQ-MONITOR-004
    # -------------------------------------------------------------------------

    async def get_pipeline(self, request: Request) -> Response:
        """GET /api/orchestrator/pipeline - Return current pipeline state.

        Returns:
            200 OK with pipeline state including active flag, ticket_key, and 6 steps
        """
        import copy
        return web.json_response(copy.deepcopy(_pipeline_state))

    async def set_pipeline(self, request: Request) -> Response:
        """POST /api/orchestrator/pipeline - Set the full pipeline state.

        Request body:
            {
                "active": true,
                "ticket_key": "AI-82",
                "ticket_title": "Pipeline Steps",
                "steps": [
                    {"id": "ops-start", "label": "...", "status": "completed", "duration": 2.3},
                    ...
                ]
            }

        Returns:
            200 OK with updated pipeline state
            400 Bad Request for invalid input
        """
        global _pipeline_state
        import copy

        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        # Validate required fields
        if 'active' not in body:
            return web.json_response({'error': 'Missing required field: active'}, status=400)

        active = bool(body.get('active', False))
        ticket_key = body.get('ticket_key', None)
        ticket_title = body.get('ticket_title', None)

        # Build steps: accept provided steps or default
        steps_input = body.get('steps', None)
        if steps_input is not None:
            if not isinstance(steps_input, list):
                return web.json_response({'error': 'steps must be an array'}, status=400)
            # Normalise each step
            steps = []
            for s in steps_input:
                step_id = s.get('id', '')
                steps.append({
                    'id': step_id,
                    'label': s.get('label', step_id),
                    'status': s.get('status', 'pending'),
                    'duration': s.get('duration', None),
                })
        else:
            steps = copy.deepcopy(_PIPELINE_DEFAULT_STEPS)

        _pipeline_state = {
            'active': active,
            'ticket_key': ticket_key,
            'ticket_title': ticket_title,
            'steps': steps,
        }

        # Broadcast via WebSocket
        await self._broadcast_pipeline_update()

        return web.json_response(copy.deepcopy(_pipeline_state))

    async def update_pipeline_step(self, request: Request) -> Response:
        """POST /api/orchestrator/pipeline/step - Update a single pipeline step.

        Request body:
            {
                "id": "coding",
                "status": "completed",
                "duration": 12.5
            }

        Returns:
            200 OK with updated pipeline state
            400 Bad Request for invalid step ID or missing fields
        """
        global _pipeline_state
        import copy

        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        step_id = body.get('id')
        if not step_id:
            return web.json_response({'error': 'Missing required field: id'}, status=400)

        new_status = body.get('status')
        if not new_status:
            return web.json_response({'error': 'Missing required field: status'}, status=400)

        # Find and update the step
        found = False
        for step in _pipeline_state.get('steps', []):
            if step['id'] == step_id:
                step['status'] = new_status
                if 'duration' in body:
                    step['duration'] = body['duration']
                found = True
                break

        if not found:
            valid_ids = [s['id'] for s in _pipeline_state.get('steps', [])]
            return web.json_response({
                'error': f'Step ID not found: {step_id!r}',
                'valid_ids': valid_ids,
            }, status=400)

        # Broadcast via WebSocket
        await self._broadcast_pipeline_update()

        return web.json_response(copy.deepcopy(_pipeline_state))

    async def _broadcast_pipeline_update(self) -> None:
        """Broadcast a pipeline_update event to all connected WebSocket clients."""
        if not _ws_clients:
            return

        import copy
        payload = json.dumps({
            'type': 'pipeline_update',
            'pipeline': copy.deepcopy(_pipeline_state),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })

        dead_clients = set()
        for ws in list(_ws_clients):
            try:
                await ws.send_str(payload)
            except Exception:
                dead_clients.add(ws)

        for ws in dead_clients:
            _ws_clients.discard(ws)

    # =========================================================================
    # AI-83: Global Metrics Bar (REQ-METRICS-001)
    # =========================================================================

    def _get_rest_uptime_seconds(self) -> int:
        """Return seconds since REST server started (or 0 if not tracked)."""
        start = _rest_global_metrics.get("_server_start_time")
        if start is None:
            return 0
        try:
            delta = (datetime.utcnow() - start).total_seconds()
            return max(0, int(delta))
        except Exception:
            return 0

    def _build_rest_global_metrics_response(self) -> dict:
        """Build the global metrics response dict from current state.

        Merges the in-memory _rest_global_metrics overrides with the persisted
        DashboardState (total_sessions, total_tokens, total_cost_usd) and
        live agent counts from _agent_status_details.

        Returns:
            dict with all required fields for REQ-METRICS-001
        """
        try:
            state = self.store.load()
            persisted_sessions = state.get("total_sessions", 0)
            persisted_tokens = state.get("total_tokens", 0)
            persisted_cost = state.get("total_cost_usd", 0.0)
            current_session = len(state.get("sessions", []))
        except Exception:
            persisted_sessions = 0
            persisted_tokens = 0
            persisted_cost = 0.0
            current_session = 0

        total_sessions = _rest_global_metrics.get("total_sessions") or persisted_sessions
        total_tokens = _rest_global_metrics.get("total_tokens") or persisted_tokens
        total_cost_usd = _rest_global_metrics.get("total_cost_usd") or persisted_cost

        agents_active = sum(
            1 for info in _agent_status_details.values()
            if info.get("status") == "running"
        )

        return {
            "total_sessions": total_sessions,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost_usd, 6),
            "uptime_seconds": self._get_rest_uptime_seconds(),
            "current_session": _rest_global_metrics.get("current_session") or current_session,
            "agents_active": agents_active,
            "tasks_completed_today": _rest_global_metrics.get("tasks_completed_today", 0),
        }

    async def get_global_metrics(self, request: Request) -> Response:
        """GET /api/metrics/global — return global metrics summary (AI-83 / REQ-METRICS-001).

        Response shape:
            {
                "total_sessions": 42,
                "total_tokens": 250000,
                "total_cost_usd": 12.50,
                "uptime_seconds": 86400,
                "current_session": 8,
                "agents_active": 3,
                "tasks_completed_today": 15
            }

        Returns:
            200 JSON with global metrics.
        """
        return web.json_response(self._build_rest_global_metrics_response())

    async def post_global_metrics(self, request: Request) -> Response:
        """POST /api/metrics/global — increment global metrics (AI-83 / REQ-METRICS-001).

        Request body (all fields optional, each increments the corresponding counter):
            {
                "total_sessions": 1,
                "total_tokens": 500,
                "total_cost_usd": 0.05,
                "tasks_completed_today": 1,
                "current_session": 9,
                "agents_active": 2
            }

        Set ``"set"`` key to true to overwrite rather than increment.

        Returns:
            200 JSON with updated global metrics.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        mode = "set" if body.get("set") else "increment"
        incrementable = ("total_sessions", "total_tokens", "total_cost_usd",
                         "tasks_completed_today", "current_session", "agents_active")

        for field in incrementable:
            if field in body:
                val = body[field]
                if mode == "set":
                    _rest_global_metrics[field] = val
                else:
                    current = _rest_global_metrics.get(field, 0)
                    if isinstance(current, float) or isinstance(val, float):
                        _rest_global_metrics[field] = round(float(current) + float(val), 6)
                    else:
                        _rest_global_metrics[field] = int(current) + int(val)

        metrics = self._build_rest_global_metrics_response()

        # Broadcast via WebSocket to all connected REST API clients
        import json as _json
        payload = _json.dumps({
            "type": "global_metrics_update",
            "data": metrics,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
        dead_clients: set = set()
        for ws in list(_ws_clients):
            try:
                await ws.send_str(payload)
            except Exception:
                dead_clients.add(ws)
        for ws in dead_clients:
            _ws_clients.discard(ws)

        return web.json_response(metrics)

    # -------------------------------------------------------------------------
    # AI-84: Agent Leaderboard - REQ-METRICS-002
    # -------------------------------------------------------------------------

    def _build_rest_leaderboard(self) -> list:
        """Build the agent leaderboard ranked by XP descending (AI-84 / REQ-METRICS-002).

        Merges in-memory XP store overrides with persisted metrics store data.

        Returns:
            List of agent dicts ranked by XP descending with rank numbers assigned.
        """
        from dashboard.xp import calculate_level_from_xp

        # Try to load persisted agent data from metrics store
        persisted_agents: Dict[str, Any] = {}
        try:
            state = self.store.load()
            persisted_agents = state.get('agents', {}) or {}
        except Exception:
            pass

        entries = []
        for name in PANEL_AGENT_NAMES:
            persisted = persisted_agents.get(name, {})
            xp_override = _rest_agent_xp_store.get(name, {})

            # XP: in-memory override takes precedence over persisted
            xp = xp_override.get('xp', persisted.get('xp', 0))
            level = calculate_level_from_xp(xp)

            success_rate = xp_override.get(
                'success_rate', persisted.get('success_rate', 0.0))
            avg_duration_s = xp_override.get(
                'avg_duration_s', persisted.get('avg_duration_seconds', 0.0))
            total_cost_usd = xp_override.get(
                'total_cost_usd', persisted.get('total_cost_usd', 0.0))

            # Status from agent status details or xp override
            status = xp_override.get(
                'status',
                _agent_status_details.get(name, {}).get('status', 'idle'))

            entries.append({
                'name': name,
                'xp': xp,
                'level': level,
                'success_rate': success_rate,
                'avg_duration_s': avg_duration_s,
                'total_cost_usd': round(total_cost_usd, 4),
                'status': status,
            })

        # Sort descending by XP, then ascending by name for stable ties
        entries.sort(key=lambda e: (-e['xp'], e['name']))

        # Assign rank numbers (1-indexed)
        for i, entry in enumerate(entries):
            entry['rank'] = i + 1

        return entries

    async def get_agent_leaderboard(self, request: Request) -> Response:
        """GET /api/agents/leaderboard — return agents ranked by XP (AI-84 / REQ-METRICS-002).

        Response: list of agent objects sorted by XP descending.

        Returns:
            200 JSON list with all 13 agents ranked.
        """
        return web.json_response(self._build_rest_leaderboard())

    async def post_agent_xp(self, request: Request) -> Response:
        """POST /api/agents/{name}/xp — add XP to an agent (AI-84 / REQ-METRICS-002).

        Request body:
            {"xp": 50}               - add 50 XP to the agent's total
            {"xp": 50, "set": true}  - set XP to exactly 50

        Returns:
            200 JSON with updated leaderboard
            400 if body is invalid
            404 if agent name not found
        """
        from dashboard.xp import calculate_level_from_xp

        agent_name = request.match_info['name']
        if agent_name not in PANEL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
                'available_agents': PANEL_AGENT_NAMES,
            }, status=404)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        xp_delta = body.get('xp')
        if xp_delta is None or not isinstance(xp_delta, (int, float)):
            return web.json_response(
                {'error': 'Missing or invalid "xp" field (must be a number)'}, status=400)

        # Initialize agent XP store entry if needed
        if agent_name not in _rest_agent_xp_store:
            persisted_xp = 0
            try:
                state = self.store.load()
                persisted_xp = state.get('agents', {}).get(agent_name, {}).get('xp', 0)
            except Exception:
                pass
            _rest_agent_xp_store[agent_name] = {'xp': persisted_xp}

        if body.get('set'):
            _rest_agent_xp_store[agent_name]['xp'] = int(xp_delta)
        else:
            _rest_agent_xp_store[agent_name]['xp'] = int(
                _rest_agent_xp_store[agent_name].get('xp', 0) + xp_delta)

        new_xp = _rest_agent_xp_store[agent_name]['xp']
        _rest_agent_xp_store[agent_name]['level'] = calculate_level_from_xp(new_xp)

        leaderboard = self._build_rest_leaderboard()

        # Broadcast to REST API WebSocket clients
        import json as _json
        payload = _json.dumps({
            'type': 'leaderboard_update',
            'data': leaderboard,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })
        dead_clients: set = set()
        for ws in list(_ws_clients):
            try:
                await ws.send_str(payload)
            except Exception:
                dead_clients.add(ws)
        for ws in dead_clients:
            _ws_clients.discard(ws)

        return web.json_response({
            'agent': agent_name,
            'xp': new_xp,
            'level': _rest_agent_xp_store[agent_name]['level'],
            'leaderboard': leaderboard,
        })

    # =========================================================================
    # AI-86: Live Activity Feed (REQ-FEED-001)
    # =========================================================================

    async def get_feed(self, request: Request) -> Response:
        """GET /api/feed — Return last 50 events across all agents.

        Returns:
            200 JSON list of feed events, newest first.
        """
        return web.json_response(list(reversed(_rest_feed_events)))

    async def post_feed(self, request: Request) -> Response:
        """POST /api/feed — Add a new event to the activity feed.

        Request body:
            {
                "agent": "coding",          # required
                "description": "...",       # required
                "status": "success",        # optional, default "success"
                "ticket_key": "AI-86",      # optional
                "duration_s": 12.3          # optional
            }

        Returns:
            201 Created with the new event.
            400 Bad Request for invalid input.
        """
        import logging as _logging
        import json as _json
        _logger = _logging.getLogger(__name__)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        agent = (body.get('agent') or '').strip()
        description = (body.get('description') or '').strip()

        if not agent:
            return web.json_response({'error': 'agent is required'}, status=400)
        if not description:
            return web.json_response({'error': 'description is required'}, status=400)

        # Warn but don't block unknown agents
        if agent not in PANEL_AGENT_NAMES:
            _logger.warning(f"POST /api/feed: unknown agent {agent!r}")

        status = body.get('status', 'success')
        valid_statuses = ('success', 'error', 'in_progress')
        if status not in valid_statuses:
            return web.json_response({
                'error': f'Invalid status. Must be one of: {list(valid_statuses)}',
                'provided': status,
            }, status=400)

        ticket_key = body.get('ticket_key', None) or None
        duration_s = body.get('duration_s', None)
        if duration_s is not None:
            try:
                duration_s = float(duration_s)
            except (TypeError, ValueError):
                duration_s = None

        from uuid import uuid4 as _uuid4
        event = {
            'id': str(_uuid4()),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'agent': agent,
            'status': status,
            'ticket_key': ticket_key,
            'duration_s': duration_s,
            'description': description[:120],
        }

        _rest_feed_events.append(event)
        # Cap at _REST_FEED_MAX (drop oldest)
        while len(_rest_feed_events) > _REST_FEED_MAX:
            del _rest_feed_events[0]

        # Broadcast feed_update via WebSocket
        payload = _json.dumps({
            'type': 'feed_update',
            'event': event,
            'timestamp': event['timestamp'],
        })
        dead_clients: set = set()
        for ws in list(_ws_clients):
            try:
                await ws.send_str(payload)
            except Exception:
                dead_clients.add(ws)
        for ws in dead_clients:
            _ws_clients.discard(ws)

        _logger.info(
            f"Feed event added: agent={agent!r}, status={status!r}, "
            f"ticket={ticket_key!r}, total={len(_rest_feed_events)}"
        )

        return web.json_response({'event': event, 'total': len(_rest_feed_events)}, status=201)

    # =========================================================================
    # AI-85: Cost and Token Charts (REQ-METRICS-003)
    # =========================================================================

    async def get_chart_token_usage(self, request: Request) -> Response:
        """GET /api/charts/token-usage — token usage by agent (AI-85 / REQ-METRICS-003).

        Response shape:
            {"agents": [{"name": "coding", "tokens": 50000}, ...], "max": 50000}

        Returns:
            200 JSON with token usage per agent sorted descending by tokens.
        """
        agents = [
            {"name": name, "tokens": _rest_chart_token_usage.get(name, 0)}
            for name in PANEL_AGENT_NAMES
        ]
        agents.sort(key=lambda a: a["tokens"], reverse=True)
        max_tokens = max((a["tokens"] for a in agents), default=0)
        return web.json_response({"agents": agents, "max": max_tokens})

    async def post_chart_token_usage(self, request: Request) -> Response:
        """POST /api/charts/token-usage — update token count for an agent (AI-85 / REQ-METRICS-003).

        Request body:
            {"agent": "coding", "tokens": 5000}              - add tokens
            {"agent": "coding", "tokens": 5000, "set": true} - set absolute value

        Returns:
            200 JSON with updated chart data.
            400 if body is invalid or agent unknown.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        agent = body.get("agent", "").strip()
        if not agent:
            return web.json_response({"error": "agent is required"}, status=400)
        if agent not in PANEL_AGENT_NAMES:
            return web.json_response(
                {"error": "Unknown agent", "agent": agent, "available": PANEL_AGENT_NAMES},
                status=400,
            )

        tokens = body.get("tokens")
        if tokens is None or not isinstance(tokens, (int, float)):
            return web.json_response(
                {"error": 'Missing or invalid "tokens" field (must be a number)'}, status=400
            )

        if body.get("set"):
            _rest_chart_token_usage[agent] = int(tokens)
        else:
            _rest_chart_token_usage[agent] = _rest_chart_token_usage.get(agent, 0) + int(tokens)

        agents = [
            {"name": name, "tokens": _rest_chart_token_usage.get(name, 0)}
            for name in PANEL_AGENT_NAMES
        ]
        agents.sort(key=lambda a: a["tokens"], reverse=True)
        max_tokens = max((a["tokens"] for a in agents), default=0)
        return web.json_response({"agents": agents, "max": max_tokens})

    async def get_chart_cost_trend(self, request: Request) -> Response:
        """GET /api/charts/cost-trend — cost per session (last 10) (AI-85 / REQ-METRICS-003).

        Response shape:
            {"sessions": [{"session": 1, "cost": 2.50}, ...]}

        Returns:
            200 JSON with cost trend data.
        """
        sessions = list(_rest_chart_cost_trend[-_REST_CHART_COST_TREND_MAX:])
        return web.json_response({"sessions": sessions})

    async def get_chart_success_rate(self, request: Request) -> Response:
        """GET /api/charts/success-rate — success rate by agent (AI-85 / REQ-METRICS-003).

        Response shape:
            {"agents": [{"name": "coding", "rate": 0.95, "total": 20}, ...]}

        Returns:
            200 JSON with success rate per agent.
        """
        agents = []
        try:
            state = self.store.load()
            stored_agents = state.get("agents", {})
        except Exception:
            stored_agents = {}

        for name in PANEL_AGENT_NAMES:
            persisted = stored_agents.get(name, {})
            xp_override = _rest_agent_xp_store.get(name, {})
            rate = xp_override.get("success_rate", persisted.get("success_rate", 0.0))
            total = persisted.get("total_invocations", 0)
            agents.append({"name": name, "rate": round(float(rate), 4), "total": int(total)})

        return web.json_response({"agents": agents})

    # =========================================================================
    # AI-77: GitHub Access - PR and Issue Management (REQ-INTEGRATION-003)
    # =========================================================================

    def _get_github_repo(self) -> Optional[str]:
        """Return the configured GitHub repo (owner/repo) from environment."""
        return os.getenv("GITHUB_REPO")

    async def github_query(self, request: Request) -> Response:
        """POST /api/github/query - Execute a natural-language GitHub query.

        Request body:
            {
                "query": "What is the status of PR #125?",
                "context": {}  (optional)
            }

        Returns:
            200 OK with {"response": "...", "data": {...}, "timestamp": "..."}
            400 Bad Request for missing/invalid input
            503 Service Unavailable if GITHUB_REPO not configured
        """
        try:
            data = await request.json()
        except (json.JSONDecodeError, Exception):
            return web.json_response(
                {"error": "Invalid JSON in request body"}, status=400
            )

        query = data.get("query", "").strip()
        if not query:
            return web.json_response(
                {"error": "Missing required field: query"}, status=400
            )

        repo = self._get_github_repo()
        context = data.get("context", {})

        if not repo:
            # Graceful degradation: still return a response with a note
            return web.json_response(
                {
                    "response": (
                        "GitHub repository not configured. "
                        "Set the GITHUB_REPO environment variable (e.g. owner/repo) "
                        "to enable GitHub integration."
                    ),
                    "data": {"query": query, "repo": None, "context": context},
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "configured": False,
                },
                status=200,
            )

        # Route via the chat handler (github agent) if available
        response_text = (
            f"GitHub query received for repo '{repo}': {query}. "
            f"Use the chat interface with 'What are my open PRs?' or similar commands "
            f"to interact with the GitHub agent directly."
        )
        try:
            from dashboard.chat_handler import ChatRouter
            router = ChatRouter()
            result = await router.handle_message(
                message=query,
                provider="claude",
            )
            response_text = result.get("response", response_text)
        except Exception:
            pass  # Fall back to the default message

        return web.json_response(
            {
                "response": response_text,
                "data": {"query": query, "repo": repo, "context": context},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "configured": True,
            }
        )

    async def github_get_prs(self, request: Request) -> Response:
        """GET /api/github/prs - Return recent pull requests from the configured repo.

        Query params:
            state: "open" | "closed" | "all" (default: "open")
            limit: int (default: 10)

        Returns:
            200 OK with {"prs": [...], "repo": "...", "timestamp": "..."}
        """
        repo = self._get_github_repo()
        state = request.rel_url.query.get("state", "open")
        try:
            limit = int(request.rel_url.query.get("limit", "10"))
        except ValueError:
            limit = 10

        if not repo:
            return web.json_response(
                {
                    "prs": [],
                    "repo": None,
                    "state": state,
                    "total": 0,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "configured": False,
                    "message": (
                        "GitHub repository not configured. "
                        "Set GITHUB_REPO environment variable."
                    ),
                }
            )

        # Return stub list — real data would come from GitHub MCP or API
        return web.json_response(
            {
                "prs": [],
                "repo": repo,
                "state": state,
                "total": 0,
                "limit": limit,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "configured": True,
                "message": (
                    f"Use the chat interface to query PRs: "
                    f"'What are the open PRs in {repo}?'"
                ),
            }
        )

    async def github_get_issues(self, request: Request) -> Response:
        """GET /api/github/issues - Return recent issues from the configured repo.

        Query params:
            state: "open" | "closed" | "all" (default: "open")
            limit: int (default: 10)

        Returns:
            200 OK with {"issues": [...], "repo": "...", "timestamp": "..."}
        """
        repo = self._get_github_repo()
        state = request.rel_url.query.get("state", "open")
        try:
            limit = int(request.rel_url.query.get("limit", "10"))
        except ValueError:
            limit = 10

        if not repo:
            return web.json_response(
                {
                    "issues": [],
                    "repo": None,
                    "state": state,
                    "total": 0,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "configured": False,
                    "message": (
                        "GitHub repository not configured. "
                        "Set GITHUB_REPO environment variable."
                    ),
                }
            )

        return web.json_response(
            {
                "issues": [],
                "repo": repo,
                "state": state,
                "total": 0,
                "limit": limit,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "configured": True,
                "message": (
                    f"Use the chat interface to query issues: "
                    f"'What are the open issues in {repo}?'"
                ),
            }
        )

    async def github_get_repo(self, request: Request) -> Response:
        """GET /api/github/repo - Return repository information.

        Returns:
            200 OK with {"name": "...", "description": "...", "open_prs": int, ...}
        """
        repo = self._get_github_repo()

        if not repo:
            return web.json_response(
                {
                    "name": None,
                    "full_name": None,
                    "description": None,
                    "open_prs": 0,
                    "open_issues": 0,
                    "stars": 0,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "configured": False,
                    "message": (
                        "GitHub repository not configured. "
                        "Set GITHUB_REPO environment variable."
                    ),
                }
            )

        # Parse owner/repo
        parts = repo.split("/", 1)
        repo_name = parts[1] if len(parts) == 2 else repo

        return web.json_response(
            {
                "name": repo_name,
                "full_name": repo,
                "description": f"Repository: {repo}",
                "open_prs": 0,
                "open_issues": 0,
                "stars": 0,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "configured": True,
                "message": (
                    f"Use the chat interface to get live repo info: "
                    f"'Show me info about {repo}'"
                ),
            }
        )

    async def serve_dashboard(self, request: Request) -> Response:
        """GET / - Serve dashboard HTML.

        Returns:
            200 OK with HTML content
            404 Not Found if HTML file doesn't exist
        """
        html_path = Path(__file__).parent / 'dashboard.html'
        if html_path.exists():
            return web.Response(
                text=html_path.read_text(),
                content_type='text/html'
            )

        return web.json_response({
            'error': 'Dashboard HTML not found',
            'message': 'dashboard.html not found in dashboard directory'
        }, status=404)

    # ── PM Task Launcher endpoints ──────────────────────────────────────

    async def get_pm_tasks(self, request: Request) -> Response:
        """GET /api/pm/tasks - List available PM task types."""
        return web.json_response({"tasks": PM_TASKS})

    async def run_pm_task(self, request: Request) -> Response:
        """POST /api/pm/run - Start a PM task as a background subprocess."""
        global _pm_process
        if _pm_process is not None and _pm_process.poll() is None:
            return web.json_response(
                {"error": "A PM task is already running"}, status=409
            )
        body = await request.json()
        task = body.get("task", "full-review")
        model = body.get("model", "sonnet")
        custom_prompt = body.get("custom_prompt", "")

        if task not in PM_TASKS:
            return web.json_response({"error": f"Unknown task: {task}"}, status=400)

        cmd = [
            "uv", "run", "python", str(_REPO_ROOT / "scripts" / "product_manager_runner.py"),
            "--task", task, "--model", model,
        ]
        if task == "custom" and custom_prompt:
            cmd += ["--custom-prompt", custom_prompt]

        log_path = _REPO_ROOT / ".pm_task_output.log"
        log_file = open(log_path, "w")
        _pm_process = subprocess.Popen(
            cmd, stdout=log_file, stderr=subprocess.STDOUT, cwd=str(_REPO_ROOT)
        )
        entry = {
            "task": task, "model": model, "pid": _pm_process.pid,
            "started_at": datetime.utcnow().isoformat() + "Z",
            "status": "running",
        }
        _pm_task_log.append(entry)
        return web.json_response({"ok": True, **entry})

    async def get_pm_status(self, request: Request) -> Response:
        """GET /api/pm/status - Get current PM task status and log tail."""
        global _pm_process
        if _pm_process is None:
            return web.json_response({"running": False, "log_tail": ""})

        running = _pm_process.poll() is None
        log_path = _REPO_ROOT / ".pm_task_output.log"
        log_tail = ""
        if log_path.exists():
            lines = log_path.read_text(errors="replace").splitlines()
            log_tail = "\n".join(lines[-50:])

        if not running and _pm_task_log:
            _pm_task_log[-1]["status"] = "completed"

        return web.json_response({
            "running": running,
            "pid": _pm_process.pid,
            "returncode": _pm_process.returncode,
            "log_tail": log_tail,
        })

    async def stop_pm_task(self, request: Request) -> Response:
        """POST /api/pm/stop - Stop the running PM task."""
        global _pm_process
        if _pm_process is None or _pm_process.poll() is not None:
            return web.json_response({"error": "No running PM task"}, status=404)
        _pm_process.send_signal(signal.SIGTERM)
        _pm_process.wait(timeout=10)
        if _pm_task_log:
            _pm_task_log[-1]["status"] = "stopped"
        return web.json_response({"ok": True, "stopped": True})

    async def get_pm_history(self, request: Request) -> Response:
        """GET /api/pm/history - List past PM task runs."""
        return web.json_response({"history": _pm_task_log})

    # -------------------------------------------------------------------------
    # AI-229: Webhook endpoints
    # -------------------------------------------------------------------------

    def _get_webhook_manager(self):
        """Lazy import and return the WebhookManager singleton."""
        try:
            from dashboard.webhooks import get_webhook_manager, VALID_EVENTS
            return get_webhook_manager(), VALID_EVENTS
        except ImportError:
            return None, []

    async def rest_list_webhooks(self, request: Request) -> Response:
        """GET /api/webhooks — list all registered webhooks."""
        manager, valid_events = self._get_webhook_manager()
        if manager is None:
            return web.json_response({"error": "Webhook module not available"}, status=503)
        webhooks = manager.list_webhooks()
        return web.json_response({
            "webhooks": webhooks,
            "count": len(webhooks),
            "valid_events": valid_events,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    async def rest_create_webhook(self, request: Request) -> Response:
        """POST /api/webhooks — register a new webhook."""
        manager, _ = self._get_webhook_manager()
        if manager is None:
            return web.json_response({"error": "Webhook module not available"}, status=503)
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        url = data.get("url", "").strip()
        events = data.get("events", [])
        secret = data.get("secret", "")

        if not url:
            return web.json_response({"error": "url is required"}, status=400)
        if not events:
            return web.json_response({"error": "events list is required"}, status=400)

        try:
            webhook_id = manager.register_webhook(url=url, events=events, secret=secret)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)

        webhook = manager.get_webhook(webhook_id)
        return web.json_response(webhook, status=201)

    async def rest_delete_webhook(self, request: Request) -> Response:
        """DELETE /api/webhooks/{webhook_id} — remove a webhook."""
        manager, _ = self._get_webhook_manager()
        if manager is None:
            return web.json_response({"error": "Webhook module not available"}, status=503)
        webhook_id = request.match_info.get("webhook_id", "")
        deleted = manager.delete_webhook(webhook_id)
        if deleted:
            return web.Response(status=204)
        return web.json_response({"error": f"Webhook {webhook_id} not found"}, status=404)

    async def rest_test_webhook(self, request: Request) -> Response:
        """POST /api/webhooks/{webhook_id}/test — send a test event to a webhook."""
        manager, _ = self._get_webhook_manager()
        if manager is None:
            return web.json_response({"error": "Webhook module not available"}, status=503)
        webhook_id = request.match_info.get("webhook_id", "")
        if manager.get_webhook(webhook_id) is None:
            return web.json_response({"error": f"Webhook {webhook_id} not found"}, status=404)
        try:
            result = await manager.test_webhook(webhook_id)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)
        return web.json_response(result)

    async def rest_webhook_deliveries(self, request: Request) -> Response:
        """GET /api/webhooks/deliveries — get delivery log (last 50)."""
        manager, _ = self._get_webhook_manager()
        if manager is None:
            return web.json_response({"error": "Webhook module not available"}, status=503)
        deliveries = manager.get_delivery_log()
        return web.json_response({
            "deliveries": deliveries,
            "count": len(deliveries),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    async def rest_inbound_run_ticket(self, request: Request) -> Response:
        """POST /api/webhooks/inbound/run-ticket — trigger agent on a ticket."""
        manager, _ = self._get_webhook_manager()
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        ticket_key = data.get("ticket_key", "").strip()
        if not ticket_key:
            return web.json_response({"error": "ticket_key is required"}, status=400)

        agent = data.get("agent", "coding")
        priority = data.get("priority", "normal")

        if manager:
            import asyncio
            asyncio.ensure_future(manager.trigger_event("agent.session.started", {
                "ticket_key": ticket_key,
                "agent": agent,
                "priority": priority,
                "source": "inbound_webhook",
            }))

        return web.json_response({
            "accepted": True,
            "ticket_key": ticket_key,
            "agent": agent,
            "priority": priority,
            "message": f"Agent {agent} queued for ticket {ticket_key}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }, status=202)

    async def rest_inbound_run_spec(self, request: Request) -> Response:
        """POST /api/webhooks/inbound/run-spec — trigger agent on a spec."""
        manager, _ = self._get_webhook_manager()
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        spec = data.get("spec", "").strip()
        if not spec:
            return web.json_response({"error": "spec is required"}, status=400)

        agent = data.get("agent", "coding")
        ticket_key = data.get("ticket_key", "")

        if manager:
            import asyncio
            asyncio.ensure_future(manager.trigger_event("agent.session.started", {
                "spec_length": len(spec),
                "agent": agent,
                "ticket_key": ticket_key,
                "source": "inbound_webhook_spec",
            }))

        return web.json_response({
            "accepted": True,
            "agent": agent,
            "ticket_key": ticket_key,
            "spec_length": len(spec),
            "message": f"Agent {agent} queued to process spec",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }, status=202)

    # ==========================================================================
    # AI-220: Free Tier / Billing endpoints
    # ==========================================================================

    def _get_free_tier_manager(self):
        """Lazily import and return the FreeTierManager singleton."""
        try:
            from dashboard.free_tier import get_free_tier_manager
            return get_free_tier_manager()
        except Exception as exc:
            return None

    def _get_billing_user_id(self, request: Request) -> str:
        """Extract user ID for billing purposes.

        For now (single-user mode, AI-220), returns a fixed 'default' user.
        Multi-user auth is introduced in AI-222.

        Returns:
            User identifier string.
        """
        return "default"

    async def get_billing_usage(self, request: Request) -> Response:
        """GET /api/billing/usage (also /api/usage) - Return current usage stats.

        Returns:
            200 OK with usage dict including hours_used, hours_limit, percent_used,
            plan, period_start, reset_date, show_upgrade_cta
        """
        manager = self._get_free_tier_manager()
        if manager is None:
            return web.json_response(
                {"error": "Billing module not available"}, status=503
            )
        user_id = self._get_billing_user_id(request)
        usage = manager.get_usage(user_id)
        usage["timestamp"] = datetime.utcnow().isoformat() + "Z"
        # Include active sessions
        usage["active_sessions"] = manager.get_active_sessions(user_id)
        return web.json_response(usage)

    async def get_billing_plan(self, request: Request) -> Response:
        """GET /api/billing/plan - Return current plan info.

        Returns:
            200 OK with plan dict including features, pricing, limits
        """
        manager = self._get_free_tier_manager()
        if manager is None:
            return web.json_response(
                {"error": "Billing module not available"}, status=503
            )
        user_id = self._get_billing_user_id(request)
        plan = manager.get_plan(user_id)
        plan["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return web.json_response(plan)

    async def post_billing_upgrade(self, request: Request) -> Response:
        """POST /api/billing/upgrade - Request an upgrade (mock for AI-220).

        Returns:
            200 OK with upgrade tier comparison and redirect URL
        """
        manager = self._get_free_tier_manager()
        if manager is None:
            return web.json_response(
                {"error": "Billing module not available"}, status=503
            )

        # Parse optional target plan from request body
        try:
            body = await request.json()
            target_plan = body.get("plan", "builder")
        except Exception:
            target_plan = "builder"

        upgrade_info = manager.get_upgrade_info()
        upgrade_info["requested_plan"] = target_plan
        upgrade_info["message"] = (
            "Upgrade request received. In production, this would redirect to billing. "
            "Billing integration is available in AI-221."
        )
        upgrade_info["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return web.json_response(upgrade_info)

    async def post_billing_session_start(self, request: Request) -> Response:
        """POST /api/billing/session/start - Record session start for usage tracking.

        Body:
            {session_id: str, model: str (optional)}

        Returns:
            200 OK with session info, or 403 if limits exceeded
        """
        manager = self._get_free_tier_manager()
        if manager is None:
            return web.json_response(
                {"error": "Billing module not available"}, status=503
            )

        try:
            body = await request.json()
        except Exception:
            body = {}

        user_id = self._get_billing_user_id(request)
        session_id = body.get("session_id", "")
        model = body.get("model", None)

        if not session_id:
            return web.json_response(
                {"error": "session_id is required"}, status=400
            )

        # Check limits before starting
        if not manager.check_agent_hour_limit(user_id):
            usage = manager.get_usage(user_id)
            return web.json_response(
                {
                    "error": "agent_hour_limit_exceeded",
                    "message": f"Monthly agent-hour limit of {usage['hours_limit']}h exceeded. "
                               "Please upgrade your plan.",
                    "usage": usage,
                },
                status=403,
            )

        if not manager.check_concurrency_limit(user_id):
            plan = manager.get_plan(user_id)
            active = manager.get_active_sessions(user_id)
            return web.json_response(
                {
                    "error": "concurrency_limit_exceeded",
                    "message": f"Concurrency limit of {plan['max_concurrent_agents']} agent(s) reached. "
                               "Please upgrade your plan or wait for a session to complete.",
                    "active_sessions": active,
                    "plan": plan,
                },
                status=403,
            )

        if model and not manager.check_model_allowed(user_id, model):
            plan = manager.get_plan(user_id)
            return web.json_response(
                {
                    "error": "model_not_allowed",
                    "message": f"Model '{model}' is not available on the {plan['display_name']} plan. "
                               "Please upgrade to access Sonnet/Opus models.",
                    "allowed_models": plan["allowed_models"],
                    "plan": plan,
                },
                status=403,
            )

        result = manager.record_session_start(user_id, session_id, model=model)
        result["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return web.json_response(result)

    async def post_billing_session_end(self, request: Request) -> Response:
        """POST /api/billing/session/end - Record session end for usage tracking.

        Body:
            {session_id: str}

        Returns:
            200 OK with session info and updated usage
        """
        manager = self._get_free_tier_manager()
        if manager is None:
            return web.json_response(
                {"error": "Billing module not available"}, status=503
            )

        try:
            body = await request.json()
        except Exception:
            body = {}

        user_id = self._get_billing_user_id(request)
        session_id = body.get("session_id", "")

        if not session_id:
            return web.json_response(
                {"error": "session_id is required"}, status=400
            )

        result = manager.record_session_end(user_id, session_id)
        result["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return web.json_response(result)

    def run(self):
        """Start the REST API server.

        Runs the aiohttp application and blocks until server is stopped.
        """
        auth_status = "ENABLED" if get_auth_token() else "DISABLED (dev mode)"

        print(f"Starting REST API Server on {self.host}:{self.port}")
        print(f"Authentication: {auth_status}")
        print()
        print("Endpoints available:")
        print(f"  GET  /api/health")
        print(f"  GET  /api/metrics")
        print(f"  GET  /api/agents")
        print(f"  GET  /api/agents/{{name}}")
        print(f"  GET  /api/agents/{{name}}/events")
        print(f"  GET  /api/sessions")
        print(f"  GET  /api/providers")
        print(f"  POST /api/chat")
        print(f"  POST /api/agents/{{name}}/pause")
        print(f"  POST /api/agents/{{name}}/resume")
        print(f"  PUT  /api/requirements/{{ticket_key}}")
        print(f"  GET  /api/requirements/{{ticket_key}}")
        print(f"  GET  /api/decisions")
        print(f"  GET  /")
        print()
        print("Press Ctrl+C to stop the server")

        try:
            web.run_app(
                self.app,
                host=self.host,
                port=self.port,
                print=None  # Disable aiohttp's default logging
            )
        except KeyboardInterrupt:
            print("\nServer stopped by user")


def main():
    """CLI entry point for REST API server."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Agent Dashboard REST API Server',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8420,
        help='HTTP server port (default: 8420)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='HTTP server host (default: 0.0.0.0)'
    )

    parser.add_argument(
        '--metrics-dir',
        type=Path,
        default=None,
        help='Directory containing .agent_metrics.json (default: current directory)'
    )

    parser.add_argument(
        '--project-name',
        type=str,
        default='agent-dashboard',
        help='Project name (default: agent-dashboard)'
    )

    args = parser.parse_args()

    # Create and run server
    server = RESTAPIServer(
        project_name=args.project_name,
        metrics_dir=args.metrics_dir,
        port=args.port,
        host=args.host
    )

    server.run()


if __name__ == '__main__':
    main()
