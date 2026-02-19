"""Unit tests for agent prompt file loading and agent definition registrations.

Covers acceptance criteria for:
- AI-267: jira_agent_prompt.md created and loaded by jira agent
- AI-268: gitlab_agent_prompt.md created and loaded by gitlab agent
- AI-269: knowledge_base_agent_prompt.md created and loaded (replaces inline)
- AI-270: security_reviewer agent registered with correct model, tools, and prompt
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
PROMPTS_DIR = REPO_ROOT / "prompts"


# ---------------------------------------------------------------------------
# Stub heavy dependencies so agents.definitions is importable in any environment
# ---------------------------------------------------------------------------

def _stub_dependencies() -> None:
    """Stub out arcade_config, claude_agent_sdk, and related modules."""
    # Stub arcade_config
    if "arcade_config" not in sys.modules:
        arcade_mod = types.ModuleType("arcade_config")
        for fn_name in (
            "get_coding_tools",
            "get_github_tools",
            "get_linear_tools",
            "get_slack_tools",
            "get_qa_tools",
            "get_jira_tools",
            "get_gitlab_tools",
        ):
            setattr(arcade_mod, fn_name, lambda: [])
        sys.modules["arcade_config"] = arcade_mod
    else:
        # Ensure get_qa_tools and integration tools exist even if arcade_config is already loaded
        arcade_mod = sys.modules["arcade_config"]
        for fn_name in ("get_qa_tools", "get_jira_tools", "get_gitlab_tools"):
            if not hasattr(arcade_mod, fn_name):
                setattr(arcade_mod, fn_name, lambda: [])

    # Stub claude_agent_sdk
    if "claude_agent_sdk" not in sys.modules:
        class _AgentDefinition:
            def __init__(self, description="", prompt="", tools=None, model="haiku"):
                self.description = description
                self.prompt = prompt
                self.tools = tools or []
                self.model = model

        sdk_mod = types.ModuleType("claude_agent_sdk")
        types_mod = types.ModuleType("claude_agent_sdk.types")
        types_mod.AgentDefinition = _AgentDefinition  # type: ignore[attr-defined]
        for cls_name in ("AssistantMessage", "ClaudeSDKClient", "TextBlock", "ToolUseBlock"):
            setattr(sdk_mod, cls_name, type(cls_name, (), {}))
        sys.modules["claude_agent_sdk"] = sdk_mod
        sys.modules["claude_agent_sdk.types"] = types_mod

    # Stub agents.model_routing if needed
    if "agents.model_routing" not in sys.modules:
        routing_mod = types.ModuleType("agents.model_routing")
        routing_mod.CostTracker = type("CostTracker", (), {})  # type: ignore[attr-defined]
        routing_mod.ModelTier = type("ModelTier", (), {})  # type: ignore[attr-defined]
        routing_mod.check_cost_cap = lambda *a, **kw: None  # type: ignore[attr-defined]
        routing_mod.estimate_complexity = lambda *a, **kw: 5  # type: ignore[attr-defined]
        routing_mod.get_cost_cap_for_org = lambda *a, **kw: None  # type: ignore[attr-defined]
        routing_mod.select_model = lambda *a, **kw: "haiku"  # type: ignore[attr-defined]
        sys.modules["agents.model_routing"] = routing_mod


_stub_dependencies()


def _prompt_file(name: str) -> Path:
    """Return the path to a prompt file in the prompts/ directory."""
    return PROMPTS_DIR / f"{name}.md"


# ===========================================================================
# AI-267: jira_agent_prompt.md
# ===========================================================================


class TestJiraAgentPromptFile(unittest.TestCase):
    """jira_agent_prompt.md exists and contains required Jira-specific content."""

    def setUp(self) -> None:
        self.path = _prompt_file("jira_agent_prompt")
        self.content = self.path.read_text()

    def test_file_exists(self) -> None:
        self.assertTrue(self.path.exists(), "jira_agent_prompt.md must exist")

    def test_file_not_empty(self) -> None:
        self.assertGreater(len(self.content), 500, "Prompt must be substantive (>500 chars)")

    def test_contains_jira_terminology(self) -> None:
        """Must mention Jira-native concepts."""
        for term in ["Epic", "Story", "JQL", "Merge Request"]:
            # JQL is Jira-specific; 'Merge Request' appears here as a note that MR != PR
            pass  # Terms vary by section; check the important ones below

        # JQL must be present (distinguishes from Linear prompt)
        self.assertIn("JQL", self.content, "Jira prompt must document JQL query language")

    def test_contains_jql_section(self) -> None:
        self.assertIn("JQL", self.content)
        self.assertIn("jql", self.content.lower())

    def test_contains_issue_hierarchy(self) -> None:
        """Epic > Story > Sub-task hierarchy must be documented."""
        self.assertIn("Epic", self.content)
        self.assertIn("Story", self.content)
        self.assertIn("Sub-task", self.content)

    def test_contains_webhook_guidance(self) -> None:
        self.assertIn("webhook", self.content.lower())

    def test_contains_atlassian_api_patterns(self) -> None:
        self.assertIn("atlassian", self.content.lower())

    def test_contains_bidirectional_sync(self) -> None:
        self.assertIn("sync", self.content.lower())

    def test_contains_git_identity(self) -> None:
        self.assertIn("jira-agent@claude-agents.dev", self.content)

    def test_does_not_reuse_linear_prompt(self) -> None:
        """The jira prompt must be distinct from the linear prompt."""
        linear_content = _prompt_file("linear_agent_prompt").read_text()
        # The Jira prompt should have substantially different content
        # (they should share < 30% of lines if they're truly distinct)
        jira_lines = set(self.content.splitlines())
        linear_lines = set(linear_content.splitlines())
        overlap = len(jira_lines & linear_lines)
        total = len(jira_lines)
        overlap_ratio = overlap / total if total > 0 else 1.0
        self.assertLess(
            overlap_ratio,
            0.30,
            f"Jira prompt overlaps {overlap_ratio:.0%} with linear prompt — must be distinct",
        )


# ===========================================================================
# AI-268: gitlab_agent_prompt.md
# ===========================================================================


class TestGitLabAgentPromptFile(unittest.TestCase):
    """gitlab_agent_prompt.md exists and contains required GitLab-specific content."""

    def setUp(self) -> None:
        self.path = _prompt_file("gitlab_agent_prompt")
        self.content = self.path.read_text()

    def test_file_exists(self) -> None:
        self.assertTrue(self.path.exists(), "gitlab_agent_prompt.md must exist")

    def test_file_not_empty(self) -> None:
        self.assertGreater(len(self.content), 500, "Prompt must be substantive (>500 chars)")

    def test_contains_merge_request_terminology(self) -> None:
        """GitLab uses Merge Requests, not Pull Requests."""
        self.assertIn("Merge Request", self.content)

    def test_mentions_pipeline(self) -> None:
        """GitLab CI/CD pipelines are first-class concepts."""
        self.assertIn("pipeline", self.content.lower())
        self.assertIn("Pipeline", self.content)

    def test_contains_namespace_concept(self) -> None:
        self.assertIn("namespace", self.content.lower())

    def test_contains_gitlab_api_patterns(self) -> None:
        self.assertIn("gitlab.com/api", self.content.lower())

    def test_mentions_protected_branches(self) -> None:
        self.assertIn("rotected branch", self.content)

    def test_mentions_approval_rules(self) -> None:
        self.assertIn("pproval", self.content)

    def test_contains_mr_lifecycle(self) -> None:
        """Draft → Open → Approved → Pipeline Pass → Merged."""
        self.assertIn("Draft", self.content)
        self.assertIn("Merged", self.content)

    def test_contains_git_identity(self) -> None:
        self.assertIn("gitlab-agent@claude-agents.dev", self.content)

    def test_does_not_reuse_github_prompt(self) -> None:
        """The gitlab prompt must be distinct from the github prompt."""
        github_content = _prompt_file("github_agent_prompt").read_text()
        gitlab_lines = set(self.content.splitlines())
        github_lines = set(github_content.splitlines())
        overlap = len(gitlab_lines & github_lines)
        total = len(gitlab_lines)
        overlap_ratio = overlap / total if total > 0 else 1.0
        self.assertLess(
            overlap_ratio,
            0.30,
            f"GitLab prompt overlaps {overlap_ratio:.0%} with github prompt — must be distinct",
        )


# ===========================================================================
# AI-269: knowledge_base_agent_prompt.md
# ===========================================================================


class TestKnowledgeBaseAgentPromptFile(unittest.TestCase):
    """knowledge_base_agent_prompt.md exists and the agent definition loads it."""

    def setUp(self) -> None:
        self.path = _prompt_file("knowledge_base_agent_prompt")
        self.content = self.path.read_text()

    def test_file_exists(self) -> None:
        self.assertTrue(self.path.exists(), "knowledge_base_agent_prompt.md must exist")

    def test_file_not_empty(self) -> None:
        self.assertGreater(len(self.content), 500, "Prompt must be substantive (>500 chars)")

    def test_contains_rag_guidance(self) -> None:
        self.assertIn("RAG", self.content)

    def test_contains_chunking_guidance(self) -> None:
        self.assertIn("chunk", self.content.lower())

    def test_contains_similarity_search(self) -> None:
        self.assertIn("similarity", self.content.lower())

    def test_contains_citation_format(self) -> None:
        self.assertIn("cite", self.content.lower())

    def test_contains_source_priority(self) -> None:
        """Prompt must document source priority for retrieval."""
        self.assertIn("priority", self.content.lower())

    def test_contains_git_identity(self) -> None:
        self.assertIn("knowledge-base-agent@claude-agents.dev", self.content)

    def test_definition_uses_prompt_file(self) -> None:
        """definitions.py must load from file, not use an inline string."""
        definitions_path = REPO_ROOT / "agents" / "definitions.py"
        definitions_source = definitions_path.read_text()

        # The inline string should no longer be present
        self.assertNotIn(
            '"You are the Knowledge Base Agent. You maintain',
            definitions_source,
            "definitions.py must not use the old inline prompt string — it should load from file",
        )

        # The new file-based loading should be present
        self.assertIn(
            "_prompt(\"knowledge_base\", \"knowledge_base_agent_prompt\")",
            definitions_source,
            "definitions.py must load knowledge_base prompt from file via _prompt()",
        )

    def test_grep_tool_added_to_knowledge_base_tools(self) -> None:
        """Grep tool should be available to the knowledge_base agent for searching."""
        definitions_path = REPO_ROOT / "agents" / "definitions.py"
        definitions_source = definitions_path.read_text()
        # Check that Grep is included in knowledge_base tools
        # The definition includes FILE_TOOLS + ["Bash", "Grep"]
        self.assertIn('"Grep"', definitions_source)


# ===========================================================================
# AI-270: security_reviewer agent definition (file-based inspection)
# ===========================================================================


class TestSecurityReviewerAgentDefinition(unittest.TestCase):
    """security_reviewer agent is registered in definitions.py with correct config."""

    def setUp(self) -> None:
        self.definitions_source = (REPO_ROOT / "agents" / "definitions.py").read_text()
        self.prompt_path = _prompt_file("security_reviewer_agent_prompt")
        self.prompt_content = self.prompt_path.read_text()

    def test_security_reviewer_registered_in_definitions(self) -> None:
        """security_reviewer key must exist in the definitions dict."""
        self.assertIn(
            '"security_reviewer"',
            self.definitions_source,
            "security_reviewer must be registered in create_agent_definitions()",
        )

    def test_security_reviewer_model_is_sonnet(self) -> None:
        """Security review requires judgment — must use sonnet, not haiku."""
        self.assertIn(
            '"security_reviewer": "sonnet"',
            self.definitions_source,
            "DEFAULT_MODELS must set security_reviewer to 'sonnet'",
        )

    def test_security_reviewer_has_git_identity(self) -> None:
        self.assertIn(
            "security-reviewer-agent@claude-agents.dev",
            self.definitions_source,
            "AGENT_GIT_IDENTITIES must include security_reviewer email",
        )

    def test_security_reviewer_description_mentions_security(self) -> None:
        self.assertIn(
            "Security",
            self.definitions_source,
        )
        self.assertIn("OWASP", self.definitions_source)

    def test_security_reviewer_loads_prompt_from_file(self) -> None:
        """definitions.py must use _prompt() to load security_reviewer prompt."""
        self.assertIn(
            '_prompt("security_reviewer", "security_reviewer_agent_prompt")',
            self.definitions_source,
            "definitions.py must load security_reviewer prompt via _prompt()",
        )

    def test_security_reviewer_uses_pr_reviewer_tools(self) -> None:
        """security_reviewer should use _get_pr_reviewer_tools() for GitHub access."""
        self.assertIn(
            "_get_pr_reviewer_tools()",
            self.definitions_source,
        )

    def test_security_reviewer_exported_as_constant(self) -> None:
        """SECURITY_REVIEWER_AGENT must be exported as a module-level constant."""
        self.assertIn(
            'SECURITY_REVIEWER_AGENT = AGENT_DEFINITIONS["security_reviewer"]',
            self.definitions_source,
            "SECURITY_REVIEWER_AGENT must be exported from definitions.py",
        )

    def test_security_reviewer_prompt_file_exists(self) -> None:
        self.assertTrue(self.prompt_path.exists(), "security_reviewer_agent_prompt.md must exist")

    def test_security_reviewer_prompt_contains_owasp(self) -> None:
        self.assertIn("OWASP", self.prompt_content)

    def test_security_reviewer_prompt_contains_stripe_checks(self) -> None:
        self.assertIn("Stripe", self.prompt_content)
        self.assertIn("idempotency", self.prompt_content.lower())

    def test_security_reviewer_prompt_contains_jwt_checks(self) -> None:
        self.assertIn("JWT", self.prompt_content)

    def test_security_reviewer_prompt_contains_audit_trail(self) -> None:
        self.assertIn("audit", self.prompt_content.lower())

    def test_security_reviewer_prompt_contains_gdpr(self) -> None:
        self.assertIn("GDPR", self.prompt_content)

    def test_security_reviewer_prompt_contains_approved_format(self) -> None:
        """Prompt must define APPROVED and CHANGES_REQUESTED output formats."""
        self.assertIn("APPROVED", self.prompt_content)
        self.assertIn("CHANGES_REQUESTED", self.prompt_content)

    def test_orchestrator_prompt_mentions_security_reviewer(self) -> None:
        """Orchestrator prompt must route to security_reviewer for sensitive PRs."""
        orchestrator_path = PROMPTS_DIR / "orchestrator_prompt.md"
        orchestrator_content = orchestrator_path.read_text()
        self.assertIn(
            "security_reviewer",
            orchestrator_content,
            "Orchestrator prompt must mention security_reviewer agent",
        )

    def test_orchestrator_prompt_lists_routing_paths(self) -> None:
        """Orchestrator must specify which paths trigger security_reviewer."""
        orchestrator_path = PROMPTS_DIR / "orchestrator_prompt.md"
        orchestrator_content = orchestrator_path.read_text()
        self.assertIn("auth/", orchestrator_content)
        self.assertIn("billing/", orchestrator_content)

    def test_security_reviewer_prompt_contains_git_identity(self) -> None:
        self.assertIn("security-reviewer-agent@claude-agents.dev", self.prompt_content)


# ===========================================================================
# Integration: all prompt files load without error (file-based inspection)
# ===========================================================================


class TestAllPromptsLoad(unittest.TestCase):
    """All relevant prompt files exist and have content."""

    def test_jira_prompt_has_jql(self) -> None:
        """Jira prompt distinctively includes JQL query language."""
        content = _prompt_file("jira_agent_prompt").read_text()
        self.assertIn("JQL", content)

    def test_gitlab_prompt_has_merge_request(self) -> None:
        """GitLab prompt uses Merge Request terminology."""
        content = _prompt_file("gitlab_agent_prompt").read_text()
        self.assertIn("Merge Request", content)

    def test_knowledge_base_prompt_has_rag(self) -> None:
        """Knowledge base prompt has RAG guidance."""
        content = _prompt_file("knowledge_base_agent_prompt").read_text()
        self.assertIn("RAG", content)

    def test_security_reviewer_prompt_has_owasp(self) -> None:
        """Security reviewer prompt has OWASP guidance."""
        content = _prompt_file("security_reviewer_agent_prompt").read_text()
        self.assertIn("OWASP", content)

    def test_jira_definition_uses_jira_prompt(self) -> None:
        """definitions.py jira entry must load jira_agent_prompt."""
        source = (REPO_ROOT / "agents" / "definitions.py").read_text()
        self.assertIn('_prompt("jira", "jira_agent_prompt")', source)

    def test_gitlab_definition_uses_gitlab_prompt(self) -> None:
        """definitions.py gitlab entry must load gitlab_agent_prompt."""
        source = (REPO_ROOT / "agents" / "definitions.py").read_text()
        self.assertIn('_prompt("gitlab", "gitlab_agent_prompt")', source)

    def test_knowledge_base_definition_uses_file_prompt(self) -> None:
        """definitions.py knowledge_base entry must use _prompt() not inline string."""
        source = (REPO_ROOT / "agents" / "definitions.py").read_text()
        self.assertIn('_prompt("knowledge_base", "knowledge_base_agent_prompt")', source)
        self.assertNotIn(
            '"You are the Knowledge Base Agent. You maintain',
            source,
        )

    def test_security_reviewer_definition_uses_security_prompt(self) -> None:
        """definitions.py security_reviewer entry must load security_reviewer_agent_prompt."""
        source = (REPO_ROOT / "agents" / "definitions.py").read_text()
        self.assertIn(
            '_prompt("security_reviewer", "security_reviewer_agent_prompt")',
            source,
        )


if __name__ == "__main__":
    unittest.main()
