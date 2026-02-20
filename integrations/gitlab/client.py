"""GitLab REST API client (AI-251).

Provides a thin wrapper around the GitLab REST API v4.
All HTTP calls are mock-friendly — the client accepts custom
``_http_get`` / ``_http_post`` / ``_http_put`` callables for testing.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class GitLabClientError(Exception):
    """Raised when a GitLab API call fails."""


class GitLabClient:
    """Client for the GitLab REST API v4.

    Args:
        base_url: GitLab instance base URL, e.g. ``https://gitlab.com``
        auth_token: Personal access token or OAuth 2.0 bearer token.
        _http_get: Optional injectable HTTP GET callable (for testing).
            Signature: ``(url, headers) -> dict``
        _http_post: Optional injectable HTTP POST callable (for testing).
            Signature: ``(url, headers, body) -> dict``
        _http_put: Optional injectable HTTP PUT callable (for testing).
            Signature: ``(url, headers, body) -> dict``
    """

    def __init__(
        self,
        base_url: str,
        auth_token: str,
        _http_get: Optional[Callable] = None,
        _http_post: Optional[Callable] = None,
        _http_put: Optional[Callable] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self._http_get = _http_get or self._default_http_get
        self._http_post = _http_post or self._default_http_post
        self._http_put = _http_put or self._default_http_put

    # ------------------------------------------------------------------
    # Default HTTP implementations (use urllib; no third-party deps)
    # ------------------------------------------------------------------

    def _default_http_get(self, url: str, headers: Dict[str, str]) -> Any:
        """Perform an HTTP GET using urllib."""
        import json
        import urllib.error
        import urllib.request

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise GitLabClientError(f"HTTP {exc.code} GET {url}") from exc
        except Exception as exc:
            raise GitLabClientError(f"GET {url} failed: {exc}") from exc

    def _default_http_post(
        self, url: str, headers: Dict[str, str], body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform an HTTP POST using urllib."""
        import json
        import urllib.error
        import urllib.request

        data = json.dumps(body).encode()
        headers = {**headers, "Content-Type": "application/json"}
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise GitLabClientError(f"HTTP {exc.code} POST {url}") from exc
        except Exception as exc:
            raise GitLabClientError(f"POST {url} failed: {exc}") from exc

    def _default_http_put(
        self, url: str, headers: Dict[str, str], body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform an HTTP PUT using urllib."""
        import json
        import urllib.error
        import urllib.request

        data = json.dumps(body).encode()
        headers = {**headers, "Content-Type": "application/json"}
        req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise GitLabClientError(f"HTTP {exc.code} PUT {url}") from exc
        except Exception as exc:
            raise GitLabClientError(f"PUT {url} failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Accept": "application/json",
        }

    def _api(self, path: str) -> str:
        return f"{self.base_url}/api/v4/{path.lstrip('/')}"

    def _project_api(self, project_id: Any, path: str = "") -> str:
        suffix = f"/{path.lstrip('/')}" if path else ""
        return self._api(f"projects/{project_id}{suffix}")

    # ------------------------------------------------------------------
    # Branch operations
    # ------------------------------------------------------------------

    def create_branch(
        self, project_id: Any, branch_name: str, ref: str = "main"
    ) -> Dict[str, Any]:
        """Create a new branch in a GitLab project.

        Args:
            project_id: GitLab project ID or URL-encoded path.
            branch_name: Name of the new branch.
            ref: Source branch or commit SHA (default: ``'main'``).

        Returns:
            Branch dict as returned by the GitLab API.

        Raises:
            GitLabClientError: On API error.
        """
        url = self._project_api(project_id, "repository/branches")
        body = {"branch": branch_name, "ref": ref}
        logger.debug("POST create branch %s from %s in project %s", branch_name, ref, project_id)
        return self._http_post(url, self._headers(), body)

    # ------------------------------------------------------------------
    # Commit operations
    # ------------------------------------------------------------------

    def create_commit(
        self,
        project_id: Any,
        branch: str,
        commit_message: str,
        actions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create a commit with file actions in a GitLab project.

        Args:
            project_id: GitLab project ID or URL-encoded path.
            branch: Branch to commit to.
            commit_message: Commit message.
            actions: List of file action dicts.  Each action has:
                ``action`` (``'create'``, ``'update'``, ``'delete'``),
                ``file_path``, and optionally ``content``.

        Returns:
            Commit dict as returned by the GitLab API.

        Raises:
            GitLabClientError: On API error.
        """
        url = self._project_api(project_id, "repository/commits")
        body = {
            "branch": branch,
            "commit_message": commit_message,
            "actions": actions,
        }
        logger.debug(
            "POST create commit on branch %s in project %s (%d actions)",
            branch, project_id, len(actions),
        )
        return self._http_post(url, self._headers(), body)

    # ------------------------------------------------------------------
    # Merge Request operations
    # ------------------------------------------------------------------

    def create_merge_request(
        self,
        project_id: Any,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str = "",
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a Merge Request in a GitLab project.

        Args:
            project_id: GitLab project ID or URL-encoded path.
            source_branch: Feature branch (source).
            target_branch: Target branch (e.g. ``'main'``).
            title: MR title.
            description: MR description (Markdown supported).
            labels: Optional list of label names.

        Returns:
            MR dict as returned by the GitLab API.

        Raises:
            GitLabClientError: On API error.
        """
        url = self._project_api(project_id, "merge_requests")
        body: Dict[str, Any] = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description,
        }
        if labels:
            body["labels"] = ",".join(labels)
        logger.debug(
            "POST create MR '%s' from %s → %s in project %s",
            title, source_branch, target_branch, project_id,
        )
        return self._http_post(url, self._headers(), body)

    def assign_mr_reviewer(
        self, project_id: Any, mr_iid: int, reviewer_ids: List[int]
    ) -> Dict[str, Any]:
        """Assign reviewers to a Merge Request.

        Args:
            project_id: GitLab project ID or URL-encoded path.
            mr_iid: MR internal ID (iid).
            reviewer_ids: List of GitLab user IDs to assign as reviewers.

        Returns:
            Updated MR dict.

        Raises:
            GitLabClientError: On API error.
        """
        url = self._project_api(project_id, f"merge_requests/{mr_iid}")
        body = {"reviewer_ids": reviewer_ids}
        logger.debug(
            "PUT assign reviewers %s to MR !%d in project %s",
            reviewer_ids, mr_iid, project_id,
        )
        return self._http_put(url, self._headers(), body)

    def merge_mr(
        self,
        project_id: Any,
        mr_iid: int,
        merge_commit_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Merge an approved Merge Request.

        Args:
            project_id: GitLab project ID or URL-encoded path.
            mr_iid: MR internal ID (iid).
            merge_commit_message: Optional custom merge commit message.

        Returns:
            Merged MR dict.

        Raises:
            GitLabClientError: On API error.
        """
        url = self._project_api(project_id, f"merge_requests/{mr_iid}/merge")
        body: Dict[str, Any] = {}
        if merge_commit_message:
            body["merge_commit_message"] = merge_commit_message
        logger.debug("POST merge MR !%d in project %s", mr_iid, project_id)
        return self._http_post(url, self._headers(), body)

    def get_mr(self, project_id: Any, mr_iid: int) -> Dict[str, Any]:
        """Fetch a Merge Request by its internal ID.

        Args:
            project_id: GitLab project ID or URL-encoded path.
            mr_iid: MR internal ID (iid).

        Returns:
            MR dict as returned by the GitLab API.

        Raises:
            GitLabClientError: On API error.
        """
        url = self._project_api(project_id, f"merge_requests/{mr_iid}")
        logger.debug("GET MR !%d in project %s", mr_iid, project_id)
        return self._http_get(url, self._headers())

    # ------------------------------------------------------------------
    # Pipeline operations
    # ------------------------------------------------------------------

    def get_pipeline_status(
        self, project_id: Any, pipeline_id: int
    ) -> Dict[str, Any]:
        """Fetch the status of a CI/CD pipeline.

        Args:
            project_id: GitLab project ID or URL-encoded path.
            pipeline_id: Pipeline ID.

        Returns:
            Pipeline dict as returned by the GitLab API.

        Raises:
            GitLabClientError: On API error.
        """
        url = self._project_api(project_id, f"pipelines/{pipeline_id}")
        logger.debug("GET pipeline %d in project %s", pipeline_id, project_id)
        return self._http_get(url, self._headers())

    def list_mr_pipelines(
        self, project_id: Any, mr_iid: int
    ) -> List[Dict[str, Any]]:
        """List CI/CD pipelines associated with a Merge Request.

        Args:
            project_id: GitLab project ID or URL-encoded path.
            mr_iid: MR internal ID (iid).

        Returns:
            List of pipeline dicts.

        Raises:
            GitLabClientError: On API error.
        """
        url = self._project_api(project_id, f"merge_requests/{mr_iid}/pipelines")
        logger.debug("GET pipelines for MR !%d in project %s", mr_iid, project_id)
        result = self._http_get(url, self._headers())
        # GitLab returns a list directly for this endpoint
        if isinstance(result, list):
            return result
        return []
