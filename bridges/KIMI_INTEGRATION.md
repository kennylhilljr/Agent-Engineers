# KIMI (Moonshot AI) Agent Integration

## Overview

Adds Moonshot AI's KIMI as a sub-agent in the multi-AI orchestrator. KIMI is
known for ultra-long context windows (up to 2M tokens) and strong
Chinese/English bilingual capabilities.

## Architecture

```
Orchestrator
    |
    +-- linear (Haiku)
    +-- coding (Sonnet)
    +-- github (Haiku)
    +-- slack (Haiku)
    +-- chatgpt (Haiku) --> OpenAI Bridge --> ChatGPT API
    +-- gemini (Haiku)  --> Gemini Bridge --> Gemini API
    +-- groq (Haiku)    --> Groq Bridge   --> Groq Cloud
    +-- kimi (Haiku)    --> KIMI Bridge   --> Moonshot API
                              |
                              Uses OpenAI-compatible SDK
                              (base_url: api.moonshot.cn/v1)
```

## Files

| File | Purpose |
|------|---------|
| `kimi_bridge.py` | Core bridge module using OpenAI-compatible API |
| `scripts/kimi_cli.py` | Standalone CLI with REPL, streaming, pipe support |
| `prompts/kimi_agent_prompt.md` | System prompt for the KIMI bridge agent |
| `agents/definitions.py` | `kimi` agent definition with `KIMI_AGENT` export |

## Setup

### 1. Get a Moonshot API Key

1. Go to https://platform.moonshot.cn/console/api-keys
2. Sign up / log in
3. Create an API key
4. Copy the key

### 2. Configure Environment

```bash
# Required
KIMI_API_KEY=your-moonshot-api-key
# Or: MOONSHOT_API_KEY=your-moonshot-api-key

# Optional
KIMI_MODEL=moonshot-v1-auto         # Default model
KIMI_AGENT_MODEL=haiku              # Orchestrator sub-agent model
```

### 3. Install Dependencies

```bash
pip install openai
```

The KIMI API is OpenAI-compatible, so only the `openai` package is needed.

### 4. Verify Setup

```bash
python scripts/kimi_cli.py --status
```

## Usage

### CLI (Standalone)

```bash
# Interactive REPL
python scripts/kimi_cli.py

# Single query
python scripts/kimi_cli.py --query "Explain quantum computing"

# Specific model
python scripts/kimi_cli.py --model kimi-k2

# Streaming
python scripts/kimi_cli.py --stream --query "Write a story"

# Pipe input
echo "Summarize this: $(cat README.md)" | python scripts/kimi_cli.py -q -

# Verbose (show token usage)
python scripts/kimi_cli.py --verbose --query "Hello"
```

### Programmatic (Python)

```python
from kimi_bridge import KimiBridge

bridge = KimiBridge.from_env()
session = bridge.create_session(model="moonshot-v1-auto")
response = bridge.send_message(session, "Hello!")
print(response.content)

# Async streaming
async for token in bridge.stream_response(session, "Tell me more"):
    print(token, end="", flush=True)
```

## Available Models

| Model | Best For | Context | Cost |
|-------|----------|---------|------|
| `moonshot-v1-auto` | Auto-selects optimal size | Auto | Optimized |
| `moonshot-v1-8k` | Short tasks, quick responses | 8K tokens | Low |
| `moonshot-v1-32k` | Medium documents, typical code | 32K tokens | Medium |
| `moonshot-v1-128k` | Large files, extensive analysis | 128K tokens | Higher |
| `kimi-k2` | Latest model, complex reasoning | Large | Varies |

Default: `moonshot-v1-auto` (API auto-selects optimal context size).

## When the Orchestrator Uses KIMI

- Ultra-long context analysis (>100K tokens) - analyzing entire codebases
- Bilingual Chinese/English tasks (translation, multilingual docs)
- Cross-validation with a different model family
- User explicitly requests KIMI or Moonshot models

## Acceptance Criteria

- [x] Terminal chat via Moonshot API
- [x] API key authentication
- [x] Orchestrator integration as sub-agent
- [x] Streaming responses
- [x] Access to all Moonshot models (v1-auto, 8k, 32k, 128k, k2)
- [x] Documentation complete
