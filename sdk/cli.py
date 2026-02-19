"""CLI tool for the Agent-Engineers SDK.

Commands
--------
agent-engineers init     — scaffold a new custom agent project
agent-engineers test     — run agent against MockOrchestrator locally
agent-engineers validate — lint agent.yaml / agent.json
agent-engineers publish  — upload agent to the registry API (stub)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional


_DEFAULT_AGENT_YAML = """\
name: my-custom-agent
title: My Custom Agent
description: A custom agent for the Agent-Engineers platform.
model: sonnet
version: 0.1.0
system_prompt: |
  You are a helpful AI assistant integrated into the Agent-Engineers platform.
  Complete tasks carefully and concisely.
tools:
  - Read
  - Write
  - Glob
# git_identity:
#   name: My Agent
#   email: agent@example.com
# org_id: null  # null = public agent
"""

_DEFAULT_README = """\
# My Custom Agent

A custom agent built with the Agent-Engineers SDK.

## Getting started

```bash
# Validate the agent definition
agent-engineers validate

# Test locally
agent-engineers test --task '{"ticket": "AI-001", "title": "Example task"}'

# Publish to the registry (requires running dashboard)
agent-engineers publish --api-url http://localhost:8080
```
"""


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------

def init(args: argparse.Namespace) -> int:
    """Scaffold a new custom agent project in the current directory."""
    output_dir = Path(args.output_dir) if hasattr(args, "output_dir") and args.output_dir else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    yaml_path = output_dir / "agent.yaml"
    readme_path = output_dir / "README.md"

    if yaml_path.exists() and not getattr(args, "force", False):
        print(f"[agent-engineers] {yaml_path} already exists. Use --force to overwrite.")
        return 1

    yaml_path.write_text(_DEFAULT_AGENT_YAML, encoding="utf-8")
    readme_path.write_text(_DEFAULT_README, encoding="utf-8")

    print(f"[agent-engineers] Scaffolded new agent project in {output_dir}")
    print(f"  - {yaml_path}")
    print(f"  - {readme_path}")
    print("\nNext steps:")
    print("  1. Edit agent.yaml to define your agent")
    print("  2. Run: agent-engineers validate")
    print("  3. Run: agent-engineers test")
    return 0


def _load_agent_file(file_path: Optional[str] = None):
    """Load an AgentDefinition from agent.yaml or agent.json in cwd."""
    from sdk.agent_definition import AgentDefinition

    candidates = [file_path] if file_path else ["agent.yaml", "agent.yml", "agent.json"]
    for candidate in candidates:
        p = Path(candidate)
        if p.exists():
            ext = p.suffix.lower()
            content = p.read_text(encoding="utf-8")
            if ext in (".yaml", ".yml"):
                try:
                    import yaml  # type: ignore[import]
                    data = yaml.safe_load(content)
                except ImportError:
                    print("[agent-engineers] PyYAML not installed. Run: pip install pyyaml")
                    sys.exit(1)
            else:
                data = json.loads(content)
            return AgentDefinition.from_dict(data)

    print("[agent-engineers] No agent.yaml / agent.yml / agent.json found in current directory.")
    sys.exit(1)


def validate(args: argparse.Namespace) -> int:
    """Validate agent.yaml and print any errors."""
    agent_file = getattr(args, "file", None)
    agent = _load_agent_file(agent_file)
    errors = agent.validate()

    if errors:
        print(f"[agent-engineers] Validation FAILED ({len(errors)} error(s)):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"[agent-engineers] Validation passed for agent {agent.name!r} v{agent.version}")
    return 0


def test(args: argparse.Namespace) -> int:
    """Run the agent against a MockOrchestrator."""
    from sdk.agent_definition import AgentDefinition
    from sdk.registry import AgentRegistry
    from sdk.mock_orchestrator import MockOrchestrator

    agent_file = getattr(args, "file", None)
    agent = _load_agent_file(agent_file)

    # Validate first
    errors = agent.validate()
    if errors:
        print("[agent-engineers] Agent definition has validation errors:")
        for err in errors:
            print(f"  - {err}")
        return 1

    # Build task payload
    task_json = getattr(args, "task", None) or "{}"
    try:
        task = json.loads(task_json)
    except json.JSONDecodeError as exc:
        print(f"[agent-engineers] Invalid --task JSON: {exc}")
        return 1

    registry = AgentRegistry()
    registry.register(agent)
    orchestrator = MockOrchestrator(registry)

    print(f"[agent-engineers] Running agent {agent.name!r} against MockOrchestrator...")
    result = orchestrator.run_agent(agent.name, task)

    print("[agent-engineers] Run completed.")
    print(json.dumps(result, indent=2))
    return 0


def publish(args: argparse.Namespace) -> int:
    """Upload agent definition to the registry REST API."""
    agent_file = getattr(args, "file", None)
    agent = _load_agent_file(agent_file)

    errors = agent.validate()
    if errors:
        print("[agent-engineers] Cannot publish: agent definition has validation errors:")
        for err in errors:
            print(f"  - {err}")
        return 1

    api_url = getattr(args, "api_url", None) or os.environ.get("AGENT_ENGINEERS_API_URL", "http://localhost:8080")
    org_id = getattr(args, "org_id", None)

    payload = agent.to_dict()
    if org_id:
        payload["org_id"] = org_id

    try:
        import urllib.request
        import urllib.error

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{api_url.rstrip('/')}/api/registry/agents",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            print(f"[agent-engineers] Published agent {agent.name!r} successfully.")
            print(json.dumps(body, indent=2))
            return 0

    except Exception as exc:  # noqa: BLE001
        print(f"[agent-engineers] Publish failed: {exc}")
        print("(This is a stub — ensure the dashboard REST API is running.)")
        return 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> None:
    """Main entry point dispatching subcommands."""
    parser = argparse.ArgumentParser(
        prog="agent-engineers",
        description="Agent-Engineers SDK CLI",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # --- init ---
    p_init = subparsers.add_parser("init", help="Scaffold a new custom agent project")
    p_init.add_argument("--output-dir", dest="output_dir", default=None,
                        help="Directory to scaffold into (default: current directory)")
    p_init.add_argument("--force", action="store_true",
                        help="Overwrite existing files")
    p_init.set_defaults(func=init)

    # --- validate ---
    p_validate = subparsers.add_parser("validate", help="Validate agent definition")
    p_validate.add_argument("--file", default=None,
                            help="Path to agent YAML/JSON file (default: auto-detect)")
    p_validate.set_defaults(func=validate)

    # --- test ---
    p_test = subparsers.add_parser("test", help="Run agent against MockOrchestrator")
    p_test.add_argument("--file", default=None,
                        help="Path to agent YAML/JSON file (default: auto-detect)")
    p_test.add_argument("--task", default="{}", metavar="JSON",
                        help="Task payload as JSON string (default: {})")
    p_test.set_defaults(func=test)

    # --- publish ---
    p_publish = subparsers.add_parser("publish", help="Publish agent to registry API")
    p_publish.add_argument("--file", default=None,
                           help="Path to agent YAML/JSON file (default: auto-detect)")
    p_publish.add_argument("--api-url", dest="api_url", default=None,
                           help="Dashboard API URL (default: http://localhost:8080)")
    p_publish.add_argument("--org-id", dest="org_id", default=None,
                           help="Organisation ID to publish under")
    p_publish.set_defaults(func=publish)

    args = parser.parse_args(argv)
    exit_code = args.func(args)
    sys.exit(exit_code if exit_code is not None else 0)


if __name__ == "__main__":
    main()
