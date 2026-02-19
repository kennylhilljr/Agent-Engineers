#!/usr/bin/env python3
"""
Product Manager Agent Runner
=============================

Launches the Product Manager agent as a standalone session via the Claude Agent SDK.
The PM agent communicates via Slack, reads Linear backlog, and provides strategic
product intelligence.

Supports multi-provider fallback: if OpenRouter rate limits are hit during
consultation, falls back to Groq then Gemini.

Usage:
    uv run python scripts/product_manager_runner.py
    uv run python scripts/product_manager_runner.py --task "sprint-planning"
    uv run python scripts/product_manager_runner.py --task "backlog-review"
    uv run python scripts/product_manager_runner.py --task "prompt-review"
    uv run python scripts/product_manager_runner.py --task "agent-analysis"
    uv run python scripts/product_manager_runner.py --task "full-review"
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from client import create_client
from agents.definitions import create_agent_definitions

# Project directory containing .linear_project.json
PROJECT_DIR = Path(__file__).resolve().parent.parent / "generations" / "agent-dashboard"
REPO_ROOT = Path(__file__).resolve().parent.parent

# Task templates for the PM agent
TASK_TEMPLATES: dict[str, str] = {
    "full-review": """
You are running as the Product Manager agent. Your working directory is: {project_dir}
The main repository root is: {repo_root}

Perform a FULL product management review session. Do ALL of the following:

1. **Post to Slack** (channel: ai-cli-macz) that you're starting a PM review session.

2. **Backlog Review**: Query Linear for all issues in the project. Analyze:
   - Read {project_dir}/.linear_project.json for project context
   - Check which tickets are Done, In Progress, Backlog, and Todo
   - Identify stale tickets (in progress too long)
   - Flag any duplicates or obsolete tickets
   - Recommend priority ordering for the backlog

3. **Sprint Planning**: Based on the backlog state:
   - What was recently completed?
   - What should be worked on next?
   - Estimate complexity for recommended tickets
   - Identify dependencies between tickets

4. **Agent Performance**: Review the agent system:
   - Read the agent prompts in {repo_root}/prompts/ directory
   - Read {repo_root}/agents/definitions.py to understand current agent setup
   - Identify any gaps or improvements needed
   - Check if model assignments make sense

5. **Project Health**: Assess overall project state:
   - Completion rate (done vs total tickets)
   - Velocity trends
   - Any blockers or risks

6. **Post all findings to Slack** (channel: ai-cli-macz) with structured recommendations.
   Break your report into multiple messages if needed, using clear section headers.

7. **Create Linear tickets** for any action items you identify.
""",

    "backlog-review": """
You are running as the Product Manager agent. Your working directory is: {project_dir}
The main repository root is: {repo_root}

Perform a BACKLOG PRIORITIZATION review:

1. Post to Slack (channel: ai-cli-macz) that you're starting a backlog review.
2. Read {project_dir}/.linear_project.json for project context.
3. Query Linear for all issues. Analyze statuses, priorities, and descriptions.
4. Identify high-priority items, items to deprioritize, missing tickets, and scope concerns.
5. Use the RICE framework (Reach, Impact, Confidence, Effort) to justify priorities.
6. Post your prioritization review to Slack (channel: ai-cli-macz).
7. Update Linear tickets with priority changes if needed.
""",

    "sprint-planning": """
You are running as the Product Manager agent. Your working directory is: {project_dir}
The main repository root is: {repo_root}

Perform SPRINT PLANNING:

1. Post to Slack (channel: ai-cli-macz) that you're starting sprint planning.
2. Read {project_dir}/.linear_project.json for project context.
3. Query Linear for recently completed issues (Done status).
4. Query Linear for Backlog and Todo issues.
5. Check GitHub for recent PRs in the repo (kennylhilljr/Agent-Engineers).
6. Recommend the next sprint's tickets with complexity estimates.
7. Identify dependencies and risks.
8. Define success criteria for the sprint.
9. Post the sprint plan to Slack (channel: ai-cli-macz).
""",

    "prompt-review": """
You are running as the Product Manager agent. Your working directory is: {project_dir}
The main repository root is: {repo_root}

Perform a PROMPT ENGINEERING REVIEW:

1. Post to Slack (channel: ai-cli-macz) that you're starting a prompt review.
2. Read all agent prompt files in {repo_root}/prompts/ directory.
3. Read {repo_root}/agents/definitions.py to understand agent configurations.
4. For each agent prompt, evaluate:
   - Clarity and specificity of instructions
   - Whether the prompt matches the agent's tools and capabilities
   - Any gaps or unclear guidance
   - Opportunities to reduce token waste
5. Suggest specific improvements with before/after text.
6. Post your prompt review findings to Slack (channel: ai-cli-macz).
""",

    "agent-analysis": """
You are running as the Product Manager agent. Your working directory is: {project_dir}
The main repository root is: {repo_root}

Perform an AGENT PERFORMANCE ANALYSIS:

1. Post to Slack (channel: ai-cli-macz) that you're starting agent analysis.
2. Read {repo_root}/agents/definitions.py to understand all 16 agents.
3. Read {repo_root}/CLAUDE.md for project conventions.
4. Read agent prompts in {repo_root}/prompts/ for each agent.
5. Analyze:
   - Which agents have the right tools for their job?
   - Are model assignments optimal? (haiku vs sonnet vs opus)
   - Which agents overlap in capabilities?
   - Which agents are underutilized?
   - What new agents might be needed?
6. Check {repo_root}/bridges/ for AI provider integration status.
7. Post your analysis and recommendations to Slack (channel: ai-cli-macz).
""",
    "custom": """
You are running as the Product Manager agent. Your working directory is: {project_dir}
The main repository root is: {repo_root}

{custom_prompt}

Post all findings and recommendations to Slack (channel: ai-cli-macz).
""",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Product Manager Agent Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Tasks:
  full-review     Complete PM review (backlog + sprint + agents + health)
  backlog-review  Prioritize and analyze the Linear backlog
  sprint-planning Plan the next sprint based on current state
  prompt-review   Review and improve all agent prompts
  agent-analysis  Analyze agent performance and configuration
  custom          Run a custom task with --custom-prompt

Examples:
  uv run python scripts/product_manager_runner.py
  uv run python scripts/product_manager_runner.py --task sprint-planning
  uv run python scripts/product_manager_runner.py --task backlog-review --model sonnet
  uv run python scripts/product_manager_runner.py --task custom --custom-prompt "Audit design system"
        """,
    )
    parser.add_argument(
        "--task",
        choices=list(TASK_TEMPLATES.keys()),
        default="full-review",
        help="PM task to perform (default: full-review)",
    )
    parser.add_argument(
        "--model",
        choices=["haiku", "sonnet", "opus"],
        default="haiku",
        help="Claude model for orchestrator (default: haiku)",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=PROJECT_DIR,
        help=f"Project directory (default: {PROJECT_DIR})",
    )
    parser.add_argument(
        "--custom-prompt",
        type=str,
        default="",
        help="Custom task prompt (required when --task=custom)",
    )
    return parser.parse_args()


async def run_pm_session(
    task: str, model: str, project_dir: Path, custom_prompt: str = "",
) -> None:
    """Run the PM agent session."""
    print(f"{'=' * 70}")
    print(f"Product Manager Agent - Task: {task}")
    print(f"Model: {model} | Project: {project_dir}")
    print(f"{'=' * 70}\n")

    if task == "custom" and not custom_prompt:
        print("ERROR: --custom-prompt is required when --task=custom")
        sys.exit(1)

    # Build task prompt
    task_prompt = TASK_TEMPLATES[task].format(
        project_dir=project_dir,
        repo_root=REPO_ROOT,
        custom_prompt=custom_prompt,
    )

    # Create client with agent definitions
    agents = create_agent_definitions()
    client = create_client(
        project_dir=project_dir,
        model=model,
        agent_overrides=agents,
    )

    # Build the orchestrator message that delegates to PM
    orchestrator_message = f"""
You are the orchestrator. Delegate the following task to the `product_manager` agent.

The product_manager agent has access to Slack, Linear, GitHub, file operations, and Bash.
It should communicate all findings via Slack (channel: ai-cli-macz).

Task for the product_manager agent:
{task_prompt}

IMPORTANT: Delegate this ENTIRE task to the product_manager agent using the Task tool.
Do not attempt to do this work yourself — pass it to the product_manager agent.
"""

    print("Launching PM agent session...\n")

    async with client:
        await client.query(orchestrator_message)

        from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock

        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="", flush=True)
                    elif isinstance(block, ToolUseBlock):
                        print(f"\n[Tool: {block.name}]", flush=True)

    print(f"\n\n{'=' * 70}")
    print("PM session complete. Check Slack (ai-cli-macz) for results.")
    print(f"{'=' * 70}")


def main() -> None:
    args = parse_args()
    asyncio.run(run_pm_session(
        task=args.task,
        model=args.model,
        project_dir=args.project_dir,
        custom_prompt=args.custom_prompt,
    ))


if __name__ == "__main__":
    main()
