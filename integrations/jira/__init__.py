"""Jira integration package for Agent Dashboard (AI-250).

Provides bidirectional issue sync between Jira and Agent-Engineers,
enabling enterprise customers on Jira to use Agent-Engineers without
migrating to Linear.

Modules:
    client  - JiraClient for Atlassian REST API communication
    mapper  - JiraIssueMapper for field type/status/priority mapping
    sync    - JiraSyncEngine for bidirectional sync logic
    oauth   - JiraOAuthHandler for Atlassian OAuth 2.0 flow
    config  - JiraIntegrationConfig dataclass and storage
"""

from integrations.jira.client import JiraClient
from integrations.jira.mapper import JiraIssueMapper
from integrations.jira.sync import JiraSyncEngine
from integrations.jira.oauth import JiraOAuthHandler
from integrations.jira.config import JiraIntegrationConfig

__all__ = [
    "JiraClient",
    "JiraIssueMapper",
    "JiraSyncEngine",
    "JiraOAuthHandler",
    "JiraIntegrationConfig",
]
