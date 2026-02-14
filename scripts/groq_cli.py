#!/usr/bin/env python3
"""
Groq CLI - Interactive terminal interface for Groq's LPU inference.

Usage:
    python scripts/groq_cli.py                          # Interactive REPL
    python scripts/groq_cli.py "What is Groq?"          # Single query
    python scripts/groq_cli.py --stream "Tell a story"  # Streaming mode
    python scripts/groq_cli.py --model llama-3.1-8b-instant "Quick answer"
    python scripts/groq_cli.py --status                 # Check connectivity
    python scripts/groq_cli.py --models                 # List available models
    echo "Explain LPUs" | python scripts/groq_cli.py    # Pipe input
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bridges.groq_bridge import DEFAULT_MODEL, GroqBridge


def parse_args():
    parser = argparse.ArgumentParser(description="Groq CLI - Ultra-fast LPU inference")
    parser.add_argument("query", nargs="?", default=None, help="Query to send")
    parser.add_argument(
        "--model", "-m", default=None, help=f"Model (default: {DEFAULT_MODEL.value})"
    )
    parser.add_argument("--stream", "-s", action="store_true", help="Stream response")
    parser.add_argument("--json", "-j", action="store_true", help="JSON response format")
    parser.add_argument("--status", action="store_true", help="Check API connectivity")
    parser.add_argument("--models", action="store_true", help="List available models")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show usage stats")
    parser.add_argument(
        "--temperature", "-t", type=float, default=0.7, help="Temperature (default: 0.7)"
    )
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens (default: 4096)")
    parser.add_argument("--system", type=str, default=None, help="System prompt")
    parser.add_argument(
        "--openai-compat", action="store_true", help="Use OpenAI SDK compatibility mode"
    )
    return parser.parse_args()


def print_status(bridge):
    status = bridge.check_status()
    if status["status"] == "connected":
        print("✅ Groq API: Connected")
        print(f"   API Key: {'set' if status['api_key_set'] else '❌ NOT SET'}")
        print(f"   Models available: {status['models_available']}")
        print(f"   Base URL: {status['base_url']}")
    else:
        print("❌ Groq API: Error")
        print(f"   Error: {status.get('error', 'Unknown')}")
        if not status["api_key_set"]:
            print("\n   Set your API key:")
            print("   export GROQ_API_KEY=your-key-here")
            print("   Get one at: https://console.groq.com/keys")


def print_models(bridge):
    try:
        models = bridge.list_models()
        print(f"📋 Available Groq Models ({len(models)} total):\n")
        for m in sorted(models, key=lambda x: x["id"]):
            print(f"  • {m['id']}")
    except Exception as e:
        print(f"❌ Error listing models: {e}")


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
    if args.stream:
        for chunk in bridge.stream_response(session, query):
            print(chunk, end="", flush=True)
        print()
    else:
        response = bridge.send_message(session, query, json_mode=args.json)
        print(response.content)
        if args.verbose and response.usage:
            print("\n--- Usage ---")
            print(f"Prompt tokens:     {response.usage.get('prompt_tokens', 'N/A')}")
            print(f"Completion tokens: {response.usage.get('completion_tokens', 'N/A')}")
            print(f"Total tokens:      {response.usage.get('total_tokens', 'N/A')}")
            if "total_time" in response.usage:
                print(f"Total time:        {response.usage['total_time']:.3f}s")
            if "completion_time" in response.usage:
                tokens = response.usage.get("completion_tokens", 0)
                time = response.usage.get("completion_time", 0)
                if time > 0:
                    print(f"Tokens/sec:        {tokens / time:.0f}")


def interactive_repl(bridge, args):
    print("🚀 Groq Interactive CLI")
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
    streaming = args.stream
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
                    session.model = cmd_parts[1]
                    print(f"✅ Model switched to: {session.model}")
                else:
                    print(f"Current model: {session.model}")
            elif cmd == "/stream":
                streaming = not streaming
                print(f"✅ Streaming: {'on' if streaming else 'off'}")
            elif cmd == "/models":
                print_models(bridge)
            elif cmd == "/status":
                print_status(bridge)
            elif cmd == "/clear":
                session.messages = []
                if session.system_prompt:
                    session.messages = [{"role": "system", "content": session.system_prompt}]
                print("✅ Conversation cleared")
            elif cmd == "/verbose":
                args.verbose = not args.verbose
                print(f"✅ Verbose: {'on' if args.verbose else 'off'}")
            elif cmd == "/help":
                print("Commands: /model <id>, /stream, /models, /status, /clear, /verbose, /quit")
            else:
                print(f"Unknown command: {cmd}. Type /help for commands.")
            continue
        print("Groq: ", end="", flush=True)
        if streaming:
            for chunk in bridge.stream_response(session, user_input):
                print(chunk, end="", flush=True)
            print()
        else:
            response = bridge.send_message(session, user_input)
            print(response.content)
            if args.verbose and response.usage:
                tokens = response.usage.get("total_tokens", "?")
                time = response.usage.get("total_time", None)
                latency = f" ({time:.3f}s)" if time else ""
                print(f"  [{tokens} tokens{latency}]")
        print()


def main():
    args = parse_args()
    bridge = GroqBridge(use_openai_compat=args.openai_compat)
    if args.status:
        print_status(bridge)
        return
    if args.models:
        print_models(bridge)
        return
    if args.query or not sys.stdin.isatty():
        single_query(bridge, args)
    else:
        interactive_repl(bridge, args)


if __name__ == "__main__":
    main()
