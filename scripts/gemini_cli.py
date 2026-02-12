#!/usr/bin/env python3
"""
Gemini CLI Wrapper - Terminal interface for Google Gemini.

Usage:
    python scripts/gemini_cli.py                      # Interactive REPL
    python scripts/gemini_cli.py --query "Hello"      # Single query
    python scripts/gemini_cli.py --model gemini-2.5-pro  # Specific model
    python scripts/gemini_cli.py --stream              # Streaming
    python scripts/gemini_cli.py --status              # Check auth
    echo "prompt" | python scripts/gemini_cli.py -q -  # Read from stdin
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gemini_bridge import (
    GeminiModel, GeminiBridge, get_available_models, print_auth_status,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemini CLI")
    parser.add_argument("-q", "--query", type=str, default=None,
        help="Single query mode. Use '-' to read from stdin.")
    parser.add_argument("-m", "--model", type=str, default=None,
        choices=get_available_models(),
        help="Gemini model (default: from GEMINI_MODEL env or gemini-2.5-flash)")
    parser.add_argument("-s", "--stream", action="store_true", default=False,
        help="Enable streaming responses (api-key/vertex-ai only)")
    parser.add_argument("--system", type=str, default=None,
        help="System prompt to set context")
    parser.add_argument("--status", action="store_true",
        help="Show authentication status and exit")
    parser.add_argument("--verbose", action="store_true",
        help="Show token usage and model info")
    return parser.parse_args()


def run_repl(bridge: GeminiBridge, args: argparse.Namespace) -> None:
    session = bridge.create_session(model=args.model, system_prompt=args.system)
    print(f"Gemini CLI - Model: {session.model.value}")
    print(f"Auth: {bridge.auth_type.value}")
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
            session.model = GeminiModel.from_string(new_model)
            print(f"Model changed to: {session.model.value}")
            continue
        try:
            if args.stream:
                print("\nGemini: ", end="", flush=True)
                asyncio.run(_stream_response(bridge, session, user_input))
                print()
            else:
                response = bridge.send_message(session, user_input)
                print(f"\nGemini: {response.content}")
                if args.verbose and response.usage:
                    print(f"\n  [{response.model} | tokens: {response.usage.get('total_tokens', '?')}]")
        except Exception as e:
            print(f"\nError: {e}")
            print("Try 'status' to check your configuration.")


async def _stream_response(bridge, session, message: str) -> None:
    async for token in bridge.stream_response(session, message):
        print(token, end="", flush=True)


def run_single_query(bridge: GeminiBridge, args: argparse.Namespace) -> None:
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
        from gemini_bridge import check_gemini_cli_installed
        print(f"gemini-cli installed: {'yes' if check_gemini_cli_installed() else 'no'}")
        return
    try:
        bridge = GeminiBridge.from_env()
    except (ValueError, ImportError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("\nSetup options:", file=sys.stderr)
        print("  1. npm install -g @google/gemini-cli && gemini (OAuth)", file=sys.stderr)
        print("  2. Set GEMINI_AUTH_TYPE=api-key and GOOGLE_API_KEY=...", file=sys.stderr)
        sys.exit(1)
    if args.query is not None:
        run_single_query(bridge, args)
    else:
        run_repl(bridge, args)


if __name__ == "__main__":
    main()
