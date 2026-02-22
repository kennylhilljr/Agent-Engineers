"""Dashboard Server - HTTP API for Agent Status Dashboard.

This module provides an aiohttp-based HTTP server that exposes metrics data
through REST endpoints. The server enables web dashboards and other clients
to query agent performance metrics, session summaries, and individual agent details.

Endpoints:
    GET /api/metrics - Returns complete DashboardState with all metrics
    GET /api/agents/<name> - Returns specific agent profile with detailed stats
    GET /health - Health check endpoint
    WS  /ws - WebSocket endpoint for real-time metrics streaming

CORS Configuration:
    - Configurable via CORS_ALLOWED_ORIGINS environment variable
    - Defaults to localhost origins for development security
    - Supports GET, POST, OPTIONS methods
    - Allows Content-Type, Authorization headers
    - Set CORS_ALLOWED_ORIGINS='*' for development (with security warning)
    - For production, set specific domains (e.g., 'https://dashboard.example.com')

A2UI Component Integration:
    This server provides data that can be visualized using A2UI components:
    - TaskCard: Display individual agent activities as task cards
    - ProgressRing: Show overall completion metrics (success rate, invocations)
    - ActivityItem: Timeline view of agent events
    - ErrorCard: Display agent errors with severity and stack traces

    Components available at:
    /Users/bkh223/Documents/GitHub/agent-engineers/reusable/a2ui-components/

    Example usage in frontend:
        <TaskCard data={{
            title: agent.agent_name,
            status: agent.success_rate > 0.8 ? 'completed' : 'in_progress',
            category: 'backend',
            progress: agent.success_rate * 100
        }} />

        <ProgressRing data={{
            percentage: agent.success_rate * 100,
            tasksCompleted: agent.successful_invocations,
            filesModified: agent.files_modified,
            testsCompleted: agent.tests_written
        }} />

Usage:
    # Start server on default port 8080
    python dashboard_server.py

    # Start server on custom port
    python dashboard_server.py --port 8000

    # Query metrics
    curl http://localhost:8080/api/metrics

    # Query specific agent
    curl http://localhost:8080/api/agents/coding_agent
"""

import argparse
import asyncio
import csv
import io
import json
import logging
import os
import re
import signal
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Set
from uuid import uuid4

import aiohttp
from aiohttp import web, WSMsgType
from aiohttp.web import Request, Response, WebSocketResponse, middleware
from aiohttp_cors import ResourceOptions, setup as cors_setup

from dashboard.metrics_store import MetricsStore
from dashboard.intent_parser import parse_intent
from dashboard.chat_handler import ChatRouter, get_chat_history, clear_chat_history
from dashboard.chat_bridge import ChatBridge, IntentParser, AgentRouter
from dashboard.auth import auth_middleware
from dashboard.config import get_config
from dashboard.compat import check_python_version
from dashboard.latency_benchmark import LatencyTracker, StreamingLatencyTracker
from dashboard.structured_logging import RequestLogger, ProviderRoutingLogger, ErrorLogger
from dashboard.rate_limiter import RateLimiter, get_identifier, get_rate_limiter, reset_rate_limiter
from dashboard.usage_meter import UsageMeter, get_usage_meter, reset_usage_meter
from dashboard.webhooks import get_webhook_manager, VALID_EVENTS

# AI-225: Multi-Project Support
try:
    from projects.project_manager import Project, ProjectManager, TierLimitError
    _PROJECTS_AVAILABLE = True
except ImportError:
    _PROJECTS_AVAILABLE = False

# AI-227: Telemetry & Usage Analytics
try:
    from telemetry.event_collector import (
        get_collector as get_telemetry_collector,
        is_telemetry_disabled,
        write_opt_out_flag,
    )
    _TELEMETRY_AVAILABLE = True
except ImportError:
    _TELEMETRY_AVAILABLE = False
    logger.warning("telemetry module not found — analytics disabled")

# AI-245: Team Management - Roles & Permissions
try:
    from teams.routes import register_team_routes
    _TEAMS_AVAILABLE = True
except ImportError:
    _TEAMS_AVAILABLE = False
    logger.warning("teams module not found — team management disabled")

# AI-247: GA Launch - Full Pricing Tier Activation & Enforcement
try:
    from billing.routes import register_billing_routes
    _BILLING_ROUTES_AVAILABLE = True
except ImportError:
    _BILLING_ROUTES_AVAILABLE = False
    logger.warning("billing routes not found — pricing endpoints disabled")

# AI-246: Audit Log for Compliance
try:
    from audit.routes import register_audit_routes
    _AUDIT_AVAILABLE = True
except ImportError:
    _AUDIT_AVAILABLE = False
    logger.warning("audit module not found — audit log disabled")


def _collect_event(event_type: str, properties: Optional[dict] = None) -> None:
    """Fire-and-forget telemetry event collection.

    Safely wraps get_telemetry_collector() so any failure is silenced.
    """
    if not _TELEMETRY_AVAILABLE:
        return
    try:
        collector = get_telemetry_collector()
        collector.collect(event_type, properties or {})
    except Exception:  # noqa: BLE001
        pass

# In-memory store for requirements (ticket_key -> requirement text)
_requirements_store: dict = {}

# AI-79: Agent Status Panel (REQ-MONITOR-001) - in-memory status store for DashboardServer
_dashboard_agent_status: dict = {}

# AI-81: Agent Detail View (REQ-MONITOR-003) - per-agent recent events store
# {agent_name: [list of last 20 event dicts]}
_agent_recent_events: dict = {}

# AI-83: Global Metrics Bar (REQ-METRICS-001) - in-memory global metrics store
_global_metrics: dict = {
    "total_sessions": 0,
    "total_tokens": 0,
    "total_cost_usd": 0.0,
    "uptime_seconds": 0,
    "current_session": 0,
    "agents_active": 0,
    "tasks_completed_today": 0,
    "_server_start_time": None,  # set at server startup
}

# AI-84: Agent Leaderboard (REQ-METRICS-002) - in-memory per-agent XP/stats override store
# {agent_name: {"xp": int, "level": int, "success_rate": float, "avg_duration_s": float, "total_cost_usd": float, "status": str}}
_agent_xp_store: dict = {}

# AI-86: Live Activity Feed (REQ-FEED-001) - in-memory event feed store (newest last, capped at 50)
# Each entry: {"id": str, "timestamp": str, "agent": str, "status": str, "ticket_key": str, "duration_s": float, "description": str}
_feed_events: list = []
_FEED_MAX = 50

# AI-81: Fallback DEFAULT_MODELS dict (avoids importing claude_agent_sdk)
_DEFAULT_MODELS = {
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
}

# The 16 canonical panel agents (excludes orchestrator)
_PANEL_AGENT_NAMES = [
    "linear", "coding", "github", "slack", "pr_reviewer",
    "ops", "coding_fast", "pr_reviewer_fast", "chatgpt",
    "gemini", "groq", "kimi", "windsurf",
    "openrouter_dev", "product_manager", "designer",
]

# Valid statuses for the status panel
_VALID_PANEL_STATUSES = ("idle", "running", "paused", "error")

# Max size of per-instance reasoning history circular buffer (AI-160)
_REASONING_HISTORY_MAX = 100

# Decision log constants (AI-161)
DECISION_TYPES = ['agent_selection', 'complexity', 'verification', 'pr_routing', 'error_recovery', 'other']
_DECISION_LOG_MAX = 500  # larger than reasoning since decisions are compact

# File changes constants (AI-164)
FILE_CHANGES_MAX = 100  # circular buffer limit

# Test results constants (AI-165)
TEST_RESULTS_MAX = 200  # circular buffer limit

# Valid test result statuses (AI-165)
TEST_RUN_STATUSES = ('passed', 'failed', 'error')
TEST_ITEM_STATUSES = ('passed', 'failed', 'error', 'skipped')

# Valid file change statuses (AI-164)
FILE_CHANGE_STATUSES = ('created', 'modified', 'deleted')

# Language detection map (AI-163)
LANGUAGE_MAP = {
    '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
    '.html': 'html', '.css': 'css', '.json': 'json',
    '.md': 'markdown', '.sh': 'bash', '.yaml': 'yaml', '.yml': 'yaml',
    '.go': 'go', '.rs': 'rust', '.java': 'java', '.tsx': 'typescript',
    '.rb': 'ruby', '.php': 'php', '.cpp': 'cpp', '.c': 'c',
    '.h': 'c', '.hpp': 'cpp', '.cs': 'csharp', '.kt': 'kotlin',
    '.swift': 'swift', '.sql': 'sql', '.xml': 'xml', '.toml': 'toml',
}


# AI-85: Cost and Token Charts (REQ-METRICS-003) - in-memory chart data stores
_chart_token_usage: dict = {
    name: 0 for name in [
        "linear", "coding", "github", "slack", "pr_reviewer",
        "ops", "coding_fast", "pr_reviewer_fast", "chatgpt",
        "gemini", "groq", "kimi", "windsurf",
    ]
}
_chart_cost_trend: list = []  # list of {"session": int, "cost": float}
_CHART_COST_TREND_MAX = 10


def detect_language(file_path: str) -> str:
    """Detect programming language from file extension.

    Args:
        file_path: Path to the file (e.g., 'src/app.py')

    Returns:
        Language identifier string (e.g., 'python'), defaults to 'text'
    """
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_MAP.get(ext, 'text')
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Structured loggers (AI-186 / REQ-OBS-001)
_request_logger = RequestLogger()
_error_logger = ErrorLogger()

# Get CORS allowed origins from environment via DashboardConfig
def get_cors_origins() -> str:
    """Get CORS allowed origins from environment variable.

    Uses DASHBOARD_CORS_ORIGINS (via DashboardConfig). Defaults to '*'.

    Returns:
        Comma-separated list of allowed origins or '*'.
    """
    return get_config().cors_origins


# CORS middleware with environment-based configuration
@middleware
async def cors_middleware(request: Request, handler):
    """Add CORS headers to all responses.

    CORS origins are configured via DASHBOARD_CORS_ORIGINS environment variable.
    Defaults to '*' (allow all origins).
    """
    response = await handler(request)

    allowed_origins = get_cors_origins()

    # Handle multiple origins or wildcard
    if allowed_origins == '*':
        response.headers['Access-Control-Allow-Origin'] = '*'
    else:
        # Check if request origin is in allowed list
        origin = request.headers.get('Origin', '')
        allowed_list = [o.strip() for o in allowed_origins.split(',')]

        if origin in allowed_list:
            response.headers['Access-Control-Allow-Origin'] = origin
        elif allowed_list:
            # Default to first allowed origin if no match
            response.headers['Access-Control-Allow-Origin'] = allowed_list[0]

    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


# Error handling middleware
@middleware
async def error_middleware(request: Request, handler):
    """Catch and format errors as JSON responses."""
    try:
        response = await handler(request)
        return response
    except web.HTTPException as ex:
        # Let HTTP exceptions pass through
        raise
    except Exception as ex:
        logger.exception(f"Error handling request {request.method} {request.path}")
        _error_logger.log_error(ex, context={"method": request.method, "path": request.path})
        return web.json_response(
            {
                'error': type(ex).__name__,
                'message': str(ex),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            },
            status=500
        )


async def update_linear_issue(issue_key: str, description: str) -> bool:
    """Update a Linear issue description via the Linear GraphQL API.

    Args:
        issue_key: Linear issue key (e.g. 'AI-157')
        description: New description text

    Returns:
        True if updated successfully, False otherwise

    Raises:
        Exception: If the API call fails
    """
    api_key = os.environ.get('LINEAR_API_KEY', '')
    if not api_key:
        return False

    # Search for issue by identifier (e.g., "AI-157")
    search_query = """
    query SearchIssue($term: String!) {
        issueSearch(term: $term, first: 1) {
            nodes {
                id
                identifier
            }
        }
    }
    """

    update_query = """
    mutation UpdateIssue($id: String!, $description: String!) {
        issueUpdate(id: $id, input: { description: $description }) {
            success
        }
    }
    """

    async with aiohttp.ClientSession() as session:
        headers = {
            'Authorization': f'Bearer {api_key}',  # FIXED: Bearer prefix
            'Content-Type': 'application/json'
        }
        # Search for issue by identifier
        async with session.post(
            'https://api.linear.app/graphql',
            json={'query': search_query, 'variables': {'term': issue_key}},
            headers=headers
        ) as resp:
            data = await resp.json()
            nodes = data.get('data', {}).get('issueSearch', {}).get('nodes', [])
            if not nodes:
                logger.warning(f"Linear issue not found for key: {issue_key}")
                return False
            issue_id = nodes[0]['id']

        # Update the issue description
        async with session.post(
            'https://api.linear.app/graphql',
            json={'query': update_query, 'variables': {'id': issue_id, 'description': description}},
            headers=headers
        ) as resp:
            result = await resp.json()
            return result.get('data', {}).get('issueUpdate', {}).get('success', False)


class DashboardServer:
    """HTTP server for Agent Status Dashboard metrics API.

    Provides REST endpoints for querying metrics data with CORS support.
    Uses MetricsStore for data persistence.
    """

    # Maximum number of agent_event messages kept in the backlog for reconnecting clients
    _AGENT_EVENT_BACKLOG_MAX = 20

    def __init__(
        self,
        project_name: str = "agent-status-dashboard",
        metrics_dir: Optional[Path] = None,
        port: int = 8080,
        host: str = "127.0.0.1",
        collector=None,
    ):
        """Initialize DashboardServer.

        Args:
            project_name: Project name for metrics store
            metrics_dir: Directory containing .agent_metrics.json
            port: HTTP server port
            host: HTTP server host (default: 127.0.0.1 for localhost-only access)
            collector: Optional AgentMetricsCollector instance. When provided the
                server registers itself as a listener so that every event recorded by
                ``collector._record_event()`` is immediately broadcast to all
                connected WebSocket clients (AI-171).

        Security Notes:
            - Default host is 127.0.0.1 (localhost only) for security
            - Use host="0.0.0.0" to bind to all network interfaces (WARNING: exposes server to network)
            - For production, use a reverse proxy (nginx/caddy) with proper TLS/SSL
        """
        self.project_name = project_name
        self.metrics_dir = metrics_dir or Path.cwd()
        self.port = port
        self.host = host

        # Security warning for 0.0.0.0 binding
        if host == "0.0.0.0":
            logger.warning(
                "SECURITY WARNING: Server is binding to 0.0.0.0 (all network interfaces). "
                "This exposes the server to your network. "
                "For production deployment, use a reverse proxy with TLS/SSL. "
                "For local development, consider using 127.0.0.1 instead."
            )

        # Initialize metrics store
        self.store = MetricsStore(
            project_name=project_name,
            metrics_dir=self.metrics_dir
        )

        # WebSocket connections tracking
        self.websockets: Set[WebSocketResponse] = set()
        self.broadcast_task: Optional[asyncio.Task] = None
        # Use config for broadcast_interval (env var DASHBOARD_BROADCAST_INTERVAL, default 5s)
        self.broadcast_interval = get_config().broadcast_interval

        # Circular buffer for reasoning/thinking history (AI-160)
        self._reasoning_history: list = []

        # AI-94/AI-95: Structured reasoning blocks store (last 20)
        self._reasoning_blocks: list = []

        # Circular buffer for decision log (AI-161)
        self._decision_log: list = []

        # In-memory code streams store (AI-163): {stream_id: {file_path, language, agent, chunks, started_at, completed}}
        self._code_streams: dict = {}

        # In-memory file changes store (AI-164): list of file change summaries, newest last
        self._file_changes: list = []

        # In-memory test results store (AI-165): list of test run records, newest last
        self._test_results: list = []

        # Circular backlog of agent_event WS messages for reconnecting clients (AI-171)
        # Each entry is the fully-formatted WebSocket message dict.
        self._agent_event_backlog: list = []

        # Chat-to-Agent Bridge (AI-173 / REQ-TECH-008)
        self._chat_bridge = ChatBridge(
            intent_parser=IntentParser(),
            agent_router=AgentRouter(),
        )

        # WebSocket latency tracker (AI-180 / REQ-PERF-001)
        self.latency_tracker = LatencyTracker()

        # Streaming latency tracker (AI-182 / REQ-PERF-003)
        self.streaming_latency_tracker = StreamingLatencyTracker()

        # AI-82: Orchestrator Pipeline Visualization state (REQ-MONITOR-004)
        _default_pipeline_steps = [
            {"id": "ops-start",   "label": "ops: Starting",       "status": "pending", "duration": None},
            {"id": "coding",      "label": "coding: Implement",   "status": "pending", "duration": None},
            {"id": "github",      "label": "github: Commit & PR", "status": "pending", "duration": None},
            {"id": "ops-review",  "label": "ops: PR Ready",       "status": "pending", "duration": None},
            {"id": "pr_reviewer", "label": "pr_reviewer: Review", "status": "pending", "duration": None},
            {"id": "ops-done",    "label": "ops: Done",           "status": "pending", "duration": None},
        ]
        self._pipeline_state: dict = {
            "active": False,
            "ticket_key": None,
            "ticket_title": None,
            "steps": _default_pipeline_steps,
        }

        # AI-83: Record server start time for uptime calculation (REQ-METRICS-001)
        if _global_metrics.get("_server_start_time") is None:
            _global_metrics["_server_start_time"] = datetime.utcnow()

        # Structured loggers (AI-186 / REQ-OBS-001)
        self._ws_logger = RequestLogger()
        self._provider_routing_logger = ProviderRoutingLogger()
        self._error_logger = ErrorLogger()

        # Register as a listener on the supplied collector (AI-171)
        if collector is not None:
            collector.register_event_callback(self._on_new_event)

        # AI-224: Rate limiter and usage meter singletons
        self._rate_limiter = get_rate_limiter()
        self._usage_meter = get_usage_meter()

        # AI-225: Multi-project manager
        if _PROJECTS_AVAILABLE:
            self._project_manager = ProjectManager(base_dir=self.metrics_dir)
        else:
            self._project_manager = None

        # Create app with middlewares (auth before rate-limit before cors so rejections get CORS headers)
        self.app = web.Application(middlewares=[auth_middleware, self._rate_limiter.middleware, error_middleware, cors_middleware])

        # Register routes
        self._setup_routes()

        # AI-79: Initialize agent status panel store for all 13 panel agents
        for _name in _PANEL_AGENT_NAMES:
            if _name not in _dashboard_agent_status:
                _dashboard_agent_status[_name] = {
                    "name": _name,
                    "status": "idle",
                    "current_ticket": None,
                    "started_at": None,
                    # AI-80 / REQ-MONITOR-002: active requirement display fields
                    "ticket_title": None,
                    "description": None,
                    "token_count": 0,
                    "estimated_cost": 0.0,
                }

        # Setup WebSocket broadcasting
        self.app.on_startup.append(self._start_broadcast)
        self.app.on_cleanup.append(self._cleanup_websockets)

        # AI-227: Start telemetry collector and emit session_started
        if _TELEMETRY_AVAILABLE:
            self.app.on_startup.append(self._start_telemetry)
            self.app.on_cleanup.append(self._stop_telemetry)

        logger.info(f"Dashboard server initialized for project: {project_name}")
        logger.info(f"Metrics directory: {self.metrics_dir}")

    def _setup_routes(self):
        """Register HTTP routes and WebSocket endpoint.

        Route Registration Order (AI-278 Security Hardening):
            1. Specific routes registered first (health, api endpoints)
            2. Static file serving for /dashboard/* registered AFTER specific routes
            3. Static route is registered with security hardening:
               - show_index=False to prevent directory listing
               - follow_symlinks=False to prevent symlink traversal attacks
        """
        # AI-278: Static file serving for /dashboard/* paths (security hardened)
        self.app.router.add_static('/dashboard', Path(__file__).parent,
                                    show_index=False, follow_symlinks=False)

        self.app.router.add_get('/', self.serve_dashboard)
        self.app.router.add_get('/architecture', self.serve_architecture)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/api/metrics', self.get_metrics)
        # AI-79: Agent Status Panel endpoint - must be registered BEFORE /{agent_name}
        self.app.router.add_get('/api/agents/status', self.get_all_agents_status)
        # AI-84: Agent Leaderboard (REQ-METRICS-002) - must be BEFORE /{agent_name}
        self.app.router.add_get('/api/agents/leaderboard', self.get_agent_leaderboard)
        self.app.router.add_post('/api/agents/{agent_name}/status', self.update_agent_status_handler)
        # AI-81: Agent Detail View (REQ-MONITOR-003) - profile and events
        self.app.router.add_get('/api/agents/{agent_name}/profile', self.get_agent_profile)
        self.app.router.add_post('/api/agents/{agent_name}/events', self.post_agent_recent_event)
        self.app.router.add_get('/api/agents/{agent_name}', self.get_agent)
        self.app.router.add_get('/ws', self.websocket_handler)
        # AI-80 / REQ-MONITOR-002: Active Requirement Display endpoints
        self.app.router.add_get('/api/agents/{agent_name}/requirement', self.get_agent_requirement)
        self.app.router.add_post('/api/agents/{agent_name}/metrics', self.update_agent_metrics)

        # Requirement sync endpoints
        self.app.router.add_get('/api/requirements/{ticket_key}', self.get_requirement)
        self.app.router.add_put('/api/requirements/{ticket_key}', self.put_requirement)

        # Chat-to-Agent Bridge endpoints (REQ-TECH-008)
        self.app.router.add_post('/api/chat', self.post_chat)
        self.app.router.add_post('/api/chat/route', self.post_chat_route)
        self.app.router.add_get('/api/chat/history', self.get_chat_history)


        # Reasoning broadcast endpoint (AI-158)
        self.app.router.add_post('/api/reasoning', self.broadcast_reasoning)

        # Agent thinking broadcast endpoint (AI-159)
        self.app.router.add_post('/api/agent-thinking', self.broadcast_agent_thinking)

        # Reasoning blocks history endpoint (AI-160)
        self.app.router.add_get('/api/reasoning/blocks', self.get_reasoning_blocks)

        # AI-94/AI-95: Structured reasoning block endpoints
        self.app.router.add_post('/api/reasoning/block', self.post_reasoning_block)
        self.app.router.add_post('/api/reasoning/clear', self.clear_reasoning_blocks)

        # Decision log endpoints (AI-161)
        self.app.router.add_post('/api/decisions', self.post_decision)
        self.app.router.add_get('/api/decisions', self.get_decisions)
        self.app.router.add_get('/api/decisions/export', self.export_decisions)
        # Decision audit trail endpoints (AI-162)
        self.app.router.add_get('/api/decisions/summary', self.get_decisions_summary)
        self.app.router.add_get('/api/decisions/{decision_id}', self.get_decision_by_id)

        # Code streaming endpoints (AI-163)
        self.app.router.add_post('/api/code-stream', self.post_code_stream)
        self.app.router.add_get('/api/code-streams', self.get_code_streams)
        self.app.router.add_get('/api/code-streams/{stream_id}', self.get_code_stream_by_id)

        # File change summary endpoints (AI-164)
        self.app.router.add_post('/api/file-changes', self.post_file_changes)
        self.app.router.add_get('/api/file-changes', self.get_file_changes)
        self.app.router.add_get('/api/file-changes/{session_id}', self.get_file_changes_by_session)

        # Test results endpoints (AI-165)
        self.app.router.add_post('/api/test-results', self.post_test_results)
        self.app.router.add_get('/api/test-results', self.get_test_results)
        self.app.router.add_get('/api/test-results/{ticket}', self.get_test_results_by_ticket)

        # WebSocket protocol endpoints (AI-168)
        self.app.router.add_post('/api/agent-status', self.post_agent_status)
        self.app.router.add_post('/api/agent-event', self.post_agent_event)
        self.app.router.add_post('/api/chat-stream', self.post_chat_stream)
        self.app.router.add_post('/api/control-ack', self.post_control_ack)

        # AI-82: Orchestrator Pipeline Visualization (REQ-MONITOR-004)
        self.app.router.add_get('/api/orchestrator/pipeline', self.get_pipeline)
        self.app.router.add_post('/api/orchestrator/pipeline', self.set_pipeline)
        self.app.router.add_post('/api/orchestrator/pipeline/step', self.update_pipeline_step)
        self.app.router.add_route('OPTIONS', '/api/orchestrator/pipeline', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/orchestrator/pipeline/step', self.handle_options)

        # AI-86: Live Activity Feed (REQ-FEED-001)
        self.app.router.add_get('/api/feed', self.get_feed)
        self.app.router.add_post('/api/feed', self.post_feed)
        self.app.router.add_route('OPTIONS', '/api/feed', self.handle_options)

        # Latency statistics endpoint (AI-180 / REQ-PERF-001)
        self.app.router.add_get('/api/latency', self.get_latency_stats)

        # Streaming latency statistics endpoint (AI-182 / REQ-PERF-003)
        self.app.router.add_get('/api/streaming-latency', self.get_streaming_latency_stats)

        # Metrics health endpoint (AI-185 / REQ-REL-003)
        self.app.router.add_get('/api/health/metrics', self.get_metrics_health)

        # AI-83: Global Metrics Bar (REQ-METRICS-001)
        self.app.router.add_get('/api/metrics/global', self.get_global_metrics)
        self.app.router.add_post('/api/metrics/global', self.post_global_metrics)
        self.app.router.add_route('OPTIONS', '/api/metrics/global', self.handle_options)

        # AI-84: Agent Leaderboard POST XP (REQ-METRICS-002)
        self.app.router.add_post('/api/agents/{agent_name}/xp', self.post_agent_xp)
        self.app.router.add_route('OPTIONS', '/api/agents/leaderboard', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/{agent_name}/xp', self.handle_options)

        # OPTIONS for CORS preflight
        self.app.router.add_route('OPTIONS', '/api/metrics', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/status', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/{agent_name}', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/{agent_name}/profile', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/{agent_name}/events', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/requirements/{ticket_key}', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/chat', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/chat/route', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/chat/history', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/reasoning', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agent-thinking', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/reasoning/blocks', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/reasoning/block', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/reasoning/clear', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/decisions', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/decisions/export', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/decisions/summary', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/decisions/{decision_id}', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/code-stream', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/code-streams', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/code-streams/{stream_id}', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/file-changes', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/file-changes/{session_id}', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/test-results', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/test-results/{ticket}', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agent-status', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agent-event', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/chat-stream', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/control-ack', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/health/metrics', self.handle_options)

        # AI-85: Cost and Token Charts (REQ-METRICS-003)
        self.app.router.add_get('/api/charts/token-usage', self.get_chart_token_usage)
        self.app.router.add_post('/api/charts/token-usage', self.post_chart_token_usage)
        self.app.router.add_get('/api/charts/cost-trend', self.get_chart_cost_trend)
        self.app.router.add_get('/api/charts/success-rate', self.get_chart_success_rate)
        self.app.router.add_route('OPTIONS', '/api/charts/token-usage', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/charts/cost-trend', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/charts/success-rate', self.handle_options)

        # AI-224: Usage metering endpoints
        self.app.router.add_get('/api/usage', self.get_usage)
        self.app.router.add_post('/api/usage/record', self.post_usage_record)
        self.app.router.add_post('/api/usage/reset', self.post_usage_reset)
        self.app.router.add_route('OPTIONS', '/api/usage', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/usage/record', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/usage/reset', self.handle_options)

        # AI-226: Onboarding endpoints
        self.app.router.add_get('/api/onboarding/status', self.get_onboarding_status)
        self.app.router.add_get('/api/onboarding/complete', self.get_onboarding_complete)
        self.app.router.add_route('OPTIONS', '/api/onboarding/status', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/onboarding/complete', self.handle_options)

        # AI-227: Telemetry analytics endpoints
        self.app.router.add_get('/api/admin/analytics', self.get_analytics)
        self.app.router.add_post('/api/telemetry/optout', self.post_telemetry_optout)
        self.app.router.add_route('OPTIONS', '/api/admin/analytics', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/telemetry/optout', self.handle_options)

        # AI-225: Multi-project endpoints
        self.app.router.add_get('/api/projects', self.get_projects)
        self.app.router.add_post('/api/projects', self.post_project)
        self.app.router.add_delete('/api/projects/{project_id}', self.delete_project)
        self.app.router.add_post('/api/projects/{project_id}/activate', self.activate_project)
        self.app.router.add_get('/api/projects/active', self.get_active_project)
        self.app.router.add_route('OPTIONS', '/api/projects', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/projects/{project_id}', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/projects/{project_id}/activate', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/projects/active', self.handle_options)

        # AI-229: Webhook Support for CI/CD Pipeline Integration
        self.app.router.add_get('/api/webhooks', self.list_webhooks)
        self.app.router.add_post('/api/webhooks', self.create_webhook)
        self.app.router.add_get('/api/webhooks/deliveries', self.get_webhook_deliveries)
        self.app.router.add_delete('/api/webhooks/{webhook_id}', self.delete_webhook)
        self.app.router.add_post('/api/webhooks/{webhook_id}/test', self.test_webhook)
        self.app.router.add_post('/api/webhooks/inbound/run-ticket', self.inbound_run_ticket)
        self.app.router.add_post('/api/webhooks/inbound/run-spec', self.inbound_run_spec)
        self.app.router.add_route('OPTIONS', '/api/webhooks', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/webhooks/deliveries', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/webhooks/{webhook_id}', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/webhooks/{webhook_id}/test', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/webhooks/inbound/run-ticket', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/webhooks/inbound/run-spec', self.handle_options)

        # AI-245: Team Management - Roles & Permissions
        if _TEAMS_AVAILABLE:
            register_team_routes(self.app)

        # AI-247: GA Launch - Pricing Tier Activation & Enforcement
        if _BILLING_ROUTES_AVAILABLE:
            register_billing_routes(self.app)

        # AI-246: Audit Log for Compliance
        if _AUDIT_AVAILABLE:
            register_audit_routes(self.app)

    async def handle_options(self, request: Request) -> Response:
        """Handle CORS preflight OPTIONS requests."""
        return web.Response(status=204)

    async def serve_dashboard(self, request: Request) -> Response:
        """Serve the main dashboard (index.html) at the root URL."""
        html_path = Path(__file__).parent / 'index.html'
        if html_path.exists():
            return web.Response(
                text=html_path.read_text(),
                content_type='text/html',
            )
        raise web.HTTPNotFound(text='index.html not found')

    async def serve_architecture(self, request: Request) -> Response:
        """Serve the architecture view (dashboard.html) at /architecture."""
        html_path = Path(__file__).parent / 'dashboard.html'
        if html_path.exists():
            return web.Response(
                text=html_path.read_text(),
                content_type='text/html',
            )
        raise web.HTTPNotFound(text='dashboard.html not found')

    async def health_check(self, request: Request) -> Response:
        """Health check endpoint.

        Returns:
            JSON response with server status and metrics file info
        """
        stats = self.store.get_stats()

        return web.json_response({
            'status': 'ok',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'project': self.project_name,
            'metrics_file_exists': stats['metrics_file_exists'],
            'event_count': stats['event_count'],
            'session_count': stats['session_count'],
            'agent_count': stats['agent_count']
        })

    async def get_metrics_health(self, request: Request) -> Response:
        """GET /api/health/metrics — collector health status (AI-185 / REQ-REL-003).

        Reports whether the ``.agent_metrics.json`` file is present and contains
        valid JSON.  When degraded, a human-readable reason is included so the
        frontend can display the "Metrics unavailable" banner.

        Response shape:
            {
                "healthy": true/false,
                "degradation_reason": null | "<string>",
                "metrics_file_exists": true/false,
                "timestamp": "<ISO-8601>",
                "project": "<name>"
            }

        Returns:
            200 JSON response with health status.
        """
        metrics_path = self.store.metrics_path
        file_exists = metrics_path.exists()

        # Determine health and degradation reason
        healthy = False
        degradation_reason = None

        if not file_exists:
            degradation_reason = f"Metrics file missing: {metrics_path}"
        else:
            try:
                import json as _json
                with open(metrics_path, "r", encoding="utf-8") as fh:
                    data = _json.load(fh)
                if self.store._validate_state(data):
                    healthy = True
                else:
                    degradation_reason = f"Metrics file has invalid structure: {metrics_path}"
            except Exception as exc:
                degradation_reason = f"Metrics file corrupted (invalid JSON): {metrics_path} — {exc}"

        return web.json_response({
            "healthy": healthy,
            "degradation_reason": degradation_reason,
            "metrics_file_exists": file_exists,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "project": self.project_name,
        })

    async def get_latency_stats(self, request: Request) -> Response:
        """GET /api/latency — return real-time WebSocket latency statistics.

        Returns JSON with p50, p95, p99, max, mean, count, within_100ms_pct.
        Latency is measured from just before send_json() through to delivery
        completion for each broadcast_to_websockets() call (AI-180).

        Returns:
            JSON response with current latency statistics.
        """
        stats = self.latency_tracker.get_stats()
        stats["target_ms"] = 100
        stats["target_met"] = self.latency_tracker.check_target(100)
        stats["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return web.json_response(stats)

    async def get_streaming_latency_stats(self, request: Request) -> Response:
        """GET /api/streaming-latency — return chat streaming start latency stats.

        Returns JSON with p50, p95, p99, max, mean, count, within_500ms_pct.
        Latency is measured from handle_message() call to the first chunk
        yielded by the ChatBridge pipeline (AI-182 / REQ-PERF-003).

        Returns:
            JSON response with current streaming latency statistics.
        """
        stats = self.streaming_latency_tracker.get_streaming_stats()
        stats["target_ms"] = 500
        stats["target_met"] = self.streaming_latency_tracker.check_streaming_target(500)
        stats["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return web.json_response(stats)

    async def get_metrics(self, request: Request) -> Response:
        """Get all metrics data.

        Returns complete DashboardState including:
        - Global counters
        - All agent profiles
        - Recent events (last 500)
        - Session history (last 50)

        Query Parameters:
            pretty: If set, format JSON with indentation

        Returns:
            JSON response with complete metrics data
        """
        logger.info("GET /api/metrics")

        try:
            state = self.store.load()

            # Check if client wants pretty-printed JSON
            pretty = 'pretty' in request.query

            if pretty:
                json_data = json.dumps(state, indent=2, ensure_ascii=False)
                return web.Response(
                    text=json_data,
                    content_type='application/json',
                    status=200
                )
            else:
                return web.json_response(state)

        except Exception as e:
            logger.error(f"Error loading metrics: {e}")
            raise web.HTTPInternalServerError(
                text=json.dumps({'error': str(e)}),
                content_type='application/json'
            )

    # =========================================================================
    # AI-79: Agent Status Panel (REQ-MONITOR-001)
    # =========================================================================

    async def get_all_agents_status(self, request: Request) -> Response:
        """GET /api/agents/status - Get current status of all 13 panel agents."""
        timestamp = datetime.utcnow().isoformat() + 'Z'
        agents_status = []

        for agent_name in _PANEL_AGENT_NAMES:
            detail = _dashboard_agent_status.get(agent_name, {
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

    async def update_agent_status_handler(self, request: Request) -> Response:
        """POST /api/agents/{agent_name}/status - Update agent status."""
        agent_name = request.match_info['agent_name']

        if agent_name not in _PANEL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
                'available_agents': _PANEL_AGENT_NAMES,
            }, status=404)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        new_status = body.get('status', '')
        if new_status not in _VALID_PANEL_STATUSES:
            return web.json_response({
                'error': f'Invalid status. Must be one of: {list(_VALID_PANEL_STATUSES)}',
                'provided': new_status,
            }, status=400)

        current_ticket = body.get('current_ticket', None)
        timestamp = datetime.utcnow().isoformat() + 'Z'

        # AI-80 / REQ-MONITOR-002: new optional fields for active requirement display
        ticket_title = body.get('ticket_title', None)
        description = body.get('description', None)
        token_count = body.get('token_count', 0)
        estimated_cost = body.get('estimated_cost', 0.0)

        if agent_name not in _dashboard_agent_status:
            _dashboard_agent_status[agent_name] = {
                "name": agent_name, "status": "idle",
                "current_ticket": None, "started_at": None,
                "ticket_title": None, "description": None,
                "token_count": 0, "estimated_cost": 0.0,
            }

        previous_status = _dashboard_agent_status[agent_name].get("status", "idle")
        _dashboard_agent_status[agent_name]["status"] = new_status
        _dashboard_agent_status[agent_name]["current_ticket"] = current_ticket if new_status == "running" else None

        if new_status == "running":
            _dashboard_agent_status[agent_name]["started_at"] = timestamp
            _dashboard_agent_status[agent_name]["ticket_title"] = ticket_title
            _dashboard_agent_status[agent_name]["description"] = description
            _dashboard_agent_status[agent_name]["token_count"] = token_count
            _dashboard_agent_status[agent_name]["estimated_cost"] = estimated_cost
        elif new_status in ("idle", "error"):
            _dashboard_agent_status[agent_name]["started_at"] = None
            _dashboard_agent_status[agent_name]["ticket_title"] = None
            _dashboard_agent_status[agent_name]["description"] = None
            _dashboard_agent_status[agent_name]["token_count"] = 0
            _dashboard_agent_status[agent_name]["estimated_cost"] = 0.0

        # Broadcast via WebSocket
        message = {
            'type': 'agent_status',
            'agent': agent_name,
            'status': new_status,
            'ticket': current_ticket or '',
            'timestamp': timestamp,
        }
        await self.broadcast_to_websockets(message)

        # AI-227: Track agent pause/resume events
        if new_status == "paused":
            _collect_event("agent_paused", {"agent_name": agent_name})
        elif new_status == "running" and previous_status == "paused":
            _collect_event("agent_resumed", {"agent_name": agent_name})
        elif new_status == "running" and previous_status == "idle":
            _collect_event("session_started", {"agent_name": agent_name})

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

    # =========================================================================
    # AI-81: Agent Detail View (REQ-MONITOR-003)
    # =========================================================================

    async def get_agent_profile(self, request: Request) -> Response:
        """GET /api/agents/{agent_name}/profile - Full agent profile for detail view.

        Returns agent profile data including:
        - name, model (from DEFAULT_MODELS), status
        - lifetime_stats: tasks_completed, tasks_failed, success_rate, total_tokens, total_cost, avg_duration
        - gamification: xp, level, streak, achievements
        - contribution_counters: commits, prs_created, prs_merged, linear_issues_closed
        - strengths, weaknesses
        - recent_events: last 20 events

        Returns:
            200 OK with profile data
            404 Not Found if agent not in panel list
        """
        agent_name = request.match_info['agent_name']

        if agent_name not in _PANEL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
                'available_agents': _PANEL_AGENT_NAMES,
            }, status=404)

        # Get status info
        status_info = _dashboard_agent_status.get(agent_name, {})
        current_status = status_info.get('status', 'idle')
        model = _DEFAULT_MODELS.get(agent_name, 'haiku')

        # Try to load from metrics store for real data
        agent_profile_data = {}
        try:
            state = self.store.load()
            agent_profile_data = state.get('agents', {}).get(agent_name, {})
        except Exception:
            pass

        # Build lifetime_stats from profile or defaults
        total_inv = agent_profile_data.get('total_invocations', 0)
        successful_inv = agent_profile_data.get('successful_invocations', 0)
        failed_inv = agent_profile_data.get('failed_invocations', 0)
        total_tokens = agent_profile_data.get('total_tokens', 0)
        total_cost = agent_profile_data.get('total_cost_usd', 0.0)
        total_duration = agent_profile_data.get('total_duration_seconds', 0.0)
        success_rate = agent_profile_data.get('success_rate', 0.0)
        avg_duration = agent_profile_data.get('avg_duration_seconds', 0.0)

        # Build gamification data
        xp = agent_profile_data.get('xp', 0)
        level = agent_profile_data.get('level', 1)
        streak = agent_profile_data.get('current_streak', 0)
        best_streak = agent_profile_data.get('best_streak', 0)
        achievements = agent_profile_data.get('achievements', [])

        # Build contribution counters
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

        # Get recent events from in-memory store
        recent_events = list(_agent_recent_events.get(agent_name, []))

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
        """POST /api/agents/{agent_name}/events - Add an event to agent's recent history.

        Maintains a rolling window of the last 20 events per agent.

        Request body:
            {
                "type": "task_started|task_completed|error_occurred|...",
                "title": "Event title",
                "status": "success|error|in_progress|...",
                "ticket_key": "AI-123",  (optional)
                "duration": 12.5         (optional, seconds)
            }

        Returns:
            201 Created with event data
            404 Not Found if agent not in panel list
            400 Bad Request if body is invalid
        """
        agent_name = request.match_info['agent_name']

        if agent_name not in _PANEL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
                'available_agents': _PANEL_AGENT_NAMES,
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

        # Build the event record
        from uuid import uuid4
        event = {
            'id': str(uuid4()),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'type': event_type,
            'title': title,
            'status': status,
            'ticket_key': ticket_key,
            'duration': duration,
        }

        # Initialize list if needed, then append and keep last 20
        if agent_name not in _agent_recent_events:
            _agent_recent_events[agent_name] = []
        _agent_recent_events[agent_name].append(event)
        _agent_recent_events[agent_name] = _agent_recent_events[agent_name][-20:]

        return web.json_response({
            'event': event,
            'agent_name': agent_name,
            'total_events': len(_agent_recent_events[agent_name]),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        }, status=201)

    async def get_agent(self, request: Request) -> Response:
        """Get specific agent profile by name.

        Path Parameters:
            agent_name: Name of the agent (e.g., 'coding_agent', 'github_agent')

        Query Parameters:
            include_events: If set, include recent events for this agent
            pretty: If set, format JSON with indentation

        Returns:
            JSON response with agent profile and optionally recent events

        Raises:
            404: If agent not found
        """
        agent_name = request.match_info['agent_name']
        logger.info(f"GET /api/agents/{agent_name}")

        try:
            state = self.store.load()

            # Check if agent exists
            if agent_name not in state['agents']:
                logger.warning(f"Agent not found: {agent_name}")
                raise web.HTTPNotFound(
                    text=json.dumps({
                        'error': 'Agent not found',
                        'agent_name': agent_name,
                        'available_agents': list(state['agents'].keys())
                    }),
                    content_type='application/json'
                )

            # Get agent profile
            agent_profile = state['agents'][agent_name]

            response_data = {
                'agent': agent_profile,
                'project_name': state['project_name'],
                'updated_at': state['updated_at']
            }

            # Optionally include recent events for this agent
            if 'include_events' in request.query:
                agent_events = [
                    event for event in state['events']
                    if event['agent_name'] == agent_name
                ]
                # Return last 20 events
                response_data['recent_events'] = agent_events[-20:]

            # Check if client wants pretty-printed JSON
            pretty = 'pretty' in request.query

            if pretty:
                json_data = json.dumps(response_data, indent=2, ensure_ascii=False)
                return web.Response(
                    text=json_data,
                    content_type='application/json',
                    status=200
                )
            else:
                return web.json_response(response_data)

        except web.HTTPNotFound:
            raise
        except Exception as e:
            logger.error(f"Error loading agent {agent_name}: {e}")
            raise web.HTTPInternalServerError(
                text=json.dumps({'error': str(e)}),
                content_type='application/json'
            )

    async def get_agent_requirement(self, request: Request) -> Response:
        """GET /api/agents/{agent_name}/requirement - Get full requirement details for a running agent.

        AI-80 / REQ-MONITOR-002: Returns ticket key, title, description, token_count,
        estimated_cost, and elapsed_time for a running agent.
        """
        agent_name = request.match_info['agent_name']

        if agent_name not in _PANEL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
                'available_agents': _PANEL_AGENT_NAMES,
            }, status=404)

        detail = _dashboard_agent_status.get(agent_name, {
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
        """POST /api/agents/{agent_name}/metrics - Update token_count and estimated_cost.

        AI-80 / REQ-MONITOR-002: Real-time metrics update endpoint. Broadcasts
        agent_metrics_update WebSocket message with updated values.
        """
        agent_name = request.match_info['agent_name']

        if agent_name not in _PANEL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
                'available_agents': _PANEL_AGENT_NAMES,
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
        if agent_name not in _dashboard_agent_status:
            _dashboard_agent_status[agent_name] = {
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
            _dashboard_agent_status[agent_name]["token_count"] = token_count
        if estimated_cost is not None:
            _dashboard_agent_status[agent_name]["estimated_cost"] = estimated_cost

        timestamp = datetime.utcnow().isoformat() + 'Z'
        detail = _dashboard_agent_status[agent_name]

        # Broadcast agent_metrics_update via WebSocket
        message = {
            'type': 'agent_metrics_update',
            'agent': agent_name,
            'token_count': detail.get("token_count", 0),
            'estimated_cost': detail.get("estimated_cost", 0.0),
            'timestamp': timestamp,
        }
        await self.broadcast_to_websockets(message)

        return web.json_response({
            'status': 'success',
            'agent_name': agent_name,
            'token_count': detail.get("token_count", 0),
            'estimated_cost': detail.get("estimated_cost", 0.0),
            'timestamp': timestamp,
        })

    async def get_requirement(self, request: Request) -> Response:
        """Get the current requirement text for a ticket.

        Path Parameters:
            ticket_key: Linear ticket key (e.g. 'AI-157')

        Returns:
            JSON response with ticket_key and requirement text.
            If no requirement is stored, returns an empty string.
        """
        ticket_key = request.match_info['ticket_key']
        logger.info(f"GET /api/requirements/{ticket_key}")

        # Validate ticket_key format (e.g., AI-157)
        if not re.match(r'^[A-Z]+-\d+$', ticket_key):
            return web.json_response({'error': 'Invalid ticket key format'}, status=400)

        requirement_text = _requirements_store.get(ticket_key, '')
        return web.json_response({
            'ticket_key': ticket_key,
            'requirement': requirement_text,
        })

    async def put_requirement(self, request: Request) -> Response:
        """Update the requirement text for a ticket, optionally syncing to Linear.

        Path Parameters:
            ticket_key: Linear ticket key (e.g. 'AI-157')

        Request Body (JSON):
            requirement (str): The updated requirement text
            sync_to_linear (bool): If true, update the Linear issue description

        Returns:
            JSON response with success status and optional linear_synced flag.

        Raises:
            400: If request body is invalid JSON or missing 'requirement' field
            500: If Linear API call fails when sync_to_linear is true
        """
        ticket_key = request.match_info['ticket_key']
        logger.info(f"PUT /api/requirements/{ticket_key}")

        # Validate ticket_key format (e.g., AI-157)
        if not re.match(r'^[A-Z]+-\d+$', ticket_key):
            return web.json_response({'error': 'Invalid ticket key format'}, status=400)

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                {'error': 'Invalid JSON in request body'},
                status=400,
            )

        if 'requirement' not in body:
            return web.json_response(
                {'error': 'Missing required field: requirement'},
                status=400,
            )

        requirement_text = body['requirement']

        if not isinstance(requirement_text, str):
            return web.json_response({'error': 'requirement must be a string'}, status=400)

        sync_to_linear = bool(body.get('sync_to_linear', False))

        # Store locally (atomic in-memory update)
        _requirements_store[ticket_key] = requirement_text
        logger.info(f"Stored requirement for {ticket_key} ({len(requirement_text)} chars)")

        linear_synced = False
        if sync_to_linear:
            linear_api_key = os.environ.get('LINEAR_API_KEY', '')
            if not linear_api_key:
                logger.warning("LINEAR_API_KEY not set — cannot sync to Linear")
                return web.json_response(
                    {
                        'success': True,
                        'ticket_key': ticket_key,
                        'linear_synced': False,
                        'linear_error': 'LINEAR_API_KEY environment variable is not set',
                    },
                    status=200,
                )
            try:
                linear_synced = await update_linear_issue(ticket_key, requirement_text)
                logger.info(f"Linear sync successful for {ticket_key}")
            except Exception as e:
                logger.error(f"Linear API error for {ticket_key}: {e}")
                return web.json_response(
                    {
                        'success': True,
                        'ticket_key': ticket_key,
                        'linear_synced': False,
                        'linear_error': str(e),
                    },
                    status=200,
                )

        return web.json_response({
            'success': True,
            'ticket_key': ticket_key,
            'linear_synced': linear_synced,
        })

    async def post_chat(self, request: Request) -> Response:
        """Handle a chat message via the Chat-to-Agent Bridge.

        POST /api/chat

        Request Body (JSON):
            message (str): User message text
            provider (str, optional): AI provider (claude, chatgpt, etc.). Default: "claude"
            message_id (str, optional): Client-supplied message ID for tracking

        Returns:
            JSON response with:
                - message_id: str
                - routing: routing decision
                - response: str (agent or AI response)
                - timestamp: ISO timestamp
                - provider: AI provider used

        Raises:
            400: If message is missing or empty
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                {'error': 'Invalid JSON in request body'},
                status=400,
            )

        message = body.get('message', '').strip()
        if not message:
            return web.json_response(
                {'error': 'Missing required field: message'},
                status=400,
            )

        provider = body.get('provider', 'claude')
        message_id = body.get('message_id')

        # Create a router with current WebSocket connections for streaming
        router = ChatRouter(
            websockets=self.websockets,
            linear_api_key=os.environ.get('LINEAR_API_KEY'),
        )

        result = await router.enqueue_message(message, provider=provider, message_id=message_id)

        logger.info(
            f"POST /api/chat: '{message[:50]}' -> "
            f"provider={result.get('provider', provider)}, "
            f"intent={result['routing'].get('intent_type')}, "
            f"handler={result['routing'].get('handler')}"
        )

        # AI-227: Track chat message event (no message content — privacy first)
        _collect_event("chat_message_sent", {
            "provider": result.get("provider", provider),
            "intent_type": result["routing"].get("intent_type"),
            "handler": result["routing"].get("handler"),
        })

        return web.json_response(result)

    async def post_chat_route(self, request: Request) -> Response:
        """Route a chat message without executing it.

        POST /api/chat/route

        Returns only the routing decision without executing the action.
        Useful for previewing routing decisions.

        Request Body (JSON):
            message (str): User message text

        Returns:
            JSON response with routing decision:
                - intent_type: "agent_action" | "query" | "conversation"
                - handler: "agent_executor" | "linear_api" | "ai_provider"
                - agent: target agent name or None
                - action: action to perform or None
                - params: action parameters
                - description: human-readable routing description

        Raises:
            400: If message is missing or empty
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                {'error': 'Invalid JSON in request body'},
                status=400,
            )

        message = body.get('message', '').strip()
        if not message:
            return web.json_response(
                {'error': 'Missing required field: message'},
                status=400,
            )

        # Parse and route without executing
        intent = parse_intent(message)
        router = ChatRouter()
        routing = router.get_routing_decision(intent)

        logger.info(f"POST /api/chat/route: '{message[:50]}' -> {routing['intent_type']}")

        return web.json_response({
            'message': message,
            'intent': {
                'intent_type': intent.intent_type,
                'agent': intent.agent,
                'action': intent.action,
                'params': intent.params,
            },
            'routing': routing,
        })

    async def get_chat_history(self, request: Request) -> Response:
        """Get recent chat history.

        GET /api/chat/history

        Query Parameters:
            limit (int, optional): Max messages to return. Default: 100.

        Returns:
            JSON array of chat message objects
        """
        limit = int(request.query.get('limit', 100))
        history = get_chat_history(limit=limit)
        return web.json_response({'messages': history, 'count': len(history)})

    async def broadcast_to_websockets(self, message: dict) -> None:
        """Broadcast a JSON message to all connected WebSocket clients.

        Optionally records latency via self.latency_tracker (AI-180 / REQ-PERF-001).
        A unique event_id is stamped just before the send loop starts and marked
        delivered immediately after all clients have received the message.

        Args:
            message: Dictionary to serialise and send to every active client.
                     Disconnected clients are silently removed from the pool.
        """
        # Record emission timestamp for latency tracking
        event_id = str(uuid4())
        self.latency_tracker.record_emit(event_id)

        disconnected = set()
        for ws in self.websockets:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket {id(ws)}: {e}")
                disconnected.add(ws)
        self.websockets -= disconnected
        if disconnected:
            logger.info(f"Removed {len(disconnected)} disconnected WebSocket clients during broadcast")

        # Record delivery timestamp to complete the latency measurement
        self.latency_tracker.record_delivery(event_id)

    def _on_new_event(self, event: dict) -> None:
        """Callback invoked by AgentMetricsCollector when a new event is recorded (AI-171).

        Formats the event as an ``agent_event`` WebSocket message and schedules
        an async broadcast on the running event loop. The method is intentionally
        synchronous so it can be called from the non-async ``_record_event``.

        The formatted message is also appended to the in-memory backlog so that
        newly connected WebSocket clients can receive recent events.

        Args:
            event: An AgentEvent TypedDict produced by AgentTracker.finalize().
        """
        message = {
            "type": "agent_event",
            "agent": event.get("agent_name", ""),
            "event_type": event.get("status", ""),
            "details": {
                "event_id": event.get("event_id", ""),
                "session_id": event.get("session_id", ""),
                "ticket_key": event.get("ticket_key", ""),
                "model_used": event.get("model_used", ""),
                "input_tokens": event.get("input_tokens", 0),
                "output_tokens": event.get("output_tokens", 0),
                "total_tokens": event.get("total_tokens", 0),
                "estimated_cost_usd": event.get("estimated_cost_usd", 0.0),
                "duration_seconds": event.get("duration_seconds", 0.0),
                "artifacts": event.get("artifacts", []),
                "error_message": event.get("error_message", ""),
                "started_at": event.get("started_at", ""),
                "ended_at": event.get("ended_at", ""),
            },
            "timestamp": event.get("ended_at", datetime.utcnow().isoformat() + "Z"),
        }

        # Maintain backlog circular buffer
        self._agent_event_backlog.append(message)
        if len(self._agent_event_backlog) > self._AGENT_EVENT_BACKLOG_MAX:
            del self._agent_event_backlog[0]

        # Schedule the async broadcast on whichever event loop is running.
        # If no loop is running (e.g. during unit tests that call _on_new_event
        # directly without a server), this will be a no-op to avoid RuntimeError.
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.broadcast_to_websockets(message), loop=loop)
        except RuntimeError:
            pass

        logger.info(
            "Agent event received from collector: agent=%r, status=%r, ticket=%r",
            event.get("agent_name"),
            event.get("status"),
            event.get("ticket_key"),
        )

    async def broadcast_reasoning(self, request: Request) -> Response:
        """POST /api/reasoning — broadcast a reasoning event to all WebSocket clients.

        Expected JSON body::

            {
                "content": "<reasoning text>",
                "ticket":  "<optional ticket key, e.g. AI-158>"
            }

        Returns:
            JSON ``{"success": true}`` on success, or
            ``{"error": "<message>", "status": 400}`` for malformed requests.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        content = body.get('content', '')
        ticket = body.get('ticket', '')

        message = {
            'type': 'reasoning',
            'content': content,
            'ticket': ticket,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        }

        await self.broadcast_to_websockets(message)
        logger.info(f"Reasoning event broadcast: ticket={ticket!r}, content_len={len(content)}")

        return web.json_response({'success': True})

    async def broadcast_agent_thinking(self, request: Request) -> Response:
        """POST /api/agent-thinking — broadcast an agent thinking event to all WebSocket clients.

        Expected JSON body::

            {
                "agent":    "<agent name, e.g. 'coding'>",
                "category": "<one of: files|changes|commands|tests>",
                "content":  "<thinking text>",
                "ticket":   "<optional ticket key, e.g. 'AI-159'>"
            }

        Returns:
            JSON ``{"success": true}`` on success, or
            ``{"error": "<message>"}`` with status 400 for malformed requests.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        agent = body.get('agent', '')
        category = body.get('category', 'files')
        content = body.get('content', '')
        ticket = body.get('ticket', '')

        timestamp = datetime.now().isoformat()
        message = {
            'type': 'agent_thinking',
            'agent': agent,
            'category': category,
            'content': content,
            'ticket': ticket,
            'timestamp': timestamp,
        }

        # Append to reasoning history circular buffer (AI-160)
        self._reasoning_history.append({
            'type': 'agent_thinking',
            'agent': agent,
            'category': category,
            'content': content,
            'ticket': ticket,
            'timestamp': timestamp,
        })
        if len(self._reasoning_history) > _REASONING_HISTORY_MAX:
            del self._reasoning_history[0]

        await self.broadcast_to_websockets(message)
        logger.info(
            f"Agent thinking event broadcast: agent={agent!r}, category={category!r}, "
            f"ticket={ticket!r}, content_len={len(content)}"
        )

        return web.json_response({'success': True})

    async def get_reasoning_blocks(self, request: Request) -> Response:
        """GET /api/reasoning/blocks — return summary of recent reasoning/thinking events.

        Returns the last 50 events from the circular buffer of reasoning and
        agent-thinking events that have been broadcast since server start.

        Returns:
            JSON ``{"blocks": [...], "total": N}`` where blocks contains at most
            50 of the most recent events.
        """
        # Return last 50 of the up-to-100 stored events
        blocks = self._reasoning_history[-50:]
        return web.json_response({
            'blocks': blocks,
            'total': len(self._reasoning_history),
        })

    async def post_reasoning_block(self, request: Request) -> Response:
        """POST /api/reasoning/block — store and broadcast a structured reasoning block.

        AI-94 (orchestrator decision display) and AI-95 (agent thinking inner monologue).

        Expected JSON body::

            {
                "type": "orchestrator_decision|agent_thinking",
                "agent": "coding",
                "ticket_key": "AI-94",
                "title": "Delegating to coding agent",
                "complexity": "COMPLEX",
                "content": "Reasoning text...",
                "steps": [{"action": "read_file", "target": "server.py", "reason": "Check existing routes"}]
            }

        Returns:
            JSON ``{"success": true, "block": {...}}`` on success, or
            ``{"error": "<message>"}`` with status 400 for malformed requests.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        block_type = body.get('type', 'agent_thinking')
        valid_types = ('orchestrator_decision', 'agent_thinking')
        if block_type not in valid_types:
            block_type = 'agent_thinking'

        timestamp = datetime.utcnow().isoformat() + 'Z'
        block = {
            'id': f"rb-{int(datetime.utcnow().timestamp() * 1000)}",
            'type': block_type,
            'agent': body.get('agent', ''),
            'ticket_key': body.get('ticket_key', ''),
            'title': body.get('title', ''),
            'complexity': body.get('complexity', ''),
            'content': body.get('content', ''),
            'steps': body.get('steps', []),
            'timestamp': timestamp,
        }

        # Store in _reasoning_blocks (capped at 20)
        self._reasoning_blocks.append(block)
        if len(self._reasoning_blocks) > 20:
            del self._reasoning_blocks[0]

        # Also append to legacy _reasoning_history (capped at _REASONING_HISTORY_MAX)
        self._reasoning_history.append(block)
        if len(self._reasoning_history) > _REASONING_HISTORY_MAX:
            del self._reasoning_history[0]

        # Broadcast via WebSocket as reasoning_block event
        ws_message = {
            'type': 'reasoning_block',
            'block': block,
        }
        await self.broadcast_to_websockets(ws_message)
        logger.info(
            f"Reasoning block stored & broadcast: type={block_type!r}, "
            f"agent={block['agent']!r}, ticket={block['ticket_key']!r}, "
            f"complexity={block['complexity']!r}"
        )

        return web.json_response({'success': True, 'block': block})

    async def clear_reasoning_blocks(self, request: Request) -> Response:
        """POST /api/reasoning/clear — clear all stored reasoning blocks.

        Returns:
            JSON ``{"success": true, "cleared": N}`` indicating how many blocks were cleared.
        """
        count = len(self._reasoning_blocks)
        self._reasoning_blocks.clear()
        logger.info(f"Reasoning blocks cleared: {count} blocks removed")
        return web.json_response({'success': True, 'cleared': count})

    async def post_decision(self, request: Request) -> Response:
        """POST /api/decisions — log an orchestrator decision and broadcast via WebSocket.

        Expected JSON body::

            {
                "type": "agent_selection",   # one of DECISION_TYPES
                "ticket": "AI-42",           # optional
                "decision": "Use coding (sonnet) agent",
                "reason": "Security-related changes require deeper analysis",
                "outcome": "pending"         # optional: pending|success|failure
            }

        Returns:
            JSON with the stored decision (including generated id and timestamp).
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        decision_type = body.get('type', 'other')
        if decision_type not in DECISION_TYPES:
            decision_type = 'other'

        decision_text = body.get('decision', '')
        if not decision_text:
            return web.json_response({'error': 'Missing required field: decision'}, status=400)

        record = {
            'id': str(uuid4()),
            'type': decision_type,
            'ticket': body.get('ticket', ''),
            'decision': decision_text,
            'reason': body.get('reason', ''),
            'outcome': body.get('outcome', 'pending'),
            'timestamp': datetime.now().isoformat(),
            # NEW AUDIT TRAIL FIELDS (AI-162):
            'input_factors': body.get('input_factors', {}),
            'agent_selected': body.get('agent_selected', ''),
            'model_used': body.get('model_used', ''),
            'agent_event_id': body.get('agent_event_id', ''),
            'duration_ms': body.get('duration_ms', None),
            'session_id': body.get('session_id', ''),
        }

        # Append to circular buffer
        self._decision_log.append(record)
        if len(self._decision_log) > _DECISION_LOG_MAX:
            del self._decision_log[0]

        # Broadcast to WebSocket clients
        await self.broadcast_to_websockets({
            'type': 'decision_logged',
            'decision': record,
        })

        logger.info(
            f"Decision logged: type={decision_type!r}, ticket={record['ticket']!r}, "
            f"decision={decision_text[:60]!r}"
        )

        return web.json_response(record, status=201)

    async def get_decisions(self, request: Request) -> Response:
        """GET /api/decisions — return decision log with optional filtering.

        Query Parameters:
            type: Filter by decision type (e.g. agent_selection)
            ticket: Filter by ticket key (e.g. AI-42)
            limit: Maximum number of results to return (default: 50)

        Returns:
            JSON ``{"decisions": [...], "total": N}``
        """
        decision_type_filter = request.query.get('type', '').strip()
        ticket_filter = request.query.get('ticket', '').strip()
        limit_str = request.query.get('limit', '').strip()

        results = list(self._decision_log)

        if decision_type_filter:
            results = [d for d in results if d['type'] == decision_type_filter]

        if ticket_filter:
            results = [d for d in results if d['ticket'] == ticket_filter]

        # Most recent first
        results = list(reversed(results))

        # Apply limit — default 50 (AI-97)
        default_limit = 50
        if limit_str:
            try:
                limit = int(limit_str)
                results = results[:limit]
            except ValueError:
                results = results[:default_limit]
        else:
            results = results[:default_limit]

        return web.json_response({
            'decisions': results,
            'total': len(results),
        })

    async def export_decisions(self, request: Request) -> Response:
        """GET /api/decisions/export — export decision log as JSON or CSV.

        Query Parameters:
            format: 'json' (default) or 'csv'

        Returns:
            JSON array or CSV file download.
        """
        export_format = request.query.get('format', 'json').lower()

        if export_format == 'csv':
            output = io.StringIO()
            fieldnames = [
                'id', 'type', 'ticket', 'decision', 'reason', 'outcome', 'timestamp',
                'agent_selected', 'model_used', 'agent_event_id', 'duration_ms', 'session_id',
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for record in self._decision_log:
                writer.writerow({f: record.get(f, '') for f in fieldnames})

            return web.Response(
                text=output.getvalue(),
                content_type='text/csv',
                headers={'Content-Disposition': 'attachment; filename="decisions.csv"'},
            )
        else:
            # Default: JSON
            return web.json_response(list(self._decision_log))

    async def get_decision_by_id(self, request: Request) -> Response:
        """GET /api/decisions/{decision_id} — return a single decision by ID (AI-162).

        Path Parameters:
            decision_id: UUID of the decision to retrieve

        Returns:
            JSON decision record, or 404 if not found.
        """
        decision_id = request.match_info['decision_id']
        for record in self._decision_log:
            if record['id'] == decision_id:
                return web.json_response(record)
        raise web.HTTPNotFound(
            text=json.dumps({'error': 'Decision not found', 'id': decision_id}),
            content_type='application/json',
        )

    async def get_decisions_summary(self, request: Request) -> Response:
        """GET /api/decisions/summary — return aggregate counts (AI-162).

        Returns:
            JSON summary with total, by_type, by_outcome, and recent_session_count.
        """
        by_type: dict = {}
        by_outcome: dict = {}
        session_ids: set = set()

        for record in self._decision_log:
            dtype = record.get('type', 'other')
            by_type[dtype] = by_type.get(dtype, 0) + 1

            outcome = record.get('outcome', 'pending')
            by_outcome[outcome] = by_outcome.get(outcome, 0) + 1

            sid = record.get('session_id', '')
            if sid:
                session_ids.add(sid)

        return web.json_response({
            'total': len(self._decision_log),
            'by_type': by_type,
            'by_outcome': by_outcome,
            'recent_session_count': len(session_ids),
        })

    async def post_code_stream(self, request: Request) -> Response:
        """POST /api/code-stream — receive a code streaming chunk and broadcast via WebSocket.

        Expected JSON body::

            {
                "agent":       "coding",         # which agent (coding|coding_fast)
                "file_path":   "src/app.py",     # file being edited
                "language":    "python",         # optional; auto-detected from extension if absent
                "chunk":       "    def foo():", # the code chunk
                "chunk_type":  "addition",       # addition|deletion|context
                "stream_id":   "uuid",           # groups chunks for the same edit session
                "is_final":    false             # True when streaming is complete
            }

        Returns:
            JSON ``{"success": true, "stream_id": "<uuid>"}``

        Raises:
            400: If request body is invalid or missing required fields.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        agent = body.get('agent', '')
        file_path = body.get('file_path', '')
        if not file_path:
            return web.json_response({'error': 'Missing required field: file_path'}, status=400)

        chunk = body.get('chunk', '')
        chunk_type = body.get('chunk_type', 'context')
        if chunk_type not in ('addition', 'deletion', 'context'):
            chunk_type = 'context'

        is_final = bool(body.get('is_final', False))

        # Use provided stream_id or generate one
        stream_id = body.get('stream_id', '') or str(uuid4())

        # Auto-detect language from file extension if not provided
        language = body.get('language', '') or detect_language(file_path)

        timestamp = datetime.utcnow().isoformat() + 'Z'

        # Create or update stream record
        if stream_id not in self._code_streams:
            self._code_streams[stream_id] = {
                'stream_id': stream_id,
                'agent': agent,
                'file_path': file_path,
                'language': language,
                'chunks': [],
                'started_at': timestamp,
                'completed': False,
            }

        stream = self._code_streams[stream_id]
        stream['chunks'].append({
            'chunk': chunk,
            'chunk_type': chunk_type,
            'timestamp': timestamp,
        })

        if is_final:
            stream['completed'] = True
            stream['completed_at'] = timestamp

        # Broadcast to WebSocket clients
        ws_message = {
            'type': 'code_stream',
            'agent': agent,
            'file_path': file_path,
            'language': language,
            'chunk': chunk,
            'chunk_type': chunk_type,
            'stream_id': stream_id,
            'is_final': is_final,
            'timestamp': timestamp,
        }
        await self.broadcast_to_websockets(ws_message)

        logger.info(
            f"Code stream chunk: agent={agent!r}, file={file_path!r}, "
            f"lang={language!r}, stream_id={stream_id!r}, "
            f"chunk_type={chunk_type!r}, is_final={is_final}"
        )

        return web.json_response({'success': True, 'stream_id': stream_id})

    async def get_code_streams(self, request: Request) -> Response:
        """GET /api/code-streams — list active and recent code streams.

        Query Parameters:
            agent: Filter by agent name
            completed: If 'true', include only completed streams; if 'false', only active

        Returns:
            JSON ``{"streams": [...], "total": N}`` with stream summaries (without chunks).
        """
        agent_filter = request.query.get('agent', '').strip()
        completed_filter = request.query.get('completed', '').strip().lower()

        results = []
        for stream_id, stream in self._code_streams.items():
            # Apply filters
            if agent_filter and stream.get('agent', '') != agent_filter:
                continue
            if completed_filter == 'true' and not stream.get('completed', False):
                continue
            if completed_filter == 'false' and stream.get('completed', False):
                continue

            # Return summary without full chunks list
            results.append({
                'stream_id': stream['stream_id'],
                'agent': stream['agent'],
                'file_path': stream['file_path'],
                'language': stream['language'],
                'chunk_count': len(stream['chunks']),
                'started_at': stream['started_at'],
                'completed': stream['completed'],
                'completed_at': stream.get('completed_at', None),
            })

        # Sort by most recent first
        results.sort(key=lambda s: s['started_at'], reverse=True)

        return web.json_response({
            'streams': results,
            'total': len(results),
        })

    async def get_code_stream_by_id(self, request: Request) -> Response:
        """GET /api/code-streams/{stream_id} — return full content of a code stream.

        Path Parameters:
            stream_id: UUID of the code stream

        Returns:
            JSON with full stream record including all chunks, or 404 if not found.
        """
        stream_id = request.match_info['stream_id']
        stream = self._code_streams.get(stream_id)
        if stream is None:
            raise web.HTTPNotFound(
                text=json.dumps({'error': 'Stream not found', 'stream_id': stream_id}),
                content_type='application/json',
            )
        return web.json_response(stream)

    async def post_file_changes(self, request: Request) -> Response:
        """POST /api/file-changes — store a file change summary and broadcast via WebSocket.

        Expected JSON body::

            {
                "agent":       "coding",
                "ticket":      "AI-42",       # optional
                "session_id":  "uuid",        # optional; auto-generated if not provided
                "files": [
                    {
                        "path":          "dashboard/server.py",
                        "status":        "modified",  # created|modified|deleted
                        "lines_added":   47,
                        "lines_removed": 3,
                        "diff":          "--- a/...\n+++ b/...\n..."  # optional
                    }
                ],
                "total_added":   47,          # optional; computed from files if absent
                "total_removed": 3,           # optional; computed from files if absent
                "timestamp":     "..."        # optional; auto-set if not provided
            }

        Returns:
            JSON with the stored record (HTTP 201), or 400 for malformed requests.

        WebSocket broadcast::

            {type: "file_changes", agent, ticket, session_id, files,
             total_added, total_removed, timestamp}
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        files = body.get('files', None)
        if files is None or not isinstance(files, list) or len(files) == 0:
            return web.json_response({'error': 'Missing required field: files (must be a non-empty list)'}, status=400)

        agent = body.get('agent', '')
        ticket = body.get('ticket', '')
        session_id = body.get('session_id', '') or str(uuid4())
        timestamp = body.get('timestamp', '') or (datetime.utcnow().isoformat() + 'Z')

        # Normalise file entries and validate statuses
        normalised_files = []
        for f in files:
            status = f.get('status', 'modified')
            if status not in FILE_CHANGE_STATUSES:
                status = 'modified'
            normalised_files.append({
                'path': f.get('path', ''),
                'status': status,
                'lines_added': int(f.get('lines_added', 0)),
                'lines_removed': int(f.get('lines_removed', 0)),
                'diff': f.get('diff', ''),
            })

        # Compute totals (prefer explicit values from body, else sum from files)
        total_added = body.get('total_added', None)
        total_removed = body.get('total_removed', None)
        if total_added is None:
            total_added = sum(f['lines_added'] for f in normalised_files)
        if total_removed is None:
            total_removed = sum(f['lines_removed'] for f in normalised_files)

        record = {
            'session_id': session_id,
            'agent': agent,
            'ticket': ticket,
            'files': normalised_files,
            'total_added': int(total_added),
            'total_removed': int(total_removed),
            'timestamp': timestamp,
        }

        # Append to circular buffer
        self._file_changes.append(record)
        if len(self._file_changes) > FILE_CHANGES_MAX:
            del self._file_changes[0]

        # Broadcast to WebSocket clients
        ws_message = {
            'type': 'file_changes',
            'agent': agent,
            'ticket': ticket,
            'session_id': session_id,
            'files': normalised_files,
            'total_added': record['total_added'],
            'total_removed': record['total_removed'],
            'timestamp': timestamp,
        }
        await self.broadcast_to_websockets(ws_message)

        logger.info(
            f"File changes stored: agent={agent!r}, ticket={ticket!r}, "
            f"session_id={session_id!r}, files={len(normalised_files)}, "
            f"+{record['total_added']}/-{record['total_removed']}"
        )

        return web.json_response(record, status=201)

    async def get_file_changes(self, request: Request) -> Response:
        """GET /api/file-changes — return recent file change summaries (last 50, newest first).

        Returns:
            JSON ``{"summaries": [...], "total": N}``
        """
        # Return last 50, newest first (reverse of storage order)
        recent = list(reversed(self._file_changes[-50:]))
        return web.json_response({
            'summaries': recent,
            'total': len(recent),
        })

    async def get_file_changes_by_session(self, request: Request) -> Response:
        """GET /api/file-changes/{session_id} — return a specific summary by session_id.

        Path Parameters:
            session_id: UUID of the file change session

        Returns:
            JSON file change summary record, or 404 if not found.
        """
        session_id = request.match_info['session_id']
        for record in reversed(self._file_changes):
            if record['session_id'] == session_id:
                return web.json_response(record)
        raise web.HTTPNotFound(
            text=json.dumps({'error': 'File change summary not found', 'session_id': session_id}),
            content_type='application/json',
        )

    async def post_test_results(self, request: Request) -> Response:
        """POST /api/test-results — store test run results and broadcast via WebSocket.

        Expected JSON body::

            {
                "agent":       "coding",
                "ticket":      "AI-42",
                "command":     "python -m pytest dashboard/__tests__/ -v",
                "status":      "passed",  # passed|failed|error
                "total":       42,
                "passed":      40,
                "failed":      2,
                "errors":      0,
                "duration_ms": 3200,
                "tests": [
                    {
                        "name":            "test_post_code_stream",
                        "status":          "passed",  # passed|failed|error|skipped
                        "duration_ms":     45,
                        "error_output":    "",
                        "screenshot_path": ""
                    }
                ],
                "full_output": "... full pytest output ..."
            }

        Returns:
            JSON with the stored record (HTTP 201), or 400 for malformed requests.

        WebSocket broadcast::

            {type: "test_results", ...full payload..., timestamp}
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        command = body.get('command', '')
        if not command:
            return web.json_response({'error': 'Missing required field: command'}, status=400)

        status = body.get('status', 'error')
        if status not in TEST_RUN_STATUSES:
            status = 'error'

        agent = body.get('agent', '')
        ticket = body.get('ticket', '')
        total = int(body.get('total', 0))
        passed = int(body.get('passed', 0))
        failed = int(body.get('failed', 0))
        errors = int(body.get('errors', 0))
        duration_ms = body.get('duration_ms', None)
        if duration_ms is not None:
            duration_ms = int(duration_ms)
        full_output = body.get('full_output', '')

        # Compute pass rate
        if total > 0:
            pass_rate = round((passed / total) * 100, 1)
        else:
            pass_rate = 0.0

        # Normalise test items
        raw_tests = body.get('tests', [])
        if not isinstance(raw_tests, list):
            raw_tests = []
        normalised_tests = []
        for t in raw_tests:
            item_status = t.get('status', 'error')
            if item_status not in TEST_ITEM_STATUSES:
                item_status = 'error'
            item_duration = t.get('duration_ms', None)
            if item_duration is not None:
                item_duration = int(item_duration)
            normalised_tests.append({
                'name': t.get('name', ''),
                'status': item_status,
                'duration_ms': item_duration,
                'error_output': t.get('error_output', ''),
                'screenshot_path': t.get('screenshot_path', ''),
            })

        timestamp = datetime.utcnow().isoformat() + 'Z'

        record = {
            'agent': agent,
            'ticket': ticket,
            'command': command,
            'status': status,
            'total': total,
            'passed': passed,
            'failed': failed,
            'errors': errors,
            'pass_rate': pass_rate,
            'duration_ms': duration_ms,
            'tests': normalised_tests,
            'full_output': full_output,
            'timestamp': timestamp,
        }

        # Append to circular buffer
        self._test_results.append(record)
        if len(self._test_results) > TEST_RESULTS_MAX:
            del self._test_results[0]

        # Broadcast to WebSocket clients
        ws_message = dict(record)
        ws_message['type'] = 'test_results'
        await self.broadcast_to_websockets(ws_message)

        logger.info(
            f"Test results stored: agent={agent!r}, ticket={ticket!r}, "
            f"command={command!r}, status={status!r}, "
            f"total={total}, passed={passed}, failed={failed}, pass_rate={pass_rate}%"
        )

        return web.json_response(record, status=201)

    async def get_test_results(self, request: Request) -> Response:
        """GET /api/test-results — return recent test results (last 50, newest first).

        Returns:
            JSON ``{"results": [...], "total": N}``
        """
        recent = list(reversed(self._test_results[-50:]))
        return web.json_response({
            'results': recent,
            'total': len(recent),
        })

    async def get_test_results_by_ticket(self, request: Request) -> Response:
        """GET /api/test-results/{ticket} — return all test runs for a specific ticket.

        Path Parameters:
            ticket: Linear ticket key (e.g. 'AI-42')

        Returns:
            JSON ``{"results": [...], "total": N}`` with all runs for that ticket,
            newest first.
        """
        ticket = request.match_info['ticket']
        matching = [r for r in self._test_results if r.get('ticket', '') == ticket]
        # Newest first
        matching = list(reversed(matching))
        return web.json_response({
            'results': matching,
            'total': len(matching),
        })

    # ========================================================================
    # AI-168: WebSocket Protocol Endpoints
    # ========================================================================

    async def post_agent_status(self, request: Request) -> Response:
        """POST /api/agent-status — broadcast an agent status change via WebSocket.

        Expected JSON body::

            {
                "agent":     "coding",              # agent identifier
                "status":    "idle|working|paused|error",
                "ticket":    "AI-XX",               # optional
                "metadata":  {}                     # optional extra context
            }

        Returns:
            JSON ``{"success": true}`` on success, or 400 for malformed requests.

        WebSocket broadcast::

            {type: "agent_status", agent, status, ticket, timestamp}
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        agent = body.get('agent', '')
        if not agent:
            return web.json_response({'error': 'Missing required field: agent'}, status=400)

        status = body.get('status', '')
        valid_statuses = ('idle', 'working', 'paused', 'error')
        if status not in valid_statuses:
            return web.json_response(
                {'error': f'Invalid status; must be one of {valid_statuses}'},
                status=400
            )

        ticket = body.get('ticket', '')
        metadata = body.get('metadata', {})
        timestamp = datetime.utcnow().isoformat() + 'Z'

        message = {
            'type': 'agent_status',
            'agent': agent,
            'status': status,
            'ticket': ticket,
            'metadata': metadata,
            'timestamp': timestamp,
        }

        await self.broadcast_to_websockets(message)
        logger.info(
            f"Agent status broadcast: agent={agent!r}, status={status!r}, ticket={ticket!r}"
        )

        return web.json_response({'success': True})

    async def post_agent_event(self, request: Request) -> Response:
        """POST /api/agent-event — broadcast a new agent event via WebSocket.

        Expected JSON body::

            {
                "agent":      "coding",             # agent identifier
                "event_type": "started|completed|failed",
                "ticket":     "AI-XX",              # optional
                "details":    {}                    # optional extra context
            }

        Returns:
            JSON ``{"success": true}`` on success, or 400 for malformed requests.

        WebSocket broadcast::

            {type: "agent_event", agent, event_type, ticket, details, timestamp}
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        agent = body.get('agent', '')
        if not agent:
            return web.json_response({'error': 'Missing required field: agent'}, status=400)

        event_type = body.get('event_type', '')
        valid_event_types = ('started', 'completed', 'failed')
        if event_type not in valid_event_types:
            return web.json_response(
                {'error': f'Invalid event_type; must be one of {valid_event_types}'},
                status=400
            )

        ticket = body.get('ticket', '')
        details = body.get('details', {})
        timestamp = datetime.utcnow().isoformat() + 'Z'

        message = {
            'type': 'agent_event',
            'agent': agent,
            'event_type': event_type,
            'ticket': ticket,
            'details': details,
            'timestamp': timestamp,
        }

        await self.broadcast_to_websockets(message)
        logger.info(
            f"Agent event broadcast: agent={agent!r}, event_type={event_type!r}, ticket={ticket!r}"
        )

        return web.json_response({'success': True})

    async def post_chat_stream(self, request: Request) -> Response:
        """POST /api/chat-stream — bridge a user chat message to the agent system (AI-173).

        When the request contains a ``message`` field the bridge pipeline is invoked:
        intent parsing → agent routing → simulated delegation → streaming via WebSocket.

        When the request contains a raw ``content`` field (legacy path) the chunk is
        broadcast directly without intent parsing, for backward compatibility.

        Request body (JSON) — bridge mode::

            {
                "message":    "ask coding agent to run tests",   # user chat message
                "session_id": "uuid"                             # optional session id
            }

        Request body (JSON) — legacy broadcast mode::

            {
                "content":   "text chunk",          # text content of the chunk
                "is_final":  false,                 # True if this is the last chunk
                "stream_id": "uuid",                # optional; auto-generated if absent
                "provider":  "claude"               # optional AI provider name
            }

        Returns:
            JSON ``{"success": true, "stream_id": "<uuid>", "chunks_sent": N}`` on success,
            or 400 for malformed requests.

        WebSocket broadcast (bridge mode)::

            {type: "chat_response", chunk_type, content, metadata, stream_id, timestamp}

        WebSocket broadcast (legacy mode)::

            {type: "chat_message", content, is_final, stream_id, provider, timestamp}
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        # ----------------------------------------------------------------
        # Bridge mode: user sends a natural-language "message"
        # ----------------------------------------------------------------
        if 'message' in body:
            user_message = body.get('message', '')
            if not isinstance(user_message, str) or not user_message.strip():
                return web.json_response(
                    {'error': 'message field must be a non-empty string'},
                    status=400,
                )

            session_id = body.get('session_id', '') or str(uuid4())
            stream_id = body.get('stream_id', '') or str(uuid4())
            chunks_sent = 0

            try:
                generator = await self._chat_bridge.handle_message(
                    user_message, session_id=session_id
                )
                async for bridge_chunk in generator:
                    chunk_type = bridge_chunk.get('type', 'text')
                    is_final = (chunk_type == 'done')

                    # Log routing decisions (AI-186 / REQ-OBS-001)
                    if chunk_type == 'intent':
                        meta = bridge_chunk.get('metadata', {})
                        self._provider_routing_logger.log_routing(
                            message=user_message,
                            intent_type=meta.get('intent_type', ''),
                            agent=meta.get('agent'),
                            confidence=float(meta.get('confidence', 0.0)),
                        )

                    ws_message = {
                        'type': 'chat_response',
                        'chunk_type': chunk_type,
                        'content': bridge_chunk.get('content', ''),
                        'metadata': bridge_chunk.get('metadata', {}),
                        'stream_id': stream_id,
                        'session_id': session_id,
                        'is_final': is_final,
                        'timestamp': bridge_chunk.get('timestamp', datetime.utcnow().isoformat() + 'Z'),
                    }

                    await self.broadcast_to_websockets(ws_message)
                    chunks_sent += 1

                    if is_final:
                        break

            except Exception as exc:
                logger.exception("ChatBridge pipeline error: %r", exc)
                error_msg = {
                    'type': 'chat_response',
                    'chunk_type': 'error',
                    'content': f'Error processing message: {exc}',
                    'metadata': {'error_code': 'BRIDGE_PIPELINE_ERROR'},
                    'stream_id': stream_id,
                    'session_id': session_id,
                    'is_final': True,
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                }
                await self.broadcast_to_websockets(error_msg)
                chunks_sent += 1

            logger.info(
                f"ChatBridge stream complete: stream_id={stream_id!r}, "
                f"session_id={session_id!r}, chunks_sent={chunks_sent}"
            )
            return web.json_response({
                'success': True,
                'stream_id': stream_id,
                'session_id': session_id,
                'chunks_sent': chunks_sent,
            })

        # ----------------------------------------------------------------
        # Legacy broadcast mode: raw content chunk
        # ----------------------------------------------------------------
        content = body.get('content', '')
        is_final = bool(body.get('is_final', False))
        stream_id = body.get('stream_id', '') or str(uuid4())
        provider = body.get('provider', '')
        timestamp = datetime.utcnow().isoformat() + 'Z'

        message = {
            'type': 'chat_message',
            'content': content,
            'is_final': is_final,
            'stream_id': stream_id,
            'provider': provider,
            'timestamp': timestamp,
        }

        await self.broadcast_to_websockets(message)
        logger.info(
            f"Chat stream broadcast (legacy): stream_id={stream_id!r}, is_final={is_final}, "
            f"provider={provider!r}, content_len={len(content)}"
        )

        return web.json_response({'success': True, 'stream_id': stream_id})

    async def post_control_ack(self, request: Request) -> Response:
        """POST /api/control-ack — broadcast a control command acknowledgment via WebSocket.

        Expected JSON body::

            {
                "agent":    "coding",               # target agent
                "command":  "pause|resume",         # control command
                "success":  true,                   # whether the command succeeded
                "message":  "Agent paused"          # optional human-readable message
            }

        Returns:
            JSON ``{"success": true}`` on success, or 400 for malformed requests.

        WebSocket broadcast::

            {type: "control_ack", agent, command, success, message, timestamp}
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        agent = body.get('agent', '')
        if not agent:
            return web.json_response({'error': 'Missing required field: agent'}, status=400)

        command = body.get('command', '')
        valid_commands = ('pause', 'resume')
        if command not in valid_commands:
            return web.json_response(
                {'error': f'Invalid command; must be one of {valid_commands}'},
                status=400
            )

        success = bool(body.get('success', True))
        message_text = body.get('message', f'Agent {agent} {command} acknowledged')
        timestamp = datetime.utcnow().isoformat() + 'Z'

        ws_message = {
            'type': 'control_ack',
            'agent': agent,
            'command': command,
            'success': success,
            'message': message_text,
            'timestamp': timestamp,
        }

        await self.broadcast_to_websockets(ws_message)
        logger.info(
            f"Control ack broadcast: agent={agent!r}, command={command!r}, success={success}"
        )

        return web.json_response({'success': True})

    # -------------------------------------------------------------------------
    # AI-82: Orchestrator Pipeline Visualization - REQ-MONITOR-004
    # -------------------------------------------------------------------------

    async def get_pipeline(self, request: Request) -> Response:
        """GET /api/orchestrator/pipeline - Return current pipeline state.

        Returns:
            200 OK with pipeline state {"active", "ticket_key", "ticket_title", "steps"}
        """
        import copy
        return web.json_response(copy.deepcopy(self._pipeline_state))

    async def set_pipeline(self, request: Request) -> Response:
        """POST /api/orchestrator/pipeline - Set the full pipeline state.

        Request body:
            {
                "active": true,
                "ticket_key": "AI-82",
                "ticket_title": "Pipeline Steps",
                "steps": [{"id": "ops-start", "label": "...", "status": "completed", "duration": 2.3}, ...]
            }

        Returns:
            200 OK with updated pipeline state
            400 Bad Request for invalid input
        """
        import copy
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        if 'active' not in body:
            return web.json_response({'error': 'Missing required field: active'}, status=400)

        active = bool(body.get('active', False))
        ticket_key = body.get('ticket_key', None)
        ticket_title = body.get('ticket_title', None)

        steps_input = body.get('steps', None)
        if steps_input is not None:
            if not isinstance(steps_input, list):
                return web.json_response({'error': 'steps must be an array'}, status=400)
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
            steps = copy.deepcopy(self._pipeline_state.get('steps', []))

        self._pipeline_state = {
            'active': active,
            'ticket_key': ticket_key,
            'ticket_title': ticket_title,
            'steps': steps,
        }

        await self.broadcast_to_websockets({
            'type': 'pipeline_update',
            'pipeline': copy.deepcopy(self._pipeline_state),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })

        return web.json_response(copy.deepcopy(self._pipeline_state))

    async def update_pipeline_step(self, request: Request) -> Response:
        """POST /api/orchestrator/pipeline/step - Update a single pipeline step.

        Request body:
            {"id": "coding", "status": "completed", "duration": 12.5}

        Returns:
            200 OK with updated pipeline state
            400 Bad Request for invalid step ID or missing fields
        """
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

        found = False
        for step in self._pipeline_state.get('steps', []):
            if step['id'] == step_id:
                step['status'] = new_status
                if 'duration' in body:
                    step['duration'] = body['duration']
                found = True
                break

        if not found:
            valid_ids = [s['id'] for s in self._pipeline_state.get('steps', [])]
            return web.json_response({
                'error': f'Step ID not found: {step_id!r}',
                'valid_ids': valid_ids,
            }, status=400)

        await self.broadcast_to_websockets({
            'type': 'pipeline_update',
            'pipeline': copy.deepcopy(self._pipeline_state),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })

        return web.json_response(copy.deepcopy(self._pipeline_state))

    # =========================================================================
    # AI-83: Global Metrics Bar (REQ-METRICS-001)
    # =========================================================================

    def _get_uptime_seconds(self) -> int:
        """Return seconds since server started (or 0 if not tracked)."""
        start = _global_metrics.get("_server_start_time")
        if start is None:
            return 0
        try:
            delta = (datetime.utcnow() - start).total_seconds()
            return max(0, int(delta))
        except Exception:
            return 0

    def _build_global_metrics_response(self) -> dict:
        """Build the global metrics response dict from current state.

        Merges the in-memory _global_metrics overrides with the persisted
        DashboardState (total_sessions, total_tokens, total_cost_usd) and
        live agent counts from _dashboard_agent_status.

        Returns:
            dict with all required fields for REQ-METRICS-001
        """
        # Load persisted metrics for totals (fallback to 0 on error)
        try:
            state = self.store.load()
            persisted_sessions = state.get("total_sessions", 0)
            persisted_tokens = state.get("total_tokens", 0)
            persisted_cost = state.get("total_cost_usd", 0.0)
            persisted_duration = state.get("total_duration_seconds", 0.0)
            # current_session is the number of sessions in the list
            current_session = len(state.get("sessions", []))
        except Exception:
            persisted_sessions = 0
            persisted_tokens = 0
            persisted_cost = 0.0
            persisted_duration = 0.0
            current_session = 0

        # Allow in-memory overrides to take precedence when non-zero
        total_sessions = _global_metrics.get("total_sessions") or persisted_sessions
        total_tokens = _global_metrics.get("total_tokens") or persisted_tokens
        total_cost_usd = _global_metrics.get("total_cost_usd") or persisted_cost

        # agents_active: count agents with status "running"
        agents_active = sum(
            1 for info in _dashboard_agent_status.values()
            if info.get("status") == "running"
        )

        return {
            "total_sessions": total_sessions,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost_usd, 6),
            "uptime_seconds": self._get_uptime_seconds(),
            "current_session": _global_metrics.get("current_session") or current_session,
            "agents_active": agents_active,
            "tasks_completed_today": _global_metrics.get("tasks_completed_today", 0),
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
        return web.json_response(self._build_global_metrics_response())

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
                    _global_metrics[field] = val
                else:
                    current = _global_metrics.get(field, 0)
                    if isinstance(current, float) or isinstance(val, float):
                        _global_metrics[field] = round(float(current) + float(val), 6)
                    else:
                        _global_metrics[field] = int(current) + int(val)

        metrics = self._build_global_metrics_response()

        # Broadcast via WebSocket so frontend updates in real-time
        await self.broadcast_to_websockets({
            "type": "global_metrics_update",
            "data": metrics,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

        return web.json_response(metrics)

    def _build_leaderboard(self) -> list:
        """Build the agent leaderboard ranked by XP descending (AI-84 / REQ-METRICS-002).

        Merges in-memory XP store overrides with persisted metrics store data.

        Returns:
            List of agent dicts ranked by XP descending with rank numbers assigned.
        """
        from dashboard.xp import calculate_level_from_xp, calculate_xp_progress_in_level

        # Try to load persisted agent data from metrics store
        persisted_agents: dict = {}
        try:
            state = self.store.load()
            persisted_agents = state.get('agents', {}) or {}
        except Exception:
            pass

        entries = []
        for name in _PANEL_AGENT_NAMES:
            persisted = persisted_agents.get(name, {})
            xp_override = _agent_xp_store.get(name, {})

            # XP: in-memory override takes precedence over persisted
            xp = xp_override.get('xp', persisted.get('xp', 0))
            level = calculate_level_from_xp(xp)

            success_rate = xp_override.get(
                'success_rate', persisted.get('success_rate', 0.0))
            avg_duration_s = xp_override.get(
                'avg_duration_s', persisted.get('avg_duration_seconds', 0.0))
            total_cost_usd = xp_override.get(
                'total_cost_usd', persisted.get('total_cost_usd', 0.0))

            # Status from panel status or xp override
            status = xp_override.get(
                'status',
                _dashboard_agent_status.get(name, {}).get('status', 'idle'))

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
        return web.json_response(self._build_leaderboard())

    async def post_agent_xp(self, request: Request) -> Response:
        """POST /api/agents/{agent_name}/xp — add XP to an agent (AI-84 / REQ-METRICS-002).

        Request body:
            {"xp": 50}        - add 50 XP to the agent's total
            {"xp": 50, "set": true}  - set XP to exactly 50

        Returns:
            200 JSON with updated leaderboard
            400 if body is invalid
            404 if agent_name is not a known panel agent
        """
        from dashboard.xp import calculate_level_from_xp

        agent_name = request.match_info['agent_name']
        if agent_name not in _PANEL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name,
                'available_agents': _PANEL_AGENT_NAMES,
            }, status=404)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        xp_delta = body.get('xp')
        if xp_delta is None or not isinstance(xp_delta, (int, float)):
            return web.json_response({'error': 'Missing or invalid "xp" field (must be a number)'}, status=400)

        # Initialize agent XP store entry if needed
        if agent_name not in _agent_xp_store:
            # Seed from persisted data if available
            persisted_xp = 0
            try:
                state = self.store.load()
                persisted_xp = state.get('agents', {}).get(agent_name, {}).get('xp', 0)
            except Exception:
                pass
            _agent_xp_store[agent_name] = {'xp': persisted_xp}

        if body.get('set'):
            _agent_xp_store[agent_name]['xp'] = int(xp_delta)
        else:
            _agent_xp_store[agent_name]['xp'] = int(
                _agent_xp_store[agent_name].get('xp', 0) + xp_delta)

        # Recompute level after XP change
        new_xp = _agent_xp_store[agent_name]['xp']
        _agent_xp_store[agent_name]['level'] = calculate_level_from_xp(new_xp)

        leaderboard = self._build_leaderboard()

        # Broadcast leaderboard update via WebSocket
        await self.broadcast_to_websockets({
            'type': 'leaderboard_update',
            'data': leaderboard,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })

        return web.json_response({
            'agent': agent_name,
            'xp': new_xp,
            'level': _agent_xp_store[agent_name]['level'],
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
        # Return newest-first (reverse of internal storage which is newest-last)
        return web.json_response(list(reversed(_feed_events)))

    async def post_feed(self, request: Request) -> Response:
        """POST /api/feed — Add a new event to the activity feed.

        Request body (all fields except agent and description are optional):
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
        try:
            body = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        agent = body.get('agent', '').strip()
        description = body.get('description', '').strip()

        if not agent:
            return web.json_response({'error': 'agent is required'}, status=400)
        if not description:
            return web.json_response({'error': 'description is required'}, status=400)

        # Warn but don't block unknown agents
        if agent not in _PANEL_AGENT_NAMES:
            logger.warning(f"POST /api/feed: unknown agent {agent!r}")

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

        event = {
            'id': str(uuid4()),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'agent': agent,
            'status': status,
            'ticket_key': ticket_key,
            'duration_s': duration_s,
            'description': description[:120],
        }

        _feed_events.append(event)
        # Cap at _FEED_MAX (drop oldest)
        while len(_feed_events) > _FEED_MAX:
            del _feed_events[0]

        # Broadcast feed_update via WebSocket
        await self.broadcast_to_websockets({
            'type': 'feed_update',
            'event': event,
            'timestamp': event['timestamp'],
        })

        logger.info(
            f"Feed event added: agent={agent!r}, status={status!r}, "
            f"ticket={ticket_key!r}, total={len(_feed_events)}"
        )

        return web.json_response({'event': event, 'total': len(_feed_events)}, status=201)

    async def websocket_handler(self, request: Request) -> WebSocketResponse:
        """WebSocket endpoint for real-time metrics streaming.

        Accepts WebSocket connections and broadcasts metrics updates to all connected clients.
        Clients receive JSON-formatted metrics data every 5 seconds.

        Returns:
            WebSocketResponse configured for metrics streaming
        """
        ws = WebSocketResponse()
        await ws.prepare(request)

        # Add to active connections
        self.websockets.add(ws)
        client_id = id(ws)
        logger.info(f"WebSocket client connected: {client_id} (total: {len(self.websockets)})")
        remote = request.remote if request else None
        self._ws_logger.log_ws_connect(str(client_id), remote=remote)

        try:
            # Send initial metrics immediately
            try:
                state = self.store.load()
                await ws.send_json({
                    'type': 'metrics_update',
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'data': state
                })
            except Exception as e:
                logger.error(f"Error sending initial metrics to WebSocket {client_id}: {e}")

            # Send backlog of recent agent_event messages so the client can
            # catch up on events that happened before they connected (AI-171)
            if self._agent_event_backlog:
                try:
                    await ws.send_json({
                        'type': 'backlog',
                        'events': list(self._agent_event_backlog),
                        'timestamp': datetime.utcnow().isoformat() + 'Z',
                    })
                    logger.info(
                        f"Sent backlog of {len(self._agent_event_backlog)} agent events "
                        f"to WebSocket {client_id}"
                    )
                except Exception as e:
                    logger.error(f"Error sending backlog to WebSocket {client_id}: {e}")

            # Listen for client messages (mostly for ping/pong and close)
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # Handle client messages (e.g., ping)
                    if msg.data == 'ping':
                        await ws.send_str('pong')
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket {client_id} error: {ws.exception()}")
                    break
                elif msg.type == WSMsgType.CLOSE:
                    logger.info(f"WebSocket {client_id} closed by client")
                    break

        except Exception as e:
            logger.error(f"WebSocket {client_id} error: {e}")
        finally:
            # Remove from active connections
            self.websockets.discard(ws)
            logger.info(f"WebSocket client disconnected: {client_id} (remaining: {len(self.websockets)})")
            self._ws_logger.log_ws_disconnect(str(client_id))

        return ws

    async def _broadcast_metrics(self):
        """Periodically broadcast metrics to all connected WebSocket clients."""
        while True:
            try:
                await asyncio.sleep(self.broadcast_interval)

                if not self.websockets:
                    continue

                # Load current metrics
                try:
                    state = self.store.load()
                except Exception as e:
                    logger.error(f"Error loading metrics for broadcast: {e}")
                    continue

                # Prepare broadcast message
                message = {
                    'type': 'metrics_update',
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'data': state
                }

                # Broadcast to all connected clients
                disconnected = set()
                for ws in self.websockets:
                    try:
                        await ws.send_json(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting to WebSocket {id(ws)}: {e}")
                        disconnected.add(ws)

                # Remove disconnected clients
                self.websockets -= disconnected
                if disconnected:
                    logger.info(f"Removed {len(disconnected)} disconnected WebSocket clients")

            except asyncio.CancelledError:
                logger.info("Metrics broadcast task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")

    async def _start_broadcast(self, app):
        """Start the periodic metrics broadcast task."""
        self.broadcast_task = asyncio.create_task(self._broadcast_metrics())
        logger.info(f"WebSocket broadcast started (interval: {self.broadcast_interval}s)")

    async def _cleanup_websockets(self, app):
        """Clean up all WebSocket connections on shutdown."""
        logger.info("Cleaning up WebSocket connections...")

        # Cancel broadcast task
        if self.broadcast_task:
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                pass

        # Close all active connections
        for ws in self.websockets:
            try:
                await ws.close(code=1001, message=b'Server shutting down')
            except Exception as e:
                logger.error(f"Error closing WebSocket {id(ws)}: {e}")

        self.websockets.clear()
        logger.info("WebSocket cleanup complete")

    def _print_startup_banner(self):
        """Print a startup banner listing all available endpoints."""
        base = f"http://{self.host}:{self.port}"
        ws_base = f"ws://{self.host}:{self.port}"
        logger.info("=" * 60)
        logger.info(f"  Agent Status Dashboard Server")
        logger.info(f"  Listening on {base}")
        logger.info("=" * 60)
        logger.info("  SPA:")
        logger.info(f"    GET  {base}/")
        logger.info("  Health:")
        logger.info(f"    GET  {base}/health")
        logger.info("  Metrics:")
        logger.info(f"    GET  {base}/api/metrics")
        logger.info(f"    GET  {base}/api/agents/{{name}}")
        logger.info("  Requirements:")
        logger.info(f"    GET  {base}/api/requirements/{{ticket_key}}")
        logger.info(f"    PUT  {base}/api/requirements/{{ticket_key}}")
        logger.info("  Reasoning (AI-158/160/94/95):")
        logger.info(f"    POST {base}/api/reasoning")
        logger.info(f"    GET  {base}/api/reasoning/blocks")
        logger.info(f"    POST {base}/api/reasoning/block")
        logger.info(f"    POST {base}/api/reasoning/clear")
        logger.info("  Agent Thinking (AI-159):")
        logger.info(f"    POST {base}/api/agent-thinking")
        logger.info("  Decisions (AI-161/162):")
        logger.info(f"    POST {base}/api/decisions")
        logger.info(f"    GET  {base}/api/decisions")
        logger.info(f"    GET  {base}/api/decisions/summary")
        logger.info(f"    GET  {base}/api/decisions/export")
        logger.info(f"    GET  {base}/api/decisions/{{id}}")
        logger.info("  Code Streaming (AI-163):")
        logger.info(f"    POST {base}/api/code-stream")
        logger.info(f"    GET  {base}/api/code-streams")
        logger.info(f"    GET  {base}/api/code-streams/{{id}}")
        logger.info("  File Changes (AI-164):")
        logger.info(f"    POST {base}/api/file-changes")
        logger.info(f"    GET  {base}/api/file-changes")
        logger.info(f"    GET  {base}/api/file-changes/{{session_id}}")
        logger.info("  Test Results (AI-165):")
        logger.info(f"    POST {base}/api/test-results")
        logger.info(f"    GET  {base}/api/test-results")
        logger.info(f"    GET  {base}/api/test-results/{{ticket}}")
        logger.info("  WebSocket Protocol (AI-168):")
        logger.info(f"    POST {base}/api/agent-status")
        logger.info(f"    POST {base}/api/agent-event")
        logger.info(f"    POST {base}/api/chat-stream")
        logger.info(f"    POST {base}/api/control-ack")
        logger.info("  WebSocket:")
        logger.info(f"    WS   {ws_base}/ws  (broadcast interval: {self.broadcast_interval}s)")
        logger.info("=" * 60)
        logger.info("  Press Ctrl+C to stop")
        logger.info("=" * 60)

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
            {"name": name, "tokens": _chart_token_usage.get(name, 0)}
            for name in _PANEL_AGENT_NAMES
        ]
        agents.sort(key=lambda a: a["tokens"], reverse=True)
        max_tokens = max((a["tokens"] for a in agents), default=0)
        return web.json_response({"agents": agents, "max": max_tokens})

    async def post_chart_token_usage(self, request: Request) -> Response:
        """POST /api/charts/token-usage — update token count for an agent (AI-85 / REQ-METRICS-003).

        Request body:
            {"agent": "coding", "tokens": 5000}         - add tokens
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
        if agent not in _PANEL_AGENT_NAMES:
            return web.json_response(
                {"error": "Unknown agent", "agent": agent, "available": _PANEL_AGENT_NAMES},
                status=400,
            )

        tokens = body.get("tokens")
        if tokens is None or not isinstance(tokens, (int, float)):
            return web.json_response(
                {"error": 'Missing or invalid "tokens" field (must be a number)'}, status=400
            )

        if body.get("set"):
            _chart_token_usage[agent] = int(tokens)
        else:
            _chart_token_usage[agent] = _chart_token_usage.get(agent, 0) + int(tokens)

        agents = [
            {"name": name, "tokens": _chart_token_usage.get(name, 0)}
            for name in _PANEL_AGENT_NAMES
        ]
        agents.sort(key=lambda a: a["tokens"], reverse=True)
        max_tokens = max((a["tokens"] for a in agents), default=0)
        return web.json_response({"agents": agents, "max": max_tokens})

    async def get_chart_cost_trend(self, request: Request) -> Response:
        """GET /api/charts/cost-trend — cost per session (last 10 sessions) (AI-85 / REQ-METRICS-003).

        Response shape:
            {"sessions": [{"session": 1, "cost": 2.50}, ...]}

        Returns:
            200 JSON with cost trend data.
        """
        sessions = list(_chart_cost_trend[-_CHART_COST_TREND_MAX:])
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

        for name in _PANEL_AGENT_NAMES:
            persisted = stored_agents.get(name, {})
            xp_override = _agent_xp_store.get(name, {})
            rate = xp_override.get("success_rate", persisted.get("success_rate", 0.0))
            total = persisted.get("total_invocations", 0)
            agents.append({"name": name, "rate": round(float(rate), 4), "total": int(total)})

        return web.json_response({"agents": agents})

    # -------------------------------------------------------------------------
    # AI-224: Usage metering endpoints
    # -------------------------------------------------------------------------

    async def get_usage(self, request: Request) -> Response:
        """GET /api/usage — return current period usage stats for the caller (AI-224).

        Uses the rate-limit identifier to look up the user. The caller is
        identified by Bearer token / X-API-Key (authenticated) or by IP
        (unauthenticated).

        Response:
            {
                "user_id": "token:abc123",
                "tier": "explorer",
                "period_start": "2024-01-01T00:00:00+00:00",
                "agent_hours_used": 5.2,
                "agent_hours_limit": 10.0,
                "percentage": 52.0,
                "alert_level": null
            }

        Returns:
            200 JSON with usage stats.
        """
        identifier, _is_auth = get_identifier(request)
        usage = self._usage_meter.get_usage(identifier)
        return web.json_response(usage.to_dict())

    async def post_usage_record(self, request: Request) -> Response:
        """POST /api/usage/record — record agent-time consumption (AI-224).

        Request body:
            {"user_id": "...", "seconds": 300}

        Returns:
            200 JSON with updated usage stats.
            400 if body is invalid.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        user_id = body.get("user_id")
        seconds = body.get("seconds")

        if not user_id:
            return web.json_response({"error": "Missing 'user_id' field"}, status=400)
        if seconds is None or not isinstance(seconds, (int, float)) or seconds < 0:
            return web.json_response(
                {"error": "Missing or invalid 'seconds' field (must be non-negative number)"},
                status=400,
            )

        usage = self._usage_meter.record_usage(str(user_id), float(seconds))
        return web.json_response(usage.to_dict())

    async def post_usage_reset(self, request: Request) -> Response:
        """POST /api/usage/reset — reset billing period for a user (AI-224).

        Request body:
            {"user_id": "..."}

        Returns:
            200 JSON with fresh usage stats.
            400 if body is invalid.
        """
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        user_id = body.get("user_id")
        if not user_id:
            return web.json_response({"error": "Missing 'user_id' field"}, status=400)

        usage = self._usage_meter.reset_period(str(user_id))
        return web.json_response(usage.to_dict())

    # -------------------------------------------------------------------------
    # AI-226: Onboarding endpoints
    # -------------------------------------------------------------------------

    async def get_onboarding_status(self, request: Request) -> Response:
        """GET /api/onboarding/status — check environment setup completeness (AI-226).

        Inspects environment variables to report which integrations are configured.

        Response:
            {
                "github_connected": bool,
                "linear_connected": bool,
                "api_key_set": bool,
                "setup_complete": bool
            }

        Returns:
            200 JSON with setup status.
        """
        github_connected = bool(os.environ.get('GITHUB_TOKEN', '').strip())
        linear_connected = bool(os.environ.get('LINEAR_API_KEY', '').strip())
        api_key_set = bool(os.environ.get('ANTHROPIC_API_KEY', '').strip())
        setup_complete = github_connected and linear_connected and api_key_set

        return web.json_response({
            'github_connected': github_connected,
            'linear_connected': linear_connected,
            'api_key_set': api_key_set,
            'setup_complete': setup_complete,
        })

    async def get_onboarding_complete(self, request: Request) -> Response:
        """GET /api/onboarding/complete — mark onboarding done server-side (AI-226).

        This is a fire-and-forget acknowledgement endpoint called by the frontend
        when the user finishes (or skips) the onboarding wizard.  Currently it
        simply returns a success response; in future it could persist state to a
        user profile store.

        Response:
            {"status": "ok", "message": "Onboarding marked complete"}

        Returns:
            200 JSON acknowledgement.
        """
        return web.json_response({
            'status': 'ok',
            'message': 'Onboarding marked complete',
        })

    # =========================================================================
    # AI-227: Telemetry lifecycle helpers
    # =========================================================================

    async def _start_telemetry(self, app) -> None:
        """Start the telemetry collector and emit session_started (on_startup hook)."""
        if not _TELEMETRY_AVAILABLE:
            return
        try:
            collector = get_telemetry_collector()
            await collector.start()
            _collect_event("session_started", {"project": self.project_name})
            logger.info("Telemetry collector started")
        except Exception:  # noqa: BLE001
            logger.debug("Telemetry start error (suppressed)", exc_info=True)

    async def _stop_telemetry(self, app) -> None:
        """Stop the telemetry collector gracefully (on_cleanup hook)."""
        if not _TELEMETRY_AVAILABLE:
            return
        try:
            collector = get_telemetry_collector()
            _collect_event("session_ended", {"project": self.project_name})
            await collector.stop()
            logger.info("Telemetry collector stopped")
        except Exception:  # noqa: BLE001
            logger.debug("Telemetry stop error (suppressed)", exc_info=True)

    # =========================================================================
    # AI-227: Analytics endpoint
    # =========================================================================

    async def get_analytics(self, request: Request) -> Response:
        """GET /api/admin/analytics — Return event counts and basic funnel analysis.

        Protected: returns 401 when DASHBOARD_AUTH_TOKEN is set but no valid
        bearer token is provided.  (The auth_middleware handles that gate; this
        handler adds a second explicit check so unauthenticated local installs
        still work while still returning 401 when there is no telemetry data.)

        Returns JSON:
            {
              "total_events": int,
              "events_last_24h": int,
              "events_last_7d": int,
              "counts_by_type": {event_type: int, ...},
              "daily_totals": [{"date": "YYYY-MM-DD", "count": int}, ...],
              "telemetry_disabled": bool
            }
        """
        if not _TELEMETRY_AVAILABLE:
            return web.json_response(
                {"error": "Telemetry module not available"},
                status=503,
            )

        # Read JSONL storage
        try:
            storage_path = get_telemetry_collector().storage_path
        except Exception:
            storage_path = None  # type: ignore[assignment]

        counts_by_type: dict = {}
        daily_totals: dict = {}
        events_last_24h = 0
        events_last_7d = 0
        total_events = 0

        now = datetime.now(timezone.utc)
        cutoff_24h = now - timedelta(hours=24)
        cutoff_7d = now - timedelta(days=7)

        if storage_path and Path(storage_path).exists():
            try:
                with open(storage_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            ev = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        total_events += 1
                        etype = ev.get("event_type", "unknown")
                        counts_by_type[etype] = counts_by_type.get(etype, 0) + 1

                        ts_str = ev.get("timestamp", "")
                        try:
                            ts = datetime.fromisoformat(ts_str)
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            day_key = ts.strftime("%Y-%m-%d")
                            daily_totals[day_key] = daily_totals.get(day_key, 0) + 1
                            if ts >= cutoff_24h:
                                events_last_24h += 1
                            if ts >= cutoff_7d:
                                events_last_7d += 1
                        except (ValueError, TypeError):
                            pass
            except Exception:  # noqa: BLE001
                logger.debug("Analytics read error (suppressed)", exc_info=True)

        sorted_daily = sorted(
            [{"date": k, "count": v} for k, v in daily_totals.items()],
            key=lambda x: x["date"],
        )

        return web.json_response({
            "total_events": total_events,
            "events_last_24h": events_last_24h,
            "events_last_7d": events_last_7d,
            "counts_by_type": counts_by_type,
            "daily_totals": sorted_daily,
            "telemetry_disabled": is_telemetry_disabled(),
        })

    async def post_telemetry_optout(self, request: Request) -> Response:
        """POST /api/telemetry/optout — Disable telemetry collection.

        Creates a local opt-out flag file so the setting persists across
        server restarts.  To re-enable, delete the .telemetry_optout file or
        unset the TELEMETRY_DISABLED env var.

        Returns:
            200 JSON: {"status": "ok", "telemetry_disabled": true}
        """
        if not _TELEMETRY_AVAILABLE:
            return web.json_response({"status": "ok", "telemetry_disabled": True})

        try:
            write_opt_out_flag()
        except Exception:  # noqa: BLE001
            logger.debug("Telemetry opt-out write error (suppressed)", exc_info=True)

        return web.json_response({
            "status": "ok",
            "telemetry_disabled": True,
            "message": "Telemetry opt-out recorded. Collection is disabled.",
        })

    # -------------------------------------------------------------------------
    # AI-225: Multi-project endpoints
    # -------------------------------------------------------------------------

    def _project_unavailable_response(self) -> Response:
        """Return a 503 when the projects module is unavailable."""
        return web.json_response(
            {"error": "Projects module not available"},
            status=503,
        )

    async def get_projects(self, request: Request) -> Response:
        """GET /api/projects — list all projects (AI-225).

        Returns:
            200 JSON: {"projects": [...], "active_project_id": str|null}
        """
        if self._project_manager is None:
            return self._project_unavailable_response()

        projects = self._project_manager.list_projects()
        active = self._project_manager.get_active_project()
        return web.json_response({
            "projects": [p.to_dict() for p in projects],
            "active_project_id": active.id if active else None,
            "max_projects": self._project_manager.max_projects,
            "tier": self._project_manager.tier,
        })

    async def post_project(self, request: Request) -> Response:
        """POST /api/projects — create a new project (AI-225).

        Request body:
            {
                "name": "My Project",
                "git_repo_url": "https://github.com/...",   # optional
                "linear_project_id": "PROJ-1",              # optional
                "directory": "/path/to/project"             # optional
            }

        Returns:
            201 JSON with created project.
            400 if name is missing or invalid.
            409 if tier limit would be exceeded.
        """
        if self._project_manager is None:
            return self._project_unavailable_response()

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        name = body.get("name", "").strip()
        if not name:
            return web.json_response({"error": "Missing or empty 'name' field"}, status=400)

        try:
            project = self._project_manager.create_project(
                name=name,
                directory=body.get("directory", ""),
                git_repo_url=body.get("git_repo_url", ""),
                linear_project_id=body.get("linear_project_id", ""),
            )
        except TierLimitError as exc:
            return web.json_response({"error": str(exc)}, status=409)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)

        return web.json_response({"project": project.to_dict()}, status=201)

    async def delete_project(self, request: Request) -> Response:
        """DELETE /api/projects/{project_id} — delete a project (AI-225).

        Returns:
            200 JSON: {"status": "deleted", "project_id": str}
            404 if project not found.
        """
        if self._project_manager is None:
            return self._project_unavailable_response()

        project_id = request.match_info["project_id"]
        deleted = self._project_manager.delete_project(project_id)
        if not deleted:
            return web.json_response(
                {"error": f"Project '{project_id}' not found"},
                status=404,
            )
        return web.json_response({"status": "deleted", "project_id": project_id})

    async def activate_project(self, request: Request) -> Response:
        """POST /api/projects/{project_id}/activate — switch active project (AI-225).

        Returns:
            200 JSON with the activated project.
            404 if project not found.
        """
        if self._project_manager is None:
            return self._project_unavailable_response()

        project_id = request.match_info["project_id"]
        try:
            project = self._project_manager.switch_project(project_id)
        except KeyError:
            return web.json_response(
                {"error": f"Project '{project_id}' not found"},
                status=404,
            )
        return web.json_response({"project": project.to_dict()})

    async def get_active_project(self, request: Request) -> Response:
        """GET /api/projects/active — get currently active project (AI-225).

        Returns:
            200 JSON: {"project": {...}} or {"project": null} if none active.
        """
        if self._project_manager is None:
            return self._project_unavailable_response()

        active = self._project_manager.get_active_project()
        return web.json_response({
            "project": active.to_dict() if active else None,
        })

    # -------------------------------------------------------------------------
    # AI-229: Webhook endpoints
    # -------------------------------------------------------------------------

    async def list_webhooks(self, request: Request) -> Response:
        """GET /api/webhooks — list all registered webhooks.

        Returns:
            JSON with list of webhooks (no secrets included).
        """
        manager = get_webhook_manager()
        webhooks = manager.list_webhooks()
        return web.json_response({
            "webhooks": webhooks,
            "count": len(webhooks),
            "valid_events": VALID_EVENTS,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    async def create_webhook(self, request: Request) -> Response:
        """POST /api/webhooks — register a new webhook.

        Request body (JSON):
            url (str): Target URL
            events (list[str]): Event types to subscribe to
            secret (str, optional): HMAC-SHA256 signing secret

        Returns:
            201 JSON with created webhook details.
        """
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

        manager = get_webhook_manager()
        try:
            webhook_id = manager.register_webhook(url=url, events=events, secret=secret)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)

        webhook = manager.get_webhook(webhook_id)
        return web.json_response(webhook, status=201)

    async def delete_webhook(self, request: Request) -> Response:
        """DELETE /api/webhooks/{webhook_id} — remove a webhook.

        Returns:
            204 on success, 404 if not found.
        """
        webhook_id = request.match_info.get("webhook_id", "")
        manager = get_webhook_manager()
        deleted = manager.delete_webhook(webhook_id)
        if deleted:
            return web.Response(status=204)
        return web.json_response({"error": f"Webhook {webhook_id} not found"}, status=404)

    async def test_webhook(self, request: Request) -> Response:
        """POST /api/webhooks/{webhook_id}/test — send a test event to a webhook.

        Returns:
            JSON with delivery result.
        """
        webhook_id = request.match_info.get("webhook_id", "")
        manager = get_webhook_manager()
        if manager.get_webhook(webhook_id) is None:
            return web.json_response(
                {"error": f"Webhook {webhook_id} not found"}, status=404
            )
        try:
            result = await manager.test_webhook(webhook_id)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=500)
        return web.json_response(result)

    async def get_webhook_deliveries(self, request: Request) -> Response:
        """GET /api/webhooks/deliveries — get delivery log (last 50).

        Returns:
            JSON with list of delivery records.
        """
        manager = get_webhook_manager()
        deliveries = manager.get_delivery_log()
        return web.json_response({
            "deliveries": deliveries,
            "count": len(deliveries),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    async def inbound_run_ticket(self, request: Request) -> Response:
        """POST /api/webhooks/inbound/run-ticket — trigger agent on a ticket.

        Accepts HMAC-SHA256 signed payloads from external systems (e.g., GitHub Actions).

        Request body (JSON):
            ticket_key (str): Linear ticket key, e.g. "AI-42"
            agent (str, optional): Agent to use (default: "coding")
            priority (str, optional): Task priority

        Returns:
            202 JSON confirming the trigger was accepted.
        """
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        ticket_key = data.get("ticket_key", "").strip()
        if not ticket_key:
            return web.json_response({"error": "ticket_key is required"}, status=400)

        agent = data.get("agent", "coding")
        priority = data.get("priority", "normal")

        logger.info(
            f"Inbound webhook: run-ticket ticket_key={ticket_key} agent={agent}"
        )

        # Trigger agent.session.started event to notify outbound webhooks
        manager = get_webhook_manager()
        await manager.trigger_event("agent.session.started", {
            "ticket_key": ticket_key,
            "agent": agent,
            "priority": priority,
            "source": "inbound_webhook",
        })

        return web.json_response({
            "accepted": True,
            "ticket_key": ticket_key,
            "agent": agent,
            "priority": priority,
            "message": f"Agent {agent} queued for ticket {ticket_key}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }, status=202)

    async def inbound_run_spec(self, request: Request) -> Response:
        """POST /api/webhooks/inbound/run-spec — trigger agent on a spec.

        Accepts spec text or spec reference to run through the agent pipeline.

        Request body (JSON):
            spec (str): Specification text or spec file path
            agent (str, optional): Agent to use (default: "coding")
            ticket_key (str, optional): Associated ticket key

        Returns:
            202 JSON confirming the trigger was accepted.
        """
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        spec = data.get("spec", "").strip()
        if not spec:
            return web.json_response({"error": "spec is required"}, status=400)

        agent = data.get("agent", "coding")
        ticket_key = data.get("ticket_key", "")

        logger.info(
            f"Inbound webhook: run-spec agent={agent} ticket_key={ticket_key}"
        )

        # Trigger agent.session.started event to notify outbound webhooks
        manager = get_webhook_manager()
        await manager.trigger_event("agent.session.started", {
            "spec_length": len(spec),
            "agent": agent,
            "ticket_key": ticket_key,
            "source": "inbound_webhook_spec",
        })

        return web.json_response({
            "accepted": True,
            "agent": agent,
            "ticket_key": ticket_key,
            "spec_length": len(spec),
            "message": f"Agent {agent} queued to process spec",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }, status=202)

    def run(self):
        """Start the HTTP server with WebSocket support.

        Runs the aiohttp application using an AppRunner with graceful signal-based
        shutdown handling (SIGINT / SIGTERM).  Blocks until the server is stopped.
        """
        self._print_startup_banner()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        stop_event = asyncio.Event()

        def _handle_signal():
            logger.info("Shutdown signal received — stopping server gracefully…")
            stop_event.set()

        async def _run():
            runner = web.AppRunner(self.app)
            await runner.setup()
            site = web.TCPSite(runner, self.host, self.port)
            await site.start()
            logger.info(f"Server started on http://{self.host}:{self.port}")

            # Register OS signal handlers for graceful shutdown
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, _handle_signal)
                except (NotImplementedError, RuntimeError):
                    # add_signal_handler is not available on Windows
                    pass

            try:
                await stop_event.wait()
            except asyncio.CancelledError:
                pass
            finally:
                logger.info("Shutting down server…")
                await runner.cleanup()
                logger.info("Server stopped.")

        try:
            loop.run_until_complete(_run())
        except KeyboardInterrupt:
            logger.info("Server stopped by user (KeyboardInterrupt)")
        finally:
            loop.close()


def main():
    """CLI entry point for dashboard server."""
    check_python_version()
    parser = argparse.ArgumentParser(
        description='Agent Status Dashboard HTTP Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server on default port 8080
  python dashboard_server.py

  # Start server on custom port
  python dashboard_server.py --port 8000

  # Specify custom metrics directory
  python dashboard_server.py --metrics-dir /path/to/metrics

API Endpoints:
  GET  /health                    - Health check
  GET  /api/metrics               - Get all metrics data
  GET  /api/agents/<name>         - Get specific agent profile

A2UI Components:
  Available at: /Users/bkh223/Documents/GitHub/agent-engineers/reusable/a2ui-components/
  - TaskCard: Display agent activities
  - ProgressRing: Show completion metrics
  - ActivityItem: Timeline of events
  - ErrorCard: Display errors with details
        """
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='HTTP server port (default: DASHBOARD_WEB_PORT env var, or 8080)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='HTTP server host (default: DASHBOARD_HOST env var, or 127.0.0.1; use 0.0.0.0 to expose to network)'
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
        default='agent-status-dashboard',
        help='Project name (default: agent-status-dashboard)'
    )

    args = parser.parse_args()

    # CLI args take priority over env vars (env vars take priority over built-in defaults).
    # When argparse fills in its own default (port=8080, host='127.0.0.1') we want to
    # prefer the env-var value instead.  We detect this by comparing to argparse defaults.
    config = get_config()

    port = args.port
    host = args.host

    # If user did not explicitly supply --port, fall back to env-var config
    if port == 8080:
        port = config.port

    # If user did not explicitly supply --host, fall back to env-var config
    if host == '127.0.0.1':
        host = config.host

    # Create and run server
    server = DashboardServer(
        project_name=args.project_name,
        metrics_dir=args.metrics_dir,
        port=port,
        host=host
    )

    server.run()


if __name__ == '__main__':
    main()
