"""SSO (Single Sign-On) module for Enterprise Authentication.

AI-232: Enterprise SSO - SAML 2.0, OIDC, JIT provisioning, SCIM 2.0

This module provides:
    - SAML 2.0 authentication via Python stdlib (xml.etree.ElementTree)
    - OIDC authentication via aiohttp
    - Organization management with SSO configuration
    - Just-in-Time (JIT) user provisioning
    - SCIM 2.0 user lifecycle management

Plan requirements: Organization plan or higher.
"""

from sso.saml_handler import SAMLHandler, SAMLConfig, SAMLResponse, SAMLError
from sso.oidc_handler import OIDCHandler, OIDCConfig, OIDCTokenResponse, OIDCError
from sso.organization_store import OrganizationStore, Organization, SSOConfig
from sso.jit_provisioner import JITProvisioner, JITResult
from sso.scim_handler import SCIMHandler, SCIMUser, SCIMGroup

__all__ = [
    "SAMLHandler",
    "SAMLConfig",
    "SAMLResponse",
    "SAMLError",
    "OIDCHandler",
    "OIDCConfig",
    "OIDCTokenResponse",
    "OIDCError",
    "OrganizationStore",
    "Organization",
    "SSOConfig",
    "JITProvisioner",
    "JITResult",
    "SCIMHandler",
    "SCIMUser",
    "SCIMGroup",
]
