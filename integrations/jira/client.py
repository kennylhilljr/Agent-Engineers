"""Jira REST API client (AI-250).

Provides a thin wrapper around the Atlassian Jira REST API v3.
All HTTP calls are mocked-friendly — the client accepts a custom
``_http_get`` / ``_http_post`` / ``_http_put`` callable for testing.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Sentinel for default http callables (replaced in tests via dependency injection)
_UNSET = object()


class JiraClientError(Exception):
    """Raised when a Jira API call fails."""


class JiraClient:
    """Client for the Atlassian Jira REST API v3.

    Args:
        base_url: Jira cloud base URL, e.g. ``https://myorg.atlassian.net``
        auth_token: Bearer access token obtained from OAuth 2.0 flow.
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

    def _default_http_get(self, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Perform an HTTP GET using urllib."""
        import urllib.request
        import urllib.error

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                import json
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise JiraClientError(f"HTTP {exc.code} GET {url}") from exc
        except Exception as exc:
            raise JiraClientError(f"GET {url} failed: {exc}") from exc

    def _default_http_post(
        self, url: str, headers: Dict[str, str], body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform an HTTP POST using urllib."""
        import json
        import urllib.request
        import urllib.error

        data = json.dumps(body).encode()
        headers = {**headers, "Content-Type": "application/json"}
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise JiraClientError(f"HTTP {exc.code} POST {url}") from exc
        except Exception as exc:
            raise JiraClientError(f"POST {url} failed: {exc}") from exc

    def _default_http_put(
        self, url: str, headers: Dict[str, str], body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform an HTTP PUT using urllib."""
        import json
        import urllib.request
        import urllib.error

        data = json.dumps(body).encode()
        headers = {**headers, "Content-Type": "application/json"}
        req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise JiraClientError(f"HTTP {exc.code} PUT {url}") from exc
        except Exception as exc:
            raise JiraClientError(f"PUT {url} failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Accept": "application/json",
        }

    def _api(self, path: str) -> str:
        return f"{self.base_url}/rest/api/3/{path.lstrip('/')}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """Fetch issue details from Jira.

        Args:
            issue_key: Jira issue key, e.g. ``PROJECT-123``

        Returns:
            Issue dict as returned by the Jira API.

        Raises:
            JiraClientError: On API error.
        """
        url = self._api(f"issue/{quote(issue_key, safe='')}")
        logger.debug("GET Jira issue %s", issue_key)
        return self._http_get(url, self._headers())

    def transition_issue(self, issue_key: str, transition_id: str) -> None:
        """Change the status of a Jira issue.

        Args:
            issue_key: Jira issue key, e.g. ``PROJECT-123``
            transition_id: Jira transition ID (from ``get_transitions``).

        Raises:
            JiraClientError: On API error.
        """
        url = self._api(f"issue/{quote(issue_key, safe='')}/transitions")
        body = {"transition": {"id": str(transition_id)}}
        logger.debug("POST transition %s on issue %s", transition_id, issue_key)
        self._http_post(url, self._headers(), body)

    def add_comment(self, issue_key: str, comment_body: str) -> Dict[str, Any]:
        """Post a comment on a Jira issue.

        Args:
            issue_key: Jira issue key.
            comment_body: Plain-text comment content.

        Returns:
            Created comment dict.

        Raises:
            JiraClientError: On API error.
        """
        url = self._api(f"issue/{quote(issue_key, safe='')}/comment")
        body = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment_body}],
                    }
                ],
            }
        }
        logger.debug("POST comment on issue %s", issue_key)
        return self._http_post(url, self._headers(), body)

    def update_story_points(self, issue_key: str, points: int) -> None:
        """Update the story points / story point estimate field on an issue.

        Jira Cloud uses customfield_10016 (story_points) by default, but
        this may vary per instance.  We attempt both common field names.

        Args:
            issue_key: Jira issue key.
            points: Story point estimate (integer).

        Raises:
            JiraClientError: On API error.
        """
        url = self._api(f"issue/{quote(issue_key, safe='')}")
        body = {
            "fields": {
                "story_points": points,
                "customfield_10016": points,
            }
        }
        logger.debug("PUT story points %d on issue %s", points, issue_key)
        self._http_put(url, self._headers(), body)

    def get_sprint_issues(
        self,
        project_key: str,
        sprint_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return issues in a project (optionally filtered to a sprint).

        Uses JQL to search for issues.

        Args:
            project_key: Jira project key, e.g. ``PROJ``.
            sprint_name: Optional sprint name to filter by.

        Returns:
            List of issue dicts.

        Raises:
            JiraClientError: On API error.
        """
        jql = f"project = {project_key}"
        if sprint_name:
            jql += f' AND sprint = "{sprint_name}"'
        url = self._api(f"search?jql={quote(jql)}&maxResults=100")
        logger.debug("GET sprint issues for %s sprint=%s", project_key, sprint_name)
        result = self._http_get(url, self._headers())
        return result.get("issues", [])

    def get_transitions(self, issue_key: str) -> List[Dict[str, Any]]:
        """Return the available status transitions for an issue.

        Args:
            issue_key: Jira issue key.

        Returns:
            List of transition dicts, each with ``id`` and ``name``.

        Raises:
            JiraClientError: On API error.
        """
        url = self._api(f"issue/{quote(issue_key, safe='')}/transitions")
        logger.debug("GET transitions for issue %s", issue_key)
        result = self._http_get(url, self._headers())
        return result.get("transitions", [])
