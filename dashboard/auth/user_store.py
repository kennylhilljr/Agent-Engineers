"""User storage and management for Agent Dashboard (AI-222).

Provides User dataclass and UserStore for creating, retrieving, and
authenticating users.  Passwords are hashed with bcrypt when available,
falling back to PBKDF2-HMAC-SHA256 from the Python standard library.

Persistence: JSON file at data/users.json (relative to project root).
"""

import hashlib
import json
import logging
import os
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password hashing helpers
# ---------------------------------------------------------------------------

try:
    import bcrypt  # type: ignore

    def _hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def _verify_password_hash(password: str, hashed: str) -> bool:
        """Verify a password against a bcrypt hash."""
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    _HASH_ALGO = "bcrypt"

except ImportError:
    # Stdlib fallback: PBKDF2-HMAC-SHA256 with 600,000 iterations (NIST 2023)
    _HASH_ALGO = "pbkdf2"

    def _hash_password(password: str) -> str:  # type: ignore[misc]
        """Hash a password using PBKDF2-HMAC-SHA256 with a random salt."""
        salt = secrets.token_hex(32)
        iterations = 600_000
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return f"pbkdf2:sha256:{iterations}:{salt}:{dk.hex()}"

    def _verify_password_hash(password: str, hashed: str) -> bool:  # type: ignore[misc]
        """Verify a password against a PBKDF2-HMAC-SHA256 hash.

        Hash format: pbkdf2:sha256:<iterations>:<salt_hex>:<dk_hex>
        """
        if not hashed.startswith("pbkdf2:sha256:"):
            return False
        try:
            # Split into exactly 5 parts
            parts = hashed.split(":", 4)
            if len(parts) != 5:
                return False
            _scheme, algo, iters_str, salt, dk_hex = parts
            iterations = int(iters_str)
            dk = hashlib.pbkdf2_hmac(
                algo,
                password.encode("utf-8"),
                salt.encode("utf-8"),
                iterations,
            )
            return secrets.compare_digest(dk.hex(), dk_hex)
        except Exception:
            return False


# ---------------------------------------------------------------------------
# User dataclass
# ---------------------------------------------------------------------------


@dataclass
class User:
    """Represents a registered user."""

    id: str
    email: str
    name: str
    password_hash: Optional[str]  # None for pure OAuth users
    provider: Optional[str]       # "github", "google", or None for email/password
    provider_id: Optional[str]    # provider-specific user ID
    created_at: str               # ISO-8601 UTC timestamp
    last_login: Optional[str]     # ISO-8601 UTC timestamp or None
    plan: str = "explorer"        # billing plan slug

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "User":
        return cls(
            id=d["id"],
            email=d["email"],
            name=d["name"],
            password_hash=d.get("password_hash"),
            provider=d.get("provider"),
            provider_id=d.get("provider_id"),
            created_at=d["created_at"],
            last_login=d.get("last_login"),
            plan=d.get("plan", "explorer"),
        )

    def public_dict(self) -> Dict:
        """Return user info safe for sending to the browser (no password hash)."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "provider": self.provider,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "plan": self.plan,
        }


# ---------------------------------------------------------------------------
# UserStore
# ---------------------------------------------------------------------------


class UserStore:
    """Manages user accounts with JSON-file persistence.

    Parameters
    ----------
    data_dir:
        Path to the directory containing ``users.json``.
        Defaults to ``<project_root>/data``.
    """

    _DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else self._DEFAULT_DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._users_file = self._data_dir / "users.json"
        self._users: Dict[str, User] = {}          # id -> User
        self._email_index: Dict[str, str] = {}     # email (lower) -> id
        self._provider_index: Dict[str, str] = {}  # "provider:provider_id" -> user_id
        self._load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load users from the JSON file."""
        if not self._users_file.exists():
            return
        try:
            with open(self._users_file, "r", encoding="utf-8") as fh:
                data: List[Dict] = json.load(fh)
            for raw in data:
                user = User.from_dict(raw)
                self._users[user.id] = user
                self._email_index[user.email.lower()] = user.id
                if user.provider and user.provider_id:
                    key = f"{user.provider}:{user.provider_id}"
                    self._provider_index[key] = user.id
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load users.json: %s", exc)

    def _save(self) -> None:
        """Persist users to the JSON file (atomic write)."""
        tmp = self._users_file.with_suffix(".json.tmp")
        try:
            data = [u.to_dict() for u in self._users.values()]
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            tmp.replace(self._users_file)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to save users.json: %s", exc)
            if tmp.exists():
                tmp.unlink()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_user(
        self,
        email: str,
        name: str,
        password: Optional[str] = None,
        provider: Optional[str] = None,
        provider_id: Optional[str] = None,
    ) -> User:
        """Create a new user.

        Parameters
        ----------
        email:   User's email address (must be unique).
        name:    Display name.
        password: Plain-text password (hashed before storage).  Required when
                  no OAuth provider is specified.
        provider: OAuth provider slug ("github" or "google").
        provider_id: The provider's ID for this user.

        Returns
        -------
        The newly-created User.

        Raises
        ------
        ValueError if a user with that email already exists, or if
        neither password nor provider is given.
        """
        if not email:
            raise ValueError("email is required")
        normalized = email.strip().lower()

        if normalized in self._email_index:
            raise ValueError(f"A user with email '{email}' already exists.")

        if password is None and provider is None:
            raise ValueError("Either password or provider must be supplied.")

        password_hash = _hash_password(password) if password else None
        now = datetime.now(timezone.utc).isoformat()

        user = User(
            id=str(uuid.uuid4()),
            email=normalized,
            name=name.strip() or email.split("@")[0],
            password_hash=password_hash,
            provider=provider,
            provider_id=provider_id,
            created_at=now,
            last_login=None,
        )

        self._users[user.id] = user
        self._email_index[normalized] = user.id
        if provider and provider_id:
            self._provider_index[f"{provider}:{provider_id}"] = user.id
        self._save()
        logger.info("Created user %s (%s) via %s", user.id, normalized, provider or "email")
        return user

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Look up a user by email address (case-insensitive)."""
        uid = self._email_index.get(email.strip().lower())
        return self._users.get(uid) if uid else None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Look up a user by their UUID."""
        return self._users.get(user_id)

    def get_or_create_oauth_user(
        self,
        provider: str,
        provider_id: str,
        email: str,
        name: str,
    ) -> User:
        """Return an existing user matched by provider ID, or create one.

        If a user with the same email already exists, link the OAuth provider
        to that account rather than creating a duplicate.
        """
        key = f"{provider}:{provider_id}"
        uid = self._provider_index.get(key)
        if uid:
            user = self._users.get(uid)
            if user:
                return user

        # Try to match by email (link OAuth to existing account)
        existing = self.get_user_by_email(email)
        if existing:
            # Attach OAuth credentials to the existing account
            existing.provider = provider
            existing.provider_id = provider_id
            self._provider_index[key] = existing.id
            self._save()
            return existing

        # Create a brand-new account
        return self.create_user(
            email=email,
            name=name,
            provider=provider,
            provider_id=provider_id,
        )

    def verify_password(self, user: User, password: str) -> bool:
        """Return True if *password* matches the user's stored hash."""
        if not user.password_hash or not password:
            return False
        return _verify_password_hash(password, user.password_hash)

    def update_password(self, user_id: str, new_password: str) -> bool:
        """Hash and save a new password for the given user.  Returns True on success."""
        user = self._users.get(user_id)
        if not user:
            return False
        user.password_hash = _hash_password(new_password)
        self._save()
        return True

    def update_last_login(self, user_id: str) -> None:
        """Record the current UTC time as the user's last login."""
        user = self._users.get(user_id)
        if user:
            user.last_login = datetime.now(timezone.utc).isoformat()
            self._save()

    def all_users(self) -> List[User]:
        """Return a list of all users (admin use only)."""
        return list(self._users.values())
