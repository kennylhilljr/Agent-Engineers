"""Team management module for Agent Dashboard.

AI-245: Team Management - Roles & Permissions (Owner/Admin/Member/Viewer)

Provides org-level team management with granular role-based access control
for Organization and Fleet tiers.

Roles:
    Owner  - Full access, billing, delete org, transfer ownership
    Admin  - Manage members, projects, agents, integrations
    Member - Run agents, create/edit projects, view all
    Viewer - Read-only access to dashboard and reports
"""

from teams.models import (
    Role,
    TeamMember,
    Invitation,
    TeamStore,
    AuditLog,
    AuditEvent,
    TeamError,
    TeamPermissionError,
    PermissionError,  # backward-compatibility alias
    InvitationError,
    get_team_store,
    get_audit_log,
    reset_team_store,
)
from teams.rbac import (
    ROLE_HIERARCHY,
    ROLE_PERMISSIONS,
    Permission,
    require_role,
    require_permission,
    check_permission,
    can_manage_role,
)

__all__ = [
    # Models
    "Role",
    "TeamMember",
    "Invitation",
    "TeamStore",
    "AuditLog",
    "AuditEvent",
    "TeamError",
    "TeamPermissionError",
    "PermissionError",  # backward-compatibility alias
    "InvitationError",
    "get_team_store",
    "get_audit_log",
    "reset_team_store",
    # RBAC
    "ROLE_HIERARCHY",
    "ROLE_PERMISSIONS",
    "Permission",
    "require_role",
    "require_permission",
    "check_permission",
    "can_manage_role",
]
