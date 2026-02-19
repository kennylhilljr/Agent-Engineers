"""Team management data models.

AI-245: TeamMember, Role, Invitation data models and in-memory stores.

Provides:
    - Role enum (owner, admin, member, viewer)
    - TeamMember dataclass (user membership record per org)
    - Invitation dataclass (pending invite with token and role)
    - AuditEvent / AuditLog (role-change audit trail)
    - TeamStore (in-memory CRUD, thread-safe via simple dict ops)
"""

import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Role(str, Enum):
    """Organizational roles in ascending privilege order."""

    VIEWER = "viewer"
    MEMBER = "member"
    ADMIN = "admin"
    OWNER = "owner"

    def __str__(self) -> str:  # noqa: D105
        return self.value


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TeamError(Exception):
    """Base exception for team management errors."""


class TeamPermissionError(TeamError):
    """Raised when a user lacks the required role or permission."""


# Backward-compatibility alias — use TeamPermissionError in new code
PermissionError = TeamPermissionError


class InvitationError(TeamError):
    """Raised for invite-related errors (expired, invalid, already accepted)."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class TeamMember:
    """A user's membership record within an organization."""

    user_id: str
    org_id: str
    email: str
    display_name: str
    role: str  # Role value string
    invited_by: Optional[str] = None  # user_id of the inviter
    joined_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    is_active: bool = True
    # Per-project role overrides: project_id -> role string
    project_roles: Dict[str, str] = field(default_factory=dict)
    # SSO-provisioned flag (set by JIT provisioner)
    sso_provisioned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-safe dictionary."""
        return {
            "user_id": self.user_id,
            "org_id": self.org_id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
            "invited_by": self.invited_by,
            "joined_at": self.joined_at,
            "updated_at": self.updated_at,
            "is_active": self.is_active,
            "project_roles": self.project_roles,
            "sso_provisioned": self.sso_provisioned,
        }


@dataclass
class Invitation:
    """A pending invitation to join an organization."""

    invite_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    org_id: str = ""
    email: Optional[str] = None  # None for shareable link (no email restriction)
    role: str = Role.MEMBER.value
    invited_by: str = ""  # user_id of sender
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    expires_at: str = field(
        default_factory=lambda: (
            datetime.now(timezone.utc) + timedelta(days=7)
        ).isoformat()
    )
    accepted: bool = False
    accepted_by: Optional[str] = None  # user_id that accepted
    accepted_at: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """True if the invitation has passed its expiry time."""
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.now(timezone.utc) > expires

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-safe dictionary (token masked if accepted)."""
        return {
            "invite_id": self.invite_id,
            "token": self.token,
            "org_id": self.org_id,
            "email": self.email,
            "role": self.role,
            "invited_by": self.invited_by,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "accepted": self.accepted,
            "accepted_by": self.accepted_by,
            "accepted_at": self.accepted_at,
        }


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


@dataclass
class AuditEvent:
    """A single audit trail entry for team management actions."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str = ""
    actor_user_id: str = ""  # who performed the action
    target_user_id: Optional[str] = None  # who was affected (if applicable)
    event_type: str = ""  # e.g. "role_changed", "member_invited", etc.
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "org_id": self.org_id,
            "actor_user_id": self.actor_user_id,
            "target_user_id": self.target_user_id,
            "event_type": self.event_type,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class AuditLog:
    """In-memory audit log for team management events.

    Capped at 10,000 entries; oldest trimmed when cap exceeded.
    """

    _MAX_ENTRIES = 10_000

    def __init__(self) -> None:
        self._events: List[AuditEvent] = []

    def record(
        self,
        org_id: str,
        actor_user_id: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        target_user_id: Optional[str] = None,
    ) -> AuditEvent:
        """Append an audit event and return it."""
        event = AuditEvent(
            org_id=org_id,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            event_type=event_type,
            details=details or {},
        )
        self._events.append(event)
        if len(self._events) > self._MAX_ENTRIES:
            self._events = self._events[-5000:]
        return event

    def get_events(
        self,
        org_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Return events filtered by org and/or event type, newest first."""
        events = self._events
        if org_id:
            events = [e for e in events if e.org_id == org_id]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return list(reversed(events))[:limit]

    def clear(self) -> None:
        """Clear all events (for testing)."""
        self._events = []


# ---------------------------------------------------------------------------
# Team store
# ---------------------------------------------------------------------------


class TeamStore:
    """In-memory team member and invitation store.

    Key lookups:
        _members[org_id][user_id] -> TeamMember
        _invitations[token]       -> Invitation

    # TODO(production): Replace with PostgreSQL-backed store. The current
    # in-memory implementation loses all data on process restart and does not
    # support horizontal scaling. See TECHNICAL_DEBT.md for details.
    """

    def __init__(self) -> None:
        # org_id -> {user_id -> TeamMember}
        self._members: Dict[str, Dict[str, TeamMember]] = {}
        # token -> Invitation
        self._invitations: Dict[str, Invitation] = {}
        # org_id -> list of invite creation timestamps (for rate limiting)
        self._invite_timestamps: Dict[str, list] = {}

    # ------------------------------------------------------------------
    # Member management
    # ------------------------------------------------------------------

    def add_member(
        self,
        org_id: str,
        user_id: str,
        email: str,
        display_name: str,
        role: str,
        invited_by: Optional[str] = None,
        sso_provisioned: bool = False,
    ) -> TeamMember:
        """Add or update a member in the org."""
        if org_id not in self._members:
            self._members[org_id] = {}

        member = TeamMember(
            user_id=user_id,
            org_id=org_id,
            email=email,
            display_name=display_name,
            role=role,
            invited_by=invited_by,
            sso_provisioned=sso_provisioned,
        )
        self._members[org_id][user_id] = member
        return member

    def get_member(self, org_id: str, user_id: str) -> Optional[TeamMember]:
        """Look up a member by org and user ID."""
        return self._members.get(org_id, {}).get(user_id)

    def get_member_by_email(self, org_id: str, email: str) -> Optional[TeamMember]:
        """Look up a member by org and email address."""
        for m in self._members.get(org_id, {}).values():
            if m.email.lower() == email.lower():
                return m
        return None

    def list_members(self, org_id: str) -> List[TeamMember]:
        """Return all active members for an org."""
        return [
            m for m in self._members.get(org_id, {}).values()
            if m.is_active
        ]

    def update_role(
        self,
        org_id: str,
        user_id: str,
        new_role: str,
    ) -> TeamMember:
        """Change a member's org-level role.

        Raises:
            TeamError: If member not found.
        """
        member = self.get_member(org_id, user_id)
        if not member:
            raise TeamError(f"Member {user_id} not found in org {org_id}")
        member.role = new_role
        member.updated_at = datetime.now(timezone.utc).isoformat()
        return member

    def update_project_role(
        self,
        org_id: str,
        user_id: str,
        project_id: str,
        role: str,
    ) -> TeamMember:
        """Set a per-project role override for a member.

        Raises:
            TeamError: If member not found.
        """
        member = self.get_member(org_id, user_id)
        if not member:
            raise TeamError(f"Member {user_id} not found in org {org_id}")
        member.project_roles[project_id] = role
        member.updated_at = datetime.now(timezone.utc).isoformat()
        return member

    def remove_member(self, org_id: str, user_id: str) -> bool:
        """Soft-delete a member (set is_active=False).

        Returns:
            True if member existed and was deactivated, False otherwise.
        """
        member = self.get_member(org_id, user_id)
        if not member:
            return False
        member.is_active = False
        member.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    def hard_remove_member(self, org_id: str, user_id: str) -> bool:
        """Permanently remove a member from the store (for testing)."""
        org_dict = self._members.get(org_id, {})
        if user_id in org_dict:
            del org_dict[user_id]
            return True
        return False

    def owner_count(self, org_id: str) -> int:
        """Count active members with the owner role in an org."""
        return sum(
            1 for m in self.list_members(org_id)
            if m.role == Role.OWNER.value
        )

    # ------------------------------------------------------------------
    # Invitation management
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Invite rate limiting
    # ------------------------------------------------------------------

    _INVITE_RATE_LIMIT = 20          # max invites
    _INVITE_RATE_WINDOW_SECONDS = 86400  # per day (24 hours)

    def check_invite_rate_limit(self, org_id: str) -> bool:
        """Return True if the org is within the invite rate limit.

        Allows at most 20 invitations per org per 24-hour window.
        Returns False if the limit has been exceeded.
        """
        now = datetime.now(timezone.utc).timestamp()
        window_start = now - self._INVITE_RATE_WINDOW_SECONDS

        timestamps = self._invite_timestamps.get(org_id, [])
        # Prune old entries
        timestamps = [t for t in timestamps if t >= window_start]
        self._invite_timestamps[org_id] = timestamps

        return len(timestamps) < self._INVITE_RATE_LIMIT

    def record_invite_timestamp(self, org_id: str) -> None:
        """Record an invite creation timestamp for rate-limit tracking."""
        now = datetime.now(timezone.utc).timestamp()
        if org_id not in self._invite_timestamps:
            self._invite_timestamps[org_id] = []
        self._invite_timestamps[org_id].append(now)

    # ------------------------------------------------------------------
    # Invitation management
    # ------------------------------------------------------------------

    def create_invitation(
        self,
        org_id: str,
        invited_by: str,
        role: str,
        email: Optional[str] = None,
        expires_days: int = 7,
    ) -> Invitation:
        """Create a new invitation token.

        Args:
            org_id:       Organization to invite to.
            invited_by:   user_id of the sender.
            role:         Role to assign on acceptance.
            email:        Target email (None = shareable link, no restriction).
            expires_days: Expiry window in days (default 7).

        Returns:
            Newly created Invitation.
        """
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=expires_days)
        ).isoformat()

        invite = Invitation(
            org_id=org_id,
            email=email,
            role=role,
            invited_by=invited_by,
            expires_at=expires_at,
        )
        self._invitations[invite.token] = invite
        return invite

    def get_invitation(self, token: str) -> Optional[Invitation]:
        """Look up an invitation by token."""
        return self._invitations.get(token)

    def accept_invitation(
        self,
        token: str,
        user_id: str,
        email: str,
        display_name: str,
    ) -> TeamMember:
        """Accept an invitation and add the user as a member.

        Args:
            token:        Invitation token.
            user_id:      Accepting user's ID.
            email:        Accepting user's email.
            display_name: Accepting user's display name.

        Returns:
            The newly created TeamMember.

        Raises:
            InvitationError: If token is invalid, expired, or already accepted.
            InvitationError: If email doesn't match a targeted invite.
        """
        invite = self._invitations.get(token)
        if not invite:
            raise InvitationError("Invitation token not found or invalid.")

        if invite.accepted:
            raise InvitationError("This invitation has already been accepted.")

        if invite.is_expired:
            raise InvitationError("This invitation has expired.")

        # For email-targeted invites, verify the email matches
        if invite.email and invite.email.lower() != email.lower():
            raise InvitationError(
                f"This invitation was sent to {invite.email}, "
                f"not {email}."
            )

        # Check if user is already a member
        existing = self.get_member(invite.org_id, user_id)
        if existing and existing.is_active:
            raise InvitationError("You are already a member of this organization.")

        # Mark invitation as accepted
        invite.accepted = True
        invite.accepted_by = user_id
        invite.accepted_at = datetime.now(timezone.utc).isoformat()

        # Add member
        member = self.add_member(
            org_id=invite.org_id,
            user_id=user_id,
            email=email,
            display_name=display_name,
            role=invite.role,
            invited_by=invite.invited_by,
        )
        return member

    def list_invitations(
        self, org_id: str, include_accepted: bool = False
    ) -> List[Invitation]:
        """List invitations for an org."""
        result = [
            inv for inv in self._invitations.values()
            if inv.org_id == org_id
        ]
        if not include_accepted:
            result = [inv for inv in result if not inv.accepted]
        return result

    def clear(self) -> None:
        """Clear all data (for testing)."""
        self._members.clear()
        self._invitations.clear()
        self._invite_timestamps.clear()


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_team_store: Optional[TeamStore] = None
_audit_log: Optional[AuditLog] = None


def get_team_store() -> TeamStore:
    """Return the global TeamStore singleton."""
    global _team_store
    if _team_store is None:
        _team_store = TeamStore()
    return _team_store


def get_audit_log() -> AuditLog:
    """Return the global AuditLog singleton."""
    global _audit_log
    if _audit_log is None:
        _audit_log = AuditLog()
    return _audit_log


def reset_team_store() -> None:
    """Reset singletons (for testing isolation)."""
    global _team_store, _audit_log
    _team_store = TeamStore()
    _audit_log = AuditLog()
