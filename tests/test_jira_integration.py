"""Comprehensive tests for Jira integration (AI-250).

Tests cover:
- JiraClient: all public methods with mocked HTTP calls
- JiraIssueMapper: all mapping and extraction methods
- JiraSyncEngine: webhook event handling, issue sync, completion sync
- JiraOAuthHandler: URL generation, code exchange, token refresh, state validation
- JiraIntegrationConfig: serialisation, persistence helpers
- REST API endpoints: jira_webhook, jira_get_status, jira_connect,
  jira_callback, jira_save_config (signature validation included)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_jira_issue(
    key: str = "PROJ-1",
    summary: str = "Test issue",
    issue_type: str = "Story",
    priority: str = "High",
    status: str = "To Do",
    description: str = "",
    story_points: int | None = None,
    sprint_name: str = "",
    assignee: str = "Alice",
) -> Dict[str, Any]:
    """Build a minimal Jira issue dict."""
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
            "status": {"name": status},
            "assignee": {"displayName": assignee},
            "customfield_10016": story_points,
            "sprint": {"name": sprint_name} if sprint_name else None,
        },
    }


# ===========================================================================
# JiraClient tests
# ===========================================================================


class TestJiraClient(unittest.TestCase):
    """Tests for integrations.jira.client.JiraClient."""

    def _make_client(self, get_response=None, post_response=None, put_response=None):
        from integrations.jira.client import JiraClient

        def _get(url, headers):
            return get_response or {}

        def _post(url, headers, body):
            return post_response or {}

        def _put(url, headers, body):
            return put_response or {}

        return JiraClient(
            base_url="https://test.atlassian.net",
            auth_token="mock-token",
            _http_get=_get,
            _http_post=_post,
            _http_put=_put,
        )

    def test_get_issue_returns_dict(self):
        issue = {"key": "PROJ-1", "fields": {"summary": "Hello"}}
        client = self._make_client(get_response=issue)
        result = client.get_issue("PROJ-1")
        self.assertEqual(result["key"], "PROJ-1")

    def test_get_issue_calls_correct_path(self):
        called = []

        def _get(url, headers):
            called.append(url)
            return {}

        from integrations.jira.client import JiraClient

        c = JiraClient("https://my.atlassian.net", "tok", _http_get=_get)
        c.get_issue("ABC-42")
        self.assertIn("ABC-42", called[0])

    def test_transition_issue_posts_to_transitions_endpoint(self):
        called = []

        def _post(url, headers, body):
            called.append((url, body))
            return {}

        from integrations.jira.client import JiraClient

        c = JiraClient("https://my.atlassian.net", "tok", _http_post=_post)
        c.transition_issue("PROJ-5", "31")
        self.assertTrue(any("transitions" in u for u, _ in called))
        body = called[0][1]
        self.assertEqual(body["transition"]["id"], "31")

    def test_add_comment_posts_to_comment_endpoint(self):
        called = []

        def _post(url, headers, body):
            called.append((url, body))
            return {"id": "comment-1"}

        from integrations.jira.client import JiraClient

        c = JiraClient("https://my.atlassian.net", "tok", _http_post=_post)
        result = c.add_comment("PROJ-6", "Great work!")
        self.assertIn("comment", called[0][0])
        # Check ADF format
        content = called[0][1]["body"]["content"][0]["content"][0]["text"]
        self.assertEqual(content, "Great work!")

    def test_update_story_points_puts_to_issue_endpoint(self):
        called = []

        def _put(url, headers, body):
            called.append((url, body))
            return {}

        from integrations.jira.client import JiraClient

        c = JiraClient("https://my.atlassian.net", "tok", _http_put=_put)
        c.update_story_points("PROJ-7", 5)
        self.assertTrue(any("PROJ-7" in u for u, _ in called))
        body = called[0][1]
        self.assertEqual(body["fields"]["customfield_10016"], 5)

    def test_get_sprint_issues_returns_issues_list(self):
        issues_data = {"issues": [{"key": "PROJ-1"}, {"key": "PROJ-2"}]}
        client = self._make_client(get_response=issues_data)
        result = client.get_sprint_issues("PROJ")
        self.assertEqual(len(result), 2)

    def test_get_sprint_issues_with_sprint_name(self):
        called = []

        def _get(url, headers):
            called.append(url)
            return {"issues": []}

        from integrations.jira.client import JiraClient

        c = JiraClient("https://my.atlassian.net", "tok", _http_get=_get)
        c.get_sprint_issues("PROJ", sprint_name="Sprint 1")
        self.assertIn("Sprint", called[0])

    def test_get_sprint_issues_empty_response(self):
        client = self._make_client(get_response={})
        result = client.get_sprint_issues("PROJ")
        self.assertEqual(result, [])

    def test_get_transitions_returns_list(self):
        transitions_data = {
            "transitions": [
                {"id": "11", "name": "To Do"},
                {"id": "21", "name": "In Progress"},
                {"id": "31", "name": "Done"},
            ]
        }
        client = self._make_client(get_response=transitions_data)
        result = client.get_transitions("PROJ-1")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["name"], "To Do")

    def test_get_transitions_empty(self):
        client = self._make_client(get_response={})
        result = client.get_transitions("PROJ-1")
        self.assertEqual(result, [])

    def test_headers_include_bearer_token(self):
        from integrations.jira.client import JiraClient

        c = JiraClient("https://x.atlassian.net", "my-secret-token")
        headers = c._headers()
        self.assertEqual(headers["Authorization"], "Bearer my-secret-token")

    def test_base_url_trailing_slash_stripped(self):
        from integrations.jira.client import JiraClient

        c = JiraClient("https://x.atlassian.net/", "tok")
        self.assertFalse(c.base_url.endswith("/"))

    def test_jira_client_error_raised_on_http_error(self):
        from integrations.jira.client import JiraClient, JiraClientError

        def _get(url, headers):
            raise JiraClientError("HTTP 404 GET /rest/api/3/issue/PROJ-99")

        c = JiraClient("https://x.atlassian.net", "tok", _http_get=_get)
        with self.assertRaises(JiraClientError):
            c.get_issue("PROJ-99")


# ===========================================================================
# JiraIssueMapper tests
# ===========================================================================


class TestJiraIssueMapper(unittest.TestCase):
    """Tests for integrations.jira.mapper.JiraIssueMapper."""

    def setUp(self):
        from integrations.jira.mapper import JiraIssueMapper
        self.mapper = JiraIssueMapper()

    # map_issue_type
    def test_story_maps_to_feature(self):
        self.assertEqual(self.mapper.map_issue_type("Story"), "feature")

    def test_bug_maps_to_bug_fix(self):
        self.assertEqual(self.mapper.map_issue_type("Bug"), "bug fix")

    def test_task_maps_to_task(self):
        self.assertEqual(self.mapper.map_issue_type("Task"), "task")

    def test_epic_maps_to_epic(self):
        self.assertEqual(self.mapper.map_issue_type("Epic"), "epic")

    def test_sub_task_maps_to_task(self):
        self.assertEqual(self.mapper.map_issue_type("Sub-task"), "task")

    def test_unknown_type_defaults_to_task(self):
        self.assertEqual(self.mapper.map_issue_type("Weird Type"), "task")

    def test_case_insensitive_mapping(self):
        self.assertEqual(self.mapper.map_issue_type("STORY"), "feature")
        self.assertEqual(self.mapper.map_issue_type("bug"), "bug fix")

    def test_improvement_maps_to_feature(self):
        self.assertEqual(self.mapper.map_issue_type("Improvement"), "feature")

    # map_priority
    def test_highest_maps_to_1(self):
        self.assertEqual(self.mapper.map_priority("Highest"), 1)

    def test_high_maps_to_2(self):
        self.assertEqual(self.mapper.map_priority("High"), 2)

    def test_medium_maps_to_3(self):
        self.assertEqual(self.mapper.map_priority("Medium"), 3)

    def test_low_maps_to_4(self):
        self.assertEqual(self.mapper.map_priority("Low"), 4)

    def test_critical_maps_to_1(self):
        self.assertEqual(self.mapper.map_priority("Critical"), 1)

    def test_blocker_maps_to_1(self):
        self.assertEqual(self.mapper.map_priority("Blocker"), 1)

    def test_major_maps_to_2(self):
        self.assertEqual(self.mapper.map_priority("Major"), 2)

    def test_minor_maps_to_4(self):
        self.assertEqual(self.mapper.map_priority("Minor"), 4)

    def test_trivial_maps_to_4(self):
        self.assertEqual(self.mapper.map_priority("Trivial"), 4)

    def test_unknown_priority_defaults_to_3(self):
        self.assertEqual(self.mapper.map_priority("Alien Priority"), 3)

    def test_priority_case_insensitive(self):
        self.assertEqual(self.mapper.map_priority("HIGH"), 2)

    # extract_acceptance_criteria
    def test_extract_ac_markdown_header(self):
        desc = (
            "## Acceptance Criteria\n"
            "- User can log in\n"
            "- Session is persistent\n"
        )
        criteria = self.mapper.extract_acceptance_criteria(desc)
        self.assertIn("User can log in", criteria)
        self.assertIn("Session is persistent", criteria)

    def test_extract_ac_no_section_returns_empty(self):
        criteria = self.mapper.extract_acceptance_criteria("Just a plain description.")
        self.assertEqual(criteria, [])

    def test_extract_ac_empty_description(self):
        criteria = self.mapper.extract_acceptance_criteria("")
        self.assertEqual(criteria, [])

    def test_extract_ac_numbered_list(self):
        desc = "## Acceptance Criteria\n1. First item\n2. Second item\n"
        criteria = self.mapper.extract_acceptance_criteria(desc)
        self.assertIn("First item", criteria)
        self.assertIn("Second item", criteria)

    def test_extract_ac_checkbox_style(self):
        desc = "## Acceptance Criteria\n- [ ] Unchecked item\n- [x] Checked item\n"
        criteria = self.mapper.extract_acceptance_criteria(desc)
        self.assertIn("Unchecked item", criteria)
        self.assertIn("Checked item", criteria)

    def test_extract_ac_stops_at_next_header(self):
        desc = (
            "## Acceptance Criteria\n"
            "- Item A\n"
            "## Technical Notes\n"
            "- Not a criterion\n"
        )
        criteria = self.mapper.extract_acceptance_criteria(desc)
        self.assertIn("Item A", criteria)
        self.assertNotIn("Not a criterion", criteria)

    def test_extract_ac_plain_header_fallback(self):
        desc = "Acceptance Criteria:\n- Do the thing\n- Check it twice\n"
        criteria = self.mapper.extract_acceptance_criteria(desc)
        self.assertIn("Do the thing", criteria)

    # map_status
    def test_to_do_maps_to_backlog(self):
        self.assertEqual(self.mapper.map_status("To Do"), "backlog")

    def test_in_progress_maps_to_in_progress(self):
        self.assertEqual(self.mapper.map_status("In Progress"), "in_progress")

    def test_done_maps_to_done(self):
        self.assertEqual(self.mapper.map_status("Done"), "done")

    def test_closed_maps_to_done(self):
        self.assertEqual(self.mapper.map_status("Closed"), "done")

    def test_in_review_maps_to_in_review(self):
        self.assertEqual(self.mapper.map_status("In Review"), "in_review")

    def test_wont_do_maps_to_cancelled(self):
        self.assertEqual(self.mapper.map_status("Won't Do"), "cancelled")

    def test_unknown_status_defaults_to_backlog(self):
        self.assertEqual(self.mapper.map_status("Mystery Status"), "backlog")

    def test_open_maps_to_backlog(self):
        self.assertEqual(self.mapper.map_status("Open"), "backlog")

    def test_resolved_maps_to_done(self):
        self.assertEqual(self.mapper.map_status("Resolved"), "done")

    def test_code_review_maps_to_in_review(self):
        self.assertEqual(self.mapper.map_status("Code Review"), "in_review")

    # format_smart_commit
    def test_smart_commit_format(self):
        result = self.mapper.format_smart_commit("PROJ-123", "Fix the bug")
        self.assertEqual(result, "PROJ-123: Fix the bug")

    def test_smart_commit_preserves_key(self):
        result = self.mapper.format_smart_commit("AI-250", "Add Jira integration")
        self.assertTrue(result.startswith("AI-250:"))

    def test_smart_commit_message_included(self):
        msg = "Implement bidirectional sync"
        result = self.mapper.format_smart_commit("PROJ-1", msg)
        self.assertIn(msg, result)


# ===========================================================================
# JiraSyncEngine tests
# ===========================================================================


class TestJiraSyncEngine(unittest.TestCase):
    """Tests for integrations.jira.sync.JiraSyncEngine."""

    def setUp(self):
        from integrations.jira.sync import JiraSyncEngine
        self.engine = JiraSyncEngine()

    # sync_issue_to_linear
    def test_sync_issue_maps_basic_fields(self):
        issue = _make_jira_issue(
            key="PROJ-10",
            summary="Login feature",
            issue_type="Story",
            priority="High",
            status="To Do",
        )
        result = self.engine.sync_issue_to_linear(issue)
        self.assertEqual(result["id"], "PROJ-10")
        self.assertEqual(result["title"], "Login feature")
        self.assertEqual(result["type"], "feature")
        self.assertEqual(result["priority"], 2)
        self.assertEqual(result["status"], "backlog")
        self.assertEqual(result["source"], "jira")
        self.assertEqual(result["jira_key"], "PROJ-10")

    def test_sync_issue_maps_bug_type(self):
        issue = _make_jira_issue(issue_type="Bug")
        result = self.engine.sync_issue_to_linear(issue)
        self.assertEqual(result["type"], "bug fix")

    def test_sync_issue_maps_task_type(self):
        issue = _make_jira_issue(issue_type="Task")
        result = self.engine.sync_issue_to_linear(issue)
        self.assertEqual(result["type"], "task")

    def test_sync_issue_extracts_story_points(self):
        issue = _make_jira_issue(story_points=8)
        result = self.engine.sync_issue_to_linear(issue)
        self.assertEqual(result["estimate"], 8)

    def test_sync_issue_extracts_sprint(self):
        issue = _make_jira_issue(sprint_name="Sprint 3")
        result = self.engine.sync_issue_to_linear(issue)
        self.assertEqual(result["sprint"], "Sprint 3")

    def test_sync_issue_extracts_acceptance_criteria(self):
        desc = "## Acceptance Criteria\n- Must work\n- Must be fast\n"
        issue = _make_jira_issue(description=desc)
        result = self.engine.sync_issue_to_linear(issue)
        self.assertIn("Must work", result["acceptance_criteria"])
        self.assertIn("Must be fast", result["acceptance_criteria"])

    def test_sync_issue_missing_fields_use_defaults(self):
        issue = {"key": "PROJ-99", "fields": {}}
        result = self.engine.sync_issue_to_linear(issue)
        self.assertEqual(result["id"], "PROJ-99")
        self.assertEqual(result["type"], "task")  # default
        self.assertEqual(result["priority"], 3)   # medium default

    # handle_webhook_event
    def test_handle_issue_created_event(self):
        event = {
            "webhookEvent": "jira:issue_created",
            "issue": _make_jira_issue(key="PROJ-20"),
        }
        result = self.engine.handle_webhook_event(event)
        self.assertEqual(result["action"], "created")
        self.assertEqual(result["event_type"], "jira:issue_created")
        self.assertIn("issue", result)
        self.assertEqual(result["issue"]["id"], "PROJ-20")

    def test_handle_issue_updated_event(self):
        event = {
            "webhookEvent": "jira:issue_updated",
            "issue": _make_jira_issue(key="PROJ-21"),
        }
        result = self.engine.handle_webhook_event(event)
        self.assertEqual(result["action"], "updated")
        self.assertIn("issue", result)

    def test_handle_issue_deleted_event(self):
        event = {
            "webhookEvent": "jira:issue_deleted",
            "issue": {"key": "PROJ-22"},
        }
        result = self.engine.handle_webhook_event(event)
        self.assertEqual(result["action"], "deleted")
        self.assertEqual(result["issue_key"], "PROJ-22")

    def test_handle_comment_created_event(self):
        event = {
            "webhookEvent": "comment_created",
            "comment": {"id": "c1", "body": "LGTM"},
        }
        result = self.engine.handle_webhook_event(event)
        self.assertEqual(result["action"], "comment")
        self.assertEqual(result["comment"]["id"], "c1")

    def test_handle_unknown_event_returns_ignored(self):
        event = {"webhookEvent": "sprint_started"}
        result = self.engine.handle_webhook_event(event)
        self.assertEqual(result["action"], "ignored")

    def test_handle_event_no_issue_in_created_payload(self):
        event = {"webhookEvent": "jira:issue_created"}
        result = self.engine.handle_webhook_event(event)
        self.assertEqual(result["action"], "skipped")

    # sync_completion_to_jira
    def test_sync_completion_without_client_logs_warning(self):
        """sync_completion_to_jira with no client should not raise."""
        engine = self._make_engine_without_client()
        # Should not raise even without a client
        engine.sync_completion_to_jira("PROJ-30", "https://github.com/pr/1", "All green")

    def _make_engine_without_client(self):
        from integrations.jira.sync import JiraSyncEngine
        return JiraSyncEngine(jira_client=None)

    def test_sync_completion_with_client_posts_comment(self):
        mock_client = MagicMock()
        from integrations.jira.sync import JiraSyncEngine
        engine = JiraSyncEngine(jira_client=mock_client)
        engine.sync_completion_to_jira("PROJ-31", "https://pr.url", "Tests passed")
        mock_client.add_comment.assert_called_once()
        comment_args = mock_client.add_comment.call_args[0]
        self.assertEqual(comment_args[0], "PROJ-31")
        self.assertIn("https://pr.url", comment_args[1])

    def test_sync_completion_with_client_transitions_issue(self):
        mock_client = MagicMock()
        from integrations.jira.sync import JiraSyncEngine
        engine = JiraSyncEngine(jira_client=mock_client)
        engine.sync_completion_to_jira("PROJ-32", "https://pr.url", "OK")
        mock_client.transition_issue.assert_called_once_with("PROJ-32", "31")

    def test_sync_completion_raises_if_comment_fails(self):
        mock_client = MagicMock()
        mock_client.add_comment.side_effect = Exception("API error")
        from integrations.jira.sync import JiraSyncEngine
        engine = JiraSyncEngine(jira_client=mock_client)
        with self.assertRaises(Exception):
            engine.sync_completion_to_jira("PROJ-33", "https://pr.url", "OK")

    # map_field_config
    def test_map_field_config_basic(self):
        mapping = {
            "jira_project": "PROJ",
            "ae_project": "my-project",
            "field_overrides": {},
        }
        result = self.engine.map_field_config(mapping)
        self.assertEqual(result["jira_project"], "PROJ")
        self.assertEqual(result["ae_project"], "my-project")
        self.assertEqual(result["story_points_field"], "customfield_10016")

    def test_map_field_config_with_overrides(self):
        mapping = {
            "jira_project": "ACME",
            "ae_project": "acme-project",
            "field_overrides": {
                "story_points_field": "customfield_10028",
                "sprint_field": "customfield_10099",
            },
        }
        result = self.engine.map_field_config(mapping)
        self.assertEqual(result["story_points_field"], "customfield_10028")
        self.assertEqual(result["sprint_field"], "customfield_10099")

    def test_map_field_config_empty(self):
        result = self.engine.map_field_config({})
        self.assertIn("story_points_field", result)
        self.assertIn("sprint_field", result)


# ===========================================================================
# JiraOAuthHandler tests
# ===========================================================================


class TestJiraOAuthHandler(unittest.TestCase):
    """Tests for integrations.jira.oauth.JiraOAuthHandler."""

    def setUp(self):
        from integrations.jira.oauth import JiraOAuthHandler
        self.handler = JiraOAuthHandler(
            client_id="test-client-id",
            client_secret="test-client-secret",
        )

    def test_get_authorization_url_returns_string(self):
        url = self.handler.get_authorization_url("org-1", "https://app.dev/callback")
        self.assertIsInstance(url, str)
        self.assertIn("https://auth.atlassian.com/authorize", url)

    def test_authorization_url_contains_client_id(self):
        url = self.handler.get_authorization_url("org-1", "https://app.dev/callback")
        self.assertIn("test-client-id", url)

    def test_authorization_url_contains_redirect_uri(self):
        url = self.handler.get_authorization_url("org-1", "https://app.dev/cb")
        self.assertIn("app.dev", url)

    def test_authorization_url_contains_state(self):
        url = self.handler.get_authorization_url("org-2", "https://app.dev/cb")
        self.assertIn("state=", url)

    def test_different_orgs_get_different_states(self):
        url1 = self.handler.get_authorization_url("org-A", "https://app.dev/cb")
        url2 = self.handler.get_authorization_url("org-B", "https://app.dev/cb")
        # Extract state params
        state1 = [p for p in url1.split("&") if "state=" in p][0]
        state2 = [p for p in url2.split("&") if "state=" in p][0]
        self.assertNotEqual(state1, state2)

    def test_exchange_code_for_token_returns_token_dict(self):
        tokens = self.handler.exchange_code_for_token("auth-code-123", "https://cb.dev/")
        self.assertIn("access_token", tokens)
        self.assertIn("refresh_token", tokens)
        self.assertIn("token_type", tokens)
        self.assertEqual(tokens["token_type"], "Bearer")

    def test_exchange_code_deterministic(self):
        t1 = self.handler.exchange_code_for_token("same-code", "https://cb.dev/")
        t2 = self.handler.exchange_code_for_token("same-code", "https://cb.dev/")
        self.assertEqual(t1["access_token"], t2["access_token"])

    def test_exchange_different_codes_gives_different_tokens(self):
        t1 = self.handler.exchange_code_for_token("code-A", "https://cb.dev/")
        t2 = self.handler.exchange_code_for_token("code-B", "https://cb.dev/")
        self.assertNotEqual(t1["access_token"], t2["access_token"])

    def test_exchange_code_includes_scope(self):
        tokens = self.handler.exchange_code_for_token("code-X", "https://cb.dev/")
        self.assertIn("scope", tokens)

    def test_exchange_code_expires_in_is_3600(self):
        tokens = self.handler.exchange_code_for_token("code-Y", "https://cb.dev/")
        self.assertEqual(tokens["expires_in"], 3600)

    def test_refresh_token_returns_new_tokens(self):
        tokens = self.handler.refresh_token("old-refresh-token")
        self.assertIn("access_token", tokens)
        self.assertIn("refresh_token", tokens)

    def test_refresh_token_returns_different_access_token(self):
        t1 = self.handler.refresh_token("refresh-A")
        t2 = self.handler.refresh_token("refresh-B")
        self.assertNotEqual(t1["access_token"], t2["access_token"])

    def test_get_accessible_resources_returns_list(self):
        resources = self.handler.get_accessible_resources("access-token")
        self.assertIsInstance(resources, list)
        self.assertGreater(len(resources), 0)

    def test_get_accessible_resources_have_id_and_url(self):
        resources = self.handler.get_accessible_resources("tok")
        for r in resources:
            self.assertIn("id", r)
            self.assertIn("url", r)

    def test_validate_state_returns_org_id(self):
        url = self.handler.get_authorization_url("org-validate", "https://cb/")
        state = [p.split("=", 1)[1] for p in url.split("&") if "state=" in p][0]
        data = self.handler.validate_state(state)
        self.assertEqual(data["org_id"], "org-validate")

    def test_validate_state_single_use(self):
        url = self.handler.get_authorization_url("org-x", "https://cb/")
        state = [p.split("=", 1)[1] for p in url.split("&") if "state=" in p][0]
        self.handler.validate_state(state)  # first use OK
        with self.assertRaises(ValueError):
            self.handler.validate_state(state)  # second use should fail

    def test_validate_unknown_state_raises(self):
        with self.assertRaises(ValueError):
            self.handler.validate_state("totally-unknown-state")

    def test_validate_expired_state_raises(self):
        # Manually inject an expired state
        self.handler._states["expired-state"] = {
            "org_id": "org-z",
            "created_at": time.time() - 700,  # > 600s
        }
        with self.assertRaises(ValueError):
            self.handler.validate_state("expired-state")


# ===========================================================================
# JiraIntegrationConfig tests
# ===========================================================================


class TestJiraIntegrationConfig(unittest.TestCase):
    """Tests for integrations.jira.config.JiraIntegrationConfig and store helpers."""

    def setUp(self):
        # Clear the in-memory store before each test
        from integrations.jira import config as jira_config
        jira_config._configs.clear()

    def test_load_from_dict_basic(self):
        from integrations.jira.config import JiraIntegrationConfig
        data = {
            "org_id": "test-org",
            "jira_base_url": "https://test.atlassian.net",
            "enabled": True,
        }
        cfg = JiraIntegrationConfig.load_from_dict(data)
        self.assertEqual(cfg.org_id, "test-org")
        self.assertEqual(cfg.jira_base_url, "https://test.atlassian.net")
        self.assertTrue(cfg.enabled)

    def test_load_from_dict_missing_org_id_raises(self):
        from integrations.jira.config import JiraIntegrationConfig
        with self.assertRaises(ValueError):
            JiraIntegrationConfig.load_from_dict({})

    def test_load_from_dict_empty_org_id_raises(self):
        from integrations.jira.config import JiraIntegrationConfig
        with self.assertRaises(ValueError):
            JiraIntegrationConfig.load_from_dict({"org_id": ""})

    def test_load_from_dict_defaults(self):
        from integrations.jira.config import JiraIntegrationConfig
        cfg = JiraIntegrationConfig.load_from_dict({"org_id": "org-d"})
        self.assertEqual(cfg.jira_base_url, "")
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.project_mappings, [])
        self.assertEqual(cfg.field_mappings, {})
        self.assertEqual(cfg.webhook_secret, "")

    def test_load_from_dict_with_project_mappings(self):
        from integrations.jira.config import JiraIntegrationConfig
        mappings = [{"jira_project": "PROJ", "ae_project": "my-proj"}]
        cfg = JiraIntegrationConfig.load_from_dict(
            {"org_id": "org-1", "project_mappings": mappings}
        )
        self.assertEqual(len(cfg.project_mappings), 1)

    def test_to_dict_round_trips(self):
        from integrations.jira.config import JiraIntegrationConfig
        cfg = JiraIntegrationConfig(
            org_id="org-rt",
            jira_base_url="https://rt.atlassian.net",
            enabled=True,
            webhook_secret="secret123",
        )
        d = cfg.to_dict()
        self.assertEqual(d["org_id"], "org-rt")
        self.assertEqual(d["webhook_secret"], "secret123")
        restored = JiraIntegrationConfig.load_from_dict(d)
        self.assertEqual(restored.org_id, cfg.org_id)
        self.assertEqual(restored.enabled, cfg.enabled)

    def test_save_and_load_config(self):
        from integrations.jira.config import (
            JiraIntegrationConfig,
            load_config,
            save_config,
        )
        cfg = JiraIntegrationConfig(org_id="org-sl", jira_base_url="https://sl.net")
        save_config(cfg)
        loaded = load_config("org-sl")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.jira_base_url, "https://sl.net")  # type: ignore[union-attr]

    def test_load_nonexistent_returns_none(self):
        from integrations.jira.config import load_config
        self.assertIsNone(load_config("does-not-exist"))

    def test_delete_config(self):
        from integrations.jira.config import (
            JiraIntegrationConfig,
            delete_config,
            load_config,
            save_config,
        )
        save_config(JiraIntegrationConfig(org_id="org-del"))
        self.assertTrue(delete_config("org-del"))
        self.assertIsNone(load_config("org-del"))

    def test_delete_nonexistent_returns_false(self):
        from integrations.jira.config import delete_config
        self.assertFalse(delete_config("phantom-org"))

    def test_list_configs(self):
        from integrations.jira.config import (
            JiraIntegrationConfig,
            list_configs,
            save_config,
        )
        save_config(JiraIntegrationConfig(org_id="org-A"))
        save_config(JiraIntegrationConfig(org_id="org-B"))
        all_cfgs = list_configs()
        org_ids = {c.org_id for c in all_cfgs}
        self.assertIn("org-A", org_ids)
        self.assertIn("org-B", org_ids)


# ===========================================================================
# REST API endpoint tests
# ===========================================================================


class TestJiraWebhookEndpoint(unittest.IsolatedAsyncioTestCase):
    """Tests for POST /api/webhooks/jira endpoint."""

    async def _make_request(
        self,
        body: dict,
        secret: str = "",
        signature: str = "",
        org_id: str = "",
        pre_save_config: bool = False,
    ):
        from aiohttp.test_utils import make_mocked_request
        from integrations.jira.config import (
            JiraIntegrationConfig,
            save_config,
        )
        from integrations.jira import config as jira_config

        jira_config._configs.clear()

        if pre_save_config and org_id:
            save_config(
                JiraIntegrationConfig(
                    org_id=org_id,
                    webhook_secret=secret,
                )
            )

        from dashboard.rest_api_server import RESTAPIServer
        from unittest.mock import AsyncMock

        server = RESTAPIServer.__new__(RESTAPIServer)

        payload_bytes = json.dumps(body).encode()

        # Build query string
        qs = f"?org_id={org_id}" if org_id else ""

        mock_request = MagicMock()
        mock_request.read = AsyncMock(return_value=payload_bytes)
        mock_request.json = AsyncMock(return_value=body)
        mock_request.headers = {"X-Jira-Signature": signature}
        mock_request.rel_url.query = {"org_id": org_id} if org_id else {}

        return await server.jira_webhook(mock_request)

    async def test_webhook_without_secret_succeeds(self):
        body = {
            "webhookEvent": "jira:issue_created",
            "issue": _make_jira_issue(),
        }
        resp = await self._make_request(body)
        self.assertEqual(resp.status, 200)

    async def test_webhook_with_valid_signature_succeeds(self):
        body = {"webhookEvent": "jira:issue_created", "issue": _make_jira_issue()}
        secret = "my-webhook-secret"
        payload_bytes = json.dumps(body).encode()
        sig = "sha256=" + hmac.new(
            secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()
        resp = await self._make_request(body, secret=secret, signature=sig, org_id="org-ws", pre_save_config=True)
        self.assertEqual(resp.status, 200)

    async def test_webhook_with_invalid_signature_returns_401(self):
        body = {"webhookEvent": "jira:issue_created", "issue": _make_jira_issue()}
        resp = await self._make_request(
            body, secret="real-secret", signature="sha256=invalidsig",
            org_id="org-bad-sig", pre_save_config=True
        )
        self.assertEqual(resp.status, 401)

    async def test_webhook_with_secret_but_no_signature_returns_401(self):
        body = {"webhookEvent": "jira:issue_created"}
        resp = await self._make_request(
            body, secret="configured-secret", signature="",
            org_id="org-no-sig", pre_save_config=True
        )
        self.assertEqual(resp.status, 401)

    async def test_webhook_issue_updated_returns_200(self):
        body = {"webhookEvent": "jira:issue_updated", "issue": _make_jira_issue()}
        resp = await self._make_request(body)
        self.assertEqual(resp.status, 200)


class TestJiraStatusEndpoint(unittest.IsolatedAsyncioTestCase):
    """Tests for GET /api/integrations/jira/status."""

    def setUp(self):
        from integrations.jira import config as jira_config
        jira_config._configs.clear()

    async def _call_status(self, org_id: str):
        from dashboard.rest_api_server import RESTAPIServer
        server = RESTAPIServer.__new__(RESTAPIServer)
        mock_request = MagicMock()
        mock_request.rel_url.query = {"org_id": org_id}
        return await server.jira_get_status(mock_request)

    async def test_status_no_org_id_returns_400(self):
        resp = await self._call_status("")
        self.assertEqual(resp.status, 400)

    async def test_status_unconnected_org_returns_200_not_connected(self):
        resp = await self._call_status("org-new")
        self.assertEqual(resp.status, 200)
        body = json.loads(resp.body)
        self.assertFalse(body["connected"])

    async def test_status_connected_org_returns_200_connected(self):
        from integrations.jira.config import JiraIntegrationConfig, save_config
        save_config(JiraIntegrationConfig(
            org_id="org-conn",
            jira_base_url="https://conn.atlassian.net",
            enabled=True,
        ))
        resp = await self._call_status("org-conn")
        body = json.loads(resp.body)
        self.assertTrue(body["connected"])
        self.assertTrue(body["enabled"])
        self.assertEqual(body["jira_base_url"], "https://conn.atlassian.net")


class TestJiraConnectEndpoint(unittest.IsolatedAsyncioTestCase):
    """Tests for POST /api/integrations/jira/connect."""

    async def _call_connect(self, body: dict):
        from unittest.mock import AsyncMock
        from dashboard.rest_api_server import RESTAPIServer
        server = RESTAPIServer.__new__(RESTAPIServer)
        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value=body)
        return await server.jira_connect(mock_request)

    async def test_connect_returns_auth_url(self):
        resp = await self._call_connect({
            "org_id": "org-connect",
            "redirect_uri": "https://app.dev/callback",
        })
        self.assertEqual(resp.status, 200)
        body = json.loads(resp.body)
        self.assertIn("auth_url", body)
        self.assertIn("atlassian.com", body["auth_url"])

    async def test_connect_missing_org_id_returns_400(self):
        resp = await self._call_connect({"redirect_uri": "https://app.dev/cb"})
        self.assertEqual(resp.status, 400)

    async def test_connect_missing_redirect_uri_returns_400(self):
        resp = await self._call_connect({"org_id": "org-x"})
        self.assertEqual(resp.status, 400)

    async def test_connect_returns_org_id(self):
        resp = await self._call_connect({
            "org_id": "org-y",
            "redirect_uri": "https://app.dev/cb",
        })
        body = json.loads(resp.body)
        self.assertEqual(body["org_id"], "org-y")


class TestJiraCallbackEndpoint(unittest.IsolatedAsyncioTestCase):
    """Tests for GET /api/integrations/jira/callback."""

    def setUp(self):
        from integrations.jira import config as jira_config
        jira_config._configs.clear()

    async def _call_callback(self, code: str, state: str, redirect_uri: str = ""):
        from dashboard.rest_api_server import RESTAPIServer
        server = RESTAPIServer.__new__(RESTAPIServer)
        mock_request = MagicMock()
        mock_request.rel_url.query = {
            "code": code,
            "state": state,
            "redirect_uri": redirect_uri,
        }
        return await server.jira_callback(mock_request)

    async def _get_valid_state(self, org_id: str = "org-cb") -> str:
        """Generate a valid OAuth state via the handler."""
        from integrations.jira.oauth import JiraOAuthHandler
        handler = JiraOAuthHandler()
        url = handler.get_authorization_url(org_id, "https://app.dev/cb")
        state = [p.split("=", 1)[1] for p in url.split("&") if "state=" in p][0]
        # Inject the handler's state into the singleton used by RESTAPIServer
        # by patching the oauth handler's _states dict
        # For this test, we pre-seed the handler through the module
        from integrations.jira import oauth as jira_oauth
        # Patch the global handler (the endpoint creates a new one, so we
        # need to pre-populate via the module-level state approach)
        # Instead: generate state directly and inject
        from integrations.jira.oauth import JiraOAuthHandler as H
        # The endpoint creates a new JiraOAuthHandler — we need to seed its state.
        # We achieve this by patching the class to return our pre-seeded handler.
        import time
        self._patched_handler = H()
        self._patched_handler._states[state] = {"org_id": org_id, "created_at": time.time()}
        return state

    async def test_callback_missing_code_returns_400(self):
        resp = await self._call_callback("", "some-state")
        self.assertEqual(resp.status, 400)

    async def test_callback_missing_state_returns_400(self):
        resp = await self._call_callback("code-123", "")
        self.assertEqual(resp.status, 400)

    async def test_callback_invalid_state_returns_400(self):
        resp = await self._call_callback("code-123", "invalid-state-nonce")
        self.assertEqual(resp.status, 400)


class TestJiraSaveConfigEndpoint(unittest.IsolatedAsyncioTestCase):
    """Tests for POST /api/integrations/jira/config."""

    def setUp(self):
        from integrations.jira import config as jira_config
        jira_config._configs.clear()

    async def _call_save(self, body: dict):
        from unittest.mock import AsyncMock
        from dashboard.rest_api_server import RESTAPIServer
        server = RESTAPIServer.__new__(RESTAPIServer)
        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value=body)
        return await server.jira_save_config(mock_request)

    async def test_save_config_basic(self):
        resp = await self._call_save({
            "org_id": "org-save",
            "jira_base_url": "https://save.atlassian.net",
            "enabled": True,
        })
        self.assertEqual(resp.status, 200)
        body = json.loads(resp.body)
        self.assertEqual(body["org_id"], "org-save")
        self.assertTrue(body["enabled"])

    async def test_save_config_no_org_id_returns_400(self):
        resp = await self._call_save({"jira_base_url": "https://x.net"})
        self.assertEqual(resp.status, 400)

    async def test_save_config_does_not_return_webhook_secret(self):
        resp = await self._call_save({
            "org_id": "org-secret",
            "webhook_secret": "super-secret",
        })
        body = json.loads(resp.body)
        self.assertNotIn("webhook_secret", body)

    async def test_save_config_persists_to_store(self):
        await self._call_save({"org_id": "org-persist", "jira_base_url": "https://p.net"})
        from integrations.jira.config import load_config
        cfg = load_config("org-persist")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.jira_base_url, "https://p.net")  # type: ignore[union-attr]

    async def test_save_config_with_project_mappings(self):
        mappings = [{"jira_project": "TEST", "ae_project": "test-proj"}]
        resp = await self._call_save({
            "org_id": "org-map",
            "project_mappings": mappings,
        })
        self.assertEqual(resp.status, 200)
        body = json.loads(resp.body)
        self.assertEqual(len(body["project_mappings"]), 1)

    async def test_save_config_with_field_mappings(self):
        resp = await self._call_save({
            "org_id": "org-field",
            "field_mappings": {"customfield_10016": "story_points"},
        })
        body = json.loads(resp.body)
        self.assertEqual(body["field_mappings"]["customfield_10016"], "story_points")


# ===========================================================================
# Integration smoke tests
# ===========================================================================


class TestJiraIntegrationSmoke(unittest.TestCase):
    """End-to-end smoke tests exercising multiple components together."""

    def test_full_inbound_flow(self):
        """Jira webhook → sync engine → linear-compatible issue."""
        from integrations.jira.sync import JiraSyncEngine

        engine = JiraSyncEngine()
        event = {
            "webhookEvent": "jira:issue_created",
            "issue": _make_jira_issue(
                key="SMOKE-1",
                summary="Smoke test issue",
                issue_type="Story",
                priority="High",
                status="To Do",
                description="## Acceptance Criteria\n- Works\n",
                story_points=3,
                sprint_name="Sprint 1",
            ),
        }
        result = engine.handle_webhook_event(event)
        self.assertEqual(result["action"], "created")
        issue = result["issue"]
        self.assertEqual(issue["id"], "SMOKE-1")
        self.assertEqual(issue["type"], "feature")
        self.assertEqual(issue["priority"], 2)
        self.assertEqual(issue["status"], "backlog")
        self.assertIn("Works", issue["acceptance_criteria"])
        self.assertEqual(issue["estimate"], 3)
        self.assertEqual(issue["sprint"], "Sprint 1")

    def test_mapper_and_smart_commit(self):
        from integrations.jira.mapper import JiraIssueMapper

        mapper = JiraIssueMapper()
        commit = mapper.format_smart_commit("SMOKE-2", "feat: Add Jira integration")
        self.assertEqual(commit, "SMOKE-2: feat: Add Jira integration")

    def test_oauth_full_flow(self):
        from integrations.jira.oauth import JiraOAuthHandler

        handler = JiraOAuthHandler()
        url = handler.get_authorization_url("smoke-org", "https://app.dev/cb")
        state = [p.split("=", 1)[1] for p in url.split("&") if "state=" in p][0]
        # Simulate state validation
        data = handler.validate_state(state)
        self.assertEqual(data["org_id"], "smoke-org")
        # Exchange code
        tokens = handler.exchange_code_for_token("smoke-code", "https://app.dev/cb")
        self.assertIn("access_token", tokens)
        # Refresh
        refreshed = handler.refresh_token(tokens["refresh_token"])
        self.assertIn("access_token", refreshed)
        # Get resources
        resources = handler.get_accessible_resources(refreshed["access_token"])
        self.assertGreater(len(resources), 0)

    def test_config_round_trip(self):
        from integrations.jira.config import (
            JiraIntegrationConfig,
            delete_config,
            load_config,
            save_config,
        )
        from integrations.jira import config as jira_config
        jira_config._configs.clear()

        cfg = JiraIntegrationConfig(
            org_id="smoke-config",
            jira_base_url="https://smoke.atlassian.net",
            project_mappings=[{"jira_project": "SMOKE", "ae_project": "smoke"}],
            field_mappings={"customfield_10016": "story_points"},
            enabled=True,
            webhook_secret="smoke-secret",
        )
        save_config(cfg)
        loaded = load_config("smoke-config")
        self.assertEqual(loaded.org_id, "smoke-config")
        self.assertEqual(loaded.webhook_secret, "smoke-secret")
        self.assertEqual(len(loaded.project_mappings), 1)
        delete_config("smoke-config")
        self.assertIsNone(load_config("smoke-config"))


if __name__ == "__main__":
    unittest.main()
