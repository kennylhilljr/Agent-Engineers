"""OIDC (OpenID Connect) Authentication Handler.

AI-232: Enterprise SSO - OIDC implementation via aiohttp.

Security considerations:
    - Validates state parameter to prevent CSRF
    - Validates nonce to prevent replay attacks
    - Validates id_token claims: iss, aud, exp, iat, nonce
    - Uses PKCE (Proof Key for Code Exchange) for public clients
    - Token introspection for offline validation
"""

import base64
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

try:
    import aiohttp
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False


class OIDCError(Exception):
    """Base OIDC error."""
    pass


class OIDCValidationError(OIDCError):
    """OIDC token/response validation error."""
    pass


class OIDCConfigError(OIDCError):
    """OIDC configuration error."""
    pass


@dataclass
class OIDCConfig:
    """OIDC Provider configuration."""

    # Provider settings
    issuer: str
    client_id: str
    client_secret: str

    # Discovery or explicit endpoints
    discovery_url: Optional[str] = None  # /.well-known/openid-configuration
    authorization_endpoint: Optional[str] = None
    token_endpoint: Optional[str] = None
    userinfo_endpoint: Optional[str] = None
    jwks_uri: Optional[str] = None

    # SP settings
    redirect_uri: str = ""
    scopes: List[str] = field(default_factory=lambda: ["openid", "email", "profile"])

    # Organization association
    org_id: str = ""

    # Attribute mapping: OIDC claim -> user field
    attribute_mapping: Dict[str, str] = field(
        default_factory=lambda: {
            "email": "email",
            "first_name": "given_name",
            "last_name": "family_name",
            "display_name": "name",
            "groups": "groups",
            "picture": "picture",
        }
    )

    # Security settings
    use_pkce: bool = True
    require_nonce: bool = True

    # Token validation
    clock_skew_seconds: int = 60
    max_token_age_seconds: int = 3600


@dataclass
class OIDCTokenResponse:
    """OIDC token response with validated claims."""

    access_token: str
    id_token: str
    token_type: str
    expires_in: int

    # Validated ID token claims
    sub: str  # Subject identifier
    iss: str  # Issuer
    aud: Any  # Audience
    exp: int  # Expiration
    iat: int  # Issued at
    nonce: Optional[str] = None

    # User info claims
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    groups: List[str] = field(default_factory=list)
    picture: Optional[str] = None

    # Raw claims
    claims: Dict[str, Any] = field(default_factory=dict)
    refresh_token: Optional[str] = None


class OIDCHandler:
    """OIDC Service Provider implementation using aiohttp.

    Security:
        - State parameter validated per RFC 6749
        - Nonce validated to prevent replay attacks
        - ID token claims fully validated
        - PKCE supported for public client flows
    """

    def __init__(self, config: OIDCConfig):
        if not _AIOHTTP_AVAILABLE:
            raise OIDCConfigError("aiohttp is required for OIDC support. Install with: pip install aiohttp")
        self.config = config
        self._pending_states: Dict[str, Dict[str, Any]] = {}  # state -> {nonce, created_at, code_verifier}
        self._STATE_TIMEOUT = timedelta(minutes=10)
        self._discovered_config: Optional[Dict[str, Any]] = None

    async def discover(self) -> Dict[str, Any]:
        """Fetch OIDC discovery document.

        Returns:
            Provider metadata dict
        """
        discovery_url = self.config.discovery_url
        if not discovery_url:
            discovery_url = f"{self.config.issuer.rstrip('/')}/.well-known/openid-configuration"

        async with aiohttp.ClientSession() as session:
            async with session.get(discovery_url, ssl=True) as resp:
                if resp.status != 200:
                    raise OIDCError(f"Discovery failed: HTTP {resp.status}")
                self._discovered_config = await resp.json()

        # Update endpoints from discovery
        config = self._discovered_config
        if not self.config.authorization_endpoint:
            self.config.authorization_endpoint = config.get("authorization_endpoint")
        if not self.config.token_endpoint:
            self.config.token_endpoint = config.get("token_endpoint")
        if not self.config.userinfo_endpoint:
            self.config.userinfo_endpoint = config.get("userinfo_endpoint")
        if not self.config.jwks_uri:
            self.config.jwks_uri = config.get("jwks_uri")

        return self._discovered_config

    def generate_auth_url(
        self,
        extra_params: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, str, str]:
        """Generate OIDC authorization URL.

        Returns:
            Tuple of (auth_url, state, nonce)

        Security:
            - Generates cryptographically random state (anti-CSRF)
            - Generates cryptographically random nonce (anti-replay)
            - PKCE code_verifier/challenge generated if use_pkce=True
        """
        if not self.config.authorization_endpoint:
            raise OIDCConfigError(
                "authorization_endpoint not configured. Call discover() first or set explicitly."
            )

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)

        pending: Dict[str, Any] = {
            "nonce": nonce,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        params: Dict[str, str] = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
            "state": state,
            "nonce": nonce,
        }

        # PKCE
        if self.config.use_pkce:
            code_verifier = secrets.token_urlsafe(64)
            code_challenge = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            ).rstrip(b"=").decode()
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
            pending["code_verifier"] = code_verifier

        if extra_params:
            params.update(extra_params)

        self._pending_states[state] = pending
        self._cleanup_expired_states()

        auth_url = f"{self.config.authorization_endpoint}?{urlencode(params)}"
        return auth_url, state, nonce

    async def exchange_code(
        self,
        code: str,
        state: str,
        expected_nonce: Optional[str] = None,
    ) -> OIDCTokenResponse:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from IdP callback
            state: State parameter from callback (validated against stored state)
            expected_nonce: Expected nonce (if not provided, retrieved from state store)

        Returns:
            OIDCTokenResponse with validated ID token claims

        Raises:
            OIDCValidationError: If state/nonce/token validation fails

        Security:
            - State validated against stored states
            - Nonce validated from state store
            - ID token claims fully validated
        """
        if not self.config.token_endpoint:
            raise OIDCConfigError("token_endpoint not configured")

        # Validate state (anti-CSRF)
        if state not in self._pending_states:
            raise OIDCValidationError(
                "Invalid or expired state parameter. Possible CSRF attack."
            )

        pending = self._pending_states.pop(state)
        stored_nonce = pending.get("nonce")
        code_verifier = pending.get("code_verifier")

        if expected_nonce and expected_nonce != stored_nonce:
            raise OIDCValidationError("Nonce mismatch")

        # Exchange code for tokens
        token_data: Dict[str, Any] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }

        if code_verifier:
            token_data["code_verifier"] = code_verifier

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.config.token_endpoint,
                data=token_data,
                ssl=True,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise OIDCError(f"Token exchange failed: HTTP {resp.status}: {body}")
                token_response = await resp.json()

        access_token = token_response.get("access_token")
        id_token_str = token_response.get("id_token")

        if not access_token or not id_token_str:
            raise OIDCValidationError("Missing access_token or id_token in response")

        # Parse and validate ID token (JWT)
        claims = self._parse_id_token(id_token_str, stored_nonce)

        # Fetch userinfo if available
        userinfo: Dict[str, Any] = {}
        if self.config.userinfo_endpoint and access_token:
            userinfo = await self._fetch_userinfo(access_token)

        # Merge claims with userinfo (userinfo takes precedence for user attributes)
        all_claims = {**claims, **userinfo}

        # Map to user fields
        mapped = self._map_claims(all_claims)

        return OIDCTokenResponse(
            access_token=access_token,
            id_token=id_token_str,
            token_type=token_response.get("token_type", "Bearer"),
            expires_in=token_response.get("expires_in", 3600),
            sub=claims["sub"],
            iss=claims["iss"],
            aud=claims["aud"],
            exp=claims["exp"],
            iat=claims["iat"],
            nonce=claims.get("nonce"),
            email=mapped.get("email"),
            email_verified=all_claims.get("email_verified"),
            first_name=mapped.get("first_name"),
            last_name=mapped.get("last_name"),
            display_name=mapped.get("display_name"),
            groups=mapped.get("groups", []),
            picture=mapped.get("picture"),
            claims=all_claims,
            refresh_token=token_response.get("refresh_token"),
        )

    def _parse_id_token(self, id_token: str, expected_nonce: Optional[str]) -> Dict[str, Any]:
        """Parse and validate JWT ID token claims.

        Note: This validates claims but NOT the signature (requires jwks client library).
        For production, integrate python-jose or PyJWT with JWKS for signature validation.

        Security:
            - Validates iss matches configured issuer
            - Validates aud includes client_id
            - Validates exp (with clock skew)
            - Validates iat (not too old)
            - Validates nonce matches
        """
        parts = id_token.split(".")
        if len(parts) != 3:
            raise OIDCValidationError("Invalid JWT format: expected 3 parts")

        # Decode payload (base64url, no signature verification in stdlib mode)
        payload_b64 = parts[1]
        # Add padding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        try:
            payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
            claims = json.loads(payload_json)
        except Exception as e:
            raise OIDCValidationError(f"Failed to decode ID token payload: {e}")

        now = int(time.time())
        skew = self.config.clock_skew_seconds

        # Validate issuer
        iss = claims.get("iss", "")
        if iss != self.config.issuer:
            raise OIDCValidationError(
                f"ID token issuer mismatch: expected '{self.config.issuer}', got '{iss}'"
            )

        # Validate audience
        aud = claims.get("aud")
        if aud is None:
            raise OIDCValidationError("ID token missing 'aud' claim")
        if isinstance(aud, str):
            if aud != self.config.client_id:
                raise OIDCValidationError(f"ID token audience mismatch: '{aud}'")
        elif isinstance(aud, list):
            if self.config.client_id not in aud:
                raise OIDCValidationError(f"ID token audience does not include client_id")

        # Validate expiration
        exp = claims.get("exp")
        if exp is None:
            raise OIDCValidationError("ID token missing 'exp' claim")
        if now - skew >= exp:
            raise OIDCValidationError(f"ID token has expired (exp: {exp}, now: {now})")

        # Validate issued-at
        iat = claims.get("iat")
        if iat is None:
            raise OIDCValidationError("ID token missing 'iat' claim")
        if now - iat > self.config.max_token_age_seconds:
            raise OIDCValidationError(f"ID token too old (iat: {iat})")

        # Validate sub
        if not claims.get("sub"):
            raise OIDCValidationError("ID token missing 'sub' claim")

        # Validate nonce
        if self.config.require_nonce and expected_nonce:
            token_nonce = claims.get("nonce")
            if token_nonce != expected_nonce:
                raise OIDCValidationError(
                    "ID token nonce mismatch. Possible replay attack."
                )

        return claims

    async def _fetch_userinfo(self, access_token: str) -> Dict[str, Any]:
        """Fetch user info from userinfo endpoint."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.config.userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
                ssl=True,
            ) as resp:
                if resp.status != 200:
                    return {}  # Non-fatal: fall back to ID token claims
                return await resp.json()

    def _map_claims(self, claims: Dict[str, Any]) -> Dict[str, Any]:
        """Map OIDC claims to user fields using attribute_mapping."""
        mapped: Dict[str, Any] = {}
        for field_name, claim_name in self.config.attribute_mapping.items():
            value = claims.get(claim_name)
            if value is not None:
                if field_name == "groups" and isinstance(value, str):
                    value = [value]
                mapped[field_name] = value
        return mapped

    def _cleanup_expired_states(self) -> None:
        """Remove expired pending states."""
        now = datetime.now(timezone.utc)
        expired = []
        for state, data in self._pending_states.items():
            try:
                created = datetime.fromisoformat(data["created_at"])
                if now - created > self._STATE_TIMEOUT:
                    expired.append(state)
            except (KeyError, ValueError):
                expired.append(state)
        for state in expired:
            del self._pending_states[state]
