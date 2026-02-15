"""Artifact Detection Module - Detects artifacts from agent outputs.

This module provides artifact detection logic that parses agent outputs to identify
specific artifacts produced by different agent types:

- coding/coding_fast: files created/modified, tests run
- github: commits, PRs, branches created
- linear: issues created/updated, comments added
- slack: messages sent
- pr_reviewer: reviews completed, approvals, change requests

The detection is based on pattern matching against tool results and agent outputs,
identifying common patterns like git commands, file operations, Linear API calls, etc.
"""

import re
from typing import List, Literal

# Agent type definitions
AgentType = Literal[
    "coding",
    "coding_fast",
    "github",
    "linear",
    "slack",
    "pr_reviewer",
    "pr_reviewer_fast",
    "ops"
]


class ArtifactDetector:
    """Detects artifacts from agent tool outputs and results.

    Usage:
        detector = ArtifactDetector()
        artifacts = detector.detect_artifacts(
            agent_name="coding",
            tool_results="Created file test.py\nModified config.json\nRan pytest with 15 tests"
        )
        # Returns: ['file:test.py:created', 'file:config.json:modified', 'tests_run:15']
    """

    def __init__(self):
        """Initialize the artifact detector with patterns for each agent type."""
        # Compile regex patterns for better performance
        self._patterns = {
            # Coding agent patterns
            "file_created": re.compile(
                r'(?:created|wrote|added|writing)\s+(?:new\s+)?(?:file\s+)?[`\'"]?([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)[`\'"]?',
                re.IGNORECASE
            ),
            "file_modified": re.compile(
                r'(?:modified|updated|edited|changed|editing)\s+(?:file\s+)?[`\'"]?([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)[`\'"]?',
                re.IGNORECASE
            ),
            "tests_run": re.compile(
                r'(?:(?:ran|run|executed|running)\s+)?(?:pytest|test|tests)?.*?(\d+)\s+(?:test|passed|failed|cases)',
                re.IGNORECASE
            ),
            "test_file": re.compile(
                r'(?:created|wrote|added)\s+(?:test\s+)?(?:file\s+)?[`\'"]?(test_[a-zA-Z0-9_\-./]+\.py)[`\'"]?',
                re.IGNORECASE
            ),

            # GitHub agent patterns
            "commit": re.compile(
                r'(?:commit|committed|created\s+commit)\s+([0-9a-f]{7,40})',
                re.IGNORECASE
            ),
            "pr_created": re.compile(
                r'(?:created|opened)\s+(?:PR|pull\s+request)\s+#?(\d+)',
                re.IGNORECASE
            ),
            "pr_merged": re.compile(
                r'(?:merged)\s+(?:PR|pull\s+request)\s+#?(\d+)',
                re.IGNORECASE
            ),
            "branch_created": re.compile(
                r'(?:created\s+branch|created\s+new\s+branch)\s+[`\'"]?([a-zA-Z0-9_\-./]+)[`\'"]?',
                re.IGNORECASE
            ),

            # Linear agent patterns
            "issue_created": re.compile(
                r'(?:created|opened)\s+(?:issue|ticket)\s+([A-Z]+-\d+)',
                re.IGNORECASE
            ),
            "issue_updated": re.compile(
                r'(?:updated|transitioned|moved)\s+(?:issue|ticket)\s+([A-Z]+-\d+)',
                re.IGNORECASE
            ),
            "comment_added": re.compile(
                r'(?:added|posted|created)\s+comment\s+(?:on|to|on\s+ticket)\s+([A-Z]+-\d+)',
                re.IGNORECASE
            ),

            # Slack agent patterns
            "message_sent": re.compile(
                r'(?:sent|posted)\s+(?:message|notification)\s+(?:to|in)\s+(?:channel\s+)?[`\'"]?([#@a-zA-Z0-9_\-]+)[`\'"]?',
                re.IGNORECASE
            ),

            # PR Reviewer agent patterns
            "review_completed": re.compile(
                r'(?:completed|submitted)\s+(?:review|PR\s+review|review\s+on\s+PR)\s+(?:on|for)?\s*#?(\d+)',
                re.IGNORECASE
            ),
            "approval": re.compile(
                r'(?:approved)\s+(?:PR|pull\s+request)\s+#?(\d+)',
                re.IGNORECASE
            ),
            "changes_requested": re.compile(
                r'(?:requested\s+changes|changes\s+requested)\s+(?:on|for)\s+(?:PR|pull\s+request)\s+#?(\d+)',
                re.IGNORECASE
            ),
        }

        # Agent-specific patterns mapping
        self._agent_patterns = {
            "coding": ["file_created", "file_modified", "tests_run", "test_file"],
            "coding_fast": ["file_created", "file_modified", "tests_run", "test_file"],
            "github": ["commit", "pr_created", "pr_merged", "branch_created"],
            "linear": ["issue_created", "issue_updated", "comment_added"],
            "slack": ["message_sent"],
            "pr_reviewer": ["review_completed", "approval", "changes_requested"],
            "pr_reviewer_fast": ["review_completed", "approval", "changes_requested"],
            "ops": ["issue_updated", "message_sent", "branch_created"],  # Composite agent
        }

    def detect_artifacts(
        self,
        agent_name: str,
        tool_results: str,
        additional_context: str = ""
    ) -> List[str]:
        """Detect artifacts from agent tool results and outputs.

        Args:
            agent_name: Name of the agent (e.g., "coding", "github", "linear")
            tool_results: Text output from agent tool executions
            additional_context: Additional context like task description or prompt

        Returns:
            List of artifact strings in format:
            - "file:<path>:created" or "file:<path>:modified"
            - "commit:<sha>"
            - "pr:<number>:created" or "pr:<number>:merged"
            - "branch:<name>:created"
            - "issue:<key>:created" or "issue:<key>:updated"
            - "comment:<issue_key>:added"
            - "message:<channel>:sent"
            - "review:<pr_number>:completed"
            - "approval:<pr_number>"
            - "changes_requested:<pr_number>"
            - "tests_run:<count>"
        """
        artifacts: List[str] = []

        # Get applicable patterns for this agent
        pattern_names = self._agent_patterns.get(agent_name, [])

        # Combine tool results and context for detection
        full_text = f"{tool_results}\n{additional_context}"

        for pattern_name in pattern_names:
            pattern = self._patterns.get(pattern_name)
            if not pattern:
                continue

            matches = pattern.finditer(full_text)
            for match in matches:
                artifact = self._format_artifact(pattern_name, match)
                if artifact and artifact not in artifacts:
                    artifacts.append(artifact)

        return artifacts

    def _format_artifact(self, pattern_name: str, match: re.Match) -> str:
        """Format a regex match into an artifact string.

        Args:
            pattern_name: Name of the pattern that matched
            match: Regex match object

        Returns:
            Formatted artifact string
        """
        # Extract captured group (usually the identifier)
        identifier = match.group(1) if match.lastindex and match.lastindex >= 1 else ""

        # Format based on pattern type
        if pattern_name == "file_created":
            return f"file:{identifier}:created"
        elif pattern_name == "file_modified":
            return f"file:{identifier}:modified"
        elif pattern_name == "tests_run":
            return f"tests_run:{identifier}"
        elif pattern_name == "test_file":
            return f"file:{identifier}:created"
        elif pattern_name == "commit":
            return f"commit:{identifier}"
        elif pattern_name == "pr_created":
            return f"pr:{identifier}:created"
        elif pattern_name == "pr_merged":
            return f"pr:{identifier}:merged"
        elif pattern_name == "branch_created":
            return f"branch:{identifier}:created"
        elif pattern_name == "issue_created":
            return f"issue:{identifier}:created"
        elif pattern_name == "issue_updated":
            return f"issue:{identifier}:updated"
        elif pattern_name == "comment_added":
            return f"comment:{identifier}:added"
        elif pattern_name == "message_sent":
            return f"message:{identifier}:sent"
        elif pattern_name == "review_completed":
            return f"review:{identifier}:completed"
        elif pattern_name == "approval":
            return f"approval:{identifier}"
        elif pattern_name == "changes_requested":
            return f"changes_requested:{identifier}"

        return ""

    def detect_from_bash_output(self, agent_name: str, bash_output: str) -> List[str]:
        """Detect artifacts from Bash tool output (git commands, pytest, etc.).

        This is a specialized detection method for parsing common CLI tool outputs.

        Args:
            agent_name: Name of the agent
            bash_output: Output from Bash tool execution

        Returns:
            List of detected artifacts
        """
        artifacts: List[str] = []

        # Detect git commits from git log output
        # Match both full line format and inline commit references
        commit_pattern = re.compile(r'(?:^commit\s+|commit\s+)([0-9a-f]{7,40})', re.MULTILINE | re.IGNORECASE)
        for match in commit_pattern.finditer(bash_output):
            sha = match.group(1)
            # Truncate to 7 chars if longer
            short_sha = sha[:7] if len(sha) > 7 else sha
            artifact = f"commit:{short_sha}"
            if artifact not in artifacts:
                artifacts.append(artifact)

        # Detect pytest test counts
        pytest_pattern = re.compile(r'(\d+)\s+passed', re.IGNORECASE)
        match = pytest_pattern.search(bash_output)
        if match:
            artifacts.append(f"tests_run:{match.group(1)}")

        # Detect file creations from git status
        if "new file:" in bash_output:
            new_file_pattern = re.compile(r'new file:\s+(.+?)(?:\n|$)')
            for match in new_file_pattern.finditer(bash_output):
                filepath = match.group(1).strip()
                artifacts.append(f"file:{filepath}:created")

        # Detect file modifications from git status
        if "modified:" in bash_output:
            modified_pattern = re.compile(r'modified:\s+(.+?)(?:\n|$)')
            for match in modified_pattern.finditer(bash_output):
                filepath = match.group(1).strip()
                artifacts.append(f"file:{filepath}:modified")

        # Detect PR creation from gh pr create output
        gh_pr_pattern = re.compile(r'https://github\.com/.+/pull/(\d+)', re.IGNORECASE)
        match = gh_pr_pattern.search(bash_output)
        if match:
            artifacts.append(f"pr:{match.group(1)}:created")

        return artifacts

    def detect_from_tool_name(
        self,
        agent_name: str,
        tool_name: str,
        tool_input: dict,
        tool_output: str
    ) -> List[str]:
        """Detect artifacts based on specific tool invocations.

        This provides tool-specific detection logic for known tools.

        Args:
            agent_name: Name of the agent
            tool_name: Name of the tool that was invoked
            tool_input: Tool input parameters (dict)
            tool_output: Tool output/result text

        Returns:
            List of detected artifacts
        """
        artifacts: List[str] = []

        # Write tool - file creation
        if tool_name == "Write":
            filepath = tool_input.get("file_path", "")
            if filepath:
                artifacts.append(f"file:{filepath}:created")

        # Edit tool - file modification
        elif tool_name == "Edit":
            filepath = tool_input.get("file_path", "")
            if filepath:
                artifacts.append(f"file:{filepath}:modified")

        # Bash tool - parse output
        elif tool_name == "Bash":
            artifacts.extend(self.detect_from_bash_output(agent_name, tool_output))

        # Linear MCP tools
        elif "Linear" in tool_name or "linear" in tool_name.lower():
            if "create_issue" in tool_name.lower():
                # Look for issue key in output
                issue_pattern = re.compile(r'([A-Z]+-\d+)')
                match = issue_pattern.search(tool_output)
                if match:
                    artifacts.append(f"issue:{match.group(1)}:created")
            elif "update_issue" in tool_name.lower():
                # Try to get issue from input
                issue_id = tool_input.get("issue_id") or tool_input.get("issueId")
                if issue_id:
                    artifacts.append(f"issue:{issue_id}:updated")
            elif "create_comment" in tool_name.lower():
                issue_id = tool_input.get("issue_id") or tool_input.get("issueId")
                if issue_id:
                    artifacts.append(f"comment:{issue_id}:added")

        # GitHub MCP tools
        elif "Github" in tool_name or "github" in tool_name.lower():
            if "CreatePullRequest" in tool_name:
                # Look for PR number in output (JSON or text)
                pr_pattern = re.compile(r'(?:"number":\s*|#)(\d+)')
                match = pr_pattern.search(tool_output)
                if match:
                    artifacts.append(f"pr:{match.group(1)}:created")
            elif "MergePullRequest" in tool_name:
                pr_num = tool_input.get("pull_number") or tool_input.get("pullNumber")
                if pr_num:
                    artifacts.append(f"pr:{pr_num}:merged")
            elif "CreateBranch" in tool_name:
                branch_name = tool_input.get("branch") or tool_input.get("branchName")
                if branch_name:
                    artifacts.append(f"branch:{branch_name}:created")
            elif "SubmitPullRequestReview" in tool_name:
                pr_num = tool_input.get("pull_number") or tool_input.get("pullNumber")
                event = tool_input.get("event", "").upper()
                if pr_num:
                    if event == "APPROVE":
                        artifacts.append(f"approval:{pr_num}")
                    elif event == "REQUEST_CHANGES":
                        artifacts.append(f"changes_requested:{pr_num}")
                    else:
                        artifacts.append(f"review:{pr_num}:completed")

        # Slack MCP tools
        elif "slack" in tool_name.lower():
            if "add_message" in tool_name.lower() or "send" in tool_name.lower():
                channel = tool_input.get("channel") or tool_input.get("channel_id")
                if channel:
                    artifacts.append(f"message:{channel}:sent")

        return artifacts


# Singleton instance for convenience
_detector_instance = None


def get_artifact_detector() -> ArtifactDetector:
    """Get the singleton artifact detector instance.

    Returns:
        Shared ArtifactDetector instance
    """
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = ArtifactDetector()
    return _detector_instance
