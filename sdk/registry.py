"""AgentRegistry — in-memory versioned registry with org-scoped lookup."""
from __future__ import annotations

import json
import os
from typing import Any, Optional

from sdk.agent_definition import AgentDefinition


class AgentRegistry:
    """Discover and manage custom :class:`AgentDefinition` instances at runtime.

    Agents can be either *public* (``org_id=None``) or *private* (scoped to a
    specific organisation).  Private agents are only visible within their own
    organisation; public agents are visible to all organisations.

    The registry is fully in-memory and process-local — suitable for unit tests
    and local development.  A future version will persist to a database.
    """

    def __init__(self) -> None:
        # Internal store: { (name, org_id) -> AgentDefinition }
        # org_id is None for public agents.
        self._store: dict[tuple[str, Optional[str]], AgentDefinition] = {}

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def register(
        self, agent: AgentDefinition, org_id: Optional[str] = None
    ) -> None:
        """Add *agent* to the registry.

        If *org_id* is provided it overrides ``agent.org_id``.  Pass
        ``org_id=None`` to register a public agent.
        """
        effective_org = org_id if org_id is not None else agent.org_id
        # Make a copy with the resolved org_id so the stored object is
        # self-consistent.
        from dataclasses import replace as dc_replace
        stored = dc_replace(agent, org_id=effective_org)
        self._store[(agent.name, effective_org)] = stored

    def unregister(self, name: str, org_id: Optional[str] = None) -> None:
        """Remove the agent identified by *name* and *org_id* from the registry.

        Silently does nothing if the agent is not found.
        """
        self._store.pop((name, org_id), None)

    def clear(self, org_id: Optional[str] = None) -> None:
        """Remove agents from the registry.

        If *org_id* is ``None`` all agents (public and private) are removed.
        Otherwise only agents belonging to *org_id* are removed.
        """
        if org_id is None:
            self._store.clear()
        else:
            keys_to_remove = [k for k in self._store if k[1] == org_id]
            for k in keys_to_remove:
                del self._store[k]

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get(self, name: str, org_id: Optional[str] = None) -> AgentDefinition:
        """Return the agent matching *name* and *org_id*.

        Lookup order: private (org-scoped) first, then public.

        Raises ``KeyError`` if no matching agent is found.
        """
        # Try private first
        if org_id is not None:
            private = self._store.get((name, org_id))
            if private is not None:
                return private

        # Fall back to public
        public = self._store.get((name, None))
        if public is not None:
            return public

        raise KeyError(
            f"Agent {name!r} not found"
            + (f" for org {org_id!r}" if org_id else " (public)")
        )

    def list_agents(self, org_id: Optional[str] = None) -> list[AgentDefinition]:
        """Return all agents visible to *org_id*.

        Includes public agents (``org_id=None``) plus, if *org_id* is given,
        agents private to that organisation.
        """
        result: list[AgentDefinition] = []
        for (_, stored_org), agent in self._store.items():
            if stored_org is None or stored_org == org_id:
                result.append(agent)
        return result

    # ------------------------------------------------------------------
    # Loader helpers
    # ------------------------------------------------------------------

    def load_from_dict(
        self, data: dict[str, Any], org_id: Optional[str] = None
    ) -> AgentDefinition:
        """Deserialise *data* into an :class:`AgentDefinition` and register it.

        Returns the registered agent.
        """
        agent = AgentDefinition.from_dict(data)
        self.register(agent, org_id=org_id)
        return agent

    def load_from_file(
        self, path: str, org_id: Optional[str] = None
    ) -> AgentDefinition:
        """Load an agent definition from a YAML or JSON file and register it.

        Supports ``.yaml`` / ``.yml`` (requires PyYAML) and ``.json``.

        Returns the registered agent.
        """
        _, ext = os.path.splitext(path)
        ext = ext.lower()

        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()

        if ext in (".yaml", ".yml"):
            try:
                import yaml  # type: ignore[import]
                data = yaml.safe_load(content)
            except ImportError as exc:
                raise ImportError(
                    "PyYAML is required to load YAML files: "
                    "pip install pyyaml"
                ) from exc
        elif ext == ".json":
            data = json.loads(content)
        else:
            raise ValueError(
                f"Unsupported file extension {ext!r}. Expected .yaml, .yml, or .json"
            )

        return self.load_from_dict(data, org_id=org_id)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_registry(self, org_id: Optional[str] = None) -> dict[str, Any]:
        """Return a JSON-serialisable dump of the registry.

        If *org_id* is given only agents visible to that organisation are
        included (private + public).  Pass ``None`` to export everything.
        """
        agents = self.list_agents(org_id=org_id)
        return {
            "agents": [a.to_dict() for a in agents],
            "count": len(agents),
        }
