"""Comprehensive tests for GitLab integration (AI-251).

Tests cover:
- GitLabClient: all public methods with mocked HTTP calls
- GitLabCIPipeline: status detection for all pipeline states
- GitLabMRManager: branch creation naming, MR creation, pipeline gating
- GitLabOAuthHandler: URL generation, state validation, token exchange
- GitLabIntegrationConfig: serialisation, persistence helpers
- REST API endpoints: gitlab_webhook, gitlab_get_status, gitlab_connect,
  gitlab_callback, gitlab_save_config, gitlab_pipeline_status
"""

from __future__ import annotations

import json
import time
import unittest
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch


# ===========================================================================
# GitLabClient tests
# ===========================================================================


class TestGitLabClient(unittest.TestCase):
    """Tests for integrations.gitlab.client.GitLabClient."""

    def _make_client(
        self,
        get_response=None,
        post_response=None,
        put_response=None,
        base_url="https://gitlab.com",
    ):
        from integrations.gitlab.client import GitLabClient

        def _get(url, headers):
            return get_response if get_response is not None else {}

        def _post(url, headers, body):
            return post_response if post_response is not None else {}

        def _put(url, headers, body):
            return put_response if put_response is not None else {}

        return GitLabClient(
            base_url=base_url,
            auth_token="mock-gitlab-token",
            _http_get=_get,
            _http_post=_post,
            _http_put=_put,
        )

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def test_base_url_trailing_slash_stripped(self):
        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com/", "tok")
        self.assertFalse(c.base_url.endswith("/"))

    def test_headers_include_bearer_token(self):
        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "my-secret-token")
        headers = c._headers()
        self.assertEqual(headers["Authorization"], "Bearer my-secret-token")

    def test_api_url_construction(self):
        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok")
        url = c._api("projects/42/branches")
        self.assertIn("/api/v4/projects/42/branches", url)

    def test_project_api_url_construction(self):
        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok")
        url = c._project_api(42, "merge_requests/1")
        self.assertIn("projects/42/merge_requests/1", url)

    def test_project_api_url_no_path(self):
        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok")
        url = c._project_api(42)
        self.assertIn("projects/42", url)
        self.assertNotIn("//", url.replace("https://", ""))

    # ------------------------------------------------------------------
    # create_branch
    # ------------------------------------------------------------------

    def test_create_branch_returns_dict(self):
        response = {"name": "feature/ai-251", "commit": {"id": "abc123"}}
        client = self._make_client(post_response=response)
        result = client.create_branch(42, "feature/ai-251", ref="main")
        self.assertEqual(result["name"], "feature/ai-251")

    def test_create_branch_posts_correct_body(self):
        called = []

        def _post(url, headers, body):
            called.append((url, body))
            return {"name": "feature/test"}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        c.create_branch(10, "feature/test", ref="develop")
        self.assertEqual(len(called), 1)
        _, body = called[0]
        self.assertEqual(body["branch"], "feature/test")
        self.assertEqual(body["ref"], "develop")

    def test_create_branch_url_contains_project_id(self):
        called = []

        def _post(url, headers, body):
            called.append(url)
            return {}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        c.create_branch(99, "my-branch")
        self.assertIn("99", called[0])

    def test_create_branch_default_ref_is_main(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        c.create_branch(1, "branch-name")
        self.assertEqual(called[0]["ref"], "main")

    # ------------------------------------------------------------------
    # create_commit
    # ------------------------------------------------------------------

    def test_create_commit_returns_dict(self):
        response = {"id": "commit-sha-123", "message": "feat: add file"}
        client = self._make_client(post_response=response)
        actions = [{"action": "create", "file_path": "README.md", "content": "hello"}]
        result = client.create_commit(42, "feature/test", "feat: add file", actions)
        self.assertEqual(result["id"], "commit-sha-123")

    def test_create_commit_posts_correct_body(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {"id": "sha"}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        actions = [{"action": "create", "file_path": "foo.py", "content": "x = 1"}]
        c.create_commit(5, "feature/f", "add foo.py", actions)
        body = called[0]
        self.assertEqual(body["branch"], "feature/f")
        self.assertEqual(body["commit_message"], "add foo.py")
        self.assertEqual(body["actions"], actions)

    def test_create_commit_multiple_actions(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        actions = [
            {"action": "create", "file_path": "a.py", "content": ""},
            {"action": "update", "file_path": "b.py", "content": "updated"},
            {"action": "delete", "file_path": "c.py"},
        ]
        c.create_commit(1, "main", "multi-file commit", actions)
        self.assertEqual(len(called[0]["actions"]), 3)

    # ------------------------------------------------------------------
    # create_merge_request
    # ------------------------------------------------------------------

    def test_create_merge_request_returns_dict(self):
        response = {
            "iid": 5,
            "title": "feat: AI-251 GitLab integration",
            "state": "opened",
        }
        client = self._make_client(post_response=response)
        result = client.create_merge_request(
            42, "feature/ai-251", "main", "feat: AI-251 GitLab integration"
        )
        self.assertEqual(result["iid"], 5)

    def test_create_merge_request_posts_correct_body(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {"iid": 1}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        c.create_merge_request(1, "feature/x", "main", "MR title", "desc", ["bug", "ci"])
        body = called[0]
        self.assertEqual(body["source_branch"], "feature/x")
        self.assertEqual(body["target_branch"], "main")
        self.assertEqual(body["title"], "MR title")
        self.assertEqual(body["description"], "desc")
        self.assertIn("bug", body["labels"])

    def test_create_merge_request_without_labels(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        c.create_merge_request(1, "feature/y", "main", "No labels MR")
        self.assertNotIn("labels", called[0])

    def test_create_merge_request_with_empty_labels(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        c.create_merge_request(1, "feature/z", "main", "Empty labels", labels=[])
        # Empty list is falsy, so labels key should not be added
        self.assertNotIn("labels", called[0])

    # ------------------------------------------------------------------
    # assign_mr_reviewer
    # ------------------------------------------------------------------

    def test_assign_mr_reviewer_puts_reviewer_ids(self):
        called = []

        def _put(url, headers, body):
            called.append((url, body))
            return {"iid": 3, "reviewer_ids": [101, 202]}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_put=_put)
        c.assign_mr_reviewer(10, 3, [101, 202])
        _, body = called[0]
        self.assertEqual(body["reviewer_ids"], [101, 202])

    def test_assign_mr_reviewer_url_contains_mr_iid(self):
        called = []

        def _put(url, headers, body):
            called.append(url)
            return {}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_put=_put)
        c.assign_mr_reviewer(5, 7, [1])
        self.assertIn("merge_requests/7", called[0])

    # ------------------------------------------------------------------
    # merge_mr
    # ------------------------------------------------------------------

    def test_merge_mr_posts_to_merge_endpoint(self):
        called = []

        def _post(url, headers, body):
            called.append(url)
            return {"state": "merged"}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        c.merge_mr(10, 4)
        self.assertIn("merge_requests/4/merge", called[0])

    def test_merge_mr_with_custom_message(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {"state": "merged"}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        c.merge_mr(10, 4, merge_commit_message="Auto-merge by agent")
        self.assertEqual(called[0].get("merge_commit_message"), "Auto-merge by agent")

    def test_merge_mr_without_message_sends_empty_body(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {"state": "merged"}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        c.merge_mr(10, 4)
        self.assertNotIn("merge_commit_message", called[0])

    # ------------------------------------------------------------------
    # get_mr
    # ------------------------------------------------------------------

    def test_get_mr_returns_dict(self):
        response = {"iid": 2, "title": "Feature MR", "state": "opened"}
        client = self._make_client(get_response=response)
        result = client.get_mr(42, 2)
        self.assertEqual(result["iid"], 2)
        self.assertEqual(result["state"], "opened")

    def test_get_mr_url_contains_mr_iid(self):
        called = []

        def _get(url, headers):
            called.append(url)
            return {}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_get=_get)
        c.get_mr(20, 9)
        self.assertIn("merge_requests/9", called[0])

    # ------------------------------------------------------------------
    # get_pipeline_status
    # ------------------------------------------------------------------

    def test_get_pipeline_status_returns_dict(self):
        response = {"id": 123, "status": "success", "ref": "main"}
        client = self._make_client(get_response=response)
        result = client.get_pipeline_status(42, 123)
        self.assertEqual(result["status"], "success")

    def test_get_pipeline_status_url_contains_pipeline_id(self):
        called = []

        def _get(url, headers):
            called.append(url)
            return {}

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_get=_get)
        c.get_pipeline_status(5, 999)
        self.assertIn("pipelines/999", called[0])

    # ------------------------------------------------------------------
    # list_mr_pipelines
    # ------------------------------------------------------------------

    def test_list_mr_pipelines_returns_list(self):
        response = [{"id": 1, "status": "success"}, {"id": 2, "status": "failed"}]
        client = self._make_client(get_response=response)
        result = client.list_mr_pipelines(42, 3)
        self.assertEqual(len(result), 2)

    def test_list_mr_pipelines_returns_empty_on_non_list(self):
        client = self._make_client(get_response={"unexpected": "object"})
        result = client.list_mr_pipelines(42, 3)
        self.assertEqual(result, [])

    def test_list_mr_pipelines_url_contains_mr_iid(self):
        called = []

        def _get(url, headers):
            called.append(url)
            return []

        from integrations.gitlab.client import GitLabClient

        c = GitLabClient("https://gitlab.com", "tok", _http_get=_get)
        c.list_mr_pipelines(10, 5)
        self.assertIn("merge_requests/5/pipelines", called[0])

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_client_error_raised_on_http_error(self):
        from integrations.gitlab.client import GitLabClient, GitLabClientError

        def _get(url, headers):
            raise GitLabClientError("HTTP 404 GET /api/v4/projects/1/merge_requests/99")

        c = GitLabClient("https://gitlab.com", "tok", _http_get=_get)
        with self.assertRaises(GitLabClientError):
            c.get_mr(1, 99)

    def test_client_error_on_post_failure(self):
        from integrations.gitlab.client import GitLabClient, GitLabClientError

        def _post(url, headers, body):
            raise GitLabClientError("HTTP 422 POST branch")

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        with self.assertRaises(GitLabClientError):
            c.create_branch(1, "conflict-branch")


# ===========================================================================
# GitLabCIPipeline tests
# ===========================================================================


class TestGitLabCIPipeline(unittest.TestCase):
    """Tests for integrations.gitlab.ci_pipeline.GitLabCIPipeline."""

    def setUp(self):
        from integrations.gitlab.ci_pipeline import GitLabCIPipeline
        self.pipeline_helper = GitLabCIPipeline()

    def _make_pipeline(self, status: str, **kwargs) -> Dict[str, Any]:
        base = {
            "id": 100,
            "status": status,
            "ref": "feature/ai-251",
            "sha": "abc123def456",
            "duration": 120,
            "web_url": "https://gitlab.com/project/-/pipelines/100",
            "created_at": "2024-01-01T00:00:00Z",
            "finished_at": "2024-01-01T00:02:00Z",
        }
        base.update(kwargs)
        return base

    # ------------------------------------------------------------------
    # Status predicates
    # ------------------------------------------------------------------

    def test_success_is_passing(self):
        p = self._make_pipeline("success")
        self.assertTrue(self.pipeline_helper.is_pipeline_passing(p))

    def test_failed_is_not_passing(self):
        p = self._make_pipeline("failed")
        self.assertFalse(self.pipeline_helper.is_pipeline_passing(p))

    def test_running_is_not_passing(self):
        p = self._make_pipeline("running")
        self.assertFalse(self.pipeline_helper.is_pipeline_passing(p))

    def test_pending_is_not_passing(self):
        p = self._make_pipeline("pending")
        self.assertFalse(self.pipeline_helper.is_pipeline_passing(p))

    def test_canceled_is_not_passing(self):
        p = self._make_pipeline("canceled")
        self.assertFalse(self.pipeline_helper.is_pipeline_passing(p))

    def test_failed_is_failed(self):
        p = self._make_pipeline("failed")
        self.assertTrue(self.pipeline_helper.is_pipeline_failed(p))

    def test_canceled_is_failed(self):
        p = self._make_pipeline("canceled")
        self.assertTrue(self.pipeline_helper.is_pipeline_failed(p))

    def test_success_is_not_failed(self):
        p = self._make_pipeline("success")
        self.assertFalse(self.pipeline_helper.is_pipeline_failed(p))

    def test_running_is_not_failed(self):
        p = self._make_pipeline("running")
        self.assertFalse(self.pipeline_helper.is_pipeline_failed(p))

    def test_running_is_running(self):
        p = self._make_pipeline("running")
        self.assertTrue(self.pipeline_helper.is_pipeline_running(p))

    def test_pending_is_running(self):
        p = self._make_pipeline("pending")
        self.assertTrue(self.pipeline_helper.is_pipeline_running(p))

    def test_created_is_running(self):
        p = self._make_pipeline("created")
        self.assertTrue(self.pipeline_helper.is_pipeline_running(p))

    def test_success_is_not_running(self):
        p = self._make_pipeline("success")
        self.assertFalse(self.pipeline_helper.is_pipeline_running(p))

    def test_failed_is_not_running(self):
        p = self._make_pipeline("failed")
        self.assertFalse(self.pipeline_helper.is_pipeline_running(p))

    def test_skipped_is_not_passing(self):
        p = self._make_pipeline("skipped")
        self.assertFalse(self.pipeline_helper.is_pipeline_passing(p))

    def test_skipped_is_not_failed(self):
        p = self._make_pipeline("skipped")
        self.assertFalse(self.pipeline_helper.is_pipeline_failed(p))

    def test_skipped_is_not_running(self):
        p = self._make_pipeline("skipped")
        self.assertFalse(self.pipeline_helper.is_pipeline_running(p))

    def test_empty_status_not_passing(self):
        self.assertFalse(self.pipeline_helper.is_pipeline_passing({}))

    def test_empty_status_not_failed(self):
        self.assertFalse(self.pipeline_helper.is_pipeline_failed({}))

    def test_empty_status_not_running(self):
        self.assertFalse(self.pipeline_helper.is_pipeline_running({}))

    # ------------------------------------------------------------------
    # get_pipeline_summary
    # ------------------------------------------------------------------

    def test_summary_contains_required_fields(self):
        p = self._make_pipeline("success")
        summary = self.pipeline_helper.get_pipeline_summary(p)
        for key in ("id", "status", "ref", "sha", "duration", "web_url", "stages"):
            self.assertIn(key, summary)

    def test_summary_passing_has_deploy_stage(self):
        p = self._make_pipeline("success")
        summary = self.pipeline_helper.get_pipeline_summary(p)
        self.assertIn("deploy", summary["stages"])

    def test_summary_failed_does_not_have_deploy_stage(self):
        p = self._make_pipeline("failed")
        summary = self.pipeline_helper.get_pipeline_summary(p)
        self.assertNotIn("deploy", summary["stages"])

    def test_summary_running_has_build_stage(self):
        p = self._make_pipeline("running")
        summary = self.pipeline_helper.get_pipeline_summary(p)
        self.assertIn("build", summary["stages"])

    def test_summary_status_preserved(self):
        p = self._make_pipeline("failed")
        summary = self.pipeline_helper.get_pipeline_summary(p)
        self.assertEqual(summary["status"], "failed")

    def test_summary_web_url_preserved(self):
        p = self._make_pipeline("success")
        summary = self.pipeline_helper.get_pipeline_summary(p)
        self.assertEqual(summary["web_url"], p["web_url"])

    def test_summary_empty_pipeline(self):
        summary = self.pipeline_helper.get_pipeline_summary({})
        self.assertEqual(summary["status"], "unknown")
        self.assertEqual(summary["stages"], [])

    # ------------------------------------------------------------------
    # get_latest_pipeline
    # ------------------------------------------------------------------

    def test_get_latest_pipeline_requires_client(self):
        from integrations.gitlab.ci_pipeline import GitLabCIPipeline

        helper = GitLabCIPipeline(client=None)
        with self.assertRaises(RuntimeError):
            helper.get_latest_pipeline(1, 1)

    def test_get_latest_pipeline_returns_first(self):
        pipelines = [
            {"id": 10, "status": "success"},
            {"id": 9, "status": "failed"},
        ]
        mock_client = MagicMock()
        mock_client.list_mr_pipelines.return_value = pipelines

        from integrations.gitlab.ci_pipeline import GitLabCIPipeline

        helper = GitLabCIPipeline(client=mock_client)
        result = helper.get_latest_pipeline(1, 1)
        self.assertEqual(result["id"], 10)

    def test_get_latest_pipeline_empty_returns_empty_dict(self):
        mock_client = MagicMock()
        mock_client.list_mr_pipelines.return_value = []

        from integrations.gitlab.ci_pipeline import GitLabCIPipeline

        helper = GitLabCIPipeline(client=mock_client)
        result = helper.get_latest_pipeline(1, 1)
        self.assertEqual(result, {})


# ===========================================================================
# GitLabMRManager tests
# ===========================================================================


class TestGitLabMRManager(unittest.TestCase):
    """Tests for integrations.gitlab.mr_manager.GitLabMRManager."""

    def _make_manager(
        self,
        get_response=None,
        post_response=None,
        put_response=None,
        pipeline_response=None,
    ):
        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.ci_pipeline import GitLabCIPipeline
        from integrations.gitlab.mr_manager import GitLabMRManager

        def _get(url, headers):
            if isinstance(get_response, list):
                # list_mr_pipelines endpoint
                return get_response
            return get_response if get_response is not None else {}

        def _post(url, headers, body):
            return post_response if post_response is not None else {}

        def _put(url, headers, body):
            return put_response if put_response is not None else {}

        client = GitLabClient(
            "https://gitlab.com", "tok",
            _http_get=_get, _http_post=_post, _http_put=_put,
        )
        pipeline = GitLabCIPipeline(client=client)
        return GitLabMRManager(client=client, pipeline=pipeline)

    # ------------------------------------------------------------------
    # create_feature_branch
    # ------------------------------------------------------------------

    def test_branch_name_prefixed_with_feature(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {"name": body["branch"]}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        manager = GitLabMRManager(client=c)
        name = manager.create_feature_branch(1, "AI-251")
        self.assertTrue(name.startswith("feature/"))

    def test_branch_name_lowercased(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {"name": body["branch"]}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        manager = GitLabMRManager(client=c)
        name = manager.create_feature_branch(1, "AI-251")
        self.assertEqual(name, name.lower())

    def test_branch_name_replaces_special_chars(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {"name": body["branch"]}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        manager = GitLabMRManager(client=c)
        name = manager.create_feature_branch(1, "AI-251: Some Feature!")
        # Should not contain colons or exclamation marks
        self.assertNotIn(":", name)
        self.assertNotIn("!", name)
        self.assertNotIn(" ", name)

    def test_branch_name_for_standard_key(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {"name": body["branch"]}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        manager = GitLabMRManager(client=c)
        name = manager.create_feature_branch(1, "AI-251")
        self.assertEqual(name, "feature/ai-251")

    def test_create_feature_branch_uses_base_branch(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {"name": body["branch"]}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        manager = GitLabMRManager(client=c)
        manager.create_feature_branch(1, "AI-251", base_branch="develop")
        self.assertEqual(called[0]["ref"], "develop")

    def test_create_feature_branch_returns_branch_name(self):
        def _post(url, headers, body):
            return {"name": body["branch"]}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        manager = GitLabMRManager(client=c)
        result = manager.create_feature_branch(1, "TICKET-42")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    # ------------------------------------------------------------------
    # create_agent_mr
    # ------------------------------------------------------------------

    def test_create_agent_mr_returns_mr_dict(self):
        response = {"iid": 7, "title": "Test MR", "state": "opened"}
        manager = self._make_manager(post_response=response)
        result = manager.create_agent_mr(1, "feature/x", "Test MR", "description")
        self.assertEqual(result["iid"], 7)

    def test_create_agent_mr_uses_main_as_target(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {"iid": 1}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        manager = GitLabMRManager(client=c)
        manager.create_agent_mr(1, "feature/y", "MR", "desc")
        self.assertEqual(called[0]["target_branch"], "main")

    def test_create_agent_mr_with_labels(self):
        called = []

        def _post(url, headers, body):
            called.append(body)
            return {"iid": 1}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_post=_post)
        manager = GitLabMRManager(client=c)
        manager.create_agent_mr(1, "feature/z", "MR with labels", "desc", labels=["ci", "agent"])
        self.assertIn("ci", called[0].get("labels", ""))

    # ------------------------------------------------------------------
    # can_merge
    # ------------------------------------------------------------------

    def test_can_merge_true_when_open_and_no_pipeline(self):
        mr_response = {"state": "opened", "merge_status": "can_be_merged"}

        def _get(url, headers):
            if "pipelines" in url:
                return []  # No pipelines
            return mr_response

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.ci_pipeline import GitLabCIPipeline
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_get=_get)
        pipeline = GitLabCIPipeline(client=c)
        manager = GitLabMRManager(client=c, pipeline=pipeline)
        self.assertTrue(manager.can_merge(1, 1))

    def test_can_merge_false_when_closed(self):
        def _get(url, headers):
            return {"state": "closed", "merge_status": "can_be_merged"}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_get=_get)
        manager = GitLabMRManager(client=c)
        self.assertFalse(manager.can_merge(1, 1))

    def test_can_merge_false_when_pipeline_failed(self):
        def _get(url, headers):
            if "pipelines" in url:
                return [{"id": 1, "status": "failed"}]
            return {"state": "opened", "merge_status": "can_be_merged"}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.ci_pipeline import GitLabCIPipeline
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_get=_get)
        pipeline = GitLabCIPipeline(client=c)
        manager = GitLabMRManager(client=c, pipeline=pipeline)
        self.assertFalse(manager.can_merge(1, 1))

    def test_can_merge_false_when_pipeline_running(self):
        def _get(url, headers):
            if "pipelines" in url:
                return [{"id": 1, "status": "running"}]
            return {"state": "opened", "merge_status": "can_be_merged"}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.ci_pipeline import GitLabCIPipeline
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_get=_get)
        pipeline = GitLabCIPipeline(client=c)
        manager = GitLabMRManager(client=c, pipeline=pipeline)
        self.assertFalse(manager.can_merge(1, 1))

    def test_can_merge_true_when_pipeline_passing(self):
        def _get(url, headers):
            if "pipelines" in url:
                return [{"id": 1, "status": "success"}]
            return {"state": "opened", "merge_status": "can_be_merged"}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.ci_pipeline import GitLabCIPipeline
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_get=_get)
        pipeline = GitLabCIPipeline(client=c)
        manager = GitLabMRManager(client=c, pipeline=pipeline)
        self.assertTrue(manager.can_merge(1, 1))

    def test_can_merge_false_on_client_error(self):
        from integrations.gitlab.client import GitLabClient, GitLabClientError
        from integrations.gitlab.mr_manager import GitLabMRManager

        def _get(url, headers):
            raise GitLabClientError("HTTP 404")

        c = GitLabClient("https://gitlab.com", "tok", _http_get=_get)
        manager = GitLabMRManager(client=c)
        self.assertFalse(manager.can_merge(1, 99))

    # ------------------------------------------------------------------
    # complete_merge
    # ------------------------------------------------------------------

    def test_complete_merge_raises_when_not_mergeable(self):
        def _get(url, headers):
            return {"state": "merged", "merge_status": "already_merged"}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_get=_get)
        manager = GitLabMRManager(client=c)
        with self.assertRaises(RuntimeError):
            manager.complete_merge(1, 1)

    def test_complete_merge_calls_merge_mr_when_mergeable(self):
        merge_calls = []

        def _get(url, headers):
            if "pipelines" in url:
                return [{"id": 1, "status": "success"}]
            return {"state": "opened", "merge_status": "can_be_merged"}

        def _post(url, headers, body):
            merge_calls.append(url)
            return {"state": "merged"}

        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.ci_pipeline import GitLabCIPipeline
        from integrations.gitlab.mr_manager import GitLabMRManager

        c = GitLabClient("https://gitlab.com", "tok", _http_get=_get, _http_post=_post)
        pipeline = GitLabCIPipeline(client=c)
        manager = GitLabMRManager(client=c, pipeline=pipeline)
        result = manager.complete_merge(1, 5)
        self.assertEqual(result.get("state"), "merged")
        self.assertTrue(any("merge_requests/5/merge" in u for u in merge_calls))


# ===========================================================================
# GitLabOAuthHandler tests
# ===========================================================================


class TestGitLabOAuthHandler(unittest.TestCase):
    """Tests for integrations.gitlab.oauth.GitLabOAuthHandler."""

    def setUp(self):
        from integrations.gitlab.oauth import GitLabOAuthHandler
        self.handler = GitLabOAuthHandler(
            client_id="test-client-id",
            client_secret="test-client-secret",
        )

    def test_get_authorization_url_returns_string(self):
        url = self.handler.get_authorization_url("org-1", "https://app.dev/callback")
        self.assertIsInstance(url, str)

    def test_authorization_url_contains_gitlab_oauth(self):
        url = self.handler.get_authorization_url("org-1", "https://app.dev/callback")
        self.assertIn("oauth/authorize", url)

    def test_authorization_url_contains_client_id(self):
        url = self.handler.get_authorization_url("org-1", "https://app.dev/callback")
        self.assertIn("test-client-id", url)

    def test_authorization_url_contains_state(self):
        url = self.handler.get_authorization_url("org-2", "https://app.dev/cb")
        self.assertIn("state=", url)

    def test_authorization_url_contains_redirect_uri(self):
        url = self.handler.get_authorization_url("org-1", "https://app.dev/cb")
        self.assertIn("app.dev", url)

    def test_different_orgs_get_different_states(self):
        url1 = self.handler.get_authorization_url("org-A", "https://app.dev/cb")
        url2 = self.handler.get_authorization_url("org-B", "https://app.dev/cb")
        state1 = [p for p in url1.split("&") if "state=" in p][0]
        state2 = [p for p in url2.split("&") if "state=" in p][0]
        self.assertNotEqual(state1, state2)

    def test_custom_gitlab_base_url(self):
        from integrations.gitlab.oauth import GitLabOAuthHandler
        handler = GitLabOAuthHandler(gitlab_base_url="https://my-gitlab.example.com")
        url = handler.get_authorization_url("org-1", "https://app.dev/cb")
        self.assertIn("my-gitlab.example.com", url)

    def test_custom_scopes(self):
        url = self.handler.get_authorization_url(
            "org-1", "https://app.dev/cb", scopes=["read_user"]
        )
        self.assertIn("read_user", url)

    def test_exchange_code_for_token_returns_token_dict(self):
        tokens = self.handler.exchange_code_for_token("auth-code-123", "https://cb.dev/")
        self.assertIn("access_token", tokens)
        self.assertIn("refresh_token", tokens)
        self.assertIn("token_type", tokens)
        self.assertEqual(tokens["token_type"], "Bearer")

    def test_exchange_code_expires_in_is_7200(self):
        tokens = self.handler.exchange_code_for_token("code-Y", "https://cb.dev/")
        self.assertEqual(tokens["expires_in"], 7200)

    def test_exchange_code_deterministic(self):
        t1 = self.handler.exchange_code_for_token("same-code", "https://cb.dev/")
        t2 = self.handler.exchange_code_for_token("same-code", "https://cb.dev/")
        self.assertEqual(t1["access_token"], t2["access_token"])

    def test_exchange_different_codes_give_different_tokens(self):
        t1 = self.handler.exchange_code_for_token("code-A", "https://cb.dev/")
        t2 = self.handler.exchange_code_for_token("code-B", "https://cb.dev/")
        self.assertNotEqual(t1["access_token"], t2["access_token"])

    def test_exchange_code_includes_scope(self):
        tokens = self.handler.exchange_code_for_token("code-X", "https://cb.dev/")
        self.assertIn("scope", tokens)

    def test_refresh_token_returns_new_tokens(self):
        tokens = self.handler.refresh_token("old-refresh-token")
        self.assertIn("access_token", tokens)
        self.assertIn("refresh_token", tokens)

    def test_refresh_token_returns_different_access_token(self):
        t1 = self.handler.refresh_token("refresh-A")
        t2 = self.handler.refresh_token("refresh-B")
        self.assertNotEqual(t1["access_token"], t2["access_token"])

    def test_refresh_token_expires_in_is_7200(self):
        tokens = self.handler.refresh_token("some-token")
        self.assertEqual(tokens["expires_in"], 7200)

    def test_validate_personal_access_token_returns_dict(self):
        result = self.handler.validate_personal_access_token("glpat-xxxx")
        self.assertIn("id", result)
        self.assertIn("active", result)
        self.assertTrue(result["active"])

    def test_validate_state_succeeds_for_valid_state(self):
        url = self.handler.get_authorization_url("org-validate", "https://cb/")
        state = [p.split("=", 1)[1] for p in url.split("&") if "state=" in p][0]
        result = self.handler.validate_state(state)
        self.assertTrue(result)

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
        self.handler._states["expired-state"] = {
            "org_id": "org-z",
            "created_at": time.time() - 700,  # > 600s
        }
        with self.assertRaises(ValueError):
            self.handler.validate_state("expired-state")

    def test_validate_state_with_org_id_mismatch_raises(self):
        url = self.handler.get_authorization_url("org-real", "https://cb/")
        state = [p.split("=", 1)[1] for p in url.split("&") if "state=" in p][0]
        with self.assertRaises(ValueError):
            self.handler.validate_state(state, org_id="wrong-org")

    def test_get_state_data_returns_org_id(self):
        url = self.handler.get_authorization_url("org-peek", "https://cb/")
        state = [p.split("=", 1)[1] for p in url.split("&") if "state=" in p][0]
        data = self.handler.get_state_data(state)
        self.assertEqual(data["org_id"], "org-peek")

    def test_get_state_data_unknown_state_raises(self):
        with self.assertRaises(ValueError):
            self.handler.get_state_data("nonexistent-state")


# ===========================================================================
# GitLabIntegrationConfig tests
# ===========================================================================


class TestGitLabIntegrationConfig(unittest.TestCase):
    """Tests for integrations.gitlab.config.GitLabIntegrationConfig and store helpers."""

    def setUp(self):
        from integrations.gitlab import config as gitlab_config
        gitlab_config._configs.clear()

    def test_load_from_dict_basic(self):
        from integrations.gitlab.config import GitLabIntegrationConfig
        data = {
            "org_id": "test-org",
            "gitlab_base_url": "https://gitlab.mycompany.com",
            "enabled": True,
        }
        cfg = GitLabIntegrationConfig.load_from_dict(data)
        self.assertEqual(cfg.org_id, "test-org")
        self.assertEqual(cfg.gitlab_base_url, "https://gitlab.mycompany.com")
        self.assertTrue(cfg.enabled)

    def test_load_from_dict_missing_org_id_raises(self):
        from integrations.gitlab.config import GitLabIntegrationConfig
        with self.assertRaises(ValueError):
            GitLabIntegrationConfig.load_from_dict({})

    def test_load_from_dict_empty_org_id_raises(self):
        from integrations.gitlab.config import GitLabIntegrationConfig
        with self.assertRaises(ValueError):
            GitLabIntegrationConfig.load_from_dict({"org_id": ""})

    def test_load_from_dict_defaults(self):
        from integrations.gitlab.config import GitLabIntegrationConfig
        cfg = GitLabIntegrationConfig.load_from_dict({"org_id": "org-d"})
        self.assertEqual(cfg.gitlab_base_url, "https://gitlab.com")
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.project_mappings, [])
        self.assertEqual(cfg.pipeline_rules, {})
        self.assertEqual(cfg.webhook_secret, "")
        self.assertEqual(cfg.auth_type, "oauth")

    def test_load_from_dict_auth_type_pat(self):
        from integrations.gitlab.config import GitLabIntegrationConfig
        cfg = GitLabIntegrationConfig.load_from_dict({"org_id": "org-pat", "auth_type": "pat"})
        self.assertEqual(cfg.auth_type, "pat")

    def test_load_from_dict_invalid_auth_type_raises(self):
        from integrations.gitlab.config import GitLabIntegrationConfig
        with self.assertRaises(ValueError):
            GitLabIntegrationConfig.load_from_dict({"org_id": "org-x", "auth_type": "invalid"})

    def test_load_from_dict_with_project_mappings(self):
        from integrations.gitlab.config import GitLabIntegrationConfig
        mappings = [{"gitlab_project_id": 42, "ae_project": "my-proj"}]
        cfg = GitLabIntegrationConfig.load_from_dict(
            {"org_id": "org-1", "project_mappings": mappings}
        )
        self.assertEqual(len(cfg.project_mappings), 1)

    def test_load_from_dict_with_pipeline_rules(self):
        from integrations.gitlab.config import GitLabIntegrationConfig
        rules = {"block_merge_on_failure": True, "required_stages": ["test"]}
        cfg = GitLabIntegrationConfig.load_from_dict(
            {"org_id": "org-2", "pipeline_rules": rules}
        )
        self.assertTrue(cfg.pipeline_rules["block_merge_on_failure"])

    def test_to_dict_round_trips(self):
        from integrations.gitlab.config import GitLabIntegrationConfig
        cfg = GitLabIntegrationConfig(
            org_id="org-rt",
            gitlab_base_url="https://rt.gitlab.com",
            auth_type="pat",
            enabled=True,
            webhook_secret="secret123",
        )
        d = cfg.to_dict()
        self.assertEqual(d["org_id"], "org-rt")
        self.assertEqual(d["webhook_secret"], "secret123")
        restored = GitLabIntegrationConfig.load_from_dict(d)
        self.assertEqual(restored.org_id, cfg.org_id)
        self.assertEqual(restored.enabled, cfg.enabled)
        self.assertEqual(restored.auth_type, cfg.auth_type)

    def test_save_and_load_config(self):
        from integrations.gitlab.config import (
            GitLabIntegrationConfig,
            load_config,
            save_config,
        )
        cfg = GitLabIntegrationConfig(
            org_id="org-sl",
            gitlab_base_url="https://sl.gitlab.com",
        )
        save_config(cfg)
        loaded = load_config("org-sl")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.gitlab_base_url, "https://sl.gitlab.com")

    def test_load_nonexistent_returns_none(self):
        from integrations.gitlab.config import load_config
        self.assertIsNone(load_config("does-not-exist"))

    def test_delete_config(self):
        from integrations.gitlab.config import (
            GitLabIntegrationConfig,
            delete_config,
            load_config,
            save_config,
        )
        save_config(GitLabIntegrationConfig(org_id="org-del"))
        self.assertTrue(delete_config("org-del"))
        self.assertIsNone(load_config("org-del"))

    def test_delete_nonexistent_returns_false(self):
        from integrations.gitlab.config import delete_config
        self.assertFalse(delete_config("phantom-org"))

    def test_list_configs(self):
        from integrations.gitlab.config import (
            GitLabIntegrationConfig,
            list_configs,
            save_config,
        )
        save_config(GitLabIntegrationConfig(org_id="org-A"))
        save_config(GitLabIntegrationConfig(org_id="org-B"))
        all_cfgs = list_configs()
        org_ids = {c.org_id for c in all_cfgs}
        self.assertIn("org-A", org_ids)
        self.assertIn("org-B", org_ids)


# ===========================================================================
# REST API endpoint tests
# ===========================================================================


class TestGitLabWebhookEndpoint(unittest.IsolatedAsyncioTestCase):
    """Tests for POST /api/webhooks/gitlab endpoint."""

    def setUp(self):
        from integrations.gitlab import config as gitlab_config
        gitlab_config._configs.clear()

    async def _make_request(
        self,
        body: dict,
        gitlab_token: str = "",
        org_id: str = "",
        pre_save_secret: str = "",
    ):
        from integrations.gitlab.config import GitLabIntegrationConfig, save_config
        from integrations.gitlab import config as gitlab_config

        gitlab_config._configs.clear()

        if pre_save_secret and org_id:
            save_config(
                GitLabIntegrationConfig(
                    org_id=org_id,
                    webhook_secret=pre_save_secret,
                )
            )

        from dashboard.rest_api_server import RESTAPIServer

        server = RESTAPIServer.__new__(RESTAPIServer)

        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value=body)
        mock_request.headers = {"X-Gitlab-Token": gitlab_token}
        mock_request.rel_url.query = {"org_id": org_id} if org_id else {}

        return await server.gitlab_webhook(mock_request)

    async def test_webhook_without_secret_succeeds(self):
        body = {"object_kind": "merge_request", "object_attributes": {"action": "open"}}
        resp = await self._make_request(body)
        self.assertEqual(resp.status, 200)

    async def test_webhook_with_valid_token_succeeds(self):
        body = {"object_kind": "push", "ref": "refs/heads/main", "commits": []}
        resp = await self._make_request(
            body,
            gitlab_token="my-secret",
            org_id="org-wh",
            pre_save_secret="my-secret",
        )
        self.assertEqual(resp.status, 200)

    async def test_webhook_with_invalid_token_returns_401(self):
        body = {"object_kind": "push"}
        resp = await self._make_request(
            body,
            gitlab_token="wrong-token",
            org_id="org-bad",
            pre_save_secret="real-secret",
        )
        self.assertEqual(resp.status, 401)

    async def test_webhook_with_secret_but_no_token_returns_401(self):
        body = {"object_kind": "push"}
        resp = await self._make_request(
            body,
            gitlab_token="",
            org_id="org-no-tok",
            pre_save_secret="configured-secret",
        )
        self.assertEqual(resp.status, 401)

    async def test_webhook_mr_event_returns_action(self):
        body = {
            "object_kind": "merge_request",
            "object_attributes": {
                "action": "open",
                "iid": 5,
                "title": "Feature MR",
                "state": "opened",
            },
        }
        resp = await self._make_request(body)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.body)
        self.assertEqual(data["object_kind"], "merge_request")
        self.assertEqual(data["action"], "open")

    async def test_webhook_pipeline_event_returns_status(self):
        body = {
            "object_kind": "pipeline",
            "object_attributes": {
                "id": 123,
                "status": "success",
                "ref": "main",
            },
        }
        resp = await self._make_request(body)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.body)
        self.assertEqual(data["object_kind"], "pipeline")
        self.assertEqual(data["pipeline_status"], "success")

    async def test_webhook_push_event_returns_commits_count(self):
        body = {
            "object_kind": "push",
            "ref": "refs/heads/feature/x",
            "commits": [{"id": "abc"}, {"id": "def"}],
        }
        resp = await self._make_request(body)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.body)
        self.assertEqual(data["commits"], 2)

    async def test_webhook_unknown_event_returns_ignored(self):
        body = {"object_kind": "unknown_event"}
        resp = await self._make_request(body)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.body)
        self.assertEqual(data["action"], "ignored")

    async def test_webhook_invalid_json_returns_400(self):
        from dashboard.rest_api_server import RESTAPIServer

        server = RESTAPIServer.__new__(RESTAPIServer)
        mock_request = MagicMock()
        mock_request.json = AsyncMock(side_effect=Exception("not json"))
        mock_request.headers = {}
        mock_request.rel_url.query = {}

        resp = await server.gitlab_webhook(mock_request)
        self.assertEqual(resp.status, 400)


class TestGitLabStatusEndpoint(unittest.IsolatedAsyncioTestCase):
    """Tests for GET /api/integrations/gitlab/status."""

    def setUp(self):
        from integrations.gitlab import config as gitlab_config
        gitlab_config._configs.clear()

    async def _call_status(self, org_id: str):
        from dashboard.rest_api_server import RESTAPIServer

        server = RESTAPIServer.__new__(RESTAPIServer)
        mock_request = MagicMock()
        mock_request.rel_url.query = {"org_id": org_id}
        return await server.gitlab_get_status(mock_request)

    async def test_status_no_org_id_returns_400(self):
        resp = await self._call_status("")
        self.assertEqual(resp.status, 400)

    async def test_status_unconnected_org_returns_200_not_connected(self):
        resp = await self._call_status("org-new")
        self.assertEqual(resp.status, 200)
        body = json.loads(resp.body)
        self.assertFalse(body["connected"])

    async def test_status_connected_org_returns_200_connected(self):
        from integrations.gitlab.config import GitLabIntegrationConfig, save_config

        save_config(
            GitLabIntegrationConfig(
                org_id="org-conn",
                gitlab_base_url="https://gitlab.mycompany.com",
                enabled=True,
            )
        )
        resp = await self._call_status("org-conn")
        body = json.loads(resp.body)
        self.assertTrue(body["connected"])
        self.assertTrue(body["enabled"])
        self.assertEqual(body["gitlab_base_url"], "https://gitlab.mycompany.com")

    async def test_status_includes_auth_type(self):
        from integrations.gitlab.config import GitLabIntegrationConfig, save_config

        save_config(
            GitLabIntegrationConfig(
                org_id="org-pat",
                auth_type="pat",
                enabled=True,
            )
        )
        resp = await self._call_status("org-pat")
        body = json.loads(resp.body)
        self.assertEqual(body["auth_type"], "pat")

    async def test_status_includes_project_count(self):
        from integrations.gitlab.config import GitLabIntegrationConfig, save_config

        save_config(
            GitLabIntegrationConfig(
                org_id="org-proj",
                project_mappings=[
                    {"gitlab_project_id": 1, "ae_project": "proj-a"},
                    {"gitlab_project_id": 2, "ae_project": "proj-b"},
                ],
            )
        )
        resp = await self._call_status("org-proj")
        body = json.loads(resp.body)
        self.assertEqual(body["project_count"], 2)


class TestGitLabConnectEndpoint(unittest.IsolatedAsyncioTestCase):
    """Tests for POST /api/integrations/gitlab/connect."""

    async def _call_connect(self, body: dict):
        from dashboard.rest_api_server import RESTAPIServer

        server = RESTAPIServer.__new__(RESTAPIServer)
        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value=body)
        return await server.gitlab_connect(mock_request)

    async def test_connect_returns_auth_url(self):
        resp = await self._call_connect({
            "org_id": "org-connect",
            "redirect_uri": "https://app.dev/callback",
        })
        self.assertEqual(resp.status, 200)
        body = json.loads(resp.body)
        self.assertIn("auth_url", body)
        self.assertIn("oauth/authorize", body["auth_url"])

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

    async def test_connect_with_custom_scopes(self):
        resp = await self._call_connect({
            "org_id": "org-scopes",
            "redirect_uri": "https://app.dev/cb",
            "scopes": ["read_user", "api"],
        })
        self.assertEqual(resp.status, 200)
        body = json.loads(resp.body)
        self.assertIn("auth_url", body)

    async def test_connect_invalid_json_returns_400(self):
        from dashboard.rest_api_server import RESTAPIServer

        server = RESTAPIServer.__new__(RESTAPIServer)
        mock_request = MagicMock()
        mock_request.json = AsyncMock(side_effect=Exception("bad json"))
        resp = await server.gitlab_connect(mock_request)
        self.assertEqual(resp.status, 400)


class TestGitLabCallbackEndpoint(unittest.IsolatedAsyncioTestCase):
    """Tests for GET /api/integrations/gitlab/callback."""

    def setUp(self):
        from integrations.gitlab import config as gitlab_config
        gitlab_config._configs.clear()

    async def _call_callback(self, code: str, state: str, redirect_uri: str = ""):
        from dashboard.rest_api_server import RESTAPIServer

        server = RESTAPIServer.__new__(RESTAPIServer)
        mock_request = MagicMock()
        mock_request.rel_url.query = {
            "code": code,
            "state": state,
            "redirect_uri": redirect_uri,
        }
        return await server.gitlab_callback(mock_request)

    async def test_callback_missing_code_returns_400(self):
        resp = await self._call_callback("", "some-state")
        self.assertEqual(resp.status, 400)

    async def test_callback_missing_state_returns_400(self):
        resp = await self._call_callback("code-123", "")
        self.assertEqual(resp.status, 400)

    async def test_callback_invalid_state_returns_400(self):
        resp = await self._call_callback("code-123", "invalid-state-nonce")
        self.assertEqual(resp.status, 400)

    async def test_callback_with_valid_flow(self):
        """Simulate a complete OAuth callback with pre-seeded state."""
        from integrations.gitlab.oauth import GitLabOAuthHandler

        # Pre-seed a valid state
        handler = GitLabOAuthHandler()
        url = handler.get_authorization_url("org-cb", "https://app.dev/cb")
        state = [p.split("=", 1)[1] for p in url.split("&") if "state=" in p][0]

        # Manually inject state into the server's OAuth handler via patch
        with patch(
            "integrations.gitlab.oauth.GitLabOAuthHandler",
            return_value=handler,
        ):
            from dashboard.rest_api_server import RESTAPIServer

            server = RESTAPIServer.__new__(RESTAPIServer)
            mock_request = MagicMock()
            mock_request.rel_url.query = {
                "code": "auth-code-xyz",
                "state": state,
                "redirect_uri": "https://app.dev/cb",
            }
            resp = await server.gitlab_callback(mock_request)
            # Will get 200 since the handler has the state
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.body)
            self.assertTrue(body["connected"])
            self.assertEqual(body["org_id"], "org-cb")


class TestGitLabSaveConfigEndpoint(unittest.IsolatedAsyncioTestCase):
    """Tests for POST /api/integrations/gitlab/config."""

    def setUp(self):
        from integrations.gitlab import config as gitlab_config
        gitlab_config._configs.clear()

    async def _call_save(self, body: dict):
        from dashboard.rest_api_server import RESTAPIServer

        server = RESTAPIServer.__new__(RESTAPIServer)
        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value=body)
        return await server.gitlab_save_config(mock_request)

    async def test_save_config_basic(self):
        resp = await self._call_save({
            "org_id": "org-save",
            "gitlab_base_url": "https://gitlab.mycompany.com",
            "enabled": True,
        })
        self.assertEqual(resp.status, 200)
        body = json.loads(resp.body)
        self.assertEqual(body["org_id"], "org-save")
        self.assertTrue(body["enabled"])

    async def test_save_config_no_org_id_returns_400(self):
        resp = await self._call_save({"gitlab_base_url": "https://x.gitlab.com"})
        self.assertEqual(resp.status, 400)

    async def test_save_config_does_not_return_webhook_secret(self):
        resp = await self._call_save({
            "org_id": "org-secret",
            "webhook_secret": "super-secret",
        })
        body = json.loads(resp.body)
        self.assertNotIn("webhook_secret", body)

    async def test_save_config_persists_to_store(self):
        await self._call_save({
            "org_id": "org-persist",
            "gitlab_base_url": "https://p.gitlab.com",
        })
        from integrations.gitlab.config import load_config

        cfg = load_config("org-persist")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.gitlab_base_url, "https://p.gitlab.com")

    async def test_save_config_with_project_mappings(self):
        mappings = [{"gitlab_project_id": 42, "ae_project": "test-proj"}]
        resp = await self._call_save({
            "org_id": "org-map",
            "project_mappings": mappings,
        })
        self.assertEqual(resp.status, 200)
        body = json.loads(resp.body)
        self.assertEqual(len(body["project_mappings"]), 1)

    async def test_save_config_with_pipeline_rules(self):
        rules = {"block_merge_on_failure": True}
        resp = await self._call_save({
            "org_id": "org-rules",
            "pipeline_rules": rules,
        })
        body = json.loads(resp.body)
        self.assertTrue(body["pipeline_rules"]["block_merge_on_failure"])

    async def test_save_config_invalid_auth_type_returns_400(self):
        resp = await self._call_save({
            "org_id": "org-bad-auth",
            "auth_type": "invalid-type",
        })
        self.assertEqual(resp.status, 400)

    async def test_save_config_pat_auth_type(self):
        resp = await self._call_save({
            "org_id": "org-pat",
            "auth_type": "pat",
            "enabled": True,
        })
        self.assertEqual(resp.status, 200)
        body = json.loads(resp.body)
        self.assertEqual(body["auth_type"], "pat")

    async def test_save_config_invalid_json_returns_400(self):
        from dashboard.rest_api_server import RESTAPIServer

        server = RESTAPIServer.__new__(RESTAPIServer)
        mock_request = MagicMock()
        mock_request.json = AsyncMock(side_effect=Exception("bad json"))
        resp = await server.gitlab_save_config(mock_request)
        self.assertEqual(resp.status, 400)


class TestGitLabPipelineStatusEndpoint(unittest.IsolatedAsyncioTestCase):
    """Tests for GET /api/integrations/gitlab/pipeline."""

    async def _call_pipeline(self, project_id: str, mr_iid: str):
        from dashboard.rest_api_server import RESTAPIServer

        server = RESTAPIServer.__new__(RESTAPIServer)
        mock_request = MagicMock()
        query = {}
        if project_id:
            query["project_id"] = project_id
        if mr_iid:
            query["mr_iid"] = mr_iid
        mock_request.rel_url.query = query
        return await server.gitlab_pipeline_status(mock_request)

    async def test_pipeline_missing_project_id_returns_400(self):
        resp = await self._call_pipeline("", "5")
        self.assertEqual(resp.status, 400)

    async def test_pipeline_missing_mr_iid_returns_400(self):
        resp = await self._call_pipeline("42", "")
        self.assertEqual(resp.status, 400)

    async def test_pipeline_non_integer_mr_iid_returns_400(self):
        resp = await self._call_pipeline("42", "not-a-number")
        self.assertEqual(resp.status, 400)

    async def test_pipeline_returns_200_with_summary(self):
        resp = await self._call_pipeline("42", "5")
        self.assertEqual(resp.status, 200)
        body = json.loads(resp.body)
        self.assertIn("status", body)
        self.assertIn("project_id", body)
        self.assertIn("mr_iid", body)
        self.assertEqual(body["project_id"], "42")
        self.assertEqual(body["mr_iid"], 5)

    async def test_pipeline_response_includes_web_url(self):
        resp = await self._call_pipeline("10", "3")
        body = json.loads(resp.body)
        self.assertIn("web_url", body)


# ===========================================================================
# Integration smoke tests
# ===========================================================================


class TestGitLabIntegrationSmoke(unittest.TestCase):
    """End-to-end smoke tests exercising multiple components together."""

    def test_full_mr_workflow(self):
        """Client → MRManager: create branch, MR, check pipeline."""
        from integrations.gitlab.client import GitLabClient
        from integrations.gitlab.ci_pipeline import GitLabCIPipeline
        from integrations.gitlab.mr_manager import GitLabMRManager

        branch_calls = []
        mr_calls = []

        def _post(url, headers, body):
            if "repository/branches" in url:
                branch_calls.append(body)
                return {"name": body.get("branch", "")}
            if url.endswith("/merge"):
                return {"state": "merged"}
            if "merge_requests" in url:
                mr_calls.append(body)
                return {
                    "iid": 1,
                    "title": body.get("title", ""),
                    "state": "opened",
                }
            return {}

        def _get(url, headers):
            if "pipelines" in url:
                return [{"id": 1, "status": "success"}]
            return {"state": "opened", "merge_status": "can_be_merged"}

        client = GitLabClient("https://gitlab.com", "tok", _http_get=_get, _http_post=_post)
        pipeline = GitLabCIPipeline(client=client)
        manager = GitLabMRManager(client=client, pipeline=pipeline)

        # Create feature branch
        branch = manager.create_feature_branch(42, "AI-251")
        self.assertEqual(branch, "feature/ai-251")

        # Create MR
        mr = manager.create_agent_mr(
            42, branch, "feat: AI-251 GitLab integration",
            "Adds GitLab integration", labels=["gitlab", "agent"]
        )
        self.assertEqual(mr["iid"], 1)

        # Check can_merge (pipeline passing)
        self.assertTrue(manager.can_merge(42, 1))

    def test_oauth_full_flow(self):
        """OAuth: URL generation → state validation → token exchange → refresh."""
        from integrations.gitlab.oauth import GitLabOAuthHandler

        handler = GitLabOAuthHandler()
        url = handler.get_authorization_url("smoke-org", "https://app.dev/cb")
        state = [p.split("=", 1)[1] for p in url.split("&") if "state=" in p][0]

        # Peek at state data without consuming
        data = handler.get_state_data(state)
        self.assertEqual(data["org_id"], "smoke-org")

        # Validate state
        result = handler.validate_state(state)
        self.assertTrue(result)

        # Exchange code
        tokens = handler.exchange_code_for_token("smoke-code", "https://app.dev/cb")
        self.assertIn("access_token", tokens)

        # Refresh
        refreshed = handler.refresh_token(tokens["refresh_token"])
        self.assertIn("access_token", refreshed)

    def test_ci_pipeline_gating_scenario(self):
        """Pipeline gating: verify all terminal states."""
        from integrations.gitlab.ci_pipeline import GitLabCIPipeline

        helper = GitLabCIPipeline()

        scenarios = [
            ("success", True, False, False),
            ("failed", False, True, False),
            ("canceled", False, True, False),
            ("running", False, False, True),
            ("pending", False, False, True),
            ("created", False, False, True),
            ("skipped", False, False, False),
        ]
        for status, passing, failed, running in scenarios:
            p = {"status": status}
            self.assertEqual(
                helper.is_pipeline_passing(p), passing,
                f"is_pipeline_passing({status!r}) should be {passing}",
            )
            self.assertEqual(
                helper.is_pipeline_failed(p), failed,
                f"is_pipeline_failed({status!r}) should be {failed}",
            )
            self.assertEqual(
                helper.is_pipeline_running(p), running,
                f"is_pipeline_running({status!r}) should be {running}",
            )

    def test_config_round_trip(self):
        """Config: save → load → delete."""
        from integrations.gitlab.config import (
            GitLabIntegrationConfig,
            delete_config,
            load_config,
            save_config,
        )
        from integrations.gitlab import config as gitlab_config

        gitlab_config._configs.clear()

        cfg = GitLabIntegrationConfig(
            org_id="smoke-config",
            gitlab_base_url="https://smoke.gitlab.com",
            auth_type="oauth",
            project_mappings=[{"gitlab_project_id": 1, "ae_project": "smoke"}],
            pipeline_rules={"block_merge_on_failure": True},
            enabled=True,
            webhook_secret="smoke-secret",
        )
        save_config(cfg)
        loaded = load_config("smoke-config")
        self.assertEqual(loaded.org_id, "smoke-config")
        self.assertEqual(loaded.webhook_secret, "smoke-secret")
        self.assertEqual(len(loaded.project_mappings), 1)
        self.assertTrue(loaded.pipeline_rules["block_merge_on_failure"])
        delete_config("smoke-config")
        self.assertIsNone(load_config("smoke-config"))


# ===========================================================================
# Agent definitions tests
# ===========================================================================

# Check whether the claude_agent_sdk is available (it's not in the test
# environment) so we can conditionally skip tests that require it.
try:
    import claude_agent_sdk  # noqa: F401
    _CLAUDE_SDK_AVAILABLE = True
except ImportError:
    _CLAUDE_SDK_AVAILABLE = False

_skip_if_no_sdk = unittest.skipUnless(
    _CLAUDE_SDK_AVAILABLE,
    "claude_agent_sdk not installed in test environment",
)


class TestGitLabAgentDefinition(unittest.TestCase):
    """Tests for the GitLab agent in agents/definitions.py."""

    @_skip_if_no_sdk
    def test_gitlab_agent_exists_in_definitions(self):
        from agents.definitions import AGENT_DEFINITIONS
        self.assertIn("gitlab", AGENT_DEFINITIONS)

    @_skip_if_no_sdk
    def test_gitlab_agent_has_description(self):
        from agents.definitions import AGENT_DEFINITIONS
        agent = AGENT_DEFINITIONS["gitlab"]
        self.assertIn("GitLab", agent.description)

    @_skip_if_no_sdk
    def test_gitlab_agent_is_exported(self):
        from agents.definitions import GITLAB_AGENT
        self.assertIsNotNone(GITLAB_AGENT)

    @_skip_if_no_sdk
    def test_gitlab_agent_description_mentions_mr(self):
        from agents.definitions import GITLAB_AGENT
        self.assertIn("MR", GITLAB_AGENT.description)

    @_skip_if_no_sdk
    def test_gitlab_agent_description_mentions_pipeline(self):
        from agents.definitions import GITLAB_AGENT
        self.assertIn("pipeline", GITLAB_AGENT.description.lower())

    def test_gitlab_entry_in_default_models(self):
        """Verify 'gitlab' appears in definitions source (without importing SDK)."""
        import ast
        import pathlib

        definitions_path = pathlib.Path(
            "/Users/bkh223/Documents/GitHub/agent-engineers/generations/"
            "agent-dashboard/.worktrees/coding-0/agents/definitions.py"
        )
        source = definitions_path.read_text()
        self.assertIn('"gitlab"', source)
        self.assertIn("GITLAB_AGENT", source)
        self.assertIn("GitLab integration agent", source)


if __name__ == "__main__":
    unittest.main()
