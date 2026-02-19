"""GitLab OAuth 2.0 and Personal Access Token handler (AI-251).

Supports both OAuth 2.0 authorization code flow and Personal Access Token
(PAT) authentication. All token-exchange calls are simulated (mocked) —
no real GitLab credentials are required.

Reference: https://docs.gitlab.com/ee/api/oauth2.html
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# GitLab OAuth 2.0 endpoints (default to gitlab.com)
_AUTH_URL_TEMPLATE = "{base_url}/oauth/authorize"
_TOKEN_URL_TEMPLATE = "{base_url}/oauth/token"

# Hard-coded for simulated OAuth — in production these come from environment
_CLIENT_ID = "mock-gitlab-client-id"
_CLIENT_SECRET = "mock-gitlab-client-secret"

# Default scopes for GitLab API access
_DEFAULT_SCOPES = ["api", "read_user", "read_repository", "write_repository"]


class GitLabOAuthHandler:
    """Handles GitLab OAuth 2.0 and Personal Access Token authentication.

    Args:
        client_id: GitLab OAuth application client ID.
        client_secret: GitLab OAuth application client secret.
        gitlab_base_url: Base URL of the GitLab instance
            (default: ``'https://gitlab.com'``).
        scopes: List of OAuth scopes to request.
    """

    def __init__(
        self,
        client_id: str = _CLIENT_ID,
        client_secret: str = _CLIENT_SECRET,
        gitlab_base_url: str = "https://gitlab.com",
        scopes: Optional[List[str]] = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.gitlab_base_url = gitlab_base_url.rstrip("/")
        self.scopes = scopes or list(_DEFAULT_SCOPES)

        # In-memory state store: state_nonce → {org_id, created_at}
        self._states: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Step 1: Build authorization URL
    # ------------------------------------------------------------------

    def get_authorization_url(
        self,
        org_id: str,
        redirect_uri: str,
        scopes: Optional[List[str]] = None,
    ) -> str:
        """Build the GitLab OAuth 2.0 authorization URL.

        Generates a secure random state nonce and stores it in memory
        associated with the given ``org_id`` for later verification.

        Args:
            org_id: Agent-Engineers organisation ID (used to correlate the
                OAuth callback with the correct organisation).
            redirect_uri: URL GitLab will redirect to after authorization.
            scopes: Override scopes for this request. Uses instance default
                if ``None``.

        Returns:
            Full authorization URL string.
        """
        state = secrets.token_urlsafe(32)
        self._states[state] = {"org_id": org_id, "created_at": time.time()}
        logger.debug("Generated GitLab OAuth state nonce for org %s", org_id)

        active_scopes = scopes if scopes is not None else self.scopes
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": " ".join(active_scopes),
        }
        base = _AUTH_URL_TEMPLATE.format(base_url=self.gitlab_base_url)
        return f"{base}?{urlencode(params)}"

    # ------------------------------------------------------------------
    # Step 2: Exchange authorization code for tokens
    # ------------------------------------------------------------------

    def exchange_code_for_token(
        self, code: str, redirect_uri: str
    ) -> Dict[str, Any]:
        """Exchange an authorization code for access + refresh tokens (simulated).

        Args:
            code: Authorization code received from GitLab redirect.
            redirect_uri: Must match the URI used in ``get_authorization_url``.

        Returns:
            Token dict with keys:
                ``access_token``, ``refresh_token``, ``token_type``,
                ``expires_in``, ``scope``.
        """
        logger.debug("Exchanging GitLab OAuth code for tokens (simulated)")
        mock_access = hashlib.sha256(f"gitlab:access:{code}".encode()).hexdigest()
        mock_refresh = hashlib.sha256(f"gitlab:refresh:{code}".encode()).hexdigest()
        return {
            "access_token": mock_access,
            "refresh_token": mock_refresh,
            "token_type": "Bearer",
            "expires_in": 7200,
            "scope": " ".join(self.scopes),
            "created_at": int(time.time()),
        }

    # ------------------------------------------------------------------
    # Token refresh
    # ------------------------------------------------------------------

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired access token using a refresh token (simulated).

        Args:
            refresh_token: Refresh token from a previous exchange.

        Returns:
            New token dict (same shape as ``exchange_code_for_token``).
        """
        logger.debug("Refreshing GitLab OAuth token (simulated)")
        new_access = hashlib.sha256(f"gitlab:refreshed:{refresh_token}".encode()).hexdigest()
        new_refresh = hashlib.sha256(
            f"gitlab:new-refresh:{refresh_token}".encode()
        ).hexdigest()
        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "Bearer",
            "expires_in": 7200,
            "scope": " ".join(self.scopes),
            "created_at": int(time.time()),
        }

    # ------------------------------------------------------------------
    # Personal Access Token validation
    # ------------------------------------------------------------------

    def validate_personal_access_token(self, token: str) -> Dict[str, Any]:
        """Validate a GitLab Personal Access Token (simulated).

        In production this would call ``GET /api/v4/personal_access_tokens/self``
        with the token.  Here we return a deterministic mock response.

        Args:
            token: GitLab Personal Access Token.

        Returns:
            Token metadata dict with ``id``, ``name``, ``scopes``, ``expires_at``.
        """
        logger.debug("Validating GitLab PAT (simulated)")
        token_id = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % 100000
        return {
            "id": token_id,
            "name": "Agent-Engineers PAT",
            "scopes": self.scopes,
            "expires_at": None,
            "active": True,
            "revoked": False,
        }

    # ------------------------------------------------------------------
    # State validation helper
    # ------------------------------------------------------------------

    def validate_state(self, state: str, org_id: Optional[str] = None) -> bool:
        """Validate an OAuth state nonce and optionally check the org_id.

        Args:
            state: State nonce from the callback URL parameter.
            org_id: Optional org ID to verify against the stored state.

        Returns:
            ``True`` if the state is valid and (if ``org_id`` given) matches.

        Raises:
            ValueError: If the state is unknown or has expired (> 10 min).
        """
        data = self._states.get(state)
        if data is None:
            raise ValueError(f"Unknown GitLab OAuth state: {state!r}")
        age = time.time() - data["created_at"]
        if age > 600:
            del self._states[state]
            raise ValueError(f"GitLab OAuth state expired (age={age:.0f}s)")
        stored_org = data.get("org_id", "")
        del self._states[state]  # single-use

        if org_id is not None and org_id != stored_org:
            raise ValueError(
                f"GitLab OAuth state org_id mismatch: expected {org_id!r}, "
                f"got {stored_org!r}"
            )
        return True

    def get_state_data(self, state: str) -> Dict[str, Any]:
        """Return state data without consuming it (peek only).

        Raises:
            ValueError: If the state is unknown.
        """
        data = self._states.get(state)
        if data is None:
            raise ValueError(f"Unknown GitLab OAuth state: {state!r}")
        return dict(data)
