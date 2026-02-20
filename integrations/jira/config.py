"""Jira integration configuration (AI-250).

Provides the :class:`JiraIntegrationConfig` dataclass and an in-memory
per-organisation config store.  No database is required; configs are
stored in a module-level dict that is cleared on server restart.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory config store: org_id → JiraIntegrationConfig
# ---------------------------------------------------------------------------
_configs: Dict[str, "JiraIntegrationConfig"] = {}


@dataclass
class JiraIntegrationConfig:
    """Configuration for one organisation's Jira integration.

    Attributes:
        org_id: Agent-Engineers organisation identifier.
        jira_base_url: Jira Cloud base URL, e.g.
            ``https://myorg.atlassian.net``.
        project_mappings: List of project-mapping dicts.  Each entry has
            ``jira_project`` (Jira project key) and ``ae_project``
            (Agent-Engineers project slug).
        field_mappings: Dict of custom Jira field names → AE field names,
            e.g. ``{"customfield_10016": "story_points"}``.
        enabled: Whether the integration is active.
        webhook_secret: Shared secret used to validate incoming Jira
            webhook signatures.
    """

    org_id: str
    jira_base_url: str = ""
    project_mappings: List[Dict[str, Any]] = field(default_factory=list)
    field_mappings: Dict[str, str] = field(default_factory=dict)
    enabled: bool = False
    webhook_secret: str = ""

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    @classmethod
    def load_from_dict(cls, data: Dict[str, Any]) -> "JiraIntegrationConfig":
        """Create a :class:`JiraIntegrationConfig` from a plain dict.

        Unknown keys are silently ignored, so this is safe for forward
        compatibility.

        Args:
            data: Config dict, typically deserialized from JSON.

        Returns:
            :class:`JiraIntegrationConfig` instance.

        Raises:
            ValueError: If ``org_id`` is missing or empty.
        """
        org_id: str = data.get("org_id", "")
        if not org_id:
            raise ValueError("JiraIntegrationConfig requires a non-empty 'org_id'")
        return cls(
            org_id=org_id,
            jira_base_url=data.get("jira_base_url", ""),
            project_mappings=data.get("project_mappings", []),
            field_mappings=data.get("field_mappings", {}),
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


def save_config(config: JiraIntegrationConfig) -> None:
    """Persist a config in the in-memory store.

    Args:
        config: :class:`JiraIntegrationConfig` instance to save.
    """
    _configs[config.org_id] = config
    logger.debug("Saved Jira config for org %s", config.org_id)


def load_config(org_id: str) -> Optional[JiraIntegrationConfig]:
    """Load a config from the in-memory store.

    Args:
        org_id: Organisation ID.

    Returns:
        :class:`JiraIntegrationConfig` or ``None`` if not found.
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


def list_configs() -> List[JiraIntegrationConfig]:
    """List all stored configs.

    Returns:
        List of :class:`JiraIntegrationConfig` instances.
    """
    return list(_configs.values())
