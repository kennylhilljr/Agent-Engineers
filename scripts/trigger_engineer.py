#!/usr/bin/env python3
"""
Trigger script for Agent-Engineers from LibreChat.
Usage: python scripts/trigger_engineer.py --project-name "my-project" --task "Build a todo app"
"""

import argparse
import os
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Trigger Agent-Engineers")
    parser.add_argument("--project-name", required=True, help="Name for the project")
    parser.add_argument("--task", required=True, help="Task description for the engineer")
    parser.add_argument("--max-iterations", type=int, default=10, help="Max iterations")
    parser.add_argument(
        "--model", default="sonnet", choices=["haiku", "sonnet", "opus"], help="Model to use"
    )

    args = parser.parse_args()

    # Get the repo root (parent of scripts/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)

    # Write the task to specs/app_spec.txt
    app_spec_path = os.path.join(repo_root, "specs", "app_spec.txt")
    with open(app_spec_path, "w") as f:
        f.write(args.task)

    print("🚀 Starting Agent-Engineers")
    print(f"   Project: {args.project_name}")
    print(f"   Task: {args.task[:100]}...")
    print(f"   Model: {args.model}")
    print(f"   Max iterations: {args.max_iterations}")

    # Activate venv and run the autonomous agent
    venv_python = os.path.join(repo_root, "venv", "bin", "python")
    demo_script = os.path.join(script_dir, "autonomous_agent_demo.py")

    cmd = [
        venv_python,
        demo_script,
        "--project-dir",
        args.project_name,
        "--max-iterations",
        str(args.max_iterations),
        "--model",
        args.model,
    ]

    try:
        result = subprocess.run(cmd, cwd=repo_root, capture_output=False)
        return result.returncode
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
