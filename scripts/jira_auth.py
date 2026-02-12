#!/usr/bin/env python3
"""
Jira Auth Manager
==================

Manages Jira authentication with automatic token refresh.
Supports OAuth 2.0 (3LO) as primary auth with Basic Auth fallback.

OAuth tokens are stored in .jira_tokens.json (gitignored).
When OAuth tokens are available, they are used and auto-refreshed.
When not available, falls back to JIRA_EMAIL + JIRA_API_TOKEN from .env.
"""

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
TOKEN_FILE = REPO_ROOT / ".jira_tokens.json"

# Atlassian OAuth 2.0 endpoints
OAUTH_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
OAUTH_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

# Refresh tokens 5 minutes before expiry
TOKEN_EXPIRY_BUFFER = 300


class JiraAuthManager:
    """Manages Jira authentication with OAuth 2.0 auto-refresh and Basic Auth fallback."""

    def __init__(self, token_file: Optional[Path] = None):
        self._token_file = token_file or TOKEN_FILE
        self._lock = Lock()

        # OAuth state (loaded from token file)
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._cloud_id: Optional[str] = None

        # OAuth client credentials (from .env)
        self._client_id = os.environ.get("JIRA_OAUTH_CLIENT_ID", "")
        self._client_secret = os.environ.get("JIRA_OAUTH_CLIENT_SECRET", "")

        # Basic Auth credentials (from .env)
        self._server = os.environ.get("JIRA_SERVER", "").rstrip("/")
        self._email = os.environ.get("JIRA_EMAIL", "")
        self._api_token = os.environ.get("JIRA_API_TOKEN", "")

        # Determine auth mode
        self._oauth_available = False
        self._load_tokens()

        mode = "OAuth 2.0" if self._oauth_available else "Basic Auth"
        logger.info(f"JiraAuthManager initialized with {mode}")

    # -----------------------------------------------------------------
    # Public interface
    # -----------------------------------------------------------------

    @property
    def auth_mode(self) -> str:
        """Current authentication mode: 'oauth' or 'basic'."""
        return "oauth" if self._oauth_available else "basic"

    def get_auth_headers(self) -> dict:
        """Return Authorization headers for Jira API requests.

        If OAuth is available and token is fresh, uses Bearer token.
        If OAuth token is expiring, refreshes it first.
        If OAuth fails entirely, falls back to Basic Auth.
        """
        with self._lock:
            if self._oauth_available:
                try:
                    if self._is_token_expired():
                        self._refresh_oauth_token()
                    return {
                        "Authorization": f"Bearer {self._access_token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    }
                except Exception as e:
                    logger.warning(f"OAuth token refresh failed: {e}. Falling back to Basic Auth.")
                    self._oauth_available = False

            return self._get_basic_auth_headers()

    def get_base_url(self) -> str:
        """Return the base URL for Jira API requests.

        OAuth uses: https://api.atlassian.com/ex/jira/{cloud_id}
        Basic uses: JIRA_SERVER from .env
        """
        if self._oauth_available and self._cloud_id:
            return f"https://api.atlassian.com/ex/jira/{self._cloud_id}"
        return self._server

    def invalidate_token(self) -> None:
        """Mark the current token as invalid, forcing a refresh on next use."""
        with self._lock:
            if self._oauth_available:
                self._token_expiry = 0.0
                logger.info("OAuth token invalidated, will refresh on next request")

    def try_restore_oauth(self) -> bool:
        """Attempt to restore OAuth auth by re-loading and refreshing tokens.

        Called by the circuit breaker's recovery logic to see if OAuth
        can be re-established after a Basic Auth period.
        """
        with self._lock:
            self._load_tokens()
            if self._refresh_token and self._client_id and self._client_secret:
                try:
                    self._refresh_oauth_token()
                    self._oauth_available = True
                    logger.info("OAuth auth restored successfully")
                    return True
                except Exception as e:
                    logger.debug(f"OAuth restore failed: {e}")
            return False

    # -----------------------------------------------------------------
    # Token file I/O
    # -----------------------------------------------------------------

    def _load_tokens(self) -> None:
        """Load OAuth tokens from the token file."""
        if not self._token_file.exists():
            logger.debug(f"No token file at {self._token_file}")
            return

        try:
            data = json.loads(self._token_file.read_text())
            self._access_token = data.get("access_token")
            self._refresh_token = data.get("refresh_token")
            self._token_expiry = data.get("expires_at", 0.0)
            self._cloud_id = data.get("cloud_id")

            if self._access_token and self._refresh_token and self._cloud_id:
                self._oauth_available = True
                logger.debug("OAuth tokens loaded from file")
            else:
                logger.debug("Token file incomplete, OAuth not available")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load token file: {e}")

    def _save_tokens(self) -> None:
        """Persist OAuth tokens to the token file."""
        data = {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "expires_at": self._token_expiry,
            "cloud_id": self._cloud_id,
            "updated_at": time.time(),
        }
        try:
            self._token_file.write_text(json.dumps(data, indent=2))
            logger.debug("OAuth tokens saved to file")
        except OSError as e:
            logger.error(f"Failed to save token file: {e}")

    # -----------------------------------------------------------------
    # OAuth token refresh
    # -----------------------------------------------------------------

    def _is_token_expired(self) -> bool:
        """Check if the access token is expired or about to expire."""
        return time.time() >= (self._token_expiry - TOKEN_EXPIRY_BUFFER)

    def _refresh_oauth_token(self) -> None:
        """Refresh the OAuth access token using the refresh token.

        Atlassian refresh tokens rotate — the response includes a new
        refresh token that must be saved for next time.
        """
        if not self._refresh_token:
            raise ValueError("No refresh token available")
        if not self._client_id or not self._client_secret:
            raise ValueError("JIRA_OAUTH_CLIENT_ID and JIRA_OAUTH_CLIENT_SECRET required")

        body = json.dumps({
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
        }).encode()

        req = urllib.request.Request(
            OAUTH_TOKEN_URL,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            logger.error(f"OAuth refresh failed ({e.code}): {error_body[:300]}")
            raise RuntimeError(f"OAuth token refresh failed: HTTP {e.code}") from e

        self._access_token = data["access_token"]
        # Atlassian rotates refresh tokens
        if "refresh_token" in data:
            self._refresh_token = data["refresh_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expiry = time.time() + expires_in

        self._save_tokens()
        logger.info(f"OAuth token refreshed, expires in {expires_in}s")

    # -----------------------------------------------------------------
    # Basic Auth fallback
    # -----------------------------------------------------------------

    def _get_basic_auth_headers(self) -> dict:
        """Return Basic Auth headers from .env credentials."""
        if not self._email or not self._api_token:
            raise ValueError("JIRA_EMAIL and JIRA_API_TOKEN must be set for Basic Auth")

        encoded = base64.b64encode(f"{self._email}:{self._api_token}".encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # -----------------------------------------------------------------
    # Save initial tokens (used by jira_oauth_setup.py)
    # -----------------------------------------------------------------

    def save_initial_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        cloud_id: str,
    ) -> None:
        """Save tokens from the initial OAuth consent flow."""
        with self._lock:
            self._access_token = access_token
            self._refresh_token = refresh_token
            self._token_expiry = time.time() + expires_in
            self._cloud_id = cloud_id
            self._oauth_available = True
            self._save_tokens()
            logger.info("Initial OAuth tokens saved")
