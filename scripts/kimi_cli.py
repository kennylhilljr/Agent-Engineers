#!/usr/bin/env python3
"""
KIMI CLI Wrapper - Terminal interface for Moonshot AI's KIMI models.

Usage:
    python scripts/kimi_cli.py                        # Interactive REPL
    python scripts/kimi_cli.py --query "Hello"        # Single query
    python scripts/kimi_cli.py --model kimi-k2        # Use specific model
    python scripts/kimi_cli.py --stream               # Enable streaming
    python scripts/kimi_cli.py --status               # Check auth
    echo "prompt" | python scripts/kimi_cli.py -q -   # Read from stdin
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bridges.kimi_bridge import (
    KimiBridge,
    KimiModel,
    get_available_models,
    print_auth_status,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KIMI CLI - Moonshot AI")
    parser.add_argument(
        "-q",
        "--query",
        type=str,
        default=None,
        help="Single query mode. Use '-' to read from stdin.",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default=None,
        choices=get_available_models(),
        help="KIMI model (default: from KIMI_MODEL env or moonshot-v1-auto)",
    )
    parser.add_argument(
        "-s", "--stream", action="store_true", default=False, help="Enable streaming responses"
    )
    parser.add_argument("--system", type=str, default=None, help="System prompt to set context")
    parser.add_argument("--status", action="store_true", help="Show authentication status and exit")
    parser.add_argument("--verbose", action="store_true", help="Show token usage and model info")
    return parser.parse_args()


def run_repl(bridge: KimiBridge, args: argparse.Namespace) -> None:
    session = bridge.create_session(model=args.model, system_prompt=args.system)
    print(f"KIMI CLI - Model: {session.model.value}")
    print("Type 'exit' or 'quit' to end. 'clear' to reset conversation.")
    print("-" * 50)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break
        if user_input.lower() == "clear":
            session = bridge.create_session(model=args.model, system_prompt=args.system)
            print("Conversation cleared.")
            continue
        if user_input.lower() == "status":
            print_auth_status()
            continue
        if user_input.lower().startswith("model "):
            new_model = user_input.split(" ", 1)[1].strip()
            session.model = KimiModel.from_string(new_model)
            print(f"Model changed to: {session.model.value}")
            continue

        try:
            if args.stream:
                print("\nKIMI: ", end="", flush=True)
                asyncio.run(_stream_response(bridge, session, user_input))
                print()
            else:
                response = bridge.send_message(session, user_input)
                print(f"\nKIMI: {response.content}")
                if args.verbose and response.usage:
                    print(
                        f"\n  [{response.model} | "
                        f"tokens: {response.usage.get('total_tokens', '?')}]"
                    )
        except Exception as e:
            print(f"\nError: {e}")
            print("Try 'status' to check your configuration.")


async def _stream_response(bridge, session, message: str) -> None:
    async for token in bridge.stream_response(session, message):
        print(token, end="", flush=True)


def run_single_query(bridge: KimiBridge, args: argparse.Namespace) -> None:
    query = args.query
    if query == "-":
        query = sys.stdin.read().strip()
        if not query:
            print("Error: No input from stdin", file=sys.stderr)
            sys.exit(1)
    session = bridge.create_session(model=args.model, system_prompt=args.system)
    try:
        if args.stream:
            asyncio.run(_stream_response(bridge, session, query))
            print()
        else:
            response = bridge.send_message(session, query)
            print(response.content)
            if args.verbose and response.usage:
                print(f"\n---\nModel: {response.model}", file=sys.stderr)
                print(f"Tokens: {response.usage.get('total_tokens', '?')}", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    args = parse_args()
    if args.status:
        print_auth_status()
        print()
        print(f"Available models: {', '.join(get_available_models())}")
        return
    try:
        bridge = KimiBridge.from_env()
    except (ValueError, ImportError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("\nSetup:", file=sys.stderr)
        print(
            "  1. Get API key from: https://platform.moonshot.cn/console/api-keys", file=sys.stderr
        )
        print("  2. Set KIMI_API_KEY=your-key in .env", file=sys.stderr)
        print("  3. pip install openai", file=sys.stderr)
        sys.exit(1)
    if args.query is not None:
        run_single_query(bridge, args)
    else:
        run_repl(bridge, args)


if __name__ == "__main__":
    main()
