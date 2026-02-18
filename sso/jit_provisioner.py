"""JIT (Just-in-Time) User Provisioning.

AI-232: Enterprise SSO - JIT provisioning creates user accounts on first SSO login.

Security considerations:
    - Only creates users from verified SSO assertions (SAML/OIDC)
    - Email domain validated against organization's allowed_domains
    - Role assignment based on IdP group membership (configurable)
    - Prevents privilege escalation via group mapping
    - Audit trail for all provisioning events
"""

import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class JITError(Exception):
    """JIT provisioning error."""
    pass


class JITDomainError(JITError):
    """Email domain not allowed for this organization."""
    pass


class JITProvisioningDisabledError(JITError):
    """JIT provisioning is disabled for this organization."""
    pass


@dataclass
class JITResult:
    """Result of a JIT provisioning operation."""

    user_id: str
    email: str
    is_new_user: bool  # True if newly created, False if existing user updated
    action: str  # "created" | "updated" | "linked"
    role: str
    org_id: str
    groups: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    provisioned_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ProvisionedUser:
    """A JIT-provisioned user record."""

    user_id: str
    email: str
    first_name: str
    last_name: str
    display_name: str
    role: str
    org_id: str
    sso_provider: str  # "saml" | "oidc"
    external_id: str  # NameID (SAML) or sub (OIDC)
    groups: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_login: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# Role hierarchy for privilege escalation prevention
ROLE_HIERARCHY = {
    "owner": 100,
    "admin": 80,
    "manager": 60,
    "member": 40,
    "viewer": 20,
    "guest": 10,
}

# Maximum role assignable via JIT provisioning (cannot JIT-provision owners/admins)
JIT_MAX_ROLE = "manager"
JIT_MAX_ROLE_LEVEL = ROLE_HIERARCHY[JIT_MAX_ROLE]


class JITProvisioner:
    """Just-in-Time user provisioning from SSO assertions.

    Creates or updates user accounts automatically when users authenticate
    via SSO for the first time (or after attribute changes).

    Security:
        - Email domain whitelist enforced
        - Role capped at JIT_MAX_ROLE to prevent privilege escalation
        - All provisioning events logged in audit trail
        - External ID (NameID/sub) used to detect returning users
    """

    def __init__(self):
        # user_id -> ProvisionedUser
        self._users: Dict[str, ProvisionedUser] = {}
        # (org_id, external_id) -> user_id (lookup by SSO identity)
        self._external_id_index: Dict[tuple, str] = {}
        # email -> user_id
        self._email_index: Dict[str, str] = {}
        # Audit trail
        self._audit_log: List[Dict[str, Any]] = []

    def provision_from_saml(
        self,
        org_id: str,
        sso_config: Any,  # SSOConfig from organization_store
        saml_response: Any,  # SAMLResponse from saml_handler
    ) -> JITResult:
        """Provision or update a user from a SAML response.

        Args:
            org_id: Organization ID
            sso_config: Organization's SSO configuration
            saml_response: Parsed SAMLResponse object

        Returns:
            JITResult with provisioning outcome

        Raises:
            JITProvisioningDisabledError: If JIT is disabled
            JITDomainError: If email domain is not allowed
            JITError: On other provisioning errors
        """
        if not sso_config.jit_enabled:
            raise JITProvisioningDisabledError(
                f"JIT provisioning is disabled for organization {org_id}"
            )

        email = saml_response.email or saml_response.name_id
        if not email or "@" not in email:
            raise JITError(
                f"Cannot provision user: no valid email in SAML response. "
                f"NameID: {saml_response.name_id}"
            )

        self._validate_email_domain(email, sso_config.allowed_domains)

        external_id = saml_response.name_id
        groups = saml_response.groups or []
        role = self._determine_role(groups, sso_config.jit_group_role_mapping, sso_config.jit_default_role)

        first_name = saml_response.first_name or ""
        last_name = saml_response.last_name or ""
        display_name = saml_response.display_name or f"{first_name} {last_name}".strip() or email

        return self._provision_user(
            org_id=org_id,
            email=email,
            external_id=external_id,
            sso_provider="saml",
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
            role=role,
            groups=groups,
            attributes={
                "session_index": saml_response.session_index,
                "issuer": saml_response.issuer,
            },
        )

    def provision_from_oidc(
        self,
        org_id: str,
        sso_config: Any,  # SSOConfig from organization_store
        oidc_response: Any,  # OIDCTokenResponse from oidc_handler
    ) -> JITResult:
        """Provision or update a user from an OIDC token response.

        Args:
            org_id: Organization ID
            sso_config: Organization's SSO configuration
            oidc_response: OIDCTokenResponse object

        Returns:
            JITResult with provisioning outcome

        Raises:
            JITProvisioningDisabledError: If JIT is disabled
            JITDomainError: If email domain is not allowed
            JITError: On other provisioning errors
        """
        if not sso_config.jit_enabled:
            raise JITProvisioningDisabledError(
                f"JIT provisioning is disabled for organization {org_id}"
            )

        email = oidc_response.email
        if not email or "@" not in email:
            raise JITError(
                f"Cannot provision user: no valid email in OIDC response. "
                f"sub: {oidc_response.sub}"
            )

        if not oidc_response.email_verified:
            # Allow unverified emails but log warning
            self._audit("warning", org_id, email, "email_not_verified", {})

        self._validate_email_domain(email, sso_config.allowed_domains)

        external_id = oidc_response.sub
        groups = oidc_response.groups or []
        role = self._determine_role(groups, sso_config.jit_group_role_mapping, sso_config.jit_default_role)

        first_name = oidc_response.first_name or ""
        last_name = oidc_response.last_name or ""
        display_name = (
            oidc_response.display_name
            or f"{first_name} {last_name}".strip()
            or email
        )

        return self._provision_user(
            org_id=org_id,
            email=email,
            external_id=external_id,
            sso_provider="oidc",
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
            role=role,
            groups=groups,
            attributes={
                "iss": oidc_response.iss,
                "email_verified": oidc_response.email_verified,
            },
        )

    def _provision_user(
        self,
        org_id: str,
        email: str,
        external_id: str,
        sso_provider: str,
        first_name: str,
        last_name: str,
        display_name: str,
        role: str,
        groups: List[str],
        attributes: Dict[str, Any],
    ) -> JITResult:
        """Core provisioning logic: create or update user."""
        key = (org_id, external_id)
        email_lower = email.lower()

        # Check if user exists by external ID
        existing_user_id = self._external_id_index.get(key)

        # Also check by email (for linking)
        if not existing_user_id:
            existing_user_id = self._email_index.get(email_lower)

        if existing_user_id and existing_user_id in self._users:
            # Update existing user
            user = self._users[existing_user_id]
            user.email = email_lower
            user.first_name = first_name
            user.last_name = last_name
            user.display_name = display_name
            user.groups = groups
            user.role = role
            user.sso_provider = sso_provider
            user.external_id = external_id
            user.attributes.update(attributes)
            user.last_login = datetime.now(timezone.utc).isoformat()
            user.last_updated = datetime.now(timezone.utc).isoformat()
            user.is_active = True

            self._external_id_index[key] = existing_user_id
            self._audit("info", org_id, email, "user_updated", {"user_id": existing_user_id, "role": role})

            return JITResult(
                user_id=existing_user_id,
                email=email_lower,
                is_new_user=False,
                action="updated",
                role=role,
                org_id=org_id,
                groups=groups,
                attributes=attributes,
            )
        else:
            # Create new user
            user_id = str(uuid.uuid4())
            user = ProvisionedUser(
                user_id=user_id,
                email=email_lower,
                first_name=first_name,
                last_name=last_name,
                display_name=display_name,
                role=role,
                org_id=org_id,
                sso_provider=sso_provider,
                external_id=external_id,
                groups=groups,
                attributes=attributes,
            )

            self._users[user_id] = user
            self._external_id_index[key] = user_id
            self._email_index[email_lower] = user_id

            self._audit("info", org_id, email, "user_created", {"user_id": user_id, "role": role})

            return JITResult(
                user_id=user_id,
                email=email_lower,
                is_new_user=True,
                action="created",
                role=role,
                org_id=org_id,
                groups=groups,
                attributes=attributes,
            )

    def get_user(self, user_id: str) -> Optional[ProvisionedUser]:
        """Get a provisioned user by ID."""
        return self._users.get(user_id)

    def get_user_by_email(self, email: str) -> Optional[ProvisionedUser]:
        """Get a provisioned user by email."""
        user_id = self._email_index.get(email.lower())
        return self._users.get(user_id) if user_id else None

    def list_org_users(self, org_id: str) -> List[ProvisionedUser]:
        """List all provisioned users for an organization."""
        return [u for u in self._users.values() if u.org_id == org_id]

    def deactivate_user(self, user_id: str, org_id: str) -> bool:
        """Deactivate a provisioned user."""
        user = self._users.get(user_id)
        if not user or user.org_id != org_id:
            return False
        user.is_active = False
        user.last_updated = datetime.now(timezone.utc).isoformat()
        self._audit("info", org_id, user.email, "user_deactivated", {"user_id": user_id})
        return True

    def get_audit_log(self, org_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get provisioning audit log, optionally filtered by org."""
        if org_id:
            return [e for e in self._audit_log if e.get("org_id") == org_id]
        return list(self._audit_log)

    def _validate_email_domain(self, email: str, allowed_domains: List[str]) -> None:
        """Validate email domain against allowed domains list."""
        if not allowed_domains:
            return  # No domain restriction configured

        domain = email.split("@")[-1].lower()
        allowed = [d.lower().lstrip("@") for d in allowed_domains]

        if domain not in allowed:
            raise JITDomainError(
                f"Email domain '{domain}' is not allowed for this organization. "
                f"Allowed domains: {allowed}"
            )

    def _determine_role(
        self,
        groups: List[str],
        group_role_mapping: Dict[str, str],
        default_role: str,
    ) -> str:
        """Determine user role from groups and mapping.

        Security: Role is capped at JIT_MAX_ROLE to prevent privilege escalation.
        """
        best_role = default_role
        best_level = ROLE_HIERARCHY.get(default_role, 0)

        for group in groups:
            mapped_role = group_role_mapping.get(group)
            if mapped_role:
                role_level = ROLE_HIERARCHY.get(mapped_role, 0)
                if role_level > best_level:
                    best_role = mapped_role
                    best_level = role_level

        # Cap at JIT_MAX_ROLE for security
        if ROLE_HIERARCHY.get(best_role, 0) > JIT_MAX_ROLE_LEVEL:
            best_role = JIT_MAX_ROLE

        return best_role

    def _audit(
        self,
        level: str,
        org_id: str,
        email: str,
        event: str,
        details: Dict[str, Any],
    ) -> None:
        """Add entry to provisioning audit log."""
        self._audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "org_id": org_id,
            "email": email,
            "event": event,
            "details": details,
        })
        # Cap audit log size
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]
