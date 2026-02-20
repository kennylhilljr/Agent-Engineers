# API Documentation

Auto-generated API documentation for Agent-Engineers.

## Modules

- [BaseBridge](bridges.md) - Abstract base class for AI provider bridges
- [AgentConfig](config.md) - Centralized configuration management
- [Protocols](protocols.md) - typing.Protocol interface definitions
- [Exceptions](exceptions.md) - Custom exception hierarchy

## Regenerating

To regenerate this documentation from the live source code, run:

```bash
bash scripts/generate_api_docs.sh
```

This requires `pdoc>=14.0.0` (already listed in `requirements.txt`).

## Overview

Agent-Engineers is a multi-provider AI agent orchestration system. The
following diagram shows how the key modules interact:

```
AgentConfig  ──────────────────────────────────────────────┐
   │                                                        │
   └─► get_config() / reset_config()                        │
                                                            │
BaseBridge ─────── send_task(task) ───────► BridgeResponse │
   │                                                        │
   ├── OpenAIBridge                                         │
   ├── GeminiBridge                                         │
   ├── GroqBridge                                           │
   ├── KimiBridge                                           │
   └── WindsurfBridge                                       │
                                                            │
Protocols (BridgeProtocol, ConfigProtocol, …)  ─── typing ─┘

Exceptions
   AgentError
   ├── BridgeError
   ├── SecurityError
   ├── ConfigurationError
   ├── TimeoutError
   ├── RateLimitError
   └── AuthenticationError
```
