#!/usr/bin/env python3
"""
Linear GraphQL API Client
==========================

Direct GraphQL client for Linear issue tracking.
No external dependencies beyond Python stdlib.

Usage as CLI:
    python scripts/linear_client.py list-teams
    python scripts/linear_client.py create-issue --team-id <id> --title "..."

Usage as library:
    from scripts.linear_client import LinearClient
    client = LinearClient()
    teams = client.list_teams()
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

LINEAR_API_URL = "https://api.linear.app/graphql"

# Priority mapping: Linear uses 0-4 numeric values
PRIORITY_MAP = {
    "none": 0,
    "urgent": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
}

PRIORITY_REVERSE = {v: k for k, v in PRIORITY_MAP.items()}


class LinearAPIError(Exception):
    """Raised when the Linear API returns an error."""

    def __init__(self, message: str, errors: list | None = None):
        super().__init__(message)
        self.errors = errors or []


class LinearClient:
    """Direct GraphQL client for the Linear API.

    Auth: uses LINEAR_API_KEY env var as a Bearer token.
    All methods return plain dicts/lists suitable for JSON serialization.
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("LINEAR_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "LINEAR_API_KEY environment variable not set.\n"
                "Get one from: Linear Settings > API > Personal API keys\n"
                "https://linear.app/settings/api"
            )

    # -----------------------------------------------------------------
    # Core GraphQL transport
    # -----------------------------------------------------------------

    def _graphql(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query/mutation against the Linear API.

        Args:
            query: GraphQL query or mutation string
            variables: Optional variables dict

        Returns:
            The 'data' field from the response

        Raises:
            LinearAPIError: If the API returns errors
            urllib.error.HTTPError: If the HTTP request fails
        """
        payload = json.dumps({"query": query, "variables": variables or {}}).encode()

        req = urllib.request.Request(
            LINEAR_API_URL,
            data=payload,
            method="POST",
            headers={
                "Authorization": self._api_key,
                "Content-Type": "application/json",
            },
        )

        # Bypass any SDK sandbox proxy
        no_proxy = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(no_proxy)

        try:
            with opener.open(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            raise LinearAPIError(f"HTTP {e.code}: {body[:500]}") from e

        if "errors" in result and result["errors"]:
            msg = result["errors"][0].get("message", "Unknown error")
            raise LinearAPIError(msg, result["errors"])

        return result.get("data", {})

    # -----------------------------------------------------------------
    # Teams
    # -----------------------------------------------------------------

    def list_teams(self) -> list:
        """List all teams in the workspace.

        Returns:
            List of team dicts with id, name, key fields.
        """
        data = self._graphql("""
            query {
                teams {
                    nodes {
                        id
                        name
                        key
                    }
                }
            }
        """)
        return data.get("teams", {}).get("nodes", [])

    # -----------------------------------------------------------------
    # Projects
    # -----------------------------------------------------------------

    def list_projects(self, team_id: str) -> list:
        """List projects for a team.

        Args:
            team_id: Linear team UUID

        Returns:
            List of project dicts.
        """
        data = self._graphql(
            """
            query ListProjects($teamId: String!) {
                team(id: $teamId) {
                    projects {
                        nodes {
                            id
                            name
                            slugId
                            description
                            state
                        }
                    }
                }
            }
        """,
            {"teamId": team_id},
        )
        return data.get("team", {}).get("projects", {}).get("nodes", [])

    def create_project(self, team_id: str, name: str, description: str = "") -> dict:
        """Create a new project.

        Args:
            team_id: Linear team UUID
            name: Project name
            description: Optional project description

        Returns:
            Created project dict with id, name, slugId.
        """
        input_data: dict[str, Any] = {
            "name": name,
            "teamIds": [team_id],
        }
        if description:
            input_data["description"] = description

        data = self._graphql(
            """
            mutation CreateProject($input: ProjectCreateInput!) {
                projectCreate(input: $input) {
                    success
                    project {
                        id
                        name
                        slugId
                    }
                }
            }
        """,
            {"input": input_data},
        )
        result = data.get("projectCreate", {})
        if not result.get("success"):
            raise LinearAPIError("Failed to create project")
        return result.get("project", {})

    # -----------------------------------------------------------------
    # Issues
    # -----------------------------------------------------------------

    def list_issues(
        self,
        team_id: str | None = None,
        project_id: str | None = None,
        state: str | None = None,
    ) -> list:
        """List issues with optional filters.

        Args:
            team_id: Filter by team UUID
            project_id: Filter by project UUID
            state: Filter by state name (e.g. "Todo", "In Progress", "Done")

        Returns:
            List of issue dicts.
        """
        # Build filter dynamically
        filter_parts = {}
        if team_id:
            filter_parts["team"] = {"id": {"eq": team_id}}
        if project_id:
            filter_parts["project"] = {"id": {"eq": project_id}}
        if state:
            filter_parts["state"] = {"name": {"eqCaseInsensitive": state}}

        data = self._graphql(
            """
            query ListIssues($filter: IssueFilter) {
                issues(filter: $filter, first: 100, orderBy: createdAt) {
                    nodes {
                        id
                        identifier
                        title
                        description
                        priority
                        state {
                            id
                            name
                            type
                        }
                        project {
                            id
                            name
                        }
                        createdAt
                    }
                }
            }
        """,
            {"filter": filter_parts if filter_parts else None},
        )
        return data.get("issues", {}).get("nodes", [])

    def get_issue(self, issue_id: str) -> dict:
        """Get a single issue by ID or identifier.

        Args:
            issue_id: Linear issue UUID or identifier (e.g. "ENG-123")

        Returns:
            Issue dict with full details including comments.
        """
        # If it looks like an identifier (contains letters and dash), search by it
        if "-" in issue_id and any(c.isalpha() for c in issue_id.split("-")[0]):
            return self._get_issue_by_identifier(issue_id)

        data = self._graphql(
            """
            query GetIssue($id: String!) {
                issue(id: $id) {
                    id
                    identifier
                    title
                    description
                    priority
                    state {
                        id
                        name
                        type
                    }
                    project {
                        id
                        name
                    }
                    team {
                        id
                        name
                        key
                    }
                    comments {
                        nodes {
                            id
                            body
                            createdAt
                        }
                    }
                }
            }
        """,
            {"id": issue_id},
        )
        issue = data.get("issue")
        if not issue:
            raise LinearAPIError(f"Issue not found: {issue_id}")
        return issue

    def _get_issue_by_identifier(self, identifier: str) -> dict:
        """Look up an issue by its human-readable identifier (e.g. ENG-123)."""
        data = self._graphql(
            """
            query SearchIssue($filter: IssueFilter) {
                issues(filter: $filter, first: 1) {
                    nodes {
                        id
                        identifier
                        title
                        description
                        priority
                        state {
                            id
                            name
                            type
                        }
                        project {
                            id
                            name
                        }
                        team {
                            id
                            name
                            key
                        }
                        comments {
                            nodes {
                                id
                                body
                                createdAt
                            }
                        }
                    }
                }
            }
        """,
            {"filter": {"identifier": {"eq": identifier}}},
        )
        nodes = data.get("issues", {}).get("nodes", [])
        if not nodes:
            raise LinearAPIError(f"Issue not found: {identifier}")
        return nodes[0]

    def create_issue(
        self,
        team_id: str,
        title: str,
        description: str = "",
        project_id: str | None = None,
        priority: str | None = None,
    ) -> dict:
        """Create a new issue.

        Args:
            team_id: Linear team UUID
            title: Issue title
            description: Issue description (markdown)
            project_id: Optional project UUID to assign to
            priority: Optional priority name (urgent/high/medium/low/none)

        Returns:
            Created issue dict with id, identifier, title, state.
        """
        input_data = {
            "teamId": team_id,
            "title": title,
            "description": description,
        }
        if project_id:
            input_data["projectId"] = project_id
        if priority and priority in PRIORITY_MAP:
            input_data["priority"] = PRIORITY_MAP[priority]

        data = self._graphql(
            """
            mutation CreateIssue($input: IssueCreateInput!) {
                issueCreate(input: $input) {
                    success
                    issue {
                        id
                        identifier
                        title
                        state {
                            name
                        }
                    }
                }
            }
        """,
            {"input": input_data},
        )
        result = data.get("issueCreate", {})
        if not result.get("success"):
            raise LinearAPIError("Failed to create issue")
        return result.get("issue", {})

    # -----------------------------------------------------------------
    # Issue transitions
    # -----------------------------------------------------------------

    def list_workflow_states(self, team_id: str) -> list:
        """List workflow states for a team.

        Args:
            team_id: Linear team UUID

        Returns:
            List of state dicts with id, name, type, position.
        """
        data = self._graphql(
            """
            query WorkflowStates($teamId: String!) {
                team(id: $teamId) {
                    states {
                        nodes {
                            id
                            name
                            type
                            position
                        }
                    }
                }
            }
        """,
            {"teamId": team_id},
        )
        return data.get("team", {}).get("states", {}).get("nodes", [])

    def transition_issue(self, issue_id: str, state_name: str) -> dict:
        """Transition an issue to a new state.

        Looks up the issue to find its team, gets workflow states,
        finds the matching state by name, and updates the issue.

        Args:
            issue_id: Linear issue UUID or identifier
            state_name: Target state name (case-insensitive match)

        Returns:
            Updated issue dict.
        """
        # Get the issue to find its team
        issue = self.get_issue(issue_id)
        team_id = issue.get("team", {}).get("id")
        if not team_id:
            raise LinearAPIError(f"Cannot determine team for issue {issue_id}")

        # Find the target state
        states = self.list_workflow_states(team_id)
        target_state = None
        for s in states:
            if s["name"].lower() == state_name.lower():
                target_state = s
                break

        if not target_state:
            available = [s["name"] for s in states]
            raise LinearAPIError(f"State '{state_name}' not found. Available: {available}")

        # Update the issue
        real_id = issue["id"]  # Always use UUID for mutations
        data = self._graphql(
            """
            mutation TransitionIssue($id: String!, $input: IssueUpdateInput!) {
                issueUpdate(id: $id, input: $input) {
                    success
                    issue {
                        id
                        identifier
                        state {
                            name
                        }
                    }
                }
            }
        """,
            {"id": real_id, "input": {"stateId": target_state["id"]}},
        )
        result = data.get("issueUpdate", {})
        if not result.get("success"):
            raise LinearAPIError(f"Failed to transition issue to {state_name}")
        return result.get("issue", {})

    # -----------------------------------------------------------------
    # Comments
    # -----------------------------------------------------------------

    def add_comment(self, issue_id: str, body: str) -> dict:
        """Add a comment to an issue.

        Args:
            issue_id: Linear issue UUID or identifier
            body: Comment body (markdown)

        Returns:
            Created comment dict.
        """
        # Resolve identifier to UUID if needed
        # Identifier format is TEAM-NUMBER (e.g., ENG-123)
        # UUID format has 4 dashes and is all hex
        parts = issue_id.split("-")
        is_identifier = (
            len(parts) == 2 and parts[0].isalpha() and len(parts[0]) <= 3 and parts[1].isdigit()
        )
        if is_identifier:
            issue = self._get_issue_by_identifier(issue_id)
            issue_id = issue["id"]

        data = self._graphql(
            """
            mutation AddComment($input: CommentCreateInput!) {
                commentCreate(input: $input) {
                    success
                    comment {
                        id
                        body
                    }
                }
            }
        """,
            {"input": {"issueId": issue_id, "body": body}},
        )
        result = data.get("commentCreate", {})
        if not result.get("success"):
            raise LinearAPIError("Failed to add comment")
        return result.get("comment", {})

    # -----------------------------------------------------------------
    # Archive
    # -----------------------------------------------------------------

    def archive_issue(self, issue_id: str) -> bool:
        """Archive an issue.

        Args:
            issue_id: Linear issue UUID or identifier

        Returns:
            True if successful.
        """
        # Resolve identifier to UUID if needed
        # Identifier format is TEAM-NUMBER (e.g., ENG-123)
        # UUID format has 4 dashes and is all hex
        parts = issue_id.split("-")
        is_identifier = (
            len(parts) == 2 and parts[0].isalpha() and len(parts[0]) <= 3 and parts[1].isdigit()
        )
        if is_identifier:
            issue = self._get_issue_by_identifier(issue_id)
            issue_id = issue["id"]

        data = self._graphql(
            """
            mutation ArchiveIssue($id: String!) {
                issueArchive(id: $id) {
                    success
                }
            }
        """,
            {"id": issue_id},
        )
        return data.get("issueArchive", {}).get("success", False)

    # -----------------------------------------------------------------
    # Labels
    # -----------------------------------------------------------------

    def list_labels(self, team_id: str) -> list:
        """List labels for a team.

        Args:
            team_id: Linear team UUID

        Returns:
            List of label dicts with id, name, color.
        """
        data = self._graphql(
            """
            query Labels($teamId: String!) {
                team(id: $teamId) {
                    labels {
                        nodes {
                            id
                            name
                            color
                        }
                    }
                }
            }
        """,
            {"teamId": team_id},
        )
        return data.get("team", {}).get("labels", {}).get("nodes", [])


# =====================================================================
# CLI Interface
# =====================================================================


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Linear GraphQL API Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list-teams
    sub.add_parser("list-teams", help="List all teams")

    # list-projects
    p = sub.add_parser("list-projects", help="List projects for a team")
    p.add_argument("--team-id", required=True)

    # create-project
    p = sub.add_parser("create-project", help="Create a new project")
    p.add_argument("--team-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--description", default="")

    # list-issues
    p = sub.add_parser("list-issues", help="List issues with filters")
    p.add_argument("--team-id")
    p.add_argument("--project-id")
    p.add_argument("--state")

    # get-issue
    p = sub.add_parser("get-issue", help="Get issue details")
    p.add_argument("--id", required=True)

    # create-issue
    p = sub.add_parser("create-issue", help="Create a new issue")
    p.add_argument("--team-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--project-id")
    p.add_argument("--priority", choices=list(PRIORITY_MAP.keys()))

    # transition-issue
    p = sub.add_parser("transition-issue", help="Transition issue to a new state")
    p.add_argument("--id", required=True)
    p.add_argument("--state", required=True)

    # add-comment
    p = sub.add_parser("add-comment", help="Add a comment to an issue")
    p.add_argument("--issue-id", required=True)
    p.add_argument("--body", required=True)

    # archive-issue
    p = sub.add_parser("archive-issue", help="Archive an issue")
    p.add_argument("--id", required=True)

    # list-workflow-states
    p = sub.add_parser("list-workflow-states", help="List workflow states for a team")
    p.add_argument("--team-id", required=True)

    # list-labels
    p = sub.add_parser("list-labels", help="List labels for a team")
    p.add_argument("--team-id", required=True)

    return parser


def _run_cli(args: argparse.Namespace) -> Any:
    """Dispatch CLI command to the appropriate LinearClient method."""
    client = LinearClient()

    cmd = args.command
    if cmd == "list-teams":
        return client.list_teams()
    elif cmd == "list-projects":
        return client.list_projects(args.team_id)
    elif cmd == "create-project":
        return client.create_project(args.team_id, args.name, args.description)
    elif cmd == "list-issues":
        return client.list_issues(args.team_id, args.project_id, args.state)
    elif cmd == "get-issue":
        return client.get_issue(args.id)
    elif cmd == "create-issue":
        return client.create_issue(
            args.team_id,
            args.title,
            args.description,
            args.project_id,
            args.priority,
        )
    elif cmd == "transition-issue":
        return client.transition_issue(args.id, args.state)
    elif cmd == "add-comment":
        return client.add_comment(args.issue_id, args.body)
    elif cmd == "archive-issue":
        return {"success": client.archive_issue(args.id)}
    elif cmd == "list-workflow-states":
        return client.list_workflow_states(args.team_id)
    elif cmd == "list-labels":
        return client.list_labels(args.team_id)
    else:
        raise ValueError(f"Unknown command: {cmd}")


def main() -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    try:
        result = _run_cli(args)
        print(json.dumps(result, indent=2))
        return 0
    except LinearAPIError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    except ValueError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(json.dumps({"error": f"Network error: {e}"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
