"""Example custom agent: SecurityReviewAgent.

Demonstrates how to define, validate, and test a custom agent using the
Agent-Engineers SDK.

Run this example::

    cd /path/to/agent-dashboard
    python -m sdk.examples.security_review_agent
"""
from __future__ import annotations

from sdk.agent_definition import AgentDefinition
from sdk.registry import AgentRegistry
from sdk.mock_orchestrator import MockOrchestrator


# ---------------------------------------------------------------------------
# Define the agent
# ---------------------------------------------------------------------------

SECURITY_REVIEW_AGENT = AgentDefinition(
    name="security-review",
    title="Security Review Agent",
    description=(
        "Reviews pull requests and code changes for security vulnerabilities, "
        "OWASP top-10 issues, secrets in code, and dependency CVEs."
    ),
    model="sonnet",
    version="0.1.0",
    system_prompt="""\
You are a security-focused code review assistant integrated into the
Agent-Engineers platform.

Your responsibilities:
1. Identify security vulnerabilities in code changes (OWASP Top 10, CWEs).
2. Flag hardcoded secrets, credentials, or API keys.
3. Check for insecure dependencies (known CVEs).
4. Review authentication and authorisation logic.
5. Verify input validation and output encoding.

For each finding, provide:
- Severity: CRITICAL / HIGH / MEDIUM / LOW / INFO
- Location: file path and line number if available
- Description: clear explanation of the issue
- Recommendation: concrete remediation steps

Always err on the side of caution — report potential issues even if you are
not 100% certain.
""",
    tools=["Read", "Glob", "Grep"],
    git_identity={
        "name": "Security Review Agent",
        "email": "security-agent@agent-engineers.io",
    },
    org_id=None,  # Public agent — available to all organisations
)


# ---------------------------------------------------------------------------
# Example: register and run via MockOrchestrator
# ---------------------------------------------------------------------------

def run_example() -> None:
    print("=== SecurityReviewAgent Example ===\n")

    # 1. Validate the definition
    errors = SECURITY_REVIEW_AGENT.validate()
    if errors:
        print("Validation errors:")
        for err in errors:
            print(f"  - {err}")
        return

    print(f"Agent: {SECURITY_REVIEW_AGENT.title} (v{SECURITY_REVIEW_AGENT.version})")
    print(f"Model: {SECURITY_REVIEW_AGENT.model}")
    print(f"Tools: {', '.join(SECURITY_REVIEW_AGENT.tools)}")
    print()

    # 2. Register in a local registry
    registry = AgentRegistry()
    registry.register(SECURITY_REVIEW_AGENT)

    # 3. Run via MockOrchestrator
    orchestrator = MockOrchestrator(registry)
    result = orchestrator.run_agent(
        agent_name="security-review",
        task={
            "ticket": "AI-SEC-001",
            "pr_number": 42,
            "diff_url": "https://github.com/example/repo/pull/42.diff",
            "files_changed": ["auth/login.py", "api/users.py"],
        },
    )

    print("Run result:")
    import json
    print(json.dumps(result, indent=2))

    # 4. Assertions (for testing)
    orchestrator.assert_agent_ran("security-review")
    orchestrator.assert_task_contains("ticket", "AI-SEC-001")
    print("\nAll assertions passed!")

    # 5. Export agent definition to dict
    agent_dict = SECURITY_REVIEW_AGENT.to_dict()
    print(f"\nAgent serialised to dict with {len(agent_dict)} fields.")

    # 6. Round-trip from dict
    restored = AgentDefinition.from_dict(agent_dict)
    assert restored.name == SECURITY_REVIEW_AGENT.name
    print("Round-trip serialisation: OK")


if __name__ == "__main__":
    run_example()
