#!/usr/bin/env python3
"""
Resilient Jira REST API Client
================================

Drop-in replacement for the original JiraClient with self-healing:

- OAuth 2.0 with auto-refresh (primary) + Basic Auth fallback
- Circuit breaker to prevent cascading failures
- Operation queue to buffer writes during outages
- Background health monitor for proactive recovery

Usage (unchanged from original):
    from scripts.jira_client import JiraClient

    jira = JiraClient()
    issue = jira.get_issue("KAN-71")
    jira.transition_by_name("KAN-71", "In Progress")
"""

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Optional

try:
    from scripts.jira_auth import JiraAuthManager
    from scripts.jira_circuit_breaker import (
        CircuitBreaker,
        CircuitState,
        JiraHealthMonitor,
        OperationQueue,
    )
except ImportError:
    from jira_auth import JiraAuthManager
    from jira_circuit_breaker import (
        CircuitBreaker,
        CircuitState,
        JiraHealthMonitor,
        OperationQueue,
    )

logger = logging.getLogger(__name__)

# Methods that are safe to queue during outages
WRITE_METHODS = {"POST", "PUT", "DELETE"}
# Paths that should NOT be queued (search results go stale)
NO_QUEUE_PATHS = {"/rest/api/3/search/jql"}


class JiraCircuitOpenError(Exception):
    """Raised when the circuit breaker is open and the request cannot proceed."""
    pass


# ---------------------------------------------------------------------------
# _BasicJiraClient — the actual HTTP layer (renamed from original JiraClient)
# ---------------------------------------------------------------------------


class _BasicJiraClient:
    """Low-level Jira REST API client. Uses JiraAuthManager for auth."""

    def __init__(self, auth_manager: JiraAuthManager):
        self._auth_manager = auth_manager
        import os
        self.project_key = os.environ.get("JIRA_PROJECT_KEY", "KAN")

    def _request(
        self, method: str, path: str, body: Optional[dict] = None
    ) -> Optional[dict]:
        """Make an authenticated request to the Jira REST API."""
        base_url = self._auth_manager.get_base_url()
        url = f"{base_url}{path}"
        data = json.dumps(body).encode() if body else None
        headers = self._auth_manager.get_auth_headers()

        req = urllib.request.Request(
            url, data=data, method=method, headers=headers,
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 204:
                    return None
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            logger.error(
                f"Jira API error {e.code} on {method} {path}: {error_body[:500]}"
            )
            raise

    # -----------------------------------------------------------------
    # Issue queries
    # -----------------------------------------------------------------

    def get_issue(self, key: str) -> dict:
        """Fetch full ticket details. Returns a plain dict."""
        data = self._request("GET", f"/rest/api/3/issue/{key}")
        fields = data["fields"]

        description = ""
        if fields.get("description"):
            description = self._adf_to_text(fields["description"])

        test_steps = ""
        if "test steps" in description.lower():
            parts = re.split(
                r"(?i)test\s*steps?\s*:?\s*", description, maxsplit=1
            )
            if len(parts) > 1:
                test_steps = parts[1].strip()

        return {
            "key": key,
            "title": fields.get("summary", ""),
            "description": description,
            "test_steps": test_steps,
            "labels": [lbl for lbl in fields.get("labels", [])],
            "status": fields.get("status", {}).get("name", ""),
        }

    def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        fields: Optional[list[str]] = None,
    ) -> list[dict]:
        """Search for issues using JQL (POST /rest/api/3/search/jql)."""
        body: dict = {"jql": jql, "maxResults": max_results}
        if fields:
            body["fields"] = fields

        data = self._request("POST", "/rest/api/3/search/jql", body)
        if not data or "issues" not in data:
            return []
        return data["issues"]

    def get_todo_tickets(
        self, exclude_labels: Optional[list[str]] = None
    ) -> list[dict]:
        """Query for unclaimed To Do tickets."""
        jql = f'project={self.project_key} AND status="To Do"'
        if exclude_labels:
            for label in exclude_labels:
                jql += f' AND labels != "{label}"'
        jql += ' AND summary !~ "META"'

        issues = self.search_issues(
            jql, max_results=20,
            fields=["summary", "status", "labels", "description"],
        )
        return [
            {
                "key": issue["key"],
                "title": issue["fields"].get("summary", ""),
                "labels": issue["fields"].get("labels", []),
                "status": issue["fields"].get("status", {}).get("name", ""),
            }
            for issue in issues
        ]

    def get_review_tickets(
        self, exclude_labels: Optional[list[str]] = None
    ) -> list[dict]:
        """Query for tickets in Review status awaiting peer review."""
        jql = f'project={self.project_key} AND status="Review"'
        if exclude_labels:
            for label in exclude_labels:
                jql += f' AND labels != "{label}"'

        issues = self.search_issues(
            jql, max_results=20,
            fields=["summary", "status", "labels", "description"],
        )
        return [
            {
                "key": issue["key"],
                "title": issue["fields"].get("summary", ""),
                "labels": issue["fields"].get("labels", []),
                "status": issue["fields"].get("status", {}).get("name", ""),
            }
            for issue in issues
        ]

    # -----------------------------------------------------------------
    # Transitions (dynamic discovery)
    # -----------------------------------------------------------------

    def get_transitions(self, key: str) -> list[dict]:
        """Get available transitions for an issue."""
        data = self._request("GET", f"/rest/api/3/issue/{key}/transitions")
        return data.get("transitions", [])

    def transition(self, key: str, transition_id: str) -> None:
        """Transition an issue using a known transition ID."""
        self._request(
            "POST",
            f"/rest/api/3/issue/{key}/transitions",
            {"transition": {"id": transition_id}},
        )
        logger.info(f"Transitioned {key} via transition {transition_id}")

    def transition_by_name(self, key: str, target_status: str) -> bool:
        """Transition to a target status by looking up available transitions."""
        transitions = self.get_transitions(key)
        target_lower = target_status.lower()

        for t in transitions:
            to_status = t.get("to", {}).get("name", "")
            if to_status.lower() == target_lower:
                self.transition(key, t["id"])
                logger.info(
                    f"Transitioned {key} to '{to_status}' (transition id={t['id']})"
                )
                return True

        available = [
            f"{t['id']}:{t.get('to', {}).get('name', '')}" for t in transitions
        ]
        logger.warning(
            f"No transition to '{target_status}' found for {key}. "
            f"Available: {available}"
        )
        return False

    # -----------------------------------------------------------------
    # Labels
    # -----------------------------------------------------------------

    def add_label(self, key: str, label: str) -> None:
        """Add a label to an issue."""
        self._request(
            "PUT",
            f"/rest/api/3/issue/{key}",
            {"update": {"labels": [{"add": label}]}},
        )
        logger.info(f"Added label '{label}' to {key}")

    def remove_label(self, key: str, label: str) -> None:
        """Remove a label from an issue."""
        self._request(
            "PUT",
            f"/rest/api/3/issue/{key}",
            {"update": {"labels": [{"remove": label}]}},
        )
        logger.info(f"Removed label '{label}' from {key}")

    # -----------------------------------------------------------------
    # Comments
    # -----------------------------------------------------------------

    def add_comment(self, key: str, body_text: str) -> None:
        """Add a comment to an issue."""
        self._request(
            "POST",
            f"/rest/api/3/issue/{key}/comment",
            {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": body_text}],
                        }
                    ],
                }
            },
        )
        logger.info(f"Added comment to {key}")

    # -----------------------------------------------------------------
    # Claiming (for dispatch)
    # -----------------------------------------------------------------

    def claim_ticket(self, key: str, provider: str) -> bool:
        """Claim a ticket: add worker label + transition to In Progress."""
        label = f"worker:{provider}"
        try:
            self.add_label(key, label)
            self.transition_by_name(key, "In Progress")
            logger.info(f"Claimed {key} for {provider}")
            return True
        except Exception as e:
            logger.error(f"Failed to claim {key} for {provider}: {e}")
            return False

    def unclaim_ticket(self, key: str, provider: str) -> None:
        """Release a claimed ticket back to To Do."""
        label = f"worker:{provider}"
        try:
            self.remove_label(key, label)
        except Exception:
            pass
        try:
            self.transition_by_name(key, "To Do")
        except Exception:
            pass
        logger.info(f"Released {key} from {provider}")

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _adf_to_text(adf: dict) -> str:
        """Convert Atlassian Document Format to plain text."""
        if isinstance(adf, str):
            return adf
        if not isinstance(adf, dict):
            return str(adf)

        text_parts = []
        for node in adf.get("content", []):
            node_type = node.get("type", "")
            if node_type == "paragraph":
                for inline in node.get("content", []):
                    if inline.get("type") == "text":
                        text_parts.append(inline.get("text", ""))
                text_parts.append("\n")
            elif node_type in ("bulletList", "orderedList"):
                for item in node.get("content", []):
                    text_parts.append(
                        "- " + _BasicJiraClient._adf_to_text(item).strip() + "\n"
                    )
            elif node_type == "heading":
                for inline in node.get("content", []):
                    if inline.get("type") == "text":
                        text_parts.append(inline.get("text", "") + "\n")
            elif node_type == "codeBlock":
                for inline in node.get("content", []):
                    if inline.get("type") == "text":
                        text_parts.append(inline.get("text", "") + "\n")
            else:
                text_parts.append(_BasicJiraClient._adf_to_text(node))

        return "".join(text_parts)


# ---------------------------------------------------------------------------
# JiraClient — resilient wrapper (same public interface)
# ---------------------------------------------------------------------------


class JiraClient:
    """Resilient Jira client with circuit breaker, auth management, and self-healing.

    Drop-in replacement: all existing `from scripts.jira_client import JiraClient`
    imports continue to work unchanged.
    """

    def __init__(self, auto_monitor: bool = False):
        self._auth_manager = JiraAuthManager()
        self._basic = _BasicJiraClient(self._auth_manager)
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=3, recovery_timeout=30.0, max_backoff=600.0
        )
        self._operation_queue = OperationQueue(max_size=100)
        self._health_monitor = JiraHealthMonitor(
            self._auth_manager, check_interval=60.0
        )

        # Wire recovery: when health monitor detects recovery, close circuit + drain queue
        self._health_monitor.on_recovery(self._on_recovery)

        # Expose project_key for workers that access it directly
        self.project_key = self._basic.project_key

        if auto_monitor:
            self.start_monitor()

    # -----------------------------------------------------------------
    # Resilient call wrapper
    # -----------------------------------------------------------------

    def _resilient_call(self, method_name: str, *args, **kwargs):
        """Wrap a _BasicJiraClient method call with circuit breaker logic.

        1. Check circuit breaker
        2. Try the call
        3. On 401: invalidate token, retry once
        4. On success: record success
        5. On failure: record failure, maybe queue if it's a write
        """
        if not self._circuit_breaker.can_execute():
            raise JiraCircuitOpenError(
                f"Jira circuit breaker is OPEN. Call to {method_name} rejected."
            )

        method = getattr(self._basic, method_name)

        try:
            result = method(*args, **kwargs)
            self._circuit_breaker.record_success()
            return result
        except urllib.error.HTTPError as e:
            if e.code == 401:
                # Auth expired — try refreshing and retrying once
                logger.info(
                    f"Got 401 on {method_name}, attempting token refresh..."
                )
                self._auth_manager.invalidate_token()
                try:
                    result = method(*args, **kwargs)
                    self._circuit_breaker.record_success()
                    return result
                except Exception as retry_err:
                    self._circuit_breaker.record_failure(retry_err)
                    raise
            else:
                self._circuit_breaker.record_failure(e)
                raise
        except Exception as e:
            self._circuit_breaker.record_failure(e)
            raise

    def _resilient_call_or_queue(
        self, method_name: str, http_method: str, path: str,
        *args, **kwargs
    ):
        """Like _resilient_call but queues write operations when circuit is open."""
        try:
            return self._resilient_call(method_name, *args, **kwargs)
        except JiraCircuitOpenError:
            if http_method in WRITE_METHODS and path not in NO_QUEUE_PATHS:
                # Queue the raw HTTP operation for replay on recovery
                body = kwargs.get("body") or (args[0] if args else None)
                self._operation_queue.enqueue(http_method, path, body)
                logger.info(
                    f"Queued {http_method} {path} (circuit open, "
                    f"{self._operation_queue.size} in queue)"
                )
                return None
            raise

    # -----------------------------------------------------------------
    # Recovery
    # -----------------------------------------------------------------

    def _on_recovery(self) -> None:
        """Called when health monitor detects Jira is back."""
        self._circuit_breaker.reset()
        self._drain_queue()

    def _drain_queue(self) -> None:
        """Replay all queued write operations."""
        ops = self._operation_queue.drain()
        if not ops:
            return
        logger.info(f"Replaying {len(ops)} queued operations...")
        for op in ops:
            try:
                self._basic._request(op.method, op.path, op.body)
                logger.info(f"Replayed {op.method} {op.path}")
            except Exception as e:
                logger.error(f"Failed to replay {op.method} {op.path}: {e}")

    # -----------------------------------------------------------------
    # Health + monitoring
    # -----------------------------------------------------------------

    def health_check(self) -> bool:
        """Probe Jira connectivity (GET /rest/api/3/myself)."""
        try:
            data = self._basic._request("GET", "/rest/api/3/myself")
            if data:
                self._circuit_breaker.record_success()
                return True
            return False
        except Exception as e:
            self._circuit_breaker.record_failure(e)
            return False

    def start_monitor(self) -> None:
        """Start the background health monitor daemon."""
        self._health_monitor.start()

    def stop_monitor(self) -> None:
        """Stop the background health monitor."""
        self._health_monitor.stop()

    # -----------------------------------------------------------------
    # Public API — delegates to _BasicJiraClient with resilience
    # -----------------------------------------------------------------

    def get_issue(self, key: str) -> dict:
        return self._resilient_call("get_issue", key)

    def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        fields: Optional[list[str]] = None,
    ) -> list[dict]:
        return self._resilient_call("search_issues", jql, max_results, fields)

    def get_todo_tickets(
        self, exclude_labels: Optional[list[str]] = None
    ) -> list[dict]:
        return self._resilient_call("get_todo_tickets", exclude_labels)

    def get_review_tickets(
        self, exclude_labels: Optional[list[str]] = None
    ) -> list[dict]:
        return self._resilient_call("get_review_tickets", exclude_labels)

    def get_transitions(self, key: str) -> list[dict]:
        return self._resilient_call("get_transitions", key)

    def transition(self, key: str, transition_id: str) -> None:
        path = f"/rest/api/3/issue/{key}/transitions"
        self._resilient_call_or_queue(
            "transition", "POST", path, key, transition_id
        )

    def transition_by_name(self, key: str, target_status: str) -> bool:
        return self._resilient_call("transition_by_name", key, target_status)

    def add_label(self, key: str, label: str) -> None:
        path = f"/rest/api/3/issue/{key}"
        self._resilient_call_or_queue("add_label", "PUT", path, key, label)

    def remove_label(self, key: str, label: str) -> None:
        path = f"/rest/api/3/issue/{key}"
        self._resilient_call_or_queue("remove_label", "PUT", path, key, label)

    def add_comment(self, key: str, body_text: str) -> None:
        path = f"/rest/api/3/issue/{key}/comment"
        self._resilient_call_or_queue(
            "add_comment", "POST", path, key, body_text
        )

    def claim_ticket(self, key: str, provider: str) -> bool:
        return self._resilient_call("claim_ticket", key, provider)

    def unclaim_ticket(self, key: str, provider: str) -> None:
        self._resilient_call("unclaim_ticket", key, provider)
