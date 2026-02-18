"""Optional bearer token authentication for the dashboard (AI-176 / REQ-TECH-011).

When DASHBOARD_AUTH_TOKEN is set, all API endpoints and WebSocket connections
require a valid bearer token.  When the variable is not set the dashboard is
open (suitable for local development).

Usage
-----
Import ``auth_middleware`` and register it BEFORE ``cors_middleware``::

    from dashboard.auth import auth_middleware
    app = web.Application(middlewares=[auth_middleware, cors_middleware])

Token delivery
--------------
HTTP requests:
    Authorization: Bearer <token>

WebSocket connections:
    ?token=<token>          (query parameter, preferred)
    Authorization: Bearer <token>  (header fallback)
"""

import hmac
import os

from aiohttp import web
from aiohttp.web import Request, Response, middleware

try:
    from dashboard.config import get_config
except ImportError:
    def get_config():  # type: ignore[misc]
        class _C:
            auth_token = os.getenv('DASHBOARD_AUTH_TOKEN', '')
            auth_required = bool(auth_token)
            auth_enabled = auth_required
        return _C()


def verify_token(provided: str, expected: str) -> bool:
    """Constant-time comparison to prevent timing attacks.

    Args:
        provided: Token supplied by the client.
        expected: The authoritative token from configuration.

    Returns:
        True only when both arguments are non-empty and identical.
    """
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided.encode(), expected.encode())


def extract_bearer_token(request: Request) -> 'str | None':
    """Extract token from ``Authorization: Bearer <token>`` header.

    Args:
        request: Incoming aiohttp request.

    Returns:
        The bare token string, or *None* if the header is absent or malformed.
    """
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:].strip()
        return token if token else None
    return None


def extract_ws_token(request: Request) -> 'str | None':
    """Extract token from a WebSocket upgrade request.

    Checks the ``?token=...`` query parameter first, then falls back to the
    ``Authorization: Bearer <token>`` header so that clients unable to set
    custom headers can still authenticate.

    Args:
        request: Incoming aiohttp request (WebSocket upgrade).

    Returns:
        The bare token string, or *None* if not found in either location.
    """
    # Prefer query parameter (browser WebSocket APIs cannot set custom headers)
    token = request.rel_url.query.get('token')
    if token:
        return token.strip() or None
    # Fall back to Authorization header
    return extract_bearer_token(request)


def _unauthorized(message: str = 'Unauthorized') -> Response:
    """Return a 401 JSON response with a descriptive error body.

    Args:
        message: Human-readable error description.

    Returns:
        aiohttp JSON response with status 401.
    """
    return web.json_response(
        {'error': message, 'status': 401},
        status=401,
    )


@middleware
async def auth_middleware(request: Request, handler):
    """Enforce bearer-token authentication when DASHBOARD_AUTH_TOKEN is set.

    - If the environment variable is **not** set the middleware is a no-op and
      every request passes through unchanged (open / development mode).
    - The ``/health`` endpoint is always exempt so that load-balancers and
      infrastructure health checks never require a token.
    - WebSocket connections (``/ws``) may supply the token via the ``?token=``
      query parameter or the ``Authorization: Bearer`` header.
    - All other endpoints must supply the token in the ``Authorization: Bearer``
      header.

    Returns:
        The upstream handler's response, or a 401 JSON response when the token
        is missing or invalid.
    """
    config = get_config()

    # No token configured → open dashboard (local development mode)
    if not config.auth_required:
        return await handler(request)

    # /health is always accessible so health-check infrastructure can work
    if request.path == '/health':
        return await handler(request)

    # OPTIONS preflight requests must not be blocked by auth so that browsers
    # can discover CORS support before sending the actual credentialed request.
    if request.method == 'OPTIONS':
        return await handler(request)

    # Extract token depending on whether this is a WebSocket upgrade
    if request.path == '/ws':
        provided = extract_ws_token(request)
    else:
        provided = extract_bearer_token(request)

    if not provided:
        return _unauthorized(
            'Authentication required. '
            'Provide a bearer token via the Authorization header '
            '(or ?token= query parameter for WebSocket connections).'
        )

    expected = config.auth_token or ''
    if not verify_token(provided, expected):
        return _unauthorized('Invalid or expired bearer token.')

    return await handler(request)
