#!/usr/bin/env python3
"""
OpenRouter CLI - Interactive terminal interface for OpenRouter's multi-model gateway.

Usage:
    python scripts/openrouter_cli.py                              # Interactive REPL
    python scripts/openrouter_cli.py "What is OpenRouter?"        # Single query
    python scripts/openrouter_cli.py --stream "Tell a story"      # Streaming mode
    python scripts/openrouter_cli.py --model deepseek-r1 "Solve this"
    python scripts/openrouter_cli.py --status                     # Check connectivity
    python scripts/openrouter_cli.py --models                     # List available models
    echo "Explain transformers" | python scripts/openrouter_cli.py  # Pipe input
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bridges.openrouter_bridge import DEFAULT_MODEL, OpenRouterBridge


def parse_args():
    parser = argparse.ArgumentParser(
        description="OpenRouter CLI - Multi-model AI gateway (free tier)"
    )
    parser.add_argument("query", nargs="?", default=None, help="Query to send")
    parser.add_argument(
        "--model", "-m", default=None, help=f"Model (default: {DEFAULT_MODEL.value})"
    )
    parser.add_argument("--stream", "-s", action="store_true", help="Stream response")
    parser.add_argument("--status", action="store_true", help="Check API connectivity")
    parser.add_argument("--models", action="store_true", help="List available free models")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show usage stats")
    parser.add_argument(
        "--temperature", "-t", type=float, default=0.7, help="Temperature (default: 0.7)"
    )
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens (default: 4096)")
    parser.add_argument("--system", type=str, default=None, help="System prompt")
    return parser.parse_args()


def print_status():
    from bridges.openrouter_bridge import print_auth_status

    print_auth_status()


def print_models():
    from bridges.openrouter_bridge import get_available_models

    models = get_available_models()
    print(f"Available OpenRouter Free Models ({len(models)} total):\n")
    for m in models:
        print(f"  - {m}")
    print("\nNote: Use 'openrouter/free' for auto-routing to best available free model.")


def single_query(bridge, args):
    query = args.query
    if query is None and not sys.stdin.isatty():
        query = sys.stdin.read().strip()
    if not query:
        print("No query provided. Use --help for usage.")
        sys.exit(1)
    session = bridge.create_session(
        model=args.model,
        system_prompt=args.system,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    response = bridge.send_message(session, query)
    print(response.content)
    if args.verbose and response.usage:
        print("\n--- Usage ---")
        print(f"Prompt tokens:     {response.usage.get('prompt_tokens', 'N/A')}")
        print(f"Completion tokens: {response.usage.get('completion_tokens', 'N/A')}")
        print(f"Total tokens:      {response.usage.get('total_tokens', 'N/A')}")


def interactive_repl(bridge, args):
    print("OpenRouter Interactive CLI")
    print(f"   Model: {args.model or DEFAULT_MODEL.value}")
    print(f"   Stream: {'on' if args.stream else 'off'}")
    print("   Commands: /model <id>, /stream, /models, /status, /quit")
    print()
    session = bridge.create_session(
        model=args.model,
        system_prompt=args.system,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if not user_input:
            continue
        if user_input.startswith("/"):
            cmd_parts = user_input.split(maxsplit=1)
            cmd = cmd_parts[0].lower()
            if cmd in ("/quit", "/exit"):
                print("Goodbye!")
                break
            elif cmd == "/model":
                if len(cmd_parts) > 1:
                    from bridges.openrouter_bridge import OpenRouterModel

                    session.model = OpenRouterModel.from_string(cmd_parts[1])
                    print(f"Model switched to: {session.model}")
                else:
                    print(f"Current model: {session.model}")
            elif cmd == "/stream":
                args.stream = not args.stream
                print(f"Streaming: {'on' if args.stream else 'off'}")
            elif cmd == "/models":
                print_models()
            elif cmd == "/status":
                print_status()
            elif cmd == "/clear":
                session.messages = []
                print("Conversation cleared")
            elif cmd == "/verbose":
                args.verbose = not args.verbose
                print(f"Verbose: {'on' if args.verbose else 'off'}")
            elif cmd == "/help":
                print("Commands: /model <id>, /stream, /models, /status, /clear, /verbose, /quit")
            else:
                print(f"Unknown command: {cmd}. Type /help for commands.")
            continue
        print("OpenRouter: ", end="", flush=True)
        response = bridge.send_message(session, user_input)
        print(response.content)
        if args.verbose and response.usage:
            tokens = response.usage.get("total_tokens", "?")
            print(f"  [{tokens} tokens]")
        print()


def main():
    args = parse_args()
    if args.status:
        print_status()
        return
    if args.models:
        print_models()
        return
    bridge = OpenRouterBridge.from_env()
    if args.query or not sys.stdin.isatty():
        single_query(bridge, args)
    else:
        interactive_repl(bridge, args)


if __name__ == "__main__":
    main()
