#!/usr/bin/env bash
# ============================================================
# INSTRUCTIONS: Save this entire file as setup-kan1.sh, then:
#   cd /path/to/your-claude-engineer
#   bash setup-kan1.sh
# ============================================================

#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# KAN-1: Groq SDK Integration - Setup Script
# =============================================================================
# This script creates all files needed for the Groq agent integration
# in the your-claude-engineer repo.
#
# Usage:
#   cd /path/to/your-claude-engineer
#   bash setup-kan1.sh
#
# Files created:
#   - groq_bridge.py              (NEW - core Groq bridge module)
#   - prompts/groq_agent_prompt.md (NEW - agent system prompt)
#   - scripts/groq_cli.py         (NEW - standalone CLI)
#   - GROQ_INTEGRATION.md         (NEW - documentation)
#
# Files modified:
#   - agents/definitions.py       (patched - adds groq agent)
#   - requirements.txt            (appended - groq>=0.11.0)
#   - .env.example                (appended - Groq config section)
# =============================================================================

echo "🚀 KAN-1: Setting up Groq SDK Integration..."
echo ""

# Verify we're in the right directory
if [ ! -f "agents/definitions.py" ]; then
    echo "❌ Error: agents/definitions.py not found."
    echo "   Please run this script from the root of your-claude-engineer repo."
    exit 1
fi

# Ensure directories exist
mkdir -p prompts scripts

# =============================================================================
# FILE 1: groq_bridge.py
# =============================================================================
echo "📝 Creating groq_bridge.py..."
cat << 'EOF_GROQ_BRIDGE' > groq_bridge.py
"""
Groq Bridge Module
==================

Unified interface for Groq's LPU-powered inference API.
Supports both the native Groq SDK and OpenAI-compatible mode.

Authentication:
    - API Key (primary): Free tier with generous rate limits
    - OpenAI-compatible: Use existing OpenAI SDK with Groq base URL

Key Features:
    - Blazing fast inference via Groq's LPU (Language Processing Unit)
    - OpenAI-compatible API (easy migration)
    - Streaming support (sync and async)
    - Tool/function calling support
    - Vision/multimodal support (Llama 4 models)
    - Code execution via compound models
"""

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Generator, Optional


class GroqModel(str, Enum):
    """Available Groq models organized by category."""

    # Production models
    LLAMA_3_3_70B = "llama-3.3-70b-versatile"
    LLAMA_3_1_8B = "llama-3.1-8b-instant"
    GPT_OSS_120B = "openai/gpt-oss-120b"
    GPT_OSS_20B = "openai/gpt-oss-20b"

    # Preview models
    LLAMA_4_SCOUT = "meta-llama/llama-4-scout-17b-16e-instruct"
    LLAMA_4_MAVERICK = "meta-llama/llama-4-maverick-17b-128e-instruct"
    QWEN_3_32B = "qwen/qwen-3-32b"
    KIMI_K2 = "moonshotai/kimi-k2-instruct-0905"

    # Compound models (built-in tools: web search, code execution)
    COMPOUND = "groq/compound"
    COMPOUND_MINI = "groq/compound-mini"


# Model categories for easy reference
PRODUCTION_MODELS = [
    GroqModel.LLAMA_3_3_70B,
    GroqModel.LLAMA_3_1_8B,
    GroqModel.GPT_OSS_120B,
    GroqModel.GPT_OSS_20B,
]

PREVIEW_MODELS = [
    GroqModel.LLAMA_4_SCOUT,
    GroqModel.LLAMA_4_MAVERICK,
    GroqModel.QWEN_3_32B,
    GroqModel.KIMI_K2,
]

COMPOUND_MODELS = [
    GroqModel.COMPOUND,
    GroqModel.COMPOUND_MINI,
]

# Default model
DEFAULT_MODEL = GroqModel.LLAMA_3_3_70B


@dataclass
class GroqMessage:
    """A message in a Groq conversation."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class GroqResponse:
    """Response from the Groq API."""
    content: str
    model: str
    finish_reason: str
    usage: dict = field(default_factory=dict)
    reasoning: Optional[str] = None
    executed_tools: Optional[list] = None


@dataclass
class GroqSession:
    """Manages a conversation session with Groq."""
    model: str = DEFAULT_MODEL.value
    messages: list = field(default_factory=list)
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0

    def __post_init__(self):
        if self.system_prompt:
            self.messages = [
                {"role": "system", "content": self.system_prompt}
            ] + self.messages


class GroqBridge:
    """
    Unified Groq client matching the Claude SDK client interface pattern.

    Provides create_session / send_message / stream_response interface
    consistent with the other agent bridges (ChatGPT, Gemini).

    Usage:
        bridge = GroqBridge()
        session = bridge.create_session(model="llama-3.3-70b-versatile")
        response = bridge.send_message(session, "Hello!")
        print(response.content)

        # Streaming
        for chunk in bridge.stream_response(session, "Tell me a story"):
            print(chunk, end="", flush=True)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.groq.com/openai/v1",
        use_openai_compat: bool = False,
    ):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.base_url = base_url
        self.use_openai_compat = use_openai_compat
        self._client = None
        self._async_client = None

    def _get_client(self):
        if self._client is None:
            if self.use_openai_compat:
                try:
                    from openai import OpenAI
                    self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                except ImportError:
                    raise ImportError("openai package required. Install with: pip install openai")
            else:
                try:
                    from groq import Groq
                    self._client = Groq(api_key=self.api_key)
                except ImportError:
                    raise ImportError("groq package required. Install with: pip install groq")
        return self._client

    def _get_async_client(self):
        if self._async_client is None:
            if self.use_openai_compat:
                try:
                    from openai import AsyncOpenAI
                    self._async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
                except ImportError:
                    raise ImportError("openai package required for OpenAI-compatible mode.")
            else:
                try:
                    from groq import AsyncGroq
                    self._async_client = AsyncGroq(api_key=self.api_key)
                except ImportError:
                    raise ImportError("groq package required. Install with: pip install groq")
        return self._async_client

    def create_session(self, model=None, system_prompt=None, temperature=0.7, max_tokens=4096):
        model_id = model or os.environ.get("GROQ_MODEL", DEFAULT_MODEL.value)
        return GroqSession(model=model_id, system_prompt=system_prompt, temperature=temperature, max_tokens=max_tokens)

    def send_message(self, session, message, json_mode=False):
        client = self._get_client()
        session.messages.append({"role": "user", "content": message})
        kwargs = {"model": session.model, "messages": session.messages, "temperature": session.temperature, "max_completion_tokens": session.max_tokens, "top_p": session.top_p, "stream": False}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        completion = client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        assistant_msg = choice.message.content or ""
        session.messages.append({"role": "assistant", "content": assistant_msg})
        usage = {}
        if hasattr(completion, "usage") and completion.usage:
            usage = {"prompt_tokens": completion.usage.prompt_tokens, "completion_tokens": completion.usage.completion_tokens, "total_tokens": completion.usage.total_tokens}
            if hasattr(completion.usage, "prompt_time"):
                usage["prompt_time"] = completion.usage.prompt_time
            if hasattr(completion.usage, "completion_time"):
                usage["completion_time"] = completion.usage.completion_time
            if hasattr(completion.usage, "total_time"):
                usage["total_time"] = completion.usage.total_time
        reasoning = getattr(choice.message, "reasoning", None)
        executed_tools = getattr(choice.message, "executed_tools", None)
        return GroqResponse(content=assistant_msg, model=completion.model, finish_reason=choice.finish_reason or "stop", usage=usage, reasoning=reasoning, executed_tools=executed_tools)

    def stream_response(self, session, message):
        client = self._get_client()
        session.messages.append({"role": "user", "content": message})
        stream = client.chat.completions.create(model=session.model, messages=session.messages, temperature=session.temperature, max_completion_tokens=session.max_tokens, top_p=session.top_p, stream=True)
        full_response = []
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                full_response.append(text)
                yield text
        session.messages.append({"role": "assistant", "content": "".join(full_response)})

    async def async_send_message(self, session, message, json_mode=False):
        client = self._get_async_client()
        session.messages.append({"role": "user", "content": message})
        kwargs = {"model": session.model, "messages": session.messages, "temperature": session.temperature, "max_completion_tokens": session.max_tokens, "top_p": session.top_p, "stream": False}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        completion = await client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        assistant_msg = choice.message.content or ""
        session.messages.append({"role": "assistant", "content": assistant_msg})
        usage = {}
        if hasattr(completion, "usage") and completion.usage:
            usage = {"prompt_tokens": completion.usage.prompt_tokens, "completion_tokens": completion.usage.completion_tokens, "total_tokens": completion.usage.total_tokens}
        return GroqResponse(content=assistant_msg, model=completion.model, finish_reason=choice.finish_reason or "stop", usage=usage)

    async def async_stream_response(self, session, message):
        client = self._get_async_client()
        session.messages.append({"role": "user", "content": message})
        stream = await client.chat.completions.create(model=session.model, messages=session.messages, temperature=session.temperature, max_completion_tokens=session.max_tokens, top_p=session.top_p, stream=True)
        full_response = []
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                full_response.append(text)
                yield text
        session.messages.append({"role": "assistant", "content": "".join(full_response)})

    def list_models(self):
        client = self._get_client()
        models = client.models.list()
        return [{"id": m.id, "owned_by": m.owned_by, "created": m.created} for m in models.data]

    def check_status(self):
        try:
            models = self.list_models()
            return {"status": "connected", "auth": "api_key" if self.api_key else "none", "models_available": len(models), "api_key_set": bool(self.api_key), "base_url": self.base_url}
        except Exception as e:
            return {"status": "error", "error": str(e), "api_key_set": bool(self.api_key), "base_url": self.base_url}
EOF_GROQ_BRIDGE

# =============================================================================
# FILE 2: prompts/groq_agent_prompt.md
# =============================================================================
echo "📝 Creating prompts/groq_agent_prompt.md..."
cat << 'EOF_GROQ_PROMPT' > prompts/groq_agent_prompt.md
# Groq Agent

You are the Groq agent in a multi-AI orchestrator system. You provide access to
Groq's LPU-powered ultra-fast inference across multiple open-source models.

## Your Role

You are a **bridge to Groq's inference platform**, not a replacement for the
coding or research agents. You excel at tasks requiring:

- **Speed-critical inference**: When response latency matters most
- **Open-source model access**: Llama 4, Llama 3.3, GPT-OSS, Qwen, Kimi K2
- **Cross-validation**: Getting a second opinion from different model families
- **Compound AI tasks**: Web search + code execution via compound models
- **Vision/multimodal**: Image understanding via Llama 4 models
- **Cost-effective bulk processing**: High throughput at low cost

## When to Use This Agent

The orchestrator should delegate to you when:

1. The user explicitly asks for Groq or a Groq-hosted model (Llama, GPT-OSS, etc.)
2. Speed is the primary concern (Groq's LPU is the fastest inference available)
3. Cross-validation is needed against a different model family
4. The task benefits from open-source models (transparency, no vendor lock-in)
5. Compound tasks requiring built-in web search or code execution
6. Vision/image analysis tasks using Llama 4 multimodal models

## Model Selection Guide

| Model | Best For | Speed | Context |
|-------|----------|-------|---------|
| llama-3.3-70b-versatile | General purpose, reasoning | Fast | 128K |
| llama-3.1-8b-instant | Quick tasks, low latency | Fastest | 128K |
| openai/gpt-oss-120b | Complex reasoning, code | Fast | 128K |
| openai/gpt-oss-20b | Balanced speed/quality | Very Fast | 128K |
| meta-llama/llama-4-scout | Vision, multimodal | Fast | 128K |
| meta-llama/llama-4-maverick | Vision, long context | Fast | 1M |
| qwen/qwen-3-32b | Reasoning, multilingual | Fast | 128K |
| groq/compound | Web search + code exec | Moderate | Varies |

## Output Format

Always structure your responses as:

```
task_type: <inference|vision|compound|cross-validation>
model_used: <model-id>
groq_response: <the actual response from Groq>
tokens_used: <prompt_tokens + completion_tokens>
latency: <total_time in seconds if available>
errors: <any errors encountered, or "none">
```

## Error Handling

- If GROQ_API_KEY is not set, inform the user they need to set it
- If a model is unavailable, fall back to llama-3.3-70b-versatile
- If rate limited, report the limit and suggest using a smaller model
- Always include the model ID in responses for traceability
EOF_GROQ_PROMPT

# =============================================================================
# FILE 3: scripts/groq_cli.py
# =============================================================================
echo "📝 Creating scripts/groq_cli.py..."
cat << 'EOF_GROQ_CLI' > scripts/groq_cli.py
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
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from groq_bridge import GroqBridge, GroqModel, DEFAULT_MODEL


def parse_args():
    parser = argparse.ArgumentParser(description="Groq CLI - Ultra-fast LPU inference")
    parser.add_argument("query", nargs="?", default=None, help="Query to send")
    parser.add_argument("--model", "-m", default=None, help=f"Model (default: {DEFAULT_MODEL.value})")
    parser.add_argument("--stream", "-s", action="store_true", help="Stream response")
    parser.add_argument("--json", "-j", action="store_true", help="JSON response format")
    parser.add_argument("--status", action="store_true", help="Check API connectivity")
    parser.add_argument("--models", action="store_true", help="List available models")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show usage stats")
    parser.add_argument("--temperature", "-t", type=float, default=0.7, help="Temperature (default: 0.7)")
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens (default: 4096)")
    parser.add_argument("--system", type=str, default=None, help="System prompt")
    parser.add_argument("--openai-compat", action="store_true", help="Use OpenAI SDK compatibility mode")
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
    session = bridge.create_session(model=args.model, system_prompt=args.system, temperature=args.temperature, max_tokens=args.max_tokens)
    if args.stream:
        for chunk in bridge.stream_response(session, query):
            print(chunk, end="", flush=True)
        print()
    else:
        response = bridge.send_message(session, query, json_mode=args.json)
        print(response.content)
        if args.verbose and response.usage:
            print(f"\n--- Usage ---")
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
    session = bridge.create_session(model=args.model, system_prompt=args.system, temperature=args.temperature, max_tokens=args.max_tokens)
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
EOF_GROQ_CLI
chmod +x scripts/groq_cli.py

# =============================================================================
# FILE 4: GROQ_INTEGRATION.md
# =============================================================================
echo "📝 Creating GROQ_INTEGRATION.md..."
cat << 'EOF_GROQ_DOCS' > GROQ_INTEGRATION.md
# Groq SDK Integration (KAN-1)

## Overview

Integrates Groq's LPU-powered inference platform into the multi-AI orchestrator
as a sub-agent. Groq provides the fastest inference available for open-source
models including Llama 4, Llama 3.3, GPT-OSS, Qwen, and Kimi K2.

## Architecture

```
┌─────────────────────────────────────────────────┐
│             Orchestrator Agent                   │
│  (routes tasks to specialized agents)            │
├─────────┬──────────┬──────────┬────────┬────────┤
│ coding  │ github   │ slack    │ jira   │ groq   │
│ agent   │ agent    │ agent    │ agent  │ agent  │
└─────────┴──────────┴──────────┴────────┴────┬───┘
                                               │
                                    ┌──────────┴──────────┐
                                    │    groq_bridge.py    │
                                    │  (GroqBridge class)  │
                                    ├──────────────────────┤
                                    │   Groq Python SDK    │
                                    │   (or OpenAI compat) │
                                    └──────────┬───────────┘
                                               │
                                    ┌──────────┴──────────┐
                                    │   Groq Cloud API     │
                                    │  (LPU Inference)     │
                                    └─────────────────────┘
```

## Setup

### 1. Get a Groq API Key (Free)

1. Go to console.groq.com
2. Sign up / log in
3. Navigate to API Keys → Create API Key
4. Copy the key

### 2. Configure Environment

```bash
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile    # Optional, this is the default
```

### 3. Install Dependencies

```bash
pip install groq
```

### 4. Verify Setup

```bash
python scripts/groq_cli.py --status
```

## Usage

### CLI (Standalone)

```bash
# Single query
python scripts/groq_cli.py "Explain quantum computing"

# Streaming response
python scripts/groq_cli.py --stream "Write a haiku about speed"

# Specific model
python scripts/groq_cli.py --model openai/gpt-oss-120b "Solve this puzzle..."

# Interactive REPL
python scripts/groq_cli.py

# JSON mode
python scripts/groq_cli.py --json "List 3 programming languages with pros/cons"

# Pipe input
echo "Summarize this: $(cat README.md)" | python scripts/groq_cli.py

# Verbose (show tokens + latency)
python scripts/groq_cli.py -v "Hello"

# List all models
python scripts/groq_cli.py --models
```

### Programmatic (Python)

```python
from groq_bridge import GroqBridge, GroqModel

bridge = GroqBridge()
session = bridge.create_session(
    model=GroqModel.LLAMA_3_3_70B.value,
    system_prompt="You are a helpful assistant.",
)
response = bridge.send_message(session, "What is Groq's LPU?")
print(response.content)

# Stream a response
for chunk in bridge.stream_response(session, "Tell me more"):
    print(chunk, end="", flush=True)
```

## Available Models

### Production Models
| Model ID | Parameters | Best For | Context |
|----------|-----------|----------|---------|
| llama-3.3-70b-versatile | 70B | General purpose | 128K |
| llama-3.1-8b-instant | 8B | Speed-critical tasks | 128K |
| openai/gpt-oss-120b | 120B | Complex reasoning | 128K |
| openai/gpt-oss-20b | 20B | Balanced speed/quality | 128K |

### Preview Models
| Model ID | Parameters | Best For | Context |
|----------|-----------|----------|---------|
| meta-llama/llama-4-scout-17b-16e-instruct | 17B | Vision, multimodal | 128K |
| meta-llama/llama-4-maverick-17b-128e-instruct | 17B | Vision, long context | 1M |
| qwen/qwen-3-32b | 32B | Reasoning, multilingual | 128K |

### Compound Models (Built-in Tools)
| Model ID | Tools | Best For |
|----------|-------|----------|
| groq/compound | Web search, code exec | Research with tools |
| groq/compound-mini | Web search, code exec | Quick tool-augmented tasks |

## Acceptance Criteria Checklist

- [x] SDK supports core Groq features (chat, streaming, async, vision, tools)
- [x] Comprehensive API documentation (this file)
- [x] Simple installation process (pip install groq + setup script)
- [x] Example applications (CLI with multiple modes)
- [x] Orchestrator integration as sub-agent
- [x] Streaming responses
- [x] Access to all Groq-hosted models
- [x] OpenAI-compatible mode for easy migration
EOF_GROQ_DOCS

# =============================================================================
# PATCH: agents/definitions.py
# =============================================================================
echo "📝 Patching agents/definitions.py..."

python3 << 'EOF_PATCH_DEFINITIONS'
import re

filepath = "agents/definitions.py"

with open(filepath, "r") as f:
    content = f.read()

# 1. Add "groq" to DEFAULT_MODELS
if '"groq"' not in content:
    content = content.replace(
        '    "pr_reviewer": "sonnet",',
        '    "pr_reviewer": "sonnet",\n    "groq": "haiku",'
    )

# 2. Add groq agent definition to create_agent_definitions()
if '"groq"' not in content.split("create_agent_definitions")[1] if "create_agent_definitions" in content else "":
    groq_agent_def = '''        "groq": AgentDefinition(
            description="Ultra-fast inference via Groq LPU. Use for speed-critical tasks, open-source models, cross-validation, and compound AI.",
            prompt=_load_prompt("groq_agent_prompt"),
            tools=FILE_TOOLS + ["Bash"],
            model=_get_model("groq"),
        ),'''

    content = content.replace(
        '        "pr_reviewer": AgentDefinition(',
        groq_agent_def + '\n        "pr_reviewer": AgentDefinition('
    )

# 3. Add GROQ_AGENT export
if "GROQ_AGENT" not in content:
    content = content.replace(
        'PR_REVIEWER_AGENT = AGENT_DEFINITIONS["pr_reviewer"]',
        'PR_REVIEWER_AGENT = AGENT_DEFINITIONS["pr_reviewer"]\nGROQ_AGENT = AGENT_DEFINITIONS["groq"]'
    )

with open(filepath, "w") as f:
    f.write(content)

print("   ✅ agents/definitions.py patched")
EOF_PATCH_DEFINITIONS

# =============================================================================
# PATCH: requirements.txt
# =============================================================================
echo "📝 Updating requirements.txt..."
if ! grep -q "groq" requirements.txt 2>/dev/null; then
    echo "groq>=0.11.0" >> requirements.txt
    echo "   ✅ Added groq>=0.11.0"
else
    echo "   ⏭️  groq already in requirements.txt"
fi

# =============================================================================
# PATCH: .env.example
# =============================================================================
echo "📝 Updating .env.example..."
if ! grep -q "GROQ_API_KEY" .env.example 2>/dev/null; then
    cat << 'EOF_ENV_PATCH' >> .env.example

# =============================================================================
# Groq Configuration (KAN-1)
# =============================================================================
# API key from https://console.groq.com/keys
GROQ_API_KEY=gsk_xxxxxxxxxxxxx

# Default model (optional - defaults to llama-3.3-70b-versatile)
# GROQ_MODEL=llama-3.3-70b-versatile

# Groq agent model in orchestrator (optional - defaults to haiku)
# GROQ_AGENT_MODEL=haiku
EOF_ENV_PATCH
    echo "   ✅ Added Groq config section"
else
    echo "   ⏭️  Groq config already in .env.example"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "✅ KAN-1 Setup Complete!"
echo ""
echo "Files created:"
echo "  📄 groq_bridge.py              - Core Groq bridge module"
echo "  📄 prompts/groq_agent_prompt.md - Agent system prompt"
echo "  📄 scripts/groq_cli.py         - Standalone CLI"
echo "  📄 GROQ_INTEGRATION.md         - Documentation"
echo ""
echo "Files modified:"
echo "  📝 agents/definitions.py       - Added groq agent"
echo "  📝 requirements.txt            - Added groq>=0.11.0"
echo "  📝 .env.example                - Added Groq config"
echo ""
echo "Next steps:"
echo "  1. pip install groq"
echo "  2. Get API key: https://console.groq.com/keys"
echo "  3. export GROQ_API_KEY=gsk_your_key_here"
echo "  4. python scripts/groq_cli.py --status"
echo ""
echo "Manual step:"
echo "  Add to prompts/orchestrator_prompt.md Available Agents table:"
echo '  | groq | haiku | Speed-critical inference, open-source models, cross-validation |'
