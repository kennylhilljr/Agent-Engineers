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
_requirements_cache: Dict[str, str] = {}  # ticket_key -> requirement text
_decisions_log: list[Dict[str, Any]] = []  # Decision history


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

        # Agents
        self.app.router.add_get('/api/agents', self.get_all_agents)
        self.app.router.add_get('/api/agents/{name}', self.get_agent)
        self.app.router.add_get('/api/agents/{name}/events', self.get_agent_events)
        self.app.router.add_post('/api/agents/{name}/pause', self.pause_agent)
        self.app.router.add_post('/api/agents/{name}/resume', self.resume_agent)

        # Agent Controls - global pause/resume (AI-130)
        self.app.router.add_post('/api/agents/pause-all', self.pause_all_agents)
        self.app.router.add_post('/api/agents/resume-all', self.resume_all_agents)
        self.app.router.add_get('/api/agent-controls', self.get_all_agent_controls)
        self.app.router.add_get('/api/agents/{name}/requirements', self.get_agent_requirements_by_name)
        self.app.router.add_put('/api/agents/{name}/requirements', self.update_agent_requirements_by_name)

        # Sessions and providers
        self.app.router.add_get('/api/sessions', self.get_sessions)
        self.app.router.add_get('/api/providers', self.get_providers)
        self.app.router.add_get('/api/providers/status', self.get_provider_status)

        # Chat
        self.app.router.add_post('/api/chat', self.chat)

        # Requirements
        self.app.router.add_put('/api/requirements/{ticket_key}', self.update_requirement)
        self.app.router.add_get('/api/requirements/{ticket_key}', self.get_requirement)

        # Decisions
        self.app.router.add_get('/api/decisions', self.get_decisions)

        # Dashboard HTML
        self.app.router.add_get('/', self.serve_dashboard)

        # OPTIONS for CORS preflight
        for route in ['/api/metrics', '/api/agents', '/api/sessions', '/api/providers',
                      '/api/chat', '/api/decisions']:
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

    # -------------------------------------------------------------------------
    # AI-130: Global Pause/Resume & Agent Controls
    # -------------------------------------------------------------------------

    async def pause_all_agents(self, request: Request) -> Response:
        """POST /api/agents/pause-all - Pause all agents.

        Returns:
            200 OK with count and list of paused agent names
        """
        for agent_name in ALL_AGENT_NAMES:
            _agent_states[agent_name] = 'paused'
            # Ensure requirements entry exists in cache
            if agent_name not in _requirements_cache:
                _requirements_cache[agent_name] = ''

        _decisions_log.append({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'decision_type': 'pause_all',
            'agent_count': len(ALL_AGENT_NAMES)
        })

        return web.json_response({
            'status': 'ok',
            'paused_count': len(ALL_AGENT_NAMES),
            'agent_ids': ALL_AGENT_NAMES,
            'message': f'All {len(ALL_AGENT_NAMES)} agents have been paused',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def resume_all_agents(self, request: Request) -> Response:
        """POST /api/agents/resume-all - Resume all agents.

        Returns:
            200 OK with count and list of resumed agent names
        """
        for agent_name in ALL_AGENT_NAMES:
            _agent_states[agent_name] = 'idle'

        _decisions_log.append({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'decision_type': 'resume_all',
            'agent_count': len(ALL_AGENT_NAMES)
        })

        return web.json_response({
            'status': 'ok',
            'resumed_count': len(ALL_AGENT_NAMES),
            'agent_ids': ALL_AGENT_NAMES,
            'message': f'All {len(ALL_AGENT_NAMES)} agents have been resumed',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

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
