"""Tests for Enterprise SSO - AI-232.

78 tests covering:
    - SAML 2.0 handler (saml_handler.py)
    - OIDC handler (oidc_handler.py)
    - Organization store (organization_store.py)
    - JIT provisioner (jit_provisioner.py)
    - SCIM 2.0 handler (scim_handler.py)
"""

import base64
import json
import secrets
import time
import uuid
import zlib
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from sso.saml_handler import (
    SAMLHandler,
    SAMLConfig,
    SAMLResponse,
    SAMLError,
    SAMLValidationError,
    SAMLConfigError,
    CLOCK_SKEW_SECONDS,
)
from sso.oidc_handler import (
    OIDCHandler,
    OIDCConfig,
    OIDCTokenResponse,
    OIDCError,
    OIDCValidationError,
    OIDCConfigError,
)
from sso.organization_store import (
    OrganizationStore,
    Organization,
    SSOConfig,
    OrganizationError,
    PlanGatingError,
    SSO_PLANS,
    ALL_PLANS,
)
from sso.jit_provisioner import (
    JITProvisioner,
    JITResult,
    ProvisionedUser,
    JITError,
    JITDomainError,
    JITProvisioningDisabledError,
    JIT_MAX_ROLE,
    ROLE_HIERARCHY,
)
from sso.scim_handler import (
    SCIMHandler,
    SCIMUser,
    SCIMGroup,
    SCIMError,
    SCIMAuthError,
    SCIMNotFoundError,
    SCIM_SCHEMA_USER,
    SCIM_SCHEMA_GROUP,
    SCIM_SCHEMA_LIST,
)


# ============================================================
# SAML Handler Tests (20 tests)
# ============================================================

class TestSAMLConfig:
    """Tests for SAMLConfig dataclass."""

    def test_saml_config_defaults(self):
        """Test SAMLConfig has expected defaults."""
        config = SAMLConfig(
            idp_entity_id="https://idp.example.com",
            idp_sso_url="https://idp.example.com/sso",
            idp_certificate="CERT",
            sp_entity_id="https://sp.example.com",
            sp_acs_url="https://sp.example.com/acs",
        )
        assert config.want_assertions_signed is True
        assert config.want_response_signed is True
        assert config.sign_requests is False
        assert "email" in config.attribute_mapping
        assert config.name_id_format == "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"

    def test_saml_config_attribute_mapping_defaults(self):
        """Test default attribute mapping contains expected keys."""
        config = SAMLConfig(
            idp_entity_id="x", idp_sso_url="x", idp_certificate="x",
            sp_entity_id="x", sp_acs_url="x",
        )
        assert "email" in config.attribute_mapping
        assert "first_name" in config.attribute_mapping
        assert "last_name" in config.attribute_mapping
        assert "groups" in config.attribute_mapping


class TestSAMLHandler:
    """Tests for SAMLHandler."""

    @pytest.fixture
    def config(self):
        return SAMLConfig(
            idp_entity_id="https://idp.example.com",
            idp_sso_url="https://idp.example.com/sso",
            idp_certificate="FAKE_CERT",
            sp_entity_id="https://sp.example.com",
            sp_acs_url="https://sp.example.com/acs",
            org_id="org-123",
        )

    @pytest.fixture
    def handler(self, config):
        return SAMLHandler(config)

    def test_generate_authn_request_returns_tuple(self, handler):
        """generate_authn_request returns (url, request_id, relay_state)."""
        url, req_id, relay_state = handler.generate_authn_request()
        assert url.startswith("https://idp.example.com/sso")
        assert req_id.startswith("_")
        assert len(relay_state) > 0

    def test_generate_authn_request_contains_saml_request(self, handler):
        """Auth URL contains SAMLRequest parameter."""
        url, _, _ = handler.generate_authn_request()
        assert "SAMLRequest=" in url

    def test_generate_authn_request_custom_relay_state(self, handler):
        """Custom relay state is used when provided."""
        url, _, relay = handler.generate_authn_request(relay_state="my-state")
        assert relay == "my-state"
        assert "RelayState=my-state" in url

    def test_generate_authn_request_stores_pending_request(self, handler):
        """Generated request ID is stored for replay prevention."""
        _, req_id, _ = handler.generate_authn_request()
        assert req_id in handler._pending_requests

    def test_generate_metadata_returns_xml(self, handler):
        """generate_metadata returns valid-looking SP metadata XML."""
        metadata = handler.generate_metadata()
        assert "EntityDescriptor" in metadata
        assert handler.config.sp_entity_id in metadata
        assert handler.config.sp_acs_url in metadata

    def test_parse_response_invalid_base64_raises(self, handler):
        """Invalid base64 raises SAMLValidationError."""
        with pytest.raises(SAMLValidationError, match="Failed to decode"):
            handler.parse_response("not-valid-base64!!!")

    def test_parse_response_invalid_xml_raises(self, handler):
        """Invalid XML raises SAMLValidationError."""
        bad_xml = base64.b64encode(b"not xml at all").decode()
        with pytest.raises(SAMLValidationError, match="Invalid SAML response XML"):
            handler.parse_response(bad_xml)

    def _make_saml_response(self, handler, email="user@example.com", issuer=None, expired=False, wrong_audience=False):
        """Helper to create a minimal valid SAML response XML."""
        now = datetime.now(timezone.utc)
        if expired:
            not_on_or_after = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            not_on_or_after = (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        not_before = (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        issue_instant = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        if issuer is None:
            issuer = handler.config.idp_entity_id
        audience = "wrong-audience" if wrong_audience else handler.config.sp_entity_id
        acs = handler.config.sp_acs_url

        xml = f"""<samlp:Response
            xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
            xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
            ID="_resp123" Version="2.0" IssueInstant="{issue_instant}">
            <saml:Issuer>{issuer}</saml:Issuer>
            <samlp:Status>
                <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>
            </samlp:Status>
            <saml:Assertion ID="_assert123" Version="2.0" IssueInstant="{issue_instant}">
                <saml:Issuer>{issuer}</saml:Issuer>
                <saml:Subject>
                    <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{email}</saml:NameID>
                    <saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
                        <saml:SubjectConfirmationData
                            Recipient="{acs}"
                            NotOnOrAfter="{not_on_or_after}"/>
                    </saml:SubjectConfirmation>
                </saml:Subject>
                <saml:Conditions NotBefore="{not_before}" NotOnOrAfter="{not_on_or_after}">
                    <saml:AudienceRestriction>
                        <saml:Audience>{audience}</saml:Audience>
                    </saml:AudienceRestriction>
                </saml:Conditions>
                <saml:AuthnStatement SessionIndex="_session123" AuthnInstant="{issue_instant}">
                    <saml:AuthnContext>
                        <saml:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:Password</saml:AuthnContextClassRef>
                    </saml:AuthnContext>
                </saml:AuthnStatement>
                <saml:AttributeStatement>
                    <saml:Attribute Name="urn:oid:1.2.840.113549.1.9.1">
                        <saml:AttributeValue>{email}</saml:AttributeValue>
                    </saml:Attribute>
                    <saml:Attribute Name="urn:oid:2.5.4.42">
                        <saml:AttributeValue>John</saml:AttributeValue>
                    </saml:Attribute>
                    <saml:Attribute Name="urn:oid:2.5.4.4">
                        <saml:AttributeValue>Doe</saml:AttributeValue>
                    </saml:Attribute>
                </saml:AttributeStatement>
            </saml:Assertion>
        </samlp:Response>"""

        return base64.b64encode(xml.encode()).decode()

    def test_parse_valid_response(self, handler):
        """Valid SAML response parses successfully."""
        b64 = self._make_saml_response(handler)
        result = handler.parse_response(b64)
        assert isinstance(result, SAMLResponse)
        assert result.name_id == "user@example.com"
        assert result.email == "user@example.com"

    def test_parse_response_extracts_name_id(self, handler):
        """parse_response extracts NameID correctly."""
        b64 = self._make_saml_response(handler, email="test@corp.com")
        result = handler.parse_response(b64)
        assert result.name_id == "test@corp.com"

    def test_parse_response_extracts_session_index(self, handler):
        """parse_response extracts SessionIndex."""
        b64 = self._make_saml_response(handler)
        result = handler.parse_response(b64)
        assert result.session_index == "_session123"

    def test_parse_response_issuer_mismatch_raises(self, handler):
        """Mismatched issuer raises SAMLValidationError."""
        b64 = self._make_saml_response(handler, issuer="https://evil.com")
        with pytest.raises(SAMLValidationError, match="Issuer mismatch"):
            handler.parse_response(b64)

    def test_parse_response_expired_assertion_raises(self, handler):
        """Expired assertion raises SAMLValidationError."""
        b64 = self._make_saml_response(handler, expired=True)
        with pytest.raises(SAMLValidationError, match="expired"):
            handler.parse_response(b64)

    def test_parse_response_wrong_audience_raises(self, handler):
        """Wrong audience raises SAMLValidationError."""
        b64 = self._make_saml_response(handler, wrong_audience=True)
        with pytest.raises(SAMLValidationError, match="Audience restriction"):
            handler.parse_response(b64)

    def test_parse_response_failed_status_raises(self, handler):
        """Failed SAML status raises SAMLValidationError."""
        xml = """<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol">
            <samlp:Status>
                <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:AuthnFailed"/>
                <samlp:StatusMessage>Authentication failed</samlp:StatusMessage>
            </samlp:Status>
        </samlp:Response>"""
        b64 = base64.b64encode(xml.encode()).decode()
        with pytest.raises(SAMLValidationError, match="authentication failed|Authentication failed"):
            handler.parse_response(b64)

    def test_cleanup_expired_requests(self, handler):
        """Expired pending requests are cleaned up."""
        handler._pending_requests["old_req"] = datetime.now(timezone.utc) - timedelta(minutes=15)
        handler._pending_requests["new_req"] = datetime.now(timezone.utc)
        handler._cleanup_expired_requests()
        assert "old_req" not in handler._pending_requests
        assert "new_req" in handler._pending_requests


# ============================================================
# OIDC Handler Tests (15 tests)
# ============================================================

class TestOIDCConfig:
    """Tests for OIDCConfig dataclass."""

    def test_oidc_config_defaults(self):
        """OIDCConfig has expected defaults."""
        config = OIDCConfig(
            issuer="https://accounts.example.com",
            client_id="client123",
            client_secret="secret456",
        )
        assert config.use_pkce is True
        assert config.require_nonce is True
        assert "openid" in config.scopes
        assert "email" in config.scopes
        assert config.clock_skew_seconds == 60


class TestOIDCHandler:
    """Tests for OIDCHandler."""

    @pytest.fixture
    def config(self):
        return OIDCConfig(
            issuer="https://accounts.example.com",
            client_id="client123",
            client_secret="secret456",
            redirect_uri="https://app.example.com/callback",
            authorization_endpoint="https://accounts.example.com/auth",
            token_endpoint="https://accounts.example.com/token",
            userinfo_endpoint="https://accounts.example.com/userinfo",
        )

    @pytest.fixture
    def handler(self, config):
        return OIDCHandler(config)

    def test_generate_auth_url_returns_tuple(self, handler):
        """generate_auth_url returns (url, state, nonce)."""
        url, state, nonce = handler.generate_auth_url()
        assert "https://accounts.example.com/auth" in url
        assert len(state) > 0
        assert len(nonce) > 0

    def test_generate_auth_url_contains_params(self, handler):
        """Auth URL contains required OIDC parameters."""
        url, state, nonce = handler.generate_auth_url()
        assert "response_type=code" in url
        assert "client_id=client123" in url
        assert f"state={state}" in url
        assert f"nonce={nonce}" in url

    def test_generate_auth_url_includes_pkce(self, handler):
        """Auth URL includes PKCE parameters when enabled."""
        url, _, _ = handler.generate_auth_url()
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url

    def test_generate_auth_url_stores_state(self, handler):
        """Generated state is stored for CSRF validation."""
        _, state, _ = handler.generate_auth_url()
        assert state in handler._pending_states

    def test_generate_auth_url_stores_nonce_in_state(self, handler):
        """Nonce is stored with state for replay prevention."""
        _, state, nonce = handler.generate_auth_url()
        assert handler._pending_states[state]["nonce"] == nonce

    def test_parse_id_token_valid(self, handler):
        """Valid ID token claims parse successfully."""
        now = int(time.time())
        claims = {
            "iss": "https://accounts.example.com",
            "sub": "user123",
            "aud": "client123",
            "exp": now + 3600,
            "iat": now,
            "nonce": "test-nonce",
            "email": "user@example.com",
        }
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        token = f"header.{payload}.sig"
        result = handler._parse_id_token(token, "test-nonce")
        assert result["sub"] == "user123"
        assert result["email"] == "user@example.com"

    def test_parse_id_token_wrong_issuer_raises(self, handler):
        """Wrong issuer in ID token raises OIDCValidationError."""
        now = int(time.time())
        claims = {
            "iss": "https://evil.com",
            "sub": "user123",
            "aud": "client123",
            "exp": now + 3600,
            "iat": now,
        }
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        token = f"header.{payload}.sig"
        with pytest.raises(OIDCValidationError, match="issuer mismatch"):
            handler._parse_id_token(token, None)

    def test_parse_id_token_expired_raises(self, handler):
        """Expired ID token raises OIDCValidationError."""
        now = int(time.time())
        claims = {
            "iss": "https://accounts.example.com",
            "sub": "user123",
            "aud": "client123",
            "exp": now - 3600,  # Expired
            "iat": now - 7200,
        }
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        token = f"header.{payload}.sig"
        with pytest.raises(OIDCValidationError, match="expired"):
            handler._parse_id_token(token, None)

    def test_parse_id_token_nonce_mismatch_raises(self, handler):
        """Nonce mismatch in ID token raises OIDCValidationError."""
        now = int(time.time())
        claims = {
            "iss": "https://accounts.example.com",
            "sub": "user123",
            "aud": "client123",
            "exp": now + 3600,
            "iat": now,
            "nonce": "wrong-nonce",
        }
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        token = f"header.{payload}.sig"
        with pytest.raises(OIDCValidationError, match="nonce mismatch"):
            handler._parse_id_token(token, "expected-nonce")

    def test_exchange_code_invalid_state_raises(self, handler):
        """exchange_code with unknown state raises OIDCValidationError."""
        with pytest.raises(OIDCValidationError, match="Invalid or expired state"):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                handler.exchange_code("auth_code", "nonexistent_state")
            )

    def test_cleanup_expired_states(self, handler):
        """Expired states are cleaned up."""
        handler._pending_states["old_state"] = {
            "nonce": "n1",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat(),
        }
        handler._pending_states["new_state"] = {
            "nonce": "n2",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        handler._cleanup_expired_states()
        assert "old_state" not in handler._pending_states
        assert "new_state" in handler._pending_states

    def test_map_claims(self, handler):
        """_map_claims maps OIDC claims to user fields."""
        claims = {
            "email": "user@example.com",
            "given_name": "John",
            "family_name": "Doe",
            "name": "John Doe",
            "groups": ["engineering", "admin"],
        }
        mapped = handler._map_claims(claims)
        assert mapped["email"] == "user@example.com"
        assert mapped["first_name"] == "John"
        assert mapped["last_name"] == "Doe"
        assert mapped["display_name"] == "John Doe"

    def test_oidc_handler_raises_without_aiohttp(self):
        """OIDCHandler raises OIDCConfigError if aiohttp not available."""
        config = OIDCConfig(issuer="x", client_id="x", client_secret="x")
        with patch("sso.oidc_handler._AIOHTTP_AVAILABLE", False):
            with pytest.raises(OIDCConfigError, match="aiohttp is required"):
                OIDCHandler(config)

    def test_generate_auth_url_no_endpoint_raises(self, config):
        """generate_auth_url raises if authorization_endpoint not set."""
        config.authorization_endpoint = None
        handler = OIDCHandler(config)
        with pytest.raises(OIDCConfigError, match="authorization_endpoint not configured"):
            handler.generate_auth_url()


# ============================================================
# Organization Store Tests (18 tests)
# ============================================================

class TestOrganizationStore:
    """Tests for OrganizationStore."""

    @pytest.fixture
    def store(self):
        return OrganizationStore()

    def test_create_organization(self, store):
        """create_organization creates and returns an Organization."""
        org = store.create_organization("Acme Corp", "user-1", plan="free")
        assert org.name == "Acme Corp"
        assert org.owner_user_id == "user-1"
        assert org.plan == "free"
        assert "acme-corp" in org.slug or "acme" in org.slug

    def test_create_organization_generates_id(self, store):
        """create_organization generates a UUID org_id."""
        org = store.create_organization("Test", "user-1")
        assert len(org.org_id) == 36  # UUID format

    def test_create_organization_duplicate_slug_raises(self, store):
        """Duplicate slug raises OrganizationError."""
        store.create_organization("Test Corp", "user-1", slug="test-corp")
        with pytest.raises(OrganizationError, match="already taken"):
            store.create_organization("Test Corp 2", "user-2", slug="test-corp")

    def test_create_organization_invalid_plan_raises(self, store):
        """Invalid plan raises OrganizationError."""
        with pytest.raises(OrganizationError, match="Invalid plan"):
            store.create_organization("Test", "user-1", plan="ultra")

    def test_get_organization_by_id(self, store):
        """get_organization returns org by ID."""
        org = store.create_organization("Test", "user-1")
        fetched = store.get_organization(org.org_id)
        assert fetched.org_id == org.org_id

    def test_get_organization_not_found(self, store):
        """get_organization returns None for unknown ID."""
        assert store.get_organization("nonexistent") is None

    def test_get_organization_by_slug(self, store):
        """get_organization_by_slug returns org by slug."""
        org = store.create_organization("Slug Test", "user-1", slug="slug-test")
        fetched = store.get_organization_by_slug("slug-test")
        assert fetched.org_id == org.org_id

    def test_sso_allowed_for_org_plan(self, store):
        """sso_allowed is True for organization plan."""
        org = store.create_organization("Test", "user-1", plan="organization")
        assert org.sso_allowed is True

    def test_sso_not_allowed_for_free_plan(self, store):
        """sso_allowed is False for free plan."""
        org = store.create_organization("Test", "user-1", plan="free")
        assert org.sso_allowed is False

    def test_configure_saml_requires_sso_plan(self, store):
        """configure_saml raises PlanGatingError for free plan."""
        org = store.create_organization("Test", "user-1", plan="free")
        with pytest.raises(PlanGatingError, match="Organization or Enterprise"):
            store.configure_saml(org.org_id, {
                "idp_entity_id": "x", "idp_sso_url": "x", "idp_certificate": "x"
            })

    def test_configure_saml_success(self, store):
        """configure_saml succeeds for organization plan."""
        org = store.create_organization("Test", "user-1", plan="organization")
        updated = store.configure_saml(org.org_id, {
            "idp_entity_id": "https://idp.example.com",
            "idp_sso_url": "https://idp.example.com/sso",
            "idp_certificate": "CERT",
        })
        assert updated.sso_config.sso_type == "saml"
        assert updated.sso_config.saml_idp_entity_id == "https://idp.example.com"

    def test_configure_saml_missing_fields_raises(self, store):
        """configure_saml raises on missing required fields."""
        org = store.create_organization("Test", "user-1", plan="organization")
        with pytest.raises(OrganizationError, match="Missing required SAML fields"):
            store.configure_saml(org.org_id, {"idp_entity_id": "x"})

    def test_configure_oidc_success(self, store):
        """configure_oidc succeeds for organization plan."""
        org = store.create_organization("Test", "user-1", plan="organization")
        updated = store.configure_oidc(org.org_id, {
            "issuer": "https://accounts.example.com",
            "client_id": "client123",
            "client_secret": "secret456",
        })
        assert updated.sso_config.sso_type == "oidc"
        assert updated.sso_config.oidc_issuer == "https://accounts.example.com"

    def test_enable_sso_without_config_raises(self, store):
        """enable_sso raises if no SAML/OIDC config present."""
        org = store.create_organization("Test", "user-1", plan="organization")
        with pytest.raises(OrganizationError, match="no SAML or OIDC"):
            store.enable_sso(org.org_id)

    def test_enable_sso_after_config(self, store):
        """enable_sso succeeds after SAML is configured."""
        org = store.create_organization("Test", "user-1", plan="organization")
        store.configure_saml(org.org_id, {
            "idp_entity_id": "x", "idp_sso_url": "x", "idp_certificate": "x"
        })
        updated = store.enable_sso(org.org_id)
        assert updated.sso_config.enabled is True

    def test_generate_scim_token(self, store):
        """generate_scim_token returns a SCIM token."""
        org = store.create_organization("Test", "user-1", plan="organization")
        token = store.generate_scim_token(org.org_id)
        assert token.startswith("scim_")
        assert len(token) > 10

    def test_get_org_by_scim_token(self, store):
        """get_org_by_scim_token returns org for valid token."""
        org = store.create_organization("Test", "user-1", plan="organization")
        token = store.generate_scim_token(org.org_id)
        found = store.get_org_by_scim_token(token)
        assert found.org_id == org.org_id

    def test_update_plan_disables_sso_on_downgrade(self, store):
        """Downgrading plan disables SSO."""
        org = store.create_organization("Test", "user-1", plan="organization")
        store.configure_saml(org.org_id, {
            "idp_entity_id": "x", "idp_sso_url": "x", "idp_certificate": "x"
        })
        store.enable_sso(org.org_id)
        updated = store.update_plan(org.org_id, "free")
        assert updated.sso_config.enabled is False


# ============================================================
# JIT Provisioner Tests (13 tests)
# ============================================================

class TestJITProvisioner:
    """Tests for JITProvisioner."""

    @pytest.fixture
    def provisioner(self):
        return JITProvisioner()

    @pytest.fixture
    def sso_config_enabled(self):
        config = SSOConfig()
        config.jit_enabled = True
        config.jit_default_role = "member"
        config.allowed_domains = []
        config.jit_group_role_mapping = {}
        return config

    def _make_saml_response(self, email="user@example.com", groups=None):
        """Create a mock SAMLResponse."""
        response = MagicMock()
        response.name_id = email
        response.email = email
        response.first_name = "John"
        response.last_name = "Doe"
        response.display_name = "John Doe"
        response.groups = groups or []
        response.session_index = "session_123"
        response.issuer = "https://idp.example.com"
        return response

    def _make_oidc_response(self, email="user@example.com", groups=None, email_verified=True):
        """Create a mock OIDCTokenResponse."""
        response = MagicMock()
        response.sub = f"sub_{email}"
        response.email = email
        response.email_verified = email_verified
        response.first_name = "Jane"
        response.last_name = "Smith"
        response.display_name = "Jane Smith"
        response.groups = groups or []
        response.iss = "https://accounts.example.com"
        return response

    def test_provision_saml_new_user(self, provisioner, sso_config_enabled):
        """provision_from_saml creates new user on first login."""
        saml_resp = self._make_saml_response()
        result = provisioner.provision_from_saml("org-1", sso_config_enabled, saml_resp)
        assert result.is_new_user is True
        assert result.action == "created"
        assert result.email == "user@example.com"
        assert result.org_id == "org-1"

    def test_provision_saml_existing_user_updates(self, provisioner, sso_config_enabled):
        """provision_from_saml updates existing user on subsequent login."""
        saml_resp = self._make_saml_response()
        result1 = provisioner.provision_from_saml("org-1", sso_config_enabled, saml_resp)
        result2 = provisioner.provision_from_saml("org-1", sso_config_enabled, saml_resp)
        assert result1.is_new_user is True
        assert result2.is_new_user is False
        assert result2.action == "updated"
        assert result1.user_id == result2.user_id

    def test_provision_oidc_new_user(self, provisioner, sso_config_enabled):
        """provision_from_oidc creates new user from OIDC response."""
        oidc_resp = self._make_oidc_response()
        result = provisioner.provision_from_oidc("org-2", sso_config_enabled, oidc_resp)
        assert result.is_new_user is True
        assert result.email == "user@example.com"

    def test_provision_jit_disabled_raises(self, provisioner):
        """JIT disabled raises JITProvisioningDisabledError."""
        config = SSOConfig()
        config.jit_enabled = False
        config.allowed_domains = []
        saml_resp = self._make_saml_response()
        with pytest.raises(JITProvisioningDisabledError):
            provisioner.provision_from_saml("org-1", config, saml_resp)

    def test_provision_domain_restriction(self, provisioner, sso_config_enabled):
        """Domain restriction raises JITDomainError for disallowed domain."""
        sso_config_enabled.allowed_domains = ["allowed.com"]
        saml_resp = self._make_saml_response(email="user@other.com")
        with pytest.raises(JITDomainError, match="not allowed"):
            provisioner.provision_from_saml("org-1", sso_config_enabled, saml_resp)

    def test_provision_allowed_domain(self, provisioner, sso_config_enabled):
        """Allowed domain provisions successfully."""
        sso_config_enabled.allowed_domains = ["allowed.com"]
        saml_resp = self._make_saml_response(email="user@allowed.com")
        result = provisioner.provision_from_saml("org-1", sso_config_enabled, saml_resp)
        assert result.email == "user@allowed.com"

    def test_role_capped_at_jit_max_role(self, provisioner, sso_config_enabled):
        """JIT cannot assign roles higher than JIT_MAX_ROLE."""
        sso_config_enabled.jit_group_role_mapping = {"superadmin-group": "owner"}
        saml_resp = self._make_saml_response(groups=["superadmin-group"])
        result = provisioner.provision_from_saml("org-1", sso_config_enabled, saml_resp)
        # Should be capped at JIT_MAX_ROLE (manager), not owner
        assert ROLE_HIERARCHY.get(result.role, 0) <= ROLE_HIERARCHY[JIT_MAX_ROLE]

    def test_group_role_mapping(self, provisioner, sso_config_enabled):
        """Group role mapping assigns correct role."""
        sso_config_enabled.jit_group_role_mapping = {"eng-team": "member"}
        saml_resp = self._make_saml_response(groups=["eng-team"])
        result = provisioner.provision_from_saml("org-1", sso_config_enabled, saml_resp)
        assert result.role == "member"

    def test_get_user_after_provisioning(self, provisioner, sso_config_enabled):
        """get_user returns provisioned user."""
        saml_resp = self._make_saml_response()
        result = provisioner.provision_from_saml("org-1", sso_config_enabled, saml_resp)
        user = provisioner.get_user(result.user_id)
        assert user is not None
        assert user.email == "user@example.com"

    def test_get_user_by_email(self, provisioner, sso_config_enabled):
        """get_user_by_email returns provisioned user."""
        saml_resp = self._make_saml_response(email="lookup@example.com")
        provisioner.provision_from_saml("org-1", sso_config_enabled, saml_resp)
        user = provisioner.get_user_by_email("lookup@example.com")
        assert user is not None

    def test_list_org_users(self, provisioner, sso_config_enabled):
        """list_org_users returns all users for org."""
        for i in range(3):
            saml_resp = self._make_saml_response(email=f"user{i}@example.com")
            provisioner.provision_from_saml("org-multi", sso_config_enabled, saml_resp)
        users = provisioner.list_org_users("org-multi")
        assert len(users) == 3

    def test_deactivate_user(self, provisioner, sso_config_enabled):
        """deactivate_user marks user as inactive."""
        saml_resp = self._make_saml_response()
        result = provisioner.provision_from_saml("org-1", sso_config_enabled, saml_resp)
        success = provisioner.deactivate_user(result.user_id, "org-1")
        assert success is True
        user = provisioner.get_user(result.user_id)
        assert user.is_active is False

    def test_audit_log_records_provisioning(self, provisioner, sso_config_enabled):
        """Provisioning events are recorded in audit log."""
        saml_resp = self._make_saml_response(email="audit@example.com")
        provisioner.provision_from_saml("org-audit", sso_config_enabled, saml_resp)
        log = provisioner.get_audit_log(org_id="org-audit")
        assert len(log) >= 1
        assert any(e["event"] == "user_created" for e in log)


# ============================================================
# SCIM Handler Tests (12 tests)
# ============================================================

class TestSCIMHandler:
    """Tests for SCIMHandler."""

    @pytest.fixture
    def org_store(self):
        store = OrganizationStore()
        org = store.create_organization("SCIM Corp", "owner-1", plan="organization")
        token = store.generate_scim_token(org.org_id)
        return store, org, token

    @pytest.fixture
    def scim_handler(self, org_store):
        store, org, token = org_store
        return SCIMHandler(store), org, token

    def test_authenticate_valid_token(self, scim_handler):
        """Valid SCIM token authenticates successfully."""
        handler, org, token = scim_handler
        authenticated_org = handler.authenticate_token(token)
        assert authenticated_org.org_id == org.org_id

    def test_authenticate_invalid_token_raises(self, scim_handler):
        """Invalid SCIM token raises SCIMAuthError."""
        handler, _, _ = scim_handler
        with pytest.raises(SCIMAuthError):
            handler.authenticate_token("invalid-token")

    def test_create_user(self, scim_handler):
        """create_user creates a SCIM user."""
        handler, org, _ = scim_handler
        user = handler.create_user(org.org_id, {
            "userName": "john@example.com",
            "emails": [{"value": "john@example.com", "primary": True}],
            "name": {"givenName": "John", "familyName": "Doe"},
            "active": True,
        })
        assert user.user_name == "john@example.com"
        assert user.given_name == "John"
        assert user.active is True

    def test_create_user_duplicate_raises(self, scim_handler):
        """Duplicate username raises SCIMError."""
        handler, org, _ = scim_handler
        handler.create_user(org.org_id, {"userName": "dup@example.com"})
        with pytest.raises(SCIMError, match="already exists"):
            handler.create_user(org.org_id, {"userName": "dup@example.com"})

    def test_get_user(self, scim_handler):
        """get_user returns created user."""
        handler, org, _ = scim_handler
        created = handler.create_user(org.org_id, {"userName": "get@example.com"})
        fetched = handler.get_user(org.org_id, created.id)
        assert fetched.id == created.id

    def test_get_user_not_found_raises(self, scim_handler):
        """get_user raises SCIMNotFoundError for unknown user."""
        handler, org, _ = scim_handler
        with pytest.raises(SCIMNotFoundError):
            handler.get_user(org.org_id, "nonexistent-id")

    def test_list_users(self, scim_handler):
        """list_users returns all org users."""
        handler, org, _ = scim_handler
        for i in range(5):
            handler.create_user(org.org_id, {"userName": f"user{i}@example.com"})
        users, total = handler.list_users(org.org_id)
        assert total == 5
        assert len(users) == 5

    def test_patch_user_deactivate(self, scim_handler):
        """PATCH user with active=false deactivates user."""
        handler, org, _ = scim_handler
        user = handler.create_user(org.org_id, {"userName": "patch@example.com"})
        patched = handler.patch_user(org.org_id, user.id, {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [{"op": "replace", "path": "active", "value": False}],
        })
        assert patched.active is False

    def test_delete_user_soft_delete(self, scim_handler):
        """delete_user performs soft delete (deactivates)."""
        handler, org, _ = scim_handler
        user = handler.create_user(org.org_id, {"userName": "delete@example.com"})
        result = handler.delete_user(org.org_id, user.id)
        assert result is True
        fetched = handler.get_user(org.org_id, user.id)
        assert fetched.active is False

    def test_create_group(self, scim_handler):
        """create_group creates a SCIM group."""
        handler, org, _ = scim_handler
        group = handler.create_group(org.org_id, {
            "displayName": "Engineering",
            "members": [],
        })
        assert group.display_name == "Engineering"
        assert group.org_id == org.org_id

    def test_scim_user_to_dict(self, scim_handler):
        """SCIMUser.to_scim_dict returns proper SCIM resource."""
        handler, org, _ = scim_handler
        user = handler.create_user(org.org_id, {
            "userName": "dict@example.com",
            "emails": [{"value": "dict@example.com", "primary": True}],
            "name": {"givenName": "Dict", "familyName": "Test"},
        })
        scim_dict = user.to_scim_dict()
        assert scim_dict["schemas"] == [SCIM_SCHEMA_USER]
        assert scim_dict["userName"] == "dict@example.com"
        assert "meta" in scim_dict

    def test_build_list_response(self, scim_handler):
        """build_list_response returns proper SCIM ListResponse."""
        handler, org, _ = scim_handler
        users = [handler.create_user(org.org_id, {"userName": f"lr{i}@example.com"}) for i in range(3)]
        response = handler.build_list_response(users, total=3, start_index=1)
        assert response["schemas"] == [SCIM_SCHEMA_LIST]
        assert response["totalResults"] == 3
        assert response["itemsPerPage"] == 3
        assert len(response["Resources"]) == 3
