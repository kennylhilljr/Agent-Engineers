"""Jira ↔ Agent-Engineers bidirectional sync engine (AI-250).

Handles:
- Converting inbound Jira webhook events into agent-compatible issue dicts
- Posting completion updates (PR URL, test summary) back to Jira
- Per-project field mapping configuration
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from integrations.jira.mapper import JiraIssueMapper

logger = logging.getLogger(__name__)


class JiraSyncEngine:
    """Bidirectional sync engine between Jira and Agent-Engineers.

    Args:
        jira_client: Optional :class:`~integrations.jira.client.JiraClient`
            instance.  When ``None`` the engine operates in read-only / test
            mode (outbound calls are skipped).
        mapper: Optional :class:`~integrations.jira.mapper.JiraIssueMapper`
            instance.  Defaults to a new instance.
    """

    def __init__(
        self,
        jira_client: Optional[Any] = None,
        mapper: Optional[JiraIssueMapper] = None,
    ) -> None:
        self.client = jira_client
        self.mapper = mapper or JiraIssueMapper()

    # ------------------------------------------------------------------
    # Inbound: Jira → Agent-Engineers
    # ------------------------------------------------------------------

    def sync_issue_to_linear(self, jira_issue: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a Jira issue dict to an Agent-Engineers (Linear-compatible) issue.

        Performs field type/status/priority mapping via
        :class:`~integrations.jira.mapper.JiraIssueMapper`.

        Args:
            jira_issue: Raw Jira issue dict (as returned by the REST API or a
                webhook payload).  Expected shape::

                    {
                        "key": "PROJ-123",
                        "fields": {
                            "summary": "...",
                            "description": "...",
                            "issuetype": {"name": "Story"},
                            "priority": {"name": "High"},
                            "status": {"name": "To Do"},
                            "assignee": {"displayName": "..."},
                            "customfield_10016": 5,   # story points
                            "sprint": {"name": "Sprint 3"},
                        }
                    }

        Returns:
            Agent-Engineers issue dict compatible with the Linear schema.
        """
        fields: Dict[str, Any] = jira_issue.get("fields", {})
        key: str = jira_issue.get("key", "")

        issue_type_raw = (fields.get("issuetype") or {}).get("name", "Task")
        priority_raw = (fields.get("priority") or {}).get("name", "Medium")
        status_raw = (fields.get("status") or {}).get("name", "To Do")
        description: str = fields.get("description") or ""
        summary: str = fields.get("summary") or ""
        assignee_name: str = (fields.get("assignee") or {}).get("displayName", "")
        story_points = fields.get("customfield_10016") or fields.get("story_points")
        sprint_name: str = (fields.get("sprint") or {}).get("name", "")

        mapped_type = self.mapper.map_issue_type(issue_type_raw)
        mapped_priority = self.mapper.map_priority(priority_raw)
        mapped_status = self.mapper.map_status(status_raw)
        acceptance_criteria = self.mapper.extract_acceptance_criteria(description)

        linear_issue: Dict[str, Any] = {
            "id": key,
            "identifier": key,
            "title": summary,
            "description": description,
            "type": mapped_type,
            "priority": mapped_priority,
            "status": mapped_status,
            "assignee": assignee_name,
            "estimate": story_points,
            "sprint": sprint_name,
            "acceptance_criteria": acceptance_criteria,
            "source": "jira",
            "jira_key": key,
        }
        logger.info("Synced Jira issue %s → linear-compatible issue", key)
        return linear_issue

    # ------------------------------------------------------------------
    # Outbound: Agent-Engineers → Jira
    # ------------------------------------------------------------------

    def sync_completion_to_jira(
        self,
        jira_key: str,
        pr_url: str,
        test_summary: str,
        done_transition_id: str = "31",
    ) -> None:
        """Post a completion update back to Jira.

        Posts a comment containing the PR URL and test summary, then
        transitions the issue to "Done".

        Args:
            jira_key: Jira issue key, e.g. ``PROJ-123``.
            pr_url: URL of the merged / open pull request.
            test_summary: Human-readable test result summary.
            done_transition_id: Jira transition ID for "Done" (default: ``"31"``).

        Note:
            If ``self.client`` is ``None`` the call is logged but no API
            requests are made (safe test mode).
        """
        comment = (
            f"Agent-Engineers completed this issue.\n\n"
            f"**PR:** {pr_url}\n\n"
            f"**Tests:** {test_summary}"
        )

        if self.client is None:
            logger.warning(
                "JiraSyncEngine.sync_completion_to_jira called without a Jira client; "
                "skipping outbound API calls for issue %s",
                jira_key,
            )
            return

        try:
            self.client.add_comment(jira_key, comment)
            logger.info("Posted completion comment on Jira issue %s", jira_key)
        except Exception as exc:
            logger.error("Failed to add comment to %s: %s", jira_key, exc)
            raise

        try:
            self.client.transition_issue(jira_key, done_transition_id)
            logger.info("Transitioned Jira issue %s → Done", jira_key)
        except Exception as exc:
            logger.error("Failed to transition %s: %s", jira_key, exc)
            raise

    # ------------------------------------------------------------------
    # Webhook event handling
    # ------------------------------------------------------------------

    def handle_webhook_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming Jira webhook event.

        Supported event types:
            - ``jira:issue_created``  → sync new issue
            - ``jira:issue_updated``  → re-sync updated issue
            - ``jira:issue_deleted``  → return cancellation marker
            - ``comment_created``     → pass through comment data

        Args:
            event: Parsed Jira webhook payload dict.  Expected fields:
                ``webhookEvent``, ``issue`` (for issue events).

        Returns:
            Result dict with ``action``, ``issue`` (if applicable), and
            ``event_type`` fields.
        """
        webhook_event: str = event.get("webhookEvent", "")
        result: Dict[str, Any] = {"event_type": webhook_event}

        if webhook_event in ("jira:issue_created", "jira:issue_updated"):
            raw_issue = event.get("issue", {})
            if raw_issue:
                synced = self.sync_issue_to_linear(raw_issue)
                result["action"] = (
                    "created" if "created" in webhook_event else "updated"
                )
                result["issue"] = synced
                logger.info(
                    "Handled %s for issue %s",
                    webhook_event,
                    raw_issue.get("key", "?"),
                )
            else:
                result["action"] = "skipped"
                result["reason"] = "no issue in payload"

        elif webhook_event == "jira:issue_deleted":
            raw_issue = event.get("issue", {})
            result["action"] = "deleted"
            result["issue_key"] = raw_issue.get("key", "")
            logger.info("Handled issue_deleted for %s", result["issue_key"])

        elif webhook_event == "comment_created":
            result["action"] = "comment"
            result["comment"] = event.get("comment", {})

        else:
            result["action"] = "ignored"
            logger.debug("Ignored unknown webhook event: %s", webhook_event)

        return result

    # ------------------------------------------------------------------
    # Field mapping
    # ------------------------------------------------------------------

    def map_field_config(self, project_mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Apply per-project field mapping configuration.

        Transforms a project-specific mapping config into a normalized
        field-mapping dict that the sync engine uses when converting issues.

        Args:
            project_mapping: Dict describing field overrides for a project::

                {
                    "jira_project": "PROJ",
                    "ae_project": "my-project",
                    "field_overrides": {
                        "story_points_field": "customfield_10028",
                        "sprint_field": "customfield_10020",
                    }
                }

        Returns:
            Normalized field-mapping dict.
        """
        jira_project = project_mapping.get("jira_project", "")
        ae_project = project_mapping.get("ae_project", "")
        overrides: Dict[str, Any] = project_mapping.get("field_overrides", {})

        config: Dict[str, Any] = {
            "jira_project": jira_project,
            "ae_project": ae_project,
            "story_points_field": overrides.get("story_points_field", "customfield_10016"),
            "sprint_field": overrides.get("sprint_field", "customfield_10020"),
            "acceptance_criteria_field": overrides.get(
                "acceptance_criteria_field", "description"
            ),
        }
        # Merge any remaining overrides
        for key, value in overrides.items():
            if key not in config:
                config[key] = value

        return config
