"""GitLab integration package for Agent Dashboard (AI-251).

Provides branch creation, commit/push, Merge Request management, and
CI/CD pipeline status gating via the GitLab REST API v4. Enables
enterprise customers on GitLab to use Agent-Engineers without migrating
to GitHub.

Modules:
    client      - GitLabClient for REST API communication
    mr_manager  - GitLabMRManager for branch/MR/pipeline workflows
    ci_pipeline - GitLabCIPipeline for pipeline status detection
    oauth       - GitLabOAuthHandler for OAuth 2.0 / PAT authentication
    config      - GitLabIntegrationConfig dataclass and storage
"""

from integrations.gitlab.client import GitLabClient
from integrations.gitlab.mr_manager import GitLabMRManager
from integrations.gitlab.ci_pipeline import GitLabCIPipeline
from integrations.gitlab.oauth import GitLabOAuthHandler
from integrations.gitlab.config import GitLabIntegrationConfig

__all__ = [
    "GitLabClient",
    "GitLabMRManager",
    "GitLabCIPipeline",
    "GitLabOAuthHandler",
    "GitLabIntegrationConfig",
]
