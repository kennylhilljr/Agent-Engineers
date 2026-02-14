#!/usr/bin/env python3
"""
Windsurf CLI - Terminal interface for Codeium Windsurf IDE in headless mode.

Usage:
    python scripts/windsurf_cli.py --task "Implement login page"  # Submit task
    python scripts/windsurf_cli.py --task "Fix bug" --workspace ./my-project
    python scripts/windsurf_cli.py --mode docker --task "Refactor auth"
    python scripts/windsurf_cli.py --status                       # Check setup
    echo "Add tests" | python scripts/windsurf_cli.py             # Pipe input
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bridges.windsurf_bridge import WindsurfBridge, print_auth_status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Windsurf CLI - Codeium IDE headless mode")
    parser.add_argument(
        "--task",
        "-t",
        type=str,
        default=None,
        help="Coding task to submit. Use '-' to read from stdin.",
    )
    parser.add_argument(
        "--workspace", "-w", type=str, default=None, help="Workspace directory (default: temp dir)"
    )
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        default=None,
        choices=["cli", "docker"],
        help="Execution mode (default: from WINDSURF_MODE env or cli)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Task timeout in seconds (default: from WINDSURF_TIMEOUT env or 300)",
    )
    parser.add_argument("--status", action="store_true", help="Show Windsurf setup status and exit")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output including changed files"
    )
    return parser.parse_args()


def run_task(bridge: WindsurfBridge, args: argparse.Namespace) -> None:
    task = args.task
    if task == "-":
        task = sys.stdin.read().strip()
    if not task and not sys.stdin.isatty():
        task = sys.stdin.read().strip()
    if not task:
        print("Error: No task provided. Use --task or pipe input.", file=sys.stderr)
        sys.exit(1)

    session = bridge.create_session(
        workspace=args.workspace,
        task_description="Execute coding task via CLI",
    )
    print(f"Windsurf CLI - Mode: {session.mode.value}")
    print(f"Workspace: {session.workspace}")
    print("Submitting task...")
    print("-" * 50)

    response = bridge.send_task(session, task)

    if response.exit_code == 0:
        print(f"\nResult:\n{response.content}")
    else:
        print(f"\nTask failed (exit code {response.exit_code}):")
        print(response.content)

    if args.verbose or response.files_changed:
        if response.files_changed:
            print(f"\nFiles changed ({len(response.files_changed)}):")
            for f in response.files_changed:
                print(f"  - {f}")
        else:
            print("\nNo files changed.")

    sys.exit(0 if response.exit_code == 0 else 1)


def interactive_mode(bridge: WindsurfBridge, args: argparse.Namespace) -> None:
    session = bridge.create_session(
        workspace=args.workspace,
        task_description="Interactive Windsurf session",
    )
    print(f"Windsurf Interactive CLI - Mode: {session.mode.value}")
    print(f"Workspace: {session.workspace}")
    print("Enter coding tasks. Type 'exit' or 'quit' to end.")
    print("-" * 50)

    while True:
        try:
            task = input("\nTask: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if not task:
            continue
        if task.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break
        if task.lower() == "status":
            print_auth_status()
            continue

        print("Running...", flush=True)
        response = bridge.send_task(session, task)
        if response.exit_code == 0:
            print(f"\nResult:\n{response.content}")
        else:
            print(f"\nFailed (exit code {response.exit_code}):\n{response.content}")
        if response.files_changed:
            print(f"\nFiles changed: {', '.join(response.files_changed)}")


def main() -> None:
    args = parse_args()

    if args.status:
        print_auth_status()
        return

    # Apply CLI overrides to env before creating bridge
    if args.mode:
        os.environ["WINDSURF_MODE"] = args.mode
    if args.timeout:
        os.environ["WINDSURF_TIMEOUT"] = str(args.timeout)

    try:
        bridge = WindsurfBridge.from_env()
    except (ValueError, ImportError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("\nSetup:", file=sys.stderr)
        print("  CLI mode: Install Windsurf from https://codeium.com/windsurf", file=sys.stderr)
        print("  Docker mode: Set WINDSURF_MODE=docker in .env", file=sys.stderr)
        sys.exit(1)

    if args.task is not None:
        run_task(bridge, args)
    elif not sys.stdin.isatty():
        args.task = "-"
        run_task(bridge, args)
    else:
        interactive_mode(bridge, args)


if __name__ == "__main__":
    main()
