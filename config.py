"""Centralized configuration management for Agent-Engineers.

All environment variables and configuration should be accessed through
this module rather than scattered os.environ calls.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pathlib import Path


class WindsurfMode(Enum):
    """Windsurf IDE integration mode."""
    DISABLED = "disabled"
    HEADLESS = "headless"
    INTERACTIVE = "interactive"


class LogLevel(Enum):
    """Application log levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class APIKeys:
    """API key configuration."""
    anthropic: Optional[str] = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    openai: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    gemini: Optional[str] = field(default_factory=lambda: os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    groq: Optional[str] = field(default_factory=lambda: os.getenv("GROQ_API_KEY"))
    linear: Optional[str] = field(default_factory=lambda: os.getenv("LINEAR_API_KEY"))
    github: Optional[str] = field(default_factory=lambda: os.getenv("GITHUB_TOKEN"))
    slack: Optional[str] = field(default_factory=lambda: os.getenv("SLACK_BOT_TOKEN"))
    arcade: Optional[str] = field(default_factory=lambda: os.getenv("ARCADE_API_KEY"))

    def validate(self) -> list[str]:
        """Return list of missing required API keys."""
        missing = []
        if not self.anthropic:
            missing.append("ANTHROPIC_API_KEY")
        return missing


@dataclass
class AgentConfig:
    """Centralized configuration for the Agent-Engineers system."""

    # Core settings
    windsurf_mode: WindsurfMode = field(
        default_factory=lambda: WindsurfMode(
            os.getenv("WINDSURF_MODE", "disabled")
        )
    )
    timeout: int = field(
        default_factory=lambda: int(os.getenv("AGENT_TIMEOUT", "300"))
    )
    log_level: LogLevel = field(
        default_factory=lambda: LogLevel(
            os.getenv("LOG_LEVEL", "info").lower()
        )
    )

    # API Keys
    api_keys: APIKeys = field(default_factory=APIKeys)

    # Paths
    prompts_dir: Path = field(
        default_factory=lambda: Path(os.getenv("PROMPTS_DIR", "prompts"))
    )
    screenshots_dir: Path = field(
        default_factory=lambda: Path(os.getenv("SCREENSHOTS_DIR", "screenshots"))
    )

    # GitHub integration
    github_repo: Optional[str] = field(
        default_factory=lambda: os.getenv("GITHUB_REPO")
    )

    # Linear integration
    linear_team_id: Optional[str] = field(
        default_factory=lambda: os.getenv("LINEAR_TEAM_ID")
    )

    # Dashboard settings
    dashboard_port: int = field(
        default_factory=lambda: int(os.getenv("DASHBOARD_PORT", "8080"))
    )
    websocket_port: int = field(
        default_factory=lambda: int(os.getenv("WEBSOCKET_PORT", "8765"))
    )

    # Daemon settings
    control_plane_port: int = field(
        default_factory=lambda: int(os.getenv("CONTROL_PLANE_PORT", "9100"))
    )
    max_workers: int = field(
        default_factory=lambda: int(os.getenv("MAX_WORKERS", "4"))
    )

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create config from environment variables."""
        return cls()

    def validate(self) -> list[str]:
        """Return list of validation errors."""
        errors = self.api_keys.validate()
        if self.timeout <= 0:
            errors.append("AGENT_TIMEOUT must be positive")
        if self.dashboard_port < 1024:
            errors.append("DASHBOARD_PORT must be >= 1024")
        return errors

    def is_valid(self) -> bool:
        """Check if config is valid."""
        return len(self.validate()) == 0


# Global config instance (lazy-loaded)
_config: Optional[AgentConfig] = None


def get_config() -> AgentConfig:
    """Get the global AgentConfig instance."""
    global _config
    if _config is None:
        _config = AgentConfig.from_env()
    return _config


def reset_config() -> None:
    """Reset the global config (useful for testing)."""
    global _config
    _config = None
