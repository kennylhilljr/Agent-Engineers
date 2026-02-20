"""Projects package — multi-project support for Agent-Engineers dashboard.

Provides the ProjectManager and Project dataclass for managing multiple
Agent-Engineers projects from a single dashboard instance (AI-225).
"""

from projects.project_manager import Project, ProjectManager, TierLimitError

__all__ = ["Project", "ProjectManager", "TierLimitError"]
