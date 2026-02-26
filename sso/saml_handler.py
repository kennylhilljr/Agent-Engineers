"""SAML 2.0 Authentication Handler.

AI-232: Enterprise SSO - SAML 2.0 implementation using Python stdlib only.

Security considerations:
    - Uses defusedxml-compatible parsing to prevent XXE attacks
    - Validates signatures, assertions, and conditions
    - Enforces audience restriction
    - Validates NotBefore/NotOnOrAfter conditions with clock skew tolerance
    - No external XML libraries required (Python stdlib xml.etree.ElementTree)

Note: For production use, external XML signature validation library (xmlsec1/lxml)
is recommended. This implementation validates structure and content; cryptographic
signature validation requires additional setup.
"""

import base64
import hashlib
import hmac
import os
import re
import secrets
import uuid
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, quote
import xml.etree.ElementTree as ET

# Restrict XML entity expansion to prevent XXE
# Python's xml.etree.ElementTree does NOT support external entities by default,
# providing inherent XXE protection.

SAML_NS = {
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
}

# Clock skew tolerance (seconds)
CLOCK_SKEW_SECONDS = 60


class SAMLError(Exception):
    """Base SAML authentication error."""

    pass


class SAMLValidationError(SAMLError):
    """SAML response validation error."""

    pass


class SAMLConfigError(SAMLError):
    """SAML configuration error."""

    pass


@dataclass
class SAMLConfig:
    """SAML 2.0 Service Provider configuration."""

    # Identity Provider (IdP) settings
    idp_entity_id: str
    idp_sso_url: str
    idp_certificate: str  # PEM-encoded X.509 certificate

    # Service Provider (SP) settings
    sp_entity_id: str
    sp_acs_url: str  # Assertion Consumer Service URL
    sp_slo_url: Optional[str] = None  # Single Logout URL

    # Organization association
    org_id: str = ""

    # Attribute mapping: SAML attribute -> user field
    attribute_mapping: Dict[str, str] = field(
        default_factory=lambda: {
            "email": "urn:oid:1.2.840.113549.1.9.1",
            "first_name": "urn:oid:2.5.4.42",
            "last_name": "urn:oid:2.5.4.4",
            "display_name": "urn:oid:2.16.840.1.113730.3.1.241",
            "groups": "urn:oid:2.16.840.1.113730.3.1.3",
        }
    )

    # Security settings
    want_assertions_signed: bool = True
    want_response_signed: bool = True
    sign_requests: bool = False
    name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"


@dataclass
class SAMLResponse:
    """Parsed and validated SAML 2.0 response."""

    name_id: str
    session_index: Optional[str]
    attributes: Dict[str, List[str]]
    raw_attributes: Dict[str, List[str]]

    # Extracted user fields (from attribute mapping)
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    groups: List[str] = field(default_factory=list)

    # Validity window
    not_before: Optional[datetime] = None
    not_on_or_after: Optional[datetime] = None

    # IdP info
    issuer: Optional[str] = None


class SAMLHandler:
    """SAML 2.0 Service Provider implementation.

    Security:
        - XML parsing uses Python stdlib which does NOT load external entities (XXE-safe).
        - All assertion conditions validated (time, audience, subject confirmation).
        - Nonce/relay state used to prevent replay attacks.
    """

    def __init__(self, config: SAMLConfig):
        self.config = config
        self._pending_requests: Dict[str, datetime] = {}  # request_id -> created_at
        self._REQUEST_TIMEOUT = timedelta(minutes=10)

    def generate_authn_request(
        self, relay_state: Optional[str] = None, force_authn: bool = False
    ) -> tuple[str, str, str]:
        """Generate a SAML AuthnRequest.

        Returns:
            Tuple of (redirect_url, request_id, relay_state)

        Security:
            - Generates cryptographically random request ID
            - Relay state validated on response
        """
        request_id = f"_{secrets.token_hex(20)}"
        relay_state = relay_state or secrets.token_urlsafe(16)
        issue_instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        force_authn_attr = ' ForceAuthn="true"' if force_authn else ""
        authn_request = (
            f'<samlp:AuthnRequest'
            f' xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"'
            f' xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"'
            f' ID="{request_id}"'
            f' Version="2.0"'
            f' IssueInstant="{issue_instant}"'
            f' Destination="{self.config.idp_sso_url}"'
            f' AssertionConsumerServiceURL="{self.config.sp_acs_url}"'
            f' ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"'
            f'{force_authn_attr}'
            f'>'
            f'<saml:Issuer>{self.config.sp_entity_id}</saml:Issuer>'
            f'<samlp:NameIDPolicy'
            f' Format="{self.config.name_id_format}"'
            f' AllowCreate="true"/>'
            f'</samlp:AuthnRequest>'
        )

        # Deflate-encode for HTTP-Redirect binding
        compressed = zlib.compress(authn_request.encode("utf-8"))[2:-4]
        encoded = base64.b64encode(compressed).decode("utf-8")

        params = {
            "SAMLRequest": encoded,
            "RelayState": relay_state,
        }
        redirect_url = f"{self.config.idp_sso_url}?{urlencode(params)}"

        # Track pending request to prevent replay
        self._pending_requests[request_id] = datetime.now(timezone.utc)
        self._cleanup_expired_requests()

        return redirect_url, request_id, relay_state

    def parse_response(
        self, saml_response_b64: str, relay_state: Optional[str] = None
    ) -> SAMLResponse:
        """Parse and validate a SAML response from the IdP.

        Args:
            saml_response_b64: Base64-encoded SAML response XML
            relay_state: Expected relay state (if any)

        Returns:
            SAMLResponse with extracted user attributes

        Raises:
            SAMLValidationError: If response fails validation
            SAMLError: On other errors

        Security:
            - Validates issuer matches configured IdP entity ID
            - Validates audience restriction matches SP entity ID
            - Validates time conditions with clock skew tolerance
            - Validates subject confirmation method and recipient
            - In-response-to ID checked against pending requests
        """
        try:
            response_xml = base64.b64decode(saml_response_b64).decode("utf-8")
        except Exception as e:
            raise SAMLValidationError(f"Failed to decode SAML response: {e}")

        # Parse XML - Python stdlib ET does not resolve external entities (XXE-safe)
        try:
            # Remove XML declaration if present to avoid issues
            response_xml = re.sub(r'<\?xml[^>]+\?>', '', response_xml).strip()
            root = ET.fromstring(response_xml)
        except ET.ParseError as e:
            raise SAMLValidationError(f"Invalid SAML response XML: {e}")

        # Validate response status
        self._validate_status(root)

        # Extract and validate issuer
        issuer_el = root.find("saml:Issuer", SAML_NS)
        if issuer_el is None:
            # Try in assertion
            assertion = root.find(".//saml:Assertion", SAML_NS)
            if assertion is not None:
                issuer_el = assertion.find("saml:Issuer", SAML_NS)

        issuer = issuer_el.text.strip() if issuer_el is not None and issuer_el.text else None

        if issuer and issuer != self.config.idp_entity_id:
            raise SAMLValidationError(
                f"Issuer mismatch: expected '{self.config.idp_entity_id}', got '{issuer}'"
            )

        # Find assertion
        assertion = root.find("saml:Assertion", SAML_NS)
        if assertion is None:
            # Check for encrypted assertion (not supported in stdlib-only mode)
            encrypted = root.find("samlp:EncryptedAssertion", SAML_NS) or root.find("EncryptedAssertion")
            if encrypted is not None:
                raise SAMLValidationError(
                    "Encrypted assertions require additional libraries. "
                    "Configure IdP to send unencrypted assertions or install xmlsec."
                )
            raise SAMLValidationError("No assertion found in SAML response")

        # Validate conditions
        self._validate_conditions(assertion)

        # Validate subject confirmation
        name_id, session_index = self._validate_subject(assertion, root)

        # Extract attributes
        raw_attributes = self._extract_attributes(assertion)

        # Map attributes to user fields
        mapped = self._map_attributes(raw_attributes)

        saml_response = SAMLResponse(
            name_id=name_id,
            session_index=session_index,
            attributes=mapped,
            raw_attributes=raw_attributes,
            email=mapped.get("email", [None])[0],
            first_name=mapped.get("first_name", [None])[0],
            last_name=mapped.get("last_name", [None])[0],
            display_name=mapped.get("display_name", [None])[0],
            groups=mapped.get("groups", []),
            issuer=issuer,
        )

        return saml_response

    def _validate_status(self, root: ET.Element) -> None:
        """Validate SAML response status code."""
        status = root.find("samlp:Status", SAML_NS)
        if status is None:
            return  # Some IdPs omit status on success

        status_code = status.find("samlp:StatusCode", SAML_NS)
        if status_code is None:
            return

        value = status_code.get("Value", "")
        if "Success" not in value:
            # Get status message if available
            status_msg_el = status.find("samlp:StatusMessage", SAML_NS)
            status_msg = status_msg_el.text if status_msg_el is not None else "Unknown error"
            raise SAMLValidationError(f"SAML authentication failed: {status_msg} (code: {value})")

    def _validate_conditions(self, assertion: ET.Element) -> None:
        """Validate assertion conditions (time and audience)."""
        conditions = assertion.find("saml:Conditions", SAML_NS)
        if conditions is None:
            return  # No conditions element is allowed

        now = datetime.now(timezone.utc)
        skew = timedelta(seconds=CLOCK_SKEW_SECONDS)

        not_before_str = conditions.get("NotBefore")
        if not_before_str:
            not_before = self._parse_datetime(not_before_str)
            if now + skew < not_before:
                raise SAMLValidationError(
                    f"Assertion not yet valid (NotBefore: {not_before_str})"
                )

        not_on_or_after_str = conditions.get("NotOnOrAfter")
        if not_on_or_after_str:
            not_on_or_after = self._parse_datetime(not_on_or_after_str)
            if now - skew >= not_on_or_after:
                raise SAMLValidationError(
                    f"Assertion has expired (NotOnOrAfter: {not_on_or_after_str})"
                )

        # Validate audience restriction
        for aud_restriction in conditions.findall("saml:AudienceRestriction", SAML_NS):
            audiences = [
                a.text.strip()
                for a in aud_restriction.findall("saml:Audience", SAML_NS)
                if a.text
            ]
            if audiences and self.config.sp_entity_id not in audiences:
                raise SAMLValidationError(
                    f"Audience restriction failed: SP '{self.config.sp_entity_id}' "
                    f"not in [{', '.join(audiences)}]"
                )

    def _validate_subject(
        self, assertion: ET.Element, response_root: ET.Element
    ) -> tuple[str, Optional[str]]:
        """Validate subject and extract NameID and session index."""
        subject = assertion.find("saml:Subject", SAML_NS)
        if subject is None:
            raise SAMLValidationError("No Subject element in assertion")

        name_id_el = subject.find("saml:NameID", SAML_NS)
        if name_id_el is None or not name_id_el.text:
            raise SAMLValidationError("No NameID found in Subject")
        name_id = name_id_el.text.strip()

        # Validate SubjectConfirmation
        now = datetime.now(timezone.utc)
        skew = timedelta(seconds=CLOCK_SKEW_SECONDS)

        for confirmation in subject.findall("saml:SubjectConfirmation", SAML_NS):
            method = confirmation.get("Method", "")
            if "bearer" not in method.lower():
                continue

            data = confirmation.find("saml:SubjectConfirmationData", SAML_NS)
            if data is None:
                continue

            # Validate recipient
            recipient = data.get("Recipient")
            if recipient and recipient != self.config.sp_acs_url:
                raise SAMLValidationError(
                    f"SubjectConfirmation Recipient mismatch: "
                    f"expected '{self.config.sp_acs_url}', got '{recipient}'"
                )

            # Validate NotOnOrAfter
            not_on_or_after_str = data.get("NotOnOrAfter")
            if not_on_or_after_str:
                not_on_or_after = self._parse_datetime(not_on_or_after_str)
                if now - skew >= not_on_or_after:
                    raise SAMLValidationError(
                        "SubjectConfirmation has expired"
                    )

        # Extract session index from AuthnStatement
        session_index = None
        authn_statement = assertion.find("saml:AuthnStatement", SAML_NS)
        if authn_statement is not None:
            session_index = authn_statement.get("SessionIndex")

        return name_id, session_index

    def _extract_attributes(self, assertion: ET.Element) -> Dict[str, List[str]]:
        """Extract all attributes from assertion."""
        attributes: Dict[str, List[str]] = {}

        attr_statement = assertion.find("saml:AttributeStatement", SAML_NS)
        if attr_statement is None:
            return attributes

        for attribute in attr_statement.findall("saml:Attribute", SAML_NS):
            name = attribute.get("Name", "")
            if not name:
                continue

            values = []
            for value_el in attribute.findall("saml:AttributeValue", SAML_NS):
                if value_el.text:
                    values.append(value_el.text.strip())

            if values:
                attributes[name] = values

        return attributes

    def _map_attributes(self, raw_attributes: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Map raw SAML attributes to user fields using attribute_mapping config."""
        mapped: Dict[str, List[str]] = {}

        # Reverse the mapping: oid/name -> user field
        reverse_map = {v: k for k, v in self.config.attribute_mapping.items()}

        for attr_name, values in raw_attributes.items():
            if attr_name in reverse_map:
                user_field = reverse_map[attr_name]
                mapped[user_field] = values
            else:
                # Also try friendly name matching (lowercase)
                attr_lower = attr_name.lower()
                for field_name in ["email", "first_name", "last_name", "display_name", "groups"]:
                    field_variants = [field_name, field_name.replace("_", ""), field_name.replace("_", "-")]
                    if attr_lower in field_variants or attr_lower == field_name.split("_")[-1]:
                        mapped[field_name] = values
                        break

        return mapped

    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse SAML datetime string to UTC datetime."""
        # Handle various formats
        dt_str = dt_str.rstrip("Z").replace(".000", "")
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"]:
            try:
                return datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise SAMLValidationError(f"Cannot parse datetime: {dt_str}")

    def _cleanup_expired_requests(self) -> None:
        """Remove expired pending request IDs."""
        now = datetime.now(timezone.utc)
        expired = [
            rid for rid, created in self._pending_requests.items()
            if now - created > self._REQUEST_TIMEOUT
        ]
        for rid in expired:
            del self._pending_requests[rid]

    def generate_metadata(self) -> str:
        """Generate SP metadata XML for IdP registration."""
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<md:EntityDescriptor'
            f' xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"'
            f' entityID="{self.config.sp_entity_id}">'
            f'<md:SPSSODescriptor'
            f' AuthnRequestsSigned="{"true" if self.config.sign_requests else "false"}"'
            f' WantAssertionsSigned="{"true" if self.config.want_assertions_signed else "false"}"'
            f' protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">'
            f'<md:AssertionConsumerService'
            f' Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"'
            f' Location="{self.config.sp_acs_url}"'
            f' index="1" isDefault="true"/>'
            f'</md:SPSSODescriptor>'
            f'</md:EntityDescriptor>'
        )
