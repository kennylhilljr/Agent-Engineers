"""SCIM 2.0 User and Group Lifecycle Management.

AI-232: Enterprise SSO - SCIM 2.0 (System for Cross-domain Identity Management).

SCIM 2.0 enables IdPs to manage user lifecycle in the application:
    - Automated user provisioning/deprovisioning
    - Group management
    - User attribute synchronization

Security considerations:
    - All SCIM endpoints require Bearer token authentication
    - Token validated against organization's stored SCIM token
    - Operations scoped to specific organization via token
    - Input validation on all user/group attributes
    - Rate limiting should be applied at the API server layer

Reference: RFC 7642, RFC 7643, RFC 7644
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


SCIM_SCHEMA_USER = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_SCHEMA_GROUP = "urn:ietf:params:scim:schemas:core:2.0:Group"
SCIM_SCHEMA_LIST = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
SCIM_SCHEMA_ERROR = "urn:ietf:params:scim:api:messages:2.0:Error"
SCIM_SCHEMA_PATCH = "urn:ietf:params:scim:api:messages:2.0:PatchOp"


class SCIMError(Exception):
    """SCIM operation error."""

    def __init__(self, message: str, status: int = 400, scim_type: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.scim_type = scim_type


class SCIMAuthError(SCIMError):
    """SCIM authentication/authorization error."""

    def __init__(self, message: str = "Invalid or missing SCIM token"):
        super().__init__(message, status=401, scim_type="invalidCredentials")


class SCIMNotFoundError(SCIMError):
    """SCIM resource not found error."""

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(f"{resource_type} not found: {resource_id}", status=404)


@dataclass
class SCIMUser:
    """SCIM 2.0 User resource."""

    id: str
    user_name: str  # Unique username (typically email)
    external_id: Optional[str] = None

    # Name
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    formatted_name: Optional[str] = None

    # Contact
    email: Optional[str] = None
    email_type: str = "work"

    # Status
    active: bool = True

    # Organization
    org_id: str = ""

    # SCIM metadata
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_modified: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Groups this user belongs to
    groups: List[str] = field(default_factory=list)  # group IDs

    # Custom attributes
    custom_attributes: Dict[str, Any] = field(default_factory=dict)

    def to_scim_dict(self, base_url: str = "") -> Dict[str, Any]:
        """Convert to SCIM 2.0 User resource dict."""
        emails = []
        if self.email:
            emails.append({"value": self.email, "type": self.email_type, "primary": True})

        result: Dict[str, Any] = {
            "schemas": [SCIM_SCHEMA_USER],
            "id": self.id,
            "userName": self.user_name,
            "active": self.active,
            "name": {
                "givenName": self.given_name or "",
                "familyName": self.family_name or "",
                "formatted": self.formatted_name or f"{self.given_name or ''} {self.family_name or ''}".strip(),
            },
            "emails": emails,
            "meta": {
                "resourceType": "User",
                "created": self.created,
                "lastModified": self.last_modified,
                "location": f"{base_url}/scim/v2/Users/{self.id}" if base_url else f"/scim/v2/Users/{self.id}",
                "version": f'W/"{self.last_modified}"',
            },
        }

        if self.external_id:
            result["externalId"] = self.external_id

        if self.groups:
            result["groups"] = [{"value": gid, "$ref": f"/scim/v2/Groups/{gid}"} for gid in self.groups]

        return result


@dataclass
class SCIMGroup:
    """SCIM 2.0 Group resource."""

    id: str
    display_name: str
    external_id: Optional[str] = None

    # Members: list of user IDs
    members: List[str] = field(default_factory=list)

    # Organization
    org_id: str = ""

    # SCIM metadata
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_modified: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_scim_dict(self, base_url: str = "") -> Dict[str, Any]:
        """Convert to SCIM 2.0 Group resource dict."""
        result: Dict[str, Any] = {
            "schemas": [SCIM_SCHEMA_GROUP],
            "id": self.id,
            "displayName": self.display_name,
            "members": [
                {"value": uid, "$ref": f"/scim/v2/Users/{uid}"}
                for uid in self.members
            ],
            "meta": {
                "resourceType": "Group",
                "created": self.created,
                "lastModified": self.last_modified,
                "location": f"{base_url}/scim/v2/Groups/{self.id}" if base_url else f"/scim/v2/Groups/{self.id}",
                "version": f'W/"{self.last_modified}"',
            },
        }

        if self.external_id:
            result["externalId"] = self.external_id

        return result


class SCIMHandler:
    """SCIM 2.0 handler for user and group lifecycle management.

    All operations are scoped to an organization via SCIM bearer token.
    Token validated against OrganizationStore.

    Security:
        - Bearer token required for all operations
        - Operations isolated per organization
        - User deactivation preferred over deletion (soft delete)
    """

    def __init__(self, org_store: Any):  # OrganizationStore
        self._org_store = org_store
        self._users: Dict[str, SCIMUser] = {}  # user_id -> SCIMUser
        self._groups: Dict[str, SCIMGroup] = {}  # group_id -> SCIMGroup

    def authenticate_token(self, token: str) -> Any:
        """Validate SCIM bearer token and return organization.

        Args:
            token: Bearer token from Authorization header

        Returns:
            Organization object

        Raises:
            SCIMAuthError: If token is invalid
        """
        org = self._org_store.get_org_by_scim_token(token)
        if not org:
            raise SCIMAuthError("Invalid or missing SCIM bearer token")
        if not org.sso_config.scim_enabled:
            raise SCIMAuthError("SCIM is disabled for this organization")
        return org

    # ---- User Operations ----

    def create_user(self, org_id: str, scim_data: Dict[str, Any]) -> SCIMUser:
        """Create a new SCIM user.

        Args:
            org_id: Organization ID (from authenticated token)
            scim_data: SCIM User resource dict

        Returns:
            Created SCIMUser

        Raises:
            SCIMError: If username already exists or data is invalid
        """
        user_name = scim_data.get("userName")
        if not user_name:
            raise SCIMError("userName is required", status=400, scim_type="invalidValue")

        # Check for duplicate username in this org
        existing = self._find_user_by_username(org_id, user_name)
        if existing:
            raise SCIMError(
                f"User with userName '{user_name}' already exists",
                status=409,
                scim_type="uniqueness",
            )

        user_id = str(uuid.uuid4())
        name = scim_data.get("name", {})
        emails = scim_data.get("emails", [])
        primary_email = next(
            (e["value"] for e in emails if e.get("primary")),
            emails[0]["value"] if emails else user_name,
        )

        user = SCIMUser(
            id=user_id,
            user_name=user_name,
            external_id=scim_data.get("externalId"),
            given_name=name.get("givenName"),
            family_name=name.get("familyName"),
            formatted_name=name.get("formatted"),
            email=primary_email,
            active=scim_data.get("active", True),
            org_id=org_id,
        )

        self._users[user_id] = user
        return user

    def get_user(self, org_id: str, user_id: str) -> SCIMUser:
        """Get a SCIM user by ID.

        Raises:
            SCIMNotFoundError: If user not found or not in org
        """
        user = self._users.get(user_id)
        if not user or user.org_id != org_id:
            raise SCIMNotFoundError("User", user_id)
        return user

    def list_users(
        self,
        org_id: str,
        filter_str: Optional[str] = None,
        start_index: int = 1,
        count: int = 100,
    ) -> Tuple[List[SCIMUser], int]:
        """List SCIM users for an organization with optional filtering.

        Args:
            org_id: Organization ID
            filter_str: SCIM filter string (e.g. "userName eq \"john@example.com\"")
            start_index: 1-based start index (pagination)
            count: Number of results per page

        Returns:
            Tuple of (users_list, total_count)
        """
        users = [u for u in self._users.values() if u.org_id == org_id]

        if filter_str:
            users = self._apply_filter(users, filter_str)

        total = len(users)
        # Apply pagination (1-based index per SCIM spec)
        start = max(0, start_index - 1)
        users = users[start: start + count]

        return users, total

    def replace_user(self, org_id: str, user_id: str, scim_data: Dict[str, Any]) -> SCIMUser:
        """Replace (PUT) a SCIM user resource.

        Args:
            org_id: Organization ID
            user_id: User ID to replace
            scim_data: Complete replacement SCIM User resource

        Returns:
            Updated SCIMUser
        """
        user = self.get_user(org_id, user_id)

        name = scim_data.get("name", {})
        emails = scim_data.get("emails", [])
        primary_email = next(
            (e["value"] for e in emails if e.get("primary")),
            emails[0]["value"] if emails else user.email,
        )

        user.user_name = scim_data.get("userName", user.user_name)
        user.external_id = scim_data.get("externalId", user.external_id)
        user.given_name = name.get("givenName", user.given_name)
        user.family_name = name.get("familyName", user.family_name)
        user.formatted_name = name.get("formatted", user.formatted_name)
        user.email = primary_email
        user.active = scim_data.get("active", user.active)
        user.last_modified = datetime.now(timezone.utc).isoformat()

        return user

    def patch_user(self, org_id: str, user_id: str, patch_data: Dict[str, Any]) -> SCIMUser:
        """Patch (PATCH) a SCIM user resource.

        Supports SCIM PATCH operations: add, replace, remove.

        Args:
            org_id: Organization ID
            user_id: User ID to patch
            patch_data: SCIM PatchOp resource

        Returns:
            Updated SCIMUser
        """
        user = self.get_user(org_id, user_id)

        if patch_data.get("schemas") != [SCIM_SCHEMA_PATCH]:
            raise SCIMError("Invalid PATCH schema", status=400)

        for operation in patch_data.get("Operations", []):
            op = operation.get("op", "").lower()
            path = operation.get("path", "")
            value = operation.get("value")

            if op == "replace" or op == "add":
                if path == "active" or (not path and isinstance(value, dict) and "active" in value):
                    active_val = value if isinstance(value, bool) else value.get("active", user.active)
                    user.active = active_val
                elif path == "userName":
                    user.user_name = value
                elif path == "name.givenName":
                    user.given_name = value
                elif path == "name.familyName":
                    user.family_name = value
                elif not path and isinstance(value, dict):
                    # Full attribute replacement
                    if "userName" in value:
                        user.user_name = value["userName"]
                    if "active" in value:
                        user.active = value["active"]
                    name = value.get("name", {})
                    if "givenName" in name:
                        user.given_name = name["givenName"]
                    if "familyName" in name:
                        user.family_name = name["familyName"]
            elif op == "remove":
                if path == "active":
                    user.active = True  # Default to active on remove

        user.last_modified = datetime.now(timezone.utc).isoformat()
        return user

    def delete_user(self, org_id: str, user_id: str) -> bool:
        """Delete (deactivate) a SCIM user.

        Performs soft delete by deactivating the user rather than removing.

        Returns:
            True if user was found and deactivated
        """
        user = self._users.get(user_id)
        if not user or user.org_id != org_id:
            raise SCIMNotFoundError("User", user_id)

        # Soft delete: deactivate rather than remove
        user.active = False
        user.last_modified = datetime.now(timezone.utc).isoformat()
        return True

    # ---- Group Operations ----

    def create_group(self, org_id: str, scim_data: Dict[str, Any]) -> SCIMGroup:
        """Create a new SCIM group."""
        display_name = scim_data.get("displayName")
        if not display_name:
            raise SCIMError("displayName is required", status=400, scim_type="invalidValue")

        group_id = str(uuid.uuid4())
        members = [m["value"] for m in scim_data.get("members", []) if "value" in m]

        group = SCIMGroup(
            id=group_id,
            display_name=display_name,
            external_id=scim_data.get("externalId"),
            members=members,
            org_id=org_id,
        )

        self._groups[group_id] = group

        # Update user group membership
        for user_id in members:
            user = self._users.get(user_id)
            if user and user.org_id == org_id:
                if group_id not in user.groups:
                    user.groups.append(group_id)

        return group

    def get_group(self, org_id: str, group_id: str) -> SCIMGroup:
        """Get a SCIM group by ID."""
        group = self._groups.get(group_id)
        if not group or group.org_id != org_id:
            raise SCIMNotFoundError("Group", group_id)
        return group

    def list_groups(
        self,
        org_id: str,
        filter_str: Optional[str] = None,
        start_index: int = 1,
        count: int = 100,
    ) -> Tuple[List[SCIMGroup], int]:
        """List SCIM groups for an organization."""
        groups = [g for g in self._groups.values() if g.org_id == org_id]

        if filter_str:
            groups = self._apply_group_filter(groups, filter_str)

        total = len(groups)
        start = max(0, start_index - 1)
        groups = groups[start: start + count]

        return groups, total

    def patch_group(self, org_id: str, group_id: str, patch_data: Dict[str, Any]) -> SCIMGroup:
        """Patch a SCIM group (add/remove members)."""
        group = self.get_group(org_id, group_id)

        for operation in patch_data.get("Operations", []):
            op = operation.get("op", "").lower()
            path = operation.get("path", "")
            value = operation.get("value", [])

            if path == "members":
                if op == "add":
                    new_members = [m["value"] for m in (value if isinstance(value, list) else []) if "value" in m]
                    for uid in new_members:
                        if uid not in group.members:
                            group.members.append(uid)
                        # Update user's group list
                        user = self._users.get(uid)
                        if user and user.org_id == org_id and group_id not in user.groups:
                            user.groups.append(group_id)
                elif op == "remove":
                    remove_ids = [m["value"] for m in (value if isinstance(value, list) else []) if "value" in m]
                    group.members = [m for m in group.members if m not in remove_ids]
                    for uid in remove_ids:
                        user = self._users.get(uid)
                        if user:
                            user.groups = [g for g in user.groups if g != group_id]
                elif op == "replace":
                    new_members = [m["value"] for m in (value if isinstance(value, list) else []) if "value" in m]
                    # Remove old membership
                    for uid in group.members:
                        user = self._users.get(uid)
                        if user:
                            user.groups = [g for g in user.groups if g != group_id]
                    group.members = new_members
                    # Add new membership
                    for uid in new_members:
                        user = self._users.get(uid)
                        if user and user.org_id == org_id and group_id not in user.groups:
                            user.groups.append(group_id)
            elif path == "displayName" and op in ("replace", "add"):
                group.display_name = value

        group.last_modified = datetime.now(timezone.utc).isoformat()
        return group

    def delete_group(self, org_id: str, group_id: str) -> bool:
        """Delete a SCIM group."""
        group = self._groups.get(group_id)
        if not group or group.org_id != org_id:
            raise SCIMNotFoundError("Group", group_id)

        # Remove group from all user memberships
        for user_id in group.members:
            user = self._users.get(user_id)
            if user:
                user.groups = [g for g in user.groups if g != group_id]

        del self._groups[group_id]
        return True

    # ---- Helper Methods ----

    def build_list_response(
        self,
        resources: List[Any],
        total: int,
        start_index: int,
        base_url: str = "",
    ) -> Dict[str, Any]:
        """Build a SCIM ListResponse."""
        return {
            "schemas": [SCIM_SCHEMA_LIST],
            "totalResults": total,
            "startIndex": start_index,
            "itemsPerPage": len(resources),
            "Resources": [
                r.to_scim_dict(base_url) if hasattr(r, "to_scim_dict") else r
                for r in resources
            ],
        }

    def build_error_response(self, error: SCIMError) -> Dict[str, Any]:
        """Build a SCIM error response."""
        result: Dict[str, Any] = {
            "schemas": [SCIM_SCHEMA_ERROR],
            "status": str(error.status),
            "detail": str(error),
        }
        if error.scim_type:
            result["scimType"] = error.scim_type
        return result

    def _find_user_by_username(self, org_id: str, user_name: str) -> Optional[SCIMUser]:
        """Find user by username within organization."""
        for user in self._users.values():
            if user.org_id == org_id and user.user_name.lower() == user_name.lower():
                return user
        return None

    def _apply_filter(self, users: List[SCIMUser], filter_str: str) -> List[SCIMUser]:
        """Apply basic SCIM filter to user list.

        Supports: userName eq, emails.value eq, active eq
        """
        # Parse simple "attr op value" filters
        import re
        match = re.match(r'(\w+(?:\.\w+)?)\s+(\w+)\s+"?([^"]*)"?', filter_str.strip())
        if not match:
            return users

        attr, op, value = match.group(1), match.group(2).lower(), match.group(3)

        filtered = []
        for user in users:
            if op == "eq":
                if attr == "userName" and user.user_name.lower() == value.lower():
                    filtered.append(user)
                elif attr in ("emails.value", "email") and user.email and user.email.lower() == value.lower():
                    filtered.append(user)
                elif attr == "active":
                    active_val = value.lower() == "true"
                    if user.active == active_val:
                        filtered.append(user)
                elif attr == "externalId" and user.external_id == value:
                    filtered.append(user)
        return filtered

    def _apply_group_filter(self, groups: List[SCIMGroup], filter_str: str) -> List[SCIMGroup]:
        """Apply basic SCIM filter to group list."""
        import re
        match = re.match(r'(\w+)\s+(\w+)\s+"?([^"]*)"?', filter_str.strip())
        if not match:
            return groups

        attr, op, value = match.group(1), match.group(2).lower(), match.group(3)

        if op == "eq" and attr == "displayName":
            return [g for g in groups if g.display_name.lower() == value.lower()]
        return groups
