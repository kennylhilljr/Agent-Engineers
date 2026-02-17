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
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

import aiohttp
from aiohttp import web, WSMsgType
from aiohttp.web import Request, Response, WebSocketResponse, middleware
from aiohttp_cors import ResourceOptions, setup as cors_setup

from dashboard.metrics_store import MetricsStore

# In-memory store for requirements (ticket_key -> requirement text)
_requirements_store: dict = {}

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

        # OPTIONS for CORS preflight
        self.app.router.add_route('OPTIONS', '/api/metrics', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/agents/{agent_name}', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/requirements/{ticket_key}', self.handle_options)
        self.app.router.add_route('OPTIONS', '/api/reasoning', self.handle_options)

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
