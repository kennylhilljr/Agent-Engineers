# ChatGPT Agent Integration

## Overview

Adds OpenAI ChatGPT as a sub-agent in the multi-AI orchestrator, enabling
mixed-model orchestration across Claude and ChatGPT from a single CLI.

## Files Added/Modified

### New Files
| File | Purpose |
|------|---------|
| `openai_bridge.py` | Core bridge module with dual auth (Codex OAuth + Session Token) |
| `model_router.py` | Routes tasks to Claude or ChatGPT |
| `scripts/chatgpt_cli.py` | Standalone CLI wrapper with REPL, streaming |
| `prompts/chatgpt_agent_prompt.md` | System prompt for the ChatGPT bridge agent |

### Modified Files
| File | Changes |
|------|---------|
| `agents/definitions.py` | Added `chatgpt` agent definition with `CHATGPT_AGENT` export |
| `.env.example` | Added ChatGPT config vars |
| `requirements.txt` | Added `openai>=1.0.0`, `httpx>=0.25.0` |

## Setup

### Path 1: Codex OAuth (Recommended)
```bash
npm install -g @openai/codex
codex  # Opens browser for OAuth sign-in
# Add to .env:
CHATGPT_AUTH_TYPE=codex-oauth
```

### Path 2: Session Token (Zero API Cost)
```bash
# Extract __Secure-next-auth.session-token from browser cookies at chatgpt.com
# Add to .env:
CHATGPT_AUTH_TYPE=session-token
CHATGPT_SESSION_TOKEN=eyJxxxxxxxxxx
```

### Install Dependencies
```bash
pip install openai httpx
```

## Usage

### Standalone CLI
```bash
python scripts/chatgpt_cli.py                    # Interactive REPL
python scripts/chatgpt_cli.py --query "Hello"    # Single query
python scripts/chatgpt_cli.py --model o3-mini    # Specific model
python scripts/chatgpt_cli.py --stream            # Streaming
python scripts/chatgpt_cli.py --status            # Check auth
echo "prompt" | python scripts/chatgpt_cli.py -q - # Pipe
```

### Programmatic
```python
from openai_bridge import OpenAIBridge

bridge = OpenAIBridge.from_env()
session = bridge.create_session(model="gpt-4o")
response = bridge.send_message(session, "Hello!")
print(response.content)
```

## Architecture
```
Orchestrator + ModelRouter
    |
    +-- linear (Haiku)
    +-- coding (Sonnet)
    +-- github (Haiku)
    +-- slack (Haiku)
    +-- chatgpt (Haiku) --> OpenAI Bridge --> ChatGPT API
                              |
                              +-- Codex OAuth (API key)
                              +-- Session Token (zero cost)
```

## Models: gpt-4o (default), o1, o3-mini, o4-mini

## Acceptance Criteria
- [x] Terminal chat using web subscription
- [x] Browser sign-in auth (Codex OAuth)
- [x] Minimal cost (session token alternative)
- [x] Orchestrator integration as sub-agent
- [x] Streaming responses
- [x] Access to gpt-4o/o1/o3-mini models
- [x] Documentation complete
