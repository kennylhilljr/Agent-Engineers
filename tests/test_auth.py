"""Tests for AI-222: User Authentication - OAuth + Email/Password.

Covers:
- UserStore: create, get, verify, OAuth user handling, password management
- SessionManager: create, validate, invalidate, expiry, rate limiting, CSRF
- OAuthHandler: configuration checks, URL generation, error handling
- API endpoints: login, logout, register, me, password-reset, change-password
- Rate limiting behavior
- CSRF token validation
"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temporary directory for test data files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def user_store(tmp_data_dir):
    """Fresh UserStore backed by a temp directory."""
    from dashboard.auth.user_store import UserStore
    return UserStore(data_dir=tmp_data_dir)


@pytest.fixture
def session_manager(tmp_data_dir):
    """Fresh SessionManager with a known secret key."""
    from dashboard.auth.session_manager import SessionManager
    return SessionManager(data_dir=tmp_data_dir, secret_key="test-secret-key-12345")


@pytest.fixture
def oauth_handler():
    """OAuthHandler with a fixed redirect base."""
    from dashboard.auth.oauth_handler import OAuthHandler
    return OAuthHandler(redirect_base="http://localhost:8420")


# ---------------------------------------------------------------------------
# UserStore tests
# ---------------------------------------------------------------------------


class TestUserStore:

    def test_create_user_email_password(self, user_store):
        """Creating a user with email+password stores the user."""
        user = user_store.create_user(
            email="alice@example.com",
            name="Alice",
            password="secretpass123"
        )
        assert user.id
        assert user.email == "alice@example.com"
        assert user.name == "Alice"
        assert user.password_hash is not None
        assert "secretpass123" not in user.password_hash  # must be hashed
        assert user.provider is None
        assert user.plan == "explorer"

    def test_create_user_email_normalized(self, user_store):
        """Email addresses are stored in lowercase."""
        user = user_store.create_user(email="ALICE@EXAMPLE.COM", name="Alice", password="pass1234")
        assert user.email == "alice@example.com"

    def test_create_user_duplicate_email_raises(self, user_store):
        """Duplicate email raises ValueError."""
        user_store.create_user(email="alice@example.com", name="Alice", password="pass1234")
        with pytest.raises(ValueError, match="already exists"):
            user_store.create_user(email="alice@example.com", name="Alice2", password="pass5678")

    def test_create_user_no_password_no_provider_raises(self, user_store):
        """Creating a user without password and without provider raises ValueError."""
        with pytest.raises(ValueError, match="password or provider"):
            user_store.create_user(email="noauth@example.com", name="NoAuth")

    def test_create_oauth_user(self, user_store):
        """Creating a user via OAuth stores provider info."""
        user = user_store.create_user(
            email="bob@github.com",
            name="Bob",
            provider="github",
            provider_id="gh-12345",
        )
        assert user.provider == "github"
        assert user.provider_id == "gh-12345"
        assert user.password_hash is None

    def test_get_user_by_email(self, user_store):
        """Can retrieve a user by email (case-insensitive)."""
        created = user_store.create_user(email="alice@example.com", name="Alice", password="pass1234")
        found = user_store.get_user_by_email("Alice@Example.COM")
        assert found is not None
        assert found.id == created.id

    def test_get_user_by_email_not_found(self, user_store):
        """Returns None for unknown email."""
        assert user_store.get_user_by_email("nobody@example.com") is None

    def test_get_user_by_id(self, user_store):
        """Can retrieve a user by ID."""
        created = user_store.create_user(email="alice@example.com", name="Alice", password="pass1234")
        found = user_store.get_user_by_id(created.id)
        assert found is not None
        assert found.email == "alice@example.com"

    def test_get_user_by_id_not_found(self, user_store):
        """Returns None for unknown user ID."""
        assert user_store.get_user_by_id("00000000-0000-0000-0000-000000000000") is None

    def test_verify_password_correct(self, user_store):
        """verify_password returns True for the correct password."""
        user = user_store.create_user(email="alice@example.com", name="Alice", password="pass1234")
        assert user_store.verify_password(user, "pass1234") is True

    def test_verify_password_incorrect(self, user_store):
        """verify_password returns False for the wrong password."""
        user = user_store.create_user(email="alice@example.com", name="Alice", password="pass1234")
        assert user_store.verify_password(user, "wrongpassword") is False

    def test_verify_password_empty(self, user_store):
        """verify_password returns False for an empty password."""
        user = user_store.create_user(email="alice@example.com", name="Alice", password="pass1234")
        assert user_store.verify_password(user, "") is False

    def test_verify_password_oauth_user(self, user_store):
        """verify_password returns False for OAuth users with no password hash."""
        user = user_store.create_user(
            email="bob@github.com", name="Bob", provider="github", provider_id="123"
        )
        assert user_store.verify_password(user, "anything") is False

    def test_update_last_login(self, user_store):
        """update_last_login sets a last_login timestamp."""
        user = user_store.create_user(email="alice@example.com", name="Alice", password="pass1234")
        assert user.last_login is None
        user_store.update_last_login(user.id)
        updated = user_store.get_user_by_id(user.id)
        assert updated.last_login is not None

    def test_update_password(self, user_store):
        """update_password changes the password hash."""
        user = user_store.create_user(email="alice@example.com", name="Alice", password="oldpass1")
        assert user_store.verify_password(user, "oldpass1") is True
        user_store.update_password(user.id, "newpass99")
        updated = user_store.get_user_by_id(user.id)
        assert user_store.verify_password(updated, "newpass99") is True
        assert user_store.verify_password(updated, "oldpass1") is False

    def test_persistence(self, tmp_data_dir):
        """Users survive a round-trip through the JSON file."""
        from dashboard.auth.user_store import UserStore
        store1 = UserStore(data_dir=tmp_data_dir)
        user = store1.create_user(email="persist@example.com", name="Persisted", password="testpass")

        store2 = UserStore(data_dir=tmp_data_dir)
        found = store2.get_user_by_id(user.id)
        assert found is not None
        assert found.email == "persist@example.com"

    def test_get_or_create_oauth_user_creates_new(self, user_store):
        """get_or_create_oauth_user creates a new account if none exists."""
        user = user_store.get_or_create_oauth_user(
            provider="github",
            provider_id="gh-999",
            email="newuser@github.com",
            name="New User",
        )
        assert user.provider == "github"
        assert user.provider_id == "gh-999"

    def test_get_or_create_oauth_user_returns_existing(self, user_store):
        """get_or_create_oauth_user returns the same user on repeated calls."""
        user1 = user_store.get_or_create_oauth_user(
            provider="github", provider_id="gh-999", email="existing@github.com", name="Existing"
        )
        user2 = user_store.get_or_create_oauth_user(
            provider="github", provider_id="gh-999", email="existing@github.com", name="Existing"
        )
        assert user1.id == user2.id

    def test_get_or_create_oauth_links_to_existing_email(self, user_store):
        """OAuth login links to an existing email/password account."""
        existing = user_store.create_user(
            email="linked@example.com", name="Linked", password="pass1234"
        )
        oauth_user = user_store.get_or_create_oauth_user(
            provider="google",
            provider_id="goo-456",
            email="linked@example.com",
            name="Linked via Google",
        )
        assert oauth_user.id == existing.id
        assert oauth_user.provider == "google"

    def test_user_public_dict(self, user_store):
        """public_dict does not contain the password hash."""
        user = user_store.create_user(email="alice@example.com", name="Alice", password="pass1234")
        d = user.public_dict()
        assert "password_hash" not in d
        assert "email" in d
        assert "id" in d
        assert "plan" in d


# ---------------------------------------------------------------------------
# SessionManager tests
# ---------------------------------------------------------------------------


class TestSessionManager:

    def test_create_session(self, session_manager):
        """create_session returns a dict with token, expires_at, csrf_token."""
        result = session_manager.create_session("user-123", "127.0.0.1")
        assert "token" in result
        assert "expires_at" in result
        assert "csrf_token" in result
        assert len(result["token"]) > 10

    def test_validate_session_valid(self, session_manager):
        """validate_session returns the user_id for a valid token."""
        session = session_manager.create_session("user-123", "127.0.0.1")
        user_id = session_manager.validate_session(session["token"])
        assert user_id == "user-123"

    def test_validate_session_invalid_token(self, session_manager):
        """validate_session returns None for a bogus token."""
        assert session_manager.validate_session("not.a.real.token") is None

    def test_validate_session_tampered_signature(self, session_manager):
        """validate_session returns None if the signature is tampered with."""
        session = session_manager.create_session("user-123", "127.0.0.1")
        token = session["token"]
        parts = token.rsplit(".", 1)
        tampered = parts[0] + ".deadbeef" + parts[1]
        assert session_manager.validate_session(tampered) is None

    def test_invalidate_session(self, session_manager):
        """invalidate_session removes the session."""
        session = session_manager.create_session("user-123", "127.0.0.1")
        assert session_manager.invalidate_session(session["token"]) is True
        assert session_manager.validate_session(session["token"]) is None

    def test_invalidate_nonexistent_session(self, session_manager):
        """invalidate_session returns False for a token that doesn't exist."""
        fake = session_manager._sign_token("nonexistent-session-id")
        assert session_manager.invalidate_session(fake) is False

    def test_session_expiry(self, session_manager, tmp_data_dir):
        """An expired session is rejected by validate_session."""
        from dashboard.auth.session_manager import SessionManager
        # Create a session that has already expired (negative TTL workaround)
        mgr = SessionManager(data_dir=tmp_data_dir, secret_key="test-secret")
        session = mgr.create_session("user-expired", "127.0.0.1")
        token = session["token"]
        session_id = token.rsplit(".", 1)[0]

        # Manually set the expiry to the past
        mgr._sessions[session_id]["expires_ts"] = time.time() - 1
        mgr._save()

        assert mgr.validate_session(token) is None

    def test_cleanup_expired_sessions(self, session_manager):
        """cleanup_expired_sessions removes expired entries."""
        session = session_manager.create_session("user-123", "127.0.0.1")
        token = session["token"]
        session_id = token.rsplit(".", 1)[0]

        # Mark it as expired
        session_manager._sessions[session_id]["expires_ts"] = time.time() - 1

        removed = session_manager.cleanup_expired_sessions()
        assert removed >= 1
        assert session_manager.validate_session(token) is None

    def test_invalidate_all_user_sessions(self, session_manager):
        """invalidate_all_user_sessions removes all sessions for a user."""
        s1 = session_manager.create_session("user-A", "10.0.0.1")
        s2 = session_manager.create_session("user-A", "10.0.0.2")
        s3 = session_manager.create_session("user-B", "10.0.0.3")

        count = session_manager.invalidate_all_user_sessions("user-A")
        assert count == 2
        assert session_manager.validate_session(s1["token"]) is None
        assert session_manager.validate_session(s2["token"]) is None
        assert session_manager.validate_session(s3["token"]) == "user-B"

    def test_csrf_token_generated(self, session_manager):
        """Each session gets a unique CSRF token."""
        s1 = session_manager.create_session("user-A", "127.0.0.1")
        s2 = session_manager.create_session("user-A", "127.0.0.1")
        assert s1["csrf_token"] != s2["csrf_token"]

    def test_validate_csrf_correct(self, session_manager):
        """validate_csrf returns True for the correct token pair."""
        session = session_manager.create_session("user-A", "127.0.0.1")
        assert session_manager.validate_csrf(session["token"], session["csrf_token"]) is True

    def test_validate_csrf_wrong_csrf(self, session_manager):
        """validate_csrf returns False for a wrong CSRF token."""
        session = session_manager.create_session("user-A", "127.0.0.1")
        assert session_manager.validate_csrf(session["token"], "wrong-csrf-value") is False

    def test_rate_limiting_not_triggered_initially(self, session_manager):
        """An IP with no failed attempts is not rate-limited."""
        assert session_manager.is_rate_limited("10.0.0.1") is False

    def test_rate_limiting_triggered_after_threshold(self, session_manager):
        """After 5 failed attempts, the IP is rate-limited."""
        ip = "10.0.0.100"
        for _ in range(5):
            session_manager.record_failed_attempt(ip)
        assert session_manager.is_rate_limited(ip) is True

    def test_rate_limiting_remaining_attempts(self, session_manager):
        """remaining_attempts counts down correctly."""
        ip = "10.0.0.200"
        assert session_manager.remaining_attempts(ip) == 5
        session_manager.record_failed_attempt(ip)
        assert session_manager.remaining_attempts(ip) == 4
        session_manager.record_failed_attempt(ip)
        assert session_manager.remaining_attempts(ip) == 3

    def test_rate_limiting_cleared_on_success(self, session_manager):
        """clear_rate_limit removes the failed attempts for an IP."""
        ip = "10.0.0.50"
        for _ in range(4):
            session_manager.record_failed_attempt(ip)
        session_manager.clear_rate_limit(ip)
        assert session_manager.is_rate_limited(ip) is False
        assert session_manager.remaining_attempts(ip) == 5

    def test_session_persistence(self, tmp_data_dir):
        """Sessions survive a round-trip through the JSON file."""
        from dashboard.auth.session_manager import SessionManager
        mgr1 = SessionManager(data_dir=tmp_data_dir, secret_key="persist-key")
        session = mgr1.create_session("user-persist", "127.0.0.1")

        mgr2 = SessionManager(data_dir=tmp_data_dir, secret_key="persist-key")
        assert mgr2.validate_session(session["token"]) == "user-persist"

    def test_generate_csrf_token_uniqueness(self, session_manager):
        """generate_csrf_token produces different values each time."""
        tokens = {session_manager.generate_csrf_token() for _ in range(10)}
        assert len(tokens) == 10  # All unique


# ---------------------------------------------------------------------------
# OAuthHandler tests
# ---------------------------------------------------------------------------


class TestOAuthHandler:

    def test_github_not_configured_when_env_missing(self, oauth_handler):
        """is_github_configured returns False when env vars are absent."""
        with patch.dict(os.environ, {}, clear=False):
            # Ensure the vars are not set
            env = {k: v for k, v in os.environ.items()
                   if k not in ('GITHUB_CLIENT_ID', 'GITHUB_CLIENT_SECRET')}
            with patch.dict(os.environ, env, clear=True):
                assert oauth_handler.is_github_configured() is False

    def test_github_configured_when_env_present(self, oauth_handler):
        """is_github_configured returns True when env vars are set."""
        with patch.dict(os.environ, {
            'GITHUB_CLIENT_ID': 'test_id',
            'GITHUB_CLIENT_SECRET': 'test_secret',
        }):
            assert oauth_handler.is_github_configured() is True

    def test_google_not_configured_when_env_missing(self, oauth_handler):
        """is_google_configured returns False when env vars are absent."""
        env = {k: v for k, v in os.environ.items()
               if k not in ('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET')}
        with patch.dict(os.environ, env, clear=True):
            assert oauth_handler.is_google_configured() is False

    def test_google_configured_when_env_present(self, oauth_handler):
        """is_google_configured returns True when env vars are set."""
        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'test_id',
            'GOOGLE_CLIENT_SECRET': 'test_secret',
        }):
            assert oauth_handler.is_google_configured() is True

    def test_get_github_auth_url_contains_client_id(self, oauth_handler):
        """get_github_auth_url includes the client_id in the URL."""
        with patch.dict(os.environ, {
            'GITHUB_CLIENT_ID': 'my-gh-client',
            'GITHUB_CLIENT_SECRET': 'my-gh-secret',
        }):
            url = oauth_handler.get_github_auth_url("state123")
            assert "my-gh-client" in url
            assert "state123" in url
            assert "github.com" in url

    def test_get_github_auth_url_contains_redirect(self, oauth_handler):
        """get_github_auth_url contains the callback URI (URL-encoded)."""
        from urllib.parse import unquote
        with patch.dict(os.environ, {
            'GITHUB_CLIENT_ID': 'my-gh-client',
            'GITHUB_CLIENT_SECRET': 'my-gh-secret',
        }):
            url = oauth_handler.get_github_auth_url("state123")
            decoded_url = unquote(url)
            assert "/auth/github/callback" in decoded_url

    def test_get_github_auth_url_raises_when_not_configured(self, oauth_handler):
        """get_github_auth_url raises OAuthNotConfiguredError when env vars missing."""
        from dashboard.auth.oauth_handler import OAuthNotConfiguredError
        env = {k: v for k, v in os.environ.items()
               if k not in ('GITHUB_CLIENT_ID', 'GITHUB_CLIENT_SECRET')}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(OAuthNotConfiguredError):
                oauth_handler.get_github_auth_url("state123")

    def test_get_google_auth_url_contains_client_id(self, oauth_handler):
        """get_google_auth_url includes the client_id in the URL."""
        with patch.dict(os.environ, {
            'GOOGLE_CLIENT_ID': 'my-g-client',
            'GOOGLE_CLIENT_SECRET': 'my-g-secret',
        }):
            url = oauth_handler.get_google_auth_url("state456")
            assert "my-g-client" in url
            assert "state456" in url
            assert "google" in url.lower()

    def test_get_google_auth_url_raises_when_not_configured(self, oauth_handler):
        """get_google_auth_url raises OAuthNotConfiguredError when env vars missing."""
        from dashboard.auth.oauth_handler import OAuthNotConfiguredError
        env = {k: v for k, v in os.environ.items()
               if k not in ('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET')}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(OAuthNotConfiguredError):
                oauth_handler.get_google_auth_url("state456")

    def test_generate_state_returns_non_empty(self, oauth_handler):
        """generate_state returns a non-empty string."""
        state = oauth_handler.generate_state()
        assert len(state) > 10

    def test_generate_state_unique(self, oauth_handler):
        """generate_state values are unique across calls."""
        states = {oauth_handler.generate_state() for _ in range(10)}
        assert len(states) == 10


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_client(tmp_data_dir):
    """Aiohttp test client with auth-aware REST API server."""
    from aiohttp.test_utils import TestClient, TestServer
    from dashboard.auth.user_store import UserStore
    from dashboard.auth.session_manager import SessionManager
    import dashboard.rest_api_server as rs_mod

    # Inject test-specific instances
    rs_mod._user_store = UserStore(data_dir=tmp_data_dir)
    rs_mod._session_manager = SessionManager(data_dir=tmp_data_dir, secret_key="test-api-key")
    rs_mod._AUTH_AVAILABLE = True

    from dashboard.rest_api_server import RESTAPIServer
    server = RESTAPIServer(project_name="test", port=0)

    # Override globals with test instances so handlers pick them up
    rs_mod._user_store = UserStore(data_dir=tmp_data_dir)
    rs_mod._session_manager = SessionManager(data_dir=tmp_data_dir, secret_key="test-api-key")

    client = TestClient(TestServer(server.app))
    await client.start_server()
    yield client
    await client.close()


class TestAuthAPI:

    async def test_login_page_returns_html(self, test_client):
        """GET /auth/login returns a 200 HTML response."""
        resp = await test_client.get("/auth/login")
        assert resp.status == 200
        text = await resp.text()
        assert "login" in text.lower() or "sign in" in text.lower()

    async def test_register_success(self, test_client):
        """POST /auth/register creates a user and returns a token."""
        resp = await test_client.post(
            "/auth/register",
            json={"email": "newuser@test.com", "name": "New User", "password": "securepass1"},
        )
        assert resp.status == 201
        data = await resp.json()
        assert data["ok"] is True
        assert "token" in data
        assert data["user"]["email"] == "newuser@test.com"

    async def test_register_duplicate_email(self, test_client):
        """Registering with a duplicate email returns 409."""
        await test_client.post(
            "/auth/register",
            json={"email": "dup@test.com", "name": "Dup", "password": "securepass1"},
        )
        resp = await test_client.post(
            "/auth/register",
            json={"email": "dup@test.com", "name": "Dup2", "password": "securepass2"},
        )
        assert resp.status == 409

    async def test_register_short_password(self, test_client):
        """Short password returns 400."""
        resp = await test_client.post(
            "/auth/register",
            json={"email": "pw@test.com", "name": "PW", "password": "short"},
        )
        assert resp.status == 400

    async def test_login_success(self, test_client):
        """POST /auth/login with valid credentials returns a token."""
        await test_client.post(
            "/auth/register",
            json={"email": "loginuser@test.com", "name": "Login", "password": "mypassword1"},
        )
        resp = await test_client.post(
            "/auth/login",
            json={"email": "loginuser@test.com", "password": "mypassword1"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True
        assert "token" in data

    async def test_login_wrong_password(self, test_client):
        """Wrong password returns 401."""
        await test_client.post(
            "/auth/register",
            json={"email": "wpw@test.com", "name": "WPW", "password": "rightpass1"},
        )
        resp = await test_client.post(
            "/auth/login",
            json={"email": "wpw@test.com", "password": "wrongpass1"},
        )
        assert resp.status == 401

    async def test_login_unknown_email(self, test_client):
        """Login with unknown email returns 401."""
        resp = await test_client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "anything"},
        )
        assert resp.status == 401

    async def test_auth_me_authenticated(self, test_client):
        """GET /auth/me with a valid token returns user info."""
        reg_resp = await test_client.post(
            "/auth/register",
            json={"email": "me@test.com", "name": "Me User", "password": "testpassword1"},
        )
        token = (await reg_resp.json())["token"]

        resp = await test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["user"]["email"] == "me@test.com"

    async def test_auth_me_unauthenticated(self, test_client):
        """GET /auth/me without token returns 401."""
        resp = await test_client.get("/auth/me")
        assert resp.status == 401

    async def test_logout_invalidates_session(self, test_client):
        """POST /auth/logout makes the token invalid."""
        reg_resp = await test_client.post(
            "/auth/register",
            json={"email": "logout@test.com", "name": "Logout", "password": "logoutpass1"},
        )
        token = (await reg_resp.json())["token"]

        await test_client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Token should no longer work
        me_resp = await test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status == 401

    async def test_password_reset_returns_200(self, test_client):
        """POST /auth/password-reset always returns 200 (prevent email enumeration)."""
        resp = await test_client.post(
            "/auth/password-reset",
            json={"email": "anyone@test.com"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["ok"] is True

    async def test_password_reset_missing_email(self, test_client):
        """POST /auth/password-reset with no email returns 400."""
        resp = await test_client.post("/auth/password-reset", json={})
        assert resp.status == 400
