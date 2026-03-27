"""Multi-tenant data models.

Defines the core data structures for tenant configuration, resource allocation,
and request-scoped tenant context used throughout the platform.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Tenant status constants
# ---------------------------------------------------------------------------

TENANT_STATUS_ACTIVE = "active"
TENANT_STATUS_SUSPENDED = "suspended"
TENANT_STATUS_DEPROVISIONING = "deprovisioning"

VALID_STATUSES = {TENANT_STATUS_ACTIVE, TENANT_STATUS_SUSPENDED, TENANT_STATUS_DEPROVISIONING}

# Default model allowlist
DEFAULT_ALLOWED_MODELS = ["haiku", "sonnet", "opus"]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TenantError(Exception):
    """Base exception for tenant operations."""


class TenantNotFoundError(TenantError):
    """Raised when a tenant ID does not match any known tenant."""


class TenantSuspendedError(TenantError):
    """Raised when an operation is attempted on a suspended tenant."""


class TenantLimitError(TenantError):
    """Raised when a tenant exceeds a configured resource limit."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class PoolAllocation:
    """Per-tenant agent pool allocation within the global pool.

    Attributes:
        pool_type: Worker pool type (coding, review, linear).
        min_reserved: Guaranteed minimum workers for this tenant.
        max_burst: Maximum workers including burst capacity.
        default_model: Default Claude model for this pool.
    """

    pool_type: str  # coding | review | linear
    min_reserved: int = 0
    max_burst: int = 3
    default_model: str = "sonnet"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pool_type": self.pool_type,
            "min_reserved": self.min_reserved,
            "max_burst": self.max_burst,
            "default_model": self.default_model,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PoolAllocation":
        return cls(
            pool_type=data.get("pool_type", "coding"),
            min_reserved=data.get("min_reserved", 0),
            max_burst=data.get("max_burst", 3),
            default_model=data.get("default_model", "sonnet"),
        )


@dataclass
class TenantConfig:
    """Per-tenant resource and feature configuration.

    Each tenant (enterprise customer) gets an isolated configuration that
    controls resource limits, feature flags, and agent pool allocation.

    Attributes:
        tenant_id: Unique tenant identifier.
        name: Human-readable tenant name.
        slug: URL-safe identifier for routing.
        max_projects: Maximum concurrent projects.
        max_concurrent_agents: Maximum simultaneously active agents.
        max_agent_hours_monthly: Monthly agent-hour budget (0 = unlimited).
        allowed_models: List of permitted Claude model tiers.
        sso_enabled: Whether SSO authentication is enabled.
        scim_enabled: Whether SCIM provisioning is enabled.
        analytics_enabled: Whether advanced analytics are available.
        audit_log_enabled: Whether audit logging is active.
        custom_integrations_enabled: Whether custom integrations are permitted.
        shared_memory_read: Whether this tenant benefits from shared memory.
        pool_config: Per-pool-type resource allocation.
        data_dir: Tenant-specific data directory path.
        worktree_base: Tenant-specific worktree root path.
        owner_user_id: User ID of the tenant owner.
        status: Tenant lifecycle status (active, suspended, deprovisioning).
    """

    tenant_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    slug: str = ""

    # Resource limits
    max_projects: int = 10
    max_concurrent_agents: int = 5
    max_agent_hours_monthly: float = 0  # 0 = unlimited
    allowed_models: List[str] = field(default_factory=lambda: list(DEFAULT_ALLOWED_MODELS))

    # Feature flags
    sso_enabled: bool = True
    scim_enabled: bool = False
    analytics_enabled: bool = True
    audit_log_enabled: bool = True
    custom_integrations_enabled: bool = True
    shared_memory_read: bool = True

    # Agent pool allocation
    pool_config: Dict[str, PoolAllocation] = field(default_factory=dict)

    # Isolation paths (set by TenantIsolationManager on provisioning)
    data_dir: str = ""
    worktree_base: str = ""

    # Metadata
    owner_user_id: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = TENANT_STATUS_ACTIVE

    def is_active(self) -> bool:
        """Return True if tenant is in active status."""
        return self.status == TENANT_STATUS_ACTIVE

    def is_model_allowed(self, model: str) -> bool:
        """Check if a model tier is permitted for this tenant."""
        return model in self.allowed_models

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON persistence."""
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "slug": self.slug,
            "max_projects": self.max_projects,
            "max_concurrent_agents": self.max_concurrent_agents,
            "max_agent_hours_monthly": self.max_agent_hours_monthly,
            "allowed_models": self.allowed_models,
            "sso_enabled": self.sso_enabled,
            "scim_enabled": self.scim_enabled,
            "analytics_enabled": self.analytics_enabled,
            "audit_log_enabled": self.audit_log_enabled,
            "custom_integrations_enabled": self.custom_integrations_enabled,
            "shared_memory_read": self.shared_memory_read,
            "pool_config": {k: v.to_dict() for k, v in self.pool_config.items()},
            "data_dir": self.data_dir,
            "worktree_base": self.worktree_base,
            "owner_user_id": self.owner_user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TenantConfig":
        """Deserialize from dictionary."""
        pool_raw = data.get("pool_config", {})
        pool_config = {k: PoolAllocation.from_dict(v) for k, v in pool_raw.items()}
        return cls(
            tenant_id=data.get("tenant_id", str(uuid.uuid4())),
            name=data.get("name", ""),
            slug=data.get("slug", ""),
            max_projects=data.get("max_projects", 10),
            max_concurrent_agents=data.get("max_concurrent_agents", 5),
            max_agent_hours_monthly=data.get("max_agent_hours_monthly", 0),
            allowed_models=data.get("allowed_models", list(DEFAULT_ALLOWED_MODELS)),
            sso_enabled=data.get("sso_enabled", True),
            scim_enabled=data.get("scim_enabled", False),
            analytics_enabled=data.get("analytics_enabled", True),
            audit_log_enabled=data.get("audit_log_enabled", True),
            custom_integrations_enabled=data.get("custom_integrations_enabled", True),
            shared_memory_read=data.get("shared_memory_read", True),
            pool_config=pool_config,
            data_dir=data.get("data_dir", ""),
            worktree_base=data.get("worktree_base", ""),
            owner_user_id=data.get("owner_user_id", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            status=data.get("status", TENANT_STATUS_ACTIVE),
        )

    def public_dict(self) -> Dict[str, Any]:
        """Return a tenant-safe view (excludes internal paths)."""
        d = self.to_dict()
        d.pop("data_dir", None)
        d.pop("worktree_base", None)
        return d


@dataclass
class TenantContext:
    """Runtime context injected into each request by tenant middleware.

    Attributes:
        tenant_id: Active tenant identifier.
        tenant_config: Full tenant configuration.
        user_id: Authenticated user making the request.
        org_id: Organization ID (1:1 with tenant).
        role: User's role within the tenant organization.
        is_platform_admin: Whether the user has platform-level admin access.
    """

    tenant_id: str
    tenant_config: TenantConfig
    user_id: str = ""
    org_id: str = ""
    role: str = ""
    is_platform_admin: bool = False
