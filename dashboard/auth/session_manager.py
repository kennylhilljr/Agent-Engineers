"""Session management for Agent Dashboard (AI-222).

Manages user sessions with:
- 30-day expiry
- HMAC-signed tokens (no third-party JWT library needed, but PyJWT is used
  when available)
- CSRF protection via double-submit cookie pattern
- Rate limiting: max 5 failed login attempts per IP per 15 minutes
- JSON-file persistence for sessions

Token format (stdlib fallback):
    <session_id>.<hmac_signature_hex>
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_EXPIRY_DAYS = 30
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 15 * 60  # 15 minutes

# ---------------------------------------------------------------------------
# Session dataclass (plain dict for simplicity + JSON compat)
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utcnow_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


class SessionManager:
    """Manages user sessions.

    Parameters
    ----------
    data_dir:
        Directory for sessions.json.  Defaults to <project_root>/data.
    secret_key:
        HMAC secret used for signing session tokens.  Falls back to the
        ``SESSION_SECRET_KEY`` environment variable, then generates a random
        key (ephemeral - sessions won't survive restart without a persistent
        key set via the env var).
    """

    _DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        secret_key: Optional[str] = None,
    ) -> None:
        self._data_dir = Path(data_dir) if data_dir else self._DEFAULT_DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._sessions_file = self._data_dir / "sessions.json"

        self._secret = (
            secret_key
            or os.getenv("SESSION_SECRET_KEY")
            or secrets.token_hex(64)
        )

        # {token -> session_dict}
        self._sessions: Dict[str, Dict] = {}
        # {ip -> [(timestamp, success)]}
        self._attempt_log: Dict[str, List[float]] = defaultdict(list)

        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._sessions_file.exists():
            return
        try:
            with open(self._sessions_file, "r", encoding="utf-8") as fh:
                raw: Dict[str, Dict] = json.load(fh)
            self._sessions = raw
            # Prune expired sessions on load
            self.cleanup_expired_sessions()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load sessions.json: %s", exc)

    def _save(self) -> None:
        tmp = self._sessions_file.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._sessions, fh, indent=2)
            tmp.replace(self._sessions_file)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to save sessions.json: %s", exc)
            if tmp.exists():
                tmp.unlink()

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _sign_token(self, session_id: str) -> str:
        """Return a signed token: <session_id>.<hex_sig>"""
        sig = hmac.new(
            self._secret.encode("utf-8"),
            session_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{session_id}.{sig}"

    def _verify_token(self, token: str) -> Optional[str]:
        """Validate a signed token; return the session_id on success, else None."""
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return None
        session_id, provided_sig = parts
        expected_sig = hmac.new(
            self._secret.encode("utf-8"),
            session_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if secrets.compare_digest(provided_sig, expected_sig):
            return session_id
        return None

    # ------------------------------------------------------------------
    # CSRF helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_csrf_token() -> str:
        """Generate a random CSRF token."""
        return secrets.token_urlsafe(32)

    def validate_csrf(self, session_token: str, submitted_csrf: str) -> bool:
        """Verify that the submitted CSRF token matches the one in the session."""
        session_id = self._verify_token(session_token)
        if not session_id:
            return False
        session = self._sessions.get(session_id)
        if not session:
            return False
        stored_csrf = session.get("csrf_token", "")
        if not stored_csrf or not submitted_csrf:
            return False
        return secrets.compare_digest(stored_csrf, submitted_csrf)

    # ------------------------------------------------------------------
    # Core session operations
    # ------------------------------------------------------------------

    def create_session(self, user_id: str, ip_address: str = "unknown") -> Dict:
        """Create a new session for *user_id*.

        Returns
        -------
        dict with keys: token, expires_at, csrf_token
        """
        session_id = str(uuid.uuid4())
        token = self._sign_token(session_id)
        expires_ts = _utcnow_ts() + SESSION_EXPIRY_DAYS * 86400
        expires_at = datetime.fromtimestamp(expires_ts, tz=timezone.utc).isoformat()
        csrf_token = self.generate_csrf_token()

        self._sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "ip_address": ip_address,
            "created_at": _utcnow_iso(),
            "expires_at": expires_at,
            "expires_ts": expires_ts,
            "csrf_token": csrf_token,
        }
        self._save()

        return {
            "token": token,
            "expires_at": expires_at,
            "csrf_token": csrf_token,
        }

    def validate_session(self, token: str) -> Optional[str]:
        """Validate *token* and return the user_id, or None if invalid/expired."""
        session_id = self._verify_token(token)
        if not session_id:
            return None

        session = self._sessions.get(session_id)
        if not session:
            return None

        # Check expiry
        expires_ts = session.get("expires_ts", 0)
        if _utcnow_ts() > expires_ts:
            # Expired - remove it
            del self._sessions[session_id]
            self._save()
            return None

        return session["user_id"]

    def get_session(self, token: str) -> Optional[Dict]:
        """Return the full session dict for *token*, or None."""
        session_id = self._verify_token(token)
        if not session_id:
            return None
        session = self._sessions.get(session_id)
        if not session:
            return None
        if _utcnow_ts() > session.get("expires_ts", 0):
            del self._sessions[session_id]
            self._save()
            return None
        return session

    def invalidate_session(self, token: str) -> bool:
        """Invalidate (delete) a session.  Returns True if found and removed."""
        session_id = self._verify_token(token)
        if session_id and session_id in self._sessions:
            del self._sessions[session_id]
            self._save()
            return True
        return False

    def invalidate_all_user_sessions(self, user_id: str) -> int:
        """Remove all sessions for *user_id*.  Returns count removed."""
        to_delete = [
            sid for sid, s in self._sessions.items()
            if s.get("user_id") == user_id
        ]
        for sid in to_delete:
            del self._sessions[sid]
        if to_delete:
            self._save()
        return len(to_delete)

    def cleanup_expired_sessions(self) -> int:
        """Remove all expired sessions.  Returns count removed."""
        now = _utcnow_ts()
        expired = [
            sid for sid, s in self._sessions.items()
            if s.get("expires_ts", 0) < now
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            self._save()
        return len(expired)

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def record_failed_attempt(self, ip_address: str) -> None:
        """Record a failed login attempt for the given IP."""
        now = _utcnow_ts()
        self._attempt_log[ip_address].append(now)
        # Prune old entries outside the window
        window_start = now - RATE_LIMIT_WINDOW_SECONDS
        self._attempt_log[ip_address] = [
            t for t in self._attempt_log[ip_address] if t >= window_start
        ]

    def is_rate_limited(self, ip_address: str) -> bool:
        """Return True if the IP has exceeded the failed-attempt threshold."""
        now = _utcnow_ts()
        window_start = now - RATE_LIMIT_WINDOW_SECONDS
        recent = [
            t for t in self._attempt_log.get(ip_address, [])
            if t >= window_start
        ]
        return len(recent) >= RATE_LIMIT_MAX_ATTEMPTS

    def clear_rate_limit(self, ip_address: str) -> None:
        """Clear failed-attempt records for an IP (called on successful login)."""
        self._attempt_log.pop(ip_address, None)

    def remaining_attempts(self, ip_address: str) -> int:
        """Return how many more attempts the IP has before being rate-limited."""
        now = _utcnow_ts()
        window_start = now - RATE_LIMIT_WINDOW_SECONDS
        recent = [
            t for t in self._attempt_log.get(ip_address, [])
            if t >= window_start
        ]
        return max(0, RATE_LIMIT_MAX_ATTEMPTS - len(recent))
