"""AgentDefinition — typed base class for custom agent definitions."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


_VALID_MODELS = ("haiku", "sonnet", "opus", "inherit")


@dataclass
class AgentDefinition:
    """Typed definition for a custom agent.

    Fields
    ------
    name:
        Unique machine-readable identifier (e.g. "security-review").
    title:
        Human-readable display name.
    system_prompt:
        The system prompt that configures the agent's behaviour.
    model:
        One of "haiku" | "sonnet" | "opus" | "inherit".  Defaults to "sonnet".
    tools:
        List of tool names the agent is allowed to use.
    git_identity:
        Optional git user identity dict with keys "name" and "email".
    version:
        Semver string, e.g. "0.1.0".
    description:
        Short human-readable description of what the agent does.
    org_id:
        Organisation that owns this agent.  ``None`` means the agent is public.
    """

    name: str
    title: str
    system_prompt: str
    model: str = "sonnet"
    tools: list[str] = field(default_factory=list)
    git_identity: Optional[dict[str, str]] = None
    version: str = "0.1.0"
    description: str = ""
    org_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of validation error messages.

        An empty list means the definition is valid.
        """
        errors: list[str] = []

        if not self.name or not self.name.strip():
            errors.append("name is required and must not be empty")

        if not self.title or not self.title.strip():
            errors.append("title is required and must not be empty")

        if not self.system_prompt or not self.system_prompt.strip():
            errors.append("system_prompt is required and must not be empty")

        if self.model not in _VALID_MODELS:
            errors.append(
                f"model must be one of {_VALID_MODELS}, got {self.model!r}"
            )

        if not isinstance(self.tools, list):
            errors.append("tools must be a list of strings")
        elif any(not isinstance(t, str) for t in self.tools):
            errors.append("each tool in tools must be a string")

        if self.git_identity is not None:
            if not isinstance(self.git_identity, dict):
                errors.append("git_identity must be a dict")
            else:
                for key in ("name", "email"):
                    if key not in self.git_identity:
                        errors.append(f"git_identity is missing required key: {key!r}")

        return errors

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentDefinition":
        """Deserialise an :class:`AgentDefinition` from a plain dict.

        Unknown keys are silently ignored so that future versions of the
        schema remain backwards-compatible with older SDK versions.
        """
        known_fields = {
            "name", "title", "system_prompt", "model", "tools",
            "git_identity", "version", "description", "org_id",
        }
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def to_json(self) -> str:
        """Return a JSON string representation."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "AgentDefinition":
        """Deserialise from a JSON string."""
        return cls.from_dict(json.loads(json_str))
