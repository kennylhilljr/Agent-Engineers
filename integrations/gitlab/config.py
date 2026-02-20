"""GitLab integration configuration (AI-251).

Provides the :class:`GitLabIntegrationConfig` dataclass and an in-memory
per-organisation config store.  No database is required; configs are
stored in a module-level dict that is cleared on server restart.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory config store: org_id → GitLabIntegrationConfig
# ---------------------------------------------------------------------------
_configs: Dict[str, "GitLabIntegrationConfig"] = {}


@dataclass
class GitLabIntegrationConfig:
    """Configuration for one organisation's GitLab integration.

    Attributes:
        org_id: Agent-Engineers organisation identifier.
        gitlab_base_url: GitLab instance base URL, e.g.
            ``https://gitlab.com`` or a self-hosted URL.
        auth_type: Authentication method — ``'oauth'`` or ``'pat'``
            (Personal Access Token).
        project_mappings: List of project-mapping dicts.  Each entry has
            ``gitlab_project_id`` (GitLab project ID) and ``ae_project``
            (Agent-Engineers project slug).
        pipeline_rules: Dict of CI/CD pipeline configuration rules, e.g.
            ``{"block_merge_on_failure": true, "required_stages": ["test"]}``.
        enabled: Whether the integration is active.
        webhook_secret: Shared secret sent in the ``X-Gitlab-Token`` header
            for webhook validation.
    """

    org_id: str
    gitlab_base_url: str = "https://gitlab.com"
    auth_type: str = "oauth"  # 'oauth' | 'pat'
    project_mappings: List[Dict[str, Any]] = field(default_factory=list)
    pipeline_rules: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = False
    webhook_secret: str = ""

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    @classmethod
    def load_from_dict(cls, data: Dict[str, Any]) -> "GitLabIntegrationConfig":
        """Create a :class:`GitLabIntegrationConfig` from a plain dict.

        Unknown keys are silently ignored for forward compatibility.

        Args:
            data: Config dict, typically deserialized from JSON.

        Returns:
            :class:`GitLabIntegrationConfig` instance.

        Raises:
            ValueError: If ``org_id`` is missing or empty.
        """
        org_id: str = data.get("org_id", "")
        if not org_id:
            raise ValueError(
                "GitLabIntegrationConfig requires a non-empty 'org_id'"
            )
        auth_type = data.get("auth_type", "oauth")
        if auth_type not in ("oauth", "pat"):
            raise ValueError(
                f"auth_type must be 'oauth' or 'pat', got {auth_type!r}"
            )
        return cls(
            org_id=org_id,
            gitlab_base_url=data.get("gitlab_base_url", "https://gitlab.com"),
            auth_type=auth_type,
            project_mappings=data.get("project_mappings", []),
            pipeline_rules=data.get("pipeline_rules", {}),
            enabled=bool(data.get("enabled", False)),
            webhook_secret=data.get("webhook_secret", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise this config to a plain dict.

        The ``webhook_secret`` is included in full (callers are responsible
        for omitting it from API responses where appropriate).

        Returns:
            Plain dict representation.
        """
        return asdict(self)


# ---------------------------------------------------------------------------
# Store helpers
# ---------------------------------------------------------------------------


def save_config(config: GitLabIntegrationConfig) -> None:
    """Persist a config in the in-memory store.

    Args:
        config: :class:`GitLabIntegrationConfig` instance to save.
    """
    _configs[config.org_id] = config
    logger.debug("Saved GitLab config for org %s", config.org_id)


def load_config(org_id: str) -> Optional[GitLabIntegrationConfig]:
    """Load a config from the in-memory store.

    Args:
        org_id: Organisation ID.

    Returns:
        :class:`GitLabIntegrationConfig` or ``None`` if not found.
    """
    return _configs.get(org_id)


def delete_config(org_id: str) -> bool:
    """Delete a config from the in-memory store.

    Args:
        org_id: Organisation ID.

    Returns:
        ``True`` if deleted, ``False`` if not found.
    """
    if org_id in _configs:
        del _configs[org_id]
        return True
    return False


def list_configs() -> List[GitLabIntegrationConfig]:
    """List all stored configs.

    Returns:
        List of :class:`GitLabIntegrationConfig` instances.
    """
    return list(_configs.values())
