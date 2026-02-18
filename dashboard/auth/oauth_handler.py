"""OAuth handler for GitHub and Google OAuth flows (AI-222).

Reads credentials from environment variables:
  GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET
  GOOGLE_CLIENT_ID  / GOOGLE_CLIENT_SECRET

If the env vars are not set, all methods raise OAuthNotConfiguredError.

Redirect URIs are configurable via:
  OAUTH_REDIRECT_BASE  (e.g. "http://localhost:8420" or "https://example.com")
  Falls back to "http://localhost:8420".
"""

import logging
import os
import secrets
from typing import Dict, Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class OAuthNotConfiguredError(Exception):
    """Raised when the required OAuth env vars are not set."""


class OAuthHandler:
    """Handles GitHub and Google OAuth 2.0 authorization code flows.

    Parameters
    ----------
    redirect_base:
        Base URL for OAuth callback URIs.
        Defaults to ``OAUTH_REDIRECT_BASE`` env var or ``http://localhost:8420``.
    """

    GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
    GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
    GITHUB_USER_URL = "https://api.github.com/user"
    GITHUB_EMAILS_URL = "https://api.github.com/user/emails"

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USER_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    def __init__(self, redirect_base: Optional[str] = None) -> None:
        self._redirect_base = (
            redirect_base
            or os.getenv("OAUTH_REDIRECT_BASE", "http://localhost:8420")
        ).rstrip("/")

    # ------------------------------------------------------------------
    # Configuration checks
    # ------------------------------------------------------------------

    def is_github_configured(self) -> bool:
        """Return True if GitHub OAuth env vars are set."""
        return bool(os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET"))

    def is_google_configured(self) -> bool:
        """Return True if Google OAuth env vars are set."""
        return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))

    def _require_github(self) -> tuple[str, str]:
        client_id = os.getenv("GITHUB_CLIENT_ID")
        client_secret = os.getenv("GITHUB_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise OAuthNotConfiguredError(
                "GitHub OAuth is not configured. "
                "Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment variables."
            )
        return client_id, client_secret

    def _require_google(self) -> tuple[str, str]:
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise OAuthNotConfiguredError(
                "Google OAuth is not configured. "
                "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables."
            )
        return client_id, client_secret

    # ------------------------------------------------------------------
    # GitHub OAuth
    # ------------------------------------------------------------------

    def get_github_auth_url(self, state: str) -> str:
        """Return the GitHub authorization URL for the given *state* nonce.

        Raises OAuthNotConfiguredError if env vars are not set.
        """
        client_id, _ = self._require_github()
        callback_uri = f"{self._redirect_base}/auth/github/callback"
        params = urlencode({
            "client_id": client_id,
            "redirect_uri": callback_uri,
            "scope": "user:email read:user",
            "state": state,
        })
        return f"{self.GITHUB_AUTH_URL}?{params}"

    async def exchange_github_code(self, code: str, state: str) -> Dict:
        """Exchange an authorization code for an access token and user info.

        Returns
        -------
        dict with keys: user_info (dict with id, email, name), access_token
        """
        import aiohttp  # lazy import - avoid ImportError at module load time

        client_id, client_secret = self._require_github()
        callback_uri = f"{self._redirect_base}/auth/github/callback"

        # Exchange code for token
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": callback_uri,
                    "state": state,
                },
            ) as resp:
                token_data = await resp.json()

        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError(f"GitHub token exchange failed: {token_data}")

        # Fetch user profile
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }
            async with session.get(self.GITHUB_USER_URL, headers=headers) as resp:
                user_data = await resp.json()

            # Fetch primary email if not in profile
            email = user_data.get("email")
            if not email:
                async with session.get(self.GITHUB_EMAILS_URL, headers=headers) as resp:
                    emails = await resp.json()
                for entry in emails:
                    if isinstance(entry, dict) and entry.get("primary") and entry.get("verified"):
                        email = entry["email"]
                        break
                if not email and emails:
                    first = emails[0]
                    email = first.get("email") if isinstance(first, dict) else None

        return {
            "user_info": {
                "id": str(user_data.get("id", "")),
                "email": email or f"{user_data.get('login', 'github-user')}@github.noemail",
                "name": user_data.get("name") or user_data.get("login") or "GitHub User",
            },
            "access_token": access_token,
        }

    # ------------------------------------------------------------------
    # Google OAuth
    # ------------------------------------------------------------------

    def get_google_auth_url(self, state: str) -> str:
        """Return the Google authorization URL for the given *state* nonce.

        Raises OAuthNotConfiguredError if env vars are not set.
        """
        client_id, _ = self._require_google()
        callback_uri = f"{self._redirect_base}/auth/google/callback"
        params = urlencode({
            "client_id": client_id,
            "redirect_uri": callback_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
        })
        return f"{self.GOOGLE_AUTH_URL}?{params}"

    async def exchange_google_code(self, code: str, state: str) -> Dict:
        """Exchange an authorization code for an access token and user info.

        Returns
        -------
        dict with keys: user_info (dict with id, email, name), access_token
        """
        import aiohttp  # lazy import

        client_id, client_secret = self._require_google()
        callback_uri = f"{self._redirect_base}/auth/google/callback"

        # Exchange code for token
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": callback_uri,
                    "grant_type": "authorization_code",
                },
            ) as resp:
                token_data = await resp.json()

        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError(f"Google token exchange failed: {token_data}")

        # Fetch user profile
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.GOOGLE_USER_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            ) as resp:
                user_data = await resp.json()

        return {
            "user_info": {
                "id": user_data.get("sub", ""),
                "email": user_data.get("email", ""),
                "name": user_data.get("name", "Google User"),
            },
            "access_token": access_token,
        }

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_state() -> str:
        """Generate a cryptographically random state parameter for CSRF protection."""
        return secrets.token_urlsafe(32)
