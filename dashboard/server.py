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
from datetime import datetime
from pathlib import Path
from typing import Optional, Set
from uuid import uuid4

import aiohttp
from aiohttp import web, WSMsgType
from aiohttp.web import Request, Response, WebSocketResponse, middleware
from aiohttp_cors import ResourceOptions, setup as cors_setup

from dashboard.metrics_store import MetricsStore

# In-memory store for requirements (ticket_key -> requirement text)
_requirements_store: dict = {}

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

    def __init__(
        self,
        project_name: str = "agent-status-dashboard",
        metrics_dir: Optional[Path] = None,
        port: int = 8080,
        host: str = "127.0.0.1"
    ):
        """Initialize DashboardServer.

        Args:
            project_name: Project name for metrics store
            metrics_dir: Directory containing .agent_metrics.json
            port: HTTP server port
            host: HTTP server host (default: 127.0.0.1 for localhost-only access)

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
        self.broadcast_interval = 5  # seconds

        # Circular buffer for reasoning/thinking history (AI-160)
        self._reasoning_history: list = []

        # Circular buffer for decision log (AI-161)
        self._decision_log: list = []

        # In-memory code streams store (AI-163): {stream_id: {file_path, language, agent, chunks, started_at, completed}}
        self._code_streams: dict = {}

        # In-memory file changes store (AI-164): list of file change summaries, newest last
        self._file_changes: list = []

        # In-memory test results store (AI-165): list of test run records, newest last
        self._test_results: list = []

        # Create app with middlewares
        self.app = web.Application(middlewares=[error_middleware, cors_middleware])

        # Register routes
        self._setup_routes()

        # Setup WebSocket broadcasting
        self.app.on_startup.append(self._start_broadcast)
        self.app.on_cleanup.append(self._cleanup_websockets)

        logger.info(f"Dashboard server initialized for project: {project_name}")
        logger.info(f"Metrics directory: {self.metrics_dir}")

    def _setup_routes(self):
        """Register HTTP routes and WebSocket endpoint."""
        self.app.router.add_get('/', self.serve_dashboard)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/api/metrics', self.get_metrics)
        self.app.router.add_get('/api/agents/{agent_name}', self.get_agent)
        self.app.router.add_get('/ws', self.websocket_handler)

        # Requirement sync endpoints
        self.app.router.add_get('/api/requirements/{ticket_key}', self.get_requirement)
        self.app.router.add_put('/api/requirements/{ticket_key}', self.put_requirement)

        # Reasoning broadcast endpoint (AI-158)
        self.app.router.add_post('/api/reasoning', self.broadcast_reasoning)

        # Agent thinking broadcast endpoint (AI-159)
        self.app.router.add_post('/api/agent-thinking', self.broadcast_agent_thinking)

        # Reasoning blocks history endpoint (AI-160)
        self.app.router.add_get('/api/reasoning/blocks', self.get_reasoning_blocks)

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

        # OPTIONS for CORS preflight
        self.app.router.add_route('OPTIONS', '/api/metrics', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/{agent_name}', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/requirements/{ticket_key}', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/reasoning', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agent-thinking', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/reasoning/blocks', self.handle_options)
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

    async def broadcast_to_websockets(self, message: dict) -> None:
        """Broadcast a JSON message to all connected WebSocket clients.

        Args:
            message: Dictionary to serialise and send to every active client.
                     Disconnected clients are silently removed from the pool.
        """
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
            limit: Maximum number of results to return (default: all)

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

        if limit_str:
            try:
                limit = int(limit_str)
                results = results[:limit]
            except ValueError:
                pass

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
        logger.info("  Reasoning (AI-158/160):")
        logger.info(f"    POST {base}/api/reasoning")
        logger.info(f"    GET  {base}/api/reasoning/blocks")
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
        logger.info("  WebSocket:")
        logger.info(f"    WS   {ws_base}/ws  (broadcast interval: {self.broadcast_interval}s)")
        logger.info("=" * 60)
        logger.info("  Press Ctrl+C to stop")
        logger.info("=" * 60)

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
        help='HTTP server port (default: 8080)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='HTTP server host (default: 127.0.0.1 for localhost-only access; use 0.0.0.0 to expose to network)'
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
        host=args.host
    )

    server.run()


if __name__ == '__main__':
    main()
