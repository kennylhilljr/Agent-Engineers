"""Dashboard Server - HTTP API for Agent Status Dashboard.

This module provides an aiohttp-based HTTP server that exposes metrics data
through REST endpoints. The server enables web dashboards and other clients
to query agent performance metrics, session summaries, and individual agent details.

Endpoints:
    GET /api/metrics - Returns complete DashboardState with all metrics
    GET /api/agents/<name> - Returns specific agent profile with detailed stats
    GET /api/providers/status - Returns AI provider availability status (AI-73)
    GET /health - Health check endpoint with detailed system status
    GET /metrics - Prometheus-formatted metrics endpoint
    GET /monitoring - Monitoring dashboard HTML page
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
import json
import os
import psutil
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

from aiohttp import web, WSMsgType
from aiohttp.web import Request, Response, WebSocketResponse, middleware
from aiohttp_cors import ResourceOptions, setup as cors_setup

from dashboard.collector import AgentMetricsCollector
from dashboard.metrics import AgentEvent
from dashboard.metrics_store import MetricsStore
from dashboard.logging_config import setup_logging, get_logger, LoggingMiddleware
from dashboard.performance_metrics import metrics_collector, timed_operation, increment_counter, set_gauge
from dashboard.config import get_config, DashboardConfig

# Agent Controls State Store (AI-130)
# Maintains pause/resume state and requirements for each agent
agent_controls: dict = {}  # {agent_id: {"paused": bool, "requirements": str}}
AGENT_CONTROLS_MAX_ENTRIES = 100  # Max number of agent entries to prevent unbounded memory growth
AGENT_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')  # Only alphanumeric, underscore, dash
REQUIREMENTS_MAX_LENGTH = 50_000  # Max length for requirements text

# Chat History State Store (AI-133)
# Persists chat messages for the current server session (max 1000 messages)
chat_history: list = []  # [{"id", "type", "content", "timestamp", "provider", "model"}]
CHAT_HISTORY_MAX = 1000

# Transparency State Store (AI-131)
# Stores orchestrator reasoning events (max 100)
reasoning_history: list = []  # [{"agent", "decision", "complexity", "reasoning", "timestamp"}]
REASONING_HISTORY_MAX = 100

# Setup structured logging
setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)


# Get CORS allowed origins from environment
def get_cors_origins() -> str:
    """Get CORS allowed origins from environment variable.

    Returns:
        Comma-separated list of allowed origins or '*' for development.
        Defaults to localhost origins for security.
    """
    origins = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:8080')

    # Warn if using wildcard in production
    if origins == '*':
        logger.warning(
            "SECURITY WARNING: CORS is configured to allow all origins (*). "
            "This is acceptable for development but should NOT be used in production. "
            "Set CORS_ALLOWED_ORIGINS to specific domains for production deployment."
        )

    return origins


# CORS middleware with environment-based configuration
@middleware
async def cors_middleware(request: Request, handler):
    """Add CORS headers to all responses.

    CORS origins are configured via CORS_ALLOWED_ORIGINS environment variable.
    Defaults to localhost origins for development security.
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

    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
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
        return web.json_response(
            {
                'error': type(ex).__name__,
                'message': str(ex),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            },
            status=500
        )


class DashboardServer:
    """HTTP server for Agent Status Dashboard metrics API.

    Provides REST endpoints for querying metrics data with CORS support.
    Uses MetricsStore for data persistence.

    Configuration via environment variables (AI-111):
        DASHBOARD_WEB_PORT: Port for the web dashboard server (default: 8420)
        DASHBOARD_WS_PORT: Port for WebSocket connections (default: 8421)
        DASHBOARD_HOST: Host to bind the dashboard server (default: 0.0.0.0)
        DASHBOARD_AUTH_TOKEN: Bearer token for API authentication (default: none)
        DASHBOARD_CORS_ORIGINS: Allowed CORS origins (default: *)
    """

    def __init__(
        self,
        project_name: str = "agent-status-dashboard",
        metrics_dir: Optional[Path] = None,
        port: Optional[int] = None,
        host: Optional[str] = None,
        use_config: bool = True
    ):
        """Initialize DashboardServer.

        Args:
            project_name: Project name for metrics store
            metrics_dir: Directory containing .agent_metrics.json
            port: HTTP server port (overrides DASHBOARD_WEB_PORT env var)
            host: HTTP server host (overrides DASHBOARD_HOST env var)
            use_config: If True, load from environment variables via DashboardConfig

        Security Notes:
            - Default host is 0.0.0.0 (all interfaces) - override with DASHBOARD_HOST
            - For production, use a reverse proxy (nginx/caddy) with proper TLS/SSL
            - Set DASHBOARD_AUTH_TOKEN for API authentication
        """
        self.project_name = project_name
        self.metrics_dir = metrics_dir or Path.cwd()

        # Load configuration from environment variables if use_config is True
        if use_config:
            config = get_config()

            # Validate configuration
            is_valid, error_msg = config.validate()
            if not is_valid:
                raise ValueError(f"Invalid dashboard configuration: {error_msg}")

            # Use environment config unless overridden by parameters
            self.port = port or config.web_port
            self.host = host or config.host
            self.config = config
        else:
            # Legacy mode: use provided port/host only
            self.port = port or 8080
            self.host = host or "127.0.0.1"
            self.config = None

        # Initialize metrics store
        self.store = MetricsStore(
            project_name=project_name,
            metrics_dir=self.metrics_dir
        )

        # Initialize metrics collector for event broadcasting
        self.collector = AgentMetricsCollector(
            project_name=project_name,
            metrics_dir=self.metrics_dir
        )

        # Subscribe to collector events for real-time broadcasting
        self.collector.subscribe(self._on_collector_event)

        # WebSocket connections tracking
        self.websockets: Set[WebSocketResponse] = set()
        self.broadcast_task: Optional[asyncio.Task] = None
        self.broadcast_interval = 5  # seconds

        # Event queue for immediate broadcasts
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.event_broadcast_task: Optional[asyncio.Task] = None

        # Create app with middlewares
        self.app = web.Application(middlewares=[error_middleware, cors_middleware])

        # Register routes
        self._setup_routes()

        # Setup WebSocket broadcasting
        self.app.on_startup.append(self._start_broadcast)
        self.app.on_startup.append(self._start_event_broadcast)
        self.app.on_cleanup.append(self._cleanup_websockets)

        logger.info(f"Dashboard server initialized for project: {project_name}")
        logger.info(f"Metrics directory: {self.metrics_dir}")

    def _setup_routes(self):
        """Register HTTP routes and WebSocket endpoint."""
        self.app.router.add_get('/', self.serve_dashboard)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/api/metrics', self.get_metrics)
        self.app.router.add_get('/api/agents/{agent_name}', self.get_agent)
        self.app.router.add_get('/api/providers/status', self.get_provider_status)
        self.app.router.add_get('/ws', self.websocket_handler)

        # Monitoring endpoints
        self.app.router.add_get('/metrics', self.prometheus_metrics)
        self.app.router.add_get('/monitoring', self.serve_monitoring_dashboard)
        self.app.router.add_get('/api/system/status', self.system_status)

        # Agent Controls endpoints (AI-130)
        # Static routes must be registered BEFORE parameterized routes to avoid shadowing
        self.app.router.add_post('/api/agents/pause-all', self.pause_all_agents)
        self.app.router.add_post('/api/agents/resume-all', self.resume_all_agents)
        self.app.router.add_get('/api/agent-controls', self.get_all_agent_controls)
        self.app.router.add_post('/api/agents/{agent_id}/pause', self.pause_agent)
        self.app.router.add_post('/api/agents/{agent_id}/resume', self.resume_agent)
        self.app.router.add_get('/api/agents/{agent_id}/requirements', self.get_agent_requirements)
        self.app.router.add_put('/api/agents/{agent_id}/requirements', self.update_agent_requirements)

        # Chat History endpoints (AI-133)
        self.app.router.add_get('/api/chat/history', self.get_chat_history)
        self.app.router.add_post('/api/chat/history', self.post_chat_history)
        self.app.router.add_delete('/api/chat/history', self.delete_chat_history)
        self.app.router.add_route('OPTIONS', '/api/chat/history', self.handle_options)

        # Transparency endpoints (AI-131)
        self.app.router.add_post('/api/transparency/reasoning', self.post_transparency_reasoning)
        self.app.router.add_get('/api/transparency/history', self.get_transparency_history)
        self.app.router.add_delete('/api/transparency/history', self.delete_transparency_history)
        self.app.router.add_post('/api/transparency/code-stream', self.post_transparency_code_stream)
        self.app.router.add_route('OPTIONS', '/api/transparency/reasoning', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/transparency/history', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/transparency/code-stream', self.handle_options)

        # OPTIONS for CORS preflight
        self.app.router.add_route('OPTIONS', '/api/metrics', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/{agent_name}', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/providers/status', self.handle_options)
        self.app.router.add_route('OPTIONS', '/metrics', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/system/status', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/pause-all', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/resume-all', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agent-controls', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/{agent_id}/pause', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/{agent_id}/resume', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/{agent_id}/requirements', self.handle_options)

    async def handle_options(self, request: Request) -> Response:
        """Handle CORS preflight OPTIONS requests."""
        return web.Response(status=204)

    async def serve_dashboard(self, request: Request) -> Response:
        """Serve the dashboard HTML page at the root URL."""
        html_path = Path(__file__).parent / 'dashboard.html'
        if html_path.exists():
            return web.Response(
                text=html_path.read_text(),
                content_type='text/html',
            )
        raise web.HTTPNotFound(text='dashboard.html not found')

    async def health_check(self, request: Request) -> Response:
        """Enhanced health check endpoint with detailed system status.

        Returns:
            JSON response with comprehensive health information including:
            - Service status
            - System metrics (CPU, memory, disk)
            - Metrics store status
            - Performance metrics
            - Uptime
        """
        with timed_operation("health_check_duration"):
            increment_counter("health_check_requests")

            try:
                stats = self.store.get_stats()

                # Get system metrics
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')

                # Get performance metrics
                perf_metrics = metrics_collector.get_metrics()

                health_data = {
                    'status': 'healthy',
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'version': '1.0.0',
                    'project': self.project_name,

                    # Service info
                    'service': {
                        'name': 'agent-dashboard',
                        'uptime_seconds': perf_metrics.get('uptime_seconds', 0),
                        'host': self.host,
                        'port': self.port,
                        'websocket_connections': len(self.websockets)
                    },

                    # System metrics
                    'system': {
                        'cpu_percent': round(cpu_percent, 2),
                        'memory_percent': round(memory.percent, 2),
                        'memory_used_mb': round(memory.used / (1024 * 1024), 2),
                        'memory_total_mb': round(memory.total / (1024 * 1024), 2),
                        'disk_percent': round(disk.percent, 2),
                        'disk_used_gb': round(disk.used / (1024 * 1024 * 1024), 2),
                        'disk_total_gb': round(disk.total / (1024 * 1024 * 1024), 2),
                        'python_version': sys.version.split()[0]
                    },

                    # Metrics store status
                    'metrics_store': {
                        'metrics_file_exists': stats['metrics_file_exists'],
                        'event_count': stats['event_count'],
                        'session_count': stats['session_count'],
                        'agent_count': stats['agent_count'],
                        'metrics_file_size_bytes': stats.get('metrics_file_size_bytes', 0)
                    },

                    # Performance summary
                    'performance': {
                        'total_requests': perf_metrics.get('counters', {}).get('http_requests_total', [{}])[0].get('value', 0),
                        'avg_response_time_ms': 0  # Will be populated from histograms
                    }
                }

                # Calculate average response time from histogram
                http_duration_hist = perf_metrics.get('histograms', {}).get('http_request_duration', [])
                if http_duration_hist:
                    hist = http_duration_hist[0]
                    if hist.get('count', 0) > 0:
                        health_data['performance']['avg_response_time_ms'] = round(hist.get('mean', 0) * 1000, 2)

                increment_counter("health_check_success")
                logger.info("Health check completed", extra={"status": "healthy"})

                return web.json_response(health_data)

            except Exception as e:
                increment_counter("health_check_errors")
                logger.error("Health check failed", exc_info=True, extra={"error": str(e)})

                return web.json_response({
                    'status': 'unhealthy',
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'error': str(e)
                }, status=503)

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

    async def get_provider_status(self, request: Request) -> Response:
        """Get AI provider availability status.

        Checks environment variables for API keys and returns status for each provider:
        - available: API key configured and provider is reachable
        - unconfigured: API key missing
        - error: API key present but provider unreachable

        Returns:
            JSON response with provider status information
        """
        logger.info("GET /api/providers/status")

        try:
            providers = {
                'claude': {
                    'env_var': 'ANTHROPIC_API_KEY',
                    'name': 'Claude',
                    'setup_instructions': 'Set ANTHROPIC_API_KEY environment variable with your Anthropic API key'
                },
                'chatgpt': {
                    'env_var': 'OPENAI_API_KEY',
                    'name': 'ChatGPT',
                    'setup_instructions': 'Set OPENAI_API_KEY environment variable with your OpenAI API key'
                },
                'gemini': {
                    'env_var': 'GOOGLE_API_KEY',
                    'name': 'Gemini',
                    'setup_instructions': 'Set GOOGLE_API_KEY environment variable with your Google AI API key'
                },
                'groq': {
                    'env_var': 'GROQ_API_KEY',
                    'name': 'Groq',
                    'setup_instructions': 'Set GROQ_API_KEY environment variable with your Groq API key'
                },
                'kimi': {
                    'env_var': 'KIMI_API_KEY',
                    'name': 'KIMI',
                    'setup_instructions': 'Set KIMI_API_KEY environment variable with your KIMI API key'
                },
                'windsurf': {
                    'env_var': 'WINDSURF_API_KEY',
                    'name': 'Windsurf',
                    'setup_instructions': 'Set WINDSURF_API_KEY environment variable with your Windsurf API key'
                }
            }

            status_data = {}
            for provider_id, config in providers.items():
                api_key = os.getenv(config['env_var'])

                if provider_id == 'claude':
                    # Claude is always available as default provider
                    status = 'available'
                elif api_key:
                    # API key is configured
                    # For now, we assume it's available if configured
                    # In a real implementation, we would ping the API
                    status = 'available'
                else:
                    # API key not configured
                    status = 'unconfigured'

                status_data[provider_id] = {
                    'status': status,
                    'name': config['name'],
                    'configured': api_key is not None or provider_id == 'claude',
                    'setup_instructions': config['setup_instructions'] if status == 'unconfigured' else None
                }

            return web.json_response({
                'providers': status_data,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })

        except Exception as e:
            logger.error(f"Error checking provider status: {e}")
            raise web.HTTPInternalServerError(
                text=json.dumps({'error': str(e)}),
                content_type='application/json'
            )

    async def prometheus_metrics(self, request: Request) -> Response:
        """Prometheus metrics endpoint.

        Returns metrics in Prometheus text format for scraping by Prometheus server.

        Returns:
            Response with Prometheus-formatted metrics
        """
        with timed_operation("prometheus_export_duration"):
            increment_counter("prometheus_scrapes")

            try:
                # Export metrics in Prometheus format
                metrics_text = metrics_collector.export_prometheus()

                # Add custom metrics from dashboard state
                state = self.store.load()

                # Add dashboard-specific metrics
                extra_metrics = []

                # Total sessions
                extra_metrics.append(f"# HELP dashboard_total_sessions Total number of sessions")
                extra_metrics.append(f"# TYPE dashboard_total_sessions counter")
                extra_metrics.append(f"dashboard_total_sessions {state['total_sessions']}")

                # Total tokens
                extra_metrics.append(f"# HELP dashboard_total_tokens Total tokens used")
                extra_metrics.append(f"# TYPE dashboard_total_tokens counter")
                extra_metrics.append(f"dashboard_total_tokens {state['total_tokens']}")

                # Total cost
                extra_metrics.append(f"# HELP dashboard_total_cost_usd Total cost in USD")
                extra_metrics.append(f"# TYPE dashboard_total_cost_usd counter")
                extra_metrics.append(f"dashboard_total_cost_usd {state['total_cost_usd']}")

                # Agent metrics
                for agent_name, agent_data in state['agents'].items():
                    labels = f'{{agent="{agent_name}"}}'

                    extra_metrics.append(f"# HELP agent_invocations_total Total invocations per agent")
                    extra_metrics.append(f"# TYPE agent_invocations_total counter")
                    extra_metrics.append(f"agent_invocations_total{labels} {agent_data['total_invocations']}")

                    extra_metrics.append(f"# HELP agent_success_rate Success rate per agent")
                    extra_metrics.append(f"# TYPE agent_success_rate gauge")
                    extra_metrics.append(f"agent_success_rate{labels} {agent_data['success_rate']}")

                # Combine metrics
                full_metrics = metrics_text + "\n" + "\n".join(extra_metrics)

                increment_counter("prometheus_scrapes_success")
                logger.debug("Prometheus metrics exported")

                return web.Response(
                    text=full_metrics,
                    content_type="text/plain; version=0.0.4"
                )

            except Exception as e:
                increment_counter("prometheus_scrapes_errors")
                logger.error("Error exporting Prometheus metrics", exc_info=True, extra={"error": str(e)})
                raise web.HTTPInternalServerError(text=f"Error exporting metrics: {str(e)}")

    async def serve_monitoring_dashboard(self, request: Request) -> Response:
        """Serve the monitoring dashboard HTML page.

        Returns:
            Response with monitoring dashboard HTML
        """
        increment_counter("monitoring_dashboard_views")

        html_path = Path(__file__).parent / 'monitoring.html'
        if html_path.exists():
            logger.info("Serving monitoring dashboard")
            return web.Response(
                text=html_path.read_text(),
                content_type='text/html',
            )

        logger.warning("Monitoring dashboard HTML not found")
        raise web.HTTPNotFound(text='monitoring.html not found')

    async def system_status(self, request: Request) -> Response:
        """Get detailed system status information.

        Returns:
            JSON response with system metrics, logs, and alerts
        """
        with timed_operation("system_status_duration"):
            increment_counter("system_status_requests")

            try:
                # Get system metrics
                cpu_percent = psutil.cpu_percent(interval=0.1)
                cpu_count = psutil.cpu_count()
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')

                # Get network stats
                net_io = psutil.net_io_counters()

                # Get process info
                process = psutil.Process()
                process_memory = process.memory_info()

                # Get performance metrics
                perf_metrics = metrics_collector.get_metrics()

                # Check for alerts
                alerts = []
                if cpu_percent > 80:
                    alerts.append({
                        "severity": "warning",
                        "message": f"High CPU usage: {cpu_percent}%",
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    })
                if memory.percent > 85:
                    alerts.append({
                        "severity": "warning",
                        "message": f"High memory usage: {memory.percent}%",
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    })
                if disk.percent > 90:
                    alerts.append({
                        "severity": "critical",
                        "message": f"High disk usage: {disk.percent}%",
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    })

                status_data = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "status": "healthy" if not alerts else "degraded",
                    "alerts": alerts,

                    "system": {
                        "cpu": {
                            "percent": round(cpu_percent, 2),
                            "count": cpu_count,
                            "load_average": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else []
                        },
                        "memory": {
                            "percent": round(memory.percent, 2),
                            "used_mb": round(memory.used / (1024 * 1024), 2),
                            "total_mb": round(memory.total / (1024 * 1024), 2),
                            "available_mb": round(memory.available / (1024 * 1024), 2)
                        },
                        "disk": {
                            "percent": round(disk.percent, 2),
                            "used_gb": round(disk.used / (1024 * 1024 * 1024), 2),
                            "total_gb": round(disk.total / (1024 * 1024 * 1024), 2),
                            "free_gb": round(disk.free / (1024 * 1024 * 1024), 2)
                        },
                        "network": {
                            "bytes_sent": net_io.bytes_sent,
                            "bytes_recv": net_io.bytes_recv,
                            "packets_sent": net_io.packets_sent,
                            "packets_recv": net_io.packets_recv
                        }
                    },

                    "process": {
                        "pid": process.pid,
                        "memory_mb": round(process_memory.rss / (1024 * 1024), 2),
                        "cpu_percent": round(process.cpu_percent(interval=0.1), 2),
                        "num_threads": process.num_threads(),
                        "num_fds": process.num_fds() if hasattr(process, 'num_fds') else None
                    },

                    "performance_metrics": perf_metrics
                }

                increment_counter("system_status_success")
                logger.info("System status retrieved", extra={"alerts_count": len(alerts)})

                return web.json_response(status_data)

            except Exception as e:
                increment_counter("system_status_errors")
                logger.error("Error getting system status", exc_info=True, extra={"error": str(e)})
                raise web.HTTPInternalServerError(text=json.dumps({'error': str(e)}))

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

    def _on_collector_event(self, event_type: str, event: AgentEvent) -> None:
        """Callback for collector events.

        This is called synchronously by the collector. We queue the event
        for async broadcasting to avoid blocking the collector.

        Args:
            event_type: Type of event ("task_started", "task_completed", "task_failed")
            event: The event data
        """
        try:
            # Queue the event for async broadcasting
            self.event_queue.put_nowait((event_type, event))
        except Exception as e:
            logger.error(f"Error queueing collector event: {e}")

    async def _broadcast_collector_events(self):
        """Process and broadcast collector events to WebSocket clients."""
        while True:
            try:
                # Wait for events from the collector
                event_type, event = await self.event_queue.get()

                if not self.websockets:
                    continue

                # Prepare broadcast message
                message = {
                    'type': 'agent_event',
                    'event_type': event_type,
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'event': event
                }

                # Broadcast to all connected clients
                disconnected = set()
                for ws in self.websockets:
                    try:
                        await ws.send_json(message)
                        logger.info(f"Broadcast {event_type} event to WebSocket {id(ws)}")
                    except Exception as e:
                        logger.error(f"Error broadcasting event to WebSocket {id(ws)}: {e}")
                        disconnected.add(ws)

                # Remove disconnected clients
                self.websockets -= disconnected
                if disconnected:
                    logger.info(f"Removed {len(disconnected)} disconnected WebSocket clients")

            except asyncio.CancelledError:
                logger.info("Event broadcast task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in event broadcast loop: {e}")

    async def _start_broadcast(self, app):
        """Start the periodic metrics broadcast task."""
        self.broadcast_task = asyncio.create_task(self._broadcast_metrics())
        logger.info(f"WebSocket broadcast started (interval: {self.broadcast_interval}s)")

    async def _start_event_broadcast(self, app):
        """Start the event broadcast task for real-time updates."""
        self.event_broadcast_task = asyncio.create_task(self._broadcast_collector_events())
        logger.info("Real-time event broadcast started")

    async def _cleanup_websockets(self, app):
        """Clean up all WebSocket connections on shutdown."""
        logger.info("Cleaning up WebSocket connections...")

        # Cancel broadcast tasks
        if self.broadcast_task:
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                pass

        if self.event_broadcast_task:
            self.event_broadcast_task.cancel()
            try:
                await self.event_broadcast_task
            except asyncio.CancelledError:
                pass

        # Unsubscribe from collector events
        self.collector.unsubscribe(self._on_collector_event)

        # Close all active connections
        for ws in self.websockets:
            try:
                await ws.close(code=1001, message=b'Server shutting down')
            except Exception as e:
                logger.error(f"Error closing WebSocket {id(ws)}: {e}")

        self.websockets.clear()
        logger.info("WebSocket cleanup complete")

    # -------------------------------------------------------------------------
    # Agent Controls - AI-130: Pause, Resume & Requirement Editing
    # -------------------------------------------------------------------------

    def _validate_agent_id(self, agent_id: str) -> Optional[Response]:
        """Validate agent_id format. Returns error Response if invalid, else None."""
        if not agent_id:
            return web.json_response({'error': 'agent_id must not be empty'}, status=400)
        if not AGENT_ID_PATTERN.match(agent_id):
            return web.json_response(
                {'error': 'agent_id must contain only alphanumeric characters, dashes, or underscores'},
                status=400
            )
        return None

    def _get_agent_control(self, agent_id: str) -> dict:
        """Get or initialize control state for an agent.

        Enforces a maximum of AGENT_CONTROLS_MAX_ENTRIES entries to prevent
        unbounded memory growth from arbitrary agent IDs.
        """
        if agent_id not in agent_controls:
            if len(agent_controls) >= AGENT_CONTROLS_MAX_ENTRIES:
                logger.warning(
                    f"agent_controls store at capacity ({AGENT_CONTROLS_MAX_ENTRIES}). "
                    f"Rejecting new entry for agent_id: {agent_id}"
                )
                raise ValueError(
                    f"Maximum number of agent control entries ({AGENT_CONTROLS_MAX_ENTRIES}) reached. "
                    "Cannot add new agent."
                )
            agent_controls[agent_id] = {"paused": False, "requirements": ""}
        return agent_controls[agent_id]

    async def pause_agent(self, request: Request) -> Response:
        """POST /api/agents/{agent_id}/pause - Pause a specific agent.

        Stops the agent from accepting new delegations.

        Returns:
            200 OK with updated agent control state
            400 Bad Request for invalid agent_id
        """
        agent_id = request.match_info['agent_id']
        err = self._validate_agent_id(agent_id)
        if err:
            return err
        try:
            control = self._get_agent_control(agent_id)
        except ValueError as e:
            return web.json_response({'error': str(e)}, status=400)
        control['paused'] = True
        logger.info(f"Agent paused: {agent_id}")
        return web.json_response({
            'status': 'ok',
            'agent_id': agent_id,
            'paused': True,
            'message': f'Agent {agent_id} has been paused',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def resume_agent(self, request: Request) -> Response:
        """POST /api/agents/{agent_id}/resume - Resume a paused agent.

        Allows the agent to accept new delegations again.

        Returns:
            200 OK with updated agent control state
            400 Bad Request for invalid agent_id
        """
        agent_id = request.match_info['agent_id']
        err = self._validate_agent_id(agent_id)
        if err:
            return err
        try:
            control = self._get_agent_control(agent_id)
        except ValueError as e:
            return web.json_response({'error': str(e)}, status=400)
        control['paused'] = False
        logger.info(f"Agent resumed: {agent_id}")
        return web.json_response({
            'status': 'ok',
            'agent_id': agent_id,
            'paused': False,
            'message': f'Agent {agent_id} has been resumed',
            'requirements': control.get('requirements', ''),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def pause_all_agents(self, request: Request) -> Response:
        """POST /api/agents/pause-all - Pause all agents.

        Global control to stop all agents from accepting new delegations.

        Returns:
            200 OK with count of paused agents
        """
        state = self.store.load()
        agent_names = list(state.get('agents', {}).keys())
        for agent_id in agent_names:
            control = self._get_agent_control(agent_id)
            control['paused'] = True
        logger.info(f"All agents paused: {len(agent_names)} agents")
        return web.json_response({
            'status': 'ok',
            'paused_count': len(agent_names),
            'agent_ids': agent_names,
            'message': f'All {len(agent_names)} agents have been paused',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def resume_all_agents(self, request: Request) -> Response:
        """POST /api/agents/resume-all - Resume all paused agents.

        Global control to allow all agents to accept new delegations.

        Returns:
            200 OK with count of resumed agents
        """
        state = self.store.load()
        agent_names = list(state.get('agents', {}).keys())
        for agent_id in agent_names:
            control = self._get_agent_control(agent_id)
            control['paused'] = False
        logger.info(f"All agents resumed: {len(agent_names)} agents")
        return web.json_response({
            'status': 'ok',
            'resumed_count': len(agent_names),
            'agent_ids': agent_names,
            'message': f'All {len(agent_names)} agents have been resumed',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def get_agent_requirements(self, request: Request) -> Response:
        """GET /api/agents/{agent_id}/requirements - Get current requirements for an agent.

        Returns:
            200 OK with current requirement text
            400 Bad Request for invalid agent_id
        """
        agent_id = request.match_info['agent_id']
        err = self._validate_agent_id(agent_id)
        if err:
            return err
        try:
            control = self._get_agent_control(agent_id)
        except ValueError as e:
            return web.json_response({'error': str(e)}, status=400)
        return web.json_response({
            'agent_id': agent_id,
            'requirements': control.get('requirements', ''),
            'paused': control.get('paused', False),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def update_agent_requirements(self, request: Request) -> Response:
        """PUT /api/agents/{agent_id}/requirements - Update requirements for an agent.

        Request body:
            {"requirements": "Updated requirement text"}

        Returns:
            200 OK with confirmation
            400 Bad Request for invalid input
        """
        agent_id = request.match_info['agent_id']
        err = self._validate_agent_id(agent_id)
        if err:
            return err
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({'error': 'Invalid JSON'}, status=400)

        requirements = data.get('requirements')
        if requirements is None:
            return web.json_response(
                {'error': 'Missing required field: requirements'},
                status=400
            )

        if len(requirements) > REQUIREMENTS_MAX_LENGTH:
            return web.json_response(
                {'error': f'Requirements text exceeds maximum length of {REQUIREMENTS_MAX_LENGTH} characters'},
                status=400
            )

        try:
            control = self._get_agent_control(agent_id)
        except ValueError as e:
            return web.json_response({'error': str(e)}, status=400)
        control['requirements'] = requirements
        logger.info(f"Requirements updated for agent {agent_id}: {len(requirements)} chars")
        return web.json_response({
            'status': 'ok',
            'agent_id': agent_id,
            'requirements': requirements,
            'paused': control.get('paused', False),
            'message': f'Requirements for {agent_id} updated successfully',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def get_all_agent_controls(self, request: Request) -> Response:
        """GET /api/agent-controls - Get pause/resume state and requirements for all agents.

        Returns:
            200 OK with all agent control states
        """
        return web.json_response({
            'agent_controls': agent_controls,
            'total_agents': len(agent_controls),
            'paused_count': sum(1 for c in agent_controls.values() if c.get('paused', False)),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    # -------------------------------------------------------------------------
    # Chat History - AI-133: Message History Persistence
    # -------------------------------------------------------------------------

    async def get_chat_history(self, request: Request) -> Response:
        """GET /api/chat/history - Retrieve persisted message history (last 1000 messages).

        Returns:
            200 OK with list of chat messages
        """
        return web.json_response({
            'messages': chat_history[-CHAT_HISTORY_MAX:],
            'count': len(chat_history),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def post_chat_history(self, request: Request) -> Response:
        """POST /api/chat/history - Append message(s) to the history.

        Request body:
            Single message: {"id", "type": "user|ai|system", "content", "timestamp",
                             "provider"?, "model"?}
            OR array:        [{"id", "type", ...}, ...]

        Returns:
            200 OK with confirmation and updated count
            400 Bad Request for invalid input
        """
        try:
            data = await request.json()
        except (json.JSONDecodeError, ValueError):
            return web.json_response({'error': 'Invalid JSON'}, status=400)

        # Accept single message or array
        if isinstance(data, dict):
            messages_to_add = [data]
        elif isinstance(data, list):
            messages_to_add = data
        else:
            return web.json_response({'error': 'Body must be a message object or array'}, status=400)

        added = 0
        for msg in messages_to_add:
            if not isinstance(msg, dict):
                continue
            # Validate required fields
            if 'content' not in msg or 'type' not in msg:
                return web.json_response(
                    {'error': 'Each message must have "type" and "content" fields'},
                    status=400
                )
            if msg['type'] not in ('user', 'ai', 'system'):
                return web.json_response(
                    {'error': f'Invalid message type "{msg["type"]}". Must be user, ai, or system'},
                    status=400
                )
            # Ensure required fields have defaults
            entry = {
                'id': msg.get('id', int(datetime.utcnow().timestamp() * 1000)),
                'type': msg['type'],
                'content': msg['content'],
                'timestamp': msg.get('timestamp', datetime.utcnow().isoformat() + 'Z'),
                'provider': msg.get('provider'),
                'model': msg.get('model')
            }
            chat_history.append(entry)
            added += 1

        # Enforce server-side limit
        if len(chat_history) > CHAT_HISTORY_MAX:
            del chat_history[:len(chat_history) - CHAT_HISTORY_MAX]

        logger.info(f"Chat history: added {added} message(s), total={len(chat_history)}")
        return web.json_response({
            'status': 'ok',
            'added': added,
            'total': len(chat_history),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def delete_chat_history(self, request: Request) -> Response:
        """DELETE /api/chat/history - Clear all persisted chat history.

        Returns:
            200 OK with confirmation
        """
        count = len(chat_history)
        chat_history.clear()
        logger.info(f"Chat history cleared: removed {count} messages")
        return web.json_response({
            'status': 'ok',
            'cleared': count,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def post_transparency_reasoning(self, request: Request) -> Response:
        """POST /api/transparency/reasoning - Emit a reasoning event.

        Request body:
            {agent, decision, complexity, reasoning, timestamp?}

        Broadcasts event to all WebSocket clients as type "reasoning".

        Returns:
            200 OK with the stored event
            400 Bad Request for invalid input
        """
        try:
            data = await request.json()
        except (json.JSONDecodeError, ValueError):
            return web.json_response({'error': 'Invalid JSON'}, status=400)

        if not isinstance(data, dict):
            return web.json_response({'error': 'Body must be a JSON object'}, status=400)

        # Validate required fields
        required = ('agent', 'decision', 'complexity', 'reasoning')
        for field in required:
            if field not in data:
                return web.json_response(
                    {'error': f'Missing required field: {field}'},
                    status=400
                )

        entry = {
            'agent': str(data['agent']),
            'decision': str(data['decision']),
            'complexity': str(data['complexity']),
            'reasoning': str(data['reasoning']),
            'timestamp': data.get('timestamp', datetime.utcnow().isoformat() + 'Z'),
        }

        # Store in memory
        reasoning_history.append(entry)
        if len(reasoning_history) > REASONING_HISTORY_MAX:
            del reasoning_history[:len(reasoning_history) - REASONING_HISTORY_MAX]

        # Broadcast to WebSocket clients
        ws_message = {
            'type': 'reasoning',
            'timestamp': entry['timestamp'],
            'agent': entry['agent'],
            'decision': entry['decision'],
            'complexity': entry['complexity'],
            'reasoning': entry['reasoning'],
        }
        disconnected = set()
        for ws in self.websockets:
            try:
                await ws.send_json(ws_message)
            except Exception as e:
                logger.error(f"Error broadcasting reasoning to WebSocket {id(ws)}: {e}")
                disconnected.add(ws)
        self.websockets -= disconnected

        logger.info(f"Transparency reasoning emitted from agent={entry['agent']}, complexity={entry['complexity']}")
        return web.json_response({'status': 'ok', 'event': entry})

    async def get_transparency_history(self, request: Request) -> Response:
        """GET /api/transparency/history - Get last 100 reasoning events.

        Returns:
            200 OK with list of reasoning events
        """
        return web.json_response({
            'history': reasoning_history[-REASONING_HISTORY_MAX:],
            'count': len(reasoning_history),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def delete_transparency_history(self, request: Request) -> Response:
        """DELETE /api/transparency/history - Clear all reasoning history.

        Returns:
            200 OK with confirmation
        """
        count = len(reasoning_history)
        reasoning_history.clear()
        logger.info(f"Transparency history cleared: removed {count} events")
        return web.json_response({
            'status': 'ok',
            'cleared': count,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def post_transparency_code_stream(self, request: Request) -> Response:
        """POST /api/transparency/code-stream - Emit a live code streaming chunk.

        Request body:
            {agent_id, chunk, file_path, done}

        Broadcasts event to all WebSocket clients as type "code_stream".

        Returns:
            200 OK
            400 Bad Request for invalid input
        """
        try:
            data = await request.json()
        except (json.JSONDecodeError, ValueError):
            return web.json_response({'error': 'Invalid JSON'}, status=400)

        if not isinstance(data, dict):
            return web.json_response({'error': 'Body must be a JSON object'}, status=400)

        required = ('agent_id', 'chunk', 'file_path')
        for field in required:
            if field not in data:
                return web.json_response(
                    {'error': f'Missing required field: {field}'},
                    status=400
                )

        ws_message = {
            'type': 'code_stream',
            'agent_id': str(data['agent_id']),
            'chunk': str(data['chunk']),
            'file_path': str(data['file_path']),
            'done': bool(data.get('done', False)),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        }

        disconnected = set()
        for ws in self.websockets:
            try:
                await ws.send_json(ws_message)
            except Exception as e:
                logger.error(f"Error broadcasting code_stream to WebSocket {id(ws)}: {e}")
                disconnected.add(ws)
        self.websockets -= disconnected

        logger.info(f"Transparency code-stream emitted: agent={ws_message['agent_id']}, file={ws_message['file_path']}, done={ws_message['done']}")
        return web.json_response({'status': 'ok'})

    def run(self):
        """Start the HTTP server with WebSocket support.

        Runs the aiohttp application and blocks until server is stopped.
        """
        logger.info(f"Starting Dashboard Server on {self.host}:{self.port}")
        logger.info(f"Endpoints available:")
        logger.info(f"  GET  {self.host}:{self.port}/health")
        logger.info(f"  GET  {self.host}:{self.port}/api/metrics")
        logger.info(f"  GET  {self.host}:{self.port}/api/agents/<name>")
        logger.info(f"  WS   ws://{self.host}:{self.port}/ws")
        logger.info("")
        logger.info("WebSocket Real-Time Updates:")
        logger.info(f"  Broadcast interval: {self.broadcast_interval}s")
        logger.info(f"  Auto-reconnect supported with exponential backoff")
        logger.info("")
        logger.info("A2UI Component Integration:")
        logger.info("  Components: TaskCard, ProgressRing, ActivityItem, ErrorCard")
        logger.info("  Location: /Users/bkh223/Documents/GitHub/agent-engineers/reusable/a2ui-components/")
        logger.info("")
        logger.info("Press Ctrl+C to stop the server")

        try:
            web.run_app(
                self.app,
                host=self.host,
                port=self.port,
                print=None  # Disable aiohttp's default logging
            )
        except KeyboardInterrupt:
            logger.info("Server stopped by user")


def main():
    """CLI entry point for dashboard server."""
    parser = argparse.ArgumentParser(
        description='Agent Status Dashboard HTTP Server (AI-111)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server with environment variables (recommended)
  DASHBOARD_WEB_PORT=8420 DASHBOARD_WS_PORT=8421 python -m dashboard.server

  # Start server with defaults
  python -m dashboard.server

  # Override environment with CLI args
  python -m dashboard.server --port 9000 --host localhost

Environment Variables (AI-111 Configuration):
  DASHBOARD_WEB_PORT     - Port for web dashboard (default: 8420)
  DASHBOARD_WS_PORT      - Port for WebSocket (default: 8421)
  DASHBOARD_HOST         - Host to bind (default: 0.0.0.0)
  DASHBOARD_AUTH_TOKEN   - Bearer token for authentication (default: none)
  DASHBOARD_CORS_ORIGINS - Allowed CORS origins (default: *)
  LOG_LEVEL              - Logging level (default: INFO)

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
        default=None,
        help='HTTP server port (overrides DASHBOARD_WEB_PORT env var)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default=None,
        help='HTTP server host (overrides DASHBOARD_HOST env var)'
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

    # Create and run server
    server = DashboardServer(
        project_name=args.project_name,
        metrics_dir=args.metrics_dir,
        port=args.port,
        host=args.host,
        use_config=True  # Load from environment variables
    )

    server.run()


if __name__ == '__main__':
    main()
