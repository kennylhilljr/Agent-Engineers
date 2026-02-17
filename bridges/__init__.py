"""
Bridge Modules for External AI Providers
==========================================

Each bridge wraps an external AI provider's API to provide a unified interface
for the multi-AI orchestrator: OpenAI (ChatGPT), Google (Gemini), Groq,
Moonshot (KIMI), and Codeium (Windsurf).
"""

from bridges.base_bridge import BaseBridge, BridgeResponse

__all__ = ["BaseBridge", "BridgeResponse"]
