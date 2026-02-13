# Google Gemini Agent Integration

## Overview

Adds Google Gemini as a sub-agent in the multi-AI orchestrator, enabling
mixed-model orchestration across Claude, ChatGPT, and Gemini from a single CLI.

## Files Added/Modified

### New Files
| File | Purpose |
|------|---------|
| `gemini_bridge.py` | Core bridge - CLI OAuth + API key + Vertex AI auth |
| `scripts/gemini_cli.py` | Standalone CLI with REPL, streaming, pipe support |
| `prompts/gemini_agent_prompt.md` | System prompt for the Gemini bridge agent |
| `setup_gemini.sh` | First-run helper: installs gemini-cli, runs OAuth |

### Modified Files
| File | Changes |
|------|---------|
| `agents/definitions.py` | Added `gemini` agent definition with `GEMINI_AGENT` export |
| `.env.example` | Added `GEMINI_AUTH_TYPE`, `GOOGLE_API_KEY`, `GEMINI_MODEL` |
| `requirements.txt` | Added `google-genai>=1.0.0` |

## Setup

### Path 1: CLI OAuth (Recommended - Zero Cost)

```bash
npm install -g @google/gemini-cli
gemini  # opens browser for OAuth
# Or: bash setup_gemini.sh

# .env:
GEMINI_AUTH_TYPE=cli-oauth
GEMINI_MODEL=gemini-2.5-flash
```

Cost: Zero per-token billing. Free tier: 60 req/min, 1000 req/day.
AI Pro/Ultra subscription removes limits.

### Path 2: API Key (Simple, Free Tier)

```bash
# Get key from https://aistudio.google.com/app/apikey
GEMINI_AUTH_TYPE=api-key
GOOGLE_API_KEY=AIza...your-key
GEMINI_MODEL=gemini-2.5-flash
```

### Path 3: Vertex AI (Enterprise)

```bash
GEMINI_AUTH_TYPE=vertex-ai
GOOGLE_CLOUD_PROJECT=my-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GEMINI_MODEL=gemini-2.5-pro
```

### Install Dependencies

```bash
pip install google-genai
```

## Usage

```bash
python scripts/gemini_cli.py                          # Interactive REPL
python scripts/gemini_cli.py --query "Hello"          # Single query
python scripts/gemini_cli.py --model gemini-2.5-pro   # Specific model
python scripts/gemini_cli.py --stream                  # Streaming
python scripts/gemini_cli.py --status                  # Check auth
echo "prompt" | python scripts/gemini_cli.py -q -      # Pipe
```

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
                              |
                              +-- CLI OAuth (gemini-cli subprocess)
                              +-- API Key (google-genai SDK)
                              +-- Vertex AI (google-genai SDK)
```

## Acceptance Criteria

- [x] User can run Gemini from terminal using Google web subscription
- [x] OAuth login flow works (browser opens, user authenticates, token saved)
- [x] NO API key required (cli-oauth mode), NO per-token charges
- [x] Gemini agent integrates with existing orchestrator as a sub-agent
- [x] Streaming responses work in terminal
- [x] Can access Gemini 2.5 Pro and Flash models via subscription
- [x] Documentation complete

## References

- [gemini-cli](https://github.com/google-gemini/gemini-cli)
- [Auth docs](https://geminicli.com/docs/get-started/authentication.html)
- [google-genai Python SDK](https://github.com/googleapis/python-genai)
- [Google AI Studio](https://aistudio.google.com)
