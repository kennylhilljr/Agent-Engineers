"""Organization Store with SSO Configuration.

AI-232: Enterprise SSO - Organization management with SSO config storage.

Organization plans:
    - free: No SSO support
    - pro: No SSO support
    - organization: SAML 2.0 + OIDC support, JIT provisioning, SCIM
    - enterprise: All organization features + additional capabilities
"""

import json
import os
import secrets
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


SSO_PLANS = ("organization", "enterprise")
ALL_PLANS = ("free", "pro", "organization", "enterprise")


class OrganizationError(Exception):
    """Organization store error."""
    pass


class PlanGatingError(OrganizationError):
    """Feature not available on current plan."""
    pass


@dataclass
class SSOConfig:
    """SSO configuration for an organization."""

    sso_type: str = ""  # "saml" | "oidc" | ""
    enabled: bool = False

    # SAML config
    saml_idp_entity_id: str = ""
    saml_idp_sso_url: str = ""
    saml_idp_certificate: str = ""
    saml_sp_entity_id: str = ""
    saml_acs_url: str = ""
    saml_attribute_mapping: Dict[str, str] = field(default_factory=dict)
    saml_want_assertions_signed: bool = True

    # OIDC config
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_discovery_url: str = ""
    oidc_redirect_uri: str = ""
    oidc_scopes: List[str] = field(default_factory=lambda: ["openid", "email", "profile"])
    oidc_attribute_mapping: Dict[str, str] = field(default_factory=dict)

    # JIT provisioning settings
    jit_enabled: bool = True
    jit_default_role: str = "member"
    jit_group_role_mapping: Dict[str, str] = field(default_factory=dict)

    # SCIM settings
    scim_enabled: bool = False
    scim_token: str = ""  # Bearer token for SCIM endpoint

    # Domain restrictions
    allowed_domains: List[str] = field(default_factory=list)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Organization:
    """Organization record with plan and SSO configuration."""

    org_id: str
    name: str
    slug: str  # URL-safe identifier
    plan: str  # free | pro | organization | enterprise
    owner_user_id: str

    # Members: user_id -> role
    members: Dict[str, str] = field(default_factory=dict)

    # SSO configuration
    sso_config: SSOConfig = field(default_factory=SSOConfig)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Settings
    settings: Dict[str, Any] = field(default_factory=dict)

    @property
    def sso_allowed(self) -> bool:
        """Returns True if org plan supports SSO."""
        return self.plan in SSO_PLANS

    @property
    def scim_allowed(self) -> bool:
        """Returns True if org plan supports SCIM."""
        return self.plan in SSO_PLANS

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (safe for JSON serialization)."""
        d = asdict(self)
        # Mask SCIM token in public representation
        if d.get("sso_config", {}).get("scim_token"):
            d["sso_config"]["scim_token"] = "***"
        return d


class OrganizationStore:
    """In-memory organization store with SSO configuration management.

    This store manages organizations and their SSO configurations.
    Plan-gating enforced: SSO features require organization or enterprise plan.
    """

    def __init__(self):
        self._orgs: Dict[str, Organization] = {}  # org_id -> Organization
        self._slug_index: Dict[str, str] = {}  # slug -> org_id
        self._user_org_index: Dict[str, List[str]] = {}  # user_id -> [org_id]

    def create_organization(
        self,
        name: str,
        owner_user_id: str,
        plan: str = "free",
        slug: Optional[str] = None,
    ) -> Organization:
        """Create a new organization.

        Args:
            name: Organization display name
            owner_user_id: User ID of the organization owner
            plan: Subscription plan (free|pro|organization|enterprise)
            slug: Optional URL-safe slug (auto-generated if not provided)

        Returns:
            Created Organization

        Raises:
            OrganizationError: If slug is already taken or plan is invalid
        """
        if plan not in ALL_PLANS:
            raise OrganizationError(f"Invalid plan: {plan}. Must be one of {ALL_PLANS}")

        # Generate slug if not provided
        if not slug:
            slug = self._generate_slug(name)
        else:
            slug = slug.lower().strip()

        if slug in self._slug_index:
            raise OrganizationError(f"Organization slug '{slug}' is already taken")

        org_id = str(uuid.uuid4())

        org = Organization(
            org_id=org_id,
            name=name,
            slug=slug,
            plan=plan,
            owner_user_id=owner_user_id,
            members={owner_user_id: "owner"},
        )

        self._orgs[org_id] = org
        self._slug_index[slug] = org_id

        # Update user-org index
        if owner_user_id not in self._user_org_index:
            self._user_org_index[owner_user_id] = []
        self._user_org_index[owner_user_id].append(org_id)

        return org

    def get_organization(self, org_id: str) -> Optional[Organization]:
        """Get organization by ID."""
        return self._orgs.get(org_id)

    def get_organization_by_slug(self, slug: str) -> Optional[Organization]:
        """Get organization by slug."""
        org_id = self._slug_index.get(slug)
        return self._orgs.get(org_id) if org_id else None

    def get_user_organizations(self, user_id: str) -> List[Organization]:
        """Get all organizations a user belongs to."""
        org_ids = self._user_org_index.get(user_id, [])
        return [self._orgs[oid] for oid in org_ids if oid in self._orgs]

    def update_plan(self, org_id: str, new_plan: str) -> Organization:
        """Update organization plan.

        Args:
            org_id: Organization ID
            new_plan: New plan name

        Returns:
            Updated Organization

        Raises:
            OrganizationError: If org not found or plan invalid
        """
        if new_plan not in ALL_PLANS:
            raise OrganizationError(f"Invalid plan: {new_plan}")

        org = self._orgs.get(org_id)
        if not org:
            raise OrganizationError(f"Organization not found: {org_id}")

        org.plan = new_plan
        org.updated_at = datetime.now(timezone.utc).isoformat()

        # Disable SSO if downgraded from SSO plan
        if new_plan not in SSO_PLANS and org.sso_config.enabled:
            org.sso_config.enabled = False

        return org

    def configure_saml(self, org_id: str, saml_config: Dict[str, Any]) -> Organization:
        """Configure SAML 2.0 for an organization.

        Args:
            org_id: Organization ID
            saml_config: SAML configuration dict

        Returns:
            Updated Organization

        Raises:
            PlanGatingError: If org plan doesn't support SSO
            OrganizationError: If org not found or config invalid
        """
        org = self._get_org_or_raise(org_id)
        self._require_sso_plan(org)

        # Validate required fields
        required = ["idp_entity_id", "idp_sso_url", "idp_certificate"]
        missing = [f for f in required if not saml_config.get(f)]
        if missing:
            raise OrganizationError(f"Missing required SAML fields: {missing}")

        sso = org.sso_config
        sso.sso_type = "saml"
        sso.saml_idp_entity_id = saml_config["idp_entity_id"]
        sso.saml_idp_sso_url = saml_config["idp_sso_url"]
        sso.saml_idp_certificate = saml_config["idp_certificate"]
        sso.saml_sp_entity_id = saml_config.get("sp_entity_id", f"urn:agent-dashboard:org:{org.slug}")
        sso.saml_acs_url = saml_config.get("acs_url", "")
        sso.saml_attribute_mapping = saml_config.get("attribute_mapping", {})
        sso.saml_want_assertions_signed = saml_config.get("want_assertions_signed", True)
        sso.updated_at = datetime.now(timezone.utc).isoformat()

        org.updated_at = datetime.now(timezone.utc).isoformat()
        return org

    def configure_oidc(self, org_id: str, oidc_config: Dict[str, Any]) -> Organization:
        """Configure OIDC for an organization.

        Args:
            org_id: Organization ID
            oidc_config: OIDC configuration dict

        Returns:
            Updated Organization

        Raises:
            PlanGatingError: If org plan doesn't support SSO
            OrganizationError: If org not found or config invalid
        """
        org = self._get_org_or_raise(org_id)
        self._require_sso_plan(org)

        required = ["issuer", "client_id", "client_secret"]
        missing = [f for f in required if not oidc_config.get(f)]
        if missing:
            raise OrganizationError(f"Missing required OIDC fields: {missing}")

        sso = org.sso_config
        sso.sso_type = "oidc"
        sso.oidc_issuer = oidc_config["issuer"]
        sso.oidc_client_id = oidc_config["client_id"]
        sso.oidc_client_secret = oidc_config["client_secret"]
        sso.oidc_discovery_url = oidc_config.get("discovery_url", "")
        sso.oidc_redirect_uri = oidc_config.get("redirect_uri", "")
        sso.oidc_scopes = oidc_config.get("scopes", ["openid", "email", "profile"])
        sso.oidc_attribute_mapping = oidc_config.get("attribute_mapping", {})
        sso.updated_at = datetime.now(timezone.utc).isoformat()

        org.updated_at = datetime.now(timezone.utc).isoformat()
        return org

    def enable_sso(self, org_id: str) -> Organization:
        """Enable SSO for an organization (requires prior SAML or OIDC config)."""
        org = self._get_org_or_raise(org_id)
        self._require_sso_plan(org)

        if not org.sso_config.sso_type:
            raise OrganizationError(
                "Cannot enable SSO: no SAML or OIDC configuration found. "
                "Configure SAML or OIDC first."
            )

        org.sso_config.enabled = True
        org.sso_config.updated_at = datetime.now(timezone.utc).isoformat()
        org.updated_at = datetime.now(timezone.utc).isoformat()
        return org

    def disable_sso(self, org_id: str) -> Organization:
        """Disable SSO for an organization."""
        org = self._get_org_or_raise(org_id)
        org.sso_config.enabled = False
        org.sso_config.updated_at = datetime.now(timezone.utc).isoformat()
        org.updated_at = datetime.now(timezone.utc).isoformat()
        return org

    def generate_scim_token(self, org_id: str) -> str:
        """Generate a new SCIM bearer token for an organization.

        Args:
            org_id: Organization ID

        Returns:
            New SCIM token

        Raises:
            PlanGatingError: If org plan doesn't support SCIM
        """
        org = self._get_org_or_raise(org_id)
        self._require_sso_plan(org)

        token = f"scim_{secrets.token_urlsafe(32)}"
        org.sso_config.scim_token = token
        org.sso_config.scim_enabled = True
        org.sso_config.updated_at = datetime.now(timezone.utc).isoformat()
        org.updated_at = datetime.now(timezone.utc).isoformat()
        return token

    def get_org_by_scim_token(self, token: str) -> Optional[Organization]:
        """Look up organization by SCIM token."""
        for org in self._orgs.values():
            if org.sso_config.scim_token == token and org.sso_config.scim_enabled:
                return org
        return None

    def add_member(self, org_id: str, user_id: str, role: str = "member") -> Organization:
        """Add a member to an organization."""
        org = self._get_org_or_raise(org_id)
        org.members[user_id] = role
        org.updated_at = datetime.now(timezone.utc).isoformat()

        if user_id not in self._user_org_index:
            self._user_org_index[user_id] = []
        if org_id not in self._user_org_index[user_id]:
            self._user_org_index[user_id].append(org_id)

        return org

    def remove_member(self, org_id: str, user_id: str) -> Organization:
        """Remove a member from an organization."""
        org = self._get_org_or_raise(org_id)
        org.members.pop(user_id, None)
        org.updated_at = datetime.now(timezone.utc).isoformat()

        if user_id in self._user_org_index:
            self._user_org_index[user_id] = [
                oid for oid in self._user_org_index[user_id] if oid != org_id
            ]

        return org

    def list_organizations(self) -> List[Organization]:
        """List all organizations."""
        return list(self._orgs.values())

    def _get_org_or_raise(self, org_id: str) -> Organization:
        """Get organization or raise OrganizationError."""
        org = self._orgs.get(org_id)
        if not org:
            raise OrganizationError(f"Organization not found: {org_id}")
        return org

    def _require_sso_plan(self, org: Organization) -> None:
        """Raise PlanGatingError if org plan doesn't support SSO."""
        if not org.sso_allowed:
            raise PlanGatingError(
                f"SSO requires an Organization or Enterprise plan. "
                f"Current plan: '{org.plan}'. "
                f"Upgrade to access SSO, JIT provisioning, and SCIM features."
            )

    def _generate_slug(self, name: str) -> str:
        """Generate a URL-safe slug from organization name."""
        import re
        slug = name.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug).strip('-')
        slug = slug[:50]  # Max 50 chars

        # Ensure uniqueness
        base_slug = slug
        counter = 1
        while slug in self._slug_index:
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug or f"org-{secrets.token_hex(4)}"
