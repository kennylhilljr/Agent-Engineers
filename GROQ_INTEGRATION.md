# Groq SDK Integration

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
│ coding  │ github   │ slack    │ linear │ groq   │
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
