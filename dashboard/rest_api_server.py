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
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from aiohttp import web
from aiohttp.web import Request, Response, middleware

from dashboard.metrics_store import MetricsStore, ALL_AGENT_NAMES
from dashboard.security_enforcement import get_security_enforcer, SecurityCheckResult

# Import only if needed - avoid importing agents.definitions which has Python 3.10+ dependencies
# from agents.definitions import DEFAULT_MODELS, AGENT_DEFINITIONS


# Agent state tracking (in-memory for pause/resume)
_agent_states: Dict[str, str] = {}  # agent_name -> "running" | "paused" | "idle"
_requirements_cache: Dict[str, str] = {}  # ticket_key -> requirement text
_decisions_log: list[Dict[str, Any]] = []  # Decision history


def get_auth_token() -> Optional[str]:
    """Get authentication token from environment variable."""
    return os.getenv("DASHBOARD_AUTH_TOKEN")


def create_auth_middleware():
    """Create authentication middleware that checks token on each request."""
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
            return web.json_response(
                {"error": "Missing or invalid Authorization header"},
                status=401
            )

        token = auth_header[7:]  # Remove "Bearer " prefix

        if token != auth_token:
            return web.json_response(
                {"error": "Invalid authentication token"},
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

        # Initialize security enforcer
        self.security = get_security_enforcer(project_root=self.metrics_dir)

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
        self.app.router.add_get('/api/metrics', self.get_metrics)

        # Agents
        self.app.router.add_get('/api/agents', self.get_all_agents)
        self.app.router.add_get('/api/agents/{name}', self.get_agent)
        self.app.router.add_get('/api/agents/{name}/events', self.get_agent_events)
        self.app.router.add_post('/api/agents/{name}/pause', self.pause_agent)
        self.app.router.add_post('/api/agents/{name}/resume', self.resume_agent)

        # Sessions and providers
        self.app.router.add_get('/api/sessions', self.get_sessions)
        self.app.router.add_get('/api/providers', self.get_providers)

        # Chat
        self.app.router.add_post('/api/chat', self.chat)

        # Requirements
        self.app.router.add_put('/api/requirements/{ticket_key}', self.update_requirement)
        self.app.router.add_get('/api/requirements/{ticket_key}', self.get_requirement)

        # Decisions
        self.app.router.add_get('/api/decisions', self.get_decisions)

        # Dashboard HTML
        self.app.router.add_get('/', self.serve_dashboard)

        # Security endpoints (AI-113)
        self.app.router.add_post('/api/security/bash', self.execute_bash_command)
        self.app.router.add_post('/api/security/file/read', self.read_file)
        self.app.router.add_post('/api/security/file/write', self.write_file)
        self.app.router.add_post('/api/security/mcp/call', self.call_mcp_tool)

        # OPTIONS for CORS preflight
        for route in ['/api/metrics', '/api/agents', '/api/sessions', '/api/providers',
                      '/api/chat', '/api/decisions', '/api/security/bash',
                      '/api/security/file/read', '/api/security/file/write',
                      '/api/security/mcp/call']:
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

        Returns:
            200 OK with list of providers and their models
        """
        providers = [
            {
                'name': 'Claude',
                'provider_id': 'claude',
                'models': ['haiku-4-5', 'sonnet-4-5', 'opus-4-6'],
                'default_model': 'sonnet-4-5',
                'available': True,  # Always available (default)
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
                'available': bool(os.getenv('GEMINI_API_KEY')),
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
                'available': bool(os.getenv('KIMI_API_KEY')),
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

    async def chat(self, request: Request) -> Response:
        """POST /api/chat - Send chat message (streaming response).

        Request body:
            {
                "message": "User message",
                "provider": "claude" (optional, default: claude),
                "model": "sonnet-4-5" (optional),
                "session_id": "session-123" (optional)
            }

        Returns:
            200 OK with streaming response
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
        model = data.get('model')
        session_id = data.get('session_id')

        # For now, return a mock response
        # TODO: Integrate with actual chat implementation
        response_data = {
            'response': f'Received message: {message}',
            'provider': provider,
            'model': model,
            'session_id': session_id,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'status': 'success',
            'note': 'Chat functionality is a placeholder - integrate with actual chat system'
        }

        return web.json_response(response_data)

    async def pause_agent(self, request: Request) -> Response:
        """POST /api/agents/{name}/pause - Pause an agent.

        Args:
            name: Agent name (path parameter)

        Returns:
            200 OK with confirmation
            404 Not Found if agent doesn't exist
        """
        agent_name = request.match_info['name']

        if agent_name not in ALL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name
            }, status=404)

        # Update agent state
        _agent_states[agent_name] = 'paused'

        # Log decision
        _decisions_log.append({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'decision_type': 'agent_pause',
            'agent_name': agent_name,
            'previous_state': 'running',
            'new_state': 'paused'
        })

        return web.json_response({
            'status': 'success',
            'agent_name': agent_name,
            'state': 'paused',
            'message': f'Agent {agent_name} has been paused',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def resume_agent(self, request: Request) -> Response:
        """POST /api/agents/{name}/resume - Resume an agent.

        Args:
            name: Agent name (path parameter)

        Returns:
            200 OK with confirmation
            404 Not Found if agent doesn't exist
        """
        agent_name = request.match_info['name']

        if agent_name not in ALL_AGENT_NAMES:
            return web.json_response({
                'error': 'Agent not found',
                'agent_name': agent_name
            }, status=404)

        # Update agent state
        previous_state = _agent_states.get(agent_name, 'paused')
        _agent_states[agent_name] = 'idle'

        # Log decision
        _decisions_log.append({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'decision_type': 'agent_resume',
            'agent_name': agent_name,
            'previous_state': previous_state,
            'new_state': 'idle'
        })

        return web.json_response({
            'status': 'success',
            'agent_name': agent_name,
            'state': 'idle',
            'message': f'Agent {agent_name} has been resumed',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def update_requirement(self, request: Request) -> Response:
        """PUT /api/requirements/{ticket_key} - Update requirement instructions.

        Args:
            ticket_key: Linear ticket key (path parameter)

        Request body:
            {
                "requirements": "Updated requirement text"
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

        requirements = data.get('requirements')
        if not requirements:
            return web.json_response({
                'error': 'Missing required field: requirements'
            }, status=400)

        # Store requirement in cache
        _requirements_cache[ticket_key] = requirements

        # Log decision
        _decisions_log.append({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'decision_type': 'requirement_update',
            'ticket_key': ticket_key,
            'requirements_length': len(requirements)
        })

        return web.json_response({
            'status': 'success',
            'ticket_key': ticket_key,
            'message': f'Requirements for {ticket_key} updated',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def get_requirement(self, request: Request) -> Response:
        """GET /api/requirements/{ticket_key} - Get current requirement instructions.

        Args:
            ticket_key: Linear ticket key (path parameter)

        Returns:
            200 OK with requirement text
            404 Not Found if requirement doesn't exist
        """
        ticket_key = request.match_info['ticket_key']

        requirements = _requirements_cache.get(ticket_key)

        if requirements is None:
            return web.json_response({
                'error': 'Requirement not found',
                'ticket_key': ticket_key,
                'message': f'No requirements cached for {ticket_key}'
            }, status=404)

        return web.json_response({
            'ticket_key': ticket_key,
            'requirements': requirements,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
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

    async def serve_dashboard(self, request: Request) -> Response:
        """GET / - Serve dashboard HTML.

        Returns:
            200 OK with HTML content
            404 Not Found if HTML file doesn't exist
        """
        html_path = Path(__file__).parent / 'index.html'
        if html_path.exists():
            return web.Response(
                text=html_path.read_text(),
                content_type='text/html'
            )

        # Fallback to dashboard.html
        html_path = Path(__file__).parent / 'dashboard.html'
        if html_path.exists():
            return web.Response(
                text=html_path.read_text(),
                content_type='text/html'
            )

        return web.json_response({
            'error': 'Dashboard HTML not found',
            'message': 'index.html or dashboard.html not found in dashboard directory'
        }, status=404)

    # ========================================================================
    # Security Endpoints (AI-113) - Sandbox Compliance
    # ========================================================================

    async def execute_bash_command(self, request: Request) -> Response:
        """POST /api/security/bash - Execute bash command with security validation.

        Request body:
            {
                "command": "ls -la"
            }

        Returns:
            200 OK with command execution result (if allowed)
            403 Forbidden if command is blocked by security policy
            400 Bad Request for invalid input

        Security:
            - Commands validated against allowlist in security.py
            - Error messages sanitized to prevent information leakage
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({
                'error': 'Invalid JSON in request body',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=400)

        command = data.get('command')
        if not command:
            return web.json_response({
                'error': 'Missing required field: command',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=400)

        # Validate command with security enforcer
        result = await self.security.validate_bash_command(command)

        if not result.allowed:
            return web.json_response({
                'error': 'Command blocked by security policy',
                'message': result.sanitized_error,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=403)

        # Command is allowed - in a real implementation, would execute it here
        # For now, just return success
        return web.json_response({
            'status': 'allowed',
            'command': command,
            'message': 'Command validated and would be executed',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def read_file(self, request: Request) -> Response:
        """POST /api/security/file/read - Read file with security validation.

        Request body:
            {
                "file_path": "src/main.py"
            }

        Returns:
            200 OK with file content (if allowed)
            403 Forbidden if file is outside project directory
            400 Bad Request for invalid input

        Security:
            - File paths validated to be within project directory
            - Symlinks resolved to prevent bypass
            - Error messages sanitized
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({
                'error': 'Invalid JSON in request body',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=400)

        file_path = data.get('file_path')
        if not file_path:
            return web.json_response({
                'error': 'Missing required field: file_path',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=400)

        # Validate file path with security enforcer
        result = self.security.validate_file_path(file_path)

        if not result.allowed:
            return web.json_response({
                'error': 'File access denied',
                'message': result.sanitized_error,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=403)

        # File path is allowed - in a real implementation, would read it here
        # For now, just return success
        return web.json_response({
            'status': 'allowed',
            'file_path': file_path,
            'message': 'File path validated and would be read',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def write_file(self, request: Request) -> Response:
        """POST /api/security/file/write - Write file with security validation.

        Request body:
            {
                "file_path": "src/main.py",
                "content": "# Python code"
            }

        Returns:
            200 OK if write would be allowed
            403 Forbidden if file is outside project directory
            400 Bad Request for invalid input

        Security:
            - File paths validated to be within project directory
            - Symlinks resolved to prevent bypass
            - Error messages sanitized
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({
                'error': 'Invalid JSON in request body',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=400)

        file_path = data.get('file_path')
        content = data.get('content')

        if not file_path:
            return web.json_response({
                'error': 'Missing required field: file_path',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=400)

        if content is None:
            return web.json_response({
                'error': 'Missing required field: content',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=400)

        # Validate file path with security enforcer
        result = self.security.validate_file_path(file_path)

        if not result.allowed:
            return web.json_response({
                'error': 'File access denied',
                'message': result.sanitized_error,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=403)

        # File path is allowed - in a real implementation, would write it here
        # For now, just return success
        return web.json_response({
            'status': 'allowed',
            'file_path': file_path,
            'content_length': len(content),
            'message': 'File path validated and would be written',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def call_mcp_tool(self, request: Request) -> Response:
        """POST /api/security/mcp/call - Call MCP tool with authorization check.

        Request body:
            {
                "tool_name": "slack__send_message",
                "tool_input": {"channel": "#general", "message": "Hello"},
                "auth_token": "arcade-gateway-token"
            }

        Returns:
            200 OK if tool call is authorized
            403 Forbidden if authorization fails
            400 Bad Request for invalid input

        Security:
            - Authorization token required
            - Token validated with Arcade gateway
            - Error messages sanitized
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({
                'error': 'Invalid JSON in request body',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=400)

        tool_name = data.get('tool_name')
        tool_input = data.get('tool_input')
        auth_token = data.get('auth_token')

        if not tool_name:
            return web.json_response({
                'error': 'Missing required field: tool_name',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=400)

        if not tool_input:
            return web.json_response({
                'error': 'Missing required field: tool_input',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=400)

        # Validate MCP tool call with security enforcer
        result = await self.security.validate_mcp_tool_call(
            tool_name=tool_name,
            tool_input=tool_input,
            auth_token=auth_token
        )

        if not result.allowed:
            return web.json_response({
                'error': 'MCP tool call denied',
                'message': result.sanitized_error,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }, status=403)

        # Tool call is authorized - in a real implementation, would execute it here
        # For now, just return success
        return web.json_response({
            'status': 'authorized',
            'tool_name': tool_name,
            'message': 'Tool call authorized and would be executed',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

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
        print("Security Endpoints (AI-113):")
        print(f"  POST /api/security/bash - Execute bash command (with allowlist validation)")
        print(f"  POST /api/security/file/read - Read file (within project directory)")
        print(f"  POST /api/security/file/write - Write file (within project directory)")
        print(f"  POST /api/security/mcp/call - Call MCP tool (with authorization)")
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
