"""Jira / Atlassian OAuth 2.0 handler (AI-250).

Implements the Atlassian OAuth 2.0 (3LO) authorization code flow.
All token-exchange calls are simulated (mocked) — no real Atlassian
credentials are required.

Reference: https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from typing import Any, Dict, List
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Atlassian OAuth 2.0 endpoints
_AUTH_URL = "https://auth.atlassian.com/authorize"
_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
_ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

# Hard-coded for simulated OAuth — in production these come from environment
_CLIENT_ID = "mock-client-id"
_CLIENT_SECRET = "mock-client-secret"
_SCOPE = "read:jira-work write:jira-work read:jira-user offline_access"


class JiraOAuthHandler:
    """Handles Atlassian OAuth 2.0 (3LO) for Jira integration.

    Args:
        client_id: Atlassian app client ID (defaults to mock value).
        client_secret: Atlassian app client secret (defaults to mock value).
        scope: OAuth scopes to request (defaults to standard Jira scopes).
    """

    def __init__(
        self,
        client_id: str = _CLIENT_ID,
        client_secret: str = _CLIENT_SECRET,
        scope: str = _SCOPE,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope

        # In-memory state store: state_nonce → {org_id, created_at}
        self._states: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Step 1: Build authorization URL
    # ------------------------------------------------------------------

    def get_authorization_url(self, org_id: str, redirect_uri: str) -> str:
        """Build the Atlassian OAuth 2.0 authorization URL.

        Generates a secure random state nonce and stores it in memory
        associated with the given ``org_id`` for later verification.

        Args:
            org_id: Agent-Engineers organisation ID (used to correlate the
                OAuth callback with the correct organisation).
            redirect_uri: URL Atlassian will redirect to after authorization.

        Returns:
            Full authorization URL string.
        """
        state = secrets.token_urlsafe(32)
        self._states[state] = {"org_id": org_id, "created_at": time.time()}
        logger.debug("Generated OAuth state nonce for org %s", org_id)

        params = {
            "audience": "api.atlassian.com",
            "client_id": self.client_id,
            "scope": self.scope,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    # ------------------------------------------------------------------
    # Step 2: Exchange authorization code for tokens
    # ------------------------------------------------------------------

    def exchange_code_for_token(
        self, code: str, redirect_uri: str
    ) -> Dict[str, Any]:
        """Exchange an authorization code for access + refresh tokens (simulated).

        In production this would POST to Atlassian's token endpoint.  Here
        we return a deterministic mock response so tests work without network.

        Args:
            code: Authorization code received from Atlassian redirect.
            redirect_uri: Must match the URI used in ``get_authorization_url``.

        Returns:
            Token dict with keys:
                ``access_token``, ``refresh_token``, ``token_type``,
                ``expires_in``, ``scope``.
        """
        logger.debug("Exchanging OAuth code for tokens (simulated)")
        # Produce a deterministic mock token derived from the code so tests
        # can assert exact values without hitting the network.
        mock_access = hashlib.sha256(f"access:{code}".encode()).hexdigest()
        mock_refresh = hashlib.sha256(f"refresh:{code}".encode()).hexdigest()
        return {
            "access_token": mock_access,
            "refresh_token": mock_refresh,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": self.scope,
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
        logger.debug("Refreshing OAuth token (simulated)")
        new_access = hashlib.sha256(f"refreshed:{refresh_token}".encode()).hexdigest()
        new_refresh = hashlib.sha256(f"new-refresh:{refresh_token}".encode()).hexdigest()
        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": self.scope,
        }

    # ------------------------------------------------------------------
    # Accessible resources
    # ------------------------------------------------------------------

    def get_accessible_resources(self, access_token: str) -> List[Dict[str, Any]]:
        """Return Atlassian cloud sites accessible with the given token (simulated).

        Args:
            access_token: A valid access token.

        Returns:
            List of resource dicts, each with ``id`` (cloud ID), ``url``,
            and ``name``.
        """
        logger.debug("Fetching accessible resources for token (simulated)")
        # In production: GET https://api.atlassian.com/oauth/token/accessible-resources
        # with Authorization: Bearer <access_token>.
        return [
            {
                "id": "mock-cloud-id-001",
                "name": "My Jira Cloud",
                "url": "https://myorg.atlassian.net",
                "scopes": self.scope.split(),
                "avatarUrl": "https://myorg.atlassian.net/avatar.png",
            }
        ]

    # ------------------------------------------------------------------
    # State validation helper
    # ------------------------------------------------------------------

    def validate_state(self, state: str) -> Dict[str, Any]:
        """Validate an OAuth state nonce and return its associated data.

        Args:
            state: State nonce from the callback URL parameter.

        Returns:
            State data dict with ``org_id`` and ``created_at``.

        Raises:
            ValueError: If the state is unknown or has expired (> 10 min).
        """
        data = self._states.get(state)
        if data is None:
            raise ValueError(f"Unknown OAuth state: {state!r}")
        age = time.time() - data["created_at"]
        if age > 600:
            del self._states[state]
            raise ValueError(f"OAuth state expired (age={age:.0f}s)")
        del self._states[state]  # single-use
        return data
