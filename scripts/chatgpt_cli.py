#!/usr/bin/env python3
"""
ChatGPT CLI Wrapper - Terminal interface for ChatGPT using the OpenAI bridge module.

Usage:
    python scripts/chatgpt_cli.py                    # Interactive REPL
    python scripts/chatgpt_cli.py --query "Hello"    # Single query
    python scripts/chatgpt_cli.py --model o3-mini    # Use specific model
    python scripts/chatgpt_cli.py --stream            # Enable streaming
    python scripts/chatgpt_cli.py --status            # Check auth
    echo "prompt" | python scripts/chatgpt_cli.py -q - # Read from stdin
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bridges.openai_bridge import (
    ChatGPTModel,
    OpenAIBridge,
    get_available_models,
    print_auth_status,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ChatGPT CLI")
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
        help="ChatGPT model to use (default: from CHATGPT_MODEL env or gpt-4o)",
    )
    parser.add_argument(
        "-s",
        "--stream",
        action="store_true",
        default=False,
        help="Enable streaming responses (codex-oauth only)",
    )
    parser.add_argument("--system", type=str, default=None, help="System prompt to set context")
    parser.add_argument("--status", action="store_true", help="Show authentication status and exit")
    parser.add_argument("--verbose", action="store_true", help="Show token usage and model info")
    return parser.parse_args()


def run_repl(bridge: OpenAIBridge, args: argparse.Namespace) -> None:
    session = bridge.create_session(model=args.model, system_prompt=args.system)
    print(f"ChatGPT CLI - Model: {session.model.value}")
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
            try:
                session.model = ChatGPTModel.from_string(new_model)
                print(f"Model changed to: {session.model.value}")
            except Exception:
                print(f"Unknown model: {new_model}")
                print(f"Available: {', '.join(get_available_models())}")
            continue

        try:
            if args.stream:
                print("\nChatGPT: ", end="", flush=True)
                asyncio.run(_stream_response(bridge, session, user_input))
                print()
            else:
                response = bridge.send_message(session, user_input)
                print(f"\nChatGPT: {response.content}")
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


def run_single_query(bridge: OpenAIBridge, args: argparse.Namespace) -> None:
    query = args.query
    if query == "-":
        query = sys.stdin.read().strip()
        if not query:
            print("Error: No input received from stdin", file=sys.stderr)
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
        from bridges.openai_bridge import check_codex_cli_installed

        print(f"Codex CLI installed: {'yes' if check_codex_cli_installed() else 'no'}")
        return
    try:
        bridge = OpenAIBridge.from_env()
    except (ValueError, ImportError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("\nSetup options:", file=sys.stderr)
        print("  1. Install Codex CLI: npm install -g @openai/codex", file=sys.stderr)
        print("     Then run: codex (to sign in with ChatGPT)", file=sys.stderr)
        print("  2. Or set CHATGPT_AUTH_TYPE=session-token and", file=sys.stderr)
        print("     CHATGPT_SESSION_TOKEN=<your-token>", file=sys.stderr)
        sys.exit(1)
    if args.query is not None:
        run_single_query(bridge, args)
    else:
        run_repl(bridge, args)


if __name__ == "__main__":
    main()
