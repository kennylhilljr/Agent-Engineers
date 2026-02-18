"""Authentication package for Agent Dashboard (AI-222).

Provides:
- user_store: User creation, storage, password hashing/verification
- session_manager: JWT/token session management, rate limiting, CSRF
- oauth_handler: GitHub and Google OAuth flow

Backward compatibility:
- verify_token, extract_bearer_token, extract_ws_token, auth_middleware
  are re-exported from this package to maintain compatibility with callers
  that previously imported from dashboard.auth (the old auth.py module).
"""

# ── Backward-compatible re-exports from old auth.py (AI-176 / REQ-TECH-011) ──

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
    ``Authorization: Bearer <token>`` header.

    Args:
        request: Incoming aiohttp request (WebSocket upgrade).

    Returns:
        The bare token string, or *None* if not found in either location.
    """
    token = request.rel_url.query.get('token')
    if token:
        return token.strip() or None
    return extract_bearer_token(request)


def _unauthorized(message: str = 'Unauthorized') -> Response:
    """Return a 401 JSON response.

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

    - If the environment variable is **not** set the middleware is a no-op.
    - The ``/health`` endpoint is always exempt.
    - WebSocket connections (``/ws``) may supply the token via ``?token=``
      or the ``Authorization: Bearer`` header.
    - AI-222: ``/auth/`` routes are always open (they manage their own auth).

    Returns:
        The upstream handler's response, or a 401 JSON response.
    """
    config = get_config()

    if not config.auth_required:
        return await handler(request)

    if request.path == '/health':
        return await handler(request)

    if request.method == 'OPTIONS':
        return await handler(request)

    # AI-222: Auth endpoints manage their own authentication
    if request.path.startswith('/auth/'):
        return await handler(request)

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


# ── New AI-222 auth sub-modules ───────────────────────────────────────────────

from dashboard.auth.user_store import UserStore, User
from dashboard.auth.session_manager import SessionManager
from dashboard.auth.oauth_handler import OAuthHandler, OAuthNotConfiguredError

__all__ = [
    # Backward-compat exports (old auth.py)
    "verify_token",
    "extract_bearer_token",
    "extract_ws_token",
    "auth_middleware",
    # New AI-222 exports
    "UserStore",
    "User",
    "SessionManager",
    "OAuthHandler",
    "OAuthNotConfiguredError",
]
